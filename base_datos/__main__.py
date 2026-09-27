"""Base de datos del escenario realista, desde la línea de comandos.

Uso:
    python -m base_datos cargar [--base datasets/auditoria_realista.db] [--datos datasets/synthetics_realista]
                                [--hasta AAAA-MM-DD]
        Crea la base si no existe, aplica las migraciones pendientes y carga el dataset (repetible:
        no duplica filas). Con --hasta carga los datos operativos solo hasta esa fecha.
    python -m base_datos verificar [--base ...]
        Integridad referencial y filas por tabla.

La base es un archivo local que no se versiona (datasets/ está fuera de Git).
"""
import argparse
import json
from pathlib import Path

from base_datos.carga import TABLAS, cargar
from base_datos.esquema import conectar, migrar, verificar

RAIZ = Path(__file__).parent.parent
BASE = RAIZ / "datasets" / "auditoria_realista.db"
DATOS = RAIZ / "datasets" / "synthetics_realista"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("cargar", help="crear o actualizar la base y cargar un dataset")
    c.add_argument("--base", default=str(BASE))
    c.add_argument("--datos", default=str(DATOS))
    c.add_argument("--hasta")
    v = sub.add_parser("verificar", help="integridad referencial y filas por tabla")
    v.add_argument("--base", default=str(BASE))
    args = parser.parse_args()

    Path(args.base).parent.mkdir(parents=True, exist_ok=True)
    conexion = conectar(args.base)
    nuevas = migrar(conexion)
    if nuevas:
        print("Migraciones aplicadas:", ", ".join(nuevas))
    if args.comando == "cargar":
        metadata = Path(args.datos) / "metadata.json"
        semilla = json.loads(metadata.read_text(encoding="utf-8")).get("seed") if metadata.exists() else None
        filas = cargar(conexion, args.datos, hasta=args.hasta, semilla=semilla)
        print(json.dumps(filas, indent=1))
    problemas = verificar(conexion)
    print("Integridad: " + ("sin problemas" if not problemas else f"{len(problemas)} problemas"))
    for problema in problemas[:20]:
        print("  ", problema)
    if args.comando == "verificar":
        for tabla in TABLAS:
            print(f"  {tabla}: {conexion.execute(f'SELECT COUNT(*) FROM {tabla}').fetchone()[0]}")
    conexion.close()
    raise SystemExit(1 if problemas else 0)


if __name__ == "__main__":
    main()
