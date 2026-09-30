# Perfiles de fuentes

Perfiles **agregados** de fuentes de datos externas: estructura y calidad, sin filas ni valores sueltos. Sirven para comparar esas fuentes con lo que produce el generador y decidir qué agregarle. Siguen las reglas de [REAL_DATA_BOUNDARY.md](../docs/REAL_DATA_BOUNDARY.md).

| Carpeta | Contenido | ¿Se versiona? |
|---|---|---|
| `pendientes/` | Perfiles recién generados, todavía sin revisar | No (está en `.gitignore`) |
| `aprobados/` | Perfiles revisados por una persona responsable, con su nombre y la fecha, y sus informes de brechas | Sí |

## Qué contiene un perfil

- **Por tabla:** filas en bandas (por ejemplo, "1.000–9.999"), cantidad de columnas, porcentaje de filas duplicadas y columnas candidatas a clave.
- **Por columna:** tipo, porcentaje de faltantes, cardinalidad en bandas, formatos (`ABC123` → `AAA999`) con su frecuencia y defectos de calidad (espacios extra, vacíos escritos como texto, números guardados como texto…).
- **Numéricas:** cuantiles con dos cifras significativas, sin mínimos ni máximos. Un cuantil se publica solo si deja al menos 20 casos de cada lado (con menos de 400 valores, p05 y p95 quedan vacíos).
- **Fechas:** formatos y cantidad por mes.
- **Categorías:** solo las que tienen 20 casos o más; el resto se agrupa como `OTRA_CATEGORIA_SINTETIZABLE`.
- **Columnas sensibles** (identificadores, personas, patentes, ubicaciones, organizaciones, texto libre): se detectan por el nombre o el formato y se describen **solo por su formato**, sin valores, cuantiles ni categorías. Sus formatos de más de 20 caracteres se resumen por su largo (`TEXTO_21-40`, `TEXTO_MAS_DE_40`), y los textos que son mayormente dígitos (remitos, extractos) se tratan como identificadores.
- **Tablas chicas** (menos de 20 filas, como un catálogo de contratos): sin estadísticas; de las columnas numéricas se informa cómo se reparte el total, en porcentajes ordenados sin asociarlos a ninguna fila, y el total redondeado. Una tabla vacía figura con `0` filas.
- **Controles que cruzan tablas** (`controles`): conteos por categoría calculados junto a los datos, con los conteos de 1 a 19 informados como `1–19`. Hoy: `telemetria_vs_estado`, móviles por estado según tengan dispositivo, si está en el grupo de depósito (baja / reemplazos) y si transmitió en la última semana; la alerta cuenta los móviles en baja con el dispositivo fuera del depósito y transmitiendo.
- **Relaciones:** qué porcentaje de los valores de una columna existe en la clave de otra tabla, exacto y después de normalizar (mayúsculas, sin espacios ni guiones).

## Procedimiento

