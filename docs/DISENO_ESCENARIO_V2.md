# Diseño: base de datos y escenario realista v2

> **Propuesta pendiente de aprobación.** Describe qué cambia en el modelo de datos, el generador y las hipótesis para acercarlos al circuito real de abastecimiento. Las proporciones finales se calibran con el perfil aprobado de las fuentes ([perfiles/](../perfiles/README.md)); las de este documento son punto de partida.

## Objetivo

Hoy el escenario realista modela solicitudes con litros autorizados y una factura por proveedor y mes. El circuito real es otro:

1. Cada vehículo tiene una **tarjeta** asignada a un **contrato** con un **tope mensual en pesos** (no hay límite en litros). Cada carga descuenta del saldo del mes; si se agota, **el suministro se corta** para todas las tarjetas del contrato. Para evitarlo, se sigue cada contrato **proyectando el consumo promedio diario a fin de mes**: si la proyección supera el saldo, se **transfiere saldo a mano antes del corte** desde otro contrato, generalmente el que más saldo tiene.
2. También hay **tarjetas personales**, asociadas a una persona y no a un vehículo. Igual requieren una solicitud en el registro interno, que indica la unidad y hasta cuánto se puede cargar en ella, así que aparecen tanto en el registro interno como en el reporte del proveedor.
3. El **registro interno** anota cada pedido de combustible y su rendición (ticket, rendido, anulado). No comparte ningún identificador con el **reporte del proveedor**: se cruzan por dominio y horario.
4. El proveedor factura **por contrato**: una deuda con el monto, un PDF con el detalle y un reporte de consumo por factura. Los tres montos deben coincidir.

## Qué muestran las fuentes reales

Por la estructura de la base MySQL del sistema en uso (nombres de tablas y columnas y cantidad de filas). El perfilador no lee esta base, solo los archivos del volumen, así que estos datos no tienen todavía un perfil:

- **Los topes se guardan como dato:** hay una tabla de contratos con seis contratos, uno por dependencia, y su límite. No se calculan.
- **Brecha con el generador actual:** no tiene contratos. Solo escribe `LimiteSaldo` y `LimiteLitros` por vehículo con valores al azar, que ninguna regla lee. Hay que modelar el contrato como maestro y hacer coherentes esos límites: en la fuente real se fijan al registrar cada tarjeta o móvil, junto con el contrato al que pertenece.
- **Las transferencias no se registran.** Existe una tabla de crédito por contrato (límite, consumido, disponible, fecha de actualización), pero está vacía. Las transferencias de saldo se hacen fuera del sistema, así que no hay datos para calibrar su frecuencia ni su margen: se fijan en este diseño.
- **Las facturas cuelgan del contrato** y guardan el monto facturado, el consumido, el total del PDF y la nota de crédito. Hay bastante más de una factura por contrato y período (unas 180 en siete períodos), y en promedio dos o tres renglones de PDF por factura.
- **Las transacciones del proveedor** (unas 80.000) marcan la contingencia.

**Consecuencia para H10:** en la realidad, las transferencias no son observables. El generador las registra (son parte de la verdad de referencia), pero la regla con contexto de H10 debe inferirlas de lo observable: el consumo de cada contrato frente a su tope y a su proyección. Registrar las transferencias, que el sistema ya prevé y no usa, queda como recomendación para la fuente real.

## Modelo de datos

La base separa los datos maestros, que cambian poco y se versionan con vigencia, de los operativos, que crecen todos los días.

| Maestros | Clave | Notas |
|---|---|---|
| `vehiculo` | matrícula | Dominio, tipo, marca, capacidad del tanque, combustible, dependencia, estado con fecha |
| `dispositivo` | IMEI | Telemetría; asignación al vehículo con fecha desde/hasta |
| `contrato` | número | Proveedor, dependencia, tope mensual en pesos, vigencia |
| `tarjeta` | número | Asignada a un contrato y, con vigencia, a un vehículo (tarjeta de unidad) o a una persona (tarjeta personal, identificada por un código sintético). Al registrarla se le fijan un límite de saldo y un límite de litros |
| `estacion` | código | Proveedor (propio o ajeno), ubicación ficticia, local o de ruta |
| `dependencia` | código | Jerarquía de direcciones y dependencias |

| Operativos | Clave | Relación |
|---|---|---|
| `carga` | id | Una fila por transacción del reporte del proveedor: tarjeta, estación, fecha y hora, litros, precio de surtidor y de empresa, origen (normal o contingencia) |
| `registro_interno` | id | Pedido y rendición: fecha y hora, dominio, litros autorizados y cargados, ticket, rendido, anulado, estación |
| `posicion_diaria` | vehículo + fecha | GPS diario |
| `factura` | número | Contrato, período, monto de la deuda, total del PDF, vencimiento |
| `factura_linea` | factura + renglón | Producto, litros, precio, importe; combustible o no |
| `transferencia_saldo` | id | Contrato de origen y de destino, monto, fecha y hora. En la fuente real está prevista pero vacía: el generador la completa como verdad de referencia |
| `saldo_contrato` | contrato + día | Derivada: tope, transferencias recibidas y cedidas, consumido y saldo; días sin suministro |

