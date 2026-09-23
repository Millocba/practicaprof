"""Análisis Maestro - Validación de Hipótesis H1-H3a con Ejemplos ANTES/DESPUÉS

MEJORAS:
- Ejemplos concretos "antes y después" en cada hipótesis
- Detalles de sesgos detectados con contexto
- Visualización de consumos anómalos con comparación
- Casos de estudio por hipótesis
"""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import plotly.graph_objects as go
import plotly.express as px

# Add utils to path
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from data_loader import (
    load_flota,
    load_telemetria,
    load_consumo_maestro,
    load_solicitudes,
    load_facturacion,
)

st.set_page_config(page_title="Análisis - H1 a H3a", page_icon="🔍", layout="wide")

st.markdown("# 🔍 Análisis de Hipótesis: Validación H1-H3a")
st.markdown("Validación con ejemplos concretos: antes y después de la detección")

# Load all data
flota = load_flota()
telemetria = load_telemetria()
consumo = load_consumo_maestro()
solicitudes = load_solicitudes()
facturacion = load_facturacion()

if flota.empty or consumo.empty:
    st.error("❌ Datos insuficientes. Ejecuta primero el Generador.")
    st.stop()

# ============================================================================
# PRECÁLCULOS: Preparar métricas de H1-H3a
# ============================================================================

# H1: Validación de Vinculaciones Cross-Entity
tele_validas = telemetria[telemetria['Placa'].isin(flota['Dominio'])] if not telemetria.empty else pd.DataFrame()
tele_total = len(telemetria) if not telemetria.empty else 0
tele_pct = (len(tele_validas) / tele_total * 100) if tele_total > 0 else 0

cons_validas = consumo[consumo['dominio'].isin(flota['Dominio'])]
cons_total = len(consumo)
cons_pct = (len(cons_validas) / cons_total * 100) if cons_total > 0 else 0

sol_validas = solicitudes[solicitudes['dominio'].isin(flota['Dominio'])] if not solicitudes.empty else pd.DataFrame()
sol_total = len(solicitudes) if not solicitudes.empty else 0
sol_pct = (len(sol_validas) / sol_total * 100) if sol_total > 0 else 0

cons_invalidas = consumo[~consumo['dominio'].isin(flota['Dominio'])]

h1_validada = (cons_pct >= 98 and tele_pct >= 98 and sol_pct >= 98)

# H2: Detección de anomalías de odómetro
anomalias_odometro = []
if not consumo.empty:
    consumo_sorted = consumo.copy()
    # IMPORTANTE: Convertir fecha a datetime
    consumo_sorted['fecha'] = pd.to_datetime(consumo_sorted['fecha'], errors='coerce')
    consumo_sorted = consumo_sorted.sort_values(['dominio', 'fecha'])

    for dominio in consumo_sorted['dominio'].unique():
        veh_consumo = consumo_sorted[consumo_sorted['dominio'] == dominio].copy()

        if len(veh_consumo) > 1:
            veh_consumo['odo_change'] = veh_consumo['odometro'].diff()
            veh_consumo['days_diff'] = veh_consumo['fecha'].diff().dt.days

            # Detectar anomalías: cambios negativos o saltos excesivos
            anomalias_veh = veh_consumo[
                (veh_consumo['odo_change'] < 0) |
                ((veh_consumo['odo_change'] > 500) & (veh_consumo['days_diff'] <= 7))
            ]

            if len(anomalias_veh) > 0:
                for idx, row in anomalias_veh.iterrows():
                    anomalias_odometro.append({
                        'dominio': dominio,
                        'fecha': row['fecha'],
                        'odometro_previo': row['odometro'] - row['odo_change'],
                        'odometro_actual': row['odometro'],
                        'cambio_km': row['odo_change'],
                        'dias': row['days_diff'],
                        'tipo': 'REGRESIÓN' if row['odo_change'] < 0 else 'SALTO_ANORMAL'
                    })

anomalias_odo_detectadas = len(anomalias_odometro)
h2_validada = (anomalias_odo_detectadas >= 10)

# H3a: Análisis de Exceso Volumétrico
analisis_volumetrico = pd.DataFrame()
veh_sin_anomalia = 0
veh_con_anomalia = 0

