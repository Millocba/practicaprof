"""Analysis and visualization page."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

# Add utils to path
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from data_loader import (
    load_vehiculo,
    load_reporte_consumo_vinculado,
    load_ground_truth,
    load_dispositivo
)

st.set_page_config(page_title="Análisis", page_icon="📈", layout="wide")

st.markdown("# 📈 Análisis y Visualizaciones")
st.markdown("Exploraciones visuales de los datos del proyecto")

# Load data
vehiculos = load_vehiculo()
consumo = load_reporte_consumo_vinculado()
ground_truth = load_ground_truth()
dispositivos = load_dispositivo()

# Tabs for different analyses
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Consumo", "🚗 Vehículos", "🐛 Defectos", "📍 Dispositivos"]
)

# Tab 1: Consumption analysis
with tab1:
    st.markdown("## Análisis de Consumo")

    if not consumo.empty:
        col1, col2, col3 = st.columns(3)

        # Try to convert numeric columns
        numeric_cols = ['LITROS UNIDADES', 'PRECIO PVP ESTABLECIMIENTO', 'IMP TOT PVP ESTABLECIMIENTO']
        for col in numeric_cols:
            if col in consumo.columns:
                consumo[col] = pd.to_numeric(consumo[col], errors='coerce')

        with col1:
            total_litros = consumo['LITROS UNIDADES'].sum()
            st.metric("Total litros", f"{total_litros:.0f}L", "Período completo")

        with col2:
            avg_litros = consumo['LITROS UNIDADES'].mean()
            st.metric("Promedio por tx", f"{avg_litros:.1f}L", "Por transacción")

        with col3:
            num_vehicles = consumo['DOMINIO'].nunique()
            st.metric("Vehículos activos", num_vehicles, "Con consumo")

        # Charts
        col1, col2 = st.columns(2)

        with col1:
            # Distribution of liters
            fig = px.histogram(
                consumo,
                x='LITROS UNIDADES',
                nbins=30,
                title='Distribución de Litros por Transacción',
                labels={'LITROS UNIDADES': 'Litros'}
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Top vehicles by consumption
            if 'DOMINIO' in consumo.columns:
                top_vehicles = consumo.groupby('DOMINIO')['LITROS UNIDADES'].sum().nlargest(10)
                fig = px.bar(
                    x=top_vehicles.values,
                    y=top_vehicles.index,
                    orientation='h',
                    title='Top 10 Vehículos por Consumo',
                    labels={'x': 'Litros', 'y': 'Dominio'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        # Price analysis
        col1, col2 = st.columns(2)

        with col1:
            if 'PRECIO PVP ESTABLECIMIENTO' in consumo.columns:
                fig = px.box(
                    consumo,
                    y='PRECIO PVP ESTABLECIMIENTO',
                    title='Distribución de Precios',
                    labels={'PRECIO PVP ESTABLECIMIENTO': 'Precio ($)'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            if 'IMP TOT PVP ESTABLECIMIENTO' in consumo.columns:
                monthly_total = consumo.copy()
                if 'FECHA' in monthly_total.columns:
                    monthly_total['Mes'] = pd.to_datetime(monthly_total['FECHA'], errors='coerce').dt.to_period('M')
                    monthly_sales = monthly_total.groupby('Mes')['IMP TOT PVP ESTABLECIMIENTO'].sum()

                    fig = px.line(
                        x=monthly_sales.index.astype(str),
                        y=monthly_sales.values,
                        title='Importe Total por Mes',
                        labels={'x': 'Mes', 'y': 'Importe ($)'}
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos de consumo disponibles")

# Tab 2: Vehicle analysis
with tab2:
    st.markdown("## Análisis de Vehículos")

    if not vehiculos.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total vehículos", len(vehiculos), "v5 Defects-Aware")

        with col2:
            defects_per_vehicle = len(ground_truth) / len(vehiculos)
            st.metric("Defectos por vehículo", f"{defects_per_vehicle:.2f}", "Promedio")

        # Vehicle distribution
        col1, col2 = st.columns(2)

        with col1:
            # Vehicles by state
            if 'Estado' in vehiculos.columns:
                state_counts = vehiculos['Estado'].value_counts()
                fig = px.pie(
                    values=state_counts.values,
                    names=state_counts.index,
                    title='Vehículos por Estado'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Tank capacity distribution
            numeric_cols = vehiculos.select_dtypes(include=['number']).columns
            if 'CapacidadTanque' in vehiculos.columns or len(numeric_cols) > 0:
                cap_col = 'CapacidadTanque' if 'CapacidadTanque' in vehiculos.columns else numeric_cols[0]
                vehiculos[cap_col] = pd.to_numeric(vehiculos[cap_col], errors='coerce')

                fig = px.histogram(
                    vehiculos,
                    x=cap_col,
                    nbins=20,
                    title='Distribución de Capacidad de Tanque',
                    labels={cap_col: 'Capacidad (L)'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos de vehículos disponibles")

# Tab 3: Defects analysis
with tab3:
    st.markdown("## Análisis de Defectos")

    if not ground_truth.empty:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total defectos", len(ground_truth), "104 inyectados")

        with col2:
            if 'detectable' in ground_truth.columns:
                detectable = (ground_truth['detectable'] == True).sum()
                st.metric("Detectables", detectable, f"{100*detectable/len(ground_truth):.1f}%")

        with col3:
            if 'tipo' in ground_truth.columns:
                unique_types = ground_truth['tipo'].nunique()
                st.metric("Tipos de defecto", unique_types, "Categorías")

        # Defect type distribution
        if 'tipo' in ground_truth.columns:
            col1, col2 = st.columns(2)

            with col1:
                tipo_counts = ground_truth['tipo'].value_counts()
                fig = px.bar(
                    x=tipo_counts.index,
                    y=tipo_counts.values,
                    title='Distribución de Tipos de Defecto',
                    labels={'x': 'Tipo', 'y': 'Cantidad'}
                )
                fig.update_layout(height=400, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                if 'detectable' in ground_truth.columns:
                    detectable_by_type = ground_truth.groupby('tipo')['detectable'].apply(
                        lambda x: (x == True).sum() / len(x) * 100
                    )
                    fig = px.bar(
                        x=detectable_by_type.index,
                        y=detectable_by_type.values,
                        title='Detectabilidad por Tipo (%)',
                        labels={'x': 'Tipo', 'y': 'Detectabilidad (%)'}
                    )
                    fig.update_layout(height=400, xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)

        # Defect details
        st.markdown("### Detalles de Defectos")
        st.dataframe(ground_truth.head(20), use_container_width=True)
    else:
        st.warning("No hay datos de defectos disponibles")

# Tab 4: Device analysis
with tab4:
    st.markdown("## Análisis de Dispositivos")

    if not dispositivos.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total dispositivos", len(dispositivos), "GPS/GPRS")

        with col2:
            if 'Dominio' in dispositivos.columns:
                active_devices = dispositivos['Dominio'].nunique()
                st.metric("Dispositivos activos", active_devices, f"{100*active_devices/len(dispositivos):.1f}%")

        # Device info
        st.markdown("### Información de Dispositivos")
        st.dataframe(dispositivos.head(10), use_container_width=True)
    else:
        st.warning("No hay datos de dispositivos disponibles")

# Footer
st.markdown("---")
st.markdown("""
### 📊 Análisis disponibles:
- **Consumo**: Distribución de litros, precios, vehículos principales
- **Vehículos**: Estado, capacidad de tanque, distribución
- **Defectos**: Tipos, detectabilidad, distribución
- **Dispositivos**: Cobertura, información técnica

### 🔄 Próximas visualizaciones:
- Análisis de correlaciones
- PCA (Principal Component Analysis)
- Clustering de patrones
- Gráficos interactivos avanzados
""")
