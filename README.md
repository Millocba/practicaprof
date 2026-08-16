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

El proyecto se encuentra en su etapa fundacional y documental. Todavía no presenta datasets, implementaciones ni resultados experimentales.

## Gobierno y colaboración

- [Reglas para agentes de IA](AGENTS.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Playbook de IA](docs/AI_PLAYBOOK.md)
- [Gobierno de datos y persistencia](docs/DATA_GOVERNANCE.md)
- [Arquitectura conceptual](docs/ARCHITECTURE.md)
- [Entorno de desarrollo](docs/DEVELOPMENT.md)
- [Modelo de datos sintéticos](docs/DATA_MODEL.md)
- [Diccionario de datos](docs/DATA_DICTIONARY.md)
- [Método de generación sintética](docs/SYNTHETIC_DATA_METHOD.md)
- [Escenarios de calidad](docs/DATA_QUALITY_SCENARIOS.md)
- [Límite de metadatos reales](docs/REAL_DATA_BOUNDARY.md)

Las personas integrantes conservan la autoridad final sobre las decisiones y sobre `main`. Las IA colaboran mediante ramas y pull requests sujetos a revisión humana.

## Hoja de ruta

- Fundación documental y reglas de trabajo.
- Especificación del modelo de datos sintéticos.
- Generador reproducible y validaciones de privacidad.
- Análisis exploratorio inicial.
- Pipeline de integración y calidad.
- Líneas base de detección.
- Experimentos de ML y evaluación.
- Presentación interactiva de resultados.

## Limitaciones iniciales

Los datos sintéticos permiten experimentar sin exponer información sensible, pero sus patrones dependen de los supuestos del generador. Los resultados no podrán generalizarse automáticamente a flotas reales y deberán interpretarse dentro del escenario simulado.
