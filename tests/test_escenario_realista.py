"""Tests del escenario realista: generador, reglas con contexto, hipótesis y priorización."""
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion import priorizacion
from deteccion.datos import cargar_dataset
from deteccion.hipotesis import HIPOTESIS, contrastar_hipotesis
from deteccion.modelo import ids_con_anomalia_de_comportamiento
from deteccion.reglas import leer_fecha, normalizar_dominio, reglas_del_dataset
from generator_pipeline_maestro import (
    CATALOGO_LEGITIMOS,
    PERFILES_VEHICULO,
    TIPOS_POR_ESCENARIO,
    GeneradorMaestro,
)

ARCHIVOS = ["flota", "estaciones", "telemetria", "telemetria_diaria", "consumo", "solicitudes",
            "facturacion", "facturacion_detalle", "contratos", "transferencias", "ground_truth", "casos_legitimos",
            "excepciones_odometro"]


def generar(directorio, seed=42, n_flota=200):
    resultado = GeneradorMaestro(n_flota=n_flota, seed=seed, output_dir=directorio, escenario="realista").ejecutar()
    assert resultado["exito"], resultado.get("error")
    return directorio


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    return cargar_dataset(generar(tmp_path_factory.mktemp("realista")))


@pytest.fixture(scope="module")
def alertas(dataset):
    return reglas_del_dataset(dataset)


def _contraste(dataset, alertas):
    return contrastar_hipotesis(alertas, dataset["ground_truth"], dataset["casos_legitimos"],
                                dataset["facturacion_detalle"])


# --- Generador --------------------------------------------------------------

def test_reproducible_con_la_misma_semilla(tmp_path):
    def huella(d):
        return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.glob("*.csv"))}
    a, b = huella(generar(tmp_path / "a", n_flota=60)), huella(generar(tmp_path / "b", n_flota=60))
    assert a == b
    assert set(a) == {f"{n}.csv" for n in ARCHIVOS}


def test_estan_todos_los_tipos_de_anomalia_y_de_caso_legitimo(dataset):
    assert set(dataset["ground_truth"]["tipo_anomalia"]) == set(TIPOS_POR_ESCENARIO["realista"])
    assert set(dataset["casos_legitimos"]["tipo_caso"]) == set(CATALOGO_LEGITIMOS)


def test_etiquetas_referencian_registros_existentes_y_no_se_superponen(dataset):
    ids = {"consumo": set(dataset["consumo"]["id"]),
           "facturacion": set(dataset["facturacion"]["numero_factura"]),
           "facturacion_detalle": set(dataset["facturacion_detalle"]["numero_linea"]),
           "solicitudes": set(dataset["solicitudes"]["id"]),
           "telemetria": set(dataset["telemetria"]["Alias"]),
           "contrato_mes": {f"CTO-{c}|{m}" for c, m in zip(dataset["consumo"]["contrato"],
                                                           pd.to_datetime(dataset["consumo"]["fecha"]).dt.to_period("M"))}}
    for tabla_etiquetas in [dataset["ground_truth"], dataset["casos_legitimos"]]:
        for tabla, grupo in tabla_etiquetas.groupby("tabla"):
            assert set(grupo["id_registro"]) <= ids[tabla], tabla
    anomalas = set(dataset["ground_truth"]["id_registro"])
    assert not anomalas & set(dataset["casos_legitimos"]["id_registro"])


def test_prevalencia_de_anomalias_de_comportamiento_es_baja(dataset):
    tasa = len(ids_con_anomalia_de_comportamiento(dataset["ground_truth"])) / len(dataset["consumo"])
    assert 0.003 < tasa < 0.03


def test_cargas_limpias_no_superan_el_tanque(dataset):
    consumo = dataset["consumo"]
    capacidad = consumo["vehiculo_id"].map(dataset["flota"].set_index("Matricula")["CapacidadTanque"])
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    limpias = ~consumo["id"].isin(etiquetadas)
    assert (consumo.loc[limpias, "litros"] <= capacidad[limpias]).all()