- La carga se vincula con el contrato por la tarjeta vigente ese día, no por texto.
- El esquema se crea con migraciones numeradas; la carga desde los CSV del generador es idempotente (clave natural de cada tabla) y se prueba sobre una base temporal.
- Motor propuesto: SQLite (incluido en Python, sin dependencias nuevas).

## Cambios en el generador (escenario realista)

**Contratos y cupo.** Seis contratos con topes desiguales en pesos (uno concentra cerca del 40% del cupo, otro menos del 2%), escalados para que la flota ejecute alrededor del 90% del total en un mes normal; algunos contratos se agotan antes de fin de mes y otros sobran. La simulación diaria descuenta cada carga del saldo del contrato de la tarjeta:

- **Seguimiento:** cada día hábil se calcula, por contrato, el consumo promedio diario del mes y se proyecta a fin de mes. Si la proyección supera el saldo (con un margen), se **transfiere** la diferencia desde el contrato con más saldo proyectado sobrante (caso legítimo `TRANSFERENCIA_DE_SALDO`, registrado en `transferencia_saldo`). La transferencia se hace con un retraso de cero a dos días hábiles.
- **Corte:** si la transferencia llega tarde o un pico de consumo le gana a la proyección, el saldo se agota y las cargas de las tarjetas del contrato no se realizan hasta que llega la transferencia; los vehículos postergan la carga (caso legítimo `CORTE_DE_SUMINISTRO`, días sin suministro en `saldo_contrato`).
- Los comportamientos irregulares, como anomalías:
  - `CARGA_CON_CUPO_AGOTADO`: carga registrada con el saldo en cero, que el corte debería haber impedido;
  - `TARJETA_DE_OTRO_CONTRATO`: durante el corte, el vehículo carga con una tarjeta de otro contrato o de otro vehículo;
  - `TRANSFERENCIA_SIN_NECESIDAD`: transferencia que la proyección no justifica (el contrato de destino alcanzaba), o que deja al contrato de origen por debajo de su propia proyección;
  - `CONSUMO_ANTICIPADO`: un contrato consume en pocos días mucho más que su promedio para forzar una transferencia.
- `CONTINGENCIA` (legítimo si tiene respaldo en el registro interno, anomalía si no): carga manual fuera del circuito normal.

**Tarjetas personales.** Una parte de las tarjetas es personal. La carga figura en el reporte con la persona (código sintético) en lugar del dominio; la solicitud del registro interno indica la unidad y el límite. Casos:

- `CARGA_PERSONAL_SIN_SOLICITUD` (anomalía): carga con tarjeta personal sin solicitud de esa persona.
- `CARGA_PERSONAL_SUPERA_AUTORIZADO` (anomalía): la carga supera el límite de la solicitud.
- `CARGA_PERSONAL_EN_OTRA_UNIDAD` (anomalía): los litros no son compatibles con la unidad de la solicitud (tanque, combustible).

**Telemetría y bajas.** A un móvil de baja no se le coloca telemetría. Si tenía dispositivo, al pasar a baja el dispositivo se mueve al grupo de depósito (baja / reemplazos) y deja de transmitir; ningún móvil debe ir a desguace con el aparato funcionando. El generador:

- asigna dispositivos sobre todo a móviles en servicio;
- al pasar un móvil a baja, mueve su dispositivo al grupo de depósito (caso legítimo `DISPOSITIVO_EN_DEPOSITO`);
- anomalía `DISPOSITIVO_ACTIVO_EN_BAJA`: móvil en baja con el dispositivo fuera del grupo de depósito y transmitiendo.

**Reporte del proveedor.** La tabla de cargas incorpora origen (normal o contingencia), remito, precio de surtidor y precio de empresa (este último alrededor de 2% menor) y los impuestos por litro incluidos en el precio.

**Registro interno.** Reemplaza a las solicitudes actuales. Cada carga normal tiene su registro rendido con ticket; además:

| Caso | Tipo | Qué es |
|---|---|---|
| `RENDIDA_SIN_CARGA` | anomalía | Registro rendido sin carga en el reporte |
| `CARGA_SIN_REGISTRO` | anomalía | Carga en el reporte sin registro interno |
| `ANULADA_CON_CARGA` | anomalía | Registro anulado cuya carga igual existe y se factura |
| `DESACUERDO_DE_LITROS` | anomalía | Registro y carga con más de 0,5 L de diferencia |
| `ESTACION_AJENA` | legítimo | Registro en una estación de otro proveedor: no está en el reporte ni se factura |
| `PENDIENTE_DE_RENDICION` | legítimo | Registro sin rendir todavía |

