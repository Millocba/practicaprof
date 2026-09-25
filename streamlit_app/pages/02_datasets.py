"""Dataset exploration and filtering page."""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from data_loader import (
    selector_escenario,
    load_diccionario,
    load_casos_legitimos,
    load_estaciones,
    load_facturacion_detalle,
    load_telemetria_diaria,
    asegurar_datos_maestro,
    load_flota,
    load_telemetria,
    load_consumo_maestro,
    load_solicitudes,
    load_facturacion,
    load_ground_truth_maestro,
    filter_dataframe
)

st.set_page_config(page_title="Datasets", page_icon="📋", layout="wide")

st.markdown("# 📋 Exploración de Datasets")
st.markdown("Visualiza, filtra y analiza todos los datasets del proyecto")

escenario = selector_escenario()
asegurar_datos_maestro(escenario)

GROUND_TRUTH = "🎯 Ground truth (anomalías inyectadas)"
LEGITIMOS = "✅ Casos legítimos (parecen anomalías)"

# etiqueta: (tabla del diccionario, datos)
fuentes = {
    "🚗 Flota": ("flota", load_flota(escenario)),
    "📡 Telemetría": ("telemetria", load_telemetria(escenario)),
    "⛽ Consumo": ("consumo", load_consumo_maestro(escenario)),
    "📋 Solicitudes": ("solicitudes", load_solicitudes(escenario)),
    "💰 Facturación": ("facturacion", load_facturacion(escenario)),
    GROUND_TRUTH: ("ground_truth", load_ground_truth_maestro(escenario)),
}
if escenario == "realista":
    fuentes.update({
        "⛽ Estaciones": ("estaciones", load_estaciones(escenario)),
        "🧾 Detalle de facturación": ("facturacion_detalle", load_facturacion_detalle(escenario)),
        "🛰️ Telemetría diaria": ("telemetria_diaria", load_telemetria_diaria(escenario)),
        LEGITIMOS: ("casos_legitimos", load_casos_legitimos(escenario)),
    })
datasets = {etiqueta: df for etiqueta, (_, df) in fuentes.items()}
diccionario = load_diccionario(escenario)

with st.expander("🔗 Relaciones entre tablas", expanded=False):
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from generator_pipeline_maestro import diagrama_relaciones
    st.graphviz_chart(diagrama_relaciones(diccionario), use_container_width=True)
    relaciones = pd.DataFrame(diccionario["relaciones"])
    if not relaciones.empty:
        st.dataframe(relaciones.rename(columns={
            "origen": "Tabla", "columna_origen": "Columna", "destino": "Se relaciona con",
            "columna_destino": "Columna destino", "cardinalidad": "Cardinalidad", "nota": "Nota"}),
            use_container_width=True, hide_index=True)
    st.caption("Las líneas punteadas no son claves: se resuelven por emparejamiento o agregación. "
               "En naranja, las tablas de evaluación (no son entradas de las reglas ni de los modelos).")

# Dataset selector
selected_dataset = st.selectbox(
    "Selecciona un dataset:",
    list(datasets.keys()),
    key="dataset_select"
)

if selected_dataset == LEGITIMOS:
    st.info(
        "ℹ️ Cargas legítimas que una regla ingenua marcaría como anomalía: tanques no registrados, "
        "viajes largos, odómetros reemplazados y errores de tipeo. Sirven para medir las falsas alarmas."
    )
if selected_dataset == GROUND_TRUTH:
    st.info(
        "ℹ️ Verdad de referencia: una fila por anomalía que inyectó el generador. "
        "Sirve para evaluar la detección; no es una entidad ni una entrada de los modelos."
    )

# Get the dataframe
df = datasets[selected_dataset]
tabla_diccionario = diccionario["tablas"].get(fuentes[selected_dataset][0])
if tabla_diccionario:
    st.caption(f"Grano: **{tabla_diccionario['grano']}** · Clave: `{tabla_diccionario['clave']}`")
    with st.expander("📖 Diccionario de columnas", expanded=False):
        st.dataframe(pd.DataFrame(tabla_diccionario["columnas"]).rename(
            columns={"nombre": "Columna", "tipo": "Tipo", "descripcion": "Descripción"}),
            use_container_width=True, hide_index=True)

if df.empty:
    st.warning(f"❌ El dataset '{selected_dataset}' está vacío")
    st.stop()

# Metrics
st.markdown(f"## 📊 {selected_dataset}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Registros", len(df))
with col2:
    st.metric("Columnas", len(df.columns))
