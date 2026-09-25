# Evolución de los generadores

Esta carpeta conserva las versiones anteriores del generador de datos sintéticos para mantener la trazabilidad del proyecto. **No se usan en el flujo actual**: el generador oficial es [`generator_pipeline_maestro.py`](../generator_pipeline_maestro.py), en la raíz del repositorio.

Cada versión se reemplazó por la siguiente porque agregaba algo que la anterior no cubría. El código se mantiene tal como estaba al momento de reemplazarlo.

## Línea de tiempo

| Fecha | Versión | Ubicación | Qué aportó | Por qué se reemplazó |
|---|---|---|---|---|
| 2026-08-16 | Etapa inicial | `etapa_inicial/synthetic_data/` | Generador relacional sin dependencias externas, semilla configurable, IDs deterministas y `manifest.json` con hashes SHA-256 | Modelo de datos reducido; las fuentes crudas en Excel dependen de una herramienta no disponible públicamente |
| 2026-08-16 | Fuentes crudas | `etapa_inicial/raw_sources/`, `etapa_inicial/tools/` | Proyecciones "sucias" de flota, telemetría y consumo interno/externo, sin claves internas, para ejercitar la vinculación | Mismo motivo que la etapa inicial |
| 2026-09-09 | v2 | `generadores/generator_v2.py` | Defectos ampliados y arquitectura modular | Absorbido por v3 |
| 2026-09-09 | v3 | `generadores/generator_v3_production.py` | Esquema ampliado (vehículo, dispositivo, eventos, transacciones) y primer registro de `ground_truth` | Cubría una sola familia de defectos |
| 2026-09-09 | v4 | `generadores/generator_v4_complete.py` | Cuatro fuentes independientes: vehículo, dispositivo, reporte de consumo y solicitudes | No registraba ground truth |
| 2026-09-09 | v5 | `generadores/generator_v5_defects_aware.py` | Cinco categorías de defectos normalizables con `ground_truth.csv` (fila, tabla, columna, tipo, severidad) | Solo defectos de formato; sin anomalías de comportamiento |
| 2026-09-09 | v7.5 | `generadores/generator_v7_5_hybrid.py` | Fusión de v5 (defectos normalizables) con anomalías detectables y ground truth dual | Requería encadenar varios scripts para obtener todas las entidades |
| 2026-09-10 | Standalone | `generadores/generator_{combustible,consumo_diario,facturas}_standalone.py` | Capas 2 a 4: combustible con cruce entre fuentes, consumo diario con anomalías de odómetro, facturación | Scripts separados; los orquestaba `run_full_pipeline.py` |
| 2026-09-10 | Orquestación | `generadores/run_full_pipeline.py`, `generadores/setup_integrador.py` | Ejecución secuencial de v7.5 más los tres standalone | Reemplazado por el pipeline maestro |
| 2026-09-22 | **Pipeline maestro** | `../generator_pipeline_maestro.py` | Las cinco entidades (flota, telemetría, consumo, solicitudes, facturación) en un solo paso, reproducible por semilla, usado por la aplicación Streamlit | **Versión actual** |

## Notebooks

| Carpeta | Contenido |
|---|---|
| `etapa_inicial/notebooks/` | EDA de la etapa inicial |
| `notebooks/` | Generación y EDA de v3, v4 y v5 (versiones para Colab) y validación de defectos |

## Cómo ejecutar el código legado

- **Etapa inicial**: sus tests siguen funcionando y se ejecutan con el resto del proyecto (`python -m pytest`). El `conftest.py` de `etapa_inicial/` hace importables los paquetes desde esta ubicación.
- **Generadores v2 a v7.5 y standalone**: se ejecutan desde `legacy/generadores/`, porque `run_full_pipeline.py` importa los demás módulos de esa misma carpeta.

```bash
cd legacy/generadores
python run_full_pipeline.py
```

Los datos que generan quedan fuera del control de versiones: se pueden recrear con la misma semilla.