**Facturación.** Una factura por contrato y mes, con total igual a la suma a precio de empresa, más:

| Caso | Tipo | Qué es |
|---|---|---|
| `DIFERENCIA_DEUDA_CONSUMO` | anomalía | El monto de la deuda no coincide con el consumo del contrato |
| `DIFERENCIA_DEUDA_PDF` | anomalía | El total del PDF no coincide con la deuda |
| `PRODUCTO_NO_COMBUSTIBLE` | anomalía | Renglón que no es combustible (lubricante) |
| `FACTURADA_A_PRECIO_DE_SURTIDOR` | anomalía | Línea facturada al precio de surtidor en lugar del de empresa |

Se mantienen las irregularidades de línea actuales (sin carga, duplicada, sobreprecio) y los casos legítimos de desfase de corte y ajuste documentado.

## Hipótesis

| | Regla ingenua | Regla con contexto |
|---|---|---|
| **H8 (reformulada).** Cruzar el registro interno con el reporte detecta cargas sin respaldo, rendiciones sin carga y anuladas que se facturan | Emparejamiento voraz por dominio y día, sin tolerancia de horario ni de litros; las cargas con tarjeta personal no tienen dominio y quedan como "sin solicitud" | Asignación óptima por dominio, o por persona en las tarjetas personales, con tolerancia de horario y litros, excluyendo estaciones ajenas y pendientes |
| **H9 (ampliada).** La conciliación triple deuda–PDF–consumo por contrato detecta sobre y subfacturación que el total mensual no ve | Total del mes contra consumo del mes | Deuda contra consumo, PDF contra deuda y cada línea contra su carga |
| **H11 (nueva).** Un móvil en baja con telemetría activa indica un dispositivo que no se recuperó | Móvil en baja con cualquier dispositivo asociado | Móvil en baja con el dispositivo fuera del grupo de depósito y con transmisión reciente |
| **H10 (nueva).** Las irregularidades del cupo solo se ven siguiendo el saldo diario de cada contrato y su proyección | Ejecución mensual de cada contrato contra su tope | Saldo diario con la proyección a fin de mes y las transferencias: transferencias que la proyección no justifica, consumo anticipado, cargas durante el corte, tarjetas de otro contrato |

La regla ingenua de H8 reproduce el cruce típico de un sistema operativo (voraz, sin tolerancias); la con contexto es el aporte metodológico del proyecto.

## Qué no cambia

- El escenario didáctico queda igual (sus datos deben seguir siendo idénticos byte a byte).
- Flota, telemetría, GPS diario, estaciones y las hipótesis H1 a H7.
- Los conductores y solicitantes siguen siendo códigos sintéticos: no se modelan documentos ni nombres de personas.

## Orden de implementación

1. Aprobar este diseño y el perfil de las fuentes; ajustar proporciones con el informe de brechas.
2. Contratos, tarjetas y cupo en el generador, con sus tests. **Hecho** (junto con H10).
3. Registro interno y H8 reformulada.
4. Facturación por contrato y H9 ampliada.
5. Telemetría y bajas (H11).
6. Base de datos: migraciones y carga desde los CSV.

Cada paso es un commit con tests y con las hipótesis verificadas en cinco semillas.

## Decisiones tomadas

- El tope es solo en pesos.
- Al agotarse un contrato se corta el suministro. Para evitarlo se proyecta el consumo promedio diario a fin de mes y, si no alcanza, se transfiere saldo a mano antes del corte, generalmente desde el contrato con más saldo.
- `LimiteSaldo` y `LimiteLitros` se fijan en cada tarjeta o móvil al registrarlo, junto con el contrato al que pertenece. El generador los asigna coherentes con el tanque y el precio, y una carga que los supera es una anomalía (`CARGA_SUPERA_LIMITE_TARJETA`).
- Las tarjetas personales se modelan: requieren solicitud con la unidad y el límite, y aparecen en el registro interno y en el reporte.

## Decisiones abiertas

- A qué período se aplican `LimiteSaldo` y `LimiteLitros` de cada tarjeta (por carga, por día o por mes): se verifica con el perfil comparando las cargas con esos límites.

- Margen de la proyección con el que se decide transferir, retraso típico de la transferencia y cuántas hay por mes. No se pueden calibrar con datos (no hay transferencias registradas): propuesta inicial, transferir cuando la proyección supere el 95% del saldo, con un retraso de 0 a 2 días hábiles.
- Cuántas facturas por contrato y período y cómo se reparten (por semana, por producto): a calibrar con el perfil de la base.
- Proporción de tarjetas personales y de cargas en contingencia (a calibrar con el perfil).
