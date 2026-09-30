"""Tests de la detección por reglas y de la evaluación contra el ground truth."""
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion.evaluacion import evaluar_binario, evaluar_por_regla, evaluar_por_tipo
from deteccion.reglas import ejecutar_reglas, secuencia_odometro
from generator_pipeline_maestro import GeneradorMaestro


# --- Métricas (casos calculados a mano) -------------------------------------

def gt(*pares):
    return pd.DataFrame([{"id_registro": i, "tipo_anomalia": t, "columna": "x"} for i, t in pares])


def alertas(*ternas):
    return pd.DataFrame([{"id_registro": i, "tipo_anomalia": t, "regla": r, "detalle": ""}
                         for i, t, r in ternas])


def test_metricas_por_tipo():
    verdad = gt(("a", "T"), ("b", "T"), ("c", "T"), ("d", "U"))
    pred = alertas(("a", "T", "r1"), ("b", "T", "r1"), ("z", "T", "r1"))
    fila = evaluar_por_tipo(pred, verdad).set_index("tipo_anomalia").loc["T"]
    assert (fila.tp, fila.fp, fila.fn) == (2, 1, 1)
    assert fila.precision == pytest.approx(2 / 3)
    assert fila.recall == pytest.approx(2 / 3)
    assert fila.f1 == pytest.approx(2 / 3)


def test_tipo_sin_alertas_tiene_recall_cero_y_precision_indefinida():
    fila = evaluar_por_tipo(alertas(("a", "T", "r1")), gt(("a", "T"), ("d", "U"))).set_index(
        "tipo_anomalia").loc["U"]
    assert (fila.tp, fila.fn, fila.recall, fila.f1) == (0, 1, 0.0, 0.0)
    assert math.isnan(fila.precision)


def test_un_acierto_requiere_el_mismo_tipo():
    fila = evaluar_por_tipo(alertas(("a", "U", "r1")), gt(("a", "T"))).set_index("tipo_anomalia")
    assert fila.loc["T", "fn"] == 1 and fila.loc["U", "fp"] == 1


def test_varias_reglas_del_mismo_tipo_se_evaluan_por_separado():
    verdad = gt(("a", "T"), ("b", "T"))
    pred = alertas(("a", "T", "r1"), ("a", "T", "r2"), ("b", "T", "r2"))
    por_regla = evaluar_por_regla(pred, verdad).set_index("regla")
    assert por_regla.loc["r1", "recall"] == 0.5
    assert por_regla.loc["r2", "recall"] == 1.0
    assert evaluar_por_tipo(pred, verdad).iloc[0].tp == 2  # la unión cuenta una vez cada anomalía


def test_evaluacion_binaria():
    m = evaluar_binario(ids_alertados={"a", "b", "c"}, ids_anomalos={"a", "b", "d"}, universo="abcdefgh")
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 4)


# --- Reglas -----------------------------------------------------------------

def test_secuencia_de_odometro_salta_lecturas_vacias():
    consumo = pd.DataFrame({
        "id": ["c1", "c2", "c3"],
        "vehiculo_id": ["V1"] * 3,
        "fecha": ["2024-01-01", "2024-01-05", "2024-01-10"],
        "odometro": [1000, None, 800],
    })
    seq = secuencia_odometro(consumo).set_index("id")
    assert seq.loc["c3", "km"] == -200  # se compara con c1, la última lectura válida


@pytest.fixture(scope="module")
def evaluacion(tmp_path_factory):
    d = tmp_path_factory.mktemp("maestro")
    assert GeneradorMaestro(n_flota=200, seed=42, output_dir=d).ejecutar()["exito"]
    flota, consumo, verdad = (pd.read_csv(d / f) for f in ["flota.csv", "consumo.csv", "ground_truth.csv"])
    return evaluar_por_regla(ejecutar_reglas(flota, consumo), verdad).set_index("regla")


@pytest.mark.parametrize("regla", [
    "duplicado_exacto", "nulo_estacion", "nulo_conductor", "nulo_odometro",
    "dominio_sin_vinculo", "litros_mayor_a_tanque", "odometro_disminuye",
    "salto_historial_vehiculo",
])
def test_reglas_detectan_todas_sus_anomalias_sin_falsos_positivos(evaluacion, regla):
    fila = evaluacion.loc[regla]
    assert fila.reales > 0
    assert (fila.precision, fila.recall) == (1.0, 1.0)


