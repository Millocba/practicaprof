# Diseño: diagnóstico agregado de H8 (ventanas del cruce) y H9 (precios del detalle de facturación)

Fecha: 2026-10-18

## Objetivo

Sumar a la auditoría agregada dos bloques de **diagnóstico** (no cambian reglas ni cifras ya
publicadas):

- **H8** — `diagnostico.cruce_registro_ventanas`: cuánto del circuito registro ↔ carga ↔ factura queda
  fuera por la **ventana** del cruce (hoy de 3 horas antes a media hora después de la carga), para
  decidir si conviene ensancharla.
- **H9** — `diagnostico.facturacion_detalle_precios`: cómo se relacionan los **precios unitarios** del
  reporte de consumo con el precio facturado y con el descuento fijo entre ellos, y qué tan lejos
  están la deuda, la suma de las líneas y el total del PDF.

## Contexto

- El cruce con contexto (`cruzar_registro(..., voraz=False, flota=...)`) une cada carga con, a lo sumo,
  un pedido del registro interno. Un pedido puede hacerse hasta `MINUTOS_ANTES_REGISTRO = 180` antes de
  la carga o hasta `MINUTOS_DESPUES_REGISTRO = 30` después.
- El adaptador trae `consumo` (con `precio_unitario` = la primera columna de precio del reporte) y
  `facturacion_detalle` (con `precio_unitario` = importe / litros de la línea).
- El reporte de consumo trae **dos** columnas de precio unitario; el adaptador hoy mapea solo una.

## Alcance

- Nuevo bloque `diagnostico.cruce_registro_ventanas` (H8).
- Nuevo bloque `diagnostico.facturacion_detalle_precios` (H9), solo sobre los meses completos del
  reporte (los que ya filtra `auditar`).
- En el adaptador: exponer **todas** las columnas de precio unitario del reporte, en su orden, con
  nombres genéricos (`precio_a`, `precio_b`, ...), en `datos["precios_reporte"]`.
- Tests sintéticos que cubran cada banda y sus bordes, y que no quede ningún entero de 1 a 19 suelto.

## Fuera de alcance

- No cambia `cruzar_registro`, la ventana ni ninguna regla o hipótesis.
- No cambia el resto de la salida de la auditoría.
- No aparece en el repo ningún nombre real de columna ni la sigla del proveedor: la detección es por
  patrón (`toda columna cuyo nombre contenga "PRECIO"`) y las etiquetas son `precio_a`, `precio_b`, ...

## 1. Columnas de precio (adaptador)

En `adaptar`, sobre el reporte de consumo crudo:

- `columnas_precio = [c for c in fuente.columns if "PRECIO" in str(c).upper()]` (en el orden del
  reporte). No se miran los totales por litro.
- Se arma `datos["precios_reporte"]` con `id` (el mismo de `consumo`) y una columna por cada precio,
  `precio_a`, `precio_b`, ... Solo si hay al menos una columna de precio.
- No se agregan columnas a `datos["consumo"]` (varias reglas recorren todas sus columnas; se deja el
  resto intacto).

## 2. H8 — `diagnostico.cruce_registro_ventanas`

Con `consumo`, el registro ya filtrado (`datos["solicitudes"]`) y la flota. Se corre el **cruce con
contexto** una vez (`cruzar_registro`) y se reusa su resultado.

**Vocabulario de bandas de tiempo (por diferencia absoluta |Δ|):** `hasta_3_horas` (≤ 180 min),
`de_3_a_6_horas` (180, 360], `de_6_a_12_horas` (360, 720], `de_12_a_24_horas` (720, 1440],
`ninguno_a_menos_de_24_horas` (> 1440 o sin pedido del mismo dominio). El uso de |Δ| ya mira hacia
adelante y hacia atrás; ±12 h queda cubierto por `de_6_a_12_horas`.

- **(a) cargas sin pedido (con contexto).** Para cada carga que el cruce dejó sin pedido, se busca un
  **pedido del mismo vehículo por dominio** (dominio normalizado del vehículo de la carga, tomado de la
  flota y, si falta, del propio reporte) a |Δ| en cada banda; la carga cae en la banda más chica que
  encuentre. Salida:
  `{"cargas_sin_pedido": {"total": ..., "con_pedido_del_mismo_vehiculo": {<banda>: ...}}}`.
  El total y las bandas forman una partición: se publican con `_partes_sin_resta`.

- **(b) pedidos sin carga.** Los pedidos rendidos (no anulados) que el cruce dejó sin carga, ya sin los
  de otra red: `{"pedidos_sin_carga": {"total": ...}}`.

