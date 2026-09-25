# Perfiles de fuentes

Perfiles **agregados** de fuentes de datos externas: estructura y calidad, sin filas ni valores sueltos. Sirven para comparar esas fuentes con lo que produce el generador y decidir qué agregarle. Siguen las reglas de [REAL_DATA_BOUNDARY.md](../docs/REAL_DATA_BOUNDARY.md).

| Carpeta | Contenido | ¿Se versiona? |
|---|---|---|
| `pendientes/` | Perfiles recién generados, todavía sin revisar | No (está en `.gitignore`) |
| `aprobados/` | Perfiles revisados por una persona responsable, con su nombre y la fecha, y sus informes de brechas | Sí |

## Qué contiene un perfil

- **Por tabla:** filas en bandas (por ejemplo, "1.000–9.999"), cantidad de columnas, porcentaje de filas duplicadas y columnas candidatas a clave.
- **Por columna:** tipo, porcentaje de faltantes, cardinalidad en bandas, formatos (`ABC123` → `AAA999`) con su frecuencia y defectos de calidad (espacios extra, vacíos escritos como texto, números guardados como texto…).
- **Numéricas:** cuantiles con dos cifras significativas, sin mínimos ni máximos.
- **Fechas:** formatos y cantidad por mes.
- **Categorías:** solo las que tienen 20 casos o más; el resto se agrupa como `OTRA_CATEGORIA_SINTETIZABLE`.
- **Columnas sensibles** (identificadores, personas, patentes, ubicaciones, texto libre): se detectan por el nombre o el formato y se describen **solo por su formato**, sin valores, cuantiles ni categorías.
- **Relaciones:** qué porcentaje de los valores de una columna existe en la clave de otra tabla, exacto y después de normalizar (mayúsculas, sin espacios ni guiones).

## Procedimiento

1. **Generar**, junto a los datos (los archivos se leen en memoria y no se copian):
   ```bash
   python -m perfilador perfilar archivo1.xlsx archivo2.csv --origen "fuentes reales"
   ```
   O desde la página **🔬 Perfil de fuentes** con la app corriendo en la máquina local. En la app publicada esa opción está deshabilitada, porque los archivos viajarían a un servidor externo.
   Se le pueden pasar carpetas: se recorren completas y se leen solo los CSV y Excel. Los archivos del mismo tipo (mismo nombre salvo los números, por ejemplo uno por día) forman una sola tabla cuyo nombre es el patrón (`consumo_9999-99-99`), así el perfil no guarda fechas ni otros números de los nombres.

   - Si el nombre es solo un identificador (un UUID), se agrupan los archivos que tienen las mismas columnas, en una tabla `tabla_de_N_columnas`.
   - Cada grupo se une como **lotes** (cada archivo trae registros distintos: se apilan) o como **versiones** (cada archivo repite casi los mismos registros, como un padrón exportado varias veces: se perfila solo el más reciente, para no multiplicar las filas). El perfil registra cuántos archivos tiene cada tabla y cómo se unieron.
   - Si un nombre de tabla incluye el de una organización o persona, se reemplaza al generar: `--renombrar "patrón=nombre"`. Editarlo a mano en el JSON obliga a cambiarlo también en las relaciones.

   **Si los archivos están en un servidor**, el perfilador se ejecuta allí, en una terminal del servicio, y solo sale el perfil:
   ```bash
   mkdir -p /tmp/p/perfilador && cd /tmp/p
   for f in __init__ __main__ perfil comparar; do
     curl -fsSL https://raw.githubusercontent.com/Millocba/practicaprof/dev-hector/perfilador/$f.py -o perfilador/$f.py
   done
   python -m perfilador perfilar /ruta/de/los/archivos --origen "fuentes reales" --salida /tmp/perfil.json
   ```
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