def test_historial_del_vehiculo_supera_al_umbral_fijo_en_saltos(evaluacion):
    assert evaluacion.loc["salto_historial_vehiculo", "recall"] > evaluacion.loc["salto_umbral_fijo", "recall"]


def test_normalizar_dominio_y_leer_fecha():
    import pandas as pd
    from deteccion.reglas import leer_fecha, normalizar_dominio

    assert list(normalizar_dominio(pd.Series(["ab0001cd", "AB 0001 CD", "AB-0001-CD", "AB0001CD "]))) == ["AB0001CD"] * 4
    fechas = leer_fecha(pd.Series(["2024-03-05", "05/03/2024", "31/12/2024"]))
    assert list(fechas.dt.strftime("%Y-%m-%d")) == ["2024-03-05", "2024-03-05", "2024-12-31"]


def test_las_cargas_de_otra_red_cierran_el_tramo_del_odometro():
    """El reporte es de un proveedor: una carga en otra red, anotada en el registro interno, parte el tramo."""
    from deteccion.reglas import cargas_fuera_del_reporte

    consumo = pd.DataFrame({"id": ["C1", "C2", "C3"], "vehiculo_id": "V1",
                            "fecha": ["2024-03-01", "2024-03-05", "2024-03-09"],
                            "hora": ["10:00:00", "10:00:00", "10:00:00"], "odometro": [1000, 1400, 1800]})
    registro = pd.DataFrame({"id": ["R1", "R2"], "vehiculo_id": "V1", "fecha": ["03/03/2024", "07/03/2024"],
                             "hora": ["09:00:00", "09:00:00"], "odometro": [1200, 1600],
                             "litros_cargados": [30.0, 30.0], "litros_autorizados": [40, 40],
                             "rendido": ["SI", "NO"], "anulado": ["NO", "NO"],
                             "estacion_servicio": ["ESTACION AJENA", "ESTACION AJENA"]})
    fuera = cargas_fuera_del_reporte(registro)
    assert list(fuera["id"]) == ["FUERA-R1"]          # solo los pedidos rendidos cuentan como carga
    secuencia = secuencia_odometro(consumo, fuera=fuera).set_index("id")
    assert secuencia.loc["C2", "km"] == 200 and secuencia.loc["C3", "km"] == 400
    assert bool(secuencia.loc["FUERA-R1", "fuera"])


def test_odometro_sin_avance_solo_alerta_sin_excepcion_ese_dia():
    """H12: la excepción puede durar un solo día; la lectura repetida el día siguiente es una alerta."""
    from deteccion.reglas import cargas_exceptuadas, detectar_sin_avance_sin_excepcion

    flota = pd.DataFrame({"Matricula": ["V1"], "Dominio": ["ZA001AA"], "ExcepcionOdometro": ["NO"],
                          "FechaHastaExcepcionOdometro": [None]})
    consumo = pd.DataFrame({"id": ["C1", "C2", "C3", "C4"], "vehiculo_id": "V1",
                            "fecha": ["2024-03-01", "2024-03-05", "2024-03-09", "2024-03-09"],
                            "odometro": [1000, 1000, 1000, 1000]})
    excepciones = pd.DataFrame({"patente": ["za 001 aa"], "fecha_creacion": ["2024-03-05"], "fecha_hasta": ["2024-03-05"]})
    exceptuadas = cargas_exceptuadas(consumo, flota, excepciones)
    assert exceptuadas == {"C2"}
    alertas = detectar_sin_avance_sin_excepcion(secuencia_odometro(consumo), exceptuadas)
    assert list(alertas["id_registro"]) == ["C3"]      # C4 es del mismo día que C3: no se vuelve a leer el tablero


# --- H5: umbral de rendimiento y descarte de lo que ya explican otras reglas -------

def dias_de_prueba(*relativos, litros=40.0, capacidad=50.0, ids=None):
    """Arma el resumen por día que consume `detectar_rendimiento_bajo`, sin pasar por el generador."""
    dias = pd.DataFrame({
        "litros": [litros] * len(relativos),
        "capacidad": [capacidad] * len(relativos),
        "rendimiento_odometro_relativo": list(relativos),
        "rendimiento_gps_relativo": [float("nan")] * len(relativos),
        "ids": ids or [[f"C{i}"] for i in range(len(relativos))],
    })
    return dias


