"""Línea base ingenua, regla con contexto y modelo baseline de una hipótesis (Sprint 4).

Compara, con la misma unidad (la carga) y el mismo target (las anomalías de los tipos de la hipótesis), la
regla ingenua, la regla con contexto, un Isolation Forest sin etiquetas, una regresión logística (el modelo
baseline: sencillo e interpretable) y un Random Forest de referencia.

Los datos con que se diseñan los modelos (`SEMILLAS_DE_DISENO`) y los con que se evalúan
(`SEMILLAS_DE_EVALUACION`, las del README) son distintos. Los modelos supervisados no usan `ground_truth`,
`tipo_anomalia` ni `casos_legitimos` como variables: solo como etiqueta de entrenamiento y de evaluación.

Si una variable define la propia regla (por ejemplo, litros sobre capacidad en H3b), un modelo que la use
aprende la regla y no demuestra nada. Por eso cada modelo supervisado se evalúa dos veces: con todas las
variables y sin las que definen la regla (`VARIABLES_DE_LA_REGLA`, un supuesto por hipótesis a revisar).

Solo las hipótesis cuya unidad es la carga (`HIPOTESIS_POR_CARGA`): las de factura (H9), de contrato y mes
(H10) y de dispositivo (H11) tienen otra unidad. Donde el target incluye registros que no son cargas (por
ejemplo, pedidos sin carga en H8), solo cuentan los que son una carga.

Uso:
    python -m deteccion.baseline H3b
    python -m deteccion.baseline H1 --sin ratio_litros_tanque --salida resultados.md
    python -m deteccion.baseline todas --salida resumen.md
"""
import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from deteccion.datos import cargar_dataset
from deteccion.hipotesis import HIPOTESIS, reglas_de
from deteccion.modelo import construir_variables, entrenar_isolation_forest
from deteccion.reglas import reglas_del_dataset

SEMILLAS_DE_DISENO = [1001, 1002, 1003]
SEMILLAS_DE_EVALUACION = [42, 7, 123, 2024, 99]
UMBRAL = 0.5          # fijo y decidido antes de mirar los datos de evaluación: no se ajusta con ellos
HIPOTESIS_POR_CARGA = ["H1", "H2b", "H2c", "H3b", "H4", "H5", "H6", "H7", "H8", "H12", "H13"]

# Variables que definen la regla de la hipótesis: un modelo que las usa aprende la regla. Es un supuesto de
# diseño (qué variables entran en la regla), a revisar con el equipo.
VARIABLES_DE_LA_REGLA = {
    "H1": (),
    "H2b": ("km", "exceso_km", "retroceso_km"),
    "H2c": ("km", "exceso_km", "retroceso_km"),
    "H3b": ("ratio_litros_tanque", "litros_vs_habitual", "tanques_en_el_dia"),
    # La regla con contexto es "fraccionamiento sin recorrido": el recorrido (km, rendimiento) es parte de la
    # regla. Sin excluirlo, el modelo veía la mitad de la regla y llegaba a 0,76 de F1; al quitar las 2 más
    # importantes (rendimiento_relativo y km) cae a 0,05 (ver `explicar`)
    "H4": ("cargas_en_el_dia", "tanques_en_el_dia", "rendimiento_relativo", "km", "exceso_km"),
    "H5": ("rendimiento_relativo",),
    "H6": ("vehiculo_inactivo",),
    "H7": ("distancia_zona_km", "distancia_gps_km", "sin_gps"),
    "H8": ("sin_solicitud", "litros_vs_autorizado"),
    "H12": ("km", "odometro_exceptuado"),
    "H13": (),
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


def ordenamiento(real, puntaje):
    """Qué tan bien ordena el método (sin umbral): precisión promedio y precisión en las primeras k cargas.

    k es la cantidad de anomalías reales: si el método ordenara perfecto, las k primeras serían todas anómalas.
    """
    real, puntaje = np.asarray(real, dtype=bool), np.asarray(puntaje, dtype=float)
    k = int(real.sum())
    if k == 0:
        return {"ap": 0.0, "precision_en_k": 0.0}
    primeras = np.argsort(-puntaje, kind="stable")[:k]
    return {"ap": float(average_precision_score(real, puntaje)), "precision_en_k": float(real[primeras].mean())}


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


def _modelos(semilla=42, n_arboles=300):
    return {
        "regresion_logistica": make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=semilla)),
        "random_forest": RandomForestClassifier(n_estimators=n_arboles, min_samples_leaf=2, random_state=semilla,
                                                class_weight="balanced_subsample", n_jobs=-1),
    }


