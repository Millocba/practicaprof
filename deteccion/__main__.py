"""Evalúa la detección sobre un dataset del pipeline maestro.

Uso:
    python -m deteccion                              # datasets/synthetics_maestro
    python -m deteccion --datos otra/carpeta
    python -m deteccion --salida results/deteccion   # guarda métricas y alertas
"""
import argparse
from pathlib import Path

import pandas as pd

from deteccion.evaluacion import evaluar_por_regla, evaluar_por_tipo
from deteccion.reglas import ejecutar_reglas

RAIZ = Path(__file__).parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", type=Path, default=RAIZ / "datasets" / "synthetics_maestro")
    parser.add_argument("--salida", type=Path, help="carpeta donde guardar métricas y alertas")
    args = parser.parse_args()

    faltantes = [f for f in ["flota.csv", "consumo.csv", "ground_truth.csv"] if not (args.datos / f).exists()]
    if faltantes:
        parser.error(f"faltan {', '.join(faltantes)} en {args.datos}; "
                     "generá los datos con `python generator_pipeline_maestro.py`")

    flota = pd.read_csv(args.datos / "flota.csv")
    consumo = pd.read_csv(args.datos / "consumo.csv")
    ground_truth = pd.read_csv(args.datos / "ground_truth.csv")

    alertas = ejecutar_reglas(flota, consumo)
    por_tipo = evaluar_por_tipo(alertas, ground_truth)
    por_regla = evaluar_por_regla(alertas, ground_truth)

    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", "{:.3f}".format)
    print(f"Datos: {args.datos}  ({len(consumo)} transacciones, {len(ground_truth)} anomalías)\n")
    print("Por tipo de anomalía (todas las reglas del tipo juntas):")
    print(por_tipo.to_string(index=False))
    print("\nPor regla:")
    print(por_regla.to_string(index=False))

    if args.salida:
        args.salida.mkdir(parents=True, exist_ok=True)
        por_tipo.to_csv(args.salida / "metricas_por_tipo.csv", index=False)
        por_regla.to_csv(args.salida / "metricas_por_regla.csv", index=False)
        alertas.to_csv(args.salida / "alertas.csv", index=False)
        print(f"\nResultados guardados en {args.salida}")


if __name__ == "__main__":
    main()