@pytest.mark.parametrize("relativo,marca", [
    (0.50, False),   # rinde normal
    (0.30, False),   # borde exacto del umbral: no se marca
    (0.2999, True),
    (0.10, True),
])
def test_umbral_de_rendimiento_marca_por_debajo_de_la_fraccion(relativo, marca):
    """El umbral es 0,3 de lo habitual del vehículo; en el borde exacto no marca."""
    from deteccion.reglas import detectar_rendimiento_bajo

    alertas = detectar_rendimiento_bajo(dias_de_prueba(relativo), "odometro")
    assert list(alertas["id_registro"]) == (["C0"] if marca else [])


def test_el_minimo_de_litros_sigue_dejando_marcar_la_carga_chica():
    """Con menos del 30% del tanque la carga no se evalúa; el resto de las del día sí."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.1, 0.1, ids=[["C1"], ["C2"]], litros=10.0, capacidad=50.0)
    assert list(detectar_rendimiento_bajo(dias, "odometro")["id_registro"]) == []


def test_el_parametro_minimo_permite_medir_la_curva_de_umbrales():
    """El umbral llega como parámetro para poder trazar la curva sin tocar el código que corre."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.45)
    assert list(detectar_rendimiento_bajo(dias, "odometro")["id_registro"]) == []
    assert list(detectar_rendimiento_bajo(dias, "odometro", minimo=0.5)["id_registro"]) == ["C0"]
    assert list(detectar_rendimiento_bajo(dias, "odometro", minimo=0.2)["id_registro"]) == []


def test_h5_no_repite_lo_que_ya_explica_otra_regla():
    """Una carga ya marcada por H2, H4, H6 o H9 saca el día de H5: su bajo rendimiento es consecuencia."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.1, 0.1, ids=[["C1", "C2"], ["C3"]])
    sin_explicar = detectar_rendimiento_bajo(dias, "odometro")
    assert sorted(sin_explicar["id_registro"]) == ["C1", "C2", "C3"]

    # El descarte es por día, no por carga: C1 ya la explicó otra regla y con ella sale el
    # día entero, porque el rendimiento es una propiedad del día. Solo C3 queda.
    explicado = detectar_rendimiento_bajo(dias, "odometro", explicadas={"C1"})
    assert sorted(explicado["id_registro"]) == ["C3"]


def test_el_descarte_de_explicadas_sacade_un_dia_completo():
    """El día entero sale, aunque solo una de sus cargas esté explicada."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.1, ids=[["C1", "C2"]])
    assert list(detectar_rendimiento_bajo(dias, "odometro", explicadas={"C2"})["id_registro"]) == []


def test_explicadas_y_sin_odometro_son_descartes_independientes():
    """Cada descarte saca lo suyo: uno por otra regla, otro por odómetro sin dato."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.1, 0.1, ids=[["C1"], ["C2"]])
    alertas = detectar_rendimiento_bajo(dias, "odometro", sin_odometro={"C2"}, explicadas={"C1"})
    assert list(alertas["id_registro"]) == []


def test_sin_explicadas_la_regla_no_cambia():
    """El parámetro vacío es el comportamiento anterior: no descarta nada."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.1, 0.5)
    assert sorted(detectar_rendimiento_bajo(dias, "odometro", explicadas=set())["id_registro"]) == ["C0"]


def test_el_gps_toma_el_odometro_cuando_no_reporto_el_intervalo_completo():
    """Sin GPS completo en el intervalo se usa el odómetro, como antes."""
    from deteccion.reglas import detectar_rendimiento_bajo

    dias = dias_de_prueba(0.1, 0.1)
    dias["rendimiento_gps_relativo"] = [0.05, float("nan")]   # solo el primer día Odds tiene GPS
    alertas = detectar_rendimiento_bajo(dias, "gps")
    assert sorted(alertas["id_registro"]) == ["C0", "C1"]