def _resumir(por_semilla):
    """Suma las matrices de confusión de las semillas y resume la estabilidad del F1."""
    suma = {k: sum(m[k] for m in por_semilla) for k in ("tp", "fp", "fn", "tn")}
    tp, fp, fn = suma["tp"], suma["fp"], suma["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1s = [m["f1"] for m in por_semilla]
    return {**suma, "ap_media": float(np.mean([m["ap"] for m in por_semilla])),
            "precision_en_k_media": float(np.mean([m["precision_en_k"] for m in por_semilla])),
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "f1_por_semilla": [round(f, 3) for f in f1s], "f1_media": float(np.mean(f1s)),
            "f1_desvio": float(np.std(f1s))}


def evaluar_varias(hipotesis, semillas_de_diseno=None, semillas_de_evaluacion=None, n_flota=200, excluir=None,
                   n_arboles=300, progreso=None):
    """Evalúa cada hipótesis con cada método y devuelve {hipótesis: resultado}.

    Genera cada dataset una sola vez, sin importar cuántas hipótesis se pidan. `excluir`: variables que no usa el
    segundo escenario de cada modelo (solo con una hipótesis); por defecto, las de `VARIABLES_DE_LA_REGLA`.
    """
    hipotesis = list(hipotesis)
    entradas = {h: _entrada(h) for h in hipotesis}
    diseno = SEMILLAS_DE_DISENO if semillas_de_diseno is None else list(semillas_de_diseno)
    evaluacion = SEMILLAS_DE_EVALUACION if semillas_de_evaluacion is None else list(semillas_de_evaluacion)
    if set(diseno) & set(evaluacion):
        raise ValueError("las semillas de diseño y de evaluación no pueden compartirse")
    if excluir is not None and len(hipotesis) != 1:
        raise ValueError("`excluir` solo se puede usar con una hipótesis")
    excluidas = {h: tuple(VARIABLES_DE_LA_REGLA.get(h, ()) if excluir is None else excluir) for h in hipotesis}

    partes_x, partes_y = [], {h: [] for h in hipotesis}
    for semilla in diseno:
        dataset = _generar(semilla, n_flota)
        variables = _variables(dataset)
        partes_x.append(variables.reset_index(drop=True))
        for h in hipotesis:
            partes_y[h].append(_etiqueta(dataset, variables, entradas[h]["tipos"]).reset_index(drop=True))
        if progreso:
            progreso(f"diseño {semilla}")
    x_diseno = pd.concat(partes_x, ignore_index=True)

    entrenados = {h: {} for h in hipotesis}
    for h in hipotesis:
        y = pd.concat(partes_y[h], ignore_index=True)
        if int(y.sum()) == 0:
            continue
        columnas = {"todas": list(x_diseno.columns),
                    "sin_las_de_la_regla": [c for c in x_diseno.columns if c not in excluidas[h]]}
        for escenario, cols in columnas.items():
            for nombre, modelo in _modelos(n_arboles=n_arboles).items():
                entrenados[h][(nombre, escenario)] = (modelo.fit(x_diseno[cols], y), cols)
        if progreso:
            progreso(f"modelos {h}")

    por_metodo = {h: {} for h in hipotesis}
    positivos = {h: 0 for h in hipotesis}
    for semilla in evaluacion:
        dataset = _generar(semilla, n_flota)
        variables = _variables(dataset)
        alertas = reglas_del_dataset(dataset)
        puntaje_if, anomalo = entrenar_isolation_forest(variables)
        anomalo = anomalo.reindex(variables.index).fillna(False)
        for h in hipotesis:
            real = _etiqueta(dataset, variables, entradas[h]["tipos"])
            positivos[h] += int(real.sum())
            reglas = entradas[h]["reglas"]
            predicciones = {"linea_base_ingenua": _bandera_de_reglas(alertas, variables, reglas_de(reglas[0][0])),
                            "regla_con_contexto": _bandera_de_reglas(alertas, variables, reglas_de(reglas[-1][0])),
                            "isolation_forest": anomalo}
            puntajes = {"linea_base_ingenua": predicciones["linea_base_ingenua"].astype(float),
                        "regla_con_contexto": predicciones["regla_con_contexto"].astype(float),
                        "isolation_forest": puntaje_if.reindex(variables.index).fillna(0.0)}
            for (nombre, escenario), (modelo, cols) in entrenados[h].items():
                probabilidad = modelo.predict_proba(variables.reindex(columns=cols, fill_value=0.0))[:, 1]
                predicciones[f"{nombre}__{escenario}"] = pd.Series(probabilidad >= UMBRAL, index=variables.index)
                puntajes[f"{nombre}__{escenario}"] = pd.Series(probabilidad, index=variables.index)
            for metodo, predicho in predicciones.items():
                por_metodo[h].setdefault(metodo, []).append({**metricas(real, predicho),
                                                              **ordenamiento(real, puntajes[metodo])})
        if progreso:
            progreso(f"evaluación {semilla}")

    return {h: {"hipotesis": h, "tipos": entradas[h]["tipos"], "unidad": "carga", "umbral": UMBRAL,
                "semillas_de_diseno": diseno, "semillas_de_evaluacion": evaluacion, "n_flota": n_flota,
                "anomalias_en_evaluacion": positivos[h], "variables_excluidas": list(excluidas[h]),
                "metodos": {m: _resumir(v) for m, v in por_metodo[h].items()}} for h in hipotesis}


def evaluar(hipotesis, semillas_de_diseno=None, semillas_de_evaluacion=None, n_flota=200, excluir=None,
            n_arboles=300, progreso=None):
    """Evalúa una hipótesis (ver `evaluar_varias`)."""
    return evaluar_varias([hipotesis], semillas_de_diseno, semillas_de_evaluacion, n_flota, excluir, n_arboles,
                          progreso)[hipotesis]


def explicar(hipotesis, semillas_de_diseno=None, semillas_de_evaluacion=None, n_flota=200, excluir=None,
             n_arboles=300, progreso=None):
    """Qué variables sostienen el modelo de una hipótesis (para justificarlas una por una).

    Con el escenario sin las variables de la regla: los coeficientes estandarizados de la regresión
    logística, la importancia por permutación de cada variable en el Random Forest (sobre los datos de
    evaluación, medida con la precisión promedio, que no depende del umbral) y una ablación: el F1 del
    Random Forest al quitar las `k` variables más importantes. Si el F1 cae casi a cero al quitar una o dos,
    el modelo depende de ellas y conviene preguntarse si el generador las delata.
    """
    from sklearn.inspection import permutation_importance

    entrada = _entrada(hipotesis)
    diseno = SEMILLAS_DE_DISENO if semillas_de_diseno is None else list(semillas_de_diseno)
    evaluacion = SEMILLAS_DE_EVALUACION if semillas_de_evaluacion is None else list(semillas_de_evaluacion)
    if set(diseno) & set(evaluacion):
        raise ValueError("las semillas de diseño y de evaluación no pueden compartirse")
    excluidas = tuple(VARIABLES_DE_LA_REGLA.get(hipotesis, ()) if excluir is None else excluir)
    tipos = entrada["tipos"]

    def datos(semillas, etapa):
        partes_x, partes_y = [], []
        for semilla in semillas:
            dataset = _generar(semilla, n_flota)
            variables = _variables(dataset)
            partes_x.append(variables.reset_index(drop=True))
            partes_y.append(_etiqueta(dataset, variables, tipos).reset_index(drop=True))
            if progreso:
                progreso(f"{etapa} {semilla}")
        return pd.concat(partes_x, ignore_index=True), pd.concat(partes_y, ignore_index=True)

    x_diseno, y_diseno = datos(diseno, "diseño")
    x_eval, y_eval = datos(evaluacion, "evaluación")
    columnas = [c for c in x_diseno.columns if c not in excluidas]
    modelos = _modelos(n_arboles=n_arboles)
    logistica, bosque = modelos["regresion_logistica"], modelos["random_forest"]
    logistica.fit(x_diseno[columnas], y_diseno)
    bosque.fit(x_diseno[columnas], y_diseno)
    coeficientes = pd.Series(logistica[-1].coef_[0], index=columnas).sort_values(key=abs, ascending=False)
    importancia = permutation_importance(bosque, x_eval[columnas], y_eval, scoring="average_precision",
                                         n_repeats=3, random_state=42, n_jobs=-1)
    por_permutacion = pd.Series(importancia.importances_mean, index=columnas).sort_values(ascending=False)

    ablacion = {"sin_ninguna": metricas(y_eval, bosque.predict_proba(x_eval[columnas])[:, 1] >= UMBRAL)["f1"]}
    for k in (1, 2, 3):
        quedan = [c for c in columnas if c not in set(por_permutacion.index[:k])]
        modelo = _modelos(n_arboles=n_arboles)["random_forest"].fit(x_diseno[quedan], y_diseno)
        ablacion[f"sin_las_{k}_mas_importantes"] = metricas(
            y_eval, modelo.predict_proba(x_eval[quedan])[:, 1] >= UMBRAL)["f1"]
    return {"hipotesis": hipotesis, "variables_excluidas": list(excluidas),
            "semillas_de_diseno": diseno, "semillas_de_evaluacion": evaluacion,
            "coeficientes_de_la_regresion_logistica": {k: float(v) for k, v in coeficientes.items()},
            "importancia_por_permutacion_del_random_forest": {k: float(v) for k, v in por_permutacion.items()},
            "f1_del_random_forest_al_quitar_las_mas_importantes": ablacion}


def explicar_a_markdown(resultado):
    """Las tres tablas de `explicar`, listas para el informe."""
    orden = list(resultado["importancia_por_permutacion_del_random_forest"])
    filas = ["| Variable | Importancia (Random Forest, por permutación) | Coeficiente (regresión logística, estandarizado) |",
             "|---|---:|---:|"]
    for v in orden:
        filas.append(f"| {v} | {resultado['importancia_por_permutacion_del_random_forest'][v]:.4f} | "
                     f"{resultado['coeficientes_de_la_regresion_logistica'][v]:+.2f} |")
    ablacion = ["| Se quitan | F1 del Random Forest |", "|---|---:|"]
    for k, f1 in resultado["f1_del_random_forest_al_quitar_las_mas_importantes"].items():
        ablacion.append(f"| {k.replace('_', ' ')} | {f1:.2f} |")
    return (f"**{resultado['hipotesis']}**: variables del modelo sin las de la regla "
            f"({', '.join(resultado['variables_excluidas']) or 'ninguna excluida'}).\n\n"
            + "\n".join(filas) + "\n\n" + "\n".join(ablacion))


ETIQUETAS = {"linea_base_ingenua": "Línea base ingenua", "regla_con_contexto": "Regla con contexto",
             "isolation_forest": "Isolation Forest (sin etiquetas)",
             "regresion_logistica__todas": "Regresión logística, todas las variables",
             "regresion_logistica__sin_las_de_la_regla": "Regresión logística, sin las variables de la regla",
             "random_forest__todas": "Random Forest, todas las variables",
             "random_forest__sin_las_de_la_regla": "Random Forest, sin las variables de la regla"}


def a_markdown(resultado):
    """Tabla de comparación de una hipótesis, lista para el informe."""
    filas = ["| Método | Precisión | Recall | F1 | F1 por semilla (media ± desvío) | Precisión promedio (sin umbral) | "
             "Precisión en las primeras k | TP | FP | FN | TN |", "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for metodo, m in resultado["metodos"].items():
        filas.append(f"| {ETIQUETAS.get(metodo, metodo)} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | "
                     f"{m['f1_media']:.2f} ± {m['f1_desvio']:.2f} | {m['ap_media']:.2f} | "
                     f"{m['precision_en_k_media']:.2f} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |")
    return (f"**{resultado['hipotesis']}** ({', '.join(resultado['tipos'])}), unidad: {resultado['unidad']}. "
            f"Diseño con las semillas {resultado['semillas_de_diseno']}; evaluación con "
            f"{resultado['semillas_de_evaluacion']} ({resultado['anomalias_en_evaluacion']} anomalías en total). "
            f"Umbral fijo {resultado['umbral']}. Variables excluidas en el segundo escenario: "
            f"{', '.join(resultado['variables_excluidas']) or 'ninguna'}.\n\n" + "\n".join(filas))


def resumen_markdown(resultados):
    """Una fila por hipótesis: cuántas anomalías hay y qué F1 logra cada método, sin trampa y con ella."""
    def f1(r, metodo):
        m = r["metodos"].get(metodo)
        return f"{m['f1']:.2f}" if m else "—"

    filas = ["| Hipótesis | Anomalías | Ingenua | Con contexto | Isolation Forest | Logística (sin las de la regla) | "
             "Random Forest (sin las de la regla) | Random Forest (todas) |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for h, r in resultados.items():
        filas.append(f"| {h} | {r['anomalias_en_evaluacion']} | {f1(r, 'linea_base_ingenua')} | "
                     f"{f1(r, 'regla_con_contexto')} | {f1(r, 'isolation_forest')} | "
                     f"{f1(r, 'regresion_logistica__sin_las_de_la_regla')} | "
                     f"{f1(r, 'random_forest__sin_las_de_la_regla')} | {f1(r, 'random_forest__todas')} |")
    return "\n".join(filas)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hipotesis", nargs="+", help="una o varias hipótesis, o 'todas' (las de unidad carga)")
    parser.add_argument("--sin", help="variables a excluir en el segundo escenario (solo con una hipótesis)")
    parser.add_argument("--n-flota", type=int, default=200)
    parser.add_argument("--n-arboles", type=int, default=300)
    parser.add_argument("--salida", type=Path, help="archivo donde guardar la tabla en Markdown (y el JSON al lado)")
    parser.add_argument("--explicar", action="store_true",
                        help="en vez de comparar métodos, muestra qué variables sostienen el modelo (una hipótesis)")
    args = parser.parse_args()
    if args.explicar:
        if len(args.hipotesis) != 1:
            parser.error("--explicar se usa con una sola hipótesis")
        explicacion = explicar(args.hipotesis[0], n_flota=args.n_flota, n_arboles=args.n_arboles,
                               excluir=[v for v in args.sin.split(",") if v] if args.sin is not None else None,
                               progreso=print)
        texto = explicar_a_markdown(explicacion)
        print("\n" + texto)
        if args.salida:
            args.salida.write_text(texto + "\n", encoding="utf-8")
            args.salida.with_suffix(".json").write_text(json.dumps(explicacion, indent=2, ensure_ascii=False),
                                                        encoding="utf-8")
        return
    lista = HIPOTESIS_POR_CARGA if args.hipotesis == ["todas"] else args.hipotesis
    excluir = [v for v in args.sin.split(",") if v] if args.sin is not None else None
    resultados = evaluar_varias(lista, n_flota=args.n_flota, excluir=excluir, n_arboles=args.n_arboles,
                                progreso=print)
    texto = (resumen_markdown(resultados) + "\n\n" if len(resultados) > 1 else "") + "\n\n".join(
        a_markdown(r) for r in resultados.values())
    print("\n" + texto)
    if args.salida:
        args.salida.write_text(texto + "\n", encoding="utf-8")
        args.salida.with_suffix(".json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False),
                                                    encoding="utf-8")


if __name__ == "__main__":
    main()
