"""Documentación viva: markdown del repositorio con variables que toman valores actuales.

Una variable se escribe `{{ nombre }}` dentro de un .md. Al mostrar el documento se
reemplaza por su valor calculado sobre los datos del escenario en uso (por ejemplo,
`{{ filas.consumo }}` o `{{ hipotesis.tabla }}`). Si un nombre no existe, se deja tal
cual y se informa, para que no pase desapercibido.

Para qué sirve este archivo
---------------------------
Los documentos del proyecto (README, bitácora, estado actual...) están escritos en
markdown, un formato de texto simple con títulos, listas y tablas. Si un documento dijera
"hay 12.345 cargas", ese número quedaría viejo apenas se regeneren los datos. Por eso, en
lugar del número se escribe una variable, y esta herramienta la reemplaza por el valor
actual en el momento de mostrar el documento. Es lo que se llama "documentación viva".

Cómo encaja con los demás
-------------------------
- La página de documentación de la app Streamlit usa `documentos_disponibles()` para armar
  el menú, `construir_contexto()` para calcular los valores, `renderizar()` para reemplazar
  las variables, `partes()` para separar texto y diagramas, y `zip_de_documentos()` para
  ofrecer la descarga de todo junto.
- Los datos que recibe `construir_contexto()` vienen de `data_loader.py`.
"""
import io
import re
import subprocess
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent
# Expresiones regulares (patrones de búsqueda de texto) que usa este archivo:
# - PATRON_VARIABLE encuentra "{{ nombre }}": dos llaves, espacios opcionales, un nombre hecho de
#   letras, números, guiones bajos y puntos (que queda "capturado" entre paréntesis), y dos llaves.
# - PATRON_MERMAID encuentra un bloque de código ```mermaid ... ``` (un diagrama); re.DOTALL hace
#   que el punto también abarque saltos de línea, para tomar el bloque entero.
PATRON_VARIABLE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
PATRON_MERMAID = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

# (sección, título, ruta relativa a la raíz); el orden es el del selector
DOCUMENTOS = [
    ("Estado", "Estado actual (valores vivos)", "docs/ESTADO_ACTUAL.md"),
    ("Estado", "Bitácora", "docs/BITACORA.md"),
    ("Proyecto", "README", "README.md"),
    ("Proyecto", "Aplicación Streamlit", "streamlit_app/README.md"),
    ("Datos", "Diccionario de datos", "docs/DICCIONARIO_DATOS.md"),
    ("Datos", "Gobierno de datos y persistencia", "docs/DATA_GOVERNANCE.md"),
    ("Datos", "Límite de metadatos reales", "docs/REAL_DATA_BOUNDARY.md"),
    ("Datos", "Perfiles de fuentes", "perfiles/README.md"),
    ("Técnica", "Arquitectura", "docs/ARCHITECTURE.md"),
    ("Técnica", "Entorno de desarrollo", "docs/DEVELOPMENT.md"),
    ("Trabajo en equipo", "Reglas para agentes de IA", "AGENTS.md"),
    ("Trabajo en equipo", "Guía de contribución", "CONTRIBUTING.md"),
    ("Trabajo en equipo", "Playbook de IA", "docs/AI_PLAYBOOK.md"),
    ("Historia", "Evolución de los generadores", "legacy/EVOLUCION.md"),
    ("Historia", "Sprint 1: registro histórico", "docs/sprints/sprint-1/README.md"),
]


def documentos_disponibles():
    """Los documentos de DOCUMENTOS que existen en el repositorio.

    No recibe nada. Devuelve la lista de (sección, título, ruta) de los documentos cuyo
    archivo existe, en el mismo orden. Así, si un documento se borra o se mueve, desaparece
    del menú en lugar de dar un error.
    """
    return [(seccion, titulo, ruta) for seccion, titulo, ruta in DOCUMENTOS if (BASE_DIR / ruta).exists()]


def leer(ruta):
    """Devuelve el texto de un documento, dada su ruta relativa a la raíz del repositorio."""
    return (BASE_DIR / ruta).read_text(encoding="utf-8")


# ============================================================================
# Variables
# ============================================================================

