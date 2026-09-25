"""Data generation page - Execute Pipeline Maestro from Streamlit."""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import json
import os
import subprocess
from datetime import datetime

# Add utils to path
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from ayudas import seccion
from data_loader import (
    NOMBRES_ESCENARIO,
    directorio,
    selector_escenario,
    load_flota,
    load_telemetria,
    load_consumo_maestro,
    load_solicitudes,
    load_facturacion,
    load_maestro_metadata,
    get_maestro_datasets_info
)

st.set_page_config(page_title="Generador", page_icon="⚙️", layout="wide")

seccion(
    "⚙️ Generador de Datos - Pipeline Maestro", nivel=1,
    ayuda="Esta página crea los datos con los que trabaja todo el proyecto. No hay datos reales: "
          "el generador produce tablas sintéticas desde cero, con anomalías inyectadas a propósito "
          "y su lista de verdad de referencia. Todo lo que se ve después en las otras páginas sale "
          "de acá, así que cambiás un parámetro y cambiás el escenario de análisis completo.")
st.markdown("Configura y ejecuta el generador de entidades sintéticas")

escenario = selector_escenario()
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** (se elige en la barra lateral). "
           "El realista simula el uso día por día e incluye anomalías sutiles y casos legítimos "
           "que se les parecen; el didáctico, anomalías inconfundibles.")

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
GENERATOR_SCRIPT = BASE_DIR / "generator_pipeline_maestro.py"
DATASETS_DIR = directorio(escenario)

# Check if generator exists
if not GENERATOR_SCRIPT.exists():
    st.error(f"❌ Generador no encontrado en: {GENERATOR_SCRIPT}")
    st.info("Por favor, copiar `generator_pipeline_maestro.py` a la raíz del proyecto")
    st.stop()

# Create two columns for configuration
col1, col2 = st.columns(2)

with col1:
    st.markdown("### ⚙️ Configuración")

    n_flota = st.slider(
        "Número de vehículos (Flota)",
        min_value=50,
        max_value=500,
        value=200,
        step=10,
        help="Cantidad de vehículos a generar"
    )

    seed = st.number_input(
        "Seed (Reproducibilidad)",
        min_value=1,
        value=42,
        step=1,
        help="Seed para reproducibilidad. Mismo seed = mismos datos"
    )

with col2:
    st.markdown("### 📊 Información")

    info_lines = [
        "**Parámetros disponibles:**",
        "- n_flota: número de vehículos (50-500)",
        "- seed: para reproducibilidad",
        "",
        "**Entidades generadas:**",
        "- Flota (vehículos maestro)",
        "- Telemetría (dispositivos GPS)",
        "- Consumo (transacciones)",
        "- Solicitudes (fuel requests)",
        "- Facturación (facturas mensuales)"
    ]
    st.info("\n".join(info_lines))

# Divider
st.markdown("---")

# Control buttons
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    execute_button = st.button(
        "🚀 Ejecutar Generador",
        use_container_width=True,
        type="primary",
        help="Ejecutar el pipeline con los parámetros configurados"
    )

with col2:
    st.markdown("")  # Spacer

with col3:
    refresh_data = st.button(
        "🔄 Refrescar",
        use_container_width=True,
        help="Recargar datos actuales"
    )

if refresh_data:
    st.cache_data.clear()
    st.rerun()

# Execute generator
if execute_button:
    st.markdown("### 📤 Ejecutando Generador...")

    progress_container = st.container()
    status_container = st.container()

    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()

    try:
        # Build command
        cmd = [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--n_flota", str(n_flota),
            "--seed", str(seed),
            "--escenario", escenario,
        ]

        status_text.info(f"⏳ Iniciando: {' '.join(cmd[-6:])}")

        # Execute with output capture
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, {str(BASE_DIR)!r})
from generator_pipeline_maestro import GeneradorMaestro

print("=== INICIANDO PIPELINE MAESTRO ===")
print(f"n_flota: {n_flota}")
print(f"seed: {seed}")
print()

