"""Evaluación de alertas contra el ground truth.

Una alerta es un acierto (TP) cuando el ground truth registra esa misma anomalía
(mismo id_registro y mismo tipo_anomalia). Las alertas que no están en el ground
truth son falsos positivos (FP) y las anomalías del ground truth que nadie alertó
son falsos negativos (FN).
"""
import pandas as pd

CLAVE = ["id_registro", "tipo_anomalia"]


def _metricas(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    if tp + fp + fn == 0:
        f1 = float("nan")
    elif tp == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _pares(df):
    return set(map(tuple, df[CLAVE].drop_duplicates().itertuples(index=False)))


def evaluar_por_tipo(alertas, ground_truth, filtro_regla=None):
    """Métricas por tipo de anomalía.

    Si varias reglas atribuyen el mismo tipo, se consideran juntas (unión de sus
    alertas), salvo que `filtro_regla` restrinja a un conjunto de reglas.
    """
    if filtro_regla is not None:
        alertas = alertas[alertas["regla"].isin(filtro_regla)]
    predichas = _pares(alertas)
    reales = _pares(ground_truth)
    filas = []
    for tipo in sorted({t for _, t in reales} | {t for _, t in predichas}):
        p = {x for x in predichas if x[1] == tipo}
        r = {x for x in reales if x[1] == tipo}
        filas.append({"tipo_anomalia": tipo, "reales": len(r), "alertas": len(p),
                      **_metricas(len(p & r), len(p - r), len(r - p))})
    return pd.DataFrame(filas)


def evaluar_por_regla(alertas, ground_truth):
    """Métricas de cada regla por separado, contra las anomalías del tipo que detecta."""
    reales = _pares(ground_truth)
    filas = []
    for (regla, tipo), grupo in alertas.groupby(["regla", "tipo_anomalia"]):
        p = _pares(grupo)
        r = {x for x in reales if x[1] == tipo}
        # Las reglas de nulos cubren un campo cada una: se comparan contra las
        # anomalías de ese campo
        if tipo == "VALOR_NULO":
            campo = regla.removeprefix("nulo_")
            ids = set(ground_truth.loc[(ground_truth["tipo_anomalia"] == tipo)
                                       & (ground_truth["columna"] == campo), "id_registro"])
            r = {(i, tipo) for i in ids}
        filas.append({"regla": regla, "tipo_anomalia": tipo, "reales": len(r), "alertas": len(p),
                      **_metricas(len(p & r), len(p - r), len(r - p))})
    return pd.DataFrame(filas)


def errores(alertas, ground_truth, tipo, filtro_regla=None):
    """Falsos positivos y falsos negativos de un tipo, para inspeccionarlos."""
    if filtro_regla is not None:
        alertas = alertas[alertas["regla"].isin(filtro_regla)]
    a = alertas[alertas["tipo_anomalia"] == tipo]
    g = ground_truth[ground_truth["tipo_anomalia"] == tipo]
    fp = a[~a["id_registro"].isin(g["id_registro"])]
    fn = g[~g["id_registro"].isin(a["id_registro"])]
    return fp, fn


def evaluar_binario(ids_alertados, ids_anomalos, universo):
    """Métricas de una clasificación anómalo / normal a nivel de transacción."""
    alertados, anomalos = set(ids_alertados), set(ids_anomalos)
    tp = len(alertados & anomalos)
    fp = len(alertados - anomalos)
    fn = len(anomalos - alertados)
    return {**_metricas(tp, fp, fn), "tn": len(set(universo)) - tp - fp - fn}
