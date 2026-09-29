"""Evaluación de alertas contra el ground truth.

Una alerta es un acierto (TP) cuando el ground truth registra esa misma anomalía
(mismo id_registro y mismo tipo_anomalia). Las alertas que no están en el ground
truth son falsos positivos (FP) y las anomalías del ground truth que nadie alertó
son falsos negativos (FN).

Para qué sirve este archivo
---------------------------
Las reglas (`reglas.py`) y los modelos (`modelo.py`) producen alertas, pero eso
solo no dice si son buenas. Este módulo las "corrige" como un examen, comparándolas
con el ground truth (la lista de anomalías que el generador inyectó a propósito).
Lo usan `__main__.py`, `modelo.py` y la aplicación Streamlit.

Conceptos básicos (se usan en todo el proyecto)
-----------------------------------------------
- TP, verdadero positivo: la alerta era correcta (había una anomalía de verdad).
- FP, falso positivo o "falsa alarma": se alertó algo que en realidad era normal.
  En auditoría cuestan tiempo: alguien revisa un caso que no tenía problema.
- FN, falso negativo: una anomalía real que ningún método detectó (se escapó).
- TN, verdadero negativo: un registro normal que correctamente no se alertó.
- Precision (precisión) = TP / (TP + FP): de todo lo que se alertó, qué fracción
  era realmente una anomalía. Alta precision = pocas falsas alarmas.
- Recall (sensibilidad o exhaustividad) = TP / (TP + FN): de todas las anomalías
  reales, qué fracción se detectó. Alto recall = se escapan pocas.
- F1 = 2 * precision * recall / (precision + recall): un único número entre 0 y 1
  que resume ambas (su media armónica). Solo es alto si precision y recall lo son a
  la vez; alertar todo (recall alto, precision baja) o casi nada (al revés) da F1 bajo.
"""
import pandas as pd

# Una anomalía se identifica por el par (registro, tipo): el mismo registro puede
# tener dos anomalías distintas y cada una cuenta por separado.
CLAVE = ["id_registro", "tipo_anomalia"]


def _metricas(tp, fp, fn):
    """Calcula precision, recall y F1 a partir de los conteos de aciertos y errores.

    Recibe: tp (aciertos), fp (falsas alarmas) y fn (anomalías no detectadas).
    Devuelve: un diccionario con los tres conteos y las tres métricas.
    Cuando una división no tiene sentido (por ejemplo, no hubo ninguna alerta y
    entonces la precision sería 0/0) se devuelve NaN ("no es un número"), que
    significa "no se puede calcular" y es distinto de cero.
    """
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
    """Convierte una tabla de alertas o del ground truth en un conjunto de pares (id_registro, tipo_anomalia).

    Usar conjuntos (sets) permite calcular aciertos y errores con operaciones simples:
    la intersección (&) son los TP, y la diferencia (-) son los FP o los FN.
    """
    return set(map(tuple, df[CLAVE].drop_duplicates().itertuples(index=False)))


def evaluar_por_tipo(alertas, ground_truth, filtro_regla=None):
    """Métricas por tipo de anomalía.

    Si varias reglas atribuyen el mismo tipo, se consideran juntas (unión de sus
    alertas), salvo que `filtro_regla` restrinja a un conjunto de reglas.

    Recibe: la tabla de alertas (de `reglas.ejecutar_reglas`), el ground truth y,
    opcionalmente, una lista de nombres de reglas a considerar.
    Devuelve: una tabla con una fila por tipo de anomalía (cuántas había, cuántas
    se alertaron, TP, FP, FN, precision, recall y F1).
    """
    if filtro_regla is not None:
        alertas = alertas[alertas["regla"].isin(filtro_regla)]
    predichas = _pares(alertas)
    reales = _pares(ground_truth)
    filas = []
    for tipo in sorted({t for _, t in reales} | {t for _, t in predichas}):
        p = {x for x in predichas if x[1] == tipo}
        r = {x for x in reales if x[1] == tipo}
        # p & r: alertadas y reales (TP); p - r: alertadas pero no reales (FP);
        # r - p: reales pero no alertadas (FN)
        filas.append({"tipo_anomalia": tipo, "reales": len(r), "alertas": len(p),
                      **_metricas(len(p & r), len(p - r), len(r - p))})
    return pd.DataFrame(filas)


def evaluar_por_regla(alertas, ground_truth):
    """Métricas de cada regla por separado, contra las anomalías del tipo que detecta.

    Sirve para ver cuál regla concreta funciona mejor o genera más falsas alarmas.
    Devuelve una tabla con una fila por regla.
    """
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
    """Falsos positivos y falsos negativos de un tipo, para inspeccionarlos.

    Devuelve dos tablas: `fp` (alertas que no correspondían a ninguna anomalía real
    de ese tipo) y `fn` (anomalías reales de ese tipo que no se alertaron). Se usa
    para el "análisis de errores": mirar caso por caso por qué se equivocó una regla.
    """
    if filtro_regla is not None:
        alertas = alertas[alertas["regla"].isin(filtro_regla)]
    a = alertas[alertas["tipo_anomalia"] == tipo]
    g = ground_truth[ground_truth["tipo_anomalia"] == tipo]
    fp = a[~a["id_registro"].isin(g["id_registro"])]
    fn = g[~g["id_registro"].isin(a["id_registro"])]
    return fp, fn


def evaluar_binario(ids_alertados, ids_anomalos, universo):
    """Métricas de una clasificación anómalo / normal a nivel de transacción.

    A diferencia de las funciones anteriores, acá no importa el tipo de anomalía:
    solo si cada transacción fue marcada o no. Recibe los ids alertados, los ids
    realmente anómalos y el universo (todos los ids evaluados). Devuelve las
    métricas de `_metricas` más `tn` (normales correctamente no alertados). Se usa
    para comparar las reglas con el Isolation Forest en `modelo.py`.
    """
    alertados, anomalos = set(ids_alertados), set(ids_anomalos)
    tp = len(alertados & anomalos)
    fp = len(alertados - anomalos)
    fn = len(anomalos - alertados)
    return {**_metricas(tp, fp, fn), "tn": len(set(universo)) - tp - fp - fn}