if not consumo.empty and not flota.empty:
    consumo_por_veh = consumo.groupby('dominio').agg({
        'litros': ['sum', 'mean', 'count'],
        'fecha': ['min', 'max']
    }).reset_index()

    consumo_por_veh.columns = ['dominio', 'litros_total', 'litros_promedio', 'num_transacciones', 'fecha_inicio', 'fecha_fin']

    analisis_volumetrico = consumo_por_veh.merge(
        flota[['Dominio', 'CapacidadTanque']],
        left_on='dominio',
        right_on='Dominio',
        how='left'
    )

    analisis_volumetrico['capacidad'] = analisis_volumetrico['CapacidadTanque']
    analisis_volumetrico['ratio_promedio'] = (
        analisis_volumetrico['litros_promedio'] / analisis_volumetrico['capacidad']
    )
    analisis_volumetrico['exceso_detectado'] = (
        analisis_volumetrico['litros_promedio'] > analisis_volumetrico['capacidad']
    )

    veh_sin_anomalia = len(analisis_volumetrico[analisis_volumetrico['ratio_promedio'] <= 1.0])
    veh_con_anomalia = len(analisis_volumetrico[analisis_volumetrico['ratio_promedio'] > 1.0])

h3a_validada = (veh_con_anomalia >= 5)

# ============================================================================
# TABS
# ============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 H1: Normalización",
    "🚩 H2: Sesgo Odómetro",
    "⛽ H3a: Exceso Volumétrico",
    "📊 Resumen Integral"
])

# ============================================================================
# TAB 1: H1 - ANTES Y DESPUÉS
# ============================================================================

with tab1:
    st.markdown("## H1: Normalización de Claves → Mejora de Vinculación")
    st.markdown("**Hipótesis:** La normalización de campos clave mejora el % de vinculación entre tablas")
    st.markdown("**Objetivo:** Vinculación ≥ 98% en todas las tablas")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📡 Flota → Telemetría")
        st.metric("Vinculación Exitosa", f"{tele_pct:.1f}%", f"{len(tele_validas)}/{tele_total}")
        fig_tele = go.Figure(data=[go.Bar(x=['Vinculadas', 'Sin Vínculo'], y=[len(tele_validas), tele_total - len(tele_validas)], marker_color=['#2ecc71', '#e74c3c'])])
        fig_tele.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_tele, use_container_width=True)

    with col2:
        st.markdown("### ⛽ Flota → Consumo")
        st.metric("Vinculación Exitosa", f"{cons_pct:.1f}%", f"{len(cons_validas)}/{cons_total}")
        fig_cons = go.Figure(data=[go.Bar(x=['Vinculadas', 'Sin Vínculo'], y=[len(cons_validas), cons_total - len(cons_validas)], marker_color=['#2ecc71', '#e74c3c'])])
        fig_cons.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_cons, use_container_width=True)

    with col3:
        st.markdown("### 📋 Flota → Solicitudes")
        st.metric("Vinculación Exitosa", f"{sol_pct:.1f}%", f"{len(sol_validas)}/{sol_total}")
        fig_sol = go.Figure(data=[go.Bar(x=['Vinculadas', 'Sin Vínculo'], y=[len(sol_validas), sol_total - len(sol_validas)], marker_color=['#2ecc71', '#e74c3c'])])
        fig_sol.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_sol, use_container_width=True)

    st.markdown("---")

    # Ejemplos ANTES Y DESPUÉS
    if not cons_invalidas.empty:
        st.markdown("### 🔍 Registros de CONSUMO que NO vinculan con FLOTA")
        st.markdown("**Estos son los registros que fallaron la normalización:**")

        sample_invalidos = cons_invalidas.head(10)[['dominio', 'fecha', 'litros', 'estacion']].copy()
        sample_invalidos.columns = ['Dominio (CONSUMO)', 'Fecha', 'Litros', 'Estación']
        st.dataframe(sample_invalidos, use_container_width=True)

        st.info(f"⚠️ {len(cons_invalidas)} registros en CONSUMO NO se encontraban en FLOTA (dominios no normalizados)")

    # Resumen
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.success("✓ Objetivo: Vinculación ≥ 98% en todas las tablas")
    with col2:
        if h1_validada:
            st.success("✅ **HIPÓTESIS H1 VALIDADA**")
        else:
            st.warning("⚠️ H1 Pendiente validación")


# ============================================================================
# TAB 2: H2 - SESGOS DETECTADOS
# ============================================================================

