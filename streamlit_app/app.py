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
sys.path.insert(0, str(Path(__file__).parent.parent))

from deteccion.reglas import normalizar_dominio  # noqa: E402
from ayudas import seccion, tarjeta  # noqa: E402
from explicaciones import camino_completo  # noqa: E402
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
    ayuda="Portada del proyecto. Resume en qué estado está el pipeline y guía a las páginas "
          "que lo componen. Todo lo que se ve acá se calcula desde los archivos generados, no "
          "está escrito a mano: si cambia el generador, esta pantalla cambia sola. Es el lugar "
          "para empezar si llegaste hace un rato y querés saber por dónde seguir.")
st.markdown("**Sistema integral para gestión, visualización y análisis del dataset integrado**")
camino_completo()

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
                activos = (~flota["Estado"].astype(str).str.contains("BAJA")).sum()
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
            normalizadas = normalizar_dominio(consumo["dominio"]).isin(set(normalizar_dominio(flota["Dominio"]))).sum()
            st.metric("Vinculación consumo ↔ flota", f"{pct:.1f}%")
            st.caption(f"{vinculadas:,} de {len(consumo):,} transacciones; "
                       f"{normalizadas / len(consumo):.1%} al normalizar el dominio")
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
    ayuda="Las nueve páginas, en el mismo orden que la barra lateral. Cada tarjeta tiene su **?** con "
          "qué hace, por qué existe y un consejo.\n\n"
          "**Ruta sugerida** para entender el método de punta a punta:\n"
          "1. **Generador** y **Datasets**: de dónde salen los datos y qué contienen.\n"
          "2. **Análisis por hipótesis**: lo que encuentran las reglas, como lo vería un auditor.\n"
          "3. **Detección** e **Hipótesis**: cuánto de eso era cierto y cuánto aporta el contexto.\n"
          "4. **Modelo de ML**: qué revisar primero con un presupuesto limitado.\n\n"
          "**Diccionario**, **Perfil de fuentes** y **Documentación** son de consulta: entrá cuando "
          "necesites una definición, el origen de las proporciones o el estado del proyecto.")

