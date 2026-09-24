# Método de generación de datos sintéticos

## Objetivo

Generar datasets reproducibles que respeten el modelo relacional y exhiban problemáticas conocidas sin derivar registros individuales de una fuente real.

## Entradas del generador

- Versión del esquema sintético.
- Escenario de calidad.
- Semilla.
- Volúmen objetivo por entidad.
- Distribuciones paramétricas o agregadas aprobadas.
- Reglas de coherencia.
- Catálogo y tasa de anomalías.

## Fases

### 1. Configuración

Validar escenario, semilla, rangos y compatibilidad con el esquema. Registrar una `ejecucion_dataset` antes de producir entidades.

### 2. Catálogos y organización

Crear unidades, subunidades, tipos, estados, roles y productos completamente ficticios. Los vocabularios no deben contener nombres externos.

### 3. Entidades maestras

Generar vehículos, personas, contratos, tarjetas y dispositivos con identificadores inequívocamente sintéticos. Aplicar relaciones y cardinalidades del modelo limpio.

### 4. Series y eventos

Simular actividad por períodos: telemetría, desplazamientos, cargas, solicitudes y facturación. Las variables correlacionadas deben compartir una causa simulada; por ejemplo, distancia, consumo y odómetro.

### 5. Inyección de problemáticas

Aplicar transformaciones deterministas según el escenario: duplicar, omitir, alterar formato, romper una relación, introducir desfase temporal o crear una anomalía operativa. Nunca mezclar inyección con la generación base sin registrar qué cambió.

### 6. Verdad sintética

Registrar por separado entidad, ID sintético, tipo, severidad, parámetros y fase. Esta capa queda fuera de las entradas del detector y se utiliza solamente para evaluar.

### 7. Validación

- Esquema y tipos.
- Integridad referencial esperada por escenario.
- Rangos y coherencia temporal.
- Conteo exacto de defectos inyectados.
- Reproducibilidad con igual semilla.
- Diferencia controlada con semillas distintas.
- Ausencia de patrones, nombres y secretos prohibidos.

### 8. Publicación local

Guardar manifiesto, configuración, datos y verdad sintética en ubicaciones separadas. Ningún dataset se versiona hasta superar la revisión definida por el gobierno de datos.

## Separación de tasas

Cada problema se expresa mediante una unidad inequívoca:

- `count`: cantidad exacta de registros afectados.
- `row_rate`: proporción de filas afectadas.
- `entity_rate`: proporción de entidades afectadas al menos una vez.
- `relative_multiplier`: multiplicador respecto de una tasa base.

No se utilizará la expresión ambigua “aumentar 10 %” sin indicar la unidad.

## Reproducibilidad

Dos ejecuciones con la misma versión, configuración y semilla deben producir los mismos artefactos lógicos. Cada salida registrará hashes y conteos para poder demostrarlo.

## Evaluación de utilidad

El dataset debe permitir responder preguntas analíticas, conservar relaciones plausibles y desafiar los controles. La similitud se evaluará mediante estadísticas agregadas aprobadas, nunca mediante correspondencia fila a fila.
