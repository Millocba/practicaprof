"""Data loading utilities for Streamlit app.

Todas las páginas leen la salida del pipeline maestro. Hay dos escenarios, cada uno
en su carpeta: didáctico (anomalías inconfundibles) y realista (uso simulado día por
día, anomalías sutiles y casos legítimos que se les parecen).
"""
import pandas as pd
import json
import sys
from pathlib import Path
import streamlit as st

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DIRECTORIOS = {
    "didactico": BASE_DIR / "datasets" / "synthetics_maestro",
    "realista": BASE_DIR / "datasets" / "synthetics_realista",
}
NOMBRES_ESCENARIO = {"realista": "Realista", "didactico": "Didáctico"}
ESCENARIO_POR_DEFECTO = "realista"

# Archivos que debe tener cada escenario; si falta alguno, los datos son de una versión anterior
ARCHIVOS_REQUERIDOS = {
    "didactico": ["flota.csv", "consumo.csv", "ground_truth.csv", "diccionario.json"],
    "realista": ["flota.csv", "consumo.csv", "ground_truth.csv", "casos_legitimos.csv", "estaciones.csv",
                 "telemetria_diaria.csv", "facturacion_detalle.csv", "contratos.csv", "transferencias.csv",
                 "diccionario.json"],
}

# Parámetros del dataset que se genera automáticamente si no hay datos
N_FLOTA_POR_DEFECTO = 200


def selector_escenario():
    """Selector del escenario en la barra lateral; la elección se comparte entre páginas."""
    opciones = list(NOMBRES_ESCENARIO)
    if "escenario" not in st.session_state:
        st.session_state["escenario"] = ESCENARIO_POR_DEFECTO
    st.sidebar.radio(
        "Escenario de datos", opciones, key="escenario",
        format_func=NOMBRES_ESCENARIO.get,
        help="Realista: uso simulado día por día, anomalías sutiles y casos legítimos que "
             "se parecen a anomalías. Didáctico: anomalías inconfundibles, para explicar el método.",
    )
    return st.session_state["escenario"]


def directorio(escenario):
    return DIRECTORIOS[escenario]


