# Encuentro 1 — Informativa

*¿Cómo vamos a trabajar y con qué?*

**Proyecto:** análisis y auditoría de datos de flota vehicular mediante datos 100 % sintéticos.<br>
**Repositorio:** github.com/Millocba/practicaprof

# 1. Equipo, roles y herramienta de gestión

El equipo está integrado por cinco personas. Los roles iniciales podrán revisarse a medida que avance el proyecto y se identifiquen nuevas necesidades.

| Integrante | Eje / rol principal | Responsabilidad en Encuentro 1 | Estado |
| :--- | :--- | :--- | :--- |
| Integrante 1 | Gestión | Organización del tablero | En curso |
| Integrante 2 | Gestión y Product Management | Mapa de hipótesis y estimación DRL | En curso |
| Integrante 3 | Negocio y datos | Mapa de hipótesis y estimación DRL | Pendiente de asignación |
| Integrante 4 | Modelado e IA | Justificación del stack tecnológico | Pendiente de asignación |
| Integrante 5 | Modelado e IA | Justificación del stack tecnológico | Pendiente de asignación |

## Herramienta de gestión elegida: Trello

Se eligió Trello para organizar, asignar y dar seguimiento a las tareas. El tablero utilizará las columnas **Backlog**, **Encuentro actual**, **En progreso**, **Revisión** y **Hecho**.

# 2. Stack tecnológico elegido y justificación

Se utilizarán Python 3.12, notebooks reproducibles en Google Colab y las bibliotecas pandas, NumPy y scikit-learn como base del trabajo analítico. Para visualización se empleará Plotly y para versionado y colaboración se utilizarán Git y GitHub.

- Python, pandas y NumPy permiten realizar perfilado, limpieza, transformación e integración de las fuentes sintéticas.
- scikit-learn permite implementar líneas base estadísticas y modelos no supervisados de detección de anomalías, como Isolation Forest y Local Outlier Factor.
- Google Colab ofrece un entorno compartido y reproducible, apropiado para la etapa exploratoria del proyecto.
- Plotly permite construir visualizaciones interactivas para el análisis exploratorio y la comunicación de indicadores.
- Git y GitHub proporcionan trazabilidad sobre código, documentación, decisiones y experimentos.
- Si posteriormente el proyecto evoluciona hacia un producto con API e interfaz, podrán incorporarse tecnologías como FastAPI y React. Esa implementación no forma parte del alcance inmediato del Encuentro 1.

El uso de aprendizaje automático no se considera un resultado garantizado. Los modelos se evaluarán experimentalmente y deberán compararse contra líneas base simples, reglas de negocio y métodos estadísticos interpretables.

# 3. Ficha de organización y nivel DRL estimado

| Campo | Detalle |
| :--- | :--- |
| Organización | El caso de estudio representa una flota vehicular ficticia. Se utilizan exclusivamente datos sintéticos generados desde cero; no se anonimizan ni transforman registros institucionales reales. |
| Stakeholders | El equipo cumple el rol de Product Owner y define el alcance, las reglas del dominio y los criterios de aceptación. No existe un stakeholder institucional externo para esta etapa académica. |
| Fuentes disponibles | Cuatro fuentes crudas sintéticas: flota vehicular, telemetría de dispositivos, consumo del sistema interno y consumo de fuente externa. Cada fuente posee un manifiesto con semilla, columnas, período, problemas de calidad y hash de verificación. |
| Volumen y período | La flota contiene 250 registros. La base relacional sintética incluye 180 dispositivos, aproximadamente 20.000 eventos de telemetría y miles de eventos de consumo distribuidos durante 2025. |
| Problemas de calidad conocidos | Duplicados controlados de matrículas y dominios, representaciones mixtas, espacios y diferencias de mayúsculas, claves naturales imperfectas, dispositivos sin asignación visible, tickets duplicados, rendiciones pendientes, anulaciones y contingencias. |
| Estado del trabajo | Ya existen generadores reproducibles, pruebas automatizadas y archivos Excel crudos. Todavía no se completaron el perfilado analítico, la limpieza, la integración ni la evaluación experimental. |
| Nivel DRL estimado | Banda C consolidada, en transición hacia Banda B. Las fuentes tienen sintaxis, estructura, metadatos y trazabilidad, pero todavía deben validarse valores, rangos, duplicados, consistencia e integración. |
| Justificación | La disponibilidad de fuentes reproducibles y manifiestos supera una etapa puramente documental. Sin embargo, la confiabilidad analítica todavía no fue demostrada mediante perfilado, limpieza, conciliación y validaciones sistemáticas. |

# 4. Problema y pregunta de investigación

Las fuentes operativas de una flota pueden presentar errores de calidad, formatos heterogéneos y claves naturales imperfectas. Estos problemas afectan la integración de los datos y pueden alterar indicadores o producir alertas incorrectas.

La pregunta principal propuesta es:

> **¿En qué medida la limpieza e integración de fuentes sintéticas heterogéneas mejora la confiabilidad de los indicadores y la detección explicable de anomalías en una flota vehicular ficticia?**

Esta pregunta permite estudiar el recorrido completo desde los datos crudos hasta los resultados analíticos, sin anticipar que un modelo de aprendizaje automático necesariamente superará a métodos más simples.

