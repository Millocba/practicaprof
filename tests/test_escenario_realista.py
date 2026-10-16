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
            "excepciones_odometro", "observaciones_alertas"]


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


def test_cargas_limpias_no_superan_la_tolerancia_del_tanque(dataset):
    consumo = dataset["consumo"]
    capacidad = consumo["vehiculo_id"].map(dataset["flota"].set_index("Matricula")["CapacidadTanque"])
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    limpias = ~consumo["id"].isin(etiquetadas)
    assert (consumo.loc[limpias, "litros"] <= capacidad[limpias] * 1.02).all()


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


def test_origen_de_la_transaccion_calibrado_con_la_fuente(dataset):
    consumo = dataset["consumo"]
    assert set(consumo["origen_transaccion"]) == {"POSNET", "CONTINGENCIA"}
    assert 0.008 < (consumo["origen_transaccion"] == "CONTINGENCIA").mean() < 0.016   # fuente: 1,2%


def test_doble_cobro_repite_una_carga_habitual_y_se_factura(dataset, alertas):
    consumo, gt = dataset["consumo"].set_index("id"), dataset["ground_truth"]
    dobles = gt[gt["tipo_anomalia"] == "DOBLE_COBRO"]
    assert len(dobles) >= 5 and (dobles["hipotesis"] == "H13").all()
    assert set(consumo.loc[dobles["id_registro"], "origen_transaccion"]) == {"CONTINGENCIA"}
    # La regla con contexto encuentra todas esas transacciones. Una contingencia legítima solo se confunde si,
    # con el decimal corrido, sus litros coinciden por azar con los de una carga cercana: pocas y nunca con
    # los mismos litros
    doble_cobro = alertas[alertas["regla"] == "doble_cobro"].set_index("id_registro")
    assert set(dobles["id_registro"]) <= set(doble_cobro.index)
    contingencias = set(consumo.index[consumo["origen_transaccion"] == "CONTINGENCIA"])
    legitimas = set(dataset["casos_legitimos"].query("tipo_caso == 'CONTINGENCIA'")["id_registro"])
    assert contingencias == set(dobles["id_registro"]) | legitimas
    confundidas = set(doble_cobro.index) - set(dobles["id_registro"])
    assert confundidas <= legitimas and len(confundidas) <= 0.05 * len(legitimas)
    assert doble_cobro.loc[list(confundidas), "detalle"].str.contains("decimal mal colocado").all()
    # Se factura: cada transacción duplicada tiene su línea, y H9 no la cuenta como línea duplicada
    lineas = dataset["facturacion_detalle"]
    de_los_dobles = set(lineas.loc[lineas["referencia_consumo"].isin(dobles["id_registro"]), "numero_linea"])
    assert len(de_los_dobles) == len(dobles)
    assert not de_los_dobles & set(alertas.loc[alertas["regla"] == "linea_duplicada", "id_registro"])


def test_el_doble_cobro_con_el_decimal_mal_colocado_se_detecta(dataset, alertas):
    """La copia de la contingencia escrita a mano puede tener los litros ×10, ×100 o ÷10 (15,96 L como 1596 L)."""
    consumo, gt = dataset["consumo"].set_index("id"), dataset["ground_truth"]
    movidos = gt[(gt["tipo_anomalia"] == "DOBLE_COBRO") & gt["descripcion"].str.contains("decimal mal colocado")]
    assert len(movidos) == 3
    original = consumo.loc[movidos["descripcion"].str.extract(r"la carga (\S+) se cobró")[0], "litros"].to_numpy()
    factores = sorted((consumo.loc[movidos["id_registro"], "litros"].to_numpy() / original).round(6))
    assert factores == [0.1, 10, 100]
    doble_cobro = alertas[alertas["regla"] == "doble_cobro"].set_index("id_registro")
    assert doble_cobro.loc[movidos["id_registro"], "detalle"].str.contains("decimal mal colocado").all()
    # Las copias que superan el tanque también las alerta H3b: son dos alertas sobre la misma carga y no se
    # debe perder ninguna (decisión del dueño, #55)
    capacidad = dataset["flota"].set_index("Matricula")["CapacidadTanque"]
    copias = consumo.loc[movidos["id_registro"]]
    superan = copias.index[copias["litros"].to_numpy() > copias["vehiculo_id"].map(capacidad).to_numpy()]
    assert len(superan) >= 1
    exceso = set(alertas.loc[alertas["regla"] == "exceso_sin_antecedente", "id_registro"])
    mayor_al_tanque = set(alertas.loc[alertas["regla"] == "litros_mayor_a_tanque", "id_registro"])
    assert set(superan) <= mayor_al_tanque           # todas siguen con su alerta de exceso del tanque
    assert set(superan) & exceso                    # y alguna también con la de H3b con contexto


