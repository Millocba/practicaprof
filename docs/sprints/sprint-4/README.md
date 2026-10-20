# Sprint 4 — Modelado y primera evaluación

> La hipótesis H3b se selecciona como rectora del Sprint 4 porque se relaciona directamente con la decisión que busca apoyar SIFAD: priorizar operaciones de combustible que requieren revisión humana. La selección se sustenta en la comparación reproducible entre una regla volumétrica simple, una regla con contexto y distintos modelos baseline. Los resultados corresponden al escenario sintético etiquetado y no deben extrapolarse directamente a operaciones reales.

## 1. Conclusión del sprint

La evaluación reproducible permitió seleccionar H3b como hipótesis rectora. La regla con contexto obtuvo un F1 de 0,98 y una precisión en las primeras k operaciones de 0,97, superando a la regla ingenua, que alcanzó 0,83 y 0,71, respectivamente.

El Random Forest alcanzó resultados prácticamente perfectos cuando utilizó las variables que definen la regla contextual. Sin embargo, al excluirlas, su F1 descendió a 0,14 y su precisión en las primeras k operaciones a 0,34. Aunque este último resultado supera ampliamente la prevalencia esperada al azar —1,1 %—, no mejora la priorización lograda por la regla contextual.

Por lo tanto, el principal resultado del Sprint 4 no es la superioridad de un modelo de aprendizaje automático, sino la comprobación de que el conocimiento del dominio aporta la señal más útil para priorizar cargas. En esta etapa se recomienda conservar la regla contextual por ser reproducible, interpretable y más eficaz que los modelos evaluados sin sus variables.

Estos resultados se obtuvieron con datos sintéticos etiquetados. Por esa razón permiten comparar métodos y comprobar el procedimiento, pero no estimar directamente el rendimiento que tendría la solución sobre datos reales.

## 2. Negocio y Datos

### 2.1 Condición de piso

La hipótesis rectora debe alcanzar una madurez Diagnóstica o superior. Al cierre del Sprint 3, H1 figura en Diagnóstico y H3b en Descriptivo. El Sprint 4 compara ambas con evidencia nueva antes de elegir la rectora.

### 2.2 Hipótesis candidatas

| Hipótesis | Problema que analiza | Evidencia que falta |
|---|---|---|
| H1 | Vinculación de las operaciones con un móvil. | Explicar las causas de los vínculos fallidos o ambiguos sobre los datos reales disponibles. |
| H3b | Cargas que superan la capacidad registrada. | Separar capacidad posiblemente mal registrada, posible uso indebido y evidencia insuficiente. |

A partir de la evaluación reproducible, se selecciona H3b como hipótesis rectora del Sprint 4. Esta hipótesis sostiene que la relación entre los litros cargados, la capacidad del tanque y el historial de consumo permite priorizar operaciones que requieren revisión.

H3b fue elegida porque responde directamente a la decisión principal de SIFAD y dispone de evidencia suficiente para comparar una regla simple, una regla contextual y distintos modelos baseline. La regla contextual mejoró el F1 de 0,83 a 0,98 y la precisión en las primeras k operaciones de 0,71 a 0,97.

H1 continúa siendo una condición habilitante fundamental para integrar las fuentes mediante identificadores normalizados. Sin embargo, no se selecciona como rectora porque su problema ya puede resolverse mediante una regla determinística y se relaciona principalmente con la calidad y vinculación de los datos, no directamente con la priorización de cargas.

### 2.3 Decisión que se busca apoyar

La decisión que SIFAD busca apoyar es qué operaciones de combustible deben priorizarse para una revisión humana. A partir de H3b, una carga adquiere mayor prioridad cuando su volumen resulta difícil de explicar mediante la capacidad del tanque, el historial de consumo y las cargas realizadas durante el mismo día.

El resultado no determina fraude ni confirma una irregularidad. Su función es ordenar los casos para que el equipo responsable concentre la revisión en las operaciones con mayor evidencia contextual.

### 2.4 Costo de los errores

Un falso positivo ocurre cuando se prioriza una carga legítima. Su costo consiste en emplear tiempo de revisión sobre una operación que puede explicarse por el contexto del vehículo.

Un falso negativo ocurre cuando una carga que requería revisión no es priorizada. Su costo es mayor, porque puede dejar sin analizar una operación relevante para el control.

