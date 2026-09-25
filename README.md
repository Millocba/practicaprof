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

- **Generador oficial**: [`generator_pipeline_maestro.py`](generator_pipeline_maestro.py) produce cinco entidades relacionadas (flota, telemetría, consumo, solicitudes y facturación) y un `ground_truth.csv` con cada anomalía inyectada. La misma semilla produce los mismos datos. Tiene dos escenarios:
  - **Didáctico**: anomalías inconfundibles, para explicar el método.
  - **Realista**: cada vehículo se simula día por día (consumo según su rendimiento, cargas cuando baja el tanque, GPS diario) y el circuito **solicitud → carga → factura** es coherente: cada carga tiene su solicitud y cada proveedor factura por mes con detalle línea por línea. Incluye anomalías sutiles, cruces entre fuentes y **casos legítimos que se parecen a anomalías** (`casos_legitimos.csv`), con una prevalencia cercana al 1%.
- **Detección**: reglas ingenuas y reglas con contexto, un Isolation Forest y un modelo supervisado, evaluados contra el ground truth (paquete [`deteccion/`](deteccion/)).
- **Aplicación**: Streamlit con generación, exploración, análisis, detección, contraste de hipótesis y priorización de la revisión ([`streamlit_app/`](streamlit_app/README.md)).
- **Tests**: `python -m pytest` cubre generador, reglas, modelo y páginas, y se ejecuta en cada push.
- Las versiones anteriores del generador se conservan en [`legacy/`](legacy/EVOLUCION.md).

### Resultados preliminares

Promedio de 5 semillas, 200 vehículos cada una.

**Escenario didáctico**

| Método | Precision | Recall | F1 |
|---|---|---|---|
| Reglas (línea base) | 1,00 | 1,00 | 1,00 |
| Isolation Forest | 0,73 | 0,82 | 0,77 |

- Las reglas son perfectas porque se diseñaron conociendo cómo se inyectan las anomalías sintéticas: funcionan como techo de referencia, no como desempeño esperable con datos reales.
- En los saltos de odómetro (H2), comparar con el historial del propio vehículo detecta el 100% de los casos, contra el 25% de un umbral fijo.
- Isolation Forest encuentra todas las anomalías de odómetro, pero solo el 76% de los excesos volumétricos: los vehículos con exceso forman un grupo denso que deja de parecer atípico.

**Escenario realista: hipótesis.** Cada una compara una regla ingenua con una regla con contexto; se sostiene si el F1 mejora al menos 0,10. Las 9 se sostienen en las 5 semillas.

| | Hipótesis | F1 ingenua → con contexto | Falsas alarmas por casos legítimos |
|---|---|---|---|
| H2b | Distinguir un odómetro nuevo o un error de tipeo elimina las falsas alarmas de retroceso, sin perder adulteraciones leves | 0,67 → 1,00 | 20 → 0 |
| H2c | Un salto sobre el ritmo habitual se confirma descartando errores de tipeo y cruzando con el GPS | 0,01 (umbral fijo) · 0,55 (historial) → 1,00 | 67 · 15 → 0 |
| H3b | Solo el exceso volumétrico que aparece después indica un problema; el que existe desde el inicio es un tanque no registrado | 0,20 → 1,00 | 208 → 0 |
| H4 | El fraccionamiento evade el control por transacción; lo revela la suma del día y el recorrido separa los viajes largos | 0,00 (por carga) · 0,84 (por día) → 0,99 | 22 → 0 |
| H5 | Una carga sin recorrido que la justifique solo se ve con el rendimiento km/L frente al habitual | 0,00 → 0,61 | 0 → 0 |
| H6 | Las cargas a vehículos de baja o fuera de servicio solo se detectan cruzando con el estado de la flota | 0,00 → 1,00 | — |
| H7 | El recorrido del GPS distingue una tarjeta usada en otro lado de un viaje real | 0,58 → 0,89 | 43 → 5 |
| H8 | Cruzar cargas con solicitudes detecta las no autorizadas o que superan lo autorizado; aceptar regularizaciones posteriores y la tolerancia del surtidor evita falsas alarmas | 0,63 → 0,98 | 90 → 0 |
| H9 | Conciliar la factura línea por línea detecta cargas inexistentes, duplicadas, sobreprecios y totales inflados que la comparación de totales mensuales no ve o confunde con desfases de corte y ajustes (evaluada por factura) | 0,49 → 1,00 | 66 → 0 |

