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
    NOMBRES_ESCENARIO,
    asegurar_datos_maestro,
    load_dataset_deteccion,
    selector_escenario,
)
from deteccion.evaluacion import errores, evaluar_por_regla, evaluar_por_tipo  # noqa: E402
from deteccion.reglas import ejecutar_reglas  # noqa: E402

st.set_page_config(page_title="Detección y evaluación", page_icon="🎯", layout="wide")

st.markdown("# 🎯 Detección por reglas y evaluación")
st.markdown(
    "Las reglas analizan solo las entidades generadas; después sus alertas se comparan "
    "con el **ground truth** (las anomalías que inyectó el generador)."
)

escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
flota, consumo, ground_truth = datos["flota"], datos["consumo"], datos["ground_truth"]
legitimos = datos["casos_legitimos"]

if flota.empty or consumo.empty or ground_truth.empty:
    st.error("❌ No hay datos con ground truth. Ejecutá el Generador y volvé a esta página.")
    st.stop()


@st.cache_data
def calcular(flota, consumo, ground_truth, estaciones, telemetria_diaria, legitimos, solicitudes,
             facturacion, facturacion_detalle, contratos=None, transferencias=None):
    alertas = ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                              facturacion_detalle, contratos=contratos, transferencias=transferencias)
    por_regla = evaluar_por_regla(alertas, ground_truth)
    if legitimos is not None:
        ids_legitimos = set(legitimos["id_registro"])
        ids_anomalos = set(ground_truth["id_registro"])
        origen = []
        for fila in por_regla.itertuples():
            gt_tipo = ground_truth[ground_truth["tipo_anomalia"] == fila.tipo_anomalia]
            if fila.tipo_anomalia == "VALOR_NULO":
                gt_tipo = gt_tipo[gt_tipo["columna"] == fila.regla.removeprefix("nulo_")]
            fp, _ = errores(alertas, gt_tipo, fila.tipo_anomalia, filtro_regla=[fila.regla])
            ids = set(fp["id_registro"])
            origen.append({"fp_legitimos": len(ids & ids_legitimos),
                           "fp_otra_anomalia": len((ids - ids_legitimos) & ids_anomalos),
                           "fp_normales": len(ids - ids_legitimos - ids_anomalos)})
        por_regla = pd.concat([por_regla, pd.DataFrame(origen)], axis=1)
    return alertas, evaluar_por_tipo(alertas, ground_truth), por_regla


alertas, por_tipo, por_regla = calcular(flota, consumo, ground_truth, datos["estaciones"],
                                        datos["telemetria_diaria"], legitimos, datos["solicitudes"],
                                        datos["facturacion"], datos["facturacion_detalle"],
                                        datos["contratos"], datos["transferencias"])

if escenario == "didactico":
    st.warning(
        "⚠️ **Escenario didáctico.** Las anomalías son inconfundibles y las reglas se diseñaron "
        "conociendo cómo se inyectan, por eso muchas alcanzan precisión y recall perfectos. Eso "
        "valida el circuito de detección y evaluación. Para ver reglas que fallan ante casos "
        "legítimos, elegí el escenario **Realista** en la barra lateral."
    )
