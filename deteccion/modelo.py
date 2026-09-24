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
from deteccion.reglas import (
    cargas_por_dia,
    detectar_duplicados,
    distancia_a_zona_habitual,
    distancia_al_recorrido_gps,
    ejecutar_reglas,
    secuencia_odometro,
)

TIPOS_COMPORTAMIENTO = ["EXCESO_VOLUMETRICO", "ODOMETRO_REGRESIVO", "ODOMETRO_SALTO"]
REGLAS_COMPORTAMIENTO = ["litros_mayor_a_tanque", "odometro_disminuye", "salto_historial_vehiculo"]

# Hipótesis de comportamiento (las de calidad de datos y vinculación, CALIDAD y H1,
# no son problemas de detección de outliers)
HIPOTESIS_COMPORTAMIENTO = {"H2", "H3a", "H4", "H5", "H6", "H7"}

VARIABLES = {
    "ratio_litros_tanque": "litros cargados / capacidad del tanque",
    "km": "cambio de odómetro desde la carga anterior válida",
    "exceso_km": "km recorridos por encima del ritmo habitual del vehículo",
}

# Variables adicionales del escenario realista
VARIABLES_CONTEXTO = {
    "litros_vs_habitual": "litros / mediana de litros del vehículo",
    "retroceso_km": "km que retrocede el odómetro (0 si avanza)",
    "rendimiento_relativo": "km/L del día / km/L habitual del vehículo (GPS si hay, si no odómetro)",
    "cargas_en_el_dia": "cantidad de cargas del vehículo ese día",
    "tanques_en_el_dia": "litros del día / capacidad del tanque",
    "distancia_zona_km": "km entre la estación y la zona habitual del vehículo",
    "distancia_gps_km": "km entre la estación y el recorrido del GPS ese día (0 sin dato)",
    "sin_gps": "1 si no hay posición GPS para esa carga",
    "vehiculo_inactivo": "1 si la carga es posterior a la baja o salida de servicio",
}


def construir_variables(flota, consumo, estaciones=None, telemetria_diaria=None):
    """Una fila por transacción con las variables del modelo.

    Las transacciones sin carga anterior válida (primera del vehículo, odómetro
    vacío o duplicado) reciben 0 en las variables de odómetro: no hay cambio
    que evaluar. Si la flota trae fecha de estado (escenario realista) se agregan
    las variables de contexto; las de estaciones y GPS, si se pasan esas fuentes.
    """
    capacidad = consumo["vehiculo_id"].map(flota.set_index("Matricula")["CapacidadTanque"])
    duplicados = detectar_duplicados(consumo)["id_registro"]
    seq = secuencia_odometro(consumo, excluir_ids=duplicados).set_index("id")

    variables = pd.DataFrame({"id": consumo["id"]}).set_index("id")
    variables["ratio_litros_tanque"] = (consumo["litros"] / capacidad).values
    variables["km"] = seq["km"].reindex(variables.index).fillna(0)
    variables["exceso_km"] = (seq["km"] - seq["km_esperados"]).reindex(variables.index).fillna(0)
    if "FechaEstado" not in flota.columns:
        return variables

    habitual = consumo.groupby("vehiculo_id")["litros"].transform("median")
    variables["litros_vs_habitual"] = (consumo["litros"] / habitual).values
    variables["retroceso_km"] = (-variables["km"]).clip(lower=0)

    dias = cargas_por_dia(consumo, flota, excluir_ids=duplicados, gps_diario=telemetria_diaria)
    dias["rendimiento_relativo"] = dias["rendimiento_gps_relativo"].fillna(dias["rendimiento_odometro_relativo"])
    dias["tanques_en_el_dia"] = dias["litros"] / dias["capacidad"]
    por_id = (dias.explode("ids").drop_duplicates("ids").set_index("ids")
              [["rendimiento_relativo", "cargas", "tanques_en_el_dia"]])
    variables["rendimiento_relativo"] = por_id["rendimiento_relativo"].reindex(variables.index).fillna(1).clip(upper=5)
    variables["cargas_en_el_dia"] = por_id["cargas"].reindex(variables.index).fillna(1)
    variables["tanques_en_el_dia"] = por_id["tanques_en_el_dia"].reindex(variables.index).fillna(
        variables["ratio_litros_tanque"])

    if estaciones is not None:
        variables["distancia_zona_km"] = distancia_a_zona_habitual(consumo, estaciones).fillna(0).values
        if telemetria_diaria is not None:
            distancia = distancia_al_recorrido_gps(consumo, flota, estaciones, telemetria_diaria)
            variables["distancia_gps_km"] = distancia.fillna(0).values
            variables["sin_gps"] = distancia.isna().astype(int).values

    inactivos = flota[(flota["Estado"] != "EN SERVICIO") & flota["FechaEstado"].notna()]
    desde = consumo["vehiculo_id"].map(pd.to_datetime(inactivos.set_index("Matricula")["FechaEstado"]))
    variables["vehiculo_inactivo"] = (pd.to_datetime(consumo["fecha"]) >= desde).astype(int).values
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
    """Transacciones con alguna anomalía de comportamiento (no de calidad ni de vinculación)."""
    return set(ground_truth.loc[ground_truth["hipotesis"].isin(HIPOTESIS_COMPORTAMIENTO), "id_registro"])


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
