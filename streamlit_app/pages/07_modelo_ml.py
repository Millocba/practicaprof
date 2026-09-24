"""Isolation Forest comparado con la línea base de reglas."""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

from data_loader import (  # noqa: E402
    asegurar_datos_maestro,
    load_consumo_maestro,
    load_flota,
    load_ground_truth_maestro,
    load_maestro_metadata,
)
from deteccion.modelo import (  # noqa: E402
    TIPOS_COMPORTAMIENTO,
    VARIABLES,
    comparar_con_reglas,
    ids_con_anomalia_de_comportamiento,
)

st.set_page_config(page_title="Modelo de ML", page_icon="🤖", layout="wide")

st.markdown("# 🤖 Isolation Forest vs. reglas")
st.markdown(
    "Modelo **no supervisado**: aprende qué es habitual sin ver ninguna etiqueta y marca "
    "las transacciones que se apartan. Se compara con la línea base de reglas sobre las "
    "anomalías de comportamiento: exceso volumétrico (H3a) y odómetro (H2)."
)

asegurar_datos_maestro()
flota = load_flota()
consumo = load_consumo_maestro()
ground_truth = load_ground_truth_maestro()
seed = int(load_maestro_metadata().get("seed", 42))

if flota.empty or consumo.empty or ground_truth.empty:
    st.error("❌ No hay datos con ground truth. Ejecutá el Generador y volvé a esta página.")
    st.stop()


@st.cache_data
def calcular(flota, consumo, ground_truth, seed):
    return comparar_con_reglas(flota, consumo, ground_truth, seed=seed)


comparacion, por_tipo, resultados = calcular(flota, consumo, ground_truth, seed)

with st.expander("Variables del modelo y criterio de corte", expanded=False):
    st.markdown("\n".join(f"- **{k}**: {v}" for k, v in VARIABLES.items()))
    st.markdown(
        "- El umbral es el de `contamination='auto'`: no se ajusta con la cantidad real de "
        "anomalías, porque eso usaría el ground truth.\n"
        "- La **precisión promedio** resume el ranking de puntajes sin depender de ningún umbral."
    )

st.markdown("## Comparación")
formato = {"precision": "{:.1%}", "recall": "{:.1%}", "f1": "{:.3f}", "precision_promedio": "{:.3f}"}
st.dataframe(
    comparacion[["metodo", "tp", "fp", "fn", "precision", "recall", "f1", "precision_promedio"]]
    .style.format(formato, na_rep="—"),
    use_container_width=True, hide_index=True,
)

st.markdown("## Recall por tipo de anomalía")
fig = px.bar(por_tipo, x="tipo_anomalia", y="recall", color="metodo", barmode="group",
             range_y=[0, 1.05], text_auto=".0%",
             labels={"tipo_anomalia": "", "recall": "Recall", "metodo": "Método"})
fig.update_layout(yaxis_tickformat=".0%", height=380)
st.plotly_chart(fig, use_container_width=True)

st.markdown("## Distribución del puntaje de anomalía")
st.caption("La etiqueta real se usa solo para colorear el gráfico; el modelo no la ve.")
reales = ids_con_anomalia_de_comportamiento(ground_truth)
resultados["Etiqueta real"] = resultados["id"].isin(reales).map(
    {True: "Anomalía de comportamiento", False: "Normal"})
fig = px.histogram(resultados, x="puntaje_if", color="Etiqueta real", nbins=60, barmode="overlay",
                   opacity=0.7, labels={"puntaje_if": "Puntaje (más alto = más anómalo)"})
fig.update_layout(height=380, yaxis_title="Transacciones")
st.plotly_chart(fig, use_container_width=True)

st.markdown("## Lectura")
ratio_exceso = por_tipo.set_index(["tipo_anomalia", "metodo"]).loc[
    ("EXCESO_VOLUMETRICO", "Isolation Forest"), "recall"]
st.markdown(
    f"- Las **reglas** conocen cómo se inyectan las anomalías sintéticas, por eso son perfectas: "
    "sirven como techo de referencia, no como resultado esperable con datos reales.\n"
    f"- **Isolation Forest** encuentra las anomalías de odómetro, que son casos aislados, pero "
    f"solo el {ratio_exceso:.0%} de los excesos volumétricos: cada vehículo con exceso carga de "
    "más en todas sus transacciones y forma un grupo denso que deja de verse raro "
    "(*efecto de enmascaramiento*).\n"
    "- Combinar reglas con un modelo no supervisado permite cubrir patrones que ninguna regla "
    "anticipó, a cambio de revisar más falsos positivos."
)

tipos = ", ".join(TIPOS_COMPORTAMIENTO)
st.caption(f"Semilla del modelo: {seed}. Tipos evaluados: {tipos}.")