def test_criterio_de_la_fuente_h12_menos_de_5_km_con_la_excepcion_de_hoy():
    """H12 (fuente): avanza menos de 5 km, aunque sea el mismo día; la excepción se mira con la vigencia de hoy."""
    from deteccion.reglas import cargas_exceptuadas, detectar_avance_menor_fuente

    flota = pd.DataFrame({"Matricula": ["V1", "V2"], "Dominio": ["ZA001AA", "ZA002AA"],
                          "ExcepcionOdometro": ["NO", "SI"], "FechaHastaExcepcionOdometro": [None, "2099-01-01"]})
    consumo = pd.DataFrame({"id": ["A1", "A2", "A3", "A4", "A5", "B1", "B2"], "vehiculo_id": ["V1"] * 5 + ["V2"] * 2,
                            "fecha": ["2024-03-01", "2024-03-05", "2024-03-05", "2024-03-09", "2024-03-12",
                                      "2024-03-01", "2024-03-05"],
                            "odometro": [1000, 1004, 1004, 1300, 1200, 500, 500]})
    alertas = detectar_avance_menor_fuente(secuencia_odometro(consumo), cargas_exceptuadas(consumo, flota))
    # A2 avanzó 4 km; A3, 0 km el mismo día. A4 avanzó 296 km y A5 retrocede (lo ve H2b).
    # B2 no avanza, pero el vehículo tiene hoy una excepción vigente.
    assert sorted(alertas["id_registro"]) == ["A2", "A3"]


def test_criterio_de_la_fuente_h4_mas_de_una_carga_en_menos_de_6_horas():
    """H4 (fuente): cada carga con otra del mismo vehículo a menos de 6 horas, sin mirar litros ni recorrido."""
    from deteccion.reglas import detectar_cargas_multiples

    consumo = pd.DataFrame({"id": ["C1", "C2", "C3", "C4", "C5"], "vehiculo_id": ["V1", "V1", "V1", "V1", "V2"],
                            "fecha": ["2024-03-01", "2024-03-01", "2024-03-01", "2024-03-02", "2024-03-01"],
                            "hora": ["08:00:00", "13:30:00", "20:00:00", "01:00:00", "08:30:00"]})
    alertas = detectar_cargas_multiples(consumo)
    # C1-C2: 5,5 h. C2-C3: 6,5 h. C3-C4: 5 h, aunque cambie el día. C5 es de otro vehículo.
    assert sorted(alertas["id_registro"]) == ["C1", "C2", "C3", "C4"]
    assert set(alertas["tipo_anomalia"]) == {"FRACCIONAMIENTO"}
    assert list(detectar_cargas_multiples(consumo, excluir_ids=["C2"])["id_registro"]) == ["C3", "C4"]


def test_criterios_de_la_fuente_en_el_borde_exacto():
    """5 km y 6:00 h justas no alertan: los criterios son "menos de"."""
    from deteccion.reglas import cargas_exceptuadas, detectar_avance_menor_fuente, detectar_cargas_multiples

    flota = pd.DataFrame({"Matricula": ["V1"], "Dominio": ["ZA001AA"], "ExcepcionOdometro": ["NO"],
                          "FechaHastaExcepcionOdometro": [None]})
    consumo = pd.DataFrame({"id": ["A1", "A2", "A3"], "vehiculo_id": "V1",
                            "fecha": ["2024-03-01", "2024-03-02", "2024-03-03"], "odometro": [1000, 1005, 1100],
                            "hora": ["08:00:00", "08:00:00", "08:00:00"]})
    assert detectar_avance_menor_fuente(secuencia_odometro(consumo), cargas_exceptuadas(consumo, flota)).empty
    seis_horas = pd.DataFrame({"id": ["C1", "C2"], "vehiculo_id": "V1", "fecha": "2024-03-01",
                               "hora": ["08:00:00", "14:00:00"]})
    assert detectar_cargas_multiples(seis_horas).empty
    # Sin hora, la carga se toma a las 00:00 de su día
    sin_hora = pd.DataFrame({"id": ["C1", "C2"], "vehiculo_id": "V1", "fecha": ["2024-03-01", "2024-03-01"],
                             "hora": [None, "05:00:00"]})
    assert sorted(detectar_cargas_multiples(sin_hora)["id_registro"]) == ["C1", "C2"]