Por este motivo, la evaluación considera conjuntamente precisión, recall y F1. El recall permite controlar cuántos casos relevantes son recuperados, mientras que la precisión indica qué proporción de las operaciones priorizadas resulta efectivamente pertinente. También se utiliza la precisión en las primeras k operaciones, porque representa la calidad de la cola limitada que recibiría el equipo de revisión.

## 3. Modelado e IA

### 3.1 Diagnóstico reproducible de H1 y H3b

H1 y H3b fueron evaluadas como candidatas a hipótesis rectora. H1 demostró que la normalización y el contexto permiten resolver la vinculación de las cargas con la flota; no obstante, se mantiene como condición habilitante porque corresponde principalmente a un problema de integración y calidad de datos.

H3b fue evaluada sobre 34.826 cargas sintéticas, de las cuales 375 correspondían al evento analizado, equivalente al 1,1 %. La unidad de análisis fue cada operación de carga y las semillas utilizadas para diseñar los métodos fueron diferentes de las empleadas para evaluarlos.

Las etiquetas ground_truth, tipo_anomalia y casos_legitimos se utilizaron exclusivamente para evaluar los resultados y no fueron incorporadas como variables predictoras.

### 3.2 Selección de la hipótesis rectora

Se selecciona H3b como hipótesis rectora porque vincula directamente la evidencia disponible con la decisión de priorizar cargas para revisión. Además, permite comprobar cuánto aporta el contexto del negocio frente a una regla volumétrica simple y frente a modelos de aprendizaje automático.

Su madurez se eleva a nivel Diagnóstico dentro del escenario sintético evaluado, ya que el análisis no solo identifica cargas con exceso volumétrico, sino que explica la priorización a partir de la capacidad del tanque, el comportamiento habitual del vehículo y la acumulación de cargas durante el día. Este nivel no implica validación sobre datos reales ni confirma irregularidades.

### 3.3 Variables seleccionadas y justificación

Para evaluar H3b se utilizaron variables disponibles antes de conocer la etiqueta de evaluación. La selección combina características propias de la operación con variables contextuales construidas a partir de la flota y del historial de cargas.

| Variable | Justificación |
|---|---|
| `litros` | Representa el volumen registrado en la operación. |
| `capacidad_tanque` | Permite evaluar el volumen según la capacidad física del vehículo. |
| `ratio_litros_tanque` | Expresa qué proporción de la capacidad representa la carga. |
| `litros_vs_habitual` | Compara la operación con el comportamiento histórico del mismo vehículo. |
| `tanques_en_el_dia` | Acumula el volumen diario y permite reconocer cargas fraccionadas o repetidas. |
| `tipo_vehiculo` | Aporta contexto sobre las diferencias operativas entre categorías de vehículos. |
| `tipo_combustible` | Permite verificar la coherencia entre la carga y el combustible asignado. |
| `hora` y variables temporales | Incorporan el momento de la operación como información contextual. |

ratio_litros_tanque, litros_vs_habitual y tanques_en_el_dia son las variables principales de la regla contextual. Para comprobar si los modelos encontraban una señal adicional, también se los evaluó excluyendo estas variables.

Las etiquetas utilizadas para medir el resultado no fueron incluidas como variables de entrada, evitando que los modelos conocieran anticipadamente la respuesta correcta.

### 3.4 Línea base ingenua

La línea base ingenua utiliza únicamente la comparación directa entre los litros cargados y la capacidad del tanque. Una operación se prioriza cuando el volumen registrado supera esa capacidad, sin considerar tolerancias, historial ni cargas acumuladas durante el día.

Esta regla obtuvo una precisión de 0,71, un recall de 1,00, un F1 de 0,83 y una precisión en las primeras k operaciones de 0,71. Su recall elevado muestra que recupera los casos etiquetados, pero su menor precisión indica que también prioriza operaciones legítimas que requieren contexto adicional.

Como referencia del desbalance, un clasificador que siempre predijera la clase mayoritaria alcanzaría una exactitud aproximada del 98,9 %, pero tendría recall y F1 iguales a cero para la clase de interés. Por eso la exactitud no se utiliza como métrica principal.

### 3.5 Modelo baseline

Se evaluaron tres familias de modelos baseline: Isolation Forest, regresión logística y Random Forest. Los modelos supervisados se entrenaron con semillas diferentes de las utilizadas en la evaluación, manteniendo un umbral fijo de 0,5.

La comparación se realizó en dos condiciones: utilizando todas las variables disponibles y excluyendo ratio_litros_tanque, litros_vs_habitual y tanques_en_el_dia, que son las variables que definen la regla contextual. Esta segunda condición permite comprobar si los modelos encuentran una señal adicional o si solamente reproducen el conocimiento ya incorporado en la regla.

