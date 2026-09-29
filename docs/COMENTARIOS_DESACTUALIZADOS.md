# Comentarios y documentación desactualizados tras el refactor

Revisión hecha después del refactor del escenario realista v2 (PR #10 y #11). El objetivo era
simple: leer los comentarios y docstrings del código y comprobar que siguen diciendo lo que el
código hace. Se buscaron solo afirmaciones **incorrectas o desactualizadas**, no carencias de
documentación.

**Resultado: 23 hallazgos.** Ninguno es un error de lógica: el código funciona y los 152 tests
pasan. Todos son textos que quedaron diciendo otra cosa.

Cada punto incluye la cita textual, la línea del código que la contradice y la comprobación
concreta que se hizo. Los tres primeros se publican en la aplicación.

---

## Los más urgentes: se muestran en la app

Estos textos no son comentarios internos. El generador los escribe en `diccionario.json` y la
página **Diccionario de datos** los muestra a quien use la aplicación.

### 1. El formato del dominio es el del escenario equivocado

`generator_pipeline_maestro.py:313`

```python
"Dominio": ("texto", "Dominio sintético ABNNNNCD, único; no proviene de un padrón"),
```

En el escenario realista el dominio lo produce `dominio_sintetico()` (`:997`), que **siempre
empieza con Z** — `Z999AAA` para motos, `ZA999AA` para autos desde 2016, `ZZA999` para los
anteriores. El propio docstring de esa función (`:279-281`) lo dice. `ABNNNNCD` solo se genera
en el escenario didáctico (`:676`, `f"AB{i:04d}CD"`), y la entrada del diccionario no está
marcada como tal.

**Comprobación:** `git grep ABNNNNCD` devuelve dos apariciones, esta y
`docs/DICCIONARIO_DATOS.md:98`. Es decir, el error está duplicado.

**Cómo corregirlo:** describir los dos formatos y decir en qué escenario aplica cada uno, o
marcar la entrada como exclusiva del didáctico.

### 2. `litros_autorizados` describe un escenario que ya no existe

`generator_pipeline_maestro.py:419-420`

```python
"litros_autorizados": ("decimal (L)", "Litros autorizados (didáctico: 0 si fue rechazada o está "
                                      "pendiente)"),
```

En el didáctico (`:905`) el valor es `round(rng.uniform(20, 100), 2)`, **sin ninguna condición
sobre el estado**. Nunca vale 0. Además `docs/DICCIONARIO_DATOS.md:155` dice del campo
"20 a 100, generados por separado", que sí es correcto.

El "0 si fue rechazada o pendiente" venía del `generar_solicitudes_realista` anterior, de los
bloques `CARGA_CON_SOLICITUD_RECHAZADA` y del bucle sobre `TASA_SOLICITUDES_SIN_CARGA`, que
pasaban `0.0` como autorizados. Ese escenario se reescribió y ya no genera solicitudes sin
carga.

**Cómo corregirlo:** sacar la.parenthetical, o declararla como exclusivo del escenario
realista y revisar que el código del nuevo registro interno la cumpla.

### 3. La relación del ground truth omite dos tablas de destino

`generator_pipeline_maestro.py:538-541` (y el paralelo de `casos_legitimos`)

```python
("ground_truth", "id_registro", "consumo / facturacion / facturacion_detalle", "id", "N:1", AMBOS,
 "según la columna tabla; en tabla contrato_mes, el id es CTO-N|AAAA-MM"),
```

`_registrar_anomalia` y `_registrar_legitimo` se llaman también con `tabla="solicitudes"`
(`:1550`, `:1552`) y con `tabla="telemetria"` (`:2036`, `:2056-2057`). La nota menciona
`contrato_mes` pero el campo de destinos no lista ni `solicitudes` ni `telemetria`.

**Gravedad:** baja. La coletilla "según la columna tabla" salva en parte, pero el campo
`destino`, que se publica, queda incompleto.

---

## Los docstrings que describen mal la arquitectura

### 4. Las fuentes que recibe cada regla

`deteccion/reglas.py:3`

> "Cada regla recibe solo las entidades generadas (flota y consumo) y devuelve alertas."

Incorrecto desde H8, y muy incorrecto desde H10 y H11. Hay **18 funciones** que reciben además
`estaciones`, `gps_diario`, `solicitudes`, `facturacion`, `facturacion_detalle`, `contratos`,
`transferencias` o `telemetria`. La firma de `ejecutar_reglas` (`:782-784`) recibe **diez
fuentes**, no dos.

Ejemplos: `distancia_al_recorrido_gps(consumo, flota, estaciones, gps_diario)` (`:423`),
`cruzar_registro(consumo, registro, ...)` (`:469`), `detectar_factura_no_concilia(facturacion,
facturacion_detalle)` (`:601`), `detectar_irregularidades_de_cupo(consumo, contratos,
transferencias)` (`:705`), `detectar_dispositivo_activo_en_baja(flota, telemetria, ...)` (`:751`).

**Origen:** el docstring no se modificó desde `c8c495d`, la primera versión del archivo, cuando
había 9 reglas y todas usaban dos fuentes.

### 5. Qué es `id_registro`

`deteccion/reglas.py:8`

> "- id_registro: id de la transacción de consumo alertada"

`_alertas` (`:45`) toma la columna `id` del DataFrame que recibe, y desde H9 ese `id` ya no es
siempre una carga de `consumo`:

| Regla | Qué va en `id_registro` | Línea |
|---|---|---|
| `conciliacion_mensual` | `marcadas["numero_factura"]` | 594 |
| `factura_no_concilia` | `d["numero_factura"]` | 607 |
| `pdf_no_concilia` | `d["numero_factura"]` | 616 |
| `linea_sin_consumo`, `linea_duplicada`, `sobreprecio`, `precio_de_surtidor`, `producto_no_combustible` | `numero_linea` | 630, 639 |
| `ejecucion_supera_tope` | `clave_contrato_mes(c, m)` → `CTO-{contrato}\|{mes}` | 699 |
| `carga_con_saldo_agotado`, `transferencia_no_justificada` | `clave_contrato_mes(c, m)` | 717, 724 |
| `baja_con_dispositivo`, `dispositivo_activo_en_baja` | `Alias` del dispositivo | 742 |
| `rendida_sin_carga` (H8) | id del pedido del registro interno | 556, 578 |

Lo confirma el propio generador, que usa las mismas unidades: `_registrar_anomalia("contrato_mes",
...)` en `:1953` y `:1956`, y `"nivel": "factura"` / `"nivel": "contrato_mes"` en
`deteccion/hipotesis.py:132` y `:146`.

**Cómo corregirlo:** decir que es "el identificador de la entidad alertada" y que su unidad
depende de la regla.

### 6. El universo de evaluación del modelo

`deteccion/modelo.py:3-4`

> "se evalúa sobre las anomalías de comportamiento: exceso volumétrico (H3a) y retrocesos o
> saltos de odómetro (H2)"

`comparar_con_reglas` evalúa contra todo `HIPOTESIS_COMPORTAMIENTO` (`:142` →
`ids_con_anomalia_de_comportamiento`), que incluye **H2, H3a, H4, H5, H6, H7 y H8**. La
enumeración del docstring describe dos de las siete. También queda desactualizada para H4 a H7
antes del refactor; H8 la agravó.

`TIPOS_COMPORTAMIENTO` (`:28`), que sí son solo tres, es el desglose por tipo que se usa en el
`por_tipo` (`:156`), no el universo de la evaluación. Conviene no confundir una cosa con la otra.

### 7. Las hipótesis que quedan fuera del modelo

`deteccion/modelo.py:31`

```python
# Hipótesis de comportamiento (las de calidad de datos y vinculación, CALIDAD y H1,
# no son problemas de detección de outliers)
HIPOTESIS_COMPORTAMIENTO = {"H2", "H3a", "H4", "H5", "H6", "H7", "H8"}
```

Lo que queda afuera es `CALIDAD, H1, H9, H10, H11`. El comentario enumera dos de los cinco.
**H9** (facturación), **H10** (cupo de contratos) y **H11** (dispositivos) quedan fuera por otra
razón: no son anomalías de consumo, y el comentario no lo dice.

**Origen:** la enumeración era correcta cuando H9, H10 y H11 no existían.

### 8. Un filtro que `contrastar_hipotesis` no hace

`deteccion/hipotesis.py:211-212`

> "Las hipótesis cuyas reglas no emitieron ninguna alerta **ni** tienen casos en el ground truth
> (por ejemplo, H9 sin detalle de facturación) se omiten."

El único criterio de omisión es la presencia de casos en el ground truth (`:218-220`):

```python
reales = ground_truth["tipo_anomalia"].isin(h["tipos"]).any()
if not reales:
    continue
```

**No hay ninguna condición sobre las alertas emitidas.** Una hipótesis con casos inyectados y
cero alertas no se omite: entra igual, genera filas con `alertas = 0` y recibe veredicto "No se
sostiene" (`:230-233`).

**Cómo corregirlo:** quitar la parte de "no emitieron ninguna alerta", o implementarla.

---

## Código muerto que todavía tiene comentario

### 9. `_estacion_real` no lo lee nadie

`generator_pipeline_maestro.py:1349-1351`

```python
# Estación de cada carga antes de los defectos de calidad: el proveedor factura
# con la estación real aunque en nuestro registro quede vacía
self._estacion_real = {c["id"]: c["estacion"] for c in cargas}
```

`git grep _estacion_real` devuelve **una sola aparición**: la asignación. Nadie consume el
atributo.

El comentario describe una cadena de datos que ya no existe. Antes (`295d50d`) la facturación
hacía `cargas["proveedor"] = cargas["id"].map(self._estacion_real).map(marca)`. Hoy el proveedor
sale del contrato (`:1589`, `cargas["vehiculo_id"].map(self._contrato_de)`) y
`facturacion_detalle` ni siquiera tiene columna de estación.

**Cómo corregirlo:** borrar el atributo o el comentario. Si se conserva el atributo, el
comentario debería decir para qué se calcula.

### 10. `TASA_SOLICITUDES_SIN_CARGA` no la usa nadie

`generator_pipeline_maestro.py:257`

```python
TASA_SOLICITUDES_SIN_CARGA = 0.08   # solicitudes rechazadas o pendientes que no terminan en carga
```

Una aparición en todo el repo: la definición. El bloque que la usaba
(`rng.choice(["RECHAZADA", "PENDIENTE"])` con `litros_autorizados = 0.0`) desapareció con la
reescritura del registro interno. El único escenario que genera estados `PENDIENTE`/`RECHAZADA` es
el didáctico, que los sortea con `rng.choice(estados_solicitud)` y **no** con esta tasa.

### 11. `TOLERANCIA_REGISTRO_LITROS` está duplicada y la copia del generador está muerta

`generator_pipeline_maestro.py:265` la define y nunca la usa dentro del generador. La única
anomalía de litros del registro interno es `DESACUERDO_DE_LITROS` (`:1505`), donde la
diferencia siempre es de 2 a 18 L: no hay ningún umbral de 0,5 L.

La constante **sí** se usa en `deteccion/reglas.py:565`, con el mismo valor y el mismo
comentario. O sea: la tolerancia es real, pero la copia del generador quedó sin uso.

---

## Comentarios con criterios desactualizados

### 12. El saldo agotado de H10

`deteccion/reglas.py:709`

> "empieza con el saldo en cero o menos y tiene cargas es una carga que el corte debió impedir"

El código no mira el saldo con el que **empieza** el día, sino el saldo disponible **después**
de aplicar las transferencias del día (`:715`, con `saldo_para_cargar` calculado en `:687` como
`saldo + recibidas - cedidas`).

Dos efectos, en direcciones opuestas: un día que arranca positivo y con las transferencias
queda en ≤ 0 se marca sin que el docstring lo cubra, y uno que arranca en ≤ 0 pero recibe saldo
ese mismo día no se marca aunque el docstring diga que debería.

El propio archivo distingue los dos conceptos: el docstring de `_saldos_por_contrato_mes` (`:661`)
enumera por separado "saldo al empezar cada día" y "saldo para cargar (con las transferencias
del día)".

