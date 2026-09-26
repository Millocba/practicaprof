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
from deteccion.reglas import detectar_carga_sin_autorizacion, ejecutar_reglas, leer_fecha, normalizar_dominio
from generator_pipeline_maestro import (
    CATALOGO_LEGITIMOS,
    PERFILES_VEHICULO,
    TIPOS_POR_ESCENARIO,
    GeneradorMaestro,
)

ARCHIVOS = ["flota", "estaciones", "telemetria", "telemetria_diaria", "consumo", "solicitudes",
            "facturacion", "facturacion_detalle", "ground_truth", "casos_legitimos"]


def generar(directorio, seed=42, n_flota=200):
    resultado = GeneradorMaestro(n_flota=n_flota, seed=seed, output_dir=directorio, escenario="realista").ejecutar()
    assert resultado["exito"], resultado.get("error")
    return directorio


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    return cargar_dataset(generar(tmp_path_factory.mktemp("realista")))


@pytest.fixture(scope="module")
def alertas(dataset):
    return ejecutar_reglas(dataset["flota"], dataset["consumo"], dataset["estaciones"], dataset["telemetria_diaria"],
                           dataset["solicitudes"], dataset["facturacion"], dataset["facturacion_detalle"])


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
           "facturacion_detalle": set(dataset["facturacion_detalle"]["numero_linea"])}
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


# --- Circuito solicitud -> carga -> factura ---------------------------------

def test_cada_carga_limpia_tiene_su_solicitud_aprobada_previa(dataset):
    consumo, solicitudes = dataset["consumo"].copy(), dataset["solicitudes"].copy()
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    consumo["fecha"] = pd.to_datetime(consumo["fecha"])
    solicitudes["fecha_solicitud"] = leer_fecha(solicitudes["fecha_solicitud"])
    limpias = consumo[~consumo["id"].isin(etiquetadas)]
    pares = limpias.merge(solicitudes[solicitudes["estado"] == "APROBADA"], on="vehiculo_id", suffixes=("", "_sol"))
    dias = (pares["fecha"] - pares["fecha_solicitud"]).dt.days
    validas = pares[dias.between(0, 2) & (pares["litros_autorizados"] >= pares["litros"])]
    assert set(validas["id"]) == set(limpias["id"])


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


def test_dominios_con_otro_formato_corresponden_a_su_vehiculo(dataset):
    legitimos = dataset["casos_legitimos"]
    con_formato = legitimos[legitimos["tipo_caso"] == "DOMINIO_CON_FORMATO"]
    consumo = dataset["consumo"].set_index("id").loc[con_formato["id_registro"]]
    assert 0.002 < len(con_formato) / len(dataset["consumo"]) < 0.01  # calibrado con la fuente: ~0,5%
    dominio_real = dataset["flota"].set_index("Matricula")["Dominio"]
    assert (normalizar_dominio(consumo["dominio"]).values == consumo["vehiculo_id"].map(dominio_real).values).all()
    assert not consumo["dominio"].isin(dominio_real).any()  # tal como llegan, no vinculan
    assert not set(con_formato["id_registro"]) & set(dataset["ground_truth"]["id_registro"])


def test_fechas_de_solicitud_en_dos_formatos_se_leen_todas(dataset):
    fechas = dataset["solicitudes"]["fecha_solicitud"]
    otro_formato = fechas.str.fullmatch(r"\d{2}/\d{2}/\d{4}")
    assert 0.1 < otro_formato.mean() < 0.2
    assert (otro_formato | fechas.str.fullmatch(r"\d{4}-\d{2}-\d{2}")).all()
    assert leer_fecha(fechas).notna().all()


def test_h8_no_depende_del_formato_de_las_fechas(dataset):
    solicitudes = dataset["solicitudes"]
    iso = solicitudes.assign(fecha_solicitud=leer_fecha(solicitudes["fecha_solicitud"]).dt.strftime("%Y-%m-%d"))
    mezcladas = detectar_carga_sin_autorizacion(dataset["consumo"], solicitudes, aceptar_posterior=True)
    uniformes = detectar_carga_sin_autorizacion(dataset["consumo"], iso, aceptar_posterior=True)
    assert set(mezcladas["id_registro"]) == set(uniformes["id_registro"])


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
