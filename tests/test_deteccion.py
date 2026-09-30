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


def test_causa_probable_de_cada_error_de_carga():
    """#24: cada firma de error de carga se reconoce; una carga con su pedido no tiene causa."""
    from deteccion.reglas import ESTACION_AJENA, causas_probables

    flota = pd.DataFrame({"Matricula": ["V1", "V2", "V3"], "Dominio": ["ZA001AA", "ZA002AA", "ZA003AA"],
                          "NumeroTarjeta": ["T1", "T2", "T3"]})
    dominio = dict(zip(flota["Matricula"], flota["Dominio"]))
    tarjeta = dict(zip(flota["Matricula"], flota["NumeroTarjeta"]))
    # (id, vehículo del reporte, fecha, hora, litros, odómetro)
    cargas = [("A1", "V1", "2024-03-01", "10:00:00", 30, 1000), ("A2", "V1", "2024-03-05", "10:00:00", 40, 1300),
              ("A3", "V1", "2024-03-10", "10:00:00", 30, 1800),
              ("B0", "V2", "2024-03-01", "10:00:00", 30, 4900), ("B1", "V2", "2024-03-02", "11:00:00", 25, 5000),
              ("B2", "V2", "2024-03-06", "10:00:00", 30, 5200),
              ("C1", "V3", "2024-03-01", "10:00:00", 30, 9000), ("X", "V3", "2024-03-08", "12:00:00", 20, 1500),
              ("C3", "V3", "2024-03-12", "10:00:00", 30, 9300)]
    consumo = pd.DataFrame(cargas, columns=["id", "vehiculo_id", "fecha", "hora", "litros", "odometro"]).assign(
        tipo_identificacion="PATENTE", conductor="C", estacion="EST-001")
    consumo["dominio"] = consumo["vehiculo_id"].map(dominio)
    consumo["numero_tarjeta"] = consumo["vehiculo_id"].map(tarjeta)

    def pedido(id_, vehiculo, carga, minutos_antes=30, estacion="EST-001"):
        c = consumo.set_index("id").loc[carga]
        instante = pd.Timestamp(f"{c['fecha']} {c['hora']}") - pd.Timedelta(minutes=minutos_antes)
        return {"id": id_, "vehiculo_id": vehiculo, "dominio": dominio[vehiculo], "fecha": instante.strftime("%d/%m/%Y"),
                "hora": instante.strftime("%H:%M:%S"), "litros_cargados": c["litros"], "litros_autorizados": c["litros"] + 5,
                "rendido": "SI", "anulado": "NO", "estacion_servicio": estacion, "tarjeta_personal": False,
                "solicitante": "C"}

    registro = pd.DataFrame([pedido(f"P-{c}", consumo.set_index("id").at[c, "vehiculo_id"], c)
                             for c in ["A1", "A3", "B0", "B2", "C1", "C3"]]
                            + [pedido("P2", "V1", "A2", 40, ESTACION_AJENA),   # proveedor equivocado
                               pedido("P3", "V3", "B1"),                        # dominio de otro vehículo
                               pedido("P4", "V1", "X", 20)])                    # tarjeta de V3, la cargó V1
    causas = causas_probables(consumo, registro, flota)
    assert causas == {"A2": "proveedor_equivocado", "P2": "proveedor_equivocado",
                      "B1": "dominio_equivocado", "P3": "dominio_equivocado",
                      "X": "tarjeta_equivocada", "P4": "tarjeta_equivocada",
                      "C3": "tarjeta_equivocada"}     # C3 cierra el tramo que abrió X en V3


def test_la_causa_va_en_el_detalle_y_la_alerta_se_mantiene():
    from deteccion.reglas import SIN_EXPLICACION, asignar_causa_probable

    alertas = pd.DataFrame({"id_registro": ["A2", "Z9", "F1"], "tipo_anomalia": "X",
                            "regla": ["carga_sin_registro", "carga_sin_registro", "linea_duplicada"],
                            "detalle": ["sin pedido", "sin pedido", "línea repetida"]})
    con_causa = asignar_causa_probable(alertas, {"A2": "proveedor_equivocado"})
    assert len(con_causa) == 3
    assert list(con_causa["causa_probable"].fillna("—")) == ["proveedor_equivocado", SIN_EXPLICACION, "—"]
    assert con_causa["detalle"].iloc[0] == "sin pedido · causa probable: proveedor equivocado"
    assert con_causa["detalle"].iloc[1] == "sin pedido"


def test_a_igual_puntaje_va_primero_lo_que_no_tiene_explicacion():
    from deteccion.priorizacion import _orden

    puntaje = pd.Series([1.0, 1.0, 0.5], index=["A", "B", "C"])
    assert list(_orden(puntaje)) == ["A", "B", "C"]
    assert list(_orden(puntaje, explicadas={"A"})) == ["B", "A", "C"]


def test_la_curva_de_esfuerzo_usa_el_mismo_desempate_que_la_cola():
    """Una carga explicada no le quita lugar, a igual puntaje, a una anomalía sin explicación."""
    from deteccion.priorizacion import curva_de_esfuerzo

    puntajes = pd.DataFrame({"Reglas con contexto": [1.0, 1.0, 0.0]}, index=["E", "F", "N"])
    ground_truth = pd.DataFrame({"id_registro": ["F"], "tipo_anomalia": ["FRACCIONAMIENTO"], "hipotesis": ["H4"]})
    sin = curva_de_esfuerzo(puntajes, ground_truth, maximo=1)
    con = curva_de_esfuerzo(puntajes, ground_truth, maximo=1, explicadas={"E"})
    assert sin["encontradas"].iloc[0] == 0 and con["encontradas"].iloc[0] == 1


def test_h8_cuenta_los_errores_de_carga_como_aciertos():
    """Decisión del dueño (PR #31): las alertas de los errores de carga son correctas, se citan."""
    from deteccion.hipotesis import HIPOTESIS

    h8 = next(h for h in HIPOTESIS if h["codigo"] == "H8")
    assert {"ERROR_PROVEEDOR", "ERROR_DOMINIO", "ERROR_TARJETA"} <= set(h8["tipos"])
