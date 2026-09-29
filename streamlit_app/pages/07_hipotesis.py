"""Contraste de las hipótesis del escenario realista.

Qué muestra esta página
-----------------------
Una hipótesis es una idea a comprobar sobre cómo detectar mejor una irregularidad; por ejemplo,
"comparar cada carga con el historial del propio vehículo detecta más saltos de odómetro que un
umbral igual para todos". Cada hipótesis tiene al menos dos reglas:

- la regla ingenua: la primera que se le ocurriría a cualquiera (por ejemplo, "más litros que el
  tanque");
- la regla con contexto: la misma idea, pero usando otras fuentes para descartar explicaciones
  normales (historial del vehículo, estado de la flota, GPS, solicitudes, detalle de facturación).

La página mide las dos reglas contra el ground truth (las anomalías que el generador inyectó) y da
un veredicto calculado: la hipótesis "se sostiene" si la regla con contexto mejora el F1 (medida
de acierto entre 0 y 1) en al menos un mínimo fijado. Para cada hipótesis muestra además el
detalle de errores, de dónde vienen las falsas alarmas y ejemplos concretos.

Para qué la usa quien audita
----------------------------
Para justificar con números qué fuentes de información vale la pena cruzar: si sumar contexto
reduce las falsas alarmas sin perder anomalías, conviene pedir y cruzar esos datos.

Cómo encaja en la app
---------------------
Siempre usa el escenario realista (el único que tiene casos legítimos que se confunden con
anomalías), sin importar lo elegido en la barra lateral. La página Análisis por hipótesis muestra
las mismas hipótesis sin ground truth y la página Detección evalúa regla por regla.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Se agregan a la ruta de búsqueda de Python la carpeta `utils` de la app y la raíz del repositorio,
# para poder importar `data_loader` (carga de datos) y el paquete `deteccion` (reglas e hipótesis).
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
from tarjetas import tarjeta  # noqa: E402
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
# Tarjeta de marco rosa que explica esta página en palabras simples (textos en utils/tarjetas.py)
tarjeta("hipotesis")
st.markdown(
    "Cada hipótesis compara una **regla ingenua** (la primera que se le ocurriría a cualquiera) "
    "con una **regla con contexto** (historial del vehículo, estado de la flota, GPS, solicitudes, detalle "
    "de facturación). La hipótesis "
    f"**se sostiene** si la regla con contexto mejora el F1 en al menos {MEJORA_MINIMA_F1:.2f}. "
    "El veredicto se calcula con los datos, no está escrito a mano."
)

# Recordatorio de Streamlit: el archivo entero se vuelve a ejecutar de arriba a abajo en cada
# interacción. Acá el escenario está fijo en "realista" (no se usa el selector de la barra lateral);
# se generan los datos si faltan y se cargan. Sin cargas o sin casos legítimos, la página se detiene.
ESCENARIO = "realista"
asegurar_datos_maestro(ESCENARIO)
datos = load_dataset_deteccion(ESCENARIO)
if datos["consumo"].empty or datos["casos_legitimos"] is None:
    st.error("❌ No hay datos del escenario realista. Generalos desde la página Generador.")
    st.stop()
st.caption("Esta página siempre usa el escenario **Realista**: las hipótesis tratan de casos legítimos "
           f"que se confunden con anomalías (semilla {load_maestro_metadata(ESCENARIO).get('seed', '—')}).")


# `@st.cache_data` guarda el resultado en memoria para no repetir el cálculo en cada re-ejecución
# de la página mientras los datos sean los mismos.
@st.cache_data
def calcular(flota, consumo, ground_truth, legitimos, estaciones, telemetria_diaria, solicitudes,
             facturacion, facturacion_detalle):
    """Corre las reglas y contrasta cada hipótesis contra el ground truth.

    Devuelve:
    - `alertas`: qué regla marcó qué registro.
    - `detalle`: una fila por regla de cada hipótesis, con sus aciertos, errores, precisión, recall
      y F1, y el origen de sus falsos positivos.
    - `veredictos`: una fila por hipótesis con el F1 de la regla ingenua, el de la regla con
      contexto y si la hipótesis se sostiene o no.
    """
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
# Tres indicadores lado a lado (`st.columns(3)` divide el ancho en tres columnas). El del medio muestra
# cuántas falsas alarmas por casos legítimos había con las reglas ingenuas y cuántas quedan con contexto.
sostenidas = (veredictos["veredicto"] == "Se sostiene").sum()
col1, col2, col3 = st.columns(3)
col1.metric("Hipótesis que se sostienen", f"{sostenidas} de {len(veredictos)}")
col2.metric("Falsas alarmas por casos legítimos",
            f"{int(veredictos['fp_legitimos_ingenua'].sum())} → {int(veredictos['fp_legitimos_contexto'].sum())}",
            help="Suma sobre todas las hipótesis: regla ingenua → regla con contexto. "
                 "En H9 se cuentan facturas; en las demás, cargas.")
col3.metric("Casos legítimos en el dataset", f"{legitimos['id_registro'].nunique():,}")

# Tabla de veredictos con nombres de columna legibles. Recordatorio de métricas: la precisión es qué
# parte de lo marcado era cierto; el recall, qué parte de las anomalías reales se encontró; el F1
# combina ambas en un número entre 0 y 1 que solo es alto si las dos lo son.
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

# Gráfico de barras: F1 de la regla ingenua contra F1 de la regla con contexto, para cada hipótesis.
# Si una regla no tiene F1 calculable, se dibuja como 0.
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
# Tabla de búsqueda: dado el id de un registro legítimo, qué tipo de caso es.
caso_legitimo = legitimos.drop_duplicates("id_registro").set_index("id_registro")

facturas = datos["facturacion"]
lineas = datos["facturacion_detalle"]
# Un bloque desplegable (`st.expander`) por hipótesis. Se saltean las hipótesis del catálogo general
# que no tienen veredicto en este escenario.
for h in HIPOTESIS:
    if h["codigo"] not in set(veredictos["hipotesis"]):
        continue
    fila = veredictos.set_index("hipotesis").loc[h["codigo"]]
    icono = "✅" if fila["veredicto"] == "Se sostiene" else "❌"
    with st.expander(f"{icono} {h['codigo']} — {h['titulo']}: {fila['veredicto']}"):
        st.markdown(f"**Hipótesis.** {h['enunciado']}")
        st.markdown(f"**Contexto que aporta:** {h['contexto']}. **Anomalías evaluadas:** "
                    + ", ".join(f"`{t}`" for t in h["tipos"]))
        # Tabla de la hipótesis: una fila por regla, con reales (anomalías que había), tp (aciertos),
        # fp (falsas alarmas), fn (anomalías que se escaparon), las métricas y el origen de las fp.
        d = detalle[detalle["hipotesis"] == h["codigo"]][
            ["regla", "descripcion", "reales", "tp", "fp", "fn", "precision", "recall", "f1",
             "fp_legitimos", "fp_otra_anomalia", "fp_normales"]]
        st.dataframe(d.style.format(formato, na_rep="—"), use_container_width=True, hide_index=True)

        # Gráfico de las falsas alarmas de cada regla según su origen (solo si hay alguna).
        origen = d.melt(id_vars="regla", value_vars=["fp_legitimos", "fp_otra_anomalia", "fp_normales"],
                        var_name="Origen", value_name="Falsos positivos")
        origen["Origen"] = origen["Origen"].map({"fp_legitimos": "Caso legítimo",
                                                 "fp_otra_anomalia": "Otra anomalía",
                                                 "fp_normales": "Carga normal"})
        if origen["Falsos positivos"].sum() > 0:
            fig = px.bar(origen, x="regla", y="Falsos positivos", color="Origen", height=300,
                         labels={"regla": ""})
            st.plotly_chart(fig, use_container_width=True)

        # Ejemplos concretos. `h["reglas"]` va de la regla ingenua (primera) a la de más contexto
        # (última). Cada una puede ser un nombre de regla o una lista de nombres; se normalizan a
        # listas para poder filtrar las alertas con `isin`. `reales` son los ids de las anomalías
        # inyectadas de los tipos que evalúa esta hipótesis.
        ingenua = describir_regla(h["reglas"][0][0])
        contexto = describir_regla(h["reglas"][-1][0])
        reglas_ingenua = h["reglas"][0][0] or []
        reglas_contexto = h["reglas"][-1][0]
        reglas_ingenua = [reglas_ingenua] if isinstance(reglas_ingenua, str) else reglas_ingenua
        reglas_contexto = [reglas_contexto] if isinstance(reglas_contexto, str) else reglas_contexto
        reales = set(ground_truth.loc[ground_truth["tipo_anomalia"].isin(h["tipos"]), "id_registro"])
        # Hipótesis de facturación: se trabaja con facturas y líneas en lugar de cargas. Se buscan
        # facturas que la regla ingenua marca sin tener irregularidades, y se explica por qué (un
        # ajuste documentado o un desfase de corte entre períodos, ambos casos legítimos).
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
        # Hipótesis sobre cargas: ejemplos de casos legítimos que la regla ingenua marca por error y
        # de anomalías reales que la regla con contexto sí encuentra.
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
