"""Dataset exploration and filtering page.

Página "Datasets" (explicación en español):

- Qué muestra: permite elegir una tabla de los datos sintéticos (flota,
  telemetría, consumo, solicitudes, facturación, la verdad de referencia y, en
  el escenario realista, algunas tablas extra), ver qué representa cada fila y
  cada columna, buscar texto, filtrar por valores de columnas, ver estadísticas
  y descargar el resultado en CSV, Excel o JSON.
- Para qué la usa quien audita: para mirar los datos "crudos" fila por fila,
  ubicar casos concretos (por ejemplo, todas las cargas de una patente) y
  exportarlos para revisarlos en otra herramienta o adjuntarlos a un informe.
- Cómo encaja en la app: no calcula ni detecta nada; muestra las mismas tablas
  que usan las páginas de análisis y detección, y toma las descripciones del
  diccionario de datos que escribe el generador.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
# Permite importar los módulos de streamlit_app/utils/ (por ejemplo data_loader).
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))
from tarjetas import tarjeta  # noqa: E402

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
# Tarjeta de marco rosa que explica esta página en palabras simples (textos en utils/tarjetas.py)
tarjeta("datasets")
st.markdown("Visualiza, filtra y analiza todos los datasets del proyecto")

# Escenario elegido en la barra lateral (se recuerda en st.session_state entre
# páginas) y, si todavía no hay datos en disco, se generan con la semilla por defecto.
escenario = selector_escenario()
asegurar_datos_maestro(escenario)

# Nombres de dos tablas especiales, guardados en variables porque se comparan más
# abajo para mostrarles una explicación propia. El "ground truth" (verdad de
# referencia) es la lista de anomalías que el generador inyectó a propósito: se
# usa solo para medir si la detección acierta, nunca como dato de entrada.
GROUND_TRUTH = "🎯 Ground truth (anomalías inyectadas)"
LEGITIMOS = "✅ Casos legítimos (parecen anomalías)"

# etiqueta: (tabla del diccionario, datos)
# Cada load_* lee un CSV (con caché, para no releerlo en cada interacción).
fuentes = {
    "🚗 Flota": ("flota", load_flota(escenario)),
    "📡 Telemetría": ("telemetria", load_telemetria(escenario)),
    "⛽ Consumo": ("consumo", load_consumo_maestro(escenario)),
    "📋 Solicitudes": ("solicitudes", load_solicitudes(escenario)),
    "💰 Facturación": ("facturacion", load_facturacion(escenario)),
    GROUND_TRUTH: ("ground_truth", load_ground_truth_maestro(escenario)),
}
# El escenario realista tiene tablas que el didáctico no genera.
if escenario == "realista":
    fuentes.update({
        "⛽ Estaciones": ("estaciones", load_estaciones(escenario)),
        "🧾 Detalle de facturación": ("facturacion_detalle", load_facturacion_detalle(escenario)),
        "🛰️ Telemetría diaria": ("telemetria_diaria", load_telemetria_diaria(escenario)),
        LEGITIMOS: ("casos_legitimos", load_casos_legitimos(escenario)),
    })
# Versión simplificada: solo etiqueta -> datos, para el selector de abajo.
datasets = {etiqueta: df for etiqueta, (_, df) in fuentes.items()}
# El diccionario describe cada tabla (grano, clave y columnas); lo escribe el generador.
diccionario = load_diccionario(escenario)

st.caption("📖 El diccionario completo y el diagrama de relaciones entre tablas están en la página "
           "**Diccionario de datos** (menú lateral).")

# Dataset selector
# key="dataset_select" le da un nombre fijo al control. Streamlit usa ese nombre
# para recordar el valor elegido en st.session_state y para no confundirlo con
# otros controles parecidos de la página.
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
# Busca la descripción de la tabla elegida. "Grano" es qué representa una fila
# (por ejemplo, una carga de combustible); "clave" es la columna que identifica
# cada fila sin repetirse. Conocer ambos evita contar dos veces lo mismo.
tabla_diccionario = diccionario["tablas"].get(fuentes[selected_dataset][0])
if tabla_diccionario:
    st.caption(f"Grano: **{tabla_diccionario['grano']}** · Clave: `{tabla_diccionario['clave']}`")
    # st.expander es una sección plegable: se muestra cerrada y se abre con un clic.
    with st.expander("📖 Diccionario de columnas", expanded=False):
        st.dataframe(pd.DataFrame(tabla_diccionario["columnas"]).rename(
            columns={"nombre": "Columna", "tipo": "Tipo", "descripcion": "Descripción"}),
            use_container_width=True, hide_index=True)

if df.empty:
    st.warning(f"❌ El dataset '{selected_dataset}' está vacío")
    # st.stop() corta el script acá: sin filas no hay nada que filtrar ni mostrar.
    st.stop()

# Metrics
# Tamaño de la tabla y cantidad total de celdas vacías, en cuatro columnas.
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
    # La key incluye el nombre del dataset: así cada tabla tiene su propio cuadro
    # de búsqueda y lo escrito para una tabla no se aplica a otra.
    search_text = st.text_input(
        "Buscar en todas las columnas",
        key=f"search_text_{selected_dataset}"
    )

with col2:
    st.info("Escribe texto para filtrar resultados")

# Apply text filter
filtered_df = df.copy()
if search_text:
    # Convierte todas las celdas a texto y se queda con las filas en las que
    # alguna columna contiene lo buscado, sin distinguir mayúsculas de minúsculas.
    mask = df.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)
    filtered_df = df[mask]
    st.success(f"✅ {len(filtered_df)} registros coinciden con la búsqueda")

# Column-specific filters
# Primero se eligen las columnas; después, por cada una, aparece un selector con
# sus valores. Una fila queda si cumple todos los filtros elegidos a la vez.
st.markdown("### Filtros por columna")

filter_cols = st.multiselect(
    "Selecciona columnas para filtrar",
    df.columns,
    key=f"filter_cols_{selected_dataset}"
)

filters = {}
if filter_cols:
    filter_col1, filter_col2 = st.columns(2)

    # Reparte los selectores alternando entre la columna izquierda y la derecha.
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
# Los filtros por columna se aplican sobre el resultado de la búsqueda de texto.
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
# Solo se muestran las primeras filas (según el slider) para que la página no se
# vuelva lenta con tablas grandes; la exportación incluye todas las filas filtradas.
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
        # describe() calcula, por columna numérica, cantidad, promedio, desvío,
        # mínimo, cuartiles y máximo: sirve para detectar valores fuera de rango.
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
# Exporta lo que quedó después de buscar y filtrar, no la tabla completa.
st.markdown("---")
st.markdown("## 💾 Exportar")

export_format = st.selectbox(
    "Formato de exportación",
    ["CSV", "Excel", "JSON"],
    key=f"export_format_{selected_dataset}"
)

# Al tocar el primer botón se prepara el archivo y aparece un segundo botón
# (st.download_button), que es el que efectivamente descarga el archivo.
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
        # El Excel se escribe en memoria (BytesIO), no en el disco.
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
