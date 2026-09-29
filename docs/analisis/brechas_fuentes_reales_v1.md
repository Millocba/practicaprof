# Brechas entre fuentes externas y el generador (v1)

Comparación del escenario **realista** con tres fuentes externas de una flota, hecha con el [perfilador](../../perfiles/README.md). Las fuentes se leyeron en memoria en la máquina local y no se copiaron. Este informe usa solo metadatos agregados: nombres de columna, tipos, formatos enmascarados, porcentajes y medianas redondeadas a dos cifras. No incluye valores ni categorías.

## Fuentes perfiladas

| Fuente | Filas | Columnas | Tabla sintética |
|---|---|---|---|
| A. Padrón de flota | 1.000–9.999 | 27 | `flota` (emparejada automáticamente) |
| B. Reporte de consumos del proveedor de tarjetas | 100–999 | 31 | `consumo` (a mano) |
| C. Autorizaciones y rendiciones de carga | 100–999 | 24 | `solicitudes` (a mano) |

Las tres fuentes se vinculan bien entre sí:
- **Dominio y matrícula:** C y A coinciden al 100%.
- **Identificación de la tarjeta (B) y dominio (A):** coinciden en el 98,8%, y en el 99,3% después de normalizar.
- **Odómetro:** B y C coinciden en el 95%.
- **Número de tarjeta:** B y A coinciden en el 93%.

## Qué ya se parece

- `flota` reproduce 18 de las 27 columnas del padrón con el mismo nombre.
- La mediana del odómetro coincide: unos 130.000 km tanto en lo real como en lo sintético.
- Los tipos de combustible, las marcas y los estados siguen la misma estructura general.

## Brechas y mejoras propuestas para el generador

### Alta prioridad

**1. `consumo` es un reporte del proveedor, no una tabla de cargas simple.** La fuente real trae:
- Dos precios: el del establecimiento y el del proveedor.
- Los impuestos desglosados: IVA, CO2, combustibles líquidos y tasa vial.
- Remito (`9999-99999999`) y extracto (`9999999999-9999999999-99999999`).
- Del establecimiento: código, nombre, domicilio, localidad y provincia.
- El origen de la transacción y si es facturable.
- La tarjeta identificada por el dominio, con formato de patente.

*Propuesta:* agregar estas columnas. El remito y el extracto permiten conciliar contra la factura por documento y no solo por fecha y litros, lo que vuelve H9 más realista. La diferencia entre los dos precios abre la hipótesis de sobreprecio por establecimiento.

**2. La escala de los montos no coincide.**

| Medida | Mediana real | Mediana sintética | Diferencia |
|---|---|---|---|
| Precio por litro | ~2.400–2.500 | 2,4 | ~1.000× |
| Importe por carga | ~88.000 | 120 | ~700× |
| Litros por carga | 37 | 52 | 0,7× |
| Límite de saldo en `flota` | — | — | ~180× |
| Límite de litros en `flota` | — | — | ~4,5× |

*Propuesta:* parametrizar la moneda y el nivel de precios, y bajar los litros por carga.

**3. `solicitudes` es en realidad un circuito de autorización y rendición.** La fuente real trae:
- Litros autorizados **y** litros cargados.
- Si la carga se rindió, con fecha y hora de la rendición.
- Número de ticket.
- Anulación y fecha de anulación.
- Quién solicitó y quién cargó.
- Estación y odómetro registrado.

Lo sintético no tiene nada de la rendición ni de la anulación.

*Propuesta:* modelar la rendición. Habilita hipótesis nuevas (ver más abajo).

**4. Columnas de `flota` que no se modelan:**
- `ExcepcionOdometro` y `FechaHastaExcepcionOdometro` (98,5% vacía): vehículos exceptuados del control de odómetro. **Afecta directamente a H2**, porque un exceptuado no debería disparar alarmas de odómetro.
- `NumeroContrato`, `Cupo` y `RelacionConsumo`: 14 categorías de una letra, probablemente una relación de consumo esperado.
- `Procedencia`, `Color` y los datos de quién retira la tarjeta (`RetiraDni`, `RetiraNombre`).

### Media prioridad