def _git(*argumentos):
    """Ejecuta un comando de git y devuelve lo que imprime, o texto vacío si no se puede.

    Git es la herramienta que guarda el historial de cambios del proyecto. Recibe los
    argumentos del comando (por ejemplo "log", "-1"). Si git no está instalado, tarda más de
    10 segundos o falla (como pasa en algunos servidores en la nube), devuelve "" en lugar de
    romper la página.
    """
    try:
        salida = subprocess.run(["git", *argumentos], cwd=BASE_DIR, capture_output=True, text=True,
                                encoding="utf-8", timeout=10)
        # returncode 0 significa que el comando terminó bien
        return salida.stdout.strip() if salida.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def historial_git(cantidad=40):
    """Últimos commits: fecha, tipo (Conventional Commits), descripción y hash. Vacío si no hay git.

    Un "commit" es un cambio guardado en el historial. Por convención (Conventional Commits),
    su título empieza con el tipo de cambio: "feat: ...", "fix: ...", "docs: ...". Recibe cuántos
    commits traer y devuelve una tabla con columnas fecha, tipo, cambio y commit (el hash, un
    código corto que identifica cada commit). Se usa para la bitácora.
    """
    # Se pide a git que separe los campos con el carácter \x1f (un separador invisible que no
    # aparece en textos normales), para poder cortarlos sin confundirlos con el contenido
    texto = _git("log", f"-n{cantidad}", "--date=short", "--pretty=format:%h\x1f%ad\x1f%s")
    filas = []
    for linea in texto.splitlines():
        hash_, fecha, asunto = linea.split("\x1f")
        # "feat: agrega X" -> tipo "feat", descripción "agrega X"; sin ": " no hay tipo
        tipo, _, descripcion = asunto.partition(": ")
        if not descripcion:
            tipo, descripcion = "", asunto
        filas.append({"fecha": fecha, "tipo": tipo, "cambio": descripcion, "commit": hash_})
    return pd.DataFrame(filas, columns=["fecha", "tipo", "cambio", "commit"])