def test_las_contingencias_con_un_par_parecido_no_son_doble_cobro(dataset, alertas):
    """Con el decimal corrido, sus litros quedan a 5%-15% de una carga habitual cercana: fuera del ±2%."""
    legitimos = dataset["casos_legitimos"]
    parecidas = set(legitimos.loc[legitimos["descripcion"].str.contains("decimal corrido"), "id_registro"])
    assert len(parecidas) == 2
    assert not parecidas & set(alertas.loc[alertas["regla"] == "doble_cobro", "id_registro"])
    # Los litros de la carga y de su pedido siguen coincidiendo: no aparece un desacuerdo de litros
    assert not parecidas & set(alertas.loc[alertas["regla"] == "desacuerdo_de_litros", "id_registro"])


def test_las_contingencias_legitimas_incluyen_casos_con_una_carga_cercana_de_otros_litros(dataset):
    consumo = dataset["consumo"].copy()
    consumo["instante"] = pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(consumo["hora"])
    legitimas = set(dataset["casos_legitimos"].query("tipo_caso == 'CONTINGENCIA'")["id_registro"])
    cercanas = 0
    for _, c in consumo[consumo["id"].isin(legitimas)].iterrows():
        otras = consumo[(consumo["vehiculo_id"] == c["vehiculo_id"]) & (consumo["id"] != c["id"])]
        horas = (otras["instante"] - c["instante"]).abs() / pd.Timedelta(hours=1)
        cercanas += bool((horas < 12).any())
    assert cercanas >= 0.2 * len(legitimas)


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
    # los que no son anomalia estan en deposito y apagados
    assert (en_deposito["Estado"] == "OFFLINE").all()
    # los que si son anomalia transmiten, este en el grupo que este (#53)
    assert (telemetria.loc[telemetria["Alias"].isin(activos), "Estado"] == "ONLINE").all()
    grupo_viejo = telemetria[telemetria["Alias"].isin(activos)
                             & (telemetria["Grupo"] == "BAJA / REEMPLAZOS")]
    assert len(grupo_viejo) >= 1, "debe haber dispositivos con el grupo desactualizado"
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


def test_la_identificacion_de_las_cargas(dataset, alertas):
    """Cargas sin móvil, identificadas por el motor y con el dominio mal tipeado (#41)."""
    from deteccion.reglas import distancia_uno

    flota, consumo, gt = dataset["flota"], dataset["consumo"].set_index("id"), dataset["ground_truth"]
    legitimos = dataset["casos_legitimos"]
    sin_movil = gt.loc[gt["tipo_anomalia"] == "DOMINIO_INVALIDO", "id_registro"]
    assert len(sin_movil) and not consumo.loc[sin_movil, "numero_tarjeta"].isin(flota["NumeroTarjeta"]).any()

    por_motor = legitimos.loc[legitimos["tipo_caso"] == "IDENTIFICADA_POR_MOTOR", "id_registro"]
    motor = flota.set_index("Matricula")["NumeroMotor"]
    assert len(por_motor)
    assert (consumo.loc[por_motor, "dominio"].astype(str).values
            == consumo.loc[por_motor, "vehiculo_id"].map(motor).str[-8:].values).all()

    tipeados = gt.loc[gt["tipo_anomalia"] == "DOMINIO_MAL_TIPEADO", "id_registro"]
    dominio = flota.set_index("Matricula")["Dominio"]
    assert len(tipeados)
    assert all(distancia_uno(d, dominio[v]) for d, v in consumo.loc[tipeados, ["dominio", "vehiculo_id"]].values)
    normalizada = alertas[alertas["regla"] == "dominio_sin_vinculo_normalizado"].set_index("id_registro")
    assert (normalizada.loc[tipeados, "causa_probable"] == "dominio_equivocado").all()
    # Con contexto, H1 alerta exactamente las cargas sin móvil
    con_contexto = set(alertas.loc[alertas["regla"] == "carga_sin_movil_identificado", "id_registro"])
    assert con_contexto == set(sin_movil)


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


def _dispositivos_de(retiros):
    """Los alias de dispositivo que el motivo de cada fila menciona."""
    return set(retiros["motivo"].str.extract(r"con (DEV-\d+)")[0].dropna())


def test_retiros_inmediatos_salen_de_las_alertas_de_h11_ordenadas_por_urgencia(dataset, alertas):
    """#53: la lista sale de las alertas del dispositivo, con el grupo desactualizado primero."""
    retiros = priorizacion.retiros_inmediatos(dataset["flota"], dataset["telemetria"], alertas)
    assert not retiros.empty, "el generador inyecta dispositivos de moviles de baja transmitiendo"

    esperado = set(alertas.loc[alertas["regla"] == "dispositivo_activo_en_baja", "id_registro"])
    assert _dispositivos_de(retiros) == esperado
    assert set(retiros["dominio"]) <= set(dataset["flota"]["Dominio"])
    assert (retiros["motivo"].str.len() > 0).all()

    grupo = retiros["grupo_desactualizado"]
    assert list(grupo) == sorted(grupo, reverse=True), "el grupo desactualizado va primero"
    assert grupo.any(), "debe haber casos de grupo desactualizado"
    assert set(retiros.loc[grupo, "Grupo"]) == {"BAJA / REEMPLAZOS"}
    # dentro de cada grupo, primero el que mas hace que falta transmision
    for _, parte in retiros.groupby("grupo_desactualizado"):
        assert list(parte["dias_sin_transmitir"]) == sorted(parte["dias_sin_transmitir"])


