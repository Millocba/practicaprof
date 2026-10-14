# Base de datos

Base SQLite del escenario realista: datos maestros con vigencia, datos operativos y vistas de control. No cambia los datos ni las hipótesis (las reglas y los modelos siguen leyendo los CSV); ordena el modelo de datos, hace verificable la integridad y deja los controles escritos en SQL.

## Para qué sirve

- **Integridad verificable.** Las relaciones entre tablas son claves foráneas y restricciones: toda carga es de una tarjeta y un contrato que existen, toda línea pertenece a una factura, ninguna transferencia va de un contrato a sí mismo. Si el generador o una fuente las rompe, la carga falla.
- **Vigencias.** Tarjetas y dispositivos se asignan a un vehículo (o a una persona) desde una fecha hasta otra, y el estado de cada vehículo tiene su historia. Responde preguntas como "¿de quién era esta tarjeta el día de la carga?".
- **Carga diaria.** Se puede cargar hasta una fecha y después seguir: cada fila se inserta o se actualiza por su clave, así que cargar dos veces no duplica nada. Cada carga queda registrada (`carga_de_datos`).
- **Controles portables.** Los controles de H9, H10, H11 y H12 están escritos como vistas con SQL estándar (ventanas y CTE), que corren en otros motores.

## Uso

```bash
python -m base_datos cargar                      # crea datasets/auditoria_realista.db y carga el dataset realista
python -m base_datos cargar --hasta 2024-04-30   # carga diaria: solo hasta esa fecha
python -m base_datos verificar                   # integridad referencial (incluidas las excepciones) y filas por tabla
```

La base es un archivo local, que se puede recrear en cualquier momento desde los CSV: `datasets/` está fuera de Git y no se versiona ninguna base. Los tests usan una base temporal.

## Esquema

```mermaid
flowchart LR
  vehiculo -->|"dependencia (N:1)"| dependencia
  estado_vehiculo -->|"matricula (N:1)"| vehiculo
  tarjeta -->|"contrato (N:1)"| contrato
  asignacion_tarjeta -->|"tarjeta (N:1)"| tarjeta
  asignacion_tarjeta -->|"matricula (N:1)"| vehiculo
  asignacion_dispositivo -->|"dispositivo (N:1)"| dispositivo
  asignacion_dispositivo -->|"matricula (N:1)"| vehiculo
  excepcion_odometro -->|"matricula (N:1)"| vehiculo
  carga -->|"tarjeta (N:1)"| tarjeta
  carga -->|"contrato (N:1)"| contrato
  carga -->|"estacion (N:1)"| estacion
  pedido -->|"matricula (N:1)"| vehiculo
  pedido -.->|"dominio + fecha + hora"| carga
  transferencia -->|"contrato_origen / contrato_destino (N:1)"| contrato
  factura -->|"contrato (N:1)"| contrato
  factura_linea -->|"factura (N:1)"| factura
  factura_linea -.->|"referencia_carga"| carga
  posicion_diaria -->|"matricula (N:1)"| vehiculo
```

| Grupo | Tablas |
|---|---|
| Maestros (con vigencia) | `contrato`, `dependencia`, `vehiculo`, `estado_vehiculo`, `tarjeta`, `asignacion_tarjeta`, `estacion`, `dispositivo`, `asignacion_dispositivo`, `excepcion_odometro` |
| Operativos (se cargan por día) | `carga` (reporte del proveedor), `pedido` (registro interno), `transferencia`, `factura`, `factura_linea`, `posicion_diaria` |
| Control | `migracion` (versiones aplicadas), `carga_de_datos` (cada carga: origen, fecha tope, semilla, filas por tabla) |

Dos relaciones no son claves foráneas a propósito (flechas punteadas): el registro interno no comparte ninguna clave con el reporte del proveedor (se cruza por dominio y horario), y una línea de factura que referencia una carga inexistente es justamente lo que se audita.

## Migraciones

| Versión | Contenido |
|---|---|
| 001 | Maestros |
| 002 | Operativos e índices |
| 003 | Vistas de control |
| 004 | Registro de cargas |
| 005 | Excepciones de odómetro y su vista de control |

Para una base creada antes de la 005, `python -m base_datos cargar` aplica la migración pendiente y carga las excepciones; el resto de las tablas no cambia.

Cada migración declara su compatibilidad, el bloqueo esperado, cómo volver atrás y cómo verificarla, y se aplica una sola vez, en su propia transacción (`base_datos/esquema.py`).

## Vistas de control

