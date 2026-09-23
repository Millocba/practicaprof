"""
Main Streamlit application for the synthetic data pipeline (Pipeline Maestro).

Reads the same source as the Generador and Análisis pages
(datasets/synthetics_maestro), which is created at runtime by the Generador.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
utils_path = Path(__file__).parent / "utils"
sys.path.insert(0, str(utils_path))

from data_loader import (
    load_flota,
    load_telemetria,
    load_consumo_maestro,
    load_solicitudes,
    load_facturacion,
    load_maestro_metadata,
    get_maestro_datasets_info,
)

# Page config
st.set_page_config(
    page_title="Pipeline Maestro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #28a745;
    }
    .info-box {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #17a2b8;
    }
</style>
""", unsafe_allow_html=True)

# Title and introduction
st.markdown("# 📊 Pipeline Maestro de Datos Sintéticos")
st.markdown("**Sistema integral para gestión, visualización y análisis del dataset integrado**")

# Load data (same source as the Generador and Análisis pages)
flota = load_flota()
telemetria = load_telemetria()
consumo = load_consumo_maestro()
solicitudes = load_solicitudes()
facturacion = load_facturacion()
metadata = load_maestro_metadata()

hay_datos = not flota.empty and not consumo.empty

# Main metrics
st.markdown("## 📈 Estado General del Pipeline")

if not hay_datos:
    st.warning(
        "⚠️ Todavía no hay datos generados en esta sesión. "
        "Abrí la página **Generador** en el menú lateral y presioná **🚀 Ejecutar Generador**; "
        "después volvé a esta página."
    )

col1, col2, col3, col4 = st.columns(4)

try:
    with col1:
        if not flota.empty:
            st.metric("Vehículos", f"{len(flota):,}")
            if "Estado" in flota.columns:
                activos = (flota["Estado"] != "BAJA").sum()
                st.caption(f"{activos:,} no dados de baja")
        else:
            st.metric("Vehículos", "—")
            st.caption("sin datos")

    with col2:
        if not consumo.empty:
            st.metric("Transacciones de consumo", f"{len(consumo):,}")
            if "litros" in consumo.columns:
                litros = pd.to_numeric(consumo["litros"], errors="coerce").sum()
                st.caption(f"{litros:,.0f} litros en total")
        else:
            st.metric("Transacciones de consumo", "—")
            st.caption("sin datos")

    with col3:
        if hay_datos and {"dominio"} <= set(consumo.columns) and {"Dominio"} <= set(flota.columns):
            vinculadas = consumo["dominio"].isin(flota["Dominio"]).sum()
            pct = vinculadas / len(consumo) * 100
            st.metric("Vinculación consumo ↔ flota", f"{pct:.1f}%")
            st.caption(f"{vinculadas:,} de {len(consumo):,} transacciones")
        else:
            st.metric("Vinculación consumo ↔ flota", "—")
            st.caption("sin datos")

    with col4:
        if not facturacion.empty and "monto_total_con_iva" in facturacion.columns:
            monto = pd.to_numeric(facturacion["monto_total_con_iva"], errors="coerce").sum()
            st.metric("Facturación (con IVA)", f"${monto:,.0f}")
            st.caption(f"{len(facturacion):,} facturas")
        else:
            st.metric("Facturación (con IVA)", "—")
            st.caption("sin datos")

except Exception as e:
    st.error(f"❌ Error al mostrar KPIs: {str(e)}")

# Info section
st.markdown("---")
st.markdown("## ℹ️ Navegación")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 🎯 1. Generador
    Ejecuta el pipeline maestro de entidades sintéticas
    - Configura cantidad de vehículos y seed
    - Visualiza resultados
    - Descarga archivos
    """)

with col2:
    st.markdown("""
    ### 📋 2. Datasets
    Explora y filtra los datos del proyecto
    - Visualiza toda la información
    - Aplica filtros y búsquedas
    - Exporta datos
    """)

with col3:
    st.markdown("""
    ### 🔍 3. Análisis Maestro
    Valida las hipótesis H1 a H3a
    - Vinculaciones entre entidades
    - Anomalías de odómetro
    - Ejemplos antes y después
    """)

# Status boxes (computed from the loaded data, not hardcoded)
st.markdown("---")
st.markdown("## ✅ Estado de la Generación")

col1, col2 = st.columns(2)

with col1:
    if hay_datos:
        fecha = str(metadata.get("fecha_generacion", "—"))[:19].replace("T", " ")
        st.markdown(f"""
        <div class="success-box">
            <h4>✅ Datos generados</h4>
            <ul>
            <li>Fecha de generación: {fecha}</li>
            <li>Seed: {metadata.get("seed", "—")}</li>
            <li>Vehículos solicitados: {metadata.get("n_flota", "—")}</li>
            <li>Generadores ejecutados: {len(metadata.get("generadores_ejecutados", []))}</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-box">
            <h4>⏳ Sin datos generados</h4>
            <p>Ejecutá el Generador para crear las entidades sintéticas.</p>
        </div>
        """, unsafe_allow_html=True)

with col2:
    entidades = {
        "Flota": flota,
        "Telemetría": telemetria,
        "Consumo": consumo,
        "Solicitudes": solicitudes,
        "Facturación": facturacion,
    }
    items = "".join(
        f"<li>{nombre}: {len(df):,} registros</li>" if not df.empty
        else f"<li>{nombre}: sin datos</li>"
        for nombre, df in entidades.items()
    )
    st.markdown(f"""
    <div class="info-box">
        <h4>📦 Entidades disponibles</h4>
        <ul>{items}</ul>
    </div>
    """, unsafe_allow_html=True)

# Datasets overview
st.markdown("---")
st.markdown("## 📂 Resumen de Datasets")

try:
    datasets_info = get_maestro_datasets_info()
    if not datasets_info.empty:
        st.dataframe(
            datasets_info,
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Dataset"),
                "rows": st.column_config.NumberColumn("Registros", format="%d"),
                "columns": st.column_config.NumberColumn("Columnas", format="%d"),
                "size_mb": st.column_config.NumberColumn("Tamaño (MB)", format="%.2f"),
                "missing": st.column_config.NumberColumn("Valores faltantes", format="%d"),
            }
        )
    else:
        st.info("No hay datasets para mostrar todavía.")
except Exception as e:
    st.warning(f"No se pudo cargar el resumen de datasets: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #999;">
    <small>
    Sprint 1 - Consolidado 2026-09-22<br>
    Fase 1: Integración ✅ | Fase 2: ML Models | Fase 3: Análisis Profundo<br>
    Estado: LISTO PARA FASE 2
    </small>
</div>
""", unsafe_allow_html=True)