generador = GeneradorMaestro(n_flota={n_flota}, seed={seed}, escenario={escenario!r},
                             output_dir={str(DATASETS_DIR)!r})
resultado = generador.ejecutar()

print()
print("=== RESULTADO ===")
if resultado['exito']:
    print("✅ ÉXITO - Archivos generados:")
    for nombre, ruta in resultado['archivos'].items():
        print(f"  - {{nombre}}: {{ruta}}")
else:
    print(f"❌ ERROR: {{resultado['error']}}")

import json
print()
print(json.dumps(resultado, indent=2, default=str))
"""],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=300
        )

        # Parse output
        output_lines = result.stdout.strip().split('\n')

        # Show progress
        progress_bar.progress(50)
        status_text.info("⏳ Generación en progreso...")

        progress_bar.progress(90)
        status_text.info("⏳ Finalizando...")

        # Check result
        if result.returncode == 0 and "✅" in result.stdout:
            progress_bar.progress(100)

            # New CSVs on disk: drop cached (possibly empty) DataFrames so every page reloads them
            st.cache_data.clear()

            with status_container:
                st.success("✅ ¡Generador ejecutado exitosamente!")

                # Parse results
                try:
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', result.stdout)
                    if json_match:
                        resultado = json.loads(json_match.group())

                        if resultado['exito']:
                            st.markdown("### 📊 Resultados")

                            # File statistics
                            results_col1, results_col2 = st.columns(2)

                            with results_col1:
                                st.markdown("**Archivos Generados:**")
                                for nombre, ruta in resultado['archivos'].items():
                                    df = pd.read_csv(ruta)
                                    st.metric(
                                        f"📄 {nombre.upper()}",
                                        f"{len(df):,} filas",
                                        f"{len(df.columns)} columnas"
                                    )

                            with results_col2:
                                st.markdown("**Metadata:**")
                                meta = resultado.get('metadata', {})
                                if meta:
                                    st.json({
                                        "Semilla": meta.get('seed'),
                                        "Vehículos": meta.get('n_flota'),
                                        "Fecha": meta.get('fecha_generacion', 'N/A')[:10],
                                        "Generadores": meta.get('generadores_ejecutados', [])
                                    })
                except Exception as e:
                    st.warning(f"Generación completada (con parsing parcial): {e}")
        else:
            progress_bar.progress(100)
            with status_container:
                st.error("❌ Error en la ejecución del generador")
                st.code(result.stdout if result.stdout else result.stderr, language="bash")

    except subprocess.TimeoutExpired:
        st.error("⏱️ Timeout: La generación tardó demasiado tiempo")
    except Exception as e:
        st.error(f"❌ Error ejecutando generador: {e}")
        st.code(str(e))

# Display current datasets status
st.markdown("---")
seccion(
    "📋 Estado Actual de Datos", nivel=3,
    ayuda="Qué hay en disco ahora mismo. La **semilla** es el número que hace reproducible el "
          "generador: con la misma semilla y la misma cantidad de vehículos, los archivos salen "
          "idénticos byte a byte. Si la fecha es vieja respecto de la última corrida, es que los "
          "datos corresponden a otros parámetros.")

try:
    # Load current metadata
    metadata_path = DATASETS_DIR / "metadata.json"

    if metadata_path.exists():
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)

        meta_col1, meta_col2, meta_col3 = st.columns(3)

        with meta_col1:
            st.metric(
                "Fecha de Generación",
                metadata.get('fecha_generacion', 'N/A')[:10]
            )

        with meta_col2:
            st.metric(
                "Seed Utilizado",
                metadata.get('seed', 'N/A')
            )

        with meta_col3:
            st.metric(
                "Vehículos Generados",
                metadata.get('n_flota', 'N/A')
            )
    else:
        st.info("Sin datos generados aún. Ejecuta el generador para crear los datasets.")

    # Dataset summary table
    seccion(
        "📊 Resumen de Datasets", nivel=3,
        ayuda="Inventario de los archivos generados: cuántas filas y columnas tiene cada tabla, "
              "cuánto pesa y cuántos valores nulos contiene. Un **nulo** no siempre es un error: "
              "el generador deja vacíos algunos campos a propósito para que las reglas de "
              "calidad tengan algo que encontrar, y `metadata.json` registra esa fecha de corte.")
    datasets_info = get_maestro_datasets_info(escenario)

    if not datasets_info.empty:
        # Format the dataframe for display
        display_df = datasets_info.copy()
        display_df.columns = ["Nombre", "Registros", "Columnas", "Tamaño (MB)", "Nulos"]

        # Format numeric columns
        display_df["Tamaño (MB)"] = display_df["Tamaño (MB)"].apply(lambda x: f"{x:.2f}")
        display_df["Registros"] = display_df["Registros"].apply(lambda x: f"{int(x):,}")

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # Cross-entity validation
        seccion(
            "✅ Validación de Integridad", nivel=3,
            ayuda="Comprueba que cada entidad que dice tener un vehículo, efectivamente tenga un "
                  "vehículo en la flota. Una cobertura menor al 100% no siempre es un defecto del "
                  "generador: el escenario realista inyecta dominios inválidos a propósito, y esa "
                  "columna mide justamente cuánto hay de eso.")

        flota = load_flota(escenario)
        consumo = load_consumo_maestro(escenario)
        solicitudes = load_solicitudes(escenario)
        telemetria = load_telemetria(escenario)

        validations = []

        if not flota.empty:
            total_flota = len(flota)
            validations.append(("🚗 Flota (Maestro)", total_flota, total_flota, "100%"))

        if not telemetria.empty and not flota.empty:
            tele_count = len(telemetria)
            tele_valid = len(telemetria[telemetria['Placa'].isin(flota['Dominio'])])
            pct = f"{100*tele_valid/tele_count:.1f}%" if tele_count > 0 else "N/A"
            validations.append(("📡 Telemetría → Flota", tele_valid, tele_count, pct))

        if not consumo.empty and not flota.empty:
            cons_count = len(consumo)
            cons_valid = len(consumo[consumo['dominio'].isin(flota['Dominio'])])
            pct = f"{100*cons_valid/cons_count:.1f}%" if cons_count > 0 else "N/A"
            validations.append(("⛽ Consumo → Flota", cons_valid, cons_count, pct))

        if not solicitudes.empty and not flota.empty:
            sol_count = len(solicitudes)
            sol_valid = len(solicitudes[solicitudes['dominio'].isin(flota['Dominio'])])
            pct = f"{100*sol_valid/sol_count:.1f}%" if sol_count > 0 else "N/A"
            validations.append(("📋 Solicitudes → Flota", sol_valid, sol_count, pct))

        if validations:
            val_df = pd.DataFrame(
                validations,
                columns=["Relación", "Válidos", "Total", "Cobertura"]
            )
            st.dataframe(val_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Sin datos para validar")
    else:
        st.warning("Sin datasets disponibles aún")

except Exception as e:
    st.error(f"Error cargando datos: {e}")

# Footer with tips
st.markdown("---")
st.markdown("""
### 💡 Tips de Uso

- **Parámetro n_flota**: Controla el tamaño total del dataset. 200 es tamaño estándar.
- **Parámetro seed**: Usar el mismo seed siempre genera los mismos datos (reproducibilidad).
- **Validaciones**: Verifica que todas las relaciones cross-entity sean válidas al 100%.
- **Tiempo de ejecución**: ~5-10 segundos para 200 vehículos (depende de tu computadora).

### 📚 Archivos Generados

Los datos se generan en `datasets/synthetics_maestro/` (didáctico) o `datasets/synthetics_realista/`
(realista). Ambos incluyen las cinco entidades, `ground_truth.csv` y `metadata.json`; el realista suma
`estaciones.csv`, `telemetria_diaria.csv` y `casos_legitimos.csv`. El detalle está en el diccionario
de datos (`docs/DICCIONARIO_DATOS.md`).

Puedes explorar estos datos en la página **"📋 Exploración de Datasets"**
""")