- En H5 el GPS no mejora al odómetro, porque en esos vehículos el odómetro no está adulterado. La mayoría de sus falsos positivos son otras anomalías que también cargan sin recorrido (vehículos inactivos, cargas lejos, fraccionamiento).
- El umbral fijo de saltos es inutilizable con uso realista: genera unas 400 falsas alarmas por dataset, porque un camión recorre 500 km en pocos días.
- Las solicitudes no traen el número de carga: se emparejan por vehículo con una asignación óptima (método húngaro) por fecha y litros. Con un emparejamiento simple, una solicitud "se la llevaba" otra carga cercana y H8 no se sostenía.
- La comparación de totales mensuales (H9) solo detecta 69% de las facturas con irregularidades: un sobreprecio o una línea de más cambian menos del 1% del total, mientras que los desfases de corte y los ajustes documentados sí superan ese umbral.

**Escenario realista: priorización de la revisión.** Qué encuentra cada método según cuántas cargas se revisan, de unas 67 anomalías de comportamiento en las cargas por dataset (prevalencia 1,3%). Con 50 revisiones, el máximo posible es 75%.

| Método | Revisando 50 | Revisando 100 | Legítimos revisados en vano (de 100) |
|---|---|---|---|
| Reglas ingenuas | 42% | 75% | 45 |
| Isolation Forest | 23% | 37% | 18 |
| Reglas con contexto | 72% | 99% | 1 |
| Modelo supervisado (entrenado con otras semillas) | 72% | 99% | 14* |
| Combinado (reglas con contexto + modelo) | 74% | 100% | 14* |

\* Revisan casos legítimos recién después de haber encontrado todas las anomalías: con 50 revisiones, el combinado no revisa ninguno.

**Escenario realista: facturas a revisar.** La conciliación línea por línea marca unas 15 de 45 facturas por dataset y encuentra todas las irregularidades de facturación (19 por dataset), con un importe en juego de 3.000 a 6.200 por dataset.

- El modelo supervisado llega al nivel de las reglas con contexto sin que nadie las haya escrito: aprende de auditorías anteriores.
- Isolation Forest confunde lo raro con lo sospechoso, porque los viajes largos y los tanques no registrados también son raros.
- La combinación de reglas con contexto y modelo es la que mejor ordena la revisión. Cada caso de la cola trae su motivo.
- **Límite:** las reglas con contexto y el modelo se evalúan con datos del mismo generador que los define. Miden cuánto aporta cada fuente bajo los supuestos del escenario, no el desempeño esperable con datos reales.

## Cómo usarlo

```bash
pip install -r requirements.txt                 # Python 3.12

python generator_pipeline_maestro.py                       # escenario didáctico: datasets/synthetics_maestro/
python generator_pipeline_maestro.py --escenario realista  # escenario realista: datasets/synthetics_realista/
python -m deteccion                                        # evalúa las reglas contra el ground truth
python -m deteccion --escenario realista --ml              # además, hipótesis y priorización
python -m pytest                                # corre todos los tests
streamlit run streamlit_app/app.py              # abre la aplicación
```

- El generador acepta `--escenario`, `--n_flota`, `--seed` y `--output`.
- La aplicación genera los datos por su cuenta si no existen.
- `datasets/` está excluido de Git: se versionan el generador, las pruebas y la configuración, y los datos se recrean con la semilla.

Cada corrida del generador escribe también un `diccionario.json` con el grano, las columnas y las relaciones de las tablas generadas. El detalle de cada archivo, las relaciones entre tablas (con diagrama) y los tipos de anomalía están en el [diccionario de datos](docs/DICCIONARIO_DATOS.md).

## Estructura

```text
generator_pipeline_maestro.py   generador oficial
deteccion/                      reglas, hipótesis, modelos de ML, priorización y evaluación
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
- [x] Escenario realista con anomalías sutiles, cruces entre fuentes y casos legítimos.
- [x] Contraste de hipótesis: reglas ingenuas vs. reglas con contexto.
- [x] Modelo supervisado y priorización de la revisión.
- [x] Circuito solicitud → carga → factura: emparejamiento de solicitudes y conciliación de facturas.
- [ ] Métodos estadísticos robustos y comparación de más modelos.
- [ ] Validaciones de privacidad automatizadas antes de versionar datos.

## Limitaciones iniciales

Los datos sintéticos permiten experimentar sin exponer información sensible, pero sus patrones dependen de los supuestos del generador. Los resultados no podrán generalizarse automáticamente a flotas reales y deberán interpretarse dentro del escenario simulado.
