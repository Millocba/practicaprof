"""Detección por reglas y evaluación contra el ground truth.

Qué muestra esta página
-----------------------
Corre todas las reglas de detección sobre los datos y compara sus alertas con el ground truth: la
lista de anomalías que el generador de datos sintéticos inyectó a propósito. Como en este proyecto
los datos son inventados, se sabe exactamente qué registros son anómalos, y eso permite medir qué
tan bien funciona cada regla. Muestra:

- Indicadores generales (cargas analizadas, anomalías reales, alertas emitidas, cantidad de reglas).
- Resultados por tipo de anomalía y por regla, con precisión, recall y F1 (explicados más abajo).
- En el escenario realista, de dónde salen los falsos positivos: casos legítimos, otra anomalía o
  cargas normales.
- Una comparación de reglas para saltos de odómetro (hipótesis H2).
- Un explorador para ver, regla por regla, los errores concretos.

Para qué la usa quien audita
----------------------------
Para saber cuánto confiar en cada regla antes de usarla: si marca mucho de más (falsos positivos,
es decir, trabajo de revisión perdido) o si se le escapan casos (falsos negativos).

Cómo encaja en la app
---------------------
La página Análisis por hipótesis muestra lo mismo pero sin ground truth (lo que vería quien audita
con datos reales). Esta página es el "control de calidad" de las reglas. La página Hipótesis hace
una comparación parecida, pero organizada por hipótesis y siempre en el escenario realista.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Se agregan a la ruta de búsqueda de Python la carpeta `utils` de la app y la raíz del repositorio,
# para poder importar `data_loader` (carga de datos) y el paquete `deteccion` (reglas y evaluación).
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
from tarjetas import tarjeta  # noqa: E402
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
# Tarjeta de marco rosa que explica esta página en palabras simples (textos en utils/tarjetas.py)
tarjeta("deteccion")
st.markdown(
    "Las reglas analizan solo las entidades generadas; después sus alertas se comparan "
    "con el **ground truth** (las anomalías que inyectó el generador)."
)

# Recordatorio de Streamlit: todo este archivo se vuelve a ejecutar de arriba a abajo cada vez que la
# persona toca un control. Estas líneas leen el escenario elegido en la barra lateral, generan los
# datos si no existen y cargan las tablas. `casos_legitimos` solo existe en el escenario realista:
# son situaciones que parecen anomalías pero tienen explicación (por ejemplo, un viaje largo).
escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
flota, consumo, ground_truth = datos["flota"], datos["consumo"], datos["ground_truth"]
legitimos = datos["casos_legitimos"]

if flota.empty or consumo.empty or ground_truth.empty:
    st.error("❌ No hay datos con ground truth. Ejecutá el Generador y volvé a esta página.")
    st.stop()


# `@st.cache_data` guarda el resultado en memoria: mientras los datos no cambien, las re-ejecuciones
# de la página reutilizan el cálculo en lugar de volver a correr todas las reglas.
@st.cache_data
def calcular(flota, consumo, ground_truth, estaciones, telemetria_diaria, legitimos, solicitudes,
             facturacion, facturacion_detalle):
    """Corre las reglas y las evalúa contra el ground truth.

    Devuelve tres tablas:
    - `alertas`: qué regla marcó qué registro.
    - evaluación por tipo de anomalía: todas las reglas de un mismo tipo contadas juntas.
    - `por_regla`: evaluación de cada regla por separado. En el escenario realista se le agregan
      tres columnas que clasifican sus falsos positivos según su origen: caso legítimo
      (`fp_legitimos`), anomalía de otro tipo (`fp_otra_anomalia`) o carga normal (`fp_normales`).
    """
    alertas = ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                              facturacion_detalle)
    por_regla = evaluar_por_regla(alertas, ground_truth)
    if legitimos is not None:
        ids_legitimos = set(legitimos["id_registro"])
        ids_anomalos = set(ground_truth["id_registro"])
        origen = []
        for fila in por_regla.itertuples():
            # Cada regla se compara solo con las anomalías reales de su tipo. Las reglas de valores
            # vacíos (`nulo_<campo>`) se comparan además solo con los vacíos de su propio campo.
            gt_tipo = ground_truth[ground_truth["tipo_anomalia"] == fila.tipo_anomalia]
            if fila.tipo_anomalia == "VALOR_NULO":
                gt_tipo = gt_tipo[gt_tipo["columna"] == fila.regla.removeprefix("nulo_")]
            fp, _ = errores(alertas, gt_tipo, fila.tipo_anomalia, filtro_regla=[fila.regla])
            # Con operaciones de conjuntos se separan los falsos positivos: los que son casos
            # legítimos, los que son otra anomalía (y no legítimos) y el resto, que son cargas normales.
            ids = set(fp["id_registro"])
            origen.append({"fp_legitimos": len(ids & ids_legitimos),
                           "fp_otra_anomalia": len((ids - ids_legitimos) & ids_anomalos),
                           "fp_normales": len(ids - ids_legitimos - ids_anomalos)})
        por_regla = pd.concat([por_regla, pd.DataFrame(origen)], axis=1)
    return alertas, evaluar_por_tipo(alertas, ground_truth), por_regla


alertas, por_tipo, por_regla = calcular(flota, consumo, ground_truth, datos["estaciones"],
                                        datos["telemetria_diaria"], legitimos, datos["solicitudes"],
                                        datos["facturacion"], datos["facturacion_detalle"])

# Aviso según el escenario, para interpretar bien los números: en el didáctico las reglas son casi
# perfectas a propósito; en el realista aparecen falsas alarmas por casos legítimos.
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
# `st.columns(4)` divide el ancho de la página en cuatro columnas; cada `metric` es un indicador grande.
col1, col2, col3, col4 = st.columns(4)
col1.metric("Transacciones analizadas", f"{len(consumo):,}")
col2.metric("Anomalías en el ground truth", f"{len(ground_truth):,}")
col3.metric("Alertas emitidas", f"{len(alertas):,}")
col4.metric("Reglas", por_regla["regla"].nunique())

# Métricas de evaluación que aparecen en las tablas. Se parte de tres conteos:
# - tp (verdaderos positivos): alertas que sí eran una anomalía real.
# - fp (falsos positivos): alertas sobre registros que no eran esa anomalía (falsas alarmas).
# - fn (falsos negativos): anomalías reales que la regla no marcó (casos que se escaparon).
# Estos conteos son las casillas de la "matriz de confusión": una tabla de 2x2 que cruza lo que dijo
# la regla (marcó / no marcó) con la realidad (anomalía / no anomalía). La cuarta casilla, los
# verdaderos negativos (registros normales no marcados), no se usa en estas métricas.
# Con ellos:
# - precision = tp / (tp + fp): de todo lo que la regla marca, qué parte era cierta. Baja precisión
#   significa mucho tiempo de revisión gastado en falsas alarmas.
# - recall = tp / (tp + fn): de todas las anomalías reales, qué parte encuentra la regla. Bajo recall
#   significa que se escapan casos.
# - f1: un solo número entre 0 y 1 que combina precisión y recall (su media armónica). Solo es alto
#   si las dos son altas a la vez.
# Este diccionario indica cómo mostrarlas: precisión y recall como porcentaje, F1 con tres decimales.
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
    # Se reemplaza el nombre técnico de cada regla por una etiqueta legible y se reorganiza la tabla
    # (`melt`) para dibujar precisión y recall como barras lado a lado para cada regla.
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
# Permite elegir una regla y ver sus falsos positivos y falsos negativos uno por uno, con los datos de
# cada carga (o línea de factura), para entender por qué la regla se equivoca.
st.markdown("## 🔎 Inspeccionar errores")
# Las reglas se ordenan para que las que tienen algún error aparezcan primero en la lista.
conteo = por_regla.groupby("regla")[["fp", "fn"]].sum()
opciones = sorted(conteo.index, key=lambda r: (conteo.loc[r].sum() == 0, r))
# `with col1:` hace que lo que se dibuje dentro del bloque quede en esa columna. El `key` del
# selector le da un nombre fijo en `st.session_state` (la memoria de la sesión), para que la regla
# elegida se mantenga cuando Streamlit vuelve a ejecutar la página.
col1, col2 = st.columns(2)
with col1:
    regla_sel = st.selectbox(
        "Regla (las que tienen errores aparecen primero)", opciones, key="regla_errores",
        format_func=lambda r: f"{r}  ({conteo.loc[r, 'fp']} FP / {conteo.loc[r, 'fn']} FN)",
    )
# Una regla puede evaluarse contra más de un tipo de anomalía: se juntan los errores de todos.
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
    # Si la regla trabaja sobre facturas (ids que empiezan con "LIN-" o "FAC-"), los datos para mostrar
    # salen del detalle de facturación; si no, de la tabla de cargas de combustible.
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
            # Columna "origen" al principio de la tabla: el tipo de caso legítimo si lo es; si no,
            # "otra anomalía: <tipo>" si es una anomalía de otro tipo; y si no, "normal".
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
