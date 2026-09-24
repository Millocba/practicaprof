"""Hipótesis del escenario realista y su contraste con las reglas.

Cada hipótesis compara reglas de menor a mayor contexto sobre los mismos tipos de
anomalía. La primera es la versión ingenua; la última, la que usa el contexto que
la hipótesis propone (historial del vehículo, estado de la flota, GPS, etc.).

El veredicto se calcula con los datos: la hipótesis se sostiene cuando la regla
con contexto mejora el F1 de la ingenua en al menos MEJORA_MINIMA_F1.
"""
import pandas as pd

MEJORA_MINIMA_F1 = 0.10

# regla None = no hay regla posible sin la fuente que aporta la hipótesis
HIPOTESIS = [
    {
        "codigo": "H2b",
        "titulo": "Retrocesos de odómetro",
        "enunciado": "Los retrocesos por un odómetro nuevo o por un error de tipeo generan falsas "
                     "alarmas; reconocer el reinicio y la lectura aislada las elimina sin perder "
                     "adulteraciones, incluidas las leves.",
        "tipos": ["ODOMETRO_REGRESIVO", "ODOMETRO_REGRESIVO_LEVE"],
        "reglas": [("odometro_disminuye", "cualquier retroceso"),
                   ("retroceso_con_contexto", "descarta reinicios y lecturas aisladas")],
        "contexto": "historial de lecturas del vehículo",
    },
    {
        "codigo": "H2c",
        "titulo": "Saltos de odómetro",
        "enunciado": "Un salto sobre el ritmo habitual puede ser un error de tipeo o un recorrido "
                     "real; descartar lecturas aisladas y confirmar con el GPS reduce las falsas alarmas.",
        "tipos": ["ODOMETRO_SALTO"],
        "reglas": [("salto_umbral_fijo", ">500 km en ≤7 días"),
                   ("salto_historial_vehiculo", "más de lo habitual para el vehículo"),
                   ("salto_con_contexto", "además: no es tipeo y el GPS no lo respalda")],
        "contexto": "historial del vehículo y km del GPS",
    },
    {
        "codigo": "H3b",
        "titulo": "Exceso volumétrico",
        "enunciado": "Un vehículo que supera su tanque desde el principio tiene más capacidad que la "
                     "registrada; solo el exceso que aparece después indica un problema.",
        "tipos": ["EXCESO_VOLUMETRICO"],
        "reglas": [("litros_mayor_a_tanque", "litros > tanque registrado"),
                   ("exceso_sin_antecedente", "además: al principio no lo superaba")],
        "contexto": "historial de cargas del vehículo",
    },
    {
        "codigo": "H4",
        "titulo": "Fraccionamiento",
        "enunciado": "Repartir una carga excesiva en varias cargas el mismo día evade el control por "
                     "transacción; agregar por día lo detecta y el recorrido del día separa los viajes largos.",
        "tipos": ["FRACCIONAMIENTO"],
        "reglas": [("litros_mayor_a_tanque", "control por transacción"),
                   ("fraccionamiento_diario", "suma del día > tanque"),
                   ("fraccionamiento_sin_recorrido", "además: el recorrido no lo justifica")],
        "contexto": "cargas agregadas por día y recorrido",
    },
    {
        "codigo": "H5",
        "titulo": "Rendimiento imposible",
        "enunciado": "Cargar mucho combustible sin recorrido que lo justifique no se ve mirando solo "
                     "los litros; el rendimiento km/L frente al habitual del vehículo lo revela.",
        "tipos": ["RENDIMIENTO_IMPOSIBLE"],
        "reglas": [("litros_mayor_a_tanque", "control de litros"),
                   ("rendimiento_bajo_odometro", "km/L según el odómetro"),
                   ("rendimiento_bajo_gps", "km/L según el GPS (odómetro si no hay)")],
        "contexto": "rendimiento habitual del vehículo",
    },
    {
        "codigo": "H6",
        "titulo": "Cargas a vehículos inactivos",
        "enunciado": "Una carga normal en litros puede corresponder a un vehículo dado de baja o fuera "
                     "de servicio; solo el cruce con el estado de la flota la detecta.",
        "tipos": ["CARGA_VEHICULO_INACTIVO"],
        "reglas": [(None, "sin cruce con la flota"),
                   ("carga_vehiculo_inactivo", "fecha posterior al cambio de estado")],
        "contexto": "estado de la flota",
    },
    {
        "codigo": "H7",
        "titulo": "Cargas lejos del vehículo",
        "enunciado": "Comparar la estación con la zona habitual confunde viajes reales con tarjetas "
                     "usadas en otro lado; el recorrido del GPS de ese día los distingue.",
        "tipos": ["CARGA_FUERA_DE_ZONA"],
        "reglas": [("carga_lejos_de_base", "lejos de su zona habitual"),
                   ("carga_lejos_del_gps", "lejos del recorrido del GPS")],
        "contexto": "telemetría diaria",
    },
]


def evaluar_regla(alertas, ground_truth, casos_legitimos, regla, tipos):
    """Métricas de una regla contra las anomalías de `tipos`, con el origen de cada falso positivo.

    Un acierto es una transacción alertada por la regla que tiene alguna anomalía de
    `tipos`. Los falsos positivos se clasifican en: caso legítimo, otra anomalía o normal.
    """
    reales = set(ground_truth.loc[ground_truth["tipo_anomalia"].isin(tipos), "id_registro"])
    alertados = set() if regla is None else set(alertas.loc[alertas["regla"] == regla, "id_registro"])
    fp = alertados - reales
    legitimos = set(casos_legitimos["id_registro"]) if casos_legitimos is not None else set()
    otras = set(ground_truth["id_registro"]) - reales
    tp, fn = len(alertados & reales), len(reales - alertados)
    precision = tp / (tp + len(fp)) if tp + len(fp) else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    return {
        "reales": len(reales), "alertas": len(alertados), "tp": tp, "fp": len(fp), "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "fp_legitimos": len(fp & legitimos), "fp_otra_anomalia": len(fp & otras),
        "fp_normales": len(fp - legitimos - otras),
    }


def contrastar_hipotesis(alertas, ground_truth, casos_legitimos):
    """Una fila por hipótesis y regla, más el veredicto de cada hipótesis."""
    filas, veredictos = [], []
    for h in HIPOTESIS:
        resultados = []
        for orden, (regla, descripcion) in enumerate(h["reglas"]):
            m = evaluar_regla(alertas, ground_truth, casos_legitimos, regla, h["tipos"])
            resultados.append(m)
            filas.append({"hipotesis": h["codigo"], "orden": orden, "regla": regla or "—",
                          "descripcion": descripcion, **m})
        ingenua, contexto = resultados[0], resultados[-1]
        if ingenua["reales"] == 0:
            veredicto = "Sin casos para evaluar"
        elif contexto["f1"] - ingenua["f1"] >= MEJORA_MINIMA_F1:
            veredicto = "Se sostiene"
        else:
            veredicto = "No se sostiene"
        veredictos.append({
            "hipotesis": h["codigo"], "titulo": h["titulo"], "veredicto": veredicto,
            "f1_ingenua": ingenua["f1"], "f1_contexto": contexto["f1"],
            "fp_legitimos_ingenua": ingenua["fp_legitimos"], "fp_legitimos_contexto": contexto["fp_legitimos"],
            "recall_contexto": contexto["recall"],
        })
    return pd.DataFrame(filas), pd.DataFrame(veredictos)
