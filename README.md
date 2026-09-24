# Proyecto de análisis y auditoría de datos de flotas

Proyecto académico colaborativo centrado en el ciclo completo de los datos: generación, calidad, limpieza, integración, análisis exploratorio, visualización y detección de anomalías.

## Declaración sobre los datos

Este proyecto utiliza exclusivamente **datos sintéticos generados desde cero** con fines educativos. No contiene información real de personas, instituciones, vehículos, contratos, tarjetas, dispositivos o ubicaciones. No es un conjunto de datos anonimizado ni una reproducción exacta de una organización existente. Cualquier semejanza con entidades reales es accidental.

Los futuros generadores serán reproducibles mediante semillas configurables. Las anomalías se inyectarán deliberadamente y sus etiquetas de evaluación se mantendrán separadas de los datos disponibles para los modelos.

## Motivación

El proyecto nace de una pregunta pequeña: **¿qué podemos aprender al observar con curiosidad la calidad y el comportamiento de datos operativos de una flota?**

Esa exploración conduce a preguntas más amplias: cómo corregir inconsistencias, vincular fuentes heterogéneas, producir indicadores confiables, explicar comportamientos y detectar eventos que merecen revisión. El resultado esperado no es solo una aplicación, sino un proceso analítico trazable y defendible.

## Objetivo general

Diseñar y evaluar un sistema reproducible de apoyo al análisis y la auditoría de una flota ficticia mediante datos sintéticos, integración de fuentes y detección explicable de anomalías.

## Objetivos específicos

- Diseñar un modelo coherente de datos sintéticos relacionados.
- Medir y mejorar calidad, completitud, consistencia y unicidad.
- Integrar flota, telemetría, recorridos, consumo y contratos ficticios.
- Desarrollar análisis exploratorios e indicadores reproducibles.
- Comparar reglas de negocio, métodos estadísticos y modelos de aprendizaje automático.
- Evaluar resultados con una verdad de referencia sintética.
- Comunicar hallazgos, supuestos, errores y limitaciones.

## Alcance previsto

1. Generación reproducible de entidades y eventos sintéticos.
2. Validación, perfilado y limpieza.
3. Transformación e integración entre fuentes.
4. Análisis descriptivo y exploratorio.
5. KPIs y visualizaciones.
6. Reglas de control como línea base.
7. Detección estadística y aprendizaje automático.
8. Evaluación, interpretabilidad y análisis de errores.
9. Capas técnicas de soporte para consultar y presentar resultados.

## Hipótesis iniciales

- Las inconsistencias de los datos afectan la confiabilidad de los indicadores.
- Integrar fuentes permite detectar situaciones invisibles en análisis aislados.
- El consumo puede explicarse parcialmente mediante características, actividad e historial del vehículo.
- Las reglas de control identifican una parte relevante de los eventos irregulares.

## Hipótesis emergentes

- Algunos aparentes problemas de consumo provienen de errores de vinculación.
- La ausencia de telemetría también puede constituir una señal.
- Los umbrales adecuados varían según el tipo de vehículo y su contexto.
- El historial individual puede resultar más informativo que un umbral general.
- Combinar reglas, estadística robusta y ML puede reducir falsas alertas.
- En auditoría, la trazabilidad puede ser tan importante como la precisión.

Estas hipótesis deberán contrastarse; no representan conclusiones anticipadas.

## ML propuesto

La detección de anomalías comparará una línea base de reglas con métodos estadísticos robustos y modelos no supervisados. Si la generación proporciona etiquetas suficientes, también podrá evaluarse un enfoque supervisado. La selección definitiva dependerá de los experimentos, no de preferencias previas.

## Estado actual

- **Generador oficial**: [`generator_pipeline_maestro.py`](generator_pipeline_maestro.py) produce cinco entidades relacionadas (flota, telemetría, consumo, solicitudes y facturación) y un `ground_truth.csv` con cada anomalía inyectada. La misma semilla produce los mismos datos.
- **Detección**: nueve reglas base y un modelo Isolation Forest, evaluados contra el ground truth (paquete [`deteccion/`](deteccion/)).
- **Aplicación**: Streamlit con generación, exploración, análisis de hipótesis, detección y ML ([`streamlit_app/`](streamlit_app/README.md)).
- **Tests**: `python -m pytest` cubre generador, reglas, modelo y páginas, y se ejecuta en cada push.
- Las versiones anteriores del generador se conservan en [`legacy/`](legacy/EVOLUCION.md).

