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

from data_loader import (  # noqa: E402
    NOMBRES_ESCENARIO,
    asegurar_datos_maestro,
    load_dataset_deteccion,
    load_solicitudes,
    load_telemetria,
    selector_escenario,
)
from deteccion.hipotesis import describir_regla, hipotesis_del_escenario, reglas_de  # noqa: E402
from deteccion.reglas import CAMPOS_OBLIGATORIOS, ejecutar_reglas, normalizar_dominio  # noqa: E402

st.set_page_config(page_title="Análisis por hipótesis", page_icon="🔍", layout="wide")

st.markdown("# 🔍 Análisis por hipótesis")
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
    st.markdown("## Resumen")
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
    st.markdown("## Calidad de datos")
    st.markdown("Defectos del registro que conviene resolver antes de analizar el comportamiento.")
    col1, col2, col3 = st.columns(3)
    col1.metric("Cargas duplicadas", len(ids_de(["duplicado_exacto"])))
    col2.metric("Campos obligatorios vacíos", len(alertas[alertas["regla"].str.startswith("nulo_")]))
    col3.metric("Dominios sin vínculo", len(ids_de(["dominio_sin_vinculo"])))

    nulos = pd.DataFrame([{"Campo": campo, "Vacíos": len(ids_de([f"nulo_{campo}"])),
                           "% de las cargas": len(ids_de([f"nulo_{campo}"])) / len(consumo)}
                          for campo in CAMPOS_OBLIGATORIOS])
    st.markdown("### Campos obligatorios vacíos")
    st.dataframe(nulos.style.format({"% de las cargas": "{:.2%}"}), use_container_width=True, hide_index=True)

    st.markdown("### Cargas duplicadas (ejemplos)")
    duplicadas = alertas[alertas["regla"] == "duplicado_exacto"]
    if duplicadas.empty:
        st.success("✅ No hay cargas duplicadas.")
    else:
        st.dataframe(tabla_de_hallazgos(duplicadas).head(20), use_container_width=True, hide_index=True)



def mostrar_hipotesis(h):
    st.markdown(f"## {h['codigo']} — {h['titulo']}")
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
        st.markdown("### Antes y después")
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
        st.markdown("### Vinculación de cada fuente con la flota")
        dominios = set(flota["Dominio"])
        normalizados = set(normalizar_dominio(flota["Dominio"]))
        fuentes = [("⛽ Consumo → flota", consumo["dominio"]),
                   ("📡 Telemetría → flota", telemetria["Placa"] if not telemetria.empty else pd.Series(dtype=str)),
                   ("📋 Solicitudes → flota", solicitudes["dominio"] if not solicitudes.empty else pd.Series(dtype=str))]
        vinculos = pd.DataFrame([{"Fuente": nombre, "Registros": len(serie),
                                  "% vinculado tal como llega": serie.isin(dominios).mean() if len(serie) else float("nan"),
                                  "% vinculado normalizado": (normalizar_dominio(serie).isin(normalizados).mean()
                                                              if len(serie) else float("nan"))}
                                 for nombre, serie in fuentes])
        st.dataframe(vinculos.style.format({"% vinculado tal como llega": "{:.1%}",
                                            "% vinculado normalizado": "{:.1%}"}, na_rep="—"),
                     use_container_width=True, hide_index=True)
        st.caption("Normalizado: en mayúsculas y sin espacios, guiones ni puntos.")

    # Hallazgos
    st.markdown("### Hallazgos")
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
