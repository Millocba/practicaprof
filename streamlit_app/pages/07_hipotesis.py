"""Contraste de las hipótesis del escenario realista."""
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
    load_dataset_deteccion,
    load_maestro_metadata,
)
from deteccion.hipotesis import HIPOTESIS, MEJORA_MINIMA_F1, contrastar_hipotesis, describir_regla  # noqa: E402
from deteccion.reglas import ejecutar_reglas  # noqa: E402

st.set_page_config(page_title="Hipótesis", page_icon="🧪", layout="wide")

st.markdown("# 🧪 Hipótesis: ¿cuánto aporta el contexto?")
st.markdown(
    "Cada hipótesis compara una **regla ingenua** (la primera que se le ocurriría a cualquiera) "
    "con una **regla con contexto** (historial del vehículo, estado de la flota, GPS, solicitudes, detalle "
    "de facturación). La hipótesis "
    f"**se sostiene** si la regla con contexto mejora el F1 en al menos {MEJORA_MINIMA_F1:.2f}. "
    "El veredicto se calcula con los datos, no está escrito a mano."
)

ESCENARIO = "realista"
asegurar_datos_maestro(ESCENARIO)
datos = load_dataset_deteccion(ESCENARIO)
if datos["consumo"].empty or datos["casos_legitimos"] is None:
    st.error("❌ No hay datos del escenario realista. Generalos desde la página Generador.")
    st.stop()
st.caption("Esta página siempre usa el escenario **Realista**: las hipótesis tratan de casos legítimos "
           f"que se confunden con anomalías (semilla {load_maestro_metadata(ESCENARIO).get('seed', '—')}).")


@st.cache_data
def calcular(flota, consumo, ground_truth, legitimos, estaciones, telemetria_diaria, solicitudes,
             facturacion, facturacion_detalle):
    alertas = ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                              facturacion_detalle)
    detalle, veredictos = contrastar_hipotesis(alertas, ground_truth, legitimos, facturacion_detalle)
    return alertas, detalle, veredictos


alertas, detalle, veredictos = calcular(datos["flota"], datos["consumo"], datos["ground_truth"],
                                        datos["casos_legitimos"], datos["estaciones"],
                                        datos["telemetria_diaria"], datos["solicitudes"],
                                        datos["facturacion"], datos["facturacion_detalle"])
consumo = datos["consumo"]
legitimos = datos["casos_legitimos"]
ground_truth = datos["ground_truth"]

# Resumen
sostenidas = (veredictos["veredicto"] == "Se sostiene").sum()
col1, col2, col3 = st.columns(3)
col1.metric("Hipótesis que se sostienen", f"{sostenidas} de {len(veredictos)}")
col2.metric("Falsas alarmas por casos legítimos",
            f"{int(veredictos['fp_legitimos_ingenua'].sum())} → {int(veredictos['fp_legitimos_contexto'].sum())}",
            help="Suma sobre todas las hipótesis: regla ingenua → regla con contexto. "
                 "En H9 se cuentan facturas; en las demás, cargas.")
col3.metric("Casos legítimos en el dataset", f"{legitimos['id_registro'].nunique():,}")

tabla = veredictos.rename(columns={
    "hipotesis": "Hipótesis", "titulo": "Tema", "veredicto": "Veredicto",
    "f1_ingenua": "F1 ingenua", "f1_contexto": "F1 con contexto",
    "fp_legitimos_ingenua": "Falsas alarmas legítimas (ingenua)",
    "fp_legitimos_contexto": "Falsas alarmas legítimas (contexto)",
    "recall_contexto": "Recall con contexto",
})
st.dataframe(tabla.style.format({"F1 ingenua": "{:.2f}", "F1 con contexto": "{:.2f}",
                                 "Recall con contexto": "{:.0%}"}, na_rep="—"),
             use_container_width=True, hide_index=True)

grafico = veredictos.melt(id_vars="hipotesis", value_vars=["f1_ingenua", "f1_contexto"],
                          var_name="Regla", value_name="F1").fillna({"F1": 0})
grafico["Regla"] = grafico["Regla"].map({"f1_ingenua": "Ingenua", "f1_contexto": "Con contexto"})
fig = px.bar(grafico, x="hipotesis", y="F1", color="Regla", barmode="group", range_y=[0, 1.05],
             text_auto=".2f", labels={"hipotesis": ""})
fig.update_layout(height=360)
st.plotly_chart(fig, use_container_width=True)

# Detalle por hipótesis
st.markdown("## Detalle por hipótesis")
formato = {"precision": "{:.0%}", "recall": "{:.0%}", "f1": "{:.2f}"}
columnas_consumo = ["id", "vehiculo_id", "fecha", "estacion", "litros", "odometro"]
caso_legitimo = legitimos.drop_duplicates("id_registro").set_index("id_registro")

