"""Data loading utilities for Streamlit app.

Todas las páginas leen la salida del pipeline maestro. Hay dos escenarios, cada uno
en su carpeta: didáctico (anomalías inconfundibles) y realista (uso simulado día por
día, anomalías sutiles y casos legítimos que se les parecen).

Para qué sirve este archivo
---------------------------
Es el único lugar de la aplicación web (hecha con Streamlit) que sabe dónde están los
datos y cómo leerlos. Las páginas de la app no abren archivos por su cuenta: llaman a las
funciones `load_...` de acá, que devuelven cada tabla como un DataFrame de pandas (una
tabla con filas y columnas en la memoria). Así, si cambia una carpeta o un nombre de
archivo, se corrige en un solo lugar.

Los datos los produce `generator_pipeline_maestro.py` (el generador de datos sintéticos)
y quedan en `datasets/`, una carpeta por escenario. Si faltan, `asegurar_datos_maestro`
los genera automáticamente.

Sobre la caché de Streamlit
---------------------------
Streamlit vuelve a ejecutar el código de la página entera cada vez que la persona toca
un botón o un filtro. Para no releer los CSV del disco en cada clic, las funciones de
lectura llevan `@st.cache_data`: la primera vez leen el archivo y guardan el resultado;
las siguientes veces, si se piden con los mismos argumentos (el mismo escenario),
devuelven directamente lo guardado.
"""
import pandas as pd
import json
import sys
from pathlib import Path
import streamlit as st

# Base paths
# (BASE_DIR es la carpeta raíz del repositorio: tres niveles arriba de este archivo)
BASE_DIR = Path(__file__).parent.parent.parent
DIRECTORIOS = {
    "didactico": BASE_DIR / "datasets" / "synthetics_maestro",
    "realista": BASE_DIR / "datasets" / "synthetics_realista",
}
# Nombre de cada escenario tal como se muestra en pantalla
NOMBRES_ESCENARIO = {"realista": "Realista", "didactico": "Didáctico"}
ESCENARIO_POR_DEFECTO = "realista"

# Archivos que debe tener cada escenario; si falta alguno, los datos son de una versión anterior
ARCHIVOS_REQUERIDOS = {
    "didactico": ["flota.csv", "consumo.csv", "ground_truth.csv", "diccionario.json"],
    "realista": ["flota.csv", "consumo.csv", "ground_truth.csv", "casos_legitimos.csv", "estaciones.csv",
                 "telemetria_diaria.csv", "facturacion_detalle.csv", "diccionario.json"],
}

# Parámetros del dataset que se genera automáticamente si no hay datos
N_FLOTA_POR_DEFECTO = 200


def selector_escenario():
    """Selector del escenario en la barra lateral; la elección se comparte entre páginas.

    Muestra en la barra lateral de la app una opción para elegir entre "Realista" y
    "Didáctico". No recibe nada y devuelve el escenario elegido ("realista" o "didactico"),
    que la página usa después para pedir los datos correspondientes.
    """
    opciones = list(NOMBRES_ESCENARIO)
    # st.session_state es la "memoria" de la sesión de la persona: sobrevive a las reejecuciones y
    # al cambio de página. Guardar ahí la elección hace que todas las páginas usen el mismo escenario.
    if "escenario" not in st.session_state:
        st.session_state["escenario"] = ESCENARIO_POR_DEFECTO
    # key="escenario" conecta el control con esa misma entrada de session_state
    st.sidebar.radio(
        "Escenario de datos", opciones, key="escenario",
        format_func=NOMBRES_ESCENARIO.get,
        help="Realista: uso simulado día por día, anomalías sutiles y casos legítimos que "
             "se parecen a anomalías. Didáctico: anomalías inconfundibles, para explicar el método.",
    )
    return st.session_state["escenario"]


def directorio(escenario):
    """Devuelve la carpeta (Path) donde están los datos del escenario indicado."""
    return DIRECTORIOS[escenario]


def asegurar_datos_maestro(escenario="didactico"):
    """Genera el dataset por defecto del escenario si todavía no existe.

    En un despliegue en la nube el disco se borra al reiniciar la aplicación; así
    cada página encuentra datos sin que haya que abrir primero el Generador. Con
    la misma semilla el resultado es siempre el mismo.

    También regenera si a los datos en disco les falta algún archivo del escenario:
    son de una versión anterior del generador.

    Devuelve True si generó datos en esta llamada.

    (La "semilla" es el número que inicializa el azar del generador: con la misma semilla,
    los datos "al azar" salen idénticos cada vez, lo que permite repetir los resultados.)
    """
    carpeta = DIRECTORIOS[escenario]
    if all((carpeta / archivo).exists() for archivo in ARCHIVOS_REQUERIDOS[escenario]):
        return False

    # El generador está en la raíz del repositorio; se agrega esa carpeta a las rutas donde Python
    # busca módulos para poder importarlo. El import va acá adentro para cargarlo solo si hace falta.
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from generator_pipeline_maestro import GeneradorMaestro, SEED

    with st.spinner(f"Generando el dataset {NOMBRES_ESCENARIO[escenario].lower()} por defecto (una sola vez)..."):
        resultado = GeneradorMaestro(
            n_flota=N_FLOTA_POR_DEFECTO, seed=SEED, output_dir=carpeta, escenario=escenario
        ).ejecutar()

    # Las páginas pudieron haber cacheado DataFrames vacíos antes de generar
    # (se vacía la caché de Streamlit para que las próximas lecturas vean los archivos nuevos)
    st.cache_data.clear()
    return resultado["exito"]