def test_h11_no_puntua_ninguna_carga_ni_entra_en_la_curva_de_esfuerzo(dataset, puntajes):
    """Lo que no puede pasar: que estas alertas toquen el puntaje de alguna carga.

    La cola y la curva de esfuerzo se cuentan en transacciones, y H11 es por vehiculo. Un movil
    de baja deja de cargar, asi que si llegara al puntaje contaria como revisada una carga que
    no es la anomalia, y moveria las metricas de todos los metodos a cambio de nada.
    """
    assert "dispositivo_activo_en_baja" not in priorizacion.REGLAS_INGENUAS
    assert "dispositivo_activo_en_baja" not in priorizacion.REGLAS_CONTEXTO

    pun, variables, alertas_ = puntajes
    cola = priorizacion.cola_de_revision(pun, "Combinado", dataset["consumo"], variables, alertas_,
                                         cantidad=100)
    assert not cola["reglas"].str.contains("dispositivo_activo_en_baja").any()
    # las alertas de H11 son por dispositivo, no tienen id de transaccion: no pueden colarse
    h11 = alertas_[alertas_["regla"] == "dispositivo_activo_en_baja"]
    assert not set(h11["id_registro"]) & set(pun.index)


# --- Errores de carga y causa probable (#24) ---------------------------------

def test_los_errores_de_carga_se_inyectan_en_la_carga_y_en_su_pedido(dataset):
    gt = dataset["ground_truth"]
    errores = gt[gt["tipo_anomalia"].str.startswith("ERROR_")]
    assert errores.groupby(["tipo_anomalia", "tabla"]).size().to_dict() == {
        ("ERROR_DOMINIO", "consumo"): 6, ("ERROR_DOMINIO", "solicitudes"): 6,
        ("ERROR_PROVEEDOR", "consumo"): 6, ("ERROR_PROVEEDOR", "solicitudes"): 6,
        ("ERROR_TARJETA", "consumo"): 4, ("ERROR_TARJETA", "solicitudes"): 4}
    assert set(errores["hipotesis"]) == {"CALIDAD"}
    pedidos = dataset["solicitudes"].set_index("id")
    proveedor = errores[(errores["tipo_anomalia"] == "ERROR_PROVEEDOR") & (errores["tabla"] == "solicitudes")]
    assert (pedidos.loc[proveedor["id_registro"], "estacion_servicio"] == "ESTACION AJENA").all()
    # En la tarjeta equivocada, la carga figura en otro vehículo que su pedido (se registran de a pares)
    cargas = dataset["consumo"].set_index("id")
    tarjeta = errores[errores["tipo_anomalia"] == "ERROR_TARJETA"]
    de_carga, de_pedido = tarjeta[tarjeta["tabla"] == "consumo"], tarjeta[tarjeta["tabla"] == "solicitudes"]
    assert (cargas.loc[de_carga["id_registro"], "vehiculo_id"].values != de_pedido["vehiculo_id"].values).all()


def test_la_causa_probable_reconoce_los_errores_y_no_las_anomalias(dataset, alertas):
    """La mayoría de los errores inyectados recibe su causa; ninguna anomalía real recibe una causa de error."""
    gt = dataset["ground_truth"]
    causa = alertas.dropna(subset=["causa_probable"]).drop_duplicates("id_registro").set_index("id_registro")[
        "causa_probable"]
    esperada = {"ERROR_PROVEEDOR": "proveedor_equivocado", "ERROR_DOMINIO": "dominio_equivocado",
                "ERROR_TARJETA": "tarjeta_equivocada"}
    cargas = gt[gt["tipo_anomalia"].isin(esperada) & (gt["tabla"] == "consumo")]
    for tipo, grupo in cargas.groupby("tipo_anomalia"):
        aciertos = (causa.reindex(grupo["id_registro"]) == esperada[tipo]).mean()
        assert aciertos > 0.5, tipo
    reales = causa.reindex(gt.loc[gt["hipotesis"] != "CALIDAD", "id_registro"]).dropna()
    assert len(reales) > 0 and (reales == "sin_explicacion").all()


def test_retiros_inmediatos_no_dependen_de_las_alertas_del_puntaje(dataset, alertas):
    """La lista se calcula con el padrón y la telemetría: el puntaje de las cargas se arma sin la telemetría,
    así que apoyarse en sus alertas dejaba la lista de la página vacía."""
    sin_pasar_alertas = priorizacion.retiros_inmediatos(dataset["flota"], dataset["telemetria"])
    con_alertas = priorizacion.retiros_inmediatos(dataset["flota"], dataset["telemetria"], alertas)
    assert not sin_pasar_alertas.empty
    assert _dispositivos_de(sin_pasar_alertas) == _dispositivos_de(con_alertas)

