# Diccionario de datos — Pipeline maestro

Describe los archivos que genera [`generator_pipeline_maestro.py`](../generator_pipeline_maestro.py), el generador oficial. Todos los datos son sintéticos. Los valores de referencia corresponden a la configuración por defecto (200 vehículos, semilla 42).

```bash
python generator_pipeline_maestro.py                  # datasets/synthetics_maestro/
python generator_pipeline_maestro.py --n_flota 500 --seed 7 --output otra/carpeta
```

| Archivo | Grano | Filas (por defecto) |
|---|---|---|
| `flota.csv` | un vehículo | 200 |
| `telemetria.csv` | un dispositivo GPS | 176 (88% de la flota) |
| `consumo.csv` | una carga de combustible | ~1.770 (5 a 12 por vehículo, más duplicados) |
| `solicitudes.csv` | una solicitud de combustible | ~500 (1 a 4 por vehículo) |
| `facturacion.csv` | una factura mensual de toda la flota | 9 (enero a septiembre de 2024) |
| `ground_truth.csv` | una anomalía inyectada | ~230 |
| `metadata.json` | una ejecución | semilla, parámetros, rutas y conteo de anomalías por tipo |

## Reproducibilidad

- La misma semilla produce archivos idénticos byte a byte (lo verifican los tests).
- Las fechas se calculan desde valores fijos: consumos y solicitudes entre el 2024-01-01 y el 2024-09-27, y la telemetría toma como "ahora" el 2024-09-28.
- Solo `metadata.json` cambia entre ejecuciones, porque registra la fecha de generación.

## Claves y relaciones

```text
flota.Matricula ──< consumo.vehiculo_id
flota.Matricula ──< solicitudes.vehiculo_id
flota.Dominio   ──< telemetria.Placa
flota.Dominio   ──< consumo.dominio        (se rompe en las anomalías DOMINIO_INVALIDO)
consumo (por mes) ──> facturacion.periodo
consumo.id ──< ground_truth.id_registro
```

## flota.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `Matricula` | texto | Clave del vehículo, `VEH-NNNNNN` |
| `Dominio` | texto | Dominio sintético `ABNNNNCD`, único; no proviene de un padrón |
| `Estado` | categoría | EN SERVICIO, EN REPARACION, FUERA DE SERVICIO o BAJA |
| `DireccionGral` | categoría | Dirección ficticia a la que pertenece el vehículo (5 valores) |
| `Dependencia` | categoría | Dependencia ficticia dentro de la dirección, `DEP A` a `DEP J` |
| `Identificable` | SI / NO | 94% SI |
| `TipoVehiculo` | categoría | SEDAN, PICK-UP, MOTOCICLETA, CAMIONETA, CAMION, AMBULANCIA, UTILITARIO o BOMBERO |
| `Marca` | categoría | Marca de un catálogo público general |
| `Modelo` | texto | `MODEL-AAAA`, genérico |
| `Año` | entero | 2005 a 2024 |
| `TipoCombustible` | categoría | GASOIL, NAFTA o GLP |
| `CapacidadTanque` | decimal (L) | 40 a 120 |
| `NumeroMotor` / `NumeroChasis` | texto | `M` y `CH` más 8 dígitos |
| `NumeroTarjeta` | texto | Tarjeta de combustible, `TARJ` más 8 dígitos |
| `LimiteSaldo` | decimal | 1.000 a 10.000 |
| `LimiteLitros` | decimal (L) | 100 a 500 |
| `SubEstado` | categoría | ACTIVO si `Estado` es EN SERVICIO; si no, INACTIVO |

## telemetria.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `IMEI` | entero | 15 dígitos, aleatorio |
| `Alias` | texto | `DEV-NNNNNN` |
| `Placa` | texto | Dominio de un vehículo de la flota (un vehículo puede tener varios dispositivos) |
| `MSISDN` | entero | Línea sintética `54911` más 7 dígitos |
| `Modelo` | texto | `GPS-{A,B,C}-{1..5}` |
| `Tipo` | texto | Siempre GPS |
| `Estado` | categoría | ONLINE (88%) u OFFLINE |
| `Bateria` | decimal (%) | 20 a 100 |
| `UltimaConexion` | fecha y hora | Hasta 15 minutos antes de la referencia si está ONLINE; hasta 10 horas si está OFFLINE |
| `Latitud` / `Longitud` | decimal | Rectángulo aproximado de un área metropolitana |
| `Odometro` | entero (km) | 10.000 a 300.000, independiente del odómetro de consumo |

