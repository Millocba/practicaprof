"""
Main Streamlit application for the synthetic data pipeline (Pipeline Maestro).

Reads the same source as the Generador and Análisis pages
(datasets/synthetics_maestro). If the data is missing it is generated with the
default seed on first load (see data_loader.asegurar_datos_maestro).

Página de inicio de la aplicación (en español, para quien recién empieza):

- Qué muestra: un tablero con los números principales de los datos sintéticos
  (cantidad de vehículos, transacciones de consumo, qué porcentaje del consumo
  se puede vincular con un vehículo de la flota y el total facturado), un mapa
  de las demás páginas, cuándo y con qué parámetros se generaron los datos, y
  una tabla con el tamaño de cada dataset.
- Para qué la usa quien audita: es el punto de partida. De un vistazo confirma
  que hay datos cargados, que el volumen es razonable y que la vinculación
  consumo ↔ flota es alta; si algo se ve raro, sabe a qué página ir para
  investigar.
- Cómo encaja en la app: Streamlit arma el menú lateral solo, con este archivo
  como "Inicio" y cada archivo de la carpeta pages/ como una página más. Esta
  página no calcula nada propio: lee los mismos CSV que el resto de las páginas
  mediante las funciones de utils/data_loader.py.

Cómo funciona Streamlit, en dos ideas:
- Este archivo es un "script" que se ejecuta entero, de arriba a abajo, cada
  vez que alguien abre la página o toca cualquier control (un botón, un
  selector, etc.). Cada `st.algo(...)` dibuja un elemento en pantalla en el
  orden en que aparece.
- Como el script se re-ejecuta tan seguido, las funciones que leen archivos
  usan una caché (`st.cache_data`, en data_loader.py): la primera vez leen el
  CSV del disco y las siguientes devuelven el resultado guardado en memoria.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add utils to path
# Se agrega la carpeta utils/ a la lista de lugares donde Python busca módulos,
# para poder hacer `from data_loader import ...` aunque no sea un paquete instalado.
utils_path = Path(__file__).parent / "utils"
sys.path.insert(0, str(utils_path))

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
# set_page_config define el título de la pestaña del navegador, el ícono y el
# ancho de la página. Tiene que ser la primera instrucción de Streamlit del script.
st.set_page_config(
    page_title="Pipeline Maestro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
# Estilos propios para las cajas de color de la sección "Estado de la Generación".
# unsafe_allow_html=True le permite a st.markdown interpretar HTML/CSS en lugar
# de mostrarlo como texto; se usa solo con contenido escrito por el proyecto.
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
# El "escenario" elige qué juego de datos sintéticos se usa: el realista (anomalías
# sutiles y casos legítimos que se les parecen) o el didáctico (anomalías obvias).
# selector_escenario() dibuja la opción en la barra lateral y guarda la elección en
# st.session_state: una especie de "memoria" que Streamlit conserva entre
# re-ejecuciones y entre páginas, así el escenario elegido vale en toda la app.
escenario = selector_escenario()
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** — se cambia en la barra lateral.")
# Si todavía no hay datos en disco (por ejemplo, la primera vez o después de un
# reinicio en la nube), los genera con la semilla por defecto antes de seguir.
asegurar_datos_maestro(escenario)
# Cada load_* lee un CSV y lo devuelve como DataFrame (una tabla de pandas).
# Si el archivo no existe, devuelve una tabla vacía en lugar de fallar.
flota = load_flota(escenario)
telemetria = load_telemetria(escenario)
consumo = load_consumo_maestro(escenario)
solicitudes = load_solicitudes(escenario)
facturacion = load_facturacion(escenario)
metadata = load_maestro_metadata(escenario)

# Sin flota o sin consumo no tiene sentido calcular los indicadores: son las dos
# tablas sobre las que se apoya el resto del análisis.
hay_datos = not flota.empty and not consumo.empty

# Main metrics
# Indicadores principales (KPIs). Sirven para comprobar rápido que los datos
# tienen el volumen esperado antes de analizarlos.
st.markdown("## 📈 Estado General del Pipeline")

if not hay_datos:
    st.warning(
        "⚠️ No se pudieron generar los datos automáticamente. "
        "Abrí la página **Generador** en el menú lateral y presioná **🚀 Ejecutar Generador**; "
        "después volvé a esta página."
    )

# st.columns(4) divide el ancho de la página en 4 columnas. Todo lo que se
# dibuja dentro de un bloque `with colN:` aparece en esa columna.
col1, col2, col3, col4 = st.columns(4)

# El try/except evita que un dato con formato inesperado rompa toda la página:
# si falla, se muestra un mensaje de error y el resto de la página sigue.
try:
    with col1:
        if not flota.empty:
            # st.metric muestra un número grande con su título; st.caption, un texto chico debajo.
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
                # to_numeric con errors="coerce" convierte a número y deja vacío lo
                # que no se pueda convertir, para que un valor mal cargado no impida sumar.
                litros = pd.to_numeric(consumo["litros"], errors="coerce").sum()
                st.caption(f"{litros:,.0f} litros en total")
        else:
            st.metric("Transacciones de consumo", "—")
            st.caption("sin datos")

    with col3:
        # Vinculación: qué porcentaje de las cargas de combustible tiene una patente
        # (dominio) que existe en la flota. Una carga que no se puede vincular con
        # ningún vehículo es, en sí misma, algo que quien audita querría revisar.
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
# Mapa de la app: una tarjeta por página, en filas de tres columnas. Es texto
# fijo; la navegación real se hace desde el menú lateral.
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

with col3:
    st.markdown("""
    ### 🔬 9. Perfil de fuentes
    Qué le falta al generador
    - Estructura y calidad, sin guardar datos
    - Comparación con los datos sintéticos
    - Informe de brechas con sugerencias
    """)

# Status boxes (computed from the loaded data, not hardcoded)
# Izquierda: con qué parámetros se generaron los datos (sale de metadata.json).
# Saber la semilla permite volver a generar exactamente los mismos datos, lo que
# hace que cualquier hallazgo se pueda reproducir. Derecha: filas por entidad.
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
    # Arma la lista HTML: una línea por tabla, con su cantidad de registros o "sin datos".
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
# Tabla resumen de todos los archivos: registros, columnas, tamaño y valores
# faltantes. Muchos faltantes en una columna es una primera señal de mala calidad.
st.markdown("---")
st.markdown("## 📂 Resumen de Datasets")

try:
    datasets_info = get_maestro_datasets_info(escenario)
    if not datasets_info.empty:
        # st.dataframe muestra una tabla interactiva (se puede ordenar y buscar).
        # column_config solo cambia los títulos y el formato de cada columna en pantalla.
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
