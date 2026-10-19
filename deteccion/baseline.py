"""Línea base ingenua, regla con contexto y modelo baseline de una hipótesis (Sprint 4).

Compara, con la misma unidad (la carga) y el mismo target (las anomalías de los tipos de la hipótesis), la
regla ingenua, la regla con contexto, un Isolation Forest sin etiquetas, una regresión logística (el modelo
baseline: sencillo e interpretable) y un Random Forest de referencia.

Los datos con que se diseñan los modelos (`SEMILLAS_DE_DISENO`) y los con que se evalúan
(`SEMILLAS_DE_EVALUACION`, las del README) son distintos. Los modelos supervisados no usan `ground_truth`,
`tipo_anomalia` ni `casos_legitimos` como variables: solo como etiqueta de entrenamiento y de evaluación.

Si una variable define la propia regla (por ejemplo, litros sobre capacidad en H3b), un modelo que la use
aprende la regla y no demuestra nada. Por eso cada modelo supervisado se evalúa dos veces: con todas las
variables y sin las que definen la regla (`VARIABLES_DE_LA_REGLA`).

Uso:
    python -m deteccion.baseline H3b
    python -m deteccion.baseline H1 --sin ratio_litros_tanque --salida resultados.md
"""
import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from deteccion.datos import cargar_dataset
from deteccion.hipotesis import HIPOTESIS, reglas_de
from deteccion.modelo import construir_variables, entrenar_isolation_forest
from deteccion.reglas import reglas_del_dataset

SEMILLAS_DE_DISENO = [1001, 1002, 1003]
SEMILLAS_DE_EVALUACION = [42, 7, 123, 2024, 99]
UMBRAL = 0.5          # fijo y decidido antes de mirar los datos de evaluación: no se ajusta con ellos

# Variables que definen la regla de la hipótesis: un modelo que las usa aprende la regla
VARIABLES_DE_LA_REGLA = {
    "H3b": ("ratio_litros_tanque", "litros_vs_habitual", "tanques_en_el_dia"),
    "H1": (),
}


def _entrada(hipotesis):
    entradas = {h["codigo"]: h for h in HIPOTESIS}
    if hipotesis not in entradas:
        raise ValueError(f"hipótesis desconocida: {hipotesis}; disponibles: {', '.join(entradas)}")
    return entradas[hipotesis]


def metricas(real, predicho):
    """Matriz de confusión y precisión, recall y F1 de dos vectores booleanos de unidades."""
    real, predicho = np.asarray(real, dtype=bool), np.asarray(predicho, dtype=bool)
    tp, fp = int((real & predicho).sum()), int((~real & predicho).sum())
    fn, tn = int((real & ~predicho).sum()), int((~real & ~predicho).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def _generar(semilla, n_flota):
    from generator_pipeline_maestro import GeneradorMaestro

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directorio:
        resultado = GeneradorMaestro(n_flota=n_flota, seed=semilla, output_dir=directorio,
                                     escenario="realista").ejecutar()
        if not resultado["exito"]:
            raise RuntimeError(resultado["error"])
        return cargar_dataset(directorio)


def _variables(dataset):
    variables = construir_variables(dataset["flota"], dataset["consumo"], dataset.get("estaciones"),
                                    dataset.get("telemetria_diaria"), dataset.get("solicitudes"),
                                    dataset.get("excepciones_odometro"))
    # Una carga sin id o con id repetido no se puede evaluar por transacción (ver construir_variables)
    return variables[~variables.index.duplicated()].fillna(0.0)


def _etiqueta(dataset, variables, tipos):
    ground_truth = dataset["ground_truth"]
    ids = set(ground_truth.loc[ground_truth["tipo_anomalia"].isin(tipos), "id_registro"])
    return pd.Series(variables.index.isin(list(ids)), index=variables.index)


def _bandera_de_reglas(alertas, variables, nombres):
    ids = set(alertas.loc[alertas["regla"].isin(nombres), "id_registro"])
    return pd.Series(variables.index.isin(list(ids)), index=variables.index)


def _modelos(semilla=42):
    return {
        "regresion_logistica": make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=semilla)),
        "random_forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=semilla,
                                                class_weight="balanced_subsample", n_jobs=-1),
    }