**Formatos que no se generan:**
- **Dominio:** tres formatos, `AA999AA` (52%), `AAA999` (22%) y `A999AAA` (21%, patente de moto). El generador produce otro formato.
- **Matrícula:** `9999`, `99999` y `A-9999`, guardada como texto en el 74% de los casos.
- **Fecha y hora de consumo:** `99/99/9999 99:99:99`, y en el 29% la hora viene sin cero a la izquierda (`9:99:99`).
- **Número de chasis y de motor:** formatos alfanuméricos de 13 a 17 caracteres.

**Defectos de calidad para inyectar y registrar en el ground truth:**
- **Ceros usados como dato faltante:** formato `9` en `Año` (7,2%), `CapacidadTanque` (6,5%), `LimiteLitros` y `RetiraDni` (4,4%). No se inyectan y afectan cualquier cálculo de rendimiento.
- **Número de chasis y de motor:** 32% de faltantes.
- **Vacíos escritos como texto** (`-`, `S/D`) en dominio, marca, chasis y motor: 1,2–1,7%.
- **Espacios de más:** en el dominio de las solicitudes (1,7%), en el motor (3,1%) y en el conductor (1%).
- **Mayúsculas y minúsculas mezcladas** en el modelo (3,8%) y en el chasis (5%).

**Tipos:**
- `CapacidadTanque`, `LimiteLitros` y `LitrosAutorizados` son enteros en la fuente real y decimales en lo sintético.

### Baja prioridad

- **Tamaño de la flota:** la real tiene de 1.000 a 9.999 vehículos; la sintética, de 101 a 1.000.
- **Variedad de valores:** la real tiene más tipos de vehículo (7), marcas (18) y subestados (12–13).

## Hipótesis nuevas que habilitan las fuentes

- **Carga mayor que lo autorizado,** comparando litros cargados con litros autorizados en la misma autorización.
- **Rendición tardía o faltante,** usando el campo de rendido y la fecha de rendición.
- **Anulaciones:** cargas anuladas que igual aparecen en el reporte del proveedor.
- **Vehículos exceptuados del control de odómetro:** separarlos antes de evaluar H2, para no generar falsas alarmas.
- **Sobreprecio por establecimiento:** comparar el precio del establecimiento con el precio del proveedor.

## Mejoras propuestas para el perfilador

Al revisar el perfil aparecieron columnas que el perfilador **no marca como sensibles** y que deberían describirse solo por su formato:

| Columna | Qué pasa hoy | Propuesta |
|---|---|---|
| `Dependencia` (padrón), `DependeciaMovil` | Guarda formatos largos que muestran cómo se nombran las unidades organizativas | Agregar la pista `dependencia` |
| `CONTRATO` | Guarda sus categorías con el valor | Agregar la pista `contrato` |
| `EXTRACTO` | Guarda como categorías valores que son identificadores numéricos | Agregar la pista `extracto`; no guardar como categoría un valor que sea mayormente dígitos |
| `PROVINCIA`, `LOCALIDAD` | Geografía real (REAL_DATA_BOUNDARY pide regiones ficticias) | Tratarlas como `ubicacion` |
| `ESTABLECIMIENTO` | Formato con código y nombre | Pistas `establecimiento` y `remito` |

Otros ajustes:
- **Año:** redondear a dos cifras significativas lo vuelve inútil (todo da 2000). Conviene agrupar en quinquenios.
- **Formatos de texto largos:** para los sensibles, guardar solo una banda de largo, no la máscara completa.
- **Falsos positivos:** `Hora` sale como identificador y `DireccionGral` como ubicación (es una unidad organizativa). Son errores del lado seguro, pero ensucian la comparación.
- **Emparejamiento automático:** falla cuando la fuente usa MAYÚSCULAS con espacios y nombres distintos. Dos de las tres tablas no se emparejaron solas. Se podría normalizar sinónimos (`litros unidades` → `litros`) o sugerir por similitud de formatos.

## Límites

- Solo se compararon tres fuentes, de un único período.
- Las medianas de montos dependen de la moneda y de la fecha: sirven para dar escala, no para calibrar.
- El perfil completo de estas fuentes no se versiona hasta resolver las mejoras de privacidad del perfilador.