def test_rendimiento_de_cargas_limpias_coincide_con_el_perfil_del_vehiculo(dataset):
    consumo, flota = dataset["consumo"].copy(), dataset["flota"]
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    consumo["fecha"] = pd.to_datetime(consumo["fecha"])
    consumo = consumo.sort_values(["vehiculo_id", "fecha", "id"])
    consumo["km"] = consumo.groupby("vehiculo_id")["odometro"].diff()
    limpias = consumo[~consumo["id"].isin(etiquetadas) & consumo["km"].notna()]
    tipo = limpias["vehiculo_id"].map(flota.set_index("Matricula")["TipoVehiculo"])
    mediana = (limpias["km"] / limpias["litros"]).groupby(tipo).median()
    for t, valor in mediana.items():
        minimo, maximo = PERFILES_VEHICULO[t][1]
        assert minimo * 0.8 <= valor <= maximo * 1.2, t


def test_vehiculos_inactivos_solo_cargan_de_forma_anomala(dataset):
    consumo, flota = dataset["consumo"], dataset["flota"]
    inactivos = flota[flota["Estado"] != "EN SERVICIO"].set_index("Matricula")["FechaEstado"]
    desde = pd.to_datetime(consumo["vehiculo_id"].map(inactivos))
    posteriores = set(consumo.loc[pd.to_datetime(consumo["fecha"]) >= desde, "id"])
    gt = dataset["ground_truth"]
    esperadas = set(gt.loc[gt["tipo_anomalia"] == "CARGA_VEHICULO_INACTIVO", "id_registro"])
    duplicados = set(gt.loc[gt["tipo_anomalia"] == "DUPLICADO", "id_registro"])
    assert posteriores - duplicados == esperadas


def test_gps_solo_de_vehiculos_con_dispositivo(dataset):
    assert set(dataset["telemetria_diaria"]["Placa"]) <= set(dataset["telemetria"]["Placa"])
    assert set(dataset["telemetria"]["Placa"]) <= set(dataset["flota"]["Dominio"])
    assert (dataset["telemetria_diaria"]["km_gps"] >= 0).all()


# --- Circuito registro interno -> carga -> factura -------------------------

def test_cada_carga_limpia_tiene_su_pedido_rendido_previo(dataset):
    consumo, registro = dataset["consumo"].copy(), dataset["solicitudes"].copy()
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    limpias = consumo[~consumo["id"].isin(etiquetadas)].copy()
    limpias["instante"] = pd.to_datetime(limpias["fecha"]) + pd.to_timedelta(limpias["hora"])
    registro["instante"] = leer_fecha(registro["fecha"]) + pd.to_timedelta(registro["hora"])
    pares = limpias.merge(registro[(registro["rendido"] == "SI") & (registro["anulado"] == "NO")],
                          on="vehiculo_id", suffixes=("", "_reg"))
    minutos = (pares["instante"] - pares["instante_reg"]).dt.total_seconds() / 60
    validas = pares[minutos.between(5, 90) & (pares["litros_cargados"].round(2) == pares["litros"].round(2))]
    assert set(validas["id"]) == set(limpias["id"])


def test_registro_interno_calibrado_con_la_fuente(dataset):
    registro, consumo = dataset["solicitudes"], dataset["consumo"]
    assert registro["fecha"].str.fullmatch(r"\d{2}/\d{2}/\d{4}").all()  # DD/MM/AAAA, como en la fuente
    assert leer_fecha(registro["fecha"]).notna().all()
    assert 0.97 < (registro["rendido"] == "SI").mean() < 1.0
    assert 0.05 < (registro["estacion_servicio"] == "ESTACION AJENA").mean() < 0.09
    assert 0.003 < (registro["anulado"] == "SI").mean() < 0.02
    personales = consumo[consumo["tipo_identificacion"] == "DNI"]
    assert 0.005 < len(personales) / len(consumo) < 0.02 and personales["dominio"].isna().all()



def test_facturas_limpias_suman_sus_lineas(dataset):
    lineas = dataset["facturacion_detalle"].groupby("numero_factura")["importe"].sum()
    facturas = dataset["facturacion"].set_index("numero_factura")
    diferencia = (facturas["total_monto"] - lineas.reindex(facturas.index)).abs()
    gt = dataset["ground_truth"]
    infladas = set(gt.loc[gt["tipo_anomalia"] == "TOTAL_INFLADO", "id_registro"])
    assert set(diferencia[diferencia > 0.05].index) == infladas


