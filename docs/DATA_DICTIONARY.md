# Diccionario inicial de datos

Los tipos son lógicos y neutrales respecto del motor. `Requerido` describe el escenario limpio; los escenarios defectuosos pueden violarlo deliberadamente en la capa raw.

## Organización ficticia

| Entidad.campo | Tipo | Requerido | Significado y validación |
|---|---|---:|---|
| `unidad.id` | UUID | Sí | Clave interna generada |
| `unidad.codigo` | texto | Sí | Formato `UNI-SYN-NNN` y valor único |
| `unidad.nombre` | texto | Sí | Nombre completamente ficticio |
| `subunidad.id` | UUID | Sí | Clave interna |
| `subunidad.unidad_id` | UUID | Sí | FK a `unidad` |
| `subunidad.codigo` | texto | Sí | Formato `SUB-SYN-NNNN` y valor único |
| `subunidad.nombre` | texto | Sí | Etiqueta ficticia normalizada |

## Flota

| Entidad.campo | Tipo | Requerido | Significado y validación |
|---|---|---:|---|
| `tipo_vehiculo.id` | UUID | Sí | Clave del catálogo |
| `tipo_vehiculo.nombre` | categoría | Sí | Categoría sintética controlada |
| `estado_vehiculo.id` | UUID | Sí | Clave del catálogo |
| `estado_vehiculo.nombre` | categoría | Sí | En servicio, fuera de servicio o baja ficticia |
| `vehiculo.id` | UUID | Sí | Clave interna |
| `vehiculo.matricula_sintetica` | texto | Sí | `VEH-SYN-NNNNN`, única en escenario limpio |
| `vehiculo.dominio_sintetico` | texto | No | Valor generado con formato argentino `ABC123` o `AA123AA`; no proviene de un padrón |
| `vehiculo.subunidad_id` | UUID | No | FK de asignación |
| `vehiculo.tipo_vehiculo_id` | UUID | Sí | FK al tipo |
| `vehiculo.estado_vehiculo_id` | UUID | Sí | FK al estado |
| `vehiculo.marca_sintetica` | categoría | No | Marca de catálogo público, sin asignación real |
| `vehiculo.modelo_sintetico` | texto | No | Modelo de catálogo público, sin asignación real |
| `vehiculo.anio_modelo` | entero | No | Año plausible dentro del escenario |
| `vehiculo.tipo_combustible` | categoría | Sí | Catálogo controlado |
| `vehiculo.capacidad_tanque_l` | decimal | No | Mayor que cero y coherente con tipo |
| `vehiculo.consumo_esperado` | decimal | No | Parámetro base del simulador |
| `vehiculo.identificable` | booleano | Sí | Indica disponibilidad de identificadores completos |

## Telemetría

| Entidad.campo | Tipo | Requerido | Significado y validación |
|---|---|---:|---|
| `dispositivo.id` | UUID | Sí | Clave interna |
| `dispositivo.codigo_sintetico` | texto | Sí | `DEV-SYN-NNNNN` |
| `dispositivo.vehiculo_id` | UUID | No | FK; puede faltar en escenarios defectuosos |
| `dispositivo.estado_transmision` | categoría | Sí | Activo, intermitente o inactivo |
| `dispositivo.fecha_alta` | fecha | Sí | No posterior a sus eventos |
| `evento_telemetria.id` | UUID | Sí | Clave del evento |
| `evento_telemetria.dispositivo_id` | UUID | Sí | FK al dispositivo |
| `evento_telemetria.instante_utc` | timestamp | Sí | Instante de observación |
| `evento_telemetria.latitud_simulada` | decimal | No | Dentro de la geografía ficticia |
| `evento_telemetria.longitud_simulada` | decimal | No | Dentro de la geografía ficticia |
| `evento_telemetria.odometro_km` | decimal | No | No decreciente, salvo anomalía inyectada |
| `evento_telemetria.horometro_h` | decimal | No | No decreciente |
| `evento_telemetria.bateria_pct` | decimal | No | Entre 0 y 100 |

## Personas, contratos y tarjetas

