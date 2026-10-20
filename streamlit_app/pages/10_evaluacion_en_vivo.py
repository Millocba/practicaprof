"""Evaluación en vivo: regla ingenua, regla con contexto y modelos baseline sobre una hipótesis por carga."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

from ayudas import seccion  # noqa: E402
from explicaciones import explicar  # noqa: E402
from deteccion import baseline  # noqa: E402
from deteccion.hipotesis import HIPOTESIS  # noqa: E402
from deteccion.modelo import VARIABLES, VARIABLES_CONTEXTO  # noqa: E402

st.set_page_config(page_title="Evaluación en vivo", page_icon="📏", layout="wide")

TITULOS = {h["codigo"]: h["titulo"] for h in HIPOTESIS}


@st.cache_data(show_spinner=False)
def _evaluar(hipotesis, n_flota, n_arboles, excluir):
    return baseline.evaluar(hipotesis, n_flota=n_flota, n_arboles=n_arboles, excluir=list(excluir))


@st.cache_data(show_spinner=False)
def _explicar(hipotesis, n_flota, n_arboles, excluir):
    return baseline.explicar(hipotesis, n_flota=n_flota, n_arboles=n_arboles, excluir=list(excluir))


seccion(
    "📏 Evaluación en vivo: ¿regla o modelo?", nivel=1,
    ayuda="Entrena y evalúa, en el momento, la regla ingenua, la regla con contexto y tres modelos "
          "(Isolation Forest, regresión logística y Random Forest) sobre la hipótesis que elijas. "
          "Los modelos se entrenan con tres semillas y se evalúan con otras cinco, distintas. La "
          "etiqueta real solo se usa para medir, nunca como variable. Un modelo que ve las variables "
          "que definen la regla aprende la regla; por eso cada modelo se corre dos veces: con todas las "
          "variables y sin las de la regla.")
explicar("evaluacion")
st.warning("⚠️ Todo es **sintético**. Las métricas comparan métodos y comprueban el procedimiento, pero no "
           "miden el desempeño sobre datos reales: la prevalencia sintética es mayor y las etiquetas salen "
           "de reglas conocidas del generador.")

izquierda, derecha = st.columns(2)
hipotesis = izquierda.selectbox("Hipótesis", baseline.HIPOTESIS_POR_CARGA, index=baseline.HIPOTESIS_POR_CARGA.index("H3b"),
                                format_func=lambda h: f"{h} · {TITULOS[h]}")
excluir = derecha.multiselect(
    "Variables que se quitan en el segundo escenario (las que definen la regla)",
    list(VARIABLES) + list(VARIABLES_CONTEXTO), default=list(baseline.VARIABLES_DE_LA_REGLA.get(hipotesis, ())), key=f"excluir_{hipotesis}")
izquierda, derecha = st.columns(2)
n_flota = izquierda.slider("Vehículos por semilla", 30, 200, 40, step=10,
                           help="Más vehículos dan resultados más estables y tardan más. La evaluación "
                                "completa del informe usa 200.")
n_arboles = derecha.slider("Árboles del Random Forest", 20, 300, 50, step=10)
con_variables = st.checkbox("Mostrar qué variables sostienen al modelo (tarda más)")

if st.button("▶️ Ejecutar evaluación", type="primary"):
    st.session_state["evaluacion_en_vivo"] = (hipotesis, n_flota, n_arboles, tuple(excluir), con_variables)

pedido = st.session_state.get("evaluacion_en_vivo")
if not pedido:
    st.info("Elegí una hipótesis y ejecutá. Con 40 vehículos por semilla tarda un par de minutos; el "
            "resultado queda guardado mientras no cambies los parámetros.")
    st.stop()

hipotesis, n_flota, n_arboles, excluir, con_variables = pedido
with st.spinner(f"Generando 8 flotas sintéticas y evaluando {hipotesis}…"):
    resultado = _evaluar(hipotesis, n_flota, n_arboles, excluir)

metodos = resultado["metodos"]
if not metodos:
    st.error("Con estos parámetros no hay anomalías de esta hipótesis para entrenar. Probá con más vehículos.")
    st.stop()

st.markdown(f"### {hipotesis} · {TITULOS[hipotesis]}")
st.caption(f"{resultado['anomalias_en_evaluacion']} anomalías en la evaluación · umbral fijo {resultado['umbral']} · "
           f"diseño {resultado['semillas_de_diseno']} · evaluación {resultado['semillas_de_evaluacion']} · "
           f"variables quitadas: {', '.join(resultado['variables_excluidas']) or 'ninguna'}")

tarjetas = st.columns(3)
for columna, (metodo, titulo) in zip(tarjetas, [("linea_base_ingenua", "F1 línea base ingenua"),
                                               ("regla_con_contexto", "F1 regla con contexto"),
                                               ("random_forest__sin_las_de_la_regla", "F1 Random Forest sin las de la regla")]):
    if metodo in metodos:
        columna.metric(titulo, f"{metodos[metodo]['f1']:.2f}")

tabla = pd.DataFrame([{
    "Método": baseline.ETIQUETAS.get(m, m), "Precisión": v["precision"], "Recall": v["recall"], "F1": v["f1"],
    "F1 por semilla (media)": v["f1_media"], "Desvío": v["f1_desvio"], "Precisión promedio": v["ap_media"],
    "Precisión en las primeras k": v["precision_en_k_media"],
    "TP": v["tp"], "FP": v["fp"], "FN": v["fn"], "TN": v["tn"]} for m, v in metodos.items()])
figura = px.bar(tabla, x="F1", y="Método", orientation="h", range_x=[0, 1], text=tabla["F1"].map("{:.2f}".format))
figura.update_layout(yaxis={"categoryorder": "total ascending"}, height=380, margin={"l": 0, "r": 0, "t": 10, "b": 0})
st.plotly_chart(figura, use_container_width=True)
st.dataframe(tabla.style.format({c: "{:.2f}" for c in tabla.columns[1:8]}), use_container_width=True, hide_index=True)

st.markdown(
    "**Cómo leerla.** Si el Random Forest con todas las variables llega a 1,00 pero cae sin las de la regla, "
    "no encontró una señal nueva: aprendió la regla. La comparación que importa es la regla con contexto "
    "contra la línea base ingenua; una hipótesis se sostiene si la mejora de F1 es de al menos 0,10. "
    "Los falsos negativos (FN) son lo caro: no se puede dejar pasar una carga.")

if con_variables:
    with st.spinner("Calculando la importancia de cada variable…"):
        explicacion = _explicar(hipotesis, n_flota, n_arboles, excluir)
    st.markdown("### Qué variables sostienen al modelo (sin las de la regla)")
    st.markdown(baseline.explicar_a_markdown(explicacion))