| Vista | Qué muestra | Hipótesis |
|---|---|---|
| `saldo_diario_contrato` | Saldo de cada contrato por día: tope, transferencias y consumo, reiniciado cada mes | H10 |
| `cargas_con_saldo_agotado` | Contratos-mes con días que empiezan sin saldo y tienen cargas | H10 |
| `conciliacion_factura` | Conciliación triple: deuda contra líneas, PDF contra deuda y renglones que no son combustible | H9 |
| `linea_sin_carga` | Líneas de combustible que facturan una carga que no está en el reporte | H9 |
| `baja_con_dispositivo_activo` | Móviles de baja cuyo dispositivo transmitió en la última semana, esté en el grupo que esté | H11 |
| `excepcion_vigente` | Excepciones activas: el estado de hoy que muestra el padrón (`ExcepcionOdometro` y `FechaHastaExcepcionOdometro`) | H12 |
| `odometro_sin_avance_sin_excepcion` | Cargas con la misma lectura que la carga anterior del vehículo, en otro día, sin una excepción vigente ese día | H12 |

Los tests verifican que cada vista encuentre exactamente las anomalías inyectadas de su tipo, y que `odometro_sin_avance_sin_excepcion` dé el mismo conjunto que la regla `sin_avance_sin_excepcion` de `deteccion/reglas.py` en 5 semillas. Como la regla, la vista intercala en la secuencia de cada vehículo las cargas en estaciones de otra red que anota el registro interno (pedidos rendidos y no anulados): sirven de lectura anterior, pero no se marcan.

## Excepciones de odómetro

Una excepción de odómetro permite que la lectura se repita mientras rige. Es un hecho con vigencia, no un atributo del vehículo: un vehículo puede tener varias a lo largo del tiempo y una puede durar un solo día. Por eso el padrón (`ExcepcionOdometro`, `FechaHastaExcepcionOdometro`) no se guarda en `vehiculo`: es el estado de hoy, y se obtiene de las excepciones activas (vista `excepcion_vigente`).

- **Origen:** `excepciones_odometro.csv`, el historial del generador (desde la versión 2.3). La patente se resuelve a la matrícula con el dominio normalizado, como en la regla de H12.
- **Clave natural:** `matricula` + `desde` + `hasta` (`UNIQUE`). La carga hace `INSERT ... ON CONFLICT (matricula, desde, hasta) DO UPDATE`: si vuelve una excepción con la misma vigencia, se actualizan su id, su motivo y si está activa. Cargar dos veces no duplica filas.
- **Conflictos y efectos laterales:** si la fuente cambia la vigencia de una excepción, la clave natural es otra pero el id (también único) se repite, y la carga falla completa en vez de guardar las dos versiones; hay que revisarlo y corregirlo a mano. Una patente que no está en el padrón no tiene matrícula y también hace fallar la carga, sin descartar la fila en silencio. `hasta` no admite vacíos para que la clave natural no deje pasar duplicados.
- **Carga diaria:** las excepciones se cargan completas, como los maestros, aunque se use `--hasta`.
- **`verificar`:** además de la clave foránea con el padrón, controla que ningún vehículo tenga más de una excepción activa (el padrón guarda una sola fecha hasta).

## Propuesta de mejora para la fuente real

La estructura de la base del sistema en uso (ver el perfil en [perfiles/](../perfiles/README.md)) muestra tres puntos que este esquema resuelve:

| En la fuente | En este esquema |
|---|---|
| El consumo se guarda como un bloque JSON por día (`data_json`), sin una fila por carga | Una fila por carga, con claves hacia tarjeta, contrato y estación: se puede consultar, sumar y cruzar sin reprocesar archivos |
| La tabla de crédito por contrato existe pero está vacía: las transferencias de saldo no quedan registradas | `transferencia` registra cada movimiento; `saldo_diario_contrato` reconstruye el saldo y permite auditar si cada transferencia era necesaria |
| El registro interno y el reporte del proveedor no comparten ninguna clave | Se cruzan igual (por dominio o persona y horario), pero el esquema deja lugar para guardar el ticket o el remito en ambos lados, lo que volvería el cruce exacto |

## Limitaciones

- Solo el escenario realista (el didáctico no tiene contratos, registro interno ni facturación por contrato).
- Si una fuente trae el padrón con excepciones pero sin el historial, la base no las reconstruye: sin la fecha desde no hay vigencia.
- Las vigencias se cargan como las da el generador: una asignación por tarjeta y dispositivo y, por vehículo, a lo sumo un cambio de estado en el período.
- SQLite es suficiente para esta escala; para un sistema en producción, el mismo esquema y las mismas vistas se trasladan a un motor servidor.
