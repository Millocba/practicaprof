"""Detección por reglas y evaluación contra el ground truth."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

from ayudas import seccion  # noqa: E402
from data_loader import (  # noqa: E402
    NOMBRES_ESCENARIO,
    asegurar_datos_maestro,
    load_dataset_deteccion,
    selector_escenario,
)
from deteccion.evaluacion import errores, evaluar_por_regla, evaluar_por_tipo  # noqa: E402
from deteccion.reglas import ejecutar_reglas  # noqa: E402

st.set_page_config(page_title="Detección y evaluación", page_icon="🎯", layout="wide")

seccion(
    "🎯 Detección por reglas y evaluación", nivel=1,
    ayuda="Esta página es el corazón metodológico del proyecto. Primero se ejecutan las reglas "
          "sobre las entidades generadas; después se compara lo que encontraron con el ground "
          "truth, que es la lista de anomalías que el generador inyectó a propósito. Conviene "
          "separar las dos ideas: **detectar** es concluir que algo parece anómalo; **evaluar** "
          "es medir si eso era cierto. Un F1 alto en un escenario donde las reglas se "
          "escribieron contra el mismo generador no dice nada sobre cómo se comportarían con "
          "datos reales.")
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
             facturacion, facturacion_detalle):
    alertas = ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                              facturacion_detalle)
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
                                        datos["facturacion"], datos["facturacion_detalle"])

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
col1.metric("Transacciones analizadas", f"{len(consumo):,}",
            help="Cargas de combustible que entraron al análisis. Es el denominador de todas "
                 "las tasas de esta página: un recall del 80% significa que de cada 100 "
                 "transacciones se detectaron 80, no que se detectaron 80 de 10.")
col2.metric("Anomalías en el ground truth", f"{len(ground_truth):,}",
            help="Anomalías que el generador inyectó a propósito y dejó anotadas. Son la verdad "
                 "de referencia: ninguna regla las ve, solo se usan para medir después.")
col3.metric("Alertas emitidas", f"{len(alertas):,}",
            help="Filas que produjo el conjunto de reglas. Suele ser mayor que la cantidad de "
                 "anomalías porque varias reglas pueden marcar la misma carga, y porque cada "
                 "regla puede tener falsos positivos.")
col4.metric("Reglas", por_regla["regla"].nunique(),
            help="Reglas que corrieron con los datos disponibles. El número depende del "
                 "escenario: en el realista hay reglas con contexto que en el didáctico no "
                 "tienen las fuentes que necesitan.")

formato = {"precision": "{:.1%}", "recall": "{:.1%}", "f1": "{:.3f}"}

seccion(
    "Resultados por tipo de anomalía",
    "Cada fila agrupa **todas las reglas que detectan el mismo tipo de anomalía**, por eso hay "
    "menos filas que reglas. Las columnas son: **TP**, anomalías reales que se detectaron; "
    "**FP**, alertas que no correspondían; **FN**, anomalías que se pasaron. La precisión "
    "responde «de lo que marqué, ¿cuánto era cierto?» y el recall «de lo que había, "
    "¿cuánto encontré?». Ojo: un F1 alto aquí no prueba nada sobre datos reales, porque las "
    "reglas se escribieron conociendo cómo el generador inyecta cada anomalía.")
st.caption("Cuando varias reglas detectan el mismo tipo, se cuentan juntas.")
st.dataframe(por_tipo.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

seccion(
    "Resultados por regla",
    "La misma medición pero una fila por regla, que es el nivel en el que se puede actuar: "
    "aquí se ve qué regla concreta falla y por qué. Una regla puede tener recall bajo porque "
    "detecta poco, o precisión baja porque marca de más. Fijate en **FN** para decidir a quién "
    "le conviene revisar primero.")
if legitimos is not None:
    st.caption("Falsos positivos por origen: **legítimos** (casos reales que parecen anomalía), "
               "**otra anomalía** (sí hay algo raro, pero de otro tipo) y **normales**.")
st.dataframe(por_regla.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

# H2: umbral general vs historial del vehículo
seccion(
    "H2 — Saltos de odómetro: umbral general vs. historial del vehículo",
    "Compara tres reglas sobre la misma anomalía, de la más simple a la más informada. El "
    "**umbral fijo** dice «si entre dos cargas pasó mucho tiempo y muchos kilómetros, es raro», "
    "pero no distingue un camión de una moto. El **historial del vehículo** compara cada carga "
    "con el ritmo habitual de ese vehículo en particular, y por eso encuentra los saltos que "
    "aparecen entre cargas muy espaciadas. La tercera agrega el descarte del error de tipeo y "
    "el cruce con el GPS. Es la demostración de que *un umbral general no alcanza: el contexto "
    "del vehículo vale más que el promedio de la flota*.")
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
seccion(
    "🔎 Inspeccionar errores",
    "Acá se baja del número agregado a los registros concretos, que es donde se entiende por "
    "qué una regla falla. Elegí una regla y vas a ver sus **falsos positivos** (lo que marcó y "
    "no era anomalía) y sus **falsos negativos** (la anomalía que se le pasó). En la columna "
    "**origen** de los falsos positivos se distingue el caso: si dice `normal`, la regla está "
    "inventando; si dice un caso legítimo como `VIAJE_LARGO`, la regla funciona pero el "
    "concepto de anomalía es demasiado crudo. El selector pone arriba las reglas que tienen "
    "errores, para no tener que buscarlas.")
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
