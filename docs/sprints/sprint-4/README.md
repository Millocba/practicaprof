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

H3b fue elegida por el equipo porque responde directamente a la decisión principal de SIFAD y permite comparar, en el escenario sintético etiquetado (375 casos), una regla simple, una regla contextual y distintos modelos baseline. La regla contextual mejoró el F1 de 0,83 a 0,98 y la precisión en las primeras k operaciones de 0,71 a 0,97.

En los datos reales aprobados el volumen de H3b es mucho menor: 66 cargas con exceso de más de 2 %, en 23 vehículos, frente a 288 alertas con contexto de H1, 2.065 de H4 y 6.535 cargas sin registro de H8. H1 tiene la evidencia real más sólida y madurez Diagnóstica; H3b se elige por su relación con la decisión de priorización y por su explicabilidad, no por tener más casos reales.

H1 continúa siendo una condición habilitante fundamental para integrar las fuentes mediante identificadores normalizados. Sin embargo, no se selecciona como rectora porque su problema ya puede resolverse mediante una regla determinística y se relaciona principalmente con la calidad y vinculación de los datos, no directamente con la priorización de cargas.

### 2.3 Decisión que se busca apoyar

La decisión que SIFAD busca apoyar es qué operaciones de combustible deben priorizarse para una revisión humana. En H3b, una carga se prioriza cuando supera en más de 2 % la capacidad registrada del tanque, y el historial del vehículo distingue el exceso que aparece desde sus primeras cargas —patrón persistente compatible con una capacidad mal registrada u otra inconsistencia de asignación— del que aparece después de un historial normal —exceso posterior sin causa identificada que requiere revisión—.

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

H3b alcanza una madurez Diagnóstica inicial para esta etapa. La evidencia sintética reproducible y los agregados reales publicables permiten diferenciar un patrón persistente desde las primeras cargas, casos con evidencia de error de asignación o carga, excesos posteriores a un historial normal y operaciones no evaluables por falta de capacidad. Esta lectura avanza desde la descripción hacia una explicación contextual, pero no implica validación operativa sobre datos reales, no confirma irregularidades ni atribuye responsabilidades. La selección y la madurez quedan sujetas a revisión si nueva evidencia modifica la interpretación.

### 3.3 Variables seleccionadas y justificación

Los modelos usan las 15 variables que construye `deteccion/modelo.py` para cada carga; ninguna incorpora la etiqueta de evaluación. Se justifican una por una:

| Variable | Qué mide | Por qué entra |
|---|---|---|
| `ratio_litros_tanque` (*) | Litros cargados sobre la capacidad del tanque. | Es el criterio base del exceso volumétrico. |
| `litros_vs_habitual` (*) | Litros sobre la mediana de litros del propio vehículo. | Compara la carga con el historial del vehículo. |
| `tanques_en_el_dia` (*) | Litros del día sobre la capacidad. | Acumulación de cargas en una misma jornada. |
| `km` | Cambio de odómetro desde la carga anterior válida. | Recorrido: separa un uso real de uno sin recorrido. |
| `exceso_km` | Kilómetros por encima del ritmo habitual del vehículo. | Recorrido inusual para el vehículo. |
| `rendimiento_relativo` | Kilómetros por litro del día frente al habitual del vehículo. | Relaciona el combustible con el recorrido. |
| `retroceso_km` | Kilómetros que retrocede el odómetro (0 si avanza). | Lectura de odómetro dudosa. |
| `cargas_en_el_dia` | Cargas del vehículo en el día. | Indicio de fraccionamiento. |
| `litros_vs_autorizado` | Litros sobre los litros autorizados en el pedido. | Respaldo en el registro interno. |
| `sin_solicitud` | 1 si la carga no tiene pedido. | Carga sin respaldo. |
| `odometro_exceptuado` | 1 si hay una excepción de odómetro vigente. | Explica lecturas repetidas. |
| `vehiculo_inactivo` | 1 si la carga es posterior a la baja o salida de servicio. | Carga que no debería existir. |
| `distancia_zona_km` | Distancia entre la estación y la zona habitual del vehículo. | Carga lejos de la base. |
| `distancia_gps_km` | Distancia entre la estación y el recorrido del GPS. | Carga lejos del recorrido. |
| `sin_gps` | 1 si no hay posición GPS ese día. | Falta de dato. |

(*) Variables derivadas de los litros. Se excluyeron en el segundo escenario para comprobar si los modelos encuentran señal propia. Es un criterio de diseño del equipo: la regla contextual de H3b se define con la capacidad registrada (con tolerancia del 2 %) y el historial del vehículo, y estas tres variables están estrechamente relacionadas con ella.

