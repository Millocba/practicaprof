# Diseño: base de datos y escenario realista v2

> **Propuesta pendiente de aprobación.** Describe qué cambia en el modelo de datos, el generador y las hipótesis para acercarlos al circuito real de abastecimiento. Las proporciones finales se calibran con el perfil aprobado de las fuentes ([perfiles/](../perfiles/README.md)); las de este documento son punto de partida.

## Objetivo

Hoy el escenario realista modela solicitudes con litros autorizados y una factura por proveedor y mes. El circuito real es otro:

1. Cada vehículo tiene una **tarjeta** asignada a un **contrato** con un **tope mensual en pesos**. Cada carga descuenta del saldo del mes; si se agota, las tarjetas del contrato no pueden cargar hasta el mes siguiente.
2. El **registro interno** anota cada pedido de combustible y su rendición (ticket, rendido, anulado). No comparte ningún identificador con el **reporte del proveedor**: se cruzan por dominio y horario.
3. El proveedor factura **por contrato**: una deuda con el monto, un PDF con el detalle y un reporte de consumo por factura. Los tres montos deben coincidir.

## Modelo de datos

La base separa los datos maestros, que cambian poco y se versionan con vigencia, de los operativos, que crecen todos los días.

| Maestros | Clave | Notas |
|---|---|---|
| `vehiculo` | matrícula | Dominio, tipo, marca, capacidad del tanque, combustible, dependencia, estado con fecha |
| `dispositivo` | IMEI | Telemetría; asignación al vehículo con fecha desde/hasta |
| `contrato` | número | Proveedor, dependencia, tope mensual en pesos, vigencia |
| `tarjeta` | número | Asignada a un contrato y a un vehículo (o a una persona) con vigencia |
| `estacion` | código | Proveedor (propio o ajeno), ubicación ficticia, local o de ruta |
| `dependencia` | código | Jerarquía de direcciones y dependencias |

| Operativos | Clave | Relación |
|---|---|---|
| `carga` | id | Una fila por transacción del reporte del proveedor: tarjeta, estación, fecha y hora, litros, precio de surtidor y de empresa, origen (normal o contingencia) |
| `registro_interno` | id | Pedido y rendición: fecha y hora, dominio, litros autorizados y cargados, ticket, rendido, anulado, estación |
| `posicion_diaria` | vehículo + fecha | GPS diario |
| `factura` | número | Contrato, período, monto de la deuda, total del PDF, vencimiento |
| `factura_linea` | factura + renglón | Producto, litros, precio, importe; combustible o no |
| `saldo_contrato` | contrato + mes | Derivada: consumido, saldo y fecha en que se agotó |

- La carga se vincula con el contrato por la tarjeta vigente ese día, no por texto.
- El esquema se crea con migraciones numeradas; la carga desde los CSV del generador es idempotente (clave natural de cada tabla) y se prueba sobre una base temporal.
- Motor propuesto: SQLite (incluido en Python, sin dependencias nuevas).

## Cambios en el generador (escenario realista)

**Contratos y cupo.** Seis contratos con topes desiguales (uno concentra cerca del 40% del cupo, otro menos del 2%), escalados para que un mes normal ejecute alrededor del 90%. La simulación diaria descuenta cada carga del saldo; cuando un contrato se agota:

- las cargas normales de sus tarjetas se rechazan (no se generan);
- aparecen los comportamientos que el tope induce, como anomalías o casos legítimos:
  - `CARGA_CON_CUPO_AGOTADO` (anomalía): carga registrada con el saldo en cero, que el sistema no debería permitir;
  - `TARJETA_DE_OTRO_CONTRATO` (anomalía): el vehículo carga con una tarjeta de otro contrato o de otro vehículo;
  - `CONTINGENCIA` (legítimo o anomalía según tenga respaldo en el registro interno): carga manual fuera del circuito normal.

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
| **H8 (reformulada).** Cruzar el registro interno con el reporte detecta cargas sin respaldo, rendiciones sin carga y anuladas que se facturan | Emparejamiento voraz por dominio y día, sin tolerancia de horario ni de litros | Asignación óptima por dominio con tolerancia de horario y litros, excluyendo estaciones ajenas y pendientes |
| **H9 (ampliada).** La conciliación triple deuda–PDF–consumo por contrato detecta sobre y subfacturación que el total mensual no ve | Total del mes contra consumo del mes | Deuda contra consumo, PDF contra deuda y cada línea contra su carga |
| **H10 (nueva).** Las irregularidades se concentran en los contratos que agotan su cupo | Controles iguales para todos los días | Controles reforzados después de agotado el cupo: tarjetas de otro contrato, contingencias sin respaldo |

La regla ingenua de H8 reproduce el cruce típico de un sistema operativo (voraz, sin tolerancias); la con contexto es el aporte metodológico del proyecto.

## Qué no cambia

- El escenario didáctico queda igual (sus datos deben seguir siendo idénticos byte a byte).
- Flota, telemetría, GPS diario, estaciones y las hipótesis H1 a H7.
- Los conductores y solicitantes siguen siendo códigos sintéticos: no se modelan documentos ni nombres de personas.

## Orden de implementación

1. Aprobar este diseño y el perfil de las fuentes; ajustar proporciones con el informe de brechas.
2. Contratos, tarjetas y cupo en el generador, con sus tests.
3. Registro interno y H8 reformulada.
4. Facturación por contrato y H9 ampliada.
5. H10.
6. Base de datos: migraciones y carga desde los CSV.

Cada paso es un commit con tests y con las hipótesis verificadas en cinco semillas.

## Decisiones abiertas

- ¿El tope es solo en pesos o también en litros por tarjeta?
- ¿Qué pasa en la realidad cuando un contrato se agota: se bloquea la tarjeta, se pasa a contingencia, se reasigna la tarjeta?
- ¿La tarjeta puede estar a nombre de una persona (DNI) además de un vehículo? Si es así, ¿se modela?
