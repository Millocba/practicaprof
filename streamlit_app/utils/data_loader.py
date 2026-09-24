"""Data loading utilities for Streamlit app.

Todas las páginas leen la salida del pipeline maestro (datasets/synthetics_maestro).
"""
import pandas as pd
import json
import sys
from pathlib import Path
import streamlit as st

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
SYNTHETICS_DIR = BASE_DIR / "datasets" / "synthetics_maestro"

# Parámetros del dataset que se genera automáticamente si no hay datos
N_FLOTA_POR_DEFECTO = 200


def asegurar_datos_maestro():
    """Genera el dataset por defecto si todavía no existe.

    En un despliegue en la nube el disco se borra al reiniciar la aplicación; así
    cada página encuentra datos sin que haya que abrir primero el Generador. Con
    la misma semilla el resultado es siempre el mismo.

    También regenera si los datos en disco son de una versión anterior del
    generador, que no producía `ground_truth.csv`.

    Devuelve True si generó datos en esta llamada.
    """
    if (SYNTHETICS_DIR / "flota.csv").exists() and (SYNTHETICS_DIR / "ground_truth.csv").exists():
        return False

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from generator_pipeline_maestro import GeneradorMaestro, SEED

    with st.spinner("Generando el dataset sintético por defecto (una sola vez)..."):
        resultado = GeneradorMaestro(
            n_flota=N_FLOTA_POR_DEFECTO, seed=SEED, output_dir=SYNTHETICS_DIR
        ).ejecutar()

    # Las páginas pudieron haber cacheado DataFrames vacíos antes de generar
    st.cache_data.clear()
    return resultado["exito"]


def get_dataset_stats(df, name):
    """Get basic stats for a dataset."""
    return {
        "name": name,
        "rows": len(df),
        "columns": len(df.columns),
        "size_mb": df.memory_usage(deep=True).sum() / 1024**2,
        "missing": df.isnull().sum().sum(),
    }


def filter_dataframe(df, filters):
    """Apply filters to a dataframe."""
    result = df.copy()

    for col, values in filters.items():
        if col in result.columns and values:
            result = result[result[col].isin(values)]

    return result


# ============================================================================
# SYNTHETICS MAESTRO - 5 entidades + verdad de referencia
# ============================================================================

def _leer_csv(nombre):
    path = SYNTHETICS_DIR / f"{nombre}.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


@st.cache_data
def load_flota():
    """Load FLOTA (vehículos) from synthetics maestro."""
    return _leer_csv("flota")


@st.cache_data
def load_telemetria():
    """Load TELEMETRIA (dispositivos GPS) from synthetics maestro."""
    return _leer_csv("telemetria")


@st.cache_data
def load_consumo_maestro():
    """Load CONSUMO (transacciones) from synthetics maestro."""
    return _leer_csv("consumo")


@st.cache_data
def load_solicitudes():
    """Load SOLICITUDES (fuel requests) from synthetics maestro."""
    return _leer_csv("solicitudes")


@st.cache_data
def load_facturacion():
    """Load FACTURACION (invoices) from synthetics maestro."""
    return _leer_csv("facturacion")


@st.cache_data
def load_ground_truth_maestro():
    """Load the ground truth: one row per injected anomaly.

    Es la verdad de referencia para evaluar la detección; no debe usarse como
    entrada de las reglas ni de los modelos.
    """
    return _leer_csv("ground_truth")


@st.cache_data
def load_maestro_metadata():
    """Load metadata from synthetics maestro."""
    path = SYNTHETICS_DIR / "metadata.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_maestro_datasets_info():
    """Get info about all synthetics maestro datasets."""
    datasets = {
        "Flota": load_flota(),
        "Telemetría": load_telemetria(),
        "Consumo": load_consumo_maestro(),
        "Solicitudes": load_solicitudes(),
        "Facturación": load_facturacion(),
    }

    stats = []
    for name, df in datasets.items():
        if not df.empty:
            stats.append(get_dataset_stats(df, name))

    return pd.DataFrame(stats) if stats else pd.DataFrame()
