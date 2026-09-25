"""Documentación viva: los .md del proyecto con valores actuales, bitácora y descarga."""
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

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

escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
metadata = load_maestro_metadata(escenario)
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** (se cambia en la barra lateral).")


@st.cache_data(show_spinner="Calculando los valores de la documentación...")
def contexto_actual(escenario, flota, consumo, ground_truth, legitimos, estaciones, telemetria, telemetria_diaria,
                    solicitudes, facturacion, facturacion_detalle, metadata):
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
    """Los enlaces relativos entre documentos no funcionan dentro de la app: se muestran en negrita."""
    return re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+\)", r"**\1**", texto)


def mostrar(texto):
    for tipo, contenido in documentacion.partes(texto):
        if tipo == "diagrama":
            st.graphviz_chart(contenido, use_container_width=True)
        else:
            st.markdown(para_pantalla(contenido))


VISTAS = ["📄 Documentos", "🗓️ Bitácora", "🔣 Variables"]
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista_documentacion", label_visibility="collapsed")
st.markdown("---")

# ---------------------------------------------------------------- Documentos
if vista == VISTAS[0]:
    disponibles = documentacion.documentos_disponibles()
    rutas = [ruta for _, _, ruta in disponibles]
    etiqueta = {ruta: f"{seccion} · {titulo}" for seccion, titulo, ruta in disponibles}
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ruta = st.selectbox("Documento", rutas, format_func=etiqueta.get, key="documento")
    texto, desconocidas = documentacion.renderizar(documentacion.leer(ruta), contexto)
    with col2:
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
    commits = documentacion.historial_git(60)
    if commits.empty:
        st.info("El historial de git no está disponible en este entorno.")
    else:
        tipos = sorted(t for t in commits["tipo"].unique() if t)
        elegidos = st.multiselect("Tipos de cambio", tipos, default=tipos, key="tipos_commit")
        filtrados = commits[commits["tipo"].isin(elegidos) | (commits["tipo"] == "")]
        st.dataframe(filtrados.rename(columns={"fecha": "Fecha", "tipo": "Tipo", "cambio": "Cambio",
                                               "commit": "Commit"}),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Variables
else:
    st.markdown("Variables disponibles para escribir en cualquier documento. Se usan así: `{{ filas.consumo }}`.")
    filas = [{"Variable": "{{ " + nombre + " }}",
              "Valor actual": "(tabla)" if str(valor).startswith("|") else str(valor)}
             for nombre, valor in sorted(contexto.items())]
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    st.caption("Las variables marcadas “(tabla)” se reemplazan por una tabla completa.")