with tab2:
    st.markdown("## H2: Detección de Sesgo en Odómetro")
    st.markdown("**Hipótesis:** Existen inconsistencias en el odómetro que indican manipulación")
    st.markdown("**Objetivo:** Detectar ≥ 10 anomalías de odómetro")

    col1, col2 = st.columns([1, 2])

    with col1:
        pct_anomalias = (anomalias_odo_detectadas / cons_total * 100) if cons_total > 0 else 0
        st.metric("Anomalías Detectadas", f"{anomalias_odo_detectadas}", f"{pct_anomalias:.2f}% de {cons_total}")
        if anomalias_odo_detectadas > 0:
            veh_afectados = len(set([a['dominio'] for a in anomalias_odometro]))
            st.metric("Vehículos Afectados", veh_afectados)

    with col2:
        if anomalias_odometro:
            df_anom = pd.DataFrame(anomalias_odometro)
            tipo_counts = df_anom['tipo'].value_counts()
            fig = px.bar(x=tipo_counts.index, y=tipo_counts.values, labels={'x': 'Tipo de Anomalía', 'y': 'Cantidad'}, title="Distribución de Anomalías Odómetro", color_discrete_sequence=['#e74c3c'])
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin anomalías detectadas")

    st.markdown("---")

    if anomalias_odometro:
        st.markdown("### 🚨 CASOS DE ESTUDIO: Sesgos Detectados")

        # Separar por tipo
        df_anom = pd.DataFrame(anomalias_odometro)

        # Regresiones (odómetro en reversa)
        regresiones = df_anom[df_anom['tipo'] == 'REGRESIÓN']
        if len(regresiones) > 0:
            st.markdown(f"#### 🔄 REGRESIONES ({len(regresiones)} casos) - Odómetro retrocede")
            sample_regr = regresiones.head(5).copy()
            sample_regr = sample_regr[['dominio', 'fecha', 'odometro_previo', 'odometro_actual', 'cambio_km', 'dias']]
            sample_regr.columns = ['Vehículo', 'Fecha', 'Odóm. Anterior (km)', 'Odóm. Actual (km)', 'Cambio (km)', 'Días']
            st.dataframe(sample_regr, use_container_width=True)
            st.warning(f"🚩 {len(regresiones)} regresiones detectadas - Indicador de manipulación o error de sensor")

        # Saltos anormales
        saltos = df_anom[df_anom['tipo'] == 'SALTO_ANORMAL']
        if len(saltos) > 0:
            st.markdown(f"#### ⚡ SALTOS ANORMALES ({len(saltos)} casos) - Más de 500km en ≤7 días")
            sample_saltos = saltos.head(5).copy()
            sample_saltos = sample_saltos[['dominio', 'fecha', 'odometro_previo', 'odometro_actual', 'cambio_km', 'dias']]
            sample_saltos.columns = ['Vehículo', 'Fecha', 'Odóm. Anterior (km)', 'Odóm. Actual (km)', 'Cambio (km)', 'Días']
            st.dataframe(sample_saltos, use_container_width=True)
            st.warning(f"⚠️ {len(saltos)} saltos detectados - Viajes de larga distancia en corto tiempo")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.info("📊 Objetivo: Detectar ≥ 10 anomalías de odómetro")
    with col2:
        if h2_validada:
            st.success("✅ **HIPÓTESIS H2 VALIDADA**")
        else:
            st.warning(f"⚠️ H2 Pendiente - Solo {anomalias_odo_detectadas} detectadas (min: 10)")


# ============================================================================
# TAB 3: H3a - CONSUMO ANÓMALO
# ============================================================================