1. **Generar**, junto a los datos (los archivos se leen en memoria y no se copian):
   ```bash
   python -m perfilador perfilar archivo1.xlsx archivo2.csv --origen "fuentes reales"
   ```
   O desde la página **🔬 Perfil de fuentes** con la app corriendo en la máquina local. En la app publicada esa opción está deshabilitada, porque los archivos viajarían a un servidor externo.
   Se le pueden pasar carpetas: se recorren completas y se leen solo los CSV, los Excel y las bases SQLite (`.db`, `.sqlite`: cada tabla, abierta en modo solo lectura). Los archivos con las mismas columnas (uno por día, copias descargadas varias veces, exportaciones del mismo padrón) forman una sola tabla, que se llama como el nombre de archivo más frecuente del grupo sin copias ni fechas: `ReporteConsumos (12)` y `consumo_2025-09-01` quedan como `ReporteConsumos` y `consumo`. Así el perfil no guarda fechas ni otros números de los nombres.

   - Si los nombres son solo identificadores (UUID), la tabla se llama `tabla_de_N_columnas`.
   - Cada grupo se une como **versiones** o como **lotes**. Son versiones cuando la unión de las claves apenas supera (hasta un 10%) al archivo más grande, como un padrón exportado varias veces: se perfila solo el más reciente, para no multiplicar las filas. Si no, son lotes: se apilan del más reciente al más antiguo y se descartan los registros cuya clave ya vino en un archivo más reciente (exportaciones que se superponen). El perfil registra cuántos archivos tiene cada tabla, cómo se unieron y qué porcentaje de filas se descartó por repetirse entre archivos.
   - Si un nombre de tabla incluye el de una organización o persona, se reemplaza al generar con `--renombrar "nombre=nuevo"`. Para un texto que aparece en cualquier parte del perfil (nombres de tabla o columna, relaciones o valores de categorías, como el nombre de un proveedor), `--reemplazar "texto=nuevo"`, sin distinguir mayúsculas. Editar el JSON a mano obliga a cambiarlo también en las relaciones.

   **Si los archivos están en un servidor**, el perfilador se ejecuta allí, en una terminal del servicio, y solo sale el perfil:
   ```bash
   mkdir -p /tmp/p/perfilador && cd /tmp/p
   for f in __init__ __main__ perfil comparar; do
     curl -fsSL https://raw.githubusercontent.com/Millocba/practicaprof/dev-hector/perfilador/$f.py -o perfilador/$f.py
   done
   python -m perfilador perfilar /ruta/de/los/archivos --origen "fuentes reales" --salida /tmp/perfil.json
   ```
   Para sumar las tablas de la base de datos del servidor, se agrega `--base-url-env VARIABLE` con el nombre de la variable de entorno que tiene la cadena de conexión (no su valor): se leen todas las tablas en una transacción de solo lectura, con el prefijo `base.`, y la cadena no se muestra ni se guarda. Necesita `sqlalchemy` y el conector de la base (por ejemplo `pymysql`), que suelen estar en el servidor de la aplicación.

   Necesita Python con `pandas` y `openpyxl`. Solo lee los archivos y escribe el perfil en `/tmp`, fuera de la carpeta de datos. Después se copia el perfil a `perfiles/pendientes/` y se borra `/tmp/p` y `/tmp/perfil.json` del servidor.
2. **Revisar** el perfil en `pendientes/`: que no incluya nombres, identificadores, lugares ni combinaciones que permitan reconocer una entidad. Si hay dudas, no se aprueba.
3. **Aprobar**, registrando quién lo revisó:
   ```bash
   python -m perfilador aprobar perfiles/pendientes/perfil_AAAA-MM-DD.json --responsable "Nombre" --notas "..."
   ```
4. **Comparar** con los datos sintéticos, desde la página o con:
   ```bash
   python -m perfilador comparar perfiles/aprobados/perfil_AAAA-MM-DD.json --escenario realista
   ```
   Se escribe `perfil_AAAA-MM-DD_brechas.md` junto al perfil, con cada brecha y su sugerencia para el generador.
5. **Commitear** el perfil aprobado y su informe.

## Auditoría agregada

Con el mismo cuidado que el perfil, las reglas y los modelos del proyecto pueden correr sobre las fuentes, junto a los datos, y devolver **solo agregados**:

```bash
python -m perfilador auditar /ruta/de/los/archivos --base-url-env VARIABLE --proveedor "TEXTO" --salida /tmp/auditoria.json
```