def test_lineas_referencian_cargas_reales_salvo_las_inexistentes(dataset):
    lineas = dataset["facturacion_detalle"]
    combustible = lineas[lineas["concepto"] == "COMBUSTIBLE"]
    sin_carga = set(combustible.loc[~combustible["referencia_consumo"].isin(dataset["consumo"]["id"]), "numero_linea"])
    gt = dataset["ground_truth"]
    assert sin_carga == set(gt.loc[gt["tipo_anomalia"] == "LINEA_SIN_CONSUMO", "id_registro"])


def test_cada_carga_real_se_factura_al_menos_una_vez(dataset):
    gt = dataset["ground_truth"]
    reales = set(dataset["consumo"]["id"]) - set(gt.loc[gt["tipo_anomalia"] == "DUPLICADO", "id_registro"])
    assert reales <= set(dataset["facturacion_detalle"]["referencia_consumo"])


def test_facturacion_por_contrato_a_precio_de_empresa(dataset):
    facturas, lineas, consumo = dataset["facturacion"], dataset["facturacion_detalle"], dataset["consumo"]
    assert not facturas.duplicated(["contrato", "periodo", "producto"]).any()
    assert set(facturas["producto"]) == {"DIESEL", "NAFTA"}
    etiquetadas = set(dataset["ground_truth"]["id_registro"])
    limpias = lineas[(lineas["concepto"] == "COMBUSTIBLE") & ~lineas["numero_linea"].isin(etiquetadas)]
    precio_surtidor = limpias["referencia_consumo"].map(consumo.set_index("id")["precio_unitario"])
    assert ((limpias["precio_unitario"] / precio_surtidor).round(2) == 0.98).all()
    sin_pdf = facturas["total_pdf"].isna().mean()
    assert 0.05 < sin_pdf < 0.3
    con_pdf = facturas.dropna(subset=["total_pdf"])
    con_pdf = con_pdf[~con_pdf["numero_factura"].isin(etiquetadas)]
    assert (con_pdf["total_pdf"] == con_pdf["total_monto"]).all()


def test_telemetria_de_los_moviles_de_baja(dataset):
    flota, telemetria = dataset["flota"], dataset["telemetria"]
    estado = telemetria["Placa"].map(flota.set_index("Dominio")["Estado"])
    de_baja = telemetria[estado.str.contains("BAJA", na=False)]
    activos = set(dataset["ground_truth"].query("tipo_anomalia == 'DISPOSITIVO_ACTIVO_EN_BAJA'")["id_registro"])
    en_deposito = de_baja[~de_baja["Alias"].isin(activos)]
    assert len(en_deposito) >= 3 and (en_deposito["Grupo"] == "BAJA / REEMPLAZOS").all()
    assert (en_deposito["Estado"] == "OFFLINE").all()
    assert (telemetria.loc[telemetria["Alias"].isin(activos), "Grupo"] != "BAJA / REEMPLAZOS").all()
    assert not (telemetria.loc[~estado.str.contains("BAJA", na=False), "Grupo"] == "BAJA / REEMPLAZOS").any()


def test_flota_calibrada_con_la_fuente(dataset):
    import re

    flota, telemetria = dataset["flota"], dataset["telemetria"]
    estados = flota["Estado"].value_counts(normalize=True)
    assert set(estados.index) == {"EN SERVICIO", "FUERA DE SERVICIO", "TRAMITE EN BAJA"}
    assert 0.4 < estados["EN SERVICIO"] < 0.65 and 0.2 < estados["TRAMITE EN BAJA"] < 0.5
    con_gps = flota["Dominio"].isin(telemetria["Placa"]).groupby(flota["Estado"]).mean()
    assert con_gps["EN SERVICIO"] > 0.65 and con_gps["TRAMITE EN BAJA"] < 0.15
    # Formatos públicos, siempre marcados como sintéticos (empiezan con Z, serie no asignada)
    assert flota["Dominio"].str.fullmatch(r"Z[A-Z]\d{3}[A-Z]{2}|ZZ[A-Z]\d{3}|Z\d{3}[A-Z]{3}").all()
    assert flota["Dominio"].is_unique


