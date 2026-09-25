"""Carga de un dataset generado por el pipeline maestro."""
from pathlib import Path

import pandas as pd

ARCHIVOS = ["flota", "consumo", "ground_truth", "casos_legitimos", "estaciones", "telemetria", "telemetria_diaria",
            "solicitudes", "facturacion", "facturacion_detalle"]


def cargar_dataset(directorio):
    """Devuelve un dict con los DataFrames presentes en `directorio` (None si falta el archivo).

    `casos_legitimos`, `estaciones` y `telemetria_diaria` solo existen en el escenario realista.
    """
    directorio = Path(directorio)
    return {nombre: pd.read_csv(directorio / f"{nombre}.csv") if (directorio / f"{nombre}.csv").exists() else None
            for nombre in ARCHIVOS}