- **(c) minutos de los pares que cruzan.** Para las cargas que sí cruzaron, |Δ| en bandas
  `hasta_5`, `de_5_a_30`, `de_30_a_60`, `de_1_a_3_horas` (60, 180], `mas_de_3_horas` (> 180). Partición
  publicada con `_partes_sin_resta`.

- **(d) por mes y por tipo de vehículo.** Conteos de cargas sin pedido y de pedidos sin carga, por mes
  (`AAAA-MM`) y por `TipoVehiculo` de la flota (o `sin_dato`). Cada serie se publica con
  `_partes_sin_resta` contra su total global, para que ningún mes chico se recupere por resta.

Se agrupa por dominio (sin producto cartesiano), con búsqueda binaria sobre instantes ordenados por
grupo: la memoria se mantiene acotada.

## 3. H9 — `diagnostico.facturacion_detalle_precios`

Con `facturacion_detalle`, `facturacion`, `consumo` y `precios_reporte`. Devuelve `None` si no hay
detalle. Cada línea se une con su carga por `referencia_consumo` → `id` de `consumo`, y con su factura
por `numero_factura` (para el mes = `periodo`).

**Bandas del cociente precio facturado / precio unitario del reporte** (una por columna de precio):
`menos_de_0_95`, `de_0_95_a_0_98`, `de_0_98_a_1_00`, `de_1_00_a_1_02`, `mas_de_1_02`, con los cortes
`[0.95, 0.98, 1.00, 1.02]` (el corte es de la banda de arriba, salvo el de 1.02, que cierra
`de_1_00_a_1_02`). Salida por columna:
`{"precio_facturado_sobre_cada_precio_unitario": {"precio_a": {"total": ..., <bandas>: ..., "por_mes":
   {AAAA-MM: {<bandas>}}, "por_producto": {PRODUCTO: {<bandas>}}}, "precio_b": {...}}}`. El `total` y
las bandas forman una partición publicada con `_partes_sin_resta`.

**Razón entre los dos precios unitarios del reporte (el segundo sobre el primero; empresa sobre
surtidor):** `menos_de_0_97`, `de_0_97_a_0_98`, `exactamente_0_98` (± 0.0005), `de_0_98_a_0_99`,
`mas_de_0_99`; solo si hay dos o más columnas de precio. Se informa sobre las cargas del detalle.
Salida: `{"razon_entre_precios_unitarios": {"total": ..., <bandas>: ..., "por_mes": {AAAA-MM: {<bandas>}}}}`.

**Diferencias de importes (por factura, por mes):**
- `deuda` menos suma de líneas: `(deuda - Σlíneas) / Σlíneas`.
- total del PDF menos deuda: `(pdf - deuda) / deuda`; las facturas sin PDF quedan en `sin_pdf`.
Bandas de diferencia relativa: `exacta` (|r| = 0), `hasta_0_1_pct` (0<|r| ≤ 0.001),
`de_0_1_a_0_5_pct` (0.001, 0.005], `de_0_5_a_2_pct` (0.005, 0.02], `mas_de_2_pct` (> 0.02). Salida:
`{"diferencias_entre_deuda_y_lineas": {"total": ..., "por_mes": ...},
  "diferencias_entre_pdf_y_deuda": {"total": ..., "por_mes": ...}}`.

**Líneas:**
- `cargas_facturadas_mas_de_una_vez` (misma carga en dos líneas).
- `lineas_sin_carga_en_el_reporte`.
- `lineas_con_concepto_distinto_de_combustible`.
- `lineas_por_mes_de_facturacion`: `en_el_mismo_mes_que_su_carga` / `en_otro_mes` (mes de la factura
  contra mes de la carga).

Todas las particiones con total visible se publican con `_partes_sin_resta`; el resto, con `acotar`.

## Privacidad

Ningún identificador sale del entorno. Solo cantidades (0, "1–19" o el número) y porcentajes. El mes
sale como `AAAA-MM`; nunca fechas sueltas.

## Pruebas

- Un test por bloque con series sintéticas que cubran cada banda y los **bordes** (pedido justo a 3 h y
  a 3 h + 1 min; cociente exactamente en 0.98 y en el borde de una banda de diferencia).
- Test de que en la salida del bloque no queda ningún entero de 1 a 19 suelto.
- `tests/test_auditoria.py` sigue pasando; se agrega una segunda columna de precio (con nombre genérico)
  a la fuente sintética para ejercitar las dos columnas.
- Suite completa `python -m pytest -q`.

## Corrida real

Dejar el JSON en `perfiles/pendientes/auditoria_AAAA-MM-DD.json`, **sin aprobar**, verificando el diff
con el aprobado de referencia (el cambio de números por data nueva ya está documentado en Tanda A).
