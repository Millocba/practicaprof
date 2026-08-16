# Gobierno de datos y persistencia

Esta política se aplica a datasets, bases, objetos almacenados, cachés, logs, exportaciones, backups, fixtures y derivados.

## Datos permitidos

Solo se permiten datos sintéticos creados desde cero: vehículos, dispositivos, contratos, viajes, posiciones, odómetros, cargas, precios, consumos, estructuras y personas completamente ficticios. Las anomalías deliberadas tendrán etiquetas de evaluación separadas.

## Datos prohibidos

- Registros reales, incluso modificados o anonimizados.
- Muestras tomadas de planillas, APIs, capturas, logs o bases reales.
- Nombres, documentos, patentes observadas, tarjetas, dispositivos, coordenadas o contratos reales. Se permiten formatos públicos y catálogos comerciales generales sin asignaciones reales.
- Logos, marcas, dominios, textos internos o referencias identificables.
- Credenciales, tokens, cadenas de conexión y archivos de entorno.
- Dumps, bases locales, backups o logs que contengan filas.

## Clasificación y generación

Cada esquema identificará sus identificadores sintéticos, cuasi-identificadores, variables operativas, etiquetas y metadatos de generación. Se prefieren formatos inequívocos como `VEH-SYN-0001`.

Los generadores deben fijar semillas, versionar esquemas y parámetros, mantener integridad referencial, separar datos crudos y derivados y registrar anomalías inyectadas. No copiarán distribuciones exactas ni combinaciones reservadas.

## Validación antes de versionar

1. Demostrar que un generador versionado produjo el archivo.
2. Validar esquema, rangos, unicidad e integridad referencial.
3. Buscar nombres, dominios, marcas, coordenadas y patrones prohibidos.
4. Ejecutar un escaneo de secretos.
5. Revisar manualmente una muestra.
6. Documentar semilla, versión y propósito.

Si no puede demostrarse el origen sintético, el archivo no se incorpora.

## Entornos

- **Local:** exclusivo, descartable y sin datos reales.
- **Prueba:** aislado, reiniciable y alimentado con fixtures sintéticos.
- **Compartido:** accesible por más de una persona, agente o servicio.
- **Producción académica:** publicado para demostraciones y también sintético.

Ante duda, una persistencia se considera compartida.

## Escrituras y operaciones destructivas

Antes de escribir se registran entorno, destino, tablas afectadas y efecto esperado. Las cargas prefieren transacciones, claves deterministas, upserts controlados e idempotencia.

Borrar, truncar, recrear, sobrescribir, restaurar, migrar irreversiblemente o reemplazar estado mediante una carga masiva requiere, sobre persistencias compartidas:

1. Aprobación humana explícita.
2. Alcance exacto y comando a ejecutar.
3. Respaldo identificado.
4. Procedimiento de restauración.
5. Ventana e impacto esperado.
6. Verificación posterior.

## Migraciones, backups y pruebas

Cada migración se versiona, prueba en una base efímera, declara compatibilidad, bloqueos, costos y rollback, y verifica versión, conteos, restricciones e integridad al terminar. No se editan esquemas compartidos manualmente.

Un backup solo se considera recuperable si se conocen fecha, alcance, ubicación protegida, retención y procedimiento de restauración probado. Los backups no se versionan en Git.

Los tests nunca apuntan a producción: utilizan bases temporales, contenedores aislados o transacciones revertidas y verifican no dejar estado residual.

## Incidentes

Ante una posible exposición se detiene el trabajo, no se reproduce el contenido y se avisa a una persona responsable. Borrar un archivo en un commit nuevo no elimina su historial; la persona responsable decide eliminación de historial y rotación de secretos.