def asegurar_datos_maestro(escenario="didactico"):
    """Genera el dataset por defecto del escenario si todavía no existe.

    En un despliegue en la nube el disco se borra al reiniciar la aplicación; así
    cada página encuentra datos sin que haya que abrir primero el Generador. Con
    la misma semilla el resultado es siempre el mismo.

    También regenera si a los datos en disco les falta algún archivo del escenario:
    son de una versión anterior del generador.

    Devuelve True si generó datos en esta llamada.
    """
    carpeta = DIRECTORIOS[escenario]
    if all((carpeta / archivo).exists() for archivo in ARCHIVOS_REQUERIDOS[escenario]):
        return False

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from generator_pipeline_maestro import GeneradorMaestro, SEED

    with st.spinner(f"Generando el dataset {NOMBRES_ESCENARIO[escenario].lower()} por defecto (una sola vez)..."):
        resultado = GeneradorMaestro(
            n_flota=N_FLOTA_POR_DEFECTO, seed=SEED, output_dir=carpeta, escenario=escenario
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
# Entidades, verdad de referencia y fuentes del escenario realista
# ============================================================================

def _leer_csv(nombre, escenario):
    path = DIRECTORIOS[escenario] / f"{nombre}.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


@st.cache_data
def load_flota(escenario="didactico"):
    """Load FLOTA (vehículos)."""
    return _leer_csv("flota", escenario)


@st.cache_data
def load_telemetria(escenario="didactico"):
    """Load TELEMETRIA (dispositivos GPS)."""
    return _leer_csv("telemetria", escenario)


@st.cache_data
def load_consumo_maestro(escenario="didactico"):
    """Load CONSUMO (transacciones)."""
    return _leer_csv("consumo", escenario)


@st.cache_data
def load_solicitudes(escenario="didactico"):
    """Load SOLICITUDES (fuel requests)."""
    return _leer_csv("solicitudes", escenario)


@st.cache_data
def load_facturacion(escenario="didactico"):
    """Load FACTURACION (invoices)."""
    return _leer_csv("facturacion", escenario)


@st.cache_data
def load_ground_truth_maestro(escenario="didactico"):
    """Load the ground truth: one row per injected anomaly.

    Es la verdad de referencia para evaluar la detección; no debe usarse como
    entrada de las reglas ni de los modelos.
    """
    return _leer_csv("ground_truth", escenario)


@st.cache_data
def load_casos_legitimos(escenario="realista"):
    """Casos que se parecen a una anomalía pero no lo son (solo escenario realista)."""
    return _leer_csv("casos_legitimos", escenario)


@st.cache_data
def load_estaciones(escenario="realista"):
    """Estaciones con coordenadas (solo escenario realista)."""
    return _leer_csv("estaciones", escenario)


@st.cache_data
def load_facturacion_detalle(escenario="realista"):
    """Líneas de cada factura, con la carga que referencian (solo escenario realista)."""
    return _leer_csv("facturacion_detalle", escenario)


@st.cache_data
def load_telemetria_diaria(escenario="realista"):
    """Recorrido diario de cada dispositivo GPS (solo escenario realista)."""
    return _leer_csv("telemetria_diaria", escenario)


@st.cache_data
def load_contratos(escenario="realista"):
    """Contratos con su tope mensual (solo escenario realista)."""
    return _leer_csv("contratos", escenario)


@st.cache_data
def load_transferencias(escenario="realista"):
    """Transferencias de saldo entre contratos (solo escenario realista)."""
    return _leer_csv("transferencias", escenario)


def load_dataset_deteccion(escenario):
    """Las tablas que usan la detección y la evaluación, como dict (None si no existen)."""
    def o_none(df):
        return None if df.empty else df
    realista = escenario == "realista"
    return {
        "flota": load_flota(escenario),
        "consumo": load_consumo_maestro(escenario),
        "ground_truth": load_ground_truth_maestro(escenario),
        "casos_legitimos": o_none(load_casos_legitimos(escenario)),
        "estaciones": o_none(load_estaciones(escenario)),
        "telemetria_diaria": o_none(load_telemetria_diaria(escenario)),
        # Solo en el escenario realista las solicitudes y la facturación son coherentes con el consumo
        "solicitudes": o_none(load_solicitudes(escenario)) if realista else None,
        "facturacion": o_none(load_facturacion(escenario)) if realista else None,
        "facturacion_detalle": o_none(load_facturacion_detalle(escenario)),
        "contratos": o_none(load_contratos(escenario)) if realista else None,
        "transferencias": o_none(load_transferencias(escenario)) if realista else None,
    }


@st.cache_data
def load_diccionario(escenario="didactico"):
    """Diccionario de datos y relaciones que escribió el generador para el escenario."""
    path = DIRECTORIOS[escenario] / "diccionario.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"tablas": {}, "relaciones": []}


@st.cache_data
def load_maestro_metadata(escenario="didactico"):
    """Load metadata of the scenario."""
    path = DIRECTORIOS[escenario] / "metadata.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_maestro_datasets_info(escenario="didactico"):
    """Get info about all datasets of the scenario."""
    datasets = {
        "Flota": load_flota(escenario),
        "Telemetría": load_telemetria(escenario),
        "Consumo": load_consumo_maestro(escenario),
        "Solicitudes": load_solicitudes(escenario),
        "Facturación": load_facturacion(escenario),
        "Estaciones": load_estaciones(escenario),
        "Detalle de facturación": load_facturacion_detalle(escenario),
        "Telemetría diaria": load_telemetria_diaria(escenario),
    }

    stats = []
    for name, df in datasets.items():
        if not df.empty:
            stats.append(get_dataset_stats(df, name))

    return pd.DataFrame(stats) if stats else pd.DataFrame()