facturas = datos["facturacion"]
lineas = datos["facturacion_detalle"]
for h in HIPOTESIS:
    if h["codigo"] not in set(veredictos["hipotesis"]):
        continue
    fila = veredictos.set_index("hipotesis").loc[h["codigo"]]
    icono = "✅" if fila["veredicto"] == "Se sostiene" else "❌"
    with st.expander(f"{icono} {h['codigo']} — {h['titulo']}: {fila['veredicto']}"):
        st.markdown(f"**Hipótesis.** {h['enunciado']}")
        st.markdown(f"**Contexto que aporta:** {h['contexto']}. **Anomalías evaluadas:** "
                    + ", ".join(f"`{t}`" for t in h["tipos"]))
        d = detalle[detalle["hipotesis"] == h["codigo"]][
            ["regla", "descripcion", "reales", "tp", "fp", "fn", "precision", "recall", "f1",
             "fp_legitimos", "fp_otra_anomalia", "fp_normales"]]
        st.dataframe(d.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

        origen = d.melt(id_vars="regla", value_vars=["fp_legitimos", "fp_otra_anomalia", "fp_normales"],
                        var_name="Origen", value_name="Falsos positivos")
        origen["Origen"] = origen["Origen"].map({"fp_legitimos": "Caso legítimo",
                                                 "fp_otra_anomalia": "Otra anomalía",
                                                 "fp_normales": "Carga normal"})
        if origen["Falsos positivos"].sum() > 0:
            fig = px.bar(origen, x="regla", y="Falsos positivos", color="Origen", height=300,
                         labels={"regla": ""})
            st.plotly_chart(fig, use_container_width=True)

        ingenua = describir_regla(h["reglas"][0][0])
        contexto = describir_regla(h["reglas"][-1][0])
        reglas_ingenua = h["reglas"][0][0] or []
        reglas_contexto = h["reglas"][-1][0]
        reglas_ingenua = [reglas_ingenua] if isinstance(reglas_ingenua, str) else reglas_ingenua
        reglas_contexto = [reglas_contexto] if isinstance(reglas_contexto, str) else reglas_contexto
        reales = set(ground_truth.loc[ground_truth["tipo_anomalia"].isin(h["tipos"]), "id_registro"])
        if h.get("nivel") == "factura":
            marcadas = alertas[alertas["regla"].isin(reglas_ingenua)]
            legit_facturas = set(legitimos.loc[legitimos["tabla"] == "facturacion", "id_registro"])
            con_desfase = set(lineas.loc[lineas["numero_linea"].isin(
                legitimos.loc[legitimos["tipo_caso"] == "DESFASE_DE_CORTE", "id_registro"]), "numero_factura"])
            falsas = marcadas[~marcadas["id_registro"].isin(
                set(lineas.loc[lineas["numero_linea"].isin(reales), "numero_factura"]) | reales)]
            if not falsas.empty:
                st.markdown(f"**Facturas sin irregularidades que alerta `{ingenua}`** (ejemplos)")
                ejemplos = falsas.head(5).merge(facturas, left_on="id_registro", right_on="numero_factura")
                ejemplos.insert(0, "explicación", ejemplos["numero_factura"].map(
                    lambda f: "ajuste documentado" if f in legit_facturas
                    else "desfase de corte" if f in con_desfase else "—"))
                st.dataframe(ejemplos[["explicación", "numero_factura", "proveedor", "periodo", "total_monto",
                                       "detalle"]], use_container_width=True, hide_index=True)
            detectadas = alertas[alertas["regla"].isin(reglas_contexto) & alertas["id_registro"].isin(reales)]
            if not detectadas.empty:
                st.markdown(f"**Irregularidades que detecta la conciliación por línea** (ejemplos)")
                st.dataframe(detectadas.drop_duplicates("id_registro").head(8)[["id_registro", "tipo_anomalia",
                                                                                 "detalle"]],
                             use_container_width=True, hide_index=True)
            continue
        if reglas_ingenua:
            ids = set(alertas.loc[alertas["regla"].isin(reglas_ingenua), "id_registro"]) & set(caso_legitimo.index)
            if ids:
                st.markdown(f"**Casos legítimos que alerta `{ingenua}`** (ejemplos)")
                ejemplos = consumo[consumo["id"].isin(ids)].head(5)[columnas_consumo]
                ejemplos.insert(0, "caso", ejemplos["id"].map(caso_legitimo["tipo_caso"]))
                st.dataframe(ejemplos, use_container_width=True, hide_index=True)
        detectadas = alertas[alertas["regla"].isin(reglas_contexto) & alertas["id_registro"].isin(reales)]
        if not detectadas.empty:
            st.markdown(f"**Anomalías que detecta `{contexto}`** (ejemplos)")
            ejemplos = detectadas.drop_duplicates("id_registro").head(5).merge(
                consumo[columnas_consumo], left_on="id_registro", right_on="id")
            st.dataframe(ejemplos[["detalle"] + columnas_consumo], use_container_width=True, hide_index=True)

st.markdown("## Relación con las hipótesis del proyecto")
st.markdown(
    "- *Integrar fuentes permite detectar situaciones invisibles en análisis aislados*: H6, H7, H8 y H9 "
    "(estado de la flota, GPS, solicitudes y detalle de facturación).\n"
    "- *Los umbrales adecuados varían según el tipo de vehículo y su contexto* y *el historial "
    "individual puede ser más informativo que un umbral general*: H2c, H3b y H5.\n"
    "- *Combinar reglas, estadística robusta y ML puede reducir falsas alertas*: ver la página "
    "**Modelo de ML**.\n\n"
    "**Límite.** Las reglas con contexto se diseñaron conociendo cómo el generador crea los casos "
    "legítimos, así que miden cuánto ayuda cada fuente *bajo los supuestos del escenario*, no el "
    "desempeño esperable con datos reales."
)