def test_contratos_tarjetas_y_cupo(dataset):
    flota, consumo, contratos = dataset["flota"], dataset["consumo"], dataset["contratos"]
    transferencias = dataset["transferencias"]
    assert list(contratos["indice"]) == [1, 2, 3, 4, 5, 6]
    assert set(flota["NumeroContrato"]) <= set(contratos["indice"])
    assert (consumo["contrato"] == consumo["vehiculo_id"].map(flota.set_index("Matricula")["NumeroContrato"])).all()
    assert (flota["Cupo"] == flota["CapacidadTanque"]).all() and (flota["LimiteLitros"] > flota["CapacidadTanque"]).all()
    # Ejecución media del cupo total cercana a la de la fuente (~93%) y transferencias entre contratos distintos
    mes = pd.to_datetime(consumo["fecha"]).dt.to_period("M")
    ejecucion = (consumo.groupby(mes)["importe_total"].sum() / contratos["limite_mensual"].sum()).iloc[:-1]
    assert 0.75 < ejecucion.mean() < 1.0
    assert (transferencias["contrato_origen"] != transferencias["contrato_destino"]).all()
    assert (transferencias["monto"] > 0).all()


def test_dominios_con_otro_formato_corresponden_a_su_vehiculo(dataset):
    legitimos = dataset["casos_legitimos"]
    con_formato = legitimos[legitimos["tipo_caso"] == "DOMINIO_CON_FORMATO"]
    consumo = dataset["consumo"].set_index("id").loc[con_formato["id_registro"]]
    assert 0.002 < len(con_formato) / len(dataset["consumo"]) < 0.01  # calibrado con la fuente: ~0,5%
    dominio_real = dataset["flota"].set_index("Matricula")["Dominio"]
    assert (normalizar_dominio(consumo["dominio"]).values == consumo["vehiculo_id"].map(dominio_real).values).all()
    assert not consumo["dominio"].isin(dominio_real).any()  # tal como llegan, no vinculan
    assert not set(con_formato["id_registro"]) & set(dataset["ground_truth"]["id_registro"])


# --- Reglas e hipótesis -----------------------------------------------------

def test_todas_las_reglas_con_contexto_emiten_alertas(alertas):
    assert set(priorizacion.REGLAS_CONTEXTO) <= set(alertas["regla"])


def test_las_hipotesis_se_sostienen(dataset, alertas):
    _, veredictos = _contraste(dataset, alertas)
    assert list(veredictos["hipotesis"]) == [h["codigo"] for h in HIPOTESIS]
    assert (veredictos["veredicto"] == "Se sostiene").all(), veredictos[["hipotesis", "f1_ingenua", "f1_contexto"]]


def test_el_contexto_reduce_las_falsas_alarmas_por_casos_legitimos(dataset, alertas):
    _, veredictos = _contraste(dataset, alertas)
    assert veredictos["fp_legitimos_contexto"].sum() < veredictos["fp_legitimos_ingenua"].sum() / 5


# --- Priorización -----------------------------------------------------------

@pytest.fixture(scope="module")
def puntajes(dataset):
    variables, etiqueta = priorizacion.datos_de_entrenamiento(semillas=[1001, 1002], n_flota=120)
    modelo = priorizacion.entrenar_supervisado(variables, etiqueta)
    return priorizacion.puntuar(dataset, modelo)


def test_combinado_prioriza_mejor_que_las_reglas_ingenuas(dataset, puntajes):
    curva = priorizacion.curva_de_esfuerzo(puntajes[0], dataset["ground_truth"], dataset["casos_legitimos"], maximo=100)
    en50 = curva[curva["revisadas"] == 50].set_index("metodo")
    assert en50.loc["Combinado", "encontradas"] > en50.loc["Reglas ingenuas", "encontradas"]
    assert en50.loc["Combinado", "legitimos_revisados"] < en50.loc["Reglas ingenuas", "legitimos_revisados"]


def test_la_cola_de_revision_explica_cada_caso(dataset, puntajes):
    pun, variables, alertas_ = puntajes
    cola = priorizacion.cola_de_revision(pun, "Combinado", dataset["consumo"], variables, alertas_, cantidad=20)
    assert len(cola) == 20 and list(cola["prioridad"]) == list(range(1, 21))
    assert (cola["motivos"].str.len() + cola["reglas"].str.len() > 0).all()