### 13. El umbral del 90 % en H10

`deteccion/reglas.py:711` y el comentario de la constante en `:41`

> "es injustificada si no llega ni al 90% del saldo" / "si la proyección no llega a este tanto del saldo"

El código real (`:720-723`):

```python
disponible = f["saldo_inicio"] - f["cedido"]
necesaria = f["proyeccion"] * MARGEN_PROYECCION      # 1.05
if necesaria < HOLGURA_TRANSFERENCIA * disponible and f["consumo"] <= disponible:
```

Tres desvíos:

1. Lo que se compara contra el 90 % es `proyeccion * 1.05`, así que el corte efectivo sobre la
   proyección cruda es `0.9 / 1.05 ≈ 0.857` de `disponible`, no 0.9.
2. La referencia es `saldo_inicio - cedido`, no "el saldo".
3. La condición es necesaria pero no suficiente: además exige que ese día no se haya cargado por
   encima de lo disponible.

---

## Otros

### 14. Un comentario pegado al valor equivocado

`generator_pipeline_maestro.py:252`

```python
"DISPOSITIVO_EN_DEPOSITO": 3,   # legítimos, como mínimo: ~4% de las bajas tiene dispositivo (fuente)    # contratos-mes en los que una transferencia llega tarde y se carga sin saldo
```

