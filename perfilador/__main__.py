"""Perfilador de fuentes, desde la línea de comandos.

Uso:
    python -m perfilador perfilar archivo1.xlsx carpeta/ --origen "fuentes reales" [--salida perfil.json]
        Acepta archivos y carpetas (se recorren completas). Los archivos con las mismas columnas
        se agrupan en una tabla, como lotes o versiones. --renombrar PATRON=NOMBRE reemplaza un
        nombre de tabla; --reemplazar TEXTO=NUEVO, un texto en todo el perfil. --base-url-env VARIABLE
        suma las tablas de una base de datos (en solo lectura, con prefijo base.). Escribe
        perfiles/pendientes/perfil_AAAA-MM-DD.json o --salida. Solo imprime conteos.
    python -m perfilador aprobar perfiles/pendientes/perfil_X.json --responsable "Nombre" [--notas "..."]
        Registra la revisión manual y lo pasa a perfiles/aprobados/ (se versiona).
    python -m perfilador comparar perfiles/aprobados/perfil_X.json [--escenario realista]
        Compara con los datos sintéticos y escribe el informe de brechas junto al perfil.

Los archivos de origen se leen en memoria y nunca se copian ni se escriben.
"""
import argparse
import json
import os
from datetime import date
from pathlib import Path

from perfilador.comparar import comparar, informe_markdown, perfil_de_directorio, sugerir_emparejamiento
from perfilador.perfil import perfilar, reemplazar_textos, tablas_de_base, tablas_de_rutas

RAIZ = Path(__file__).parent.parent
PENDIENTES = RAIZ / "perfiles" / "pendientes"
APROBADOS = RAIZ / "perfiles" / "aprobados"
DATOS = {"didactico": RAIZ / "datasets" / "synthetics_maestro", "realista": RAIZ / "datasets" / "synthetics_realista"}


def guardar(perfil, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(perfil, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_perfilar(args):
    renombrar = dict(r.split("=", 1) for r in args.renombrar)
    tablas, lectura = tablas_de_rutas(args.archivos, renombrar)
    if args.base_url_env:
        url = os.environ.get(args.base_url_env)
        if not url:
            raise SystemExit(f"La variable de entorno {args.base_url_env} no está definida.")
        try:
            de_base, lectura_base = tablas_de_base(url)
        except Exception as error:  # noqa: BLE001 - el mensaje podría incluir datos de conexión
            raise SystemExit(f"No se pudo leer la base ({type(error).__name__}).") from None
        tablas.update(de_base)
        lectura.update(lectura_base)
    if not tablas:
        raise SystemExit("No se encontraron archivos CSV o Excel legibles ni tablas en la base.")
    perfil = perfilar(tablas, origen=args.origen)
    perfil["lectura"] = lectura
    if args.reemplazar:
        perfil = reemplazar_textos(perfil, dict(r.split("=", 1) for r in args.reemplazar))
    destino = Path(args.salida) if args.salida else PENDIENTES / f"perfil_{date.today().isoformat()}.json"
    guardar(perfil, destino)
    print(f"Perfil de {len(perfil['tablas'])} tablas ({sum(lectura['archivos_por_tabla'].values())} archivos) "
          f"y {len(perfil['relaciones'])} relaciones en {destino}")
    if lectura["no_leidos_por_error"]:
        print("Archivos no leídos, por tipo de error:", lectura["no_leidos_por_error"])
    print("Revisalo antes de aprobarlo: python -m perfilador aprobar", destino, '--responsable "Nombre"')


def cmd_aprobar(args):
    origen = Path(args.perfil)
    perfil = json.loads(origen.read_text(encoding="utf-8"))
    perfil["revision"] = {"revisado": True, "responsable": args.responsable, "fecha": date.today().isoformat(),
                          "notas": args.notas}
    destino = APROBADOS / origen.name
    guardar(perfil, destino)
    if origen.resolve() != destino.resolve():
        origen.unlink()
    print(f"Perfil aprobado por {args.responsable}: {destino}")


def cmd_comparar(args):
    perfil_real = json.loads(Path(args.perfil).read_text(encoding="utf-8"))
    carpeta = DATOS[args.escenario]
    if not (carpeta / "flota.csv").exists():
        raise SystemExit(f"No hay datos sintéticos en {carpeta}: generalos con "
                         f"`python generator_pipeline_maestro.py --escenario {args.escenario}`")
    perfil_sintetico = perfil_de_directorio(carpeta, origen=f"sintético ({args.escenario})")
    brechas = comparar(perfil_real, perfil_sintetico, sugerir_emparejamiento(perfil_real, perfil_sintetico))
    destino = Path(args.perfil).with_name(Path(args.perfil).stem + "_brechas.md")
    destino.write_text(informe_markdown(brechas, perfil_real, perfil_sintetico), encoding="utf-8")
    print(brechas["severidad"].value_counts().to_string())
    print(f"Informe de brechas en {destino}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("perfilar", help="perfilar archivos CSV o Excel")
    p.add_argument("archivos", nargs="*", help="archivos o carpetas (CSV y Excel)")
    p.add_argument("--base-url-env", metavar="VARIABLE",
                   help="variable de entorno con la cadena de conexión de una base de datos para sumar sus "
                        "tablas (prefijo base.), en solo lectura; la cadena no se muestra ni se guarda")
    p.add_argument("--origen", default="fuentes reales")
    p.add_argument("--salida")
    p.add_argument("--renombrar", action="append", default=[], metavar="PATRON=NOMBRE",
                   help="reemplaza el nombre de una tabla (por ejemplo, si incluye el de una organización)")
    p.add_argument("--reemplazar", action="append", default=[], metavar="TEXTO=NUEVO",
                   help="reemplaza un texto en todo el perfil, sin distinguir mayúsculas (organizaciones, proveedores)")
    p.set_defaults(funcion=cmd_perfilar)
    a = sub.add_parser("aprobar", help="registrar la revisión manual de un perfil")
    a.add_argument("perfil")
    a.add_argument("--responsable", required=True)
    a.add_argument("--notas")
    a.set_defaults(funcion=cmd_aprobar)
    c = sub.add_parser("comparar", help="comparar un perfil con los datos sintéticos")
    c.add_argument("perfil")
    c.add_argument("--escenario", choices=list(DATOS), default="realista")
    c.set_defaults(funcion=cmd_comparar)
    args = parser.parse_args()
    args.funcion(args)


if __name__ == "__main__":
    main()
