"""Análisis por hipótesis: qué encuentran las reglas en los datos.

Usa el mismo catálogo de hipótesis y las mismas reglas que las páginas de Detección e
Hipótesis. No usa el ground truth: muestra lo que vería un auditor. La validación
contra las anomalías inyectadas está en la página Hipótesis.
"""
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
    load_solicitudes,
    load_telemetria,
    selector_escenario,
)
from deteccion.hipotesis import describir_regla, hipotesis_del_escenario, reglas_de  # noqa: E402
from deteccion.reglas import CAMPOS_OBLIGATORIOS, ejecutar_reglas  # noqa: E402

st.set_page_config(page_title="Análisis por hipótesis", page_icon="🔍", layout="wide")

seccion(
    "🔍 Análisis por hipótesis", nivel=1,
    ayuda="Recorre las hipótesis una por una y muestra qué encuentra cada regla en los datos, con "
          "los casos concretos. Arriba hay tres vistas: un resumen de todas, la calidad del "
          "registro, y el detalle de una hipótesis. Ojo con una distinción importante: esta "
          "página **no mira la verdad de referencia**, muestra lo que vería un auditor sin saber "
          "qué se inyectó. Si un caso listado acá fuera un falso positivo, esta página no lo "
          "puede saber; eso se verifica en la página Hipótesis.")
st.markdown(
    "Qué encuentran las reglas en los datos, hipótesis por hipótesis. Para cada una se muestra cuánto "
    "marca la **regla ingenua** y cuánto queda con la **regla con contexto**, con los casos concretos. "
    "Esta página **no usa el ground truth**: muestra lo que vería un auditor. Cuántas de esas alertas son "
    "anomalías reales se valida en la página **Hipótesis**."
)

escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
flota, consumo = datos["flota"], datos["consumo"]
telemetria = load_telemetria(escenario)
solicitudes = load_solicitudes(escenario)
detalle_factura = datos["facturacion_detalle"]
facturas = datos["facturacion"]

if flota.empty or consumo.empty:
    st.error("❌ Datos insuficientes. Ejecutá primero el Generador.")
    st.stop()
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** (se cambia en la barra lateral).")


@st.cache_data
def calcular_alertas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion, facturacion_detalle):
    return ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                           facturacion_detalle)


alertas = calcular_alertas(flota, consumo, datos["estaciones"], datos["telemetria_diaria"], datos["solicitudes"],
                           facturas, detalle_factura)
catalogo = hipotesis_del_escenario(escenario)


factura_de_linea = (dict(zip(detalle_factura["numero_linea"], detalle_factura["numero_factura"]))
                    if detalle_factura is not None else {})


def ids_de(reglas, por_factura=False):
    """Registros marcados por las reglas; `por_factura` cuenta cada línea como su factura."""
    ids = set(alertas.loc[alertas["regla"].isin(reglas), "id_registro"])
    return {factura_de_linea.get(i, i) for i in ids} if por_factura else ids


def tabla_de_hallazgos(ids_alertas):
    """Alertas con los datos del registro alertado (carga, línea de factura o factura)."""
    columnas_carga = ["id", "vehiculo_id", "dominio", "fecha", "estacion", "litros", "odometro"]
    tablas = [consumo[columnas_carga]]
    if detalle_factura is not None:
        tablas.append(detalle_factura.rename(columns={"numero_linea": "id"})[
            ["id", "numero_factura", "referencia_consumo", "fecha", "dominio", "litros", "precio_unitario", "importe"]])
    if facturas is not None:
        tablas.append(facturas.rename(columns={"numero_factura": "id"})[["id", "proveedor", "periodo", "total_monto"]])
    registros = pd.concat(tablas, ignore_index=True).drop_duplicates("id")
    return (ids_alertas.merge(registros, left_on="id_registro", right_on="id", how="left")
            .drop(columns="id").dropna(axis=1, how="all"))