def get_dataset_stats(df, name):
    """Get basic stats for a dataset.

    Recibe una tabla (DataFrame) y el nombre con que se la muestra. Devuelve un diccionario
    con su cantidad de filas, de columnas, cuánta memoria ocupa (en MB) y cuántas celdas
    vacías tiene. Se usa para el cuadro resumen de `get_maestro_datasets_info`.
    """
    return {
        "name": name,
        "rows": len(df),
        "columns": len(df.columns),
        # deep=True mide también el texto guardado en cada celda; 1024**2 pasa de bytes a megabytes
        "size_mb": df.memory_usage(deep=True).sum() / 1024**2,
        "missing": df.isnull().sum().sum(),
    }


def filter_dataframe(df, filters):
    """Apply filters to a dataframe.

    Recibe una tabla y un diccionario {columna: lista de valores permitidos}. Devuelve una
    copia de la tabla con solo las filas cuyos valores están en esas listas. Los filtros con
    lista vacía o sobre columnas que no existen se ignoran. La tabla original no se modifica.
    """
    result = df.copy()

    for col, values in filters.items():
        if col in result.columns and values:
            result = result[result[col].isin(values)]

    return result


# ============================================================================
# Entidades, verdad de referencia y fuentes del escenario realista
# ============================================================================

def _leer_csv(nombre, escenario):
    """Lee `<nombre>.csv` de la carpeta del escenario.

    Recibe el nombre del archivo sin extensión y el escenario. Devuelve la tabla, o una tabla
    vacía si el archivo no existe (por ejemplo, tablas que solo tiene el escenario realista).
    Así las páginas pueden preguntar `df.empty` en lugar de fallar.
    """
    path = DIRECTORIOS[escenario] / f"{nombre}.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


# Cada función load_... lee una tabla del escenario. Todas usan la caché de Streamlit
# (@st.cache_data, explicada al principio del archivo) y devuelven un DataFrame, vacío si
# el archivo no existe en ese escenario.

@st.cache_data
def load_flota(escenario="didactico"):
    """Load FLOTA (vehículos).

    La tabla maestra de vehículos de la flota: una fila por vehículo.
    """
    return _leer_csv("flota", escenario)


@st.cache_data
def load_telemetria(escenario="didactico"):
    """Load TELEMETRIA (dispositivos GPS).

    Los dispositivos de seguimiento instalados en los vehículos.
    """
    return _leer_csv("telemetria", escenario)


@st.cache_data
def load_consumo_maestro(escenario="didactico"):
    """Load CONSUMO (transacciones).

    Las cargas de combustible: una fila por carga. Es la tabla principal que se audita.
    """
    return _leer_csv("consumo", escenario)


@st.cache_data
def load_solicitudes(escenario="didactico"):
    """Load SOLICITUDES (fuel requests).

    Los pedidos de combustible que deberían respaldar las cargas.
    """
    return _leer_csv("solicitudes", escenario)


@st.cache_data
def load_facturacion(escenario="didactico"):
    """Load FACTURACION (invoices).

    Las facturas del proveedor de combustible.
    """
    return _leer_csv("facturacion", escenario)


@st.cache_data
def load_ground_truth_maestro(escenario="didactico"):
    """Load the ground truth: one row per injected anomaly.

    Es la verdad de referencia para evaluar la detección; no debe usarse como
    entrada de las reglas ni de los modelos.

    ("Ground truth" es la lista de anomalías que el generador metió a propósito en los
    datos. Como se sabe exactamente cuáles son, sirve para medir cuántas encuentra la
    detección; usarla para detectar sería hacer trampa.)
    """
    return _leer_csv("ground_truth", escenario)


@st.cache_data
def load_casos_legitimos(escenario="realista"):
    """Casos que se parecen a una anomalía pero no lo son (solo escenario realista).

    Sirven para medir las falsas alarmas: una buena detección no debería marcarlos.
    """
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


def load_dataset_deteccion(escenario):
    """Las tablas que usan la detección y la evaluación, como dict (None si no existen).

    Recibe el escenario y devuelve un diccionario {nombre de tabla: DataFrame o None}. Las
    tablas opcionales que no existen (o están vacías) vienen como None, para que el código
    de detección pueda preguntar simplemente "¿está esta tabla?".
    """
    def o_none(df):
        """Devuelve None si la tabla está vacía; si no, la misma tabla."""
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
    }


@st.cache_data
def load_diccionario(escenario="didactico"):
    """Diccionario de datos y relaciones que escribió el generador para el escenario.

    Un "diccionario de datos" describe cada tabla y cada columna (qué significa, de qué
    tipo es) y cómo se relacionan las tablas. Devuelve su contenido como diccionario de
    Python, o uno vacío con la misma forma si el archivo no existe.
    """
    path = DIRECTORIOS[escenario] / "diccionario.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"tablas": {}, "relaciones": []}


@st.cache_data
def load_maestro_metadata(escenario="didactico"):
    """Load metadata of the scenario.

    Datos sobre la generación en sí (semilla, cantidad de vehículos, fecha en que se
    generó...). Devuelve un diccionario, vacío si el archivo no existe.
    """
    path = DIRECTORIOS[escenario] / "metadata.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_maestro_datasets_info(escenario="didactico"):
    """Get info about all datasets of the scenario.

    Recibe el escenario y devuelve una tabla resumen con una fila por cada tabla disponible
    (filas, columnas, tamaño y vacíos; ver `get_dataset_stats`). Las tablas que no existen
    en el escenario se omiten.
    """
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