def _resumir(por_semilla):
    """Suma las matrices de confusión de las semillas y resume la estabilidad del F1."""
    suma = {k: sum(m[k] for m in por_semilla) for k in ("tp", "fp", "fn", "tn")}
    tp, fp, fn = suma["tp"], suma["fp"], suma["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1s = [m["f1"] for m in por_semilla]
    return {**suma, "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "f1_por_semilla": [round(f, 3) for f in f1s], "f1_media": float(np.mean(f1s)),
            "f1_desvio": float(np.std(f1s))}


def evaluar(hipotesis, semillas_de_diseno=None, semillas_de_evaluacion=None, n_flota=200, excluir=None,
            progreso=None):
    """Evalúa la hipótesis con cada método y devuelve un diccionario con las métricas.

    `excluir`: variables que no usa el segundo escenario de cada modelo; por defecto, las que definen la regla.
    """
    entrada = _entrada(hipotesis)
    diseno = SEMILLAS_DE_DISENO if semillas_de_diseno is None else list(semillas_de_diseno)
    evaluacion = SEMILLAS_DE_EVALUACION if semillas_de_evaluacion is None else list(semillas_de_evaluacion)
    if set(diseno) & set(evaluacion):
        raise ValueError("las semillas de diseño y de evaluación no pueden compartirse")
    excluir = tuple(VARIABLES_DE_LA_REGLA.get(hipotesis, ()) if excluir is None else excluir)
    ingenuas, contexto = reglas_de(entrada["reglas"][0][0]), reglas_de(entrada["reglas"][-1][0])
    tipos = entrada["tipos"]

    partes_x, partes_y = [], []
    for semilla in diseno:
        dataset = _generar(semilla, n_flota)
        variables = _variables(dataset)
        partes_x.append(variables.reset_index(drop=True))
        partes_y.append(_etiqueta(dataset, variables, tipos).reset_index(drop=True))
        if progreso:
            progreso(f"diseño {semilla}")
    x_diseno, y_diseno = pd.concat(partes_x, ignore_index=True), pd.concat(partes_y, ignore_index=True)
    columnas = {"todas": list(x_diseno.columns),
                "sin_las_de_la_regla": [c for c in x_diseno.columns if c not in excluir]}
    entrenados = {}
    if int(y_diseno.sum()) > 0:
        for escenario, cols in columnas.items():
            for nombre, modelo in _modelos().items():
                entrenados[(nombre, escenario)] = (modelo.fit(x_diseno[cols], y_diseno), cols)

    por_metodo = {}
    positivos = 0
    for semilla in evaluacion:
        dataset = _generar(semilla, n_flota)
        variables = _variables(dataset)
        real = _etiqueta(dataset, variables, tipos)
        positivos += int(real.sum())
        alertas = reglas_del_dataset(dataset)
        predicciones = {"linea_base_ingenua": _bandera_de_reglas(alertas, variables, ingenuas),
                        "regla_con_contexto": _bandera_de_reglas(alertas, variables, contexto)}
        _, anomalo = entrenar_isolation_forest(variables)
        predicciones["isolation_forest"] = anomalo.reindex(variables.index).fillna(False)
        for (nombre, escenario), (modelo, cols) in entrenados.items():
            probabilidad = modelo.predict_proba(variables.reindex(columns=cols, fill_value=0.0))[:, 1]
            predicciones[f"{nombre}__{escenario}"] = pd.Series(probabilidad >= UMBRAL, index=variables.index)
        for metodo, predicho in predicciones.items():
            por_metodo.setdefault(metodo, []).append(metricas(real, predicho))
        if progreso:
            progreso(f"evaluación {semilla}")

    return {"hipotesis": hipotesis, "tipos": tipos, "unidad": "carga", "umbral": UMBRAL,
            "semillas_de_diseno": diseno, "semillas_de_evaluacion": evaluacion, "n_flota": n_flota,
            "anomalias_en_evaluacion": positivos, "variables_excluidas": list(excluir),
            "metodos": {m: _resumir(v) for m, v in por_metodo.items()}}


ETIQUETAS = {"linea_base_ingenua": "Línea base ingenua", "regla_con_contexto": "Regla con contexto",
             "isolation_forest": "Isolation Forest (sin etiquetas)",
             "regresion_logistica__todas": "Regresión logística, todas las variables",
             "regresion_logistica__sin_las_de_la_regla": "Regresión logística, sin las variables de la regla",
             "random_forest__todas": "Random Forest, todas las variables",
             "random_forest__sin_las_de_la_regla": "Random Forest, sin las variables de la regla"}


def a_markdown(resultado):
    """Tabla de comparación lista para el informe."""
    filas = ["| Método | Precisión | Recall | F1 | F1 por semilla (media ± desvío) | TP | FP | FN | TN |",
             "|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    for metodo, m in resultado["metodos"].items():
        filas.append(f"| {ETIQUETAS.get(metodo, metodo)} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | "
                     f"{m['f1_media']:.2f} ± {m['f1_desvio']:.2f} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |")
    return (f"**{resultado['hipotesis']}** ({', '.join(resultado['tipos'])}), unidad: {resultado['unidad']}. "
            f"Diseño con las semillas {resultado['semillas_de_diseno']}; evaluación con "
            f"{resultado['semillas_de_evaluacion']} ({resultado['anomalias_en_evaluacion']} anomalías en total). "
            f"Umbral fijo {resultado['umbral']}. Variables excluidas en el segundo escenario: "
            f"{', '.join(resultado['variables_excluidas']) or 'ninguna'}.\n\n" + "\n".join(filas))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hipotesis")
    parser.add_argument("--sin", help="variables a excluir en el segundo escenario, separadas por coma")
    parser.add_argument("--n-flota", type=int, default=200)
    parser.add_argument("--salida", type=Path, help="archivo donde guardar la tabla en Markdown (y el JSON al lado)")
    args = parser.parse_args()
    excluir = [v for v in args.sin.split(",") if v] if args.sin is not None else None
    resultado = evaluar(args.hipotesis, n_flota=args.n_flota, excluir=excluir, progreso=print)
    tabla = a_markdown(resultado)
    print("\n" + tabla)
    if args.salida:
        args.salida.write_text(tabla + "\n", encoding="utf-8")
        args.salida.with_suffix(".json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False),
                                                    encoding="utf-8")


if __name__ == "__main__":
    main()