vehiculo_de_carga = consumo.set_index("id")["vehiculo_id"]
fecha_de_carga = pd.to_datetime(consumo.set_index("id")["fecha"])

# ============================================================================
# Vistas
# ============================================================================

def mostrar_resumen():
    seccion(
        "Resumen",
        ayuda="Las nueve hipótesis en una tabla: qué dice cada una, cuántas alertas produce la "
              "regla ingenua y cuántas quedan con la regla que usa más contexto. Sirve para "
              "elegir por dónde empezar. La última columna avisa si el conteo va en **facturas** "
              "o en **registros**, porque no es lo mismo: una factura con tres líneas "
              "irregulares es un solo documento que revisar.")
    filas = []
    for h in catalogo:
        ingenua, contexto = h["reglas"][0][0], h["reglas"][-1][0]
        por_factura = h.get("nivel") == "factura"
        n_ingenua = len(ids_de(reglas_de(ingenua), por_factura))
        n_contexto = len(ids_de(reglas_de(contexto), por_factura))
        filas.append({
            "Hipótesis": h["codigo"], "Tema": h["titulo"],
            "Regla ingenua": describir_regla(ingenua) if len(h["reglas"]) > 1 else "—",
            "Marcadas (ingenua)": f"{n_ingenua:,}" if len(h["reglas"]) > 1 else "—",
            "Regla con contexto": describir_regla(contexto), "Marcadas (con contexto)": n_contexto,
            "Unidad": "facturas" if h.get("nivel") == "factura" else "registros",
        })
    resumen = pd.DataFrame(filas)
    st.dataframe(resumen, use_container_width=True, hide_index=True)

    comparables = resumen[resumen["Regla ingenua"] != "—"].assign(
        **{"Marcadas (ingenua)": lambda d: d["Marcadas (ingenua)"].str.replace(",", "").astype(int)})
    grafico = comparables.melt(
        id_vars="Hipótesis", value_vars=["Marcadas (ingenua)", "Marcadas (con contexto)"],
        var_name="Regla", value_name="Registros marcados")
    if not grafico.empty:
        fig = px.bar(grafico, x="Hipótesis", y="Registros marcados", color="Regla", barmode="group",
                     log_y=True, text_auto=True, height=380)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Escala logarítmica. Que la regla con contexto marque menos no garantiza que acierte más: "
                   "eso se valida en la página Hipótesis.")



def mostrar_calidad():
    seccion(
        "Calidad de datos",
        ayuda="Defectos del registro que conviene arreglar **antes** de sacar conclusiones sobre "
              "el comportamiento de consumo. Si hay cargas duplicadas o dominios sin vincular, "
              "cualquier promedio o umbral que se calcule encima va a estar mal. Es un paso "
              "previo, no un resultado del análisis.")
    st.markdown("Defectos del registro que conviene resolver antes de analizar el comportamiento.")
    col1, col2, col3 = st.columns(3)
    col1.metric("Cargas duplicadas", len(ids_de(["duplicado_exacto"])))
    col2.metric("Campos obligatorios vacíos", len(alertas[alertas["regla"].str.startswith("nulo_")]))
    col3.metric("Dominios sin vínculo", len(ids_de(["dominio_sin_vinculo"])))

    nulos = pd.DataFrame([{"Campo": campo, "Vacíos": len(ids_de([f"nulo_{campo}"])),
                           "% de las cargas": len(ids_de([f"nulo_{campo}"])) / len(consumo)}
                          for campo in CAMPOS_OBLIGATORIOS])
    seccion(
        "Campos obligatorios vacíos", nivel=3,
        ayuda="Porcentaje de cargas a las que les falta cada campo. No todos los vacíos son "
              "anomalías: el `conductor` puede no venir en todas las cargas según cómo se captura "
              "el dato, y el generador lo inyecta como defecto de calidad con una tasa baja. Lo "
              "que importa es la proporción, no el caso individual.")
    st.dataframe(nulos.style.format({"% de las cargas": "{:.2%}"}), use_container_width=True, hide_index=True)

    seccion(
        "Cargas duplicadas (ejemplos)", nivel=3,
        ayuda="Cargas exactamente repetidas con un identificador nuevo. No son dos operaciones: "
              "es la misma operación registrada dos veces. Contarlas como dos infla el volumen de "
              "litros, así que hay que identificarlas y descartarlas antes de cualquier total.")
    duplicadas = alertas[alertas["regla"] == "duplicado_exacto"]
    if duplicadas.empty:
        st.success("✅ No hay cargas duplicadas.")
    else:
        st.dataframe(tabla_de_hallazgos(duplicadas).head(20), use_container_width=True, hide_index=True)



