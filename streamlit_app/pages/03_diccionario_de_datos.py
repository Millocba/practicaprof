"""Diccionario de datos: tablas, columnas, relaciones y catálogos del escenario.

Todo sale del `diccionario.json` que escribe el generador en cada corrida y de los
catálogos del propio generador, así que describe exactamente los datos generados.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

from data_loader import (  # noqa: E402
    NOMBRES_ESCENARIO,
    asegurar_datos_maestro,
    directorio,
    load_casos_legitimos,
    load_diccionario,
    load_ground_truth_maestro,
    selector_escenario,
)
from generator_pipeline_maestro import (  # noqa: E402
    CATALOGO_ANOMALIAS,
    CATALOGO_LEGITIMOS,
    TIPOS_POR_ESCENARIO,
    diagrama_relaciones,
)

st.set_page_config(page_title="Diccionario de datos", page_icon="📖", layout="wide")

st.markdown("# 📖 Diccionario de datos")
st.markdown(
    "Qué contiene cada tabla, cómo se relacionan y qué anomalías y casos legítimos se inyectan. "
    "Lo escribe el generador en cada corrida (`diccionario.json`), así que describe exactamente los "
    "datos que se están usando."
)

escenario = selector_escenario()
asegurar_datos_maestro(escenario)
diccionario = load_diccionario(escenario)
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** (se cambia en la barra lateral).")

if not diccionario["tablas"]:
    st.error("❌ No se encontró el diccionario. Ejecutá el Generador y volvé a esta página.")
    st.stop()

EVALUACION = {"ground_truth", "casos_legitimos"}
DETALLE = {"telemetria_diaria": "telemetria", "facturacion_detalle": "facturacion"}


def rol(tabla):
    if tabla in EVALUACION:
        return "Evaluación"
    if tabla in DETALLE:
        return f"Detalle de {DETALLE[tabla]}"
    return "Entidad"


def filas_de(tabla):
    archivo = directorio(escenario) / f"{tabla}.csv"
    if not archivo.exists():
        return None
    with open(archivo, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


# ---------------------------------------------------------------- Tablas
st.markdown("## Tablas")
resumen = pd.DataFrame([{
    "Tabla": nombre, "Rol": rol(nombre), "Grano (una fila por…)": tabla["grano"], "Clave": tabla["clave"],
    "Columnas": len(tabla["columnas"]), "Filas": filas_de(nombre),
} for nombre, tabla in diccionario["tablas"].items()])
st.dataframe(resumen, use_container_width=True, hide_index=True,
             column_config={"Filas": st.column_config.NumberColumn(format="%d")})
st.caption("**Entidad**: lo que se audita. **Detalle**: la misma entidad con más grano (no es un duplicado). "
           "**Evaluación**: verdad de referencia; no es entrada de las reglas ni de los modelos.")

# ---------------------------------------------------------------- Relaciones
st.markdown("## Relaciones")
st.graphviz_chart(diagrama_relaciones(diccionario), use_container_width=True)
st.caption("Las líneas punteadas no son claves: se resuelven por emparejamiento o agregación. "
           "En naranja, las tablas de evaluación.")
relaciones = pd.DataFrame(diccionario["relaciones"]).rename(columns={
    "origen": "Tabla", "columna_origen": "Columna", "destino": "Se relaciona con",
    "columna_destino": "Columna destino", "cardinalidad": "Cardinalidad", "nota": "Nota"})
st.dataframe(relaciones, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Columnas
st.markdown("## Columnas")
col1, col2 = st.columns([3, 1])
with col1:
    tabla_sel = st.selectbox("Tabla", list(diccionario["tablas"]), key="tabla_diccionario",
                             format_func=lambda t: f"{t} — {diccionario['tablas'][t]['grano']}")
with col2:
    st.markdown("&nbsp;")
    st.download_button("⬇️ Descargar diccionario (JSON)", json.dumps(diccionario, indent=2, ensure_ascii=False),
                       file_name=f"diccionario_{escenario}.json", mime="application/json",
                       use_container_width=True)
tabla = diccionario["tablas"][tabla_sel]
st.caption(f"Grano: **{tabla['grano']}** · Clave: `{tabla['clave']}` · {rol(tabla_sel)}")
st.dataframe(pd.DataFrame(tabla["columnas"]).rename(
    columns={"nombre": "Columna", "tipo": "Tipo", "descripcion": "Descripción"}),
    use_container_width=True, hide_index=True)
vinculos = relaciones[(relaciones["Tabla"] == tabla_sel)
                      | relaciones["Se relaciona con"].str.contains(rf"\b{tabla_sel}\b", regex=True)]
if not vinculos.empty:
    st.markdown(f"**Relaciones de `{tabla_sel}`**")
    st.dataframe(vinculos, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Catálogos
st.markdown("## Anomalías inyectadas")
ground_truth = load_ground_truth_maestro(escenario)
cantidad = ground_truth["tipo_anomalia"].value_counts() if not ground_truth.empty else pd.Series(dtype=int)
tabla_de = ground_truth.groupby("tipo_anomalia")["tabla"].first() if not ground_truth.empty else pd.Series(dtype=str)
anomalias = pd.DataFrame([{
    "Tipo": tipo, "Hipótesis": CATALOGO_ANOMALIAS[tipo][0], "Severidad": CATALOGO_ANOMALIAS[tipo][1],
    "Tabla": tabla_de.get(tipo, "consumo"), "En los datos": int(cantidad.get(tipo, 0)),
} for tipo in TIPOS_POR_ESCENARIO[escenario]])
st.dataframe(anomalias, use_container_width=True, hide_index=True)
st.caption("Cómo se inyecta cada una: `docs/DICCIONARIO_DATOS.md`. El detalle de cada caso está en la tabla "
           "`ground_truth`.")

if escenario == "realista":
    st.markdown("## Casos legítimos que se parecen a anomalías")
    legitimos = load_casos_legitimos(escenario)
    casos = legitimos["tipo_caso"].value_counts() if not legitimos.empty else pd.Series(dtype=int)
    st.dataframe(pd.DataFrame([{"Tipo": tipo, "Qué ocurre": descripcion, "En los datos": int(casos.get(tipo, 0))}
                               for tipo, descripcion in CATALOGO_LEGITIMOS.items()]),
                 use_container_width=True, hide_index=True)
    st.caption("No son anomalías: sirven para medir cuántas falsas alarmas produce cada regla.")
