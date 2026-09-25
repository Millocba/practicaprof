"""Hipótesis del escenario realista y su contraste con las reglas.

Cada hipótesis compara reglas de menor a mayor contexto sobre los mismos tipos de
anomalía. La primera es la versión ingenua; la última, la que usa el contexto que
la hipótesis propone (historial del vehículo, estado de la flota, GPS, etc.).

El veredicto se calcula con los datos: la hipótesis se sostiene cuando la regla
con contexto mejora el F1 de la ingenua en al menos MEJORA_MINIMA_F1.
"""
import pandas as pd

MEJORA_MINIMA_F1 = 0.10

# regla None = no hay regla posible sin la fuente que aporta la hipótesis; una lista de
# reglas se evalúa como la unión de sus alertas. "nivel": "factura" evalúa por factura:
# una línea irregular cuenta como una factura con problemas.
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
    {
        "codigo": "H8",
        "titulo": "Cargas y solicitudes",
        "enunciado": "Cruzar cada carga con las solicitudes detecta las que no tienen autorización o la "
                     "superan; aceptar regularizaciones posteriores y la tolerancia de medición evita "
                     "falsas alarmas.",
        "tipos": ["CARGA_SIN_SOLICITUD", "CARGA_CON_SOLICITUD_RECHAZADA", "CARGA_SUPERA_AUTORIZADO"],
        "reglas": [(["carga_sin_solicitud_previa", "litros_superan_autorizado"],
                    "solicitud previa y litros autorizados exactos"),
                   (["carga_sin_autorizacion", "supera_autorizado_con_tolerancia"],
                    "acepta regularizaciones y 5% de tolerancia")],
        "contexto": "solicitudes aprobadas y rechazadas",
    },
    {
        "codigo": "H9",
        "titulo": "Conciliación de facturas",
        "enunciado": "Comparar el total mensual facturado con el consumo registrado confunde desfases de "
                     "corte y ajustes documentados, y no ve irregularidades chicas; conciliar la factura "
                     "línea por línea contra las cargas las detecta.",
        "tipos": ["TOTAL_INFLADO", "LINEA_SIN_CONSUMO", "LINEA_DUPLICADA", "SOBREPRECIO"],
        "reglas": [("conciliacion_mensual", "total del mes vs. consumo del mes"),
                   (["factura_no_concilia", "linea_sin_consumo", "linea_duplicada", "sobreprecio"],
                    "encabezado vs. líneas y cada línea vs. su carga")],
        "contexto": "detalle de facturación",
        "nivel": "factura",
    },
]


def _nombres(regla):
    if regla is None:
        return []
    return [regla] if isinstance(regla, str) else list(regla)


def describir_regla(regla):
    return " + ".join(_nombres(regla)) or "—"


def evaluar_regla(alertas, ground_truth, casos_legitimos, regla, tipos, agrupar=None):
    """Métricas de una regla (o unión de reglas) contra las anomalías de `tipos`.

    Un acierto es un registro alertado que tiene alguna anomalía de `tipos`. Los falsos
    positivos se clasifican en: caso legítimo, otra anomalía o normal. `agrupar` traduce
    ids a la unidad de evaluación (por ejemplo, línea de factura -> factura).
    """
    agrupar = agrupar or {}

    def unidad(ids):
        return {agrupar.get(i, i) for i in ids}

    reales = unidad(ground_truth.loc[ground_truth["tipo_anomalia"].isin(tipos), "id_registro"])
    alertados = unidad(alertas.loc[alertas["regla"].isin(_nombres(regla)), "id_registro"])
    fp = alertados - reales
    legitimos = unidad(casos_legitimos["id_registro"]) if casos_legitimos is not None else set()
    otras = unidad(ground_truth["id_registro"]) - reales
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


def factura_de_cada_linea(facturacion_detalle):
    """Mapa numero_linea -> numero_factura, para evaluar por factura."""
    if facturacion_detalle is None:
        return {}
    return dict(zip(facturacion_detalle["numero_linea"], facturacion_detalle["numero_factura"]))


def contrastar_hipotesis(alertas, ground_truth, casos_legitimos, facturacion_detalle=None):
    """Una fila por hipótesis y regla, más el veredicto de cada hipótesis.

    Las hipótesis cuyas reglas no emitieron ninguna alerta ni tienen casos en el ground
    truth (por ejemplo, H9 sin detalle de facturación) se omiten.
    """
    agrupaciones = {"factura": factura_de_cada_linea(facturacion_detalle)}
    filas, veredictos = [], []
    for h in HIPOTESIS:
        agrupar = agrupaciones.get(h.get("nivel"))
        reales = ground_truth["tipo_anomalia"].isin(h["tipos"]).any()
        if not reales:
            continue
        resultados = []
        for orden, (regla, descripcion) in enumerate(h["reglas"]):
            m = evaluar_regla(alertas, ground_truth, casos_legitimos, regla, h["tipos"], agrupar)
            resultados.append(m)
            filas.append({"hipotesis": h["codigo"], "orden": orden, "regla": describir_regla(regla),
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


# ============================================================================
# Catálogo único para la app
#
# Las hipótesis de HIPOTESIS se contrastan contra el ground truth (escenario
# realista). Las de HIPOTESIS_DESCRIPTIVAS completan el catálogo: H1 aplica a
# ambos escenarios y H2 y H3a son las versiones del escenario didáctico, donde
# no hay casos legítimos con los que contrastar.
# ============================================================================

HIPOTESIS_DESCRIPTIVAS = {
    "H1": {
        "codigo": "H1",
        "titulo": "Vinculación con la flota",
        "enunciado": "Las cargas, los dispositivos y las solicitudes deben vincularse con un vehículo de "
                     "la flota por su dominio; un dominio sin vínculo impide cualquier otro control.",
        "tipos": ["DOMINIO_INVALIDO"],
        "reglas": [("dominio_sin_vinculo", "dominio que no existe en la flota")],
        "contexto": "catálogo de la flota",
    },
    "H2": {
        "codigo": "H2",
        "titulo": "Odómetro",
        "enunciado": "Un odómetro que retrocede o salta más de lo habitual para el vehículo indica una "
                     "lectura adulterada.",
        "tipos": ["ODOMETRO_REGRESIVO", "ODOMETRO_SALTO"],
        "reglas": [("salto_umbral_fijo", ">500 km en ≤7 días"),
                   (["odometro_disminuye", "salto_historial_vehiculo"], "retroceso o salto sobre el ritmo habitual")],
        "contexto": "historial de lecturas del vehículo",
    },
    "H3a": {
        "codigo": "H3a",
        "titulo": "Exceso volumétrico",
        "enunciado": "Cargar más litros que la capacidad del tanque indica combustible que no llegó al vehículo.",
        "tipos": ["EXCESO_VOLUMETRICO"],
        "reglas": [("litros_mayor_a_tanque", "litros > tanque registrado")],
        "contexto": "capacidad registrada del tanque",
    },
}


def hipotesis_del_escenario(escenario):
    """Hipótesis que aplican a un escenario, en el orden en que se presentan."""
    if escenario == "realista":
        return [HIPOTESIS_DESCRIPTIVAS["H1"]] + HIPOTESIS
    return [HIPOTESIS_DESCRIPTIVAS[c] for c in ["H1", "H2", "H3a"]]


def reglas_de(regla):
    """Nombres de reglas de una entrada de `reglas` (str, lista o None)."""
    return _nombres(regla)
