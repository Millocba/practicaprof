"""
Main Streamlit application for the synthetic data pipeline (Pipeline Maestro).

Reads the same source as the Generador and Análisis pages
(datasets/synthetics_maestro). If the data is missing it is generated with the
default seed on first load (see data_loader.asegurar_datos_maestro).
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
utils_path = Path(__file__).parent / "utils"
sys.path.insert(0, str(utils_path))

from ayudas import seccion
from data_loader import (
    NOMBRES_ESCENARIO,
    selector_escenario,
    asegurar_datos_maestro,
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
seccion(
    "📊 Pipeline Maestro de Datos Sintéticos", nivel=1,
    ayuda="Portada del proyecto. Resume en qué estado está el pipeline y guía a las ocho páginas "
          "que lo componen. Todo lo que se ve acá se calcula desde los archivos generados, no está "
          "escrito a mano: si cambia el generador, esta pantalla cambia sola. Es el lugar para "
          "empezar si llegaste hace un rato y querés saber por dónde seguir.")
st.markdown("**Sistema integral para gestión, visualización y análisis del dataset integrado**")

# Load data (same source as the Generador and Análisis pages)
escenario = selector_escenario()
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** — se cambia en la barra lateral.")
asegurar_datos_maestro(escenario)
flota = load_flota(escenario)
telemetria = load_telemetria(escenario)
consumo = load_consumo_maestro(escenario)
solicitudes = load_solicitudes(escenario)
facturacion = load_facturacion(escenario)
metadata = load_maestro_metadata(escenario)

hay_datos = not flota.empty and not consumo.empty

# Main metrics
seccion(
    "📈 Estado General del Pipeline",
    ayuda="Cuatro cifras para saber si los datos están en orden. **Vinculación consumo ↔ flota** "
          "es la que hay que mirar: dice qué porcentaje de las cargas tiene un dominio que "
          "existe en la flota. Si baja del 100% no es necesariamente un error, porque el "
          "escenario realista inyecta dominios inválidos a propósito, pero conviene saber "
          "cuántos son antes de cruzar datos.")

if not hay_datos:
    st.warning(
        "⚠️ No se pudieron generar los datos automáticamente. "
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
seccion(
    "ℹ️ Navegación",
    ayuda="Las ocho páginas y para qué sirve cada una. No es un orden obligatorio:_generador y "
          "datasets son de preparación, y las cinco últimas son de análisis. Si querés entender "
          "el método de punta a punta, seguí el orden en que están; si ya sabés qué buscás, "
          "entrá directo por donde corresponda.")
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
    ### 🔍 3. Análisis por hipótesis
    Qué encuentran las reglas en los datos
    - Calidad de datos y vinculación
    - Una pestaña por hipótesis (H1 a H9)
    - Antes y después: regla ingenua vs. con contexto
    """)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 🎯 4. Detección
    Reglas base evaluadas contra el ground truth
    - Precision, recall y F1 por tipo y por regla
    - Umbral fijo vs. historial del vehículo
    - Explorador de errores
    """)

with col2:
    st.markdown("""
    ### 🧪 5. Hipótesis
    Análisis del escenario realista
    - Regla ingenua vs. regla con contexto
    - Falsas alarmas por casos legítimos
    - Veredicto de cada hipótesis
    """)

with col3:
    st.markdown("""
    ### 🤖 6. Modelo de ML
    Qué revisar primero
    - Cola de revisión con motivos
    - Curva de esfuerzo por método
    - Vehículos a auditar
    """)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 📖 7. Diccionario de datos
    Qué contiene cada tabla
    - Grano, clave y columnas
    - Diagrama de relaciones
    - Catálogos de anomalías y casos legítimos
    """)

with col2:
    st.markdown("""
    ### 📚 8. Documentación
    La documentación con valores actuales
    - Estado actual del proyecto
    - Bitácora de cambios
    - Descarga en .md o .zip
    """)

# Status boxes (computed from the loaded data, not hardcoded)
st.markdown("---")
seccion(
    "✅ Estado de la Generación",
    ayuda="De dónde salieron los archivos que está usando la app. La **semilla** y la **fecha** "
          "sirven para reproducir: con la misma semilla, el generador devuelve los mismos datos. "
          "Si regenerás con otra semilla, cambiás todos los números de análisis y las conclusiones "
          "de la bitácora quedan desactualizadas.")
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
seccion(
    "📂 Resumen de Datasets",
    ayuda="Inventario archivo por archivo: cuántas filas, cuántas columnas y cuánto pesan. Los "
          "**valores faltantes** no son necesariamente errores: el generador deja algunos campos "
          "vacíos a propósito para que las reglas de calidad tengan qué detectar, así que un "
          "número alto acá es parte del diseño y no una falla.")
try:
    datasets_info = get_maestro_datasets_info(escenario)
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