### Resultados preliminares

Promedio de 5 semillas, 200 vehículos cada una:

| Método | Precision | Recall | F1 |
|---|---|---|---|
| Reglas (línea base) | 1,00 | 1,00 | 1,00 |
| Isolation Forest | 0,73 | 0,82 | 0,77 |

- Las reglas son perfectas porque se diseñaron conociendo cómo se inyectan las anomalías sintéticas: funcionan como techo de referencia, no como desempeño esperable con datos reales.
- En los saltos de odómetro (H2), comparar con el historial del propio vehículo detecta el 100% de los casos, contra el 25% de un umbral fijo.
- Isolation Forest encuentra todas las anomalías de odómetro, pero solo el 76% de los excesos volumétricos: los vehículos con exceso forman un grupo denso que deja de parecer atípico.

## Cómo usarlo

```bash
pip install -r requirements.txt                 # Python 3.12

python generator_pipeline_maestro.py            # genera datasets/synthetics_maestro/
python -m deteccion                             # evalúa las reglas contra el ground truth
python -m pytest                                # corre todos los tests
streamlit run streamlit_app/app.py              # abre la aplicación
```

- El generador acepta `--n_flota`, `--seed` y `--output`.
- La aplicación genera los datos por su cuenta si no existen.
- `datasets/` está excluido de Git: se versionan el generador, las pruebas y la configuración, y los datos se recrean con la semilla.

El detalle de cada archivo, columna y tipo de anomalía está en el [diccionario de datos](docs/DICCIONARIO_DATOS.md).

## Estructura

```text
generator_pipeline_maestro.py   generador oficial
deteccion/                      reglas, modelo de ML y evaluación
streamlit_app/                  aplicación (páginas y carga de datos)
tests/                          tests del generador, la detección y la app
docs/                           gobierno, arquitectura, diccionario, sprints y análisis
results/                        reportes de los encuentros
legacy/                         generadores, notebooks y etapa inicial anteriores
```

## Gobierno y colaboración

- [Reglas para agentes de IA](AGENTS.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Playbook de IA](docs/AI_PLAYBOOK.md)
- [Gobierno de datos y persistencia](docs/DATA_GOVERNANCE.md)
- [Arquitectura conceptual](docs/ARCHITECTURE.md)
- [Entorno de desarrollo](docs/DEVELOPMENT.md)
- [Diccionario de datos del pipeline maestro](docs/DICCIONARIO_DATOS.md)
- [Límite de metadatos reales](docs/REAL_DATA_BOUNDARY.md)
- [Evolución de los generadores](legacy/EVOLUCION.md)
- [Registro del Sprint 1](docs/sprints/sprint-1/README.md)

Las personas integrantes conservan la autoridad final sobre las decisiones y sobre `main`. Las IA colaboran mediante ramas y pull requests sujetos a revisión humana.

## Hoja de ruta

- [x] Fundación documental y reglas de trabajo.
- [x] Especificación del modelo de datos sintéticos.
- [x] Generador reproducible con verdad de referencia.
- [x] Análisis exploratorio inicial.
- [x] Líneas base de detección por reglas.
- [x] Primer experimento de ML (Isolation Forest) y evaluación.
- [x] Presentación interactiva de resultados (aplicación Streamlit).
- [ ] Pipeline de integración y limpieza sobre fuentes con defectos de formato.
- [ ] Anomalías en facturación y solicitudes.
- [ ] Métodos estadísticos robustos y comparación de más modelos.
- [ ] Validaciones de privacidad automatizadas antes de versionar datos.

## Limitaciones iniciales

Los datos sintéticos permiten experimentar sin exponer información sensible, pero sus patrones dependen de los supuestos del generador. Los resultados no podrán generalizarse automáticamente a flotas reales y deberán interpretarse dentro del escenario simulado.
