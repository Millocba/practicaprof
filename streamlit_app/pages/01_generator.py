"""Generator execution page."""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from generator_runner import (
    check_generator_exists,
    run_generator,
    get_generated_files,
    load_generated_report
)

st.set_page_config(page_title="Generador", page_icon="🎯")

st.markdown("# 🎯 Generador de Reportes de Consumo")
st.markdown("Ejecuta el generador para crear nuevos reportes de consumo en formato YPF")

# Check if generator exists
if not check_generator_exists():
    st.error("❌ Generator script not found. Please check the installation.")
    st.stop()

# Section 1: Generator execution
st.markdown("## ⚙️ Ejecutar Generador")

col1, col2 = st.columns(2)

with col1:
    meses = st.slider(
        "Número de meses a generar",
        min_value=1,
        max_value=12,
        value=2,
        help="Especifica cuántos meses hacia atrás generar reportes"
    )

with col2:
    st.info(f"Se generarán reportes para los últimos {meses} mes(es)")

# Run button
if st.button("▶️ Ejecutar Generador", type="primary", use_container_width=True):
    with st.spinner("Generando reportes..."):
        result = run_generator(meses=meses)

        if result["success"]:
            st.success(result["message"])
            if "output" in result:
                with st.expander("📝 Detalles de ejecución"):
                    st.text(result["output"])
        else:
            st.error(result["message"])
            if "output" in result and result["output"]:
                with st.expander("📝 Detalles de error"):
                    st.text(result["output"])

# Section 2: Generated files
st.markdown("---")
st.markdown("## 📁 Archivos Generados")

generated_files = get_generated_files()

if generated_files:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Archivos", len(generated_files))
    with col2:
        total_size = sum(f["size_kb"] for f in generated_files)
        st.metric("Tamaño total", f"{total_size/1024:.2f} MB")
    with col3:
        st.metric("Período más reciente", generated_files[-1]["filename"])

    # File list with download buttons
    st.markdown("### Reportes disponibles:")

    for file_info in generated_files:
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.write(f"📄 {file_info['filename']}")
        with col2:
            st.write(f"{file_info['size_kb']:.0f} KB")
        with col3:
            with open(file_info['path'], 'rb') as f:
                st.download_button(
                    label="⬇️ Descargar",
                    data=f,
                    file_name=file_info['filename'],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=file_info['filename']
                )

    # Preview section
    st.markdown("### 👁️ Vista previa de datos")

    selected_file = st.selectbox(
        "Selecciona un archivo para previsualizar",
        [f['filename'] for f in generated_files],
        key="file_select"
    )

    if selected_file:
        file_path = None
        for f in generated_files:
            if f['filename'] == selected_file:
                file_path = f['path']
                break

        if file_path:
            try:
                df = load_generated_report(file_path)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Registros", len(df))
                with col2:
                    st.metric("Columnas", len(df.columns))
                with col3:
                    st.metric("Tamaño", f"{df.memory_usage(deep=True).sum()/1024/1024:.2f} MB")

                # Data display
                st.markdown("**Primeros 10 registros:**")
                st.dataframe(df.head(10), use_container_width=True)

                # Summary statistics
                st.markdown("**Estadísticas:**")
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    st.dataframe(df[numeric_cols].describe(), use_container_width=True)

                # Column info
                st.markdown("**Información de columnas:**")
                col_info = pd.DataFrame({
                    'Columna': df.columns,
                    'Tipo': df.dtypes.astype(str),
                    'No nulos': df.count(),
                    'Nulos': df.isnull().sum()
                })
                st.dataframe(col_info, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Error loading file: {str(e)}")

else:
    st.info("No hay archivos generados aún. Ejecuta el generador para crear los primeros reportes.")

# Section 3: Configuration info
st.markdown("---")
st.markdown("## 📋 Configuración del Generador")

st.markdown("""
### Parámetros disponibles:

- **--meses N**: Número de meses a generar (por defecto: 2)
- **Seed**: Fijo en 20260906 para reproducibilidad
- **Transacciones por día**: 33 (TX_POR_DIA)

### Características:

✅ Genera reportes en formato YPF
✅ Vinculación automática a flota v5
✅ Anomalías de odómetro inyectadas
✅ Salida en formato Excel (.xlsx)
✅ Normalización de dominios

### Ubicación de salida:

Los reportes se guardan en: `data/consumo/ReporteConsumos_YYYYMM.xlsx`
""")
