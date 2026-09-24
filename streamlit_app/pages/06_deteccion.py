"""Detección por reglas y evaluación contra el ground truth."""
import sys
from pathlib import Path

import pandas as pd
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
)
from deteccion.evaluacion import errores, evaluar_por_regla, evaluar_por_tipo  # noqa: E402
from deteccion.reglas import ejecutar_reglas  # noqa: E402

st.set_page_config(page_title="Detección y evaluación", page_icon="🎯", layout="wide")

st.markdown("# 🎯 Detección por reglas y evaluación")
st.markdown(
    "Las reglas analizan solo las entidades generadas; después sus alertas se comparan "
    "con el **ground truth** (las anomalías que inyectó el generador)."
)

asegurar_datos_maestro()
flota = load_flota()
consumo = load_consumo_maestro()
ground_truth = load_ground_truth_maestro()

if flota.empty or consumo.empty or ground_truth.empty:
    st.error("❌ No hay datos con ground truth. Ejecutá el Generador y volvé a esta página.")
    st.stop()


@st.cache_data
def calcular(flota, consumo, ground_truth):
    alertas = ejecutar_reglas(flota, consumo)
    return alertas, evaluar_por_tipo(alertas, ground_truth), evaluar_por_regla(alertas, ground_truth)


alertas, por_tipo, por_regla = calcular(flota, consumo, ground_truth)

st.warning(
    "⚠️ **Cómo leer estos resultados.** Las anomalías son sintéticas y las reglas se "
    "diseñaron conociendo cómo se inyectan, por eso muchas alcanzan precisión y recall "
    "perfectos. Eso valida el circuito de detección y evaluación, no el desempeño esperable "
    "con datos reales."
)

# KPIs
col1, col2, col3, col4 = st.columns(4)
col1.metric("Transacciones analizadas", f"{len(consumo):,}")
col2.metric("Anomalías en el ground truth", f"{len(ground_truth):,}")
col3.metric("Alertas emitidas", f"{len(alertas):,}")
col4.metric("Reglas", por_regla["regla"].nunique())

formato = {"precision": "{:.1%}", "recall": "{:.1%}", "f1": "{:.3f}"}

st.markdown("## Resultados por tipo de anomalía")
st.caption("Cuando varias reglas detectan el mismo tipo, se cuentan juntas.")
st.dataframe(por_tipo.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

st.markdown("## Resultados por regla")
st.dataframe(por_regla.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

# H2: umbral general vs historial del vehículo
st.markdown("## H2 — Saltos de odómetro: umbral general vs. historial del vehículo")
saltos = por_regla[por_regla["tipo_anomalia"] == "ODOMETRO_SALTO"].copy()
if not saltos.empty:
    etiquetas = {
        "salto_umbral_fijo": "Umbral fijo (>500 km en ≤7 días)",
        "salto_historial_vehiculo": "Historial del vehículo (>1000 km sobre lo habitual)",
    }
    saltos["Regla"] = saltos["regla"].map(etiquetas).fillna(saltos["regla"])
    largo = saltos.melt(id_vars="Regla", value_vars=["precision", "recall"],
                        var_name="Métrica", value_name="Valor")
    fig = px.bar(largo, x="Regla", y="Valor", color="Métrica", barmode="group",
                 range_y=[0, 1.05], text_auto=".0%")
    fig.update_layout(yaxis_tickformat=".0%", xaxis_title=None, height=380)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        "El umbral fijo solo encuentra los saltos que ocurren en pocos días. Comparar cada "
        "carga con el ritmo habitual del propio vehículo detecta también los saltos entre "
        "cargas espaciadas: es la hipótesis de que *el historial individual es más "
        "informativo que un umbral general*."
    )

# Inspección de errores
st.markdown("## 🔎 Inspeccionar errores")
col1, col2 = st.columns(2)
with col1:
    regla_sel = st.selectbox("Regla", sorted(por_regla["regla"]), key="regla_errores")
tipo_sel = por_regla.loc[por_regla["regla"] == regla_sel, "tipo_anomalia"].iloc[0]
gt_tipo = ground_truth
if tipo_sel == "VALOR_NULO":
    gt_tipo = ground_truth[ground_truth["columna"] == regla_sel.removeprefix("nulo_")]
fp, fn = errores(alertas, gt_tipo, tipo_sel, filtro_regla=[regla_sel])
with col2:
    st.metric("Falsos positivos / falsos negativos", f"{len(fp)} / {len(fn)}")

if fp.empty and fn.empty:
    st.success(f"✅ `{regla_sel}` no tiene errores en este dataset.")
else:
    columnas = ["id", "vehiculo_id", "dominio", "fecha", "litros", "odometro"]
    if not fp.empty:
        st.markdown("**Falsos positivos** (alertas que no corresponden a una anomalía inyectada)")
        st.dataframe(fp.merge(consumo[columnas], left_on="id_registro", right_on="id"),
                     use_container_width=True, hide_index=True)
    if not fn.empty:
        st.markdown("**Falsos negativos** (anomalías inyectadas que la regla no detectó)")
        st.dataframe(fn.merge(consumo[columnas], left_on="id_registro", right_on="id"),
                     use_container_width=True, hide_index=True)