El texto sobre contratos-mes describe a `CARGA_CON_CUPO_AGOTADO`, que está en `:250`, dos
líneas arriba y **sin comentario**. Quien lea `EVENTOS_REALISTA` no puede saber qué significa
`"CARGA_CON_CUPO_AGOTADO": 1`.

### 15. `ARCHIVOS_REQUERIDOS` no cubre todo lo que el generador escribe

`streamlit_app/utils/data_loader.py:66-67`

> "También regenera si los datos en disco son de otra versión del generador (según
> `metadata.json`) o les falta algún archivo del escenario."

El chequeo real (`:76`) es `all((carpeta / archivo).exists() for archivo in
ARCHIVOS_REQUERIDOS[escenario])`, y esa lista es un **subconjunto** de lo que el generador
escribe:

- didáctico: faltan `telemetria.csv` (`:738`), `solicitudes.csv` (`:913`), `facturacion.csv` (`:950`)
- realista: faltan `telemetria.csv` (`:1388`), `solicitudes.csv` (`:1559`), `facturacion.csv`
  (`:1728`) y `metadata.json` (`:1778`)

Si falta uno de esos, la función devuelve `False` y no regenera, que es justo el caso que el
docstring dice cubrir. Las páginas que los usan (`load_telemetria`, H11, el inventario de la
página Generador) quedan sin datos.