### 3.6 Métricas y comparación

Debido al desbalance del target, la evaluación se realizó mediante precisión, recall, F1, precisión promedio y precisión en las primeras k operaciones. Esta última métrica indica qué proporción de las primeras 375 cargas priorizadas corresponde efectivamente a la clase evaluada.

| Método | Precisión | Recall | F1 | Precisión promedio | Precisión primeras k |
|---|---:|---:|---:|---:|---:|
| Línea base ingenua | 0,71 | 1,00 | 0,83 | 0,69 | 0,71 |
| Regla con contexto | 0,95 | 1,00 | 0,98 | 0,94 | 0,97 |
| Isolation Forest | 0,06 | 0,42 | 0,10 | 0,06 | 0,04 |
| Regresión logística, todas las variables | 0,30 | 1,00 | 0,46 | 0,77 | 0,74 |
| Random Forest, todas las variables | 1,00 | 0,99 | 1,00 | 1,00 | 1,00 |
| Regresión logística, sin variables de la regla | 0,03 | 0,70 | 0,06 | 0,06 | 0,15 |
| Random Forest, sin variables de la regla | 0,52 | 0,08 | 0,14 | 0,31 | 0,34 |

La regla con contexto mejora el F1 de 0,83 a 0,98 y la precisión en las primeras k operaciones de 0,71 a 0,97 respecto de la línea base ingenua.

El Random Forest alcanza resultados prácticamente perfectos cuando recibe las variables que definen la regla, lo que indica que logra aprender ese mismo criterio. Al excluirlas, su F1 desciende a 0,14 y su precisión en las primeras k operaciones a 0,34. Este último valor supera ampliamente el 1,1 % esperado por azar, pero no alcanza el desempeño de la regla ingenua ni de la regla contextual.

Por lo tanto, con las variables y los datos disponibles, los modelos evaluados no aportan una mejora independiente frente a la regla contextual. La evidencia favorece una solución explicable y reproducible basada en conocimiento del dominio.

Limitación: los resultados provienen de datos sintéticos etiquetados. La prevalencia observada en este escenario es del 1,1 %, mientras que el agregado real aprobado es cercano al 0,03 %. En consecuencia, estas métricas permiten comparar métodos dentro del experimento, pero no deben trasladarse directamente al escenario real.

## 4. Producto y Gestión

### 4.1 Estado y madurez de la hipótesis rectora

H3b se selecciona como hipótesis rectora y pasa de madurez Descriptiva a Diagnóstica dentro del escenario sintético evaluado. El cambio se justifica porque la evidencia no se limita a describir cargas elevadas: permite explicar su priorización mediante la capacidad del tanque, el historial del vehículo y las cargas acumuladas durante el día.

La hipótesis queda respaldada para continuar, pero no validada sobre datos reales. La diferencia entre la prevalencia sintética y el agregado real aprobado, junto con la forma en que se generaron las etiquetas, impide considerar los resultados como una medición del desempeño operativo definitivo.

| Hipótesis | Estado al cierre del Sprint 4 | Madurez | Decisión |
|---|---|---|---|
| H3b | Rectora, respaldada en el escenario sintético | Diagnóstica | Continuar con regla contextual y validar externamente |
| H1 | Resuelta como condición habilitante | Diagnóstica | Mantener normalización y controles de vinculación |
| Restantes | Pendientes de evidencia suficiente | Descriptiva | Permanecen en el backlog |



### 4.2 Ciclo 3 de CRISP-DM

| Fase CRISP-DM | Trabajo realizado en el Sprint 4 |
|---|---|
| Comprensión del negocio | Se definió la priorización de cargas para revisión como decisión principal. |
| Comprensión de los datos | Se examinó el desbalance, la unidad de análisis y la disponibilidad de etiquetas. |
| Preparación de los datos | Se construyeron variables contextuales y se separaron semillas de diseño y evaluación. |
| Modelado | Se compararon la línea ingenua, la regla contextual, Isolation Forest, regresión logística y Random Forest. |
| Evaluación | Se utilizaron precisión, recall, F1, precisión promedio y precisión en las primeras k operaciones. |
| Decisión | Se seleccionó H3b y se recomendó conservar la regla contextual frente a los modelos evaluados. |

### 4.3 Backlog actualizado

