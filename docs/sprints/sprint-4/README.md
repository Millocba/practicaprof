# Sprint 4 — Modelado y primera evaluación

> Documento de trabajo. La hipótesis rectora todavía no está definida: se decidirá después de comparar el diagnóstico real de H1 y H3b.

## 1. Conclusión del sprint

Pendiente de completar al cierre. Debe presentar primero el resultado principal, la hipótesis seleccionada, la comparación breve entre métodos y el alcance de la evidencia.

## 2. Negocio y Datos

### 2.1 Condición de piso

La hipótesis rectora debe alcanzar una madurez Diagnóstica o superior. Al cierre del Sprint 3, H1 figura en Diagnóstico y H3b en Descriptivo. El Sprint 4 compara ambas con evidencia nueva antes de elegir la rectora.

### 2.2 Hipótesis candidatas

| Hipótesis | Problema que analiza | Evidencia que falta |
|---|---|---|
| H1 | Vinculación de las operaciones con un móvil. | Explicar las causas de los vínculos fallidos o ambiguos sobre los datos reales disponibles. |
| H3b | Cargas que superan la capacidad registrada. | Separar capacidad posiblemente mal registrada, posible uso indebido y evidencia insuficiente. |

### 2.3 Decisión que se busca apoyar

Priorizar operaciones de combustible que requieren revisión humana, conservando la explicación de por qué cada caso fue señalado.

### 2.4 Costo de los errores

Pendiente de acordar con el equipo:

- **Falso positivo:** revisar una operación legítima.
- **Falso negativo:** no priorizar una operación que requería revisión.

## 3. Modelado e IA

### 3.1 Diagnóstico reproducible de H1 y H3b

Pendiente de incorporar los agregados aprobados obtenidos de la ejecución sobre datos reales.

Para H1 se deben explicar las cargas sin móvil identificado y separar las causas de vinculación. Para H3b se deben diferenciar los excesos atribuibles a una capacidad posiblemente mal registrada, los compatibles con un posible uso indebido y los casos sin evidencia suficiente.

### 3.2 Selección de la hipótesis rectora

Pendiente. La decisión debe comparar madurez, evidencia causal, relevancia de negocio, cobertura y posibilidad de evaluación reproducible. La hipótesis no seleccionada permanece en el backlog.

### 3.3 Variables seleccionadas y justificación

Pendiente de definir después de seleccionar la hipótesis rectora. Cada variable deberá justificarse individualmente y ninguna etiqueta de evaluación podrá utilizarse como variable predictora.

### 3.4 Línea base ingenua

Pendiente de definir sobre la misma unidad de análisis y el mismo target que los demás métodos.

### 3.5 Modelo baseline

Pendiente. Debe ser un modelo sencillo e interpretable que permita comprobar si el aprendizaje automático mejora la referencia básica.

### 3.6 Métricas y comparación

Se informarán precisión, recall, F1 y matriz de confusión. La exactitud no será la métrica principal si la clase positiva está desbalanceada. Los datos utilizados para diseñar o ajustar los métodos deberán mantenerse separados de los utilizados para evaluarlos.

## 4. Producto y Gestión

### 4.1 Estado y madurez de la hipótesis rectora

Pendiente de la comparación diagnóstica.

### 4.2 Ciclo 3 de CRISP-DM

Pendiente de documentar con las decisiones y evidencias del Sprint 4.

### 4.3 Backlog actualizado

Pendiente de registrar la hipótesis rectora, la hipótesis no seleccionada y las tareas que continúan.

### 4.4 Borrador del informe técnico

Pendiente. Incluirá método, resultados, límites y trazabilidad.

### 4.5 Retrospectiva

Pendiente de completar al cierre del sprint.

## 5. Pendientes para el Sprint 5

Se completará al cierre con las limitaciones encontradas, las decisiones pendientes y los próximos pasos.

## Trazabilidad

- Issue de trabajo: #75.
- Los resultados reales se incorporarán únicamente como agregados aprobados.
- No se anticipa la selección de la hipótesis rectora ni resultados de modelos.
- `ground_truth`, `tipo_anomalia` y `casos_legitimos` no se utilizarán como variables predictoras.