**Aclaración:** los 4 archivos del didáctico y los 10 del realista que declara la lista **sí
existen todos**. El problema es que la lista es incompleta, no que nombre mal algún archivo.

### 16. Un comentario que menciona 2 de las 5 fuentes que restringe

`streamlit_app/utils/data_loader.py:210`

> "# Solo en el escenario realista las solicitudes y la facturación son coherentes con el consumo"

La guarda `if realista else None` de las líneas siguientes se aplica a `solicitudes` (`:211`),
`facturacion` (`:212`), `contratos` (`:214`), `transferencias` (`:215`) y `telemetria` (`:216`).
Leído tal cual, sugiere que las otras tres no tienen esa restricción, cuando la tienen por lo
mismo: solo el realista las produce.

### 17 y 18. Dos textos del pie de la página Generador

`streamlit_app/pages/01_generador.py:370`

> "- **Validaciones**: Verifica que todas las relaciones cross-entity sean válidas al 100%."

El código valida tres relaciones (`:331-335`, `:337-341`, `:343-347`) y la primera fila se agrega
con un `"100%"` fijo sin comprobar nada (`:329`). El escenario realista incumple a propósito:
`DOMINIO_INVALIDO` al 0,3 % y `TASA_DOMINIO_CON_FORMATO` al 0,5 % (generador `:258`, `:262`).

La ayuda de esa misma sección (`:316-318`) dice lo contrario, así que la página se contradice.

`streamlit_app/pages/01_generador.py:376-377`

> "Ambos incluyen las cinco entidades, `ground_truth.csv` y `metadata.json`; el realista suma
> `estaciones.csv`, `telemetria_diaria.csv` y `casos_legitimos.csv`."

El realista suma **seis** archivos: también `facturacion_detalle.csv` (`:1729`), `contratos.csv`
(`:1854`) y `transferencias.csv` (`:1968`). Y `diccionario.json` se escribe en **ambos**
escenarios (`:1772-1774`), no solo en uno. Los que faltan son justamente los que alimentan H9,
H10 y H11.

### 19. La "primera regla" de H6 no es una regla ingenua

`deteccion/hipotesis.py:4`

> "La primera es la versión ingenua; la última, la que usa el contexto que la hipótesis propone"

En H6 la primera entrada es `(None, "sin cruce con la flota")` (`:89`): **no hay regla
posible**, y el propio archivo lo define así en el comentario de `:14`. El código la reporta
igual como `f1_ingenua` valiendo 0.0 (`:227`, `:236`).

El docstring del módulo no lo contempla. Puede leerse como simplificación aceptable dado que
el comentario de `None` ya está documentado, pero conviene que quede explícito en el resumen.

### 20. El valor `"nivel"` tiene un caso sin documentar

El comentario de `deteccion/hipotesis.py:15` documenta `"nivel": "factura"`, pero H10 declara
`"nivel": "contrato_mes"` (`:146`) y `contrastar_hipotesis` no lo tiene en su diccionario
`agrupaciones` (`:214`), así que no agrupa. No es un comentario incorrecto —no afirma que
`factura` sea el único valor—, pero queda incompleto.

---

## Precisiones de origen, no causadas por el refactor

Se incluyen para que consten, pero no son regresiones.

### 21. `DESVIO_TIPEO_KM` no aplica a todos los patrones

`deteccion/reglas.py:27`