# 5. Mapa de hipótesis revisado

Las hipótesis se formulan a partir de las variables y relaciones que actualmente existen en los datasets. Se separan de las ideas que requerirán ampliar el generador sintético.

## 5.1 Hipótesis principales comprobables

| Eje | Hipótesis | Variables o métricas posibles |
| :--- | :--- | :--- |
| Calidad e integración | **H1.** La normalización de dominios, matrículas y otros identificadores incrementa la proporción de registros vinculados correctamente entre las fuentes de flota, telemetría y consumo. | Tasa de vinculación, registros no encontrados, vinculaciones ambiguas, precisión contra la relación sintética original. |
| Impacto analítico | **H2.** Los errores de calidad y vinculación alteran los indicadores de cobertura, consumo y cantidad de vehículos con eventos irregulares. | Diferencia de indicadores antes y después de limpiar, vehículos sin consumo aparente, vehículos sin telemetría, cantidad de alertas. |
| Integración de fuentes | **H3.** La integración de flota, telemetría y consumo permite detectar inconsistencias que no son observables al analizar cada fuente por separado. | Discrepancias entre consumo interno y externo, consumos sin telemetría asociada, dominios no vinculados, eventos administrativos inconsistentes. |
| Métodos de detección | **H4.** Las reglas de negocio proporcionan una línea base interpretable, mientras que los métodos estadísticos permiten identificar patrones atípicos no cubiertos por reglas explícitas. | Precisión, recall, F1, falsos positivos y tipos de anomalías detectadas por cada método. |
| Enfoque híbrido | **H5.** La combinación de reglas de negocio y métodos de detección de anomalías puede mejorar el desempeño respecto de utilizar cada enfoque de manera aislada. | F1, recall a precisión fija, cobertura de tipos de anomalías y explicabilidad. |

Las hipótesis H4 y H5 requieren incorporar una verdad sintética de anomalías de consumo suficientemente completa. Hasta contar con esas etiquetas, deben considerarse hipótesis de una etapa experimental posterior.

## 5.2 Hipótesis nulas de referencia

- **H0.1:** La normalización de identificadores no produce una mejora relevante en la tasa de vinculación entre fuentes.
- **H0.2:** Los indicadores obtenidos desde datos crudos no presentan diferencias relevantes respecto de los calculados después de la limpieza e integración.
- **H0.3:** La integración de múltiples fuentes no permite detectar inconsistencias adicionales frente al análisis aislado.
- **H0.4:** Los métodos estadísticos o de aprendizaje automático no mejoran el desempeño de una línea base basada en reglas.

## 5.3 Líneas futuras que requieren ampliar el generador

Las siguientes ideas son relevantes para el dominio, pero todavía no pueden contrastarse adecuadamente con los datos actuales:

- influencia del estilo de conducción sobre el consumo;
- diferencias de calidad de carga entre dependencias;
- variaciones por turno, calendario o estacionalidad;
- consumo esperado en función de kilómetros, tipo de vehículo, motor y antigüedad;
- relación entre ausencia de telemetría y eventos irregulares;
- efecto de cupos, saldos, contratos y autorizaciones administrativas.

Para estudiarlas será necesario simular explícitamente recorridos, consumo por kilómetro, estilos de conducción, turnos, comportamiento por dependencia, fallas de dispositivos, reglas contractuales y anomalías etiquetadas.

# 6. Nivel de madurez analítica objetivo

El objetivo inmediato es alcanzar una madurez **descriptiva y diagnóstica**:

1. describir la estructura, distribución y calidad de cada fuente;
2. explicar cómo los problemas de calidad afectan la integración y los indicadores;
3. construir reglas de control interpretables;
4. evaluar métodos estadísticos de detección de anomalías.

Como objetivo posterior y condicionado a la calidad de la verdad sintética, se podrán comparar modelos de aprendizaje automático para priorizar eventos que merezcan revisión. En este contexto, “predictivo” no significa anticipar hechos reales futuros, sino estimar qué registros sintéticos presentan mayor probabilidad de pertenecer a una clase anómala definida por el experimento.

# 7. Próximos pasos

- Confirmar los roles concretos de cada integrante dentro de los ejes de gestión, negocio/datos y modelado/IA.
- Revisar en equipo `AGENTS.md`, `CONTRIBUTING.md` y `DATA_GOVERNANCE.md`.
- Incorporar este contenido al tablero de Trello.
- Crear un diccionario de variables observables por cada hipótesis.
- Ejecutar el perfilado inicial de las cuatro fuentes crudas.
- Definir métricas de calidad: completitud, unicidad, validez, consistencia e integridad referencial recuperada.
- Diseñar el pipeline de normalización e integración.
- Definir una línea base de reglas antes de experimentar con modelos de ML.
- Acordar el formato final de entrega y exposición del Encuentro 1.

# 8. Alcance y limitaciones

Los resultados se interpretarán exclusivamente dentro del escenario sintético. La utilidad del proyecto reside en demostrar un proceso reproducible de calidad, integración, análisis y evaluación; no en afirmar conclusiones sobre una institución o flota real.

Los patrones encontrados dependerán de los supuestos incorporados al generador. Por ese motivo, toda conclusión deberá indicar qué parte fue observada en los datos y qué parte responde al diseño de la simulación.
