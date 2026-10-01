"""Presentación Streamlit del EDA; los cálculos viven en :mod:`eda`."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from eda import (
    comparacion_auditoria,
    preparar_cargas,
    resumen_calidad,
    resumen_cargas,
    resumen_cruces,
    resumen_flota,
    resumen_temporal,
)


PALETA = ["#1d4b73", "#2a8b8b", "#d08a26", "#79a65a", "#765a9b"]


@st.cache_data(show_spinner=False)
def calcular_eda(flota, telemetria, consumo, solicitudes, gps_diario, detalle, fuentes):
    """Ejecuta una vez los resúmenes que alimentan la pestaña."""
    solicitudes_validas = None if solicitudes.empty else solicitudes
    gps_valido = None if gps_diario.empty else gps_diario
    detalle_valido = None if detalle.empty else detalle
    cargas = preparar_cargas(consumo, flota, solicitudes_validas, gps_valido)
    return {
        "flota": resumen_flota(flota, telemetria),
        "cargas": resumen_cargas(cargas),
        "tiempo": resumen_temporal(cargas),
        "calidad": resumen_calidad(fuentes, flota, consumo),
        "cruces": resumen_cruces(consumo, flota, solicitudes_validas, gps_valido, detalle_valido),
    }


def _barra(df, x, y, titulo, color=None):
    if df.empty:
        st.info("Esta vista no está disponible para el escenario seleccionado.")
        return
    figura = px.bar(df, x=x, y=y, color=color, title=titulo, color_discrete_sequence=PALETA)
    figura.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(figura, use_container_width=True)


def mostrar_eda(
    escenario: str,
    flota: pd.DataFrame,
    telemetria: pd.DataFrame,
    consumo: pd.DataFrame,
    solicitudes: pd.DataFrame,
    gps_diario: pd.DataFrame,
    detalle: pd.DataFrame,
    fuentes: dict[str, pd.DataFrame],
    base_dir: Path,
):
    """Dibuja los seis bloques exploratorios exigidos para el Sprint 3."""
    st.subheader("📊 Análisis exploratorio")
    st.caption(
        "Lectura descriptiva y reproducible de las fuentes del escenario seleccionado. "
        "Las diferencias observadas orientan preguntas: no constituyen por sí solas alertas ni causas confirmadas."
    )
    datos = calcular_eda(flota, telemetria, consumo, solicitudes, gps_diario, detalle, fuentes)

    st.markdown("### 1. Flota — ¿Cómo está compuesta?")
    c1, c2 = st.columns(2)
    with c1:
        _barra(datos["flota"]["estados"], "estado", "cantidad", "Vehículos por estado")
    with c2:
        _barra(datos["flota"]["tipos"], "tipo_vehiculo", "cantidad", "Vehículos por tipo")
    c3, c4 = st.columns(2)
    with c3:
        _barra(datos["flota"]["combustibles"], "combustible", "cantidad", "Combustible declarado")
    with c4:
        _barra(datos["flota"]["telemetria_estado"], "Estado", "cantidad",
               "Cobertura de telemetría por estado", "telemetria")
    st.caption("Lectura: la composición y la cobertura tecnológica deben considerarse antes de comparar vehículos.")

    st.markdown("### 2. Cargas — ¿Cómo carga la flota?")
    por_tipo = datos["cargas"]["por_tipo"]
    c1, c2 = st.columns(2)
    with c1:
        _barra(por_tipo, "TipoVehiculo", "litros_mediana", "Mediana de litros por tipo")
    with c2:
        _barra(por_tipo, "TipoVehiculo", "cargas", "Cantidad de cargas por tipo")
    percentiles = datos["cargas"]["percentiles"]
    if not percentiles.empty:
        st.dataframe(percentiles, use_container_width=True, hide_index=True)
    st.caption("Lectura: volumen, proporción del tanque, distancia y rendimiento se presentan como contexto operativo, no como umbrales de anomalía.")

    st.markdown("### 3. Tiempo — ¿Cuándo se realizan las cargas?")
    c1, c2, c3 = st.columns(3)
    with c1:
        _barra(datos["tiempo"]["mes"], "mes", "cargas", "Cargas por mes")
    with c2:
        _barra(datos["tiempo"]["dia_semana"], "dia_semana", "cargas", "Cargas por día")
    with c3:
        _barra(datos["tiempo"]["hora_del_dia"], "hora_del_dia", "cargas", "Cargas por hora")
    st.caption("Lectura: la distribución temporal permite reconocer concentración y cobertura del período antes de comparar indicadores.")

    st.markdown("### 4. Calidad — ¿Qué tan preparados están los datos?")
    vinculacion = datos["calidad"]["vinculacion"]
    c1, c2 = st.columns(2)
    with c1:
        _barra(vinculacion, "criterio", "porcentaje", "Vinculación con la flota antes y después de H1")
    with c2:
        _barra(datos["calidad"]["formatos_dominio"], "formato", "cantidad", "Formatos de dominio")
    calidad = datos["calidad"]["columnas"]
    if not calidad.empty:
        st.dataframe(calidad.sort_values(["completitud_pct", "fuente", "columna"]).head(30),
                     use_container_width=True, hide_index=True)
        st.caption("Se muestran primero las 30 columnas con menor completitud; el cálculo conserva todas las fuentes operativas.")
    st.info("La comparación completa entre reglas simples y reglas con contexto se mantiene en las páginas de análisis e hipótesis.")
    st.markdown(
        "Continuar en **5. Análisis por hipótesis** para comparar reglas y en "
        "**7. Hipótesis** para revisar su validación. Ambas páginas están disponibles en el menú lateral."
    )

    st.markdown("### 5. Cruce entre fuentes — ¿Qué partes del circuito pueden vincularse?")
    cruces = datos["cruces"]
    _barra(cruces, "tramo", "cobertura_pct", "Cobertura de los cruces disponibles")
    if not cruces.empty:
        st.dataframe(cruces, use_container_width=True, hide_index=True)
    st.caption("Lectura: las coberturas describen disponibilidad y correspondencia; una fila sin vínculo no demuestra por sí sola una irregularidad.")
    if escenario != "realista":
        st.info("El escenario didáctico no incluye el circuito relacional completo ni GPS diario; por eso este bloque tiene alcance parcial.")

    st.markdown("### 6. Sintético frente a real — ¿El escenario conserva la escala observada?")
    auditoria = base_dir / "perfiles" / "aprobados" / "auditoria_2026-09-30.json"
    comparacion = comparacion_auditoria(auditoria) if auditoria.exists() else pd.DataFrame()
    if comparacion.empty:
        st.info("No se encontró una auditoría agregada aprobada para realizar la comparación.")
    else:
        elegidas = ["ratio_litros_tanque", "km", "rendimiento_relativo", "cargas_en_el_dia", "litros_vs_autorizado"]
        comparacion = comparacion[comparacion["variable"].isin(elegidas)]
        grafico = comparacion.melt(id_vars=["variable", "percentil"], value_vars=["real", "sintetico"],
                                  var_name="origen", value_name="valor")
        figura = px.bar(grafico, x="percentil", y="valor", color="origen", facet_col="variable",
                        barmode="group", color_discrete_sequence=PALETA,
                        title="Percentiles aprobados: fuente real agregada y escenario sintético")
        figura.update_yaxes(matches=None)
        figura.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        figura.update_layout(margin=dict(l=10, r=10, t=70, b=10), legend_title_text="")
        st.plotly_chart(figura, use_container_width=True)
        st.dataframe(comparacion, use_container_width=True, hide_index=True)
        st.caption("Solo se utilizan p05, mediana y p95 de la auditoría aprobada; no se exponen registros ni identificadores reales.")