**Qué sostiene al modelo sin esas tres variables.** Con el Random Forest sin las variables derivadas de los litros, las que más pesan (importancia por permutación) son `km` (0,22), `rendimiento_relativo` (0,15) y `litros_vs_autorizado` (0,12); el resto pesa menos de 0,02. Al quitar la más importante, el F1 baja de 0,14 a 0,10, y al quitar las dos primeras, a 0,00. El desempeño residual de ese modelo depende, entonces, de variables de recorrido y de respaldo en el pedido, no de los litros. La tabla se genera con `python -m deteccion.baseline H3b --explicar`.

### 3.4 Línea base ingenua

La línea base ingenua utiliza únicamente la comparación directa entre los litros cargados y la capacidad del tanque. Una operación se prioriza cuando el volumen registrado supera esa capacidad, sin considerar tolerancias, historial ni cargas acumuladas durante el día.

Esta regla obtuvo una precisión de 0,71, un recall de 1,00, un F1 de 0,83 y una precisión en las primeras k operaciones de 0,71. Su recall elevado muestra que recupera los casos etiquetados, pero su menor precisión indica que también prioriza operaciones legítimas que requieren contexto adicional.

Como referencia del desbalance, un clasificador que siempre predijera la clase mayoritaria alcanzaría una exactitud aproximada del 98,9 %, pero tendría recall y F1 iguales a cero para la clase de interés. Por eso la exactitud no se utiliza como métrica principal.

### 3.5 Modelo baseline

Se evaluaron tres familias de modelos baseline: Isolation Forest, regresión logística y Random Forest. Los modelos supervisados se entrenaron con semillas diferentes de las utilizadas en la evaluación, manteniendo un umbral fijo de 0,5.

La comparación se realizó en dos condiciones: utilizando todas las variables disponibles y excluyendo ratio_litros_tanque, litros_vs_habitual y tanques_en_el_dia, las variables derivadas de los litros. Esta segunda condición permite comprobar si los modelos encuentran una señal adicional o si solamente reproducen el conocimiento ya incorporado en la regla.

### 3.6 Métricas y comparación

Debido al desbalance del target, la evaluación se realizó mediante precisión, recall, F1, precisión promedio y precisión en las primeras k operaciones. Esta última métrica indica qué proporción de las primeras k cargas priorizadas corresponde efectivamente a la clase evaluada; k es la cantidad de casos reales de cada semilla (unos 75) y el resultado es el promedio de las cinco semillas.

| Método | Precisión | Recall | F1 | Precisión promedio | Precisión primeras k |
|---|---:|---:|---:|---:|---:|
| Línea base ingenua | 0,71 | 1,00 | 0,83 | 0,69 | 0,71 |
| Regla con contexto | 0,95 | 1,00 | 0,98 | 0,94 | 0,97 |
| Isolation Forest | 0,06 | 0,42 | 0,10 | 0,06 | 0,04 |
| Regresión logística, todas las variables | 0,30 | 1,00 | 0,46 | 0,77 | 0,74 |
| Random Forest, todas las variables | 1,00 | 0,99 | 1,00 | 1,00 | 1,00 |
| Regresión logística, sin variables de la regla | 0,03 | 0,70 | 0,06 | 0,06 | 0,15 |
| Random Forest, sin variables de la regla | 0,52 | 0,08 | 0,14 | 0,31 | 0,34 |

La precisión en las primeras k del Random Forest sin variables de la regla varió entre 0,33 y 0,34 en distintas ejecuciones, porque depende del orden de los empates; el resto de las cifras fue idéntico.

La regla con contexto mejora el F1 de 0,83 a 0,98 y la precisión en las primeras k operaciones de 0,71 a 0,97 respecto de la línea base ingenua.

El Random Forest alcanza resultados prácticamente perfectos cuando recibe las variables que definen la regla, lo que indica que logra aprender ese mismo criterio. Al excluirlas, su F1 desciende a 0,14 y su precisión en las primeras k operaciones a 0,34. Este último valor supera ampliamente el 1,1 % esperado por azar, pero no alcanza el desempeño de la regla ingenua ni de la regla contextual.

Por lo tanto, con las variables y los datos disponibles, los modelos evaluados no aportan una mejora independiente frente a la regla contextual. La evidencia favorece una solución explicable y reproducible basada en conocimiento del dominio.

Limitación: los resultados provienen de datos sintéticos etiquetados. La prevalencia observada en este escenario es del 1,1 %, mientras que el agregado real aprobado es cercano al 0,03 %. En consecuencia, estas métricas permiten comparar métodos dentro del experimento, pero no deben trasladarse directamente al escenario real.

## 4. Producto y Gestión

### 4.1 Estado y madurez de la hipótesis rectora