| Elemento del backlog | Estado al cierre del Sprint 4 | Próxima acción | Prioridad |
|---|---|---|---|
| H3b — Exceso volumétrico con contexto | Seleccionada como hipótesis rectora; respaldada en el escenario sintético | Validar la regla contextual con datos y criterios independientes | Alta |
| H1 — Vinculación de cargas con la flota | Resuelta como condición habilitante | Mantener controles de normalización, vínculos ambiguos y no resueltos | Alta |
| H2b y H2c — Retrocesos y saltos de odómetro | Pendientes de mayor evidencia | Contrastar secuencias y excepciones vigentes | Media |
| H4, H5 y H6 | No seleccionadas como rectoras | Conservar para nuevas evaluaciones si existen datos suficientes | Media |
| H7 a H13 | No seleccionadas como rectoras | Mantener en el backlog y revisar su viabilidad con fuentes reales | Media |
| Validación de H3b | Pendiente sobre datos reales etiquetados | Comparar prevalencia, precisión y cobertura sin extrapolar métricas sintéticas | Alta |
| Pipeline reproducible | Completado para la evaluación sintética | Conservar código, semillas, resultados y pruebas automáticas | Alta |
| Informe técnico | En elaboración | Incorporar método, resultados, limitaciones y recomendación final | Alta |

Las hipótesis no seleccionadas no se consideran descartadas. Permanecen en el backlog porque todavía no cuentan con evidencia suficiente o porque requieren fuentes y validaciones adicionales. La prioridad inmediata se concentra en validar H3b y conservar H1 como control indispensable de integración.

### 4.4 Borrador del informe técnico

Problema: priorizar operaciones de combustible que requieren revisión humana.

Hipótesis rectora: H3b, basada en la relación entre el volumen cargado, la capacidad del tanque, el comportamiento habitual del vehículo y las cargas acumuladas durante el día.

Datos de evaluación: 34.826 cargas sintéticas correspondientes a cinco semillas, con 375 casos etiquetados para H3b. Las semillas utilizadas para diseñar los métodos fueron diferentes de las empleadas para evaluarlos.

Métodos comparados: línea base ingenua, regla contextual, Isolation Forest, regresión logística y Random Forest, incluyendo evaluaciones con y sin las variables que definen la regla.

Resultado principal: la regla contextual obtuvo un F1 de 0,98 y una precisión en las primeras k operaciones de 0,97. Los modelos no lograron superarla cuando se excluyeron las variables que componen esa regla.

Recomendación: utilizar la regla contextual como mecanismo inicial de priorización por su rendimiento, reproducibilidad e interpretación, y mantener los modelos como evidencia experimental hasta disponer de datos reales etiquetados de forma independiente.

Limitación principal: la evaluación utiliza etiquetas sintéticas y presenta una prevalencia diferente de la observada en los agregados reales. Por ello, los resultados no representan todavía una validación operativa.

### 4.5 Retrospectiva

| Aspecto | Síntesis |
|---|---|
| Qué funcionó | La evaluación reproducible, la separación de semillas y la comparación de métodos con métricas adecuadas al desbalance. |
| Qué aprendimos | El contexto del negocio aporta más valor que la complejidad del modelo para H3b. |
| Qué debe mejorar | La validación con datos reales etiquetados y la independencia entre las reglas de generación y evaluación. |
| Decisión | Continuar con H3b y la regla contextual, sin presentar el modelo como solución operativa definitiva. |

## 5. Pendientes para el Sprint 5

Validar H3b con evidencia real o agregados aprobados sin extrapolar las métricas sintéticas.
Evaluar la viabilidad operativa de la regla contextual y definir sus límites de aplicación.
Documentar el pipeline reproducible desde la preparación de los datos hasta la priorización.
Establecer el criterio para continuar, ajustar o pivotar la solución.
Identificar quién realizará la validación externa dentro de la organización.
Preparar el informe de viabilidad y el plan de continuidad para PP2.

## Trazabilidad

La selección y evaluación de la hipótesis rectora se documentan en la issue #75. La implementación reproducible de los métodos y sus pruebas corresponde al PR #78.

La evidencia generada se conserva en:
- docs/sprints/sprint-4/evidencias/resultados_h3b.md
- docs/sprints/sprint-4/evidencias/resultados_h3b.json
- deteccion/baseline.py
- tests/test_baseline.py
Los resultados fueron obtenidos mediante:

python -m deteccion.baseline H3b --salida resultados_h3b.md

Las etiquetas se utilizaron exclusivamente para evaluar los métodos. No fueron incorporadas como variables predictoras.
