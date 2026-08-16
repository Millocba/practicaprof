# Escenarios de calidad de datos

## Propósito

Los escenarios representan etapas académicas de evolución de un sistema. No son mediciones exactas de una organización ni una cronología externa.

## Escenarios

| Escenario | Uso | Características |
|---|---|---|
| `clean` | Referencia técnica | Integridad completa y sin defectos deliberados |
| `early_stage` | Etapa inicial | Duplicados, faltantes, formatos heterogéneos y relaciones débiles |
| `transition` | Mejora progresiva | Menos defectos estructurales y coexistencia de formatos |
| `mature` | Operación estabilizada | Identificadores únicos y problemas principalmente operativos |
| `stress` | Robustez | Volumen y tasas aumentadas de manera explícita |

## Matriz inicial de problemáticas

| Código | Problemática | `early_stage` | `transition` | `mature` | `stress` |
|---|---|---:|---:|---:|---:|
| `DQ_DUP_VEH_ID` | Matrícula sintética duplicada | `count: 32` | `count: 8` | `count: 0` | configurable |
| `DQ_DUP_DOMAIN` | Dominio sintético duplicado | `count: 32` | `count: 8` | `count: 0` | configurable |
| `DQ_MISSING_ID` | Identificador faltante | por definir | por definir | cercano a cero | multiplicador explícito |
| `DQ_FORMAT_DRIFT` | Formato inconsistente | alto | medio | bajo | multiplicador explícito |
| `DQ_ORPHAN_REL` | Relación sin coincidencia | por definir | menor | cero esperado | configurable |
| `DQ_NO_TELEMETRY` | Vehículo sin cobertura | tasa por definir | tasa por definir | tasa agregada aprobada | configurable |
| `DQ_ODOMETER` | Odómetro regresivo o incompatible | inyectado | inyectado | inyectado | elevado |
| `AN_TANK_OVERFLOW` | Litros sobre capacidad simulada | inyectado | inyectado | inyectado | elevado |
| `AN_FUEL_MISMATCH` | Producto incompatible | inyectado | inyectado | inyectado | elevado |
| `AN_TEMPORAL` | Fechas fuera de secuencia | frecuente | menor | excepcional | elevado |

Los `32` duplicados son una **decisión de simulación para el escenario inicial**. Se documentan como casos inyectados, no como resultado estadístico publicado.

## Reglas para el escenario `stress`

El escenario de estrés no aplicará un porcentaje global. Cada problemática declarará si aumenta mediante cantidad, tasa de filas, tasa de entidades o multiplicador relativo. Por ejemplo, una tasa base de 5 % con `relative_multiplier: 1.10` produce 5,5 %, no 15 %.

## Evolución esperada

- Los errores de unicidad y formato disminuyen al madurar los controles.
- La falta de coincidencia disminuye al consolidar claves.
- La ausencia de telemetría puede persistir como condición operativa.
- Las anomalías de consumo no desaparecen y requieren detección contextual.
- Los controles futuros deben medir tanto falsos positivos como defectos omitidos.

## Configuración futura

Las tasas pendientes se completarán solo con una de estas fuentes: decisión académica documentada o estadística agregada aprobada. Nunca se completarán copiando registros.
