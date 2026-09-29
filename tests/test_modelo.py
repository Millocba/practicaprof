"""Tests del modelo Isolation Forest y su comparación con las reglas.

Qué prueba: `deteccion/modelo.py`, que usa Isolation Forest, un método de
aprendizaje automático que busca registros "raros" sin conocer las etiquetas,
y lo compara con las reglas de negocio.

Por qué importa: el proyecto afirma que el modelo encuentra anomalías mejor que
elegir al azar, pero que las reglas siguen siendo la referencia para los tipos
de anomalía que tienen una definición exacta. Estos tests sostienen esas dos
afirmaciones y verifican que el modelo no use las etiquetas como pista.

Para una explicación general de qué es un test, pytest y un fixture, ver el
docstring de `test_deteccion.py`.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion.modelo import (
    VARIABLES,
    comparar_con_reglas,
    construir_variables,
    entrenar_isolation_forest,
    ids_con_anomalia_de_comportamiento,
)
from generator_pipeline_maestro import GeneradorMaestro


# Genera una sola vez (scope="module") un dataset de 200 vehículos en una
# carpeta temporal y devuelve las tablas flota, consumo y ground truth.
@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    d = tmp_path_factory.mktemp("maestro")
    assert GeneradorMaestro(n_flota=200, seed=42, output_dir=d).ejecutar()["exito"]
    return tuple(pd.read_csv(d / f) for f in ["flota.csv", "consumo.csv", "ground_truth.csv"])


def test_variables_completas_y_sin_etiquetas(datos):
    """Las variables del modelo son las previstas, una fila por carga y sin valores vacíos.

    Si falla, el modelo recibiría columnas de más (por ejemplo, la etiqueta),
    filas perdidas o vacíos que no sabe manejar.
    """
    flota, consumo, _ = datos
    variables = construir_variables(flota, consumo)
    assert list(variables.columns) == list(VARIABLES)
    assert len(variables) == len(consumo)
    assert not variables.isna().any().any()


def test_modelo_reproducible_con_la_misma_semilla(datos):
    """Entrenar dos veces con la misma semilla da exactamente los mismos puntajes.

    Si falla, los resultados del modelo no se pueden reproducir.
    """
    flota, consumo, _ = datos
    variables = construir_variables(flota, consumo)
    a, _ = entrenar_isolation_forest(variables, seed=42)
    b, _ = entrenar_isolation_forest(variables, seed=42)
    pd.testing.assert_series_equal(a, b)


def test_modelo_ordena_mejor_que_el_azar(datos):
    """La precisión promedio del modelo es más del doble de la que se obtendría eligiendo al azar.

    Si falla, el modelo dejó de aportar información útil para encontrar anomalías.
    """
    flota, consumo, ground_truth = datos
    comparacion, _, _ = comparar_con_reglas(flota, consumo, ground_truth)
    tasa_base = len(ids_con_anomalia_de_comportamiento(ground_truth)) / len(consumo)
    modelo = comparacion.set_index("metodo").loc["Isolation Forest"]
    assert modelo.precision_promedio > 2 * tasa_base


def test_reglas_son_el_techo_de_referencia(datos):
    """Las reglas logran F1 perfecto, el modelo no las supera y se comparan los tres tipos de comportamiento.

    Si falla, cambiaron las reglas, el modelo o los tipos de anomalía que se comparan.
    """
    comparacion, por_tipo, _ = comparar_con_reglas(*datos)
    metodos = comparacion.set_index("metodo")
    assert metodos.loc["Reglas (línea base)", "f1"] == 1.0
    assert metodos.loc["Reglas (línea base)", "f1"] >= metodos.loc["Isolation Forest", "f1"]
    assert set(por_tipo["tipo_anomalia"]) == {"EXCESO_VOLUMETRICO", "ODOMETRO_REGRESIVO", "ODOMETRO_SALTO"}
