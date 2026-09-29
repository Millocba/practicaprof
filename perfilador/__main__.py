"""Perfilador de fuentes, desde la línea de comandos.

Uso:
    python -m perfilador perfilar archivo1.xlsx archivo2.csv --origen "fuentes reales"
        Escribe perfiles/pendientes/perfil_AAAA-MM-DD.json. Solo imprime conteos.
    python -m perfilador aprobar perfiles/pendientes/perfil_X.json --responsable "Nombre" [--notas "..."]
        Registra la revisión manual y lo pasa a perfiles/aprobados/ (se versiona).
    python -m perfilador comparar perfiles/aprobados/perfil_X.json [--escenario realista]
        Compara con los datos sintéticos y escribe el informe de brechas junto al perfil.

Los archivos de origen se leen en memoria y nunca se copian ni se escriben.
"""
# Nota: el texto de arriba (el "docstring" del módulo) también es la ayuda que se muestra con
# `python -m perfilador --help` (ver `description=__doc__` en main()). Por eso la explicación
# para quien lee el código va en estos comentarios y no dentro de ese texto.
#
# Qué es este archivo
# -------------------
# Un archivo llamado __main__.py dentro de un paquete es lo que Python ejecuta cuando se
# escribe `python -m perfilador` en la terminal. Es la "puerta de entrada" por línea de
# comandos: no calcula nada por sí mismo, sino que lee lo que escribió la persona (el
# subcomando y sus opciones) y llama a las funciones de `perfil.py` y `comparar.py`.
#
# Los tres subcomandos siguen el circuito de revisión descrito en perfiles/README.md:
#   1. perfilar  -> genera un perfil agregado y lo deja en perfiles/pendientes/ (no se versiona).
#   2. aprobar   -> una persona responsable lo revisó; se registra quién y cuándo, y el perfil
#                   pasa a perfiles/aprobados/ (sí se versiona con git).
#   3. comparar  -> se contrasta el perfil aprobado con los datos sintéticos del proyecto y se
#                   escribe un informe de "brechas" (diferencias) en markdown.
import argparse
import json
from datetime import date
from pathlib import Path

from perfilador.comparar import comparar, informe_markdown, perfil_de_directorio, sugerir_emparejamiento
from perfilador.perfil import aprobar_archivo, leer_tablas, perfilar

# Rutas de trabajo, calculadas a partir de la ubicación de este archivo para que funcionen
# sin importar desde qué carpeta se ejecute el comando. RAIZ es la carpeta del repositorio.
RAIZ = Path(__file__).parent.parent
PENDIENTES = RAIZ / "perfiles" / "pendientes"
APROBADOS = RAIZ / "perfiles" / "aprobados"
# Carpeta de datos sintéticos de cada escenario: "didactico" (anomalías evidentes, para explicar)
# y "realista" (anomalías sutiles). Son las que genera generator_pipeline_maestro.py.
DATOS = {"didactico": RAIZ / "datasets" / "synthetics_maestro", "realista": RAIZ / "datasets" / "synthetics_realista"}


def guardar(perfil, destino):
    """Guarda un perfil en disco como archivo JSON legible.

    Recibe:
        perfil: el diccionario que devuelve `perfilar()`.
        destino: la ruta (Path) del archivo a escribir.

    Crea la carpeta si no existe. `indent=2` deja el JSON con sangría para que una persona
    pueda revisarlo a simple vista, y `ensure_ascii=False` conserva los acentos tal cual
    en lugar de escribirlos como códigos. No devuelve nada.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(perfil, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_perfilar(args):
    """Subcomando `perfilar`: lee los archivos indicados y escribe su perfil agregado.

    Recibe `args`, las opciones que escribió la persona en la terminal (ya interpretadas
    por argparse): la lista de archivos, el texto de `--origen` y, opcionalmente, `--salida`.

    Junta todas las tablas de todos los archivos (un Excel puede aportar varias, una por
    hoja), arma un único perfil y lo guarda en perfiles/pendientes/ con la fecha del día,
    salvo que se indique otra ruta. En pantalla solo muestra conteos (cuántas tablas y
    relaciones), nunca valores de los datos. No devuelve nada.
    """
    tablas = {}
    for archivo in args.archivos:
        tablas.update(leer_tablas(Path(archivo), Path(archivo).name))
    perfil = perfilar(tablas, origen=args.origen)
    destino = Path(args.salida) if args.salida else PENDIENTES / f"perfil_{date.today().isoformat()}.json"
    guardar(perfil, destino)
    print(f"Perfil de {len(perfil['tablas'])} tablas y {len(perfil['relaciones'])} relaciones en {destino}")
    print("Revisalo antes de aprobarlo: python -m perfilador aprobar", destino, '--responsable "Nombre"')


def cmd_aprobar(args):
    """Subcomando `aprobar`: registra que una persona revisó el perfil y lo mueve a aprobados.

    Recibe `args` con la ruta del perfil, el nombre de `--responsable` y las `--notas`
    opcionales. La revisión manual es obligatoria según docs/REAL_DATA_BOUNDARY.md: nada
    sale de "pendientes" sin que alguien confirme que no permite reconocer a nadie.
    No devuelve nada; imprime dónde quedó el perfil aprobado.
    """
    destino = aprobar_archivo(args.perfil, APROBADOS, args.responsable, args.notas)
    print(f"Perfil aprobado por {args.responsable}: {destino}")


def cmd_comparar(args):
    """Subcomando `comparar`: contrasta un perfil real con los datos sintéticos del proyecto.

    Recibe `args` con la ruta del perfil y el `--escenario` sintético contra el que comparar.

    Pasos: 1) lee el perfil real; 2) arma, con el mismo perfilador, el perfil de los CSV
    sintéticos del escenario (así ambos se miden igual); 3) empareja cada tabla real con la
    sintética más parecida; 4) calcula las brechas; 5) escribe el informe en markdown junto
    al perfil (mismo nombre terminado en `_brechas.md`). Imprime cuántas brechas hay de cada
    severidad. No devuelve nada.
    """
    perfil_real = json.loads(Path(args.perfil).read_text(encoding="utf-8"))
    carpeta = DATOS[args.escenario]
    # Si todavía no se generaron los datos sintéticos, se corta con un mensaje que dice cómo generarlos
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
    """Punto de entrada: interpreta lo escrito en la terminal y ejecuta el subcomando elegido.

    Usa argparse, la herramienta estándar de Python para leer opciones de línea de comandos.
    Cada subcomando (perfilar, aprobar, comparar) tiene sus propias opciones y queda asociado
    a su función `cmd_...` mediante `set_defaults(funcion=...)`; al final se llama a esa
    función con las opciones ya interpretadas. No recibe ni devuelve nada.
    """
    # RawDescriptionHelpFormatter respeta los saltos de línea del docstring al mostrar la ayuda
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("perfilar", help="perfilar archivos CSV o Excel")
    # nargs="+" significa "uno o más archivos"
    p.add_argument("archivos", nargs="+")
    p.add_argument("--origen", default="fuentes reales")
    p.add_argument("--salida")
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


# Este bloque solo corre cuando el archivo se ejecuta directamente (python -m perfilador),
# no cuando otro archivo lo importa.
if __name__ == "__main__":
    main()
