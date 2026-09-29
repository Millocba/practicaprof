"""Carga de un dataset generado por el pipeline maestro.

Para qué sirve este archivo
---------------------------
Es la "puerta de entrada" de los datos. El generador (`generator_pipeline_maestro.py`)
escribe una carpeta con varios archivos CSV (tablas de texto separadas por comas).
Este módulo los lee todos de una vez y los devuelve como DataFrames de pandas
(tablas en memoria, parecidas a una hoja de cálculo) para que el resto del paquete
(`reglas.py`, `modelo.py`, `priorizacion.py`, `__main__.py`) trabaje con ellos.
"""
from pathlib import Path

import pandas as pd

# Nombres (sin la extensión .csv) de todas las tablas que puede tener un dataset:
# - flota: los vehículos (matrícula, dominio/patente, capacidad del tanque, estado).
# - consumo: cada carga de combustible (vehículo, fecha, estación, litros, odómetro).
# - ground_truth: las anomalías que el generador inyectó a propósito (la "respuesta
#   correcta", que solo se usa para evaluar).
# - casos_legitimos: casos normales que a propósito se parecen a anomalías.
# - estaciones: estaciones de servicio con sus coordenadas.
# - telemetria / telemetria_diaria: datos del GPS de los vehículos.
# - solicitudes: pedidos de autorización para cargar combustible.
# - facturacion / facturacion_detalle: facturas de los proveedores y sus líneas.
ARCHIVOS = ["flota", "consumo", "ground_truth", "casos_legitimos", "estaciones", "telemetria", "telemetria_diaria",
            "solicitudes", "facturacion", "facturacion_detalle"]


def cargar_dataset(directorio):
    """Devuelve un dict con los DataFrames presentes en `directorio` (None si falta el archivo).

    `casos_legitimos`, `estaciones` y `telemetria_diaria` solo existen en el escenario realista.

    Recibe: la ruta de la carpeta donde el generador dejó los CSV.
    Devuelve: un diccionario (una colección de pares nombre -> valor) donde cada
    clave es un nombre de ARCHIVOS y cada valor es la tabla leída, o None si ese
    archivo no está en la carpeta. Así el resto del código puede preguntar
    "¿tengo GPS?" simplemente viendo si el valor es None.
    """
    directorio = Path(directorio)
    return {nombre: pd.read_csv(directorio / f"{nombre}.csv") if (directorio / f"{nombre}.csv").exists() else None
            for nombre in ARCHIVOS}