> "DESVIO_TIPEO_KM = 500  # desvío mínimo de una lectura aislada para suponer un error de tipeo"

En `_es_error_de_tipeo`, el desvío se aplica a `hueco` (`:211`) y `rebote_tras_pico` (`:212`),
pero no a `pico` (`:213`) ni a `rebote_tras_hueco` (`:214`). Una lectura aislada desviada 30 km ya
se considera tipeo en la mitad de los casos. Nunca se cambió ahí (introducido en `f516fbb`).

### 22 y 23. Omisiones en varios docstrings

No son contradicciones, son falta de cobertura:

- El docstring de módulo del generador (`:4`) sigue listando solo "Flota, Telemetría, Consumo,
  Facturación, Solicitudes", sin estaciones, contratos, transferencias ni `facturacion_detalle`.
- `generar_solicitudes_realista` (`:1420-1422`) enumera los casos legítimos pero no menciona
  `REGISTRO_REHECHO`.
- `generar_flota` (`:655`) dice "(200 vehículos)" cuando usa `self.n_flota`.

---

## Lo que se verificó y está correcto

Para que conste lo que se revisó y **no** está roto:

- **Los 21 umbrales** de `deteccion/reglas.py` (`:22-42`, `:460-462`, `:736`) coinciden en
  nombre, valor y uso con el código. También los de H10, H11 y las constantes del generador con las
  que se contrastan.
- **`FACTOR_PRECIO_EMPRESA = 0.98`** del generador contra el "2% menor" del docstring en
  `reglas.py:626`.
- **`generar_consumo`**: los porcentajes del docstring (7 %, 1,2 %, 1,2 %, 1 %, 2 %, 1 %) coinciden
  con las constantes `TASA_*`.
- **`dominio_sintetico`**, `_alterar_odometros`, `_dia_de_saldo_agotado`, `_cargas_sin_saldo` y
  `generar_contratos_realista` (lunes/jueves, margen 1,05, día 5, reserva 1,2).
- **`VERSION_GENERADOR = "2.0"`** y su referencia a `docs/DISENO_ESCENARIO_V2.md`, que existe.
- **`deteccion/datos.py`**: el docstring de `cargar_dataset` está sincronizado con lo que el
  generador escribe.
- **`deteccion/evaluacion.py`**: la clave `["id_registro", "tipo_anomalia"]` y el caso especial
  de `VALOR_NULO` coinciden.
- **`deteccion/priorizacion.py`**: los cinco métodos y el uso de `SEMILLAS_ENTRENAMIENTO` (1001-1003)
  frente a la 42 por defecto.
- **Las 12 descripciones de `HIPOTESIS`** contra los nombres de regla y umbrales reales.
- **`deteccion/reglas.py`**: los docstrings de `cruzar_registro`, `detectar_fraccionamiento`,
  `cargar_por_dia`, `_km_gps_entre_fechas` y `detectar_irregularidades_de_linea`.
- **`streamlit_app/utils/ayudas.py`**: el docstring afirma que el título sigue escribiéndose con
  `st.markdown`, y `tests/test_streamlit_pages.py:71` lo verifica buscando `## {codigo} ` entre
  los markdown.
- **`streamlit_app/pages/04_perfil_de_fuentes.py`**: el módulo, `es_local` y la descripción de
  relaciones son coherentes con `perfilador/perfil.py`.
- **152 tests pasan, 2 skip** (los 2 skips son tests de `perfilador` que requieren `sqlalchemy`,
  una dependencia opcional declarada con `importorskip`).

## Dos hallazgos que se descartaron por ser falsos

Se reportan para que no se vuelven a plantear:

- **`HIPOTESIS_COMPORTAMIENTO` usa `H2` y `H3a` mientras el catálogo tiene `H2b`, `H2c` y `H3b`.**
  No es un error: `ground_truth` usa los códigos gruesos y el catálogo del módulo los
  desglosados. El filtro de `:124` funciona correctamente sobre los datos reales.
- **`ARCHIVOS_REQUERIDOS` nombra archivos que no existen.** Todos los que declara existen. El
  problema es que la lista es un subconjunto, no que los nombres sean incorrectos.

## Nota sobre el método

La comprobación automática de acentos produjo 43 candidatos y casi todos eran falsos positivos:
`esta` como demostrativo ("esta página", sin tilde) y nombres de variable en inglés (`precision`,
`comparacion`, `despues`, `categorias`). Se revisó además el texto renderizado, no el código, que
es lo que la separación de comillas y las tildes codificadas a `?` pueden disimular. Los 23
hallazgos son los que un lector humano comprobaría como ciertos.
