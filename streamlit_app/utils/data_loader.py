"""Data loading utilities for Streamlit app."""
import pandas as pd
import json
from pathlib import Path
import streamlit as st

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DATASETS_DIR = BASE_DIR / "datasets" / "defects_aware_v5"
RESULTS_DIR = BASE_DIR / "results"
CONSUMO_DIR = BASE_DIR / "data" / "consumo"


@st.cache_data
def load_vehiculo():
    """Load vehicle data."""
    path = DATASETS_DIR / "vehiculo.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str)
    return pd.DataFrame()


@st.cache_data
def load_dispositivo():
    """Load device data."""
    path = DATASETS_DIR / "dispositivo.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str)
    return pd.DataFrame()


@st.cache_data
def load_reporte_consumo_vinculado():
    """Load linked consumption report."""
    path = DATASETS_DIR / "reporte_consumo_v5_vinculado.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str)
    return pd.DataFrame()


@st.cache_data
def load_ground_truth():
    """Load ground truth defects."""
    path = DATASETS_DIR / "ground_truth.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str)
    return pd.DataFrame()


@st.cache_data
def load_solicitud_combustible():
    """Load fuel requests."""
    path = DATASETS_DIR / "solicitud_combustible.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str)
    return pd.DataFrame()


@st.cache_data
def load_reporte_enriquecido():
    """Load enriched consumption report."""
    path = RESULTS_DIR / "integracion_cruces" / "reporte_consumo_v5_vinculado_enriquecido.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str)
    return pd.DataFrame()


@st.cache_data
def load_integracion_resumen():
    """Load integration summary."""
    path = RESULTS_DIR / "integracion_cruces" / "INTEGRACION_CONSUMO_RESUMEN.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def get_dataset_stats(df, name):
    """Get basic stats for a dataset."""
    return {
        "name": name,
        "rows": len(df),
        "columns": len(df.columns),
        "size_mb": df.memory_usage(deep=True).sum() / 1024**2,
        "missing": df.isnull().sum().sum(),
    }


def get_all_datasets_info():
    """Get info about all available datasets."""
    datasets = {
        "Vehículos": load_vehiculo(),
        "Dispositivos": load_dispositivo(),
        "Consumo Vinculado": load_reporte_consumo_vinculado(),
        "Solicitud Combustible": load_solicitud_combustible(),
        "Ground Truth": load_ground_truth(),
        "Consumo Enriquecido": load_reporte_enriquecido(),
    }

    stats = []
    for name, df in datasets.items():
        if not df.empty:
            stats.append(get_dataset_stats(df, name))

    return pd.DataFrame(stats)


def filter_dataframe(df, filters):
    """Apply filters to a dataframe."""
    result = df.copy()

    for col, values in filters.items():
        if col in result.columns and values:
            result = result[result[col].isin(values)]

    return result