else:
    st.info(
        "ℹ️ **Escenario realista.** Hay casos legítimos que se parecen a anomalías (tanques no "
        "registrados, viajes largos, odómetros reemplazados, errores de tipeo). La tabla por regla "
        "separa los falsos positivos según su origen. El contraste de cada hipótesis está en la "
        "página **Hipótesis**."
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
if legitimos is not None:
    st.caption("Falsos positivos por origen: **legítimos** (casos reales que parecen anomalía), "
               "**otra anomalía** (sí hay algo raro, pero de otro tipo) y **normales**.")
st.dataframe(por_regla.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

# H2: umbral general vs historial del vehículo
st.markdown("## H2 — Saltos de odómetro: umbral general vs. historial del vehículo")
saltos = por_regla[por_regla["tipo_anomalia"] == "ODOMETRO_SALTO"].copy()
if not saltos.empty:
    etiquetas = {
        "salto_umbral_fijo": "Umbral fijo (>500 km en ≤7 días)",
        "salto_historial_vehiculo": "Historial del vehículo (>1000 km sobre lo habitual)",
        "salto_con_contexto": "Historial + tipeo + GPS",
    }
    saltos["Regla"] = saltos["regla"].map(etiquetas).fillna(saltos["regla"])
    largo = saltos.melt(id_vars="Regla", value_vars=["precision", "recall"],
                        var_name="Métrica", value_name="Valor")
    fig = px.bar(largo, x="Regla", y="Valor", color="Métrica", barmode="group",
                 range_y=[0, 1.05], text_auto=".0%")
    fig.update_layout(yaxis_tickformat=".0%", xaxis_title=None, height=380)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        "El umbral fijo solo encuentra los saltos que ocurren en pocos días (y, con uso realista, "
        "marca a los vehículos que recorren mucho). Comparar cada carga con el ritmo habitual del "
        "propio vehículo detecta también los saltos entre cargas espaciadas: es la hipótesis de que "
        "*el historial individual es más informativo que un umbral general*."
    )

# Inspección de errores
st.markdown("## 🔎 Inspeccionar errores")
conteo = por_regla.groupby("regla")[["fp", "fn"]].sum()
opciones = sorted(conteo.index, key=lambda r: (conteo.loc[r].sum() == 0, r))
col1, col2 = st.columns(2)
with col1:
    regla_sel = st.selectbox(
        "Regla (las que tienen errores aparecen primero)", opciones, key="regla_errores",
        format_func=lambda r: f"{r}  ({conteo.loc[r, 'fp']} FP / {conteo.loc[r, 'fn']} FN)",
    )
tipos_sel = por_regla.loc[por_regla["regla"] == regla_sel, "tipo_anomalia"].tolist()
columnas = ["id", "vehiculo_id", "dominio", "fecha", "estacion", "litros", "odometro"]
bloques_fp, bloques_fn = [], []
for tipo_sel in tipos_sel:
    gt_tipo = ground_truth
    if tipo_sel == "VALOR_NULO":
        gt_tipo = ground_truth[ground_truth["columna"] == regla_sel.removeprefix("nulo_")]
    fp, fn = errores(alertas, gt_tipo, tipo_sel, filtro_regla=[regla_sel])
    bloques_fp.append(fp)
    bloques_fn.append(fn)
fp, fn = pd.concat(bloques_fp), pd.concat(bloques_fn)
with col2:
    st.metric("Falsos positivos / falsos negativos", f"{len(fp)} / {len(fn)}")

if fp.empty and fn.empty:
    st.success(f"✅ `{regla_sel}` no tiene errores en este dataset.")
else:
    detalle_factura = datos["facturacion_detalle"]
    if detalle_factura is not None and fp["id_registro"].str.startswith(("LIN-", "FAC-")).any():
        columnas_linea = ["numero_linea", "numero_factura", "referencia_consumo", "concepto", "fecha",
                          "litros", "precio_unitario", "importe"]
        consumo_o_factura = detalle_factura[columnas_linea].rename(columns={"numero_linea": "id"})
        columnas = ["id"] + columnas_linea[1:]
    else:
        consumo_o_factura = consumo
    if not fp.empty:
        st.markdown("**Falsos positivos** (alertas que no corresponden a una anomalía de ese tipo)")
        tabla = fp.merge(consumo_o_factura[columnas], left_on="id_registro", right_on="id", how="left")
        if legitimos is not None:
            caso = legitimos.drop_duplicates("id_registro").set_index("id_registro")["tipo_caso"]
            anomalia = ground_truth.groupby("id_registro")["tipo_anomalia"].first()
            tabla.insert(0, "origen", tabla["id_registro"].map(caso).fillna(
                tabla["id_registro"].map(anomalia).radd("otra anomalía: ")).fillna("normal"))
        st.dataframe(tabla, use_container_width=True, hide_index=True)
    if not fn.empty:
        st.markdown("**Falsos negativos** (anomalías inyectadas que la regla no detectó)")
        st.dataframe(fn.merge(consumo_o_factura[columnas], left_on="id_registro", right_on="id", how="left"),
                     use_container_width=True, hide_index=True)

st.caption(f"Escenario: {NOMBRES_ESCENARIO[escenario]}.")