with tab3:
    st.markdown("## H3a: Detección de Exceso Volumétrico")
    st.markdown("**Hipótesis:** Se pueden detectar casos donde consumo promedio > capacidad del tanque")
    st.markdown("**Objetivo:** Mínimo 5 vehículos con consumo anómalo")

    if not analisis_volumetrico.empty:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Vehículos Normales", veh_sin_anomalia, "Consumo ≤ Capacidad")
        with col2:
            st.metric("Vehículos Anómalos", veh_con_anomalia, "Consumo > Capacidad")
        with col3:
            promedio_ratio = analisis_volumetrico['ratio_promedio'].mean()
            st.metric("Ratio Promedio", f"{promedio_ratio:.2f}x", "Consumo / Capacidad")
        with col4:
            max_ratio = analisis_volumetrico['ratio_promedio'].max()
            st.metric("Máximo Ratio", f"{max_ratio:.2f}x", "Caso más extremo")

        st.markdown("### 📊 Consumo Promedio vs Capacidad (ANTES Y DESPUÉS)")
        st.markdown("**Línea diagonal:** Límite de capacidad (ratio = 1.0x). Puntos rojos = consumo excesivo")

        fig_scatter = px.scatter(
            analisis_volumetrico,
            x='capacidad',
            y='litros_promedio',
            color='exceso_detectado',
            labels={'capacidad': 'Capacidad (L)', 'litros_promedio': 'Consumo Promedio (L)', 'exceso_detectado': 'Exceso Detectado'},
            title="Identificación de Exceso Volumétrico",
            color_discrete_map={True: '#e74c3c', False: '#2ecc71'},
            hover_data=['dominio', 'num_transacciones', 'ratio_promedio']
        )

        max_val = max(analisis_volumetrico['capacidad'].max(), analisis_volumetrico['litros_promedio'].max())
        fig_scatter.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode='lines', name='Límite (1.0x)', line=dict(dash='dash', color='gray')))
        fig_scatter.update_layout(height=400)
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown("---")

        if veh_con_anomalia > 0:
            st.markdown(f"### 🚨 CASOS ANÓMALOS DETECTADOS ({veh_con_anomalia} vehículos)")
            st.markdown("**Estos vehículos están consumiendo más que la capacidad de su tanque:**")

            anomalos = analisis_volumetrico[analisis_volumetrico['exceso_detectado']].sort_values('ratio_promedio', ascending=False)
            df_anom = anomalos[['dominio', 'capacidad', 'litros_promedio', 'ratio_promedio', 'num_transacciones']].copy()
            df_anom.columns = ['Vehículo', 'Capacidad (L)', 'Consumo Promedio (L)', 'Ratio', 'Transacciones']
            df_anom['Ratio'] = df_anom['Ratio'].apply(lambda x: f"{x:.2f}x")
            st.dataframe(df_anom, use_container_width=True)

            st.error("🚨 Estos vehículos tienen consumos anómalos que superan la capacidad de sus tanques")

        st.markdown("### 📈 Distribución de Ratios Consumo/Capacidad")
        fig_hist = px.histogram(analisis_volumetrico, x='ratio_promedio', nbins=20, title="Ratios de Consumo", labels={'ratio_promedio': 'Ratio'}, color_discrete_sequence=['#3498db'])
        fig_hist.add_vline(x=1.0, line_dash="dash", line_color="red", annotation_text="Límite Crítico")
        fig_hist.update_layout(height=300)
        st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.info("🎯 Objetivo: ≥ 5 vehículos con consumo anómalo")
        with col2:
            if h3a_validada:
                st.success("✅ **HIPÓTESIS H3a VALIDADA**")
            else:
                st.warning(f"⚠️ H3a Pendiente - {veh_con_anomalia} detectados (min: 5)")


# ============================================================================
# TAB 4: RESUMEN INTEGRAL
# ============================================================================

with tab4:
    st.markdown("## 📊 Resumen Integral")

    status_data = {
        'Hipótesis': ['H1: Normalización', 'H2: Sesgo Odómetro', 'H3a: Exceso Volumétrico'],
        'Métrica': [f'Vinculación: {cons_pct:.1f}%', f'Anomalías: {anomalias_odo_detectadas}', f'Vehículos anómalos: {veh_con_anomalia}'],
        'Objetivo': ['≥ 98%', '≥ 10', '≥ 5'],
        'Estado': ['✅ VALIDADA' if h1_validada else '⚠️ Pendiente', '✅ VALIDADA' if h2_validada else '⚠️ Pendiente', '✅ VALIDADA' if h3a_validada else '⚠️ Pendiente']
    }
    st.dataframe(pd.DataFrame(status_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📋 Datasets Originales")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("🚗 Flota", len(flota))
    with col2:
        st.metric("📡 Telemetría", len(telemetria))
    with col3:
        st.metric("⛽ Consumo", len(consumo))
    with col4:
        st.metric("📋 Solicitudes", len(solicitudes))
    with col5:
        st.metric("💰 Facturación", len(facturacion))

    st.markdown("---")

    st.markdown("### 📌 Conclusiones")

    col1, col2 = st.columns(2)

    with col1:
        if h1_validada and h2_validada and h3a_validada:
            st.success("""
✅ **TODAS LAS HIPÓTESIS VALIDADAS**

La auditoría de datos demuestra:
- Normalización exitosa de claves
- Detección de inconsistencias de odómetro
- Identificación de consumos anómalos

Pipeline de auditoría **CONFIABLE**
            """)
        else:
            st.warning("""
⚠️ **VALIDACIÓN PARCIAL**

Revisar los tabs individuales para detalles sobre las hipótesis pendientes.
            """)

    with col2:
        st.info("""
📊 **Metodología de Validación**

Cada hipótesis incluye:
- Ejemplos ANTES Y DESPUÉS
- Métricas cuantitativas
- Casos de estudio específicos
- Criterios de validación claros

Los datos están listos para análisis posterior.
        """)