MODULOS = [
    {
        "titulo": "🎯 1. Generador",
        "cuerpo": "Crea los datos sintéticos del proyecto\n"
                  "- Escenario didáctico o realista\n- Cantidad de vehículos y semilla\n- Descarga de archivos",
        "que": "Ejecuta el generador maestro: flota, telemetría, cargas, registro interno, contratos, facturación, "
               "la verdad de referencia (las anomalías que inyectó) y los casos legítimos que se les parecen.",
        "por_que": "El proyecto no usa datos reales: todo sale de acá y se puede reproducir con la semilla. El "
                   "escenario realista está calibrado con el perfil agregado de fuentes reales.",
        "consejo": "Con la misma semilla los datos son idénticos. Cambiar la semilla o la cantidad de vehículos "
                   "sirve para ver si las conclusiones se sostienen; los números de las demás páginas cambian.",
    },
    {
        "titulo": "📋 2. Datasets",
        "cuerpo": "Explora y filtra los datos del proyecto\n"
                  "- Cada tabla con su grano y su clave\n- Filtros y búsquedas\n- Exportación",
        "que": "Muestra cada tabla generada, con su grano (qué representa una fila), su clave y la descripción de "
               "cada columna, con filtros y exportación.",
        "por_que": "Antes de analizar conviene conocer qué hay y cómo viene: formatos, faltantes, relaciones.",
        "consejo": "La verdad de referencia y los casos legítimos son tablas de **evaluación**: las reglas y los "
                   "modelos no las ven, solo se usan para medirlos.",
    },
    {
        "titulo": "📖 3. Diccionario de datos",
        "cuerpo": "Qué contiene cada tabla\n"
                  "- Grano, clave y columnas\n- Diagrama de relaciones\n- Catálogos de anomalías y casos legítimos",
        "que": "Presenta las tablas, sus columnas y relaciones (con diagrama) y los catálogos de anomalías y de casos "
               "legítimos, a partir del diccionario que escribe el generador junto a los datos.",
        "por_que": "Es la referencia común del equipo: qué significa cada columna y cómo se vinculan las fuentes.",
        "consejo": "Las flechas punteadas no son claves: el registro interno y el reporte del proveedor no comparten "
                   "ningún identificador y se cruzan por dominio y horario, como en la realidad.",
    },
    {
        "titulo": "🔬 4. Perfil de fuentes",
        "cuerpo": "Qué le falta al generador\n"
                  "- Estructura y calidad, sin guardar datos\n- Comparación con los datos sintéticos\n"
                  "- Informe de brechas",
        "que": "Describe una fuente real solo con agregados (tipos, formatos, faltantes, proporciones, relaciones) y "
               "la compara con los datos sintéticos.",
        "por_que": "Acercar el generador a la realidad sin traer datos reales al proyecto. De acá salieron los estados "
                   "de la flota, la telemetría por estado, los litros por carga y las demás proporciones.",
        "consejo": "En la app publicada no se pueden subir archivos (irían a un servidor externo): el perfil se genera "
                   "en la máquina donde están los datos y una persona lo aprueba antes de versionarlo.",
    },
    {
        "titulo": "🔍 5. Análisis por hipótesis",
        "cuerpo": "Qué encuentran las reglas en los datos\n"
                  "- Calidad de datos y vinculación\n- Una vista por hipótesis (H1 a H12)\n"
                  "- Antes y después: regla ingenua vs. con contexto",
        "que": "Para cada hipótesis muestra cuánto marca la regla ingenua y cuánto la regla con contexto, con los casos "
               "concretos, **sin usar** la verdad de referencia.",
        "por_que": "Es la vista del auditor: lo que se vería trabajando con datos reales, donde no se sabe de antemano "
                   "qué es irregular.",
        "consejo": "Empezá por el Resumen. Que la regla con contexto marque menos no prueba que sea mejor: eso se "
                   "valida en Detección e Hipótesis.",
    },
    {
        "titulo": "🎯 6. Detección",
        "cuerpo": "Reglas evaluadas contra el ground truth\n"
                  "- Precisión, recall y F1 por tipo y por regla\n- Origen de cada falsa alarma\n"
                  "- Explorador de errores",
        "que": "Compara lo que marcan las reglas con las anomalías que inyectó el generador y clasifica cada falsa "
               "alarma: caso legítimo, otra anomalía o carga normal.",
        "por_que": "Detectar es concluir que algo parece anómalo; evaluar es medir si lo era. Esta página hace lo "
                   "segundo.",
        "consejo": "Un F1 alto con datos del mismo generador que define las reglas es un **techo de referencia**, no el "
                   "desempeño esperable con datos reales.",
    },
    {
        "titulo": "🧪 7. Hipótesis",
        "cuerpo": "¿Cuánto aporta el contexto?\n"
                  "- Regla ingenua vs. regla con contexto\n- Falsas alarmas por casos legítimos\n"
                  "- Veredicto calculado de cada hipótesis",
        "que": "Contrasta las trece hipótesis del escenario realista: cada una se sostiene si la regla con contexto "
               "mejora el F1 de la ingenua en al menos 0,10. El veredicto sale de los datos.",
        "por_que": "Es la evidencia central del proyecto: integrar fuentes y usar el contexto de cada vehículo, contrato "
                   "o dispositivo separa las irregularidades de los casos legítimos que se les parecen.",
        "consejo": "Mirá la columna de falsas alarmas por casos legítimos: ahí se ve mejor el aporte del contexto "
                   "(por ejemplo, H8 baja de cientos a cero).",
    },
    {
        "titulo": "🤖 8. Modelo de ML",
        "cuerpo": "Qué revisar primero\n"
                  "- Cola de revisión con motivos\n- Curva de esfuerzo por método\n- Vehículos y facturas a revisar",
        "que": "Ordena las cargas por prioridad de revisión con reglas, Isolation Forest, un modelo supervisado "
               "entrenado con datasets de otras semillas y una combinación, y muestra la curva de esfuerzo.",
        "por_que": "Nadie revisa todo: con un presupuesto limitado de revisiones, importa en qué orden se mira.",
        "consejo": "Mové el presupuesto y compará cuántas anomalías encuentra cada método revisando la misma cantidad "
                   "de casos. La primera vez, el modelo supervisado tarda unos segundos en entrenarse.",
    },
    {
        "titulo": "📚 9. Documentación",
        "cuerpo": "La documentación con valores actuales\n"
                  "- Estado actual del proyecto\n- Bitácora de cambios\n- Descarga en .md o .zip",
        "que": "Muestra los documentos del proyecto con variables que toman los valores de los datos en uso, la "
               "bitácora con el historial de git y la descarga de uno o de todos.",
        "por_que": "Tener el marco del proyecto al día para presentaciones y seguimiento, sin copiar números a mano.",
        "consejo": "**Estado actual** se completa solo con los datos en uso; la **bitácora** registra cada cambio con "
                   "su motivo. Si regenerás con otra semilla, el estado cambia y la bitácora no.",
    },
]

for fila in range(0, len(MODULOS), 3):
    for columna, modulo in zip(st.columns(3), MODULOS[fila:fila + 3]):
        with columna:
            tarjeta(modulo["titulo"], modulo["cuerpo"],
                    f"**Qué hace.** {modulo['que']}\n\n**Por qué.** {modulo['por_que']}\n\n"
                    f"**Consejo.** {modulo['consejo']}")

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