## consumo.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | texto | Clave de la transacción, `CONS-NNNNNNNN` |
| `vehiculo_id` | texto | FK a `flota.Matricula` |
| `dominio` | texto | Dominio informado en la carga; puede no coincidir con la flota |
| `fecha` | fecha | Fecha de la carga |
| `estacion` | categoría | Estación de servicio (5 valores); puede estar vacía |
| `producto` | categoría | GASOIL, NAFTA, INFINIA, SUPER o GLP |
| `litros` | decimal (L) | Normal: de 5 L al 80% del tanque (tope 80 L). Exceso: 110% a 180% del tanque |
| `precio_unitario` | decimal | 1,5 a 3,5 |
| `importe_total` | decimal | `litros × precio_unitario`, redondeado |
| `numero_tarjeta` | texto | Tarjeta del vehículo |
| `conductor` | texto | `CONDUCTOR-N`; puede estar vacío |
| `odometro` | entero (km) | Crece según los días entre cargas (20 a 60 km por día, propio de cada vehículo); puede estar vacío |

## solicitudes.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | texto | `SOL-NNNNNNNN` |
| `vehiculo_id` / `dominio` | texto | Vehículo solicitante (siempre válido) |
| `fecha_solicitud` | fecha | Dentro de la misma ventana que el consumo |
| `litros_solicitados` / `litros_autorizados` | decimal (L) | 20 a 100, generados por separado |
| `estado` | categoría | APROBADA (50%), PENDIENTE o RECHAZADA |
| `centro_costo` | texto | `CC-NNN` |
| `responsable` | texto | `RESP-N` |
| `observaciones` | categoría | OK, REVISADO, PENDIENTE o vacío (el vacío es un valor posible, no una anomalía) |

## facturacion.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `numero_factura` | texto | `FAC-AAAAMM-NNNN` |
| `fecha_factura` | fecha | Último día del período |
| `periodo` | texto | `AAAA-MM` |
| `total_litros` / `total_monto` | decimal | Suma del consumo del período |
| `iva` | decimal | 21% de `total_monto` |
| `monto_total_con_iva` | decimal | `total_monto × 1,21` |
| `estado` | categoría | PAGADA, PENDIENTE o VENCIDA |
| `numero_transacciones` | entero | Cantidad de cargas del período |

## ground_truth.csv

Verdad de referencia: una fila por anomalía inyectada. **Se usa solo para evaluar la detección; no es una entrada de las reglas ni de los modelos.** Un registro puede tener más de una anomalía (por ejemplo, un duplicado de una carga con exceso).

| Columna | Descripción |
|---|---|
| `tabla` | Tabla afectada (hoy, siempre `consumo`) |
| `id_registro` | `consumo.id` de la transacción |
| `vehiculo_id` | Vehículo de la transacción |
| `tipo_anomalia` | Ver el catálogo |
| `columna` | Columna donde se manifiesta |
| `hipotesis` / `severidad` | Según el catálogo |
| `descripcion` | Detalle legible, por ejemplo `retroceso de 12000 km` |

### Catálogo de anomalías

| Tipo | Hipótesis | Severidad | Tasa | Cómo se inyecta |
|---|---|---|---|---|
| `EXCESO_VOLUMETRICO` | H3a | ALTA | 7% de los vehículos | Todas las cargas del vehículo superan la capacidad del tanque |
| `ODOMETRO_REGRESIVO` | H2 | ALTA | 1,2% de las cargas | El odómetro retrocede entre 3.000 y 40.000 km y las cargas siguientes continúan desde ese valor |
| `ODOMETRO_SALTO` | H2 | ALTA | 1,2% de las cargas | El odómetro avanza entre 1.500 y 9.000 km extra y las cargas siguientes continúan desde ese valor |
| `DOMINIO_INVALIDO` | H1 | MEDIA | 1% de las cargas | El dominio se reemplaza por `XXNNNXX`, sin vínculo con la flota |
| `VALOR_NULO` | CALIDAD | BAJA | 2% de las cargas | Se vacía `estacion`, `conductor` u `odometro` (nunca un odómetro alterado) |
| `DUPLICADO` | CALIDAD | MEDIA | 1% de las cargas | Copia exacta de otra carga con un `id` nuevo; hereda sus anomalías de valor, no las de odómetro |

## Limitaciones conocidas

Las siguientes incoherencias **no son anomalías inyectadas** y no figuran en el ground truth:

- `litros_autorizados` puede superar a `litros_solicitados`, porque ambos se generan por separado.
- El odómetro de telemetría no se relaciona con el de consumo.
- Hay una sola factura por mes para toda la flota; no se inyectan anomalías de facturación.
- La telemetría siempre apunta a dominios válidos, así que la vinculación de dispositivos (H1) es del 100%.