| Entidad.campo | Tipo | Requerido | Significado y validación |
|---|---|---:|---|
| `persona.id` | UUID | Sí | Clave interna |
| `persona.codigo_sintetico` | texto | Sí | `PER-SYN-NNNNN`; no es documento real |
| `persona.nombre_sintetico` | texto | Sí | Generado desde vocabularios ficticios |
| `persona.subunidad_id` | UUID | No | FK organizativa |
| `persona.rol_sintetico` | categoría | No | Función dentro del escenario |
| `contrato.id` | UUID | Sí | Clave interna |
| `contrato.codigo_sintetico` | texto | Sí | `CTR-SYN-NNNN` |
| `contrato.subunidad_id` | UUID | No | FK responsable |
| `contrato.limite_importe` | decimal | No | No negativo |
| `contrato.limite_litros` | decimal | No | No negativo |
| `tarjeta.id` | UUID | Sí | Clave interna |
| `tarjeta.codigo_sintetico` | texto | Sí | `CARD-SYN-NNNNN`; no imita numeración comercial |
| `tarjeta.contrato_id` | UUID | Sí | FK al contrato |
| `tarjeta.vehiculo_id` | UUID | No | FK al vehículo asignado |
| `tarjeta.estado` | categoría | Sí | Activa, suspendida o vencida |

## Operaciones y facturación

| Entidad.campo | Tipo | Requerido | Significado y validación |
|---|---|---:|---|
| `transaccion_combustible.id` | UUID | Sí | Clave de la operación |
| `transaccion_combustible.tarjeta_id` | UUID | Sí | FK a tarjeta |
| `transaccion_combustible.persona_id` | UUID | No | FK a persona sintética |
| `transaccion_combustible.instante_utc` | timestamp | Sí | Fecha de carga |
| `transaccion_combustible.producto` | categoría | Sí | Tipo de combustible |
| `transaccion_combustible.litros` | decimal | Sí | Positivo; puede exceder capacidad solo por anomalía |
| `transaccion_combustible.precio_unitario` | decimal | Sí | Positivo y ligado al período simulado |
| `transaccion_combustible.importe_total` | decimal | Sí | Litros por precio, salvo error inyectado |
| `transaccion_combustible.odometro_declarado_km` | decimal | No | Lectura declarada al cargar |
| `periodo_facturacion.id` | UUID | Sí | Clave del período |
| `periodo_facturacion.desde` | fecha | Sí | Inicio inclusivo |
| `periodo_facturacion.hasta` | fecha | Sí | Fin no anterior al inicio |
| `factura.id` | UUID | Sí | Clave del comprobante |
| `factura.periodo_id` | UUID | Sí | FK al período |
| `factura.contrato_id` | UUID | Sí | FK al contrato |
| `factura.importe_facturado` | decimal | Sí | Total sintético del comprobante |
| `factura.importe_conciliado` | decimal | Sí | Total vinculado a transacciones |
| `solicitud_combustible.id` | UUID | Sí | Clave de solicitud |
| `solicitud_combustible.vehiculo_id` | UUID | No | FK a vehículo |
| `solicitud_combustible.persona_id` | UUID | No | FK a persona |
| `solicitud_combustible.fecha` | fecha | Sí | Fecha operativa |
| `solicitud_combustible.litros_solicitados` | decimal | Sí | Positivo |
| `solicitud_combustible.estado` | categoría | Sí | Pendiente, rendida o anulada |

## Reproducibilidad y verdad sintética

| Entidad.campo | Tipo | Requerido | Significado y validación |
|---|---|---:|---|
| `ejecucion_dataset.id` | UUID | Sí | Identifica una generación |
| `ejecucion_dataset.escenario` | categoría | Sí | `clean`, `early_stage`, `transition`, `mature` o `stress` |
| `ejecucion_dataset.semilla` | entero | Sí | Semilla reproducible |
| `ejecucion_dataset.version_generador` | texto | Sí | Versión de código o artefacto |
| `verdad_anomalia.id` | UUID | Sí | Clave del evento inyectado |
| `verdad_anomalia.ejecucion_id` | UUID | Sí | FK a ejecución |
| `verdad_anomalia.entidad` | texto | Sí | Entidad afectada |
| `verdad_anomalia.registro_id` | UUID | Sí | ID sintético afectado |
| `verdad_anomalia.tipo` | categoría | Sí | Catálogo de problemáticas |
| `verdad_anomalia.severidad` | categoría | Sí | Baja, media o alta |
| `verdad_anomalia.parametros` | JSON | Sí | Configuración no sensible de la inyección |