def mostrar_hipotesis(h):
    seccion(
        f"{h['codigo']} — {h['titulo']}",
        ayuda="Una hipótesis a la vez. Lo que se muestra es lo que marcó la regla con más "
              "contexto: los indicadores de arriba dicen cuántos registros cayeron y cuántos "
              "vehículos o facturas implica, y la tabla del final trae los casos concretos con "
              "sus datos. Para saber si esos casos eran anomalías reales o falsos positivos, "
              "hay que ir a la página Hipótesis: acá no se usa la verdad de referencia.")
    st.markdown(f"**Hipótesis.** {h['enunciado']}")
    st.caption(f"Contexto que usa: {h['contexto']}.")
    por_factura = h.get("nivel") == "factura"
    reglas_contexto = reglas_de(h["reglas"][-1][0])
    hallazgos = alertas[alertas["regla"].isin(reglas_contexto)]
    ids = set(hallazgos["id_registro"])

    # Indicadores
    col1, col2, col3 = st.columns(3)
    if por_factura:
        factura_de = dict(zip(detalle_factura["numero_linea"], detalle_factura["numero_factura"]))
        facturas_marcadas = {factura_de.get(i, i) for i in ids}
        importe = detalle_factura.set_index("numero_linea")["importe"]
        col1.metric("Facturas con hallazgos", f"{len(facturas_marcadas)} de {len(facturas)}")
        col2.metric("Líneas irregulares", len(ids & set(importe.index)))
        col3.metric("Importe de esas líneas", f"${importe.reindex(list(ids & set(importe.index))).sum():,.0f}")
    else:
        vehiculos = {vehiculo_de_carga.get(i) for i in ids} - {None}
        col1.metric("Cargas marcadas", f"{len(ids):,}")
        col2.metric("% de las cargas", f"{len(ids) / len(consumo):.2%}")
        col3.metric("Vehículos involucrados", len(vehiculos))

    # Antes y después: de la regla ingenua a la regla con contexto
    if len(h["reglas"]) > 1:
        seccion(
            "Antes y después", nivel=3,
            ayuda="El camino de la regla ingenua a la regla con contexto, paso por paso. Cada fila "
                  "agrega un dato: primero un criterio simple, después el historial del vehículo, "
                  "luego el GPS, la fecha de estado, la solicitud. Lo que se busca no es marcar "
                  "menos, es marcar menos cosas que están bien.")
        pasos = pd.DataFrame([{"Regla": describir_regla(regla), "Criterio": descripcion,
                               "Marcadas": len(ids_de(reglas_de(regla), por_factura))}
                              for regla, descripcion in h["reglas"]])
        if por_factura:
            st.caption("Contado en facturas: una línea irregular cuenta como su factura.")
        st.dataframe(pasos, use_container_width=True, hide_index=True)
        antes, despues = pasos["Marcadas"].iloc[0], pasos["Marcadas"].iloc[-1]
        unidad = "facturas" if por_factura else "registros"
        if antes > despues:
            st.markdown(f"Con contexto se descartan **{antes - despues:,}** de las **{antes:,}** {unidad} que "
                        f"marcaría la regla ingenua ({(antes - despues) / antes:.0%}).")
        elif antes < despues:
            st.markdown(f"La regla ingenua marca **{antes:,}** {unidad} y la regla con contexto **{despues:,}**: "
                        "el contexto permite ver casos que la ingenua no alcanza.")

    # H1: vinculación de cada fuente con la flota
    if h["codigo"] == "H1":
        seccion(
            "Vinculación de cada fuente con la flota", nivel=3,
            ayuda="Cuánto se parece cada fuente al dominio real del vehículo, para contrastar una "
                  "con otra. Es el fundamento de H1: la misma anomalía de vinculación puede "
                  "aparecer solo en el consumo y no en la telemetría, y esa diferencia es la que "
                  "permite detectarla sin adivinar.")
        dominios = set(flota["Dominio"])
        fuentes = [("⛽ Consumo → flota", consumo["dominio"]),
                   ("📡 Telemetría → flota", telemetria["Placa"] if not telemetria.empty else pd.Series(dtype=str)),
                   ("📋 Solicitudes → flota", solicitudes["dominio"] if not solicitudes.empty else pd.Series(dtype=str))]
        vinculos = pd.DataFrame([{"Fuente": nombre, "Registros": len(serie),
                                  "Vinculados": int(serie.isin(dominios).sum()),
                                  "% vinculado": serie.isin(dominios).mean() if len(serie) else float("nan")}
                                 for nombre, serie in fuentes])
        st.dataframe(vinculos.style.format({"% vinculado": "{:.1%}"}, na_rep="—"),
                     use_container_width=True, hide_index=True)

    # Hallazgos
    seccion(
        "Hallazgos", nivel=3,
        ayuda="Los registros marcados, con el gráfico de cómo se reparten en el tiempo y la tabla "
              "de casos. El gráfico sirve para ver si un problema se concentra en un mes, lo que "
              "suele indicar que cambió el proceso de carga y no el comportamiento de los "
              "conductores.")
    if hallazgos.empty:
        st.success("✅ Las reglas no encontraron casos en estos datos.")
        return
    if por_factura:
        por_regla = hallazgos.groupby("regla")["id_registro"].nunique().reset_index(name="Hallazgos")
        fig = px.bar(por_regla, x="regla", y="Hallazgos", text_auto=True, height=320, labels={"regla": ""})
    else:
        en_el_tiempo = hallazgos.assign(mes=hallazgos["id_registro"].map(fecha_de_carga).dt.to_period("M")
                                        .astype(str)).dropna(subset=["mes"])
        por_mes = en_el_tiempo.groupby(["mes", "regla"])["id_registro"].nunique().reset_index(name="Cargas")
        fig = px.bar(por_mes, x="mes", y="Cargas", color="regla", height=320, labels={"mes": ""})
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(tabla_de_hallazgos(hallazgos.drop_duplicates("id_registro")).head(100),
                 use_container_width=True, hide_index=True)
    if len(ids) > 100:
        st.caption(f"Se muestran 100 de {len(ids):,} registros.")


# ============================================================================
# Navegación: una vista a la vez (las pestañas no entraban en la pantalla)
# ============================================================================

VISTAS = ["📋 Resumen", "🧹 Calidad de datos", "🔍 Por hipótesis"]
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista_analisis", label_visibility="collapsed")
st.markdown("---")

if vista == VISTAS[0]:
    mostrar_resumen()
    st.info("💡 Para ver los hallazgos de una hipótesis, elegí **🔍 Por hipótesis** arriba.")
elif vista == VISTAS[1]:
    mostrar_calidad()
else:
    por_codigo = {h["codigo"]: h for h in catalogo}
    codigo = st.selectbox("Hipótesis", list(por_codigo), key="hipotesis_analisis",
                          format_func=lambda c: f"{c} · {por_codigo[c]['titulo']}")
    mostrar_hipotesis(por_codigo[codigo])