- Un adaptador traduce cada fuente al esquema del generador. Cada fuente se reconoce por sus columnas, no por su nombre.
- `--proveedor` es el texto que identifica las estaciones del proveedor en el registro interno. Se usa para separar las estaciones de otra red y no se guarda en ningún lado.
- **Resultado:**
  - cuántas cargas marca cada regla y cada hipótesis, con la versión ingenua y con contexto;
  - qué proporción de cargas cruza con el registro interno y con qué diferencia de horario;
  - cuantiles de las variables del modelo, reales frente a sintéticos, para ver si el modelo generaliza;
  - coincidencias entre los métodos en las 100 cargas más prioritarias;
  - diagnósticos de la traducción;
  - **odómetro** (`diagnostico.odometro`): vehículos exceptuados hoy, cargas con excepción vigente y cargas sin avance, separadas en las cubiertas por una excepción o del mismo día y las que no tienen justificación (H12). Usa `ExcepcionOdometro` y `FechaHastaExcepcionOdometro` del padrón y el historial de excepciones si está;
  - **alcance y cobertura** (`diagnostico.cobertura`): de qué red es cada fuente (el reporte, la facturación y los contratos, de un proveedor; el registro interno, de todas), cargas, pedidos y líneas facturadas por mes, qué parte de los vehículos del registro aparece en el reporte, si los pedidos rendidos sin carga son de vehículos que el reporte trae ese mes y cuántas cargas de otra red cierran tramos de odómetro;
  - **reclamos al proveedor** (`diagnostico.reclamos`), si está la tabla de reclamos (la que tiene `tipo_alerta`, `estado_reclamo`, `monto_reclamable` y `nro_ticket`): reclamos por tipo y por estado, y qué parte se vinculó con una carga del reporte. Se vinculan por el ticket, que es el REMITO (entero o su segunda parte, también si llegó como número); si falta, por patente y hora o, para las tarjetas personales, por tarjeta y hora, con la carga más cercana a menos de 15 minutos. Por cada tipo (doble cobro, que en la fuente se llama `duplicidad_metodo`, con H13; cargas múltiples con H4; y odómetro estancado con H12) y cada regla de su hipótesis: qué parte de los reclamos anticipa la regla (una estimación de lo que se escapa), qué parte de sus alertas del período que cubren los reclamos terminó en un reclamo, qué parte de los resueltos terminó en nota de crédito (la mejor estimación de precisión disponible) y el monto reclamable cubierto, con dos cifras significativas y solo los montos positivos (los demás se cuentan aparte). Los tipos y estados se agrupan por palabras clave; cualquier otro valor queda como `otro`. El mensaje, los números de ticket y de reclamo, la patente, la tarjeta y el establecimiento no salen.
- **Privacidad:** los conteos de 1 a 19 se informan como `1–19`. No sale ningún identificador, carga, vehículo ni persona.
- **Qué no corre:** las hipótesis cuyos datos no están en la fuente, es decir, la ubicación de las estaciones (H7), el GPS diario, la fecha del cambio de estado (H6) y las transferencias (H10). El diagnóstico lo informa.
- **Período:** los pedidos del proveedor se limitan a los días con cargas en el reporte; las cargas de otra red se conservan en todo el período, porque cierran tramos. La facturación se concilia solo en los meses que el reporte cubre completos (cargas en el 90% de sus días y en alguno de los últimos 3): en un mes parcial o en curso, las líneas de los días que faltan quedarían sin carga. Un reporte puede tener meses sin descargar: sus pedidos se cuentan en `cobertura.por_mes`, pero no se cruzan.
- **Otras redes:** las cargas en estaciones de otra red que anota el registro interno se intercalan en la secuencia de cada vehículo para las reglas con contexto y las variables del modelo. Sus reportes y su facturación no están, así que no se concilian.
- **Qué no mide:** sin etiquetas reales no hay precisión ni recall. Mide cuánto marca cada regla, cuánto se parecen los datos y cuánto coinciden los métodos. Los reclamos son la referencia más cercana, con dos límites: nacen de las alertas de la fuente (lo que la fuente no alerta no se reclama) y, mientras casi todos estén pendientes, la nota de crédito no se puede estimar (queda vacía con menos de 20 resueltos).
- **Requisitos:** necesita el repositorio completo (el generador, `deteccion/` y `perfilador/`) y las librerías `scipy` y `scikit-learn`.
- **Aprobación:** el resultado se revisa y se aprueba igual que un perfil (`aprobar`).

