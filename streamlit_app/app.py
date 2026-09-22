"""
Main Streamlit application for Dataset v5 Integration Pipeline.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
utils_path = Path(__file__).parent / "utils"
sys.path.insert(0, str(utils_path))

from data_loader import (
    get_all_datasets_info,
    load_vehiculo,
    load_reporte_consumo_vinculado,
    load_ground_truth,
    load_integracion_resumen
)

# Page config
st.set_page_config(
    page_title="Dataset v5 Integrator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #28a745;
    }
    .info-box {
        background-color: #d1ecf1;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #17a2b8;
    }
</style>
""", unsafe_allow_html=True)

# Title and introduction
st.markdown("# 📊 Dataset v5 Integration Pipeline")
st.markdown("**Sistema integral para gestión, visualización y análisis del dataset integrado**")

# Main metrics
st.markdown("## 📈 Estado General del Pipeline")

col1, col2, col3, col4 = st.columns(4)

# Load summary data
try:
    vehiculos = load_vehiculo()
    consumo = load_reporte_consumo_vinculado()
    ground_truth = load_ground_truth()
    integracion = load_integracion_resumen()

    with col1:
        st.metric("Vehículos", len(vehiculos), "200 total")

    with col2:
        st.metric("Transacciones", len(consumo), "1749 vinculadas")

    with col3:
        st.metric("Defectos", len(ground_truth), "104 inyectados")

    with col4:
        detectability = integracion.get("detectability", "94.2%")
        st.metric("Detectabilidad", detectability, "94.2% visible")

except Exception as e:
    st.error(f"Error loading data: {str(e)}")

# Info section
st.markdown("---")
st.markdown("## ℹ️ Navegación")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 🎯 1. Generador
    Ejecuta el generador de reportes de consumo
    - Configura periodos de generación
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
    ### 🔄 3. Pipeline
    Visualiza el flujo ETL completo
    - Pasos de transformación
    - Validaciones aplicadas
    - Estadísticas de cruces
    """)

# Status boxes
st.markdown("---")
st.markdown("## ✅ Estado de Consolidación")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="success-box">
        <h4>✅ Consolidación Completa</h4>
        <ul>
        <li>Dataset v5: 200 vehículos, 104 defectos</li>
        <li>Consumo vinculado: 1749 transacciones (100%)</li>
        <li>Integración: 100% de cruces exitosos</li>
        <li>4 Encuentros: Completados</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="info-box">
        <h4>📦 Archivos Disponibles</h4>
        <ul>
        <li>datasets/defects_aware_v5/ (7 archivos)</li>
        <li>results/integracion_cruces/ (2 archivos)</li>
        <li>results/4_encuentros/ (6 archivos)</li>
        <li>data/consumo/ (reportes Excel)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Datasets overview
st.markdown("---")
st.markdown("## 📂 Resumen de Datasets")

try:
    datasets_info = get_all_datasets_info()
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
except Exception as e:
    st.warning(f"Could not load datasets info: {str(e)}")

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