with col3:
    st.metric("Memoria", f"{df.memory_usage(deep=True).sum()/1024/1024:.2f} MB")
with col4:
    st.metric("Datos faltantes", df.isnull().sum().sum())

# Filters
st.markdown("---")
st.markdown("## 🔍 Filtros")

col1, col2 = st.columns(2)

with col1:
    search_text = st.text_input(
        "Buscar en todas las columnas",
        key=f"search_text_{selected_dataset}"
    )

with col2:
    st.info("Escribe texto para filtrar resultados")

# Apply text filter
filtered_df = df.copy()
if search_text:
    mask = df.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)
    filtered_df = df[mask]
    st.success(f"✅ {len(filtered_df)} registros coinciden con la búsqueda")

# Column-specific filters
st.markdown("### Filtros por columna")

filter_cols = st.multiselect(
    "Selecciona columnas para filtrar",
    df.columns,
    key=f"filter_cols_{selected_dataset}"
)

filters = {}
if filter_cols:
    filter_col1, filter_col2 = st.columns(2)

    for i, col in enumerate(filter_cols):
        if i % 2 == 0:
            container = filter_col1
        else:
            container = filter_col2

        with container:
            # Hasta 100 valores; key=str permite ordenar columnas con tipos mezclados
            unique_values = sorted(df[col].dropna().unique()[:100], key=str)

            selected_values = st.multiselect(
                f"Filtrar {col}",
                unique_values,
                key=f"filter_{selected_dataset}_{col}"
            )

            if selected_values:
                filters[col] = selected_values

# Apply column filters
if filters:
    filtered_df = filter_dataframe(filtered_df, filters)
    st.success(f"✅ {len(filtered_df)} registros después de aplicar filtros")

# Data display
st.markdown("---")
st.markdown(f"## 📈 Datos ({len(filtered_df)} registros)")

# Display options
col1, col2, col3 = st.columns(3)
with col1:
    rows_to_show = st.slider("Registros a mostrar", 10, 1000, 100, step=10)
with col2:
    show_stats = st.checkbox("Mostrar estadísticas", value=True)
with col3:
    show_info = st.checkbox("Mostrar información de columnas", value=False)

# Display dataframe
st.dataframe(
    filtered_df.head(rows_to_show),
    use_container_width=True,
    height=400
)

# Statistics
if show_stats and len(filtered_df) > 0:
    st.markdown("### 📊 Estadísticas")

    numeric_cols = filtered_df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        st.dataframe(
            filtered_df[numeric_cols].describe(),
            use_container_width=True
        )
    else:
        st.info("No hay columnas numéricas en este dataset")

# Column info
if show_info and len(filtered_df) > 0:
    st.markdown("### 📋 Información de Columnas")

    col_info = pd.DataFrame({
        'Columna': filtered_df.columns,
        'Tipo': filtered_df.dtypes.astype(str),
        'No nulos': filtered_df.count(),
        'Nulos': filtered_df.isnull().sum(),
        'Únicos': [filtered_df[col].nunique() for col in filtered_df.columns]
    })

    st.dataframe(col_info, use_container_width=True, hide_index=True)

# Export
st.markdown("---")
st.markdown("## 💾 Exportar")

export_format = st.selectbox(
    "Formato de exportación",
    ["CSV", "Excel", "JSON"],
    key=f"export_format_{selected_dataset}"
)

if st.button("⬇️ Descargar datos", use_container_width=True, type="primary"):
    if export_format == "CSV":
        csv_data = filtered_df.to_csv(index=False)
        st.download_button(
            label="Descargar CSV",
            data=csv_data,
            file_name=f"{selected_dataset.replace(' ', '_')}.csv",
            mime="text/csv"
        )
    elif export_format == "Excel":
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Data')
        st.download_button(
            label="Descargar Excel",
            data=buffer.getvalue(),
            file_name=f"{selected_dataset.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif export_format == "JSON":
        json_data = filtered_df.to_json(orient='records', indent=2)
        st.download_button(
            label="Descargar JSON",
            data=json_data,
            file_name=f"{selected_dataset.replace(' ', '_')}.json",
            mime="application/json"
        )

# Footer
st.markdown("---")
st.markdown(f"""
### 💡 Tips
- Usa la búsqueda para encontrar datos específicos
- Filtra por columna para análisis detallado
- Exporta los datos para procesamiento externo
- Puedes combinar múltiples filtros
""")
