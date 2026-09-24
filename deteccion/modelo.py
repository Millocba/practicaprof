"""Detección no supervisada con Isolation Forest, comparada con la línea base de reglas.

El modelo trabaja con variables derivadas de las entidades (nunca del ground truth)
y se evalúa sobre las anomalías de comportamiento: exceso volumétrico (H3a) y
retrocesos o saltos de odómetro (H2). Los defectos de calidad (duplicados, nulos,
dominios sin vínculo) no son un problema de detección de outliers y los cubren
las reglas.

El umbral no se ajusta con la tasa real de anomalías (eso filtraría el ground
truth): se usa `contamination="auto"` y además se informa la precisión promedio,
que no depende de ningún umbral.
"""
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score

from deteccion.evaluacion import evaluar_binario
from deteccion.reglas import detectar_duplicados, ejecutar_reglas, secuencia_odometro

TIPOS_COMPORTAMIENTO = ["EXCESO_VOLUMETRICO", "ODOMETRO_REGRESIVO", "ODOMETRO_SALTO"]
REGLAS_COMPORTAMIENTO = ["litros_mayor_a_tanque", "odometro_disminuye", "salto_historial_vehiculo"]

VARIABLES = {
    "ratio_litros_tanque": "litros cargados / capacidad del tanque",
    "km": "cambio de odómetro desde la carga anterior válida",
    "exceso_km": "km recorridos por encima del ritmo habitual del vehículo",
}


def construir_variables(flota, consumo):
    """Una fila por transacción con las variables del modelo.

    Las transacciones sin carga anterior válida (primera del vehículo, odómetro
    vacío o duplicado) reciben 0 en las variables de odómetro: no hay cambio
    que evaluar.
    """
    capacidad = consumo["vehiculo_id"].map(flota.set_index("Matricula")["CapacidadTanque"])
    duplicados = detectar_duplicados(consumo)["id_registro"]
    seq = secuencia_odometro(consumo, excluir_ids=duplicados).set_index("id")

    variables = pd.DataFrame({"id": consumo["id"]}).set_index("id")
    variables["ratio_litros_tanque"] = (consumo["litros"] / capacidad).values
    variables["km"] = seq["km"].reindex(variables.index).fillna(0)
    variables["exceso_km"] = (seq["km"] - seq["km_esperados"]).reindex(variables.index).fillna(0)
    return variables


def entrenar_isolation_forest(variables, seed=42):
    """Ajusta el modelo y devuelve (puntaje de anomalía, marca de anómalo) por transacción.

    Puntaje más alto = más anómalo.
    """
    modelo = IsolationForest(n_estimators=300, contamination="auto", random_state=seed)
    modelo.fit(variables)
    puntaje = pd.Series(-modelo.score_samples(variables), index=variables.index, name="puntaje")
    anomalo = pd.Series(modelo.predict(variables) == -1, index=variables.index, name="anomalo")
    return puntaje, anomalo


def ids_con_anomalia_de_comportamiento(ground_truth):
    return set(ground_truth.loc[ground_truth["tipo_anomalia"].isin(TIPOS_COMPORTAMIENTO), "id_registro"])


def comparar_con_reglas(flota, consumo, ground_truth, seed=42):
    """Compara Isolation Forest y las reglas sobre las anomalías de comportamiento.

    Devuelve:
    - comparacion: una fila por método con precision, recall, F1 y precisión promedio
    - por_tipo: recall de cada método en cada tipo de anomalía
    - resultados: puntaje y marcas de cada transacción (sin la etiqueta real)
    """
    variables = construir_variables(flota, consumo)
    puntaje, anomalo_if = entrenar_isolation_forest(variables, seed=seed)

    alertas = ejecutar_reglas(flota, consumo)
    alertados_reglas = set(alertas.loc[alertas["regla"].isin(REGLAS_COMPORTAMIENTO), "id_registro"])
    alertados_if = set(anomalo_if[anomalo_if].index)

    reales = ids_con_anomalia_de_comportamiento(ground_truth)
    universo = list(variables.index)
    etiqueta = pd.Series([i in reales for i in universo], index=universo)

    metodos = {"Reglas (línea base)": alertados_reglas, "Isolation Forest": alertados_if}
    comparacion = pd.DataFrame([
        {"metodo": nombre, **evaluar_binario(ids, reales, universo)} for nombre, ids in metodos.items()
    ])
    comparacion["precision_promedio"] = [
        average_precision_score(etiqueta, etiqueta.index.isin(list(alertados_reglas)).astype(float)),
        average_precision_score(etiqueta, puntaje.loc[universo]),
    ]

    filas = []
    for tipo in TIPOS_COMPORTAMIENTO:
        ids_tipo = set(ground_truth.loc[ground_truth["tipo_anomalia"] == tipo, "id_registro"])
        for nombre, ids in metodos.items():
            filas.append({"tipo_anomalia": tipo, "metodo": nombre, "reales": len(ids_tipo),
                          "detectadas": len(ids_tipo & ids),
                          "recall": len(ids_tipo & ids) / len(ids_tipo) if ids_tipo else float("nan")})
    por_tipo = pd.DataFrame(filas)

    resultados = variables.assign(
        puntaje_if=puntaje, anomalo_if=anomalo_if,
        alerta_reglas=variables.index.isin(list(alertados_reglas)),
    ).reset_index()
    return comparacion, por_tipo, resultados
