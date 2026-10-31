# Sprint 5 — Evaluación de viabilidad y cierre de PP1

> Pregunta eje: ¿La solución propuesta es técnicamente reproducible, operativamente útil y suficientemente validada para continuar su desarrollo en PP2?

## 1. Conclusión del sprint

Pendiente de completar con la decisión final de continuar, ajustar o pivotar la solución.

## 2. Negocio y Datos

### 2.1 Decisión que se evalúa

Determinar si la regla contextual de H3b puede utilizarse como mecanismo inicial para priorizar operaciones de combustible que requieren revisión humana.

### 2.2 Valor esperado para el negocio

Pendiente de validación con el referente de la organización.

### 2.3 Límites de interpretación

La priorización no confirma fraude, irregularidades ni responsabilidades. Su propósito es ordenar casos para una revisión humana utilizando la información disponible sobre la carga, el vehículo y su historial.

### 2.4 Validación externa

Pendiente de obtener y documentar una devolución del referente de la organización sobre la utilidad, claridad y aplicabilidad de la propuesta.

## 3. Modelado e IA

### 3.1 Prueba de concepto

La prueba de concepto integra generación reproducible de datos sintéticos, preparación e integración de fuentes, construcción de variables, aplicación de reglas contextuales, comparación con modelos baseline y presentación de resultados mediante Streamlit.

La POC no determina la existencia de fraude ni automatiza decisiones operativas. Su alcance consiste en demostrar que SIFAD puede generar una cola explicable de operaciones priorizadas para revisión humana.

### 3.2 Pipeline reproducible

El recorrido técnico verificado comprende:

1. instalación de las dependencias;
2. ejecución de las pruebas automáticas;
3. generación reproducible de los escenarios mediante semillas;
4. construcción de variables para cada carga;
5. aplicación de la línea base ingenua y de la regla contextual de H3b;
6. evaluación de los modelos baseline;
7. generación de resultados en Markdown y JSON;
8. consulta de los resultados mediante la aplicación Streamlit.

La instalación y verificación general se realizan mediante:

```bash
pip install -r requirements.txt
python -m pytest -q

## 4. Producto y Gestión

### 4.1 Decisión de viabilidad

Pendiente de definir una de las siguientes decisiones:

- continuar;
- continuar con ajustes;
- pivotar;
- detener.

### 4.2 Backlog final de PP1

Pendiente de actualizar con el estado final, evidencia, madurez, prioridad y destino de cada hipótesis.

### 4.3 Plan de continuidad para PP2

Pendiente de definir qué componentes se transfieren a PP2, bajo qué condiciones y con qué validaciones adicionales.

### 4.4 Retrospectiva final

Pendiente de completar con los aprendizajes, dificultades, decisiones y mejoras del equipo.

## 5. Informe de viabilidad

### 5.1 Alcance alcanzado

Pendiente.

### 5.2 Evidencia disponible

Pendiente.

### 5.3 Riesgos y limitaciones

Pendiente.

### 5.4 Recomendación final

Pendiente.

## 6. Trazabilidad

Pendiente de incorporar issues, pull requests, comandos, pruebas, evidencias y versión final del repositorio.