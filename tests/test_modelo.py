"""Tests del modelo Isolation Forest y su comparación con las reglas."""
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


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    d = tmp_path_factory.mktemp("maestro")
    assert GeneradorMaestro(n_flota=200, seed=42, output_dir=d).ejecutar()["exito"]
    return tuple(pd.read_csv(d / f) for f in ["flota.csv", "consumo.csv", "ground_truth.csv"])


def test_variables_completas_y_sin_etiquetas(datos):
    flota, consumo, _ = datos
    variables = construir_variables(flota, consumo)
    assert list(variables.columns) == list(VARIABLES)
    assert len(variables) == len(consumo)
    assert not variables.isna().any().any()


def test_modelo_reproducible_con_la_misma_semilla(datos):
    flota, consumo, _ = datos
    variables = construir_variables(flota, consumo)
    a, _ = entrenar_isolation_forest(variables, seed=42)
    b, _ = entrenar_isolation_forest(variables, seed=42)
    pd.testing.assert_series_equal(a, b)


def test_modelo_ordena_mejor_que_el_azar(datos):
    flota, consumo, ground_truth = datos
    comparacion, _, _ = comparar_con_reglas(flota, consumo, ground_truth)
    tasa_base = len(ids_con_anomalia_de_comportamiento(ground_truth)) / len(consumo)
    modelo = comparacion.set_index("metodo").loc["Isolation Forest"]
    assert modelo.precision_promedio > 2 * tasa_base


def test_reglas_son_el_techo_de_referencia(datos):
    comparacion, por_tipo, _ = comparar_con_reglas(*datos)
    metodos = comparacion.set_index("metodo")
    assert metodos.loc["Reglas (línea base)", "f1"] == 1.0
    assert metodos.loc["Reglas (línea base)", "f1"] >= metodos.loc["Isolation Forest", "f1"]
    assert set(por_tipo["tipo_anomalia"]) == {"EXCESO_VOLUMETRICO", "ODOMETRO_REGRESIVO", "ODOMETRO_SALTO"}


def test_la_carga_sin_id_o_con_id_repetido_no_entra_al_modelo():
    # El reporte real trae cargas sin remito (sin id) y remitos repetidos: una carga sin id
    # no se puede evaluar por transacción, así que no entra al modelo en lugar de romper la corrida.
    flota = pd.DataFrame({"Matricula": ["AAA"], "CapacidadTanque": [100.0]})
    consumo = pd.DataFrame({
        "id": ["R1", "R1", None, "R2"],
        "vehiculo_id": ["AAA"] * 4,
        "dominio": ["AAA"] * 4,
        "fecha": ["2026-01-01"] * 4,
        "hora": ["08:00:00", "09:00:00", "10:00:00", "11:00:00"],
        "estacion": ["1"] * 4,
        "producto": ["DIESEL"] * 4,
        "litros": [10.0] * 4,
        "precio_unitario": [1.0] * 4,
        "importe_total": [10.0] * 4,
        "numero_tarjeta": ["T1"] * 4,
        "conductor": [None] * 4,
        "odometro": pd.array([100, 200, 300, 400], dtype="Int64"),
        "tipo_identificacion": ["PATENTE"] * 4,
        "origen_transaccion": ["POSNET"] * 4,
        "contrato": pd.array([1] * 4, dtype="Int64"),
    })
    variables = construir_variables(flota, consumo)
    assert list(variables.index) == ["R1", "R2"]
