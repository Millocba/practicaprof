"""Documentación viva: markdown del repositorio con variables que toman valores actuales.

Una variable se escribe `{{ nombre }}` dentro de un .md. Al mostrar el documento se
reemplaza por su valor calculado sobre los datos del escenario en uso (por ejemplo,
`{{ filas.consumo }}` o `{{ hipotesis.tabla }}`). Si un nombre no existe, se deja tal
cual y se informa, para que no pase desapercibido.
"""
import io
import re
import subprocess
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent
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
    ("Técnica", "Arquitectura", "docs/ARCHITECTURE.md"),
    ("Técnica", "Entorno de desarrollo", "docs/DEVELOPMENT.md"),
    ("Trabajo en equipo", "Reglas para agentes de IA", "AGENTS.md"),
    ("Trabajo en equipo", "Guía de contribución", "CONTRIBUTING.md"),
    ("Trabajo en equipo", "Playbook de IA", "docs/AI_PLAYBOOK.md"),
    ("Historia", "Evolución de los generadores", "legacy/EVOLUCION.md"),
    ("Historia", "Sprint 1: registro histórico", "docs/sprints/sprint-1/README.md"),
]


def documentos_disponibles():
    """Los documentos de DOCUMENTOS que existen en el repositorio."""
    return [(seccion, titulo, ruta) for seccion, titulo, ruta in DOCUMENTOS if (BASE_DIR / ruta).exists()]


def leer(ruta):
    return (BASE_DIR / ruta).read_text(encoding="utf-8")


# ============================================================================
# Variables
# ============================================================================

def _git(*argumentos):
    try:
        salida = subprocess.run(["git", *argumentos], cwd=BASE_DIR, capture_output=True, text=True,
                                encoding="utf-8", timeout=10)
        return salida.stdout.strip() if salida.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def historial_git(cantidad=40):
    """Últimos commits: fecha, tipo (Conventional Commits), descripción y hash. Vacío si no hay git."""
    texto = _git("log", f"-n{cantidad}", "--date=short", "--pretty=format:%h\x1f%ad\x1f%s")
    filas = []
    for linea in texto.splitlines():
        hash_, fecha, asunto = linea.split("\x1f")
        tipo, _, descripcion = asunto.partition(": ")
        if not descripcion:
            tipo, descripcion = "", asunto
        filas.append({"fecha": fecha, "tipo": tipo, "cambio": descripcion, "commit": hash_})
    return pd.DataFrame(filas, columns=["fecha", "tipo", "cambio", "commit"])


def _tabla_markdown(df):
    encabezado = "| " + " | ".join(df.columns) + " |"
    separador = "|" + "---|" * len(df.columns)
    filas = ["| " + " | ".join(str(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join([encabezado, separador] + filas)


def construir_contexto(escenario, datos, metadata, veredictos=None):
    """Valores disponibles para los documentos, calculados sobre los datos en uso.

    `datos` es un dict {tabla: DataFrame o None}; `veredictos`, el resultado de
    `contrastar_hipotesis` (solo escenario realista).
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
    for tabla, df in datos.items():
        contexto[f"filas.{tabla}"] = f"{len(df):,}".replace(",", ".") if df is not None else "—"

    ground_truth = datos.get("ground_truth")
    consumo = datos.get("consumo")
    if ground_truth is not None and consumo is not None:
        comportamiento = ground_truth[~ground_truth["hipotesis"].isin(["CALIDAD", "H1"])]
        en_cargas = comportamiento[comportamiento["tabla"] == "consumo"]["id_registro"].nunique()
        contexto.update({
            "anomalias.total": f"{len(ground_truth):,}".replace(",", "."),
            "anomalias.tipos": ground_truth["tipo_anomalia"].nunique(),
            "anomalias.prevalencia": f"{en_cargas / len(consumo):.2%}".replace(".", ","),
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
        for fila in veredictos.itertuples():
            contexto[f"hipotesis.{fila.hipotesis}.veredicto"] = fila.veredicto
            contexto[f"hipotesis.{fila.hipotesis}.f1"] = f"{fila.f1_contexto:.2f}".replace(".", ",")

    # Lo que no aplica al escenario (por ejemplo, hipótesis en el didáctico) se muestra explícitamente
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


PATRON_CODIGO = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)


def renderizar(texto, contexto):
    """Reemplaza las variables `{{ nombre }}`. Devuelve (texto, variables desconocidas).

    Lo que está escrito como código (entre backticks o en un bloque de código) no se
    reemplaza: así un documento puede mostrar una variable de ejemplo tal cual.
    """
    desconocidas = []

    def valor(coincidencia):
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
    """Convierte un flowchart de Mermaid simple (A -->|"etiqueta"| B) a DOT de Graphviz."""
    aristas, nodos_evaluacion = [], set()
    for linea in bloque.splitlines():
        linea = linea.strip()
        m = re.match(r'(\w+)\s*(-\.->|-->)\s*\|"?(.*?)"?\|\s*(\w+)', linea)
        if m:
            origen, flecha, etiqueta, destino = m.groups()
            estilo = ", style=dashed" if flecha == "-.->" else ""
            aristas.append(f'  "{origen}" -> "{destino}" [label="{etiqueta}"{estilo}];')
        elif linea.startswith("class "):
            nodos_evaluacion.update(n.strip() for n in linea.split()[1].split(","))
    nodos = [f'  "{n}" [fillcolor="#fdf1dc"];' for n in sorted(nodos_evaluacion)]
    return "\n".join(['digraph {', '  rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#eef3fb", '
                      'fontname="Helvetica"]; edge [fontname="Helvetica", fontsize=9];'] + nodos + aristas + ["}"])


def partes(texto):
    """Divide el markdown en fragmentos ("markdown", texto) y ("diagrama", dot)."""
    resultado, inicio = [], 0
    for m in PATRON_MERMAID.finditer(texto):
        resultado.append(("markdown", texto[inicio:m.start()]))
        resultado.append(("diagrama", mermaid_a_dot(m.group(1))))
        inicio = m.end()
    resultado.append(("markdown", texto[inicio:]))
    return [(tipo, contenido) for tipo, contenido in resultado if contenido.strip()]


def zip_de_documentos(contexto):
    """Toda la documentación, con las variables ya reemplazadas, en un .zip en memoria."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivo:
        for _, _, ruta in documentos_disponibles():
            texto, _ = renderizar(leer(ruta), contexto)
            archivo.writestr(ruta, texto)
    return buffer.getvalue()
