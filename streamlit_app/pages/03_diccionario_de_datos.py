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

from ayudas import seccion  # noqa: E402
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

seccion(
    "📖 Diccionario de datos", nivel=1,
    ayuda="El mapa de los datos: qué contiene cada tabla, cómo se unen y qué defectos se les "
          "metieron a propósito. Todo sale del `diccionario.json` que escribe el generador en cada "
          "carrida, así que describe exactamente los archivos que están en disco, no una "
          "documentación que puede quedar vieja. Si no encontrás una tabla o una columna, no "
          "existe en estos datos.")
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
seccion(
    "Tablas",
    ayuda="Una fila por tabla, con su **grano** (qué representa una fila) y su **clave** (qué la "
          "identifica). El grano es lo más importante: sin él no se puede cruzar nada, porque dos "
          "tablas que parecen duplicadas pueden tener grano distinto. La columna de filas se lee "
          "contando los datos, no el tamaño del archivo.")
resumen = pd.DataFrame([{
    "Tabla": nombre, "Rol": rol(nombre), "Grano (una fila por…)": tabla["grano"], "Clave": tabla["clave"],
    "Columnas": len(tabla["columnas"]), "Filas": filas_de(nombre),
} for nombre, tabla in diccionario["tablas"].items()])
st.dataframe(resumen, use_container_width=True, hide_index=True,
             column_config={"Filas": st.column_config.NumberColumn(format="%d")})
st.caption("**Entidad**: lo que se audita. **Detalle**: la misma entidad con más grano (no es un duplicado). "
           "**Evaluación**: verdad de referencia; no es entrada de las reglas ni de los modelos.")

# ---------------------------------------------------------------- Relaciones
seccion(
    "Relaciones",
    ayuda="El diagrama muestra cómo se une cada tabla con las demás. Una flecha con cardinalidad "
          "**N:1** significa que muchas filas apuntan a una; una **1:1**, que el vínculo es único. "
          "Las flechas **punteadas no son claves**: son relaciones que existen en la realidad pero "
          "no se pueden resolver con una columna, así que hay que emparejarlas a mano. La tabla "
          "de abajo lista cada vínculo con su nota.")
st.graphviz_chart(diagrama_relaciones(diccionario), use_container_width=True)
st.caption("Las líneas punteadas no son claves: se resuelven por emparejamiento o agregación. "
           "En naranja, las tablas de evaluación.")
relaciones = pd.DataFrame(diccionario["relaciones"]).rename(columns={
    "origen": "Tabla", "columna_origen": "Columna", "destino": "Se relaciona con",
    "columna_destino": "Columna destino", "cardinalidad": "Cardinalidad", "nota": "Nota"})
st.dataframe(relaciones, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Columnas
seccion(
    "Columnas",
    ayuda="Elegí una tabla y queda el detalle de cada columna con su tipo y qué significa. Debajo "
          "aparecen solo las relaciones que **tocan esa tabla**, para no tener que filtrar la "
          "tabla grande. Es la página a la que hay que ir cuando una regla falla y no se entiende "
          "de dónde salió el dato.")
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
seccion(
    "Anomalías inyectadas",
    ayuda="Catálogo de los defectos que el generador metió a propósito, con la hipótesis a la que "
          "pertenecen, su severidad y **cuántas hay en los datos actuales**. Esta lista es la que "
          "permite medir si una regla funciona: es la verdad de referencia contra la que se "
          "evalúa todo en la página Detección.")
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
    seccion(
        "Casos legítimos que se parecen a anomalías",
        ayuda="Cargas que son perfectamente normales pero que una regla ingenua marcaría: un "
              "camión en un viaje largo, un odómetro nuevo, un tanque auxiliar no registrado. No "
              "están en la lista de anomalías y no hay que corregirlas; están para medir **cuántas "
              "falsas alarmas** produce cada regla. Si una técnica las confunde con anomalías, "
              "pierde valor aunque acierte en el resto.")
    legitimos = load_casos_legitimos(escenario)
    casos = legitimos["tipo_caso"].value_counts() if not legitimos.empty else pd.Series(dtype=int)
    st.dataframe(pd.DataFrame([{"Tipo": tipo, "Qué ocurre": descripcion, "En los datos": int(casos.get(tipo, 0))}
                               for tipo, descripcion in CATALOGO_LEGITIMOS.items()]),
                 use_container_width=True, hide_index=True)
    st.caption("No son anomalías: sirven para medir cuántas falsas alarmas produce cada regla.")
