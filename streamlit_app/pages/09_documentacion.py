"""Documentación viva: los .md del proyecto con valores actuales, bitácora y descarga.

Qué muestra esta página
-----------------------
Los documentos del proyecto (archivos `.md`, texto con formato Markdown) dentro de la app. Tiene
tres vistas:

- Documentos: elegir un documento, leerlo y descargarlo (uno o todos juntos en un `.zip`).
- Bitácora: el registro de cambios importantes del proyecto, escrito a mano, más el historial de
  commits de git (cada cambio guardado en el código).
- Variables: la lista de valores que se pueden insertar en los documentos.

Es "documentación viva" porque los documentos pueden tener variables con la forma `{{ nombre }}`
(por ejemplo, la cantidad de filas de una tabla o el veredicto de cada hipótesis). Al mostrarlos o
descargarlos, esas variables se reemplazan por los valores calculados con los datos en uso, así el
texto nunca queda desactualizado respecto de los números.

Para qué la usa quien audita
----------------------------
Para consultar la metodología y los resultados vigentes sin salir de la app, y para descargar un
informe con los números del escenario elegido.

Cómo encaja en la app
---------------------
Usa el escenario elegido en la barra lateral. La lista de documentos y el cálculo de las variables
están en `utils/documentacion.py`; esta página solo junta los datos, arma los valores y los muestra.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Se agregan a la ruta de búsqueda de Python la carpeta `utils` de la app y la raíz del repositorio,
# para poder importar `documentacion`, `data_loader` y el paquete `deteccion`.
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

import documentacion  # noqa: E402
from data_loader import (  # noqa: E402
    NOMBRES_ESCENARIO,
    asegurar_datos_maestro,
    load_dataset_deteccion,
    load_maestro_metadata,
    load_telemetria,
    selector_escenario,
)
from deteccion.hipotesis import contrastar_hipotesis  # noqa: E402
from deteccion.reglas import ejecutar_reglas  # noqa: E402

st.set_page_config(page_title="Documentación", page_icon="📚", layout="wide")

st.markdown("# 📚 Documentación")
st.markdown(
    "La documentación del proyecto con los **valores actuales**: las variables de cada documento "
    "(`{{ nombre }}`) se completan con los datos en uso. Incluye la **bitácora** de cambios y se puede "
    "descargar tal como se ve."
)

# Recordatorio de Streamlit: el archivo entero se vuelve a ejecutar de arriba a abajo cada vez que la
# persona toca un control. Acá se lee el escenario de la barra lateral, se generan los datos si
# faltan y se cargan las tablas y la metadata (semilla, cantidad de vehículos, etc.).
escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
metadata = load_maestro_metadata(escenario)
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** (se cambia en la barra lateral).")


# `@st.cache_data` guarda el resultado en memoria: los valores se calculan una vez por dataset y no
# en cada re-ejecución. `show_spinner` define el mensaje de espera que se ve la primera vez.
@st.cache_data(show_spinner="Calculando los valores de la documentación...")
def contexto_actual(escenario, flota, consumo, ground_truth, legitimos, estaciones, telemetria, telemetria_diaria,
                    solicitudes, facturacion, facturacion_detalle, metadata):
    """Calcula el "contexto": el diccionario de variables que se reemplazan en los documentos.

    Junta las tablas del dataset (las vacías se pasan como `None`) y, si hay casos legítimos
    (escenario realista), corre las reglas y contrasta las hipótesis para tener sus veredictos.
    Devuelve un diccionario `nombre de variable -> valor`.
    """
    tablas = {
        "flota": flota, "consumo": consumo, "solicitudes": solicitudes, "facturacion": facturacion,
        "facturacion_detalle": facturacion_detalle, "telemetria": telemetria,
        "telemetria_diaria": telemetria_diaria, "estaciones": estaciones,
        "ground_truth": ground_truth, "casos_legitimos": legitimos,
    }
    tablas = {nombre: (None if df is None or df.empty else df) for nombre, df in tablas.items()}
    veredictos = None
    if legitimos is not None:
        alertas = ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                                  facturacion_detalle)
        _, veredictos = contrastar_hipotesis(alertas, ground_truth, legitimos, facturacion_detalle)
    return documentacion.construir_contexto(escenario, tablas, metadata, veredictos)


contexto = contexto_actual(
    escenario, datos["flota"], datos["consumo"], datos["ground_truth"], datos["casos_legitimos"],
    datos["estaciones"], load_telemetria(escenario), datos["telemetria_diaria"],
    datos["solicitudes"], datos["facturacion"],
    datos["facturacion_detalle"], metadata)


def para_pantalla(texto):
    """Los enlaces relativos entre documentos no funcionan dentro de la app: se muestran en negrita.

    Usa una expresión regular (un patrón de búsqueda de texto) que encuentra los enlaces Markdown
    `[texto](destino)` cuyo destino no empieza con http:// o https:// y los reemplaza por
    `**texto**`. Los enlaces a páginas web se dejan como están.
    """
    return re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+\)", r"**\1**", texto)


def mostrar(texto):
    """Muestra un documento en pantalla.

    El documento se divide en partes: los diagramas (escritos en el lenguaje de Graphviz) se dibujan
    como gráfico, y el resto se muestra como texto Markdown con los enlaces internos ajustados.
    """
    for tipo, contenido in documentacion.partes(texto):
        if tipo == "diagrama":
            st.graphviz_chart(contenido, use_container_width=True)
        else:
            st.markdown(para_pantalla(contenido))


# Selector de vista. `st.radio` devuelve la opción elegida y el `key` le da un nombre fijo en
# `st.session_state` (la memoria de la sesión), para que la vista elegida se mantenga entre
# re-ejecuciones. Según la opción se dibuja solo uno de los tres bloques de abajo.
VISTAS = ["📄 Documentos", "🗓️ Bitácora", "🔣 Variables"]
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista_documentacion", label_visibility="collapsed")
st.markdown("---")

# ---------------------------------------------------------------- Documentos
if vista == VISTAS[0]:
    # Cada documento disponible viene como (sección, título, ruta del archivo). El selector usa la ruta
    # como valor, pero muestra "sección · título". Tres columnas: selector ancho y dos botones.
    disponibles = documentacion.documentos_disponibles()
    rutas = [ruta for _, _, ruta in disponibles]
    etiqueta = {ruta: f"{seccion} · {titulo}" for seccion, titulo, ruta in disponibles}
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ruta = st.selectbox("Documento", rutas, format_func=etiqueta.get, key="documento")
    # `renderizar` reemplaza las variables `{{ ... }}` por sus valores y devuelve también la lista de
    # variables que no encontró (para avisar más abajo).
    texto, desconocidas = documentacion.renderizar(documentacion.leer(ruta), contexto)
    with col2:
        # Un espacio en blanco para que el botón quede alineado con el selector de la izquierda.
        st.markdown("&nbsp;")
        st.download_button("⬇️ Este documento", texto, file_name=Path(ruta).name, mime="text/markdown",
                           use_container_width=True, key="descargar_documento")
    with col3:
        st.markdown("&nbsp;")
        st.download_button("⬇️ Toda la documentación", documentacion.zip_de_documentos(contexto),
                           file_name=f"documentacion_{contexto['hoy']}.zip", mime="application/zip",
                           use_container_width=True, key="descargar_todo")
    st.caption(f"Archivo: `{ruta}`. La descarga incluye los valores actuales.")
    if desconocidas:
        st.warning("⚠️ Variables sin valor en este documento: " + ", ".join(f"`{v}`" for v in desconocidas)
                   + ". Revisá la lista en la vista **🔣 Variables**.")
    mostrar(texto)

# ---------------------------------------------------------------- Bitácora
elif vista == VISTAS[1]:
    texto, _ = documentacion.renderizar(documentacion.leer("docs/BITACORA.md"), contexto)
    st.download_button("⬇️ Descargar la bitácora", texto, file_name="BITACORA.md", mime="text/markdown",
                       key="descargar_bitacora")
    mostrar(texto)
    st.markdown("## Historial de commits")
    st.caption("Leído en vivo de git: cada cambio del código, con su tipo (feat, fix, docs, test…).")
    # Los últimos 60 commits. Si la app corre donde no hay git (por ejemplo, un despliegue en la nube
    # sin historial), la tabla viene vacía y se muestra un aviso.
    commits = documentacion.historial_git(60)
    if commits.empty:
        st.info("El historial de git no está disponible en este entorno.")
    else:
        tipos = sorted(t for t in commits["tipo"].unique() if t)
        elegidos = st.multiselect("Tipos de cambio", tipos, default=tipos, key="tipos_commit")
        # Los commits sin tipo reconocido se muestran siempre, sin importar el filtro.
        filtrados = commits[commits["tipo"].isin(elegidos) | (commits["tipo"] == "")]
        st.dataframe(filtrados.rename(columns={"fecha": "Fecha", "tipo": "Tipo", "cambio": "Cambio",
                                               "commit": "Commit"}),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Variables
else:
    st.markdown("Variables disponibles para escribir en cualquier documento. Se usan así: `{{ filas.consumo }}`.")
    # Una fila por variable. Las que contienen una tabla Markdown completa (empiezan con "|") se
    # resumen como "(tabla)" para no llenar la pantalla.
    filas = [{"Variable": "{{ " + nombre + " }}",
              "Valor actual": "(tabla)" if str(valor).startswith("|") else str(valor)}
             for nombre, valor in sorted(contexto.items())]
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    st.caption("Las variables marcadas “(tabla)” se reemplazan por una tabla completa.")