H3b se selecciona como hipótesis rectora y el equipo la declara **Diagnóstica**. El nivel Diagnóstico exige una explicación sustentada de los factores que producen el hallazgo, y el equipo fijó este criterio antes de mirar el resultado: la mayoría de las cargas con exceso debe tener una causa explicada por fuentes ajenas a la regla.

**Evidencia real (agregados, sin filas):** en los datos reales hay 66 cargas con exceso volumétrico, en 23 vehículos. Se las clasificó por causa con fuentes distintas de la propia regla (padrón, vinculación por tarjeta y dominio, historial de capacidad):

| Causa | Cargas | Proporción |
|---|---:|---:|
| Error de vinculación (tarjeta o dominio equivocado) | 39 | 59 % |
| Sin explicación por fuentes ajenas a la regla | 27 | 41 % |

- La causa dominante es el error de vinculación, que se corrige en la carga y no es una conducta del conductor.
- La causa "capacidad del padrón inconsistente" no aparece en los datos reales. En el generador sintético, en cambio, es la causa principal de la anomalía; esa diferencia se declara como límite y no se corrige en el generador.
- Las cargas sin explicación se declaran **casos para revisión por posible uso indebido**. La evidencia descarta las causas administrativas conocidas, pero no prueba intención: pueden ser un error puntual de tipeo o de medición, y solo una revisión documental puede calificarlas.
- Los grupos de menos de 20 vehículos o cargas no se detallan (regla de grupos chicos).
- La corrida real que respalda esta tabla está en revisión (PR #80) y no está aprobada todavía.

La hipótesis queda respaldada y diagnosticada, pero su rendimiento no está validado sobre datos reales etiquetados. La diferencia entre la prevalencia sintética (1,1 %) y la real (66 cargas en unas 217 mil, 0,03 %), junto con la forma en que se generaron las etiquetas, impide considerar las métricas sintéticas como una medición del desempeño operativo.

La lectura diagnóstica se apoya únicamente en resultados publicables. Los grupos pequeños se informan de manera agrupada y no se combinan totales que permitan reconstruirlos por resta. Tanto la elección de H3b como su clasificación y madurez quedan sujetas a revisión si nuevos datos o evaluaciones modifican la evidencia disponible.

| Hipótesis | Estado al cierre del Sprint 4 | Madurez | Decisión |
|---|---|---|---|
| H3b | Rectora: regla evaluada en sintético y causas del exceso explicadas en datos reales (59 % de las cargas) | Diagnóstica (decisión del equipo) | Conservar la regla contextual; revisar el residuo como posible uso indebido |
| H1 | Validada de manera condicionada; condición habilitante | Diagnóstica | Mantener controles de normalización y vinculación |
| H9 | Con evidencia real sólida: la factura toma el precio de empresa y el PDF coincide con la deuda | Sin actualizar en este sprint | Evaluar su madurez con el equipo |
| Restantes | Pendientes de evidencia suficiente | Descriptiva | Permanecen en el backlog |



### 4.2 Ciclo 3 de CRISP-DM

| Fase CRISP-DM | Trabajo realizado en el Sprint 4 |
|---|---|
| Comprensión del negocio | Se definió la priorización de cargas para revisión como decisión principal. |
| Comprensión de los datos | Se examinó el desbalance, la unidad de análisis y la disponibilidad de etiquetas. |
| Preparación de los datos | Se construyeron variables contextuales y se separaron semillas de diseño y evaluación. |
| Modelado | Se compararon la línea ingenua, la regla contextual, Isolation Forest, regresión logística y Random Forest. |
| Evaluación | Se utilizaron precisión, recall, F1, precisión promedio y precisión en las primeras k operaciones. |
| Decisión | Se seleccionó H3b, se la declaró Diagnóstica con evidencia real y se recomendó conservar la regla contextual frente a los modelos evaluados. |

### 4.3 Backlog actualizado

| Elemento del backlog | Estado al cierre del Sprint 4 | Próxima acción | Prioridad |
|---|---|---|---|
| H3b — Exceso volumétrico con contexto | Rectora y Diagnóstica; 59 % de las cargas con exceso explicadas por error de vinculación | Revisar documentalmente el 41 % restante (posible uso indebido) y aprobar la corrida real del PR #80 | Alta |
| H1 — Vinculación de cargas con la flota | Validada de manera condicionada; condición habilitante | Mantener controles sobre vínculos ambiguos y no resueltos | Alta |
| H2b y H2c — Retrocesos y saltos de odómetro | Pendientes de mayor evidencia | Contrastar secuencias, lecturas inválidas y excepciones vigentes | Media |
| H4, H5 y H7 | Descartadas como candidatas rectoras independientes para PP1; no se descartan como reglas operativas | Conservar la evidencia de ablación; solo podrían reevaluarse con etiquetas reales independientes | Media |
| H6, H8, H9, H10, H11 y H12 | Pendientes de evidencia suficiente | Evaluar su viabilidad según la disponibilidad y calidad de las fuentes | Media |
| H13 — Cargas asociadas con contingencias | Inconclusa: la señal no cae al retirar las variables principales | Revisar el generador y posibles variables que anticipen la etiqueta antes de continuar | Alta |
| Validación de H3b | Pendiente sobre datos reales etiquetados | Comparar prevalencia, precisión y cobertura sin extrapolar métricas sintéticas | Alta |
| Brecha de causas sintético-real | El generador modela la capacidad mal registrada como causa principal; en lo real domina el error de vinculación | Documentar y, si el equipo lo decide, ajustar el escenario sintético sin tocar el origen de los datos | Alta |
| Fuga entre bloques de H3b en el agregado aprobado | La resta entre bloques deja deducir un grupo chico | Decidir si se corrige el agregado aprobado | Media |
| Variables nuevas para el modelo | Con las 15 actuales el modelo no supera la regla al quitar las variables que la definen | Incorporar variables independientes de la regla | Media |
| Pull requests abiertos | #76 (H12) y #80 (exceso por causa y fraccionamiento de H4); #73 (pruebas de excepciones) y #81 (orden del odómetro) en revisión | Revisar y fusionar por separado | Media |
| Pipeline reproducible | Completado para la evaluación sintética | Conservar código, semillas, resultados y pruebas automáticas | Alta |
| Informe técnico | En elaboración | Incorporar método, resultados, limitaciones y recomendación final | Alta |

Los criterios cuantitativos de éxito de H7 a H13 no se fijan retroactivamente. Para esas hipótesis aún no se definieron la unidad de análisis, la métrica, el umbral ni la evidencia mínima aceptable. Las hipótesis sin evidencia suficiente permanecen pendientes. H4, H5 y H7 se descartan únicamente como candidatas rectoras independientes para PP1 porque la ablación no sostiene señal propia; pueden conservarse como reglas operativas y reevaluarse con datos reales independientes. Descartar una candidatura con evidencia no implica que la situación de negocio sea inexistente.

### 4.4 Borrador del informe técnico

Problema: priorizar operaciones de combustible que requieren revisión humana.

Hipótesis rectora: H3b, exceso volumétrico respecto de la capacidad registrada, con tolerancia del 2 % y clasificado según el historial del vehículo. H1 se conserva como condición habilitante validada de manera condicionada; H4, H5 y H7 se descartan solamente como candidatas rectoras independientes, y H13 permanece inconclusa. Madurez: Diagnóstica (decisión del equipo), con la causa del exceso explicada por error de vinculación en el 59 % de las cargas reales con exceso.

Datos de evaluación: 34.826 cargas sintéticas correspondientes a cinco semillas, con 375 casos etiquetados para H3b. Las semillas utilizadas para diseñar los métodos fueron diferentes de las empleadas para evaluarlos.

Métodos comparados: línea base ingenua, regla contextual, Isolation Forest, regresión logística y Random Forest, incluyendo evaluaciones con y sin las variables que definen la regla.

Resultado principal: la regla contextual obtuvo un F1 de 0,98 y una precisión en las primeras k operaciones de 0,97. Los modelos no lograron superarla cuando se excluyeron las variables que componen esa regla.

Recomendación: utilizar la regla contextual como mecanismo inicial de priorización por su rendimiento, reproducibilidad e interpretación, y mantener los modelos como evidencia experimental hasta disponer de datos reales etiquetados de forma independiente.

Diagnóstico con datos reales: de 66 cargas con exceso, 39 (59 %) se explican por error de vinculación y 27 (41 %) quedan como casos para revisión por posible uso indebido.

Limitación principal: la evaluación utiliza etiquetas sintéticas y presenta una prevalencia diferente de la observada en los agregados reales. Por ello, los resultados no representan todavía una validación operativa.

### 4.5 Retrospectiva

| Aspecto | Síntesis |
|---|---|
| Qué funcionó | La evaluación reproducible, la separación de semillas y la comparación de métodos con métricas adecuadas al desbalance. |
| Qué aprendimos | El contexto del negocio aporta más valor que la complejidad del modelo para H3b. |
| Qué debe mejorar | La validación con datos reales etiquetados y la independencia entre las reglas de generación y evaluación. |
| Decisión | Continuar con H3b y la regla contextual, sin presentar el modelo como solución operativa definitiva. |

## 5. Pendientes para el Sprint 5

Revisar el residuo sin explicación de H3b (posible uso indebido) con la fuente documental.
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