def _tabla_markdown(df):
    """Convierte una tabla de pandas en el texto de una tabla markdown.

    Recibe un DataFrame y devuelve un texto con la forma
    "| col1 | col2 |", "|---|---|", "| valor | valor |"..., que al mostrarse como markdown
    se ve como una tabla. Se usa para las variables que valen una tabla entera.
    """
    encabezado = "| " + " | ".join(df.columns) + " |"
    separador = "|" + "---|" * len(df.columns)
    filas = ["| " + " | ".join(str(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join([encabezado, separador] + filas)


def construir_contexto(escenario, datos, metadata, veredictos=None):
    """Valores disponibles para los documentos, calculados sobre los datos en uso.

    `datos` es un dict {tabla: DataFrame o None}; `veredictos`, el resultado de
    `contrastar_hipotesis` (solo escenario realista).

    El "contexto" es el diccionario {nombre de variable: valor} que usa `renderizar()`.
    Recibe además el escenario y la `metadata` de la generación (semilla, cantidad de
    vehículos, fecha). Devuelve ese diccionario con: fecha de hoy, datos de la generación y
    de la versión del código, cantidad de filas de cada tabla, resumen de anomalías, casos
    legítimos, resultado de las hipótesis y últimos cambios de la bitácora. Los números se
    escriben al estilo español (punto de miles, coma decimal).
    """
    contexto = {
        "hoy": date.today().isoformat(),
        "escenario": {"realista": "realista", "didactico": "didáctico"}[escenario],
        "generacion.seed": metadata.get("seed", "—"),
        "generacion.vehiculos": metadata.get("n_flota", "—"),
        "generacion.fecha": str(metadata.get("fecha_generacion", "—"))[:10],
        "version.commit": _git("rev-parse", "--short", "HEAD") or "—",
        "version.fecha": _git("log", "-1", "--date=short", "--pretty=format:%ad") or "—",
        "version.rama": _git("rev-parse", "--abbrev-ref", "HEAD") or "—",
    }
    # Python escribe los miles con coma (12,345); se cambia por punto (12.345)
    for tabla, df in datos.items():
        contexto[f"filas.{tabla}"] = f"{len(df):,}".replace(",", ".") if df is not None else "—"

    ground_truth = datos.get("ground_truth")
    consumo = datos.get("consumo")
    if ground_truth is not None and consumo is not None:
        # Prevalencia: qué porcentaje de las cargas tiene alguna anomalía de comportamiento. Se
        # excluyen las de calidad de datos y las de H1 (vinculación entre tablas), que no son
        # conductas sobre una carga, y cada carga se cuenta una sola vez (nunique)
        comportamiento = ground_truth[~ground_truth["hipotesis"].isin(["CALIDAD", "H1"])]
        en_cargas = comportamiento[comportamiento["tabla"] == "consumo"]["id_registro"].nunique()
        contexto.update({
            "anomalias.total": f"{len(ground_truth):,}".replace(",", "."),
            "anomalias.tipos": ground_truth["tipo_anomalia"].nunique(),
            "anomalias.prevalencia": f"{en_cargas / len(consumo):.2%}".replace(".", ","),
            # Cantidad de casos por tipo de anomalía e hipótesis, como tabla
            "anomalias.tabla": _tabla_markdown(
                ground_truth.groupby(["tipo_anomalia", "hipotesis"]).size().reset_index(name="casos")
                .rename(columns={"tipo_anomalia": "Tipo", "hipotesis": "Hipótesis", "casos": "Casos"})),
        })
    legitimos = datos.get("casos_legitimos")
    if legitimos is not None:
        contexto.update({
            "legitimos.total": f"{len(legitimos):,}".replace(",", "."),
            "legitimos.tabla": _tabla_markdown(
                legitimos.groupby("tipo_caso").size().reset_index(name="casos")
                .rename(columns={"tipo_caso": "Tipo", "casos": "Casos"})),
        })
    # Resultado de contrastar cada hipótesis. F1 es una medida de acierto de la detección entre 0 y 1
    # (1 = encuentra todas las anomalías sin falsas alarmas). Se compara la detección "ingenua" con la
    # que usa contexto, y cuántas falsas alarmas sobre casos legítimos tiene cada una ("antes → después").
    if veredictos is not None and not veredictos.empty:
        tabla = veredictos.assign(
            f1_ingenua=veredictos["f1_ingenua"].fillna(0).map(lambda v: f"{v:.2f}".replace(".", ",")),
            f1_contexto=veredictos["f1_contexto"].map(lambda v: f"{v:.2f}".replace(".", ",")),
            falsas=veredictos["fp_legitimos_ingenua"].astype(int).astype(str) + " → "
            + veredictos["fp_legitimos_contexto"].astype(int).astype(str),
        )[["hipotesis", "titulo", "veredicto", "f1_ingenua", "f1_contexto", "falsas"]]
        tabla.columns = ["Hipótesis", "Tema", "Veredicto", "F1 ingenua", "F1 con contexto",
                         "Falsas alarmas legítimas"]
        contexto.update({
            "hipotesis.total": len(veredictos),
            "hipotesis.sostenidas": int((veredictos["veredicto"] == "Se sostiene").sum()),
            "hipotesis.tabla": _tabla_markdown(tabla),
        })
        # Además, una variable por hipótesis (por ejemplo, hipotesis.H1.veredicto)
        for fila in veredictos.itertuples():
            contexto[f"hipotesis.{fila.hipotesis}.veredicto"] = fila.veredicto
            contexto[f"hipotesis.{fila.hipotesis}.f1"] = f"{fila.f1_contexto:.2f}".replace(".", ",")

    # Lo que no aplica al escenario (por ejemplo, hipótesis en el didáctico) se muestra explícitamente
    # (setdefault solo asigna el valor si la variable todavía no tiene uno)
    no_aplica = "—"
    for nombre in ["hipotesis.total", "hipotesis.sostenidas", "legitimos.total", "anomalias.total",
                   "anomalias.tipos", "anomalias.prevalencia"]:
        contexto.setdefault(nombre, no_aplica)
    contexto.setdefault("hipotesis.tabla", "_Las hipótesis se contrastan en el escenario realista._")
    contexto.setdefault("legitimos.tabla", "_Los casos legítimos solo existen en el escenario realista._")
    contexto.setdefault("anomalias.tabla", "_Sin datos._")

    commits = historial_git(10)
    contexto["bitacora.ultimos_cambios"] = (
        _tabla_markdown(commits.rename(columns={"fecha": "Fecha", "tipo": "Tipo", "cambio": "Cambio",
                                                "commit": "Commit"}))
        if not commits.empty else "_El historial de git no está disponible en este entorno._")
    return contexto


# Encuentra lo que en markdown está escrito como código: bloques entre tres backticks (```...```)
# o fragmentos cortos entre un backtick de cada lado (`...`) que no cruzan de línea
PATRON_CODIGO = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)


def renderizar(texto, contexto):
    """Reemplaza las variables `{{ nombre }}`. Devuelve (texto, variables desconocidas).

    Lo que está escrito como código (entre backticks o en un bloque de código) no se
    reemplaza: así un documento puede mostrar una variable de ejemplo tal cual.

    Recibe el texto markdown de un documento y el contexto que arma `construir_contexto()`.
    Devuelve el texto ya completado y la lista ordenada de variables que no existían en el
    contexto, para poder avisar de ellas en pantalla.
    """
    desconocidas = []

    def valor(coincidencia):
        """Texto que reemplaza a una variable encontrada en el documento.

        Se llama una vez por cada "{{ nombre }}" que encuentra PATRON_VARIABLE. Recibe la
        coincidencia (qué se encontró) y devuelve el valor de la variable como texto. Si la
        variable no existe en el contexto, la anota en `desconocidas` y devuelve
        "{{ nombre }}" tal cual estaba.
        """
        nombre = coincidencia.group(1)
        if nombre in contexto:
            return str(contexto[nombre])
        desconocidas.append(nombre)
        return coincidencia.group(0)

    fragmentos = PATRON_CODIGO.split(texto)
    # split con un grupo alterna texto (posiciones pares) y código (impares)
    resultado = [PATRON_VARIABLE.sub(valor, f) if i % 2 == 0 else f for i, f in enumerate(fragmentos)]
    return "".join(resultado), sorted(set(desconocidas))


# ============================================================================
# Diagramas y descarga
# ============================================================================

def mermaid_a_dot(bloque):
    """Convierte un flowchart de Mermaid simple (A -->|"etiqueta"| B) a DOT de Graphviz.

    Mermaid y DOT son dos formas de describir un diagrama con texto (cajas unidas por
    flechas). Los documentos usan Mermaid, pero Streamlit dibuja diagramas en DOT (el formato
    de la herramienta Graphviz), así que se traduce. Recibe el texto del bloque Mermaid y
    devuelve el texto DOT equivalente. Solo entiende lo que usan los documentos del proyecto:
    flechas con etiqueta (continuas "-->" o punteadas "-.->") y la línea "class" que marca
    algunos nodos, que se pintan de otro color.
    """
    aristas, nodos_evaluacion = [], set()
    for linea in bloque.splitlines():
        linea = linea.strip()
        # Captura: nodo de origen, tipo de flecha, etiqueta (con o sin comillas) y nodo de destino
        m = re.match(r'(\w+)\s*(-\.->|-->)\s*\|"?(.*?)"?\|\s*(\w+)', linea)
        if m:
            origen, flecha, etiqueta, destino = m.groups()
            estilo = ", style=dashed" if flecha == "-.->" else ""
            aristas.append(f'  "{origen}" -> "{destino}" [label="{etiqueta}"{estilo}];')
        elif linea.startswith("class "):
            # "class A,B,C nombreDeClase": se toman los nodos A, B y C
            nodos_evaluacion.update(n.strip() for n in linea.split()[1].split(","))
    nodos = [f'  "{n}" [fillcolor="#fdf1dc"];' for n in sorted(nodos_evaluacion)]
    # Encabezado del diagrama: de izquierda a derecha (rankdir=LR), cajas redondeadas y el estilo de letra
    return "\n".join(['digraph {', '  rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#eef3fb", '
                      'fontname="Helvetica"]; edge [fontname="Helvetica", fontsize=9];'] + nodos + aristas + ["}"])


def partes(texto):
    """Divide el markdown en fragmentos ("markdown", texto) y ("diagrama", dot).

    Recibe el texto de un documento y devuelve una lista de pares (tipo, contenido), en el
    orden en que aparecen. La página muestra los fragmentos "markdown" como texto y dibuja
    los "diagrama" como gráficos. Se descartan los fragmentos vacíos.
    """
    resultado, inicio = [], 0
    # Se recorre cada bloque Mermaid: lo anterior a él es texto, y el bloque se convierte en diagrama
    for m in PATRON_MERMAID.finditer(texto):
        resultado.append(("markdown", texto[inicio:m.start()]))
        resultado.append(("diagrama", mermaid_a_dot(m.group(1))))
        inicio = m.end()
    resultado.append(("markdown", texto[inicio:]))
    return [(tipo, contenido) for tipo, contenido in resultado if contenido.strip()]


def zip_de_documentos(contexto):
    """Toda la documentación, con las variables ya reemplazadas, en un .zip en memoria.

    Recibe el contexto de `construir_contexto()` y devuelve el contenido del archivo .zip
    (en bytes) para que la página lo ofrezca como descarga. "En memoria" quiere decir que el
    .zip se arma sin escribir ningún archivo en disco. Dentro, cada documento conserva su
    ruta en el repositorio.
    """
    # BytesIO es un "archivo" que vive en la memoria
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivo:
        for _, _, ruta in documentos_disponibles():
            texto, _ = renderizar(leer(ruta), contexto)
            archivo.writestr(ruta, texto)
    return buffer.getvalue()
