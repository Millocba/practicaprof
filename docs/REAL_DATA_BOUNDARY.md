# Límite entre metadatos reales y datos sintéticos

## Regla central

El entorno del proyecto no recibe filas reales. Un futuro perfilador autorizado se ejecutará cerca de la fuente, con credenciales temporales de solo lectura, y devolverá solamente metadatos estructurales y estadísticas agregadas aprobadas.

## Información permitida

- Nombres técnicos de tablas y columnas previamente revisados.
- Tipos, nulabilidad, claves, restricciones y relaciones.
- Conteos aproximados o agrupados en bandas.
- Porcentajes de faltantes y duplicados.
- Cardinalidades aproximadas.
- Cuantiles redondeados y distribuciones agrupadas.
- Frecuencias de categorías con umbral mínimo de grupo.
- Patrones temporales agregados por intervalos suficientemente amplios.
- Tipos y tasas agregadas de problemas de calidad.

## Información prohibida

- Filas o muestras, aunque se oculten algunas columnas.
- Valores directos, mínimos o máximos que representen casos singulares.
- Texto libre, nombres, identificadores, coordenadas exactas o recorridos.
- Combinaciones raras que permitan inferir una entidad.
- Dumps, backups, logs, capturas o respuestas completas de consultas.
- Credenciales, URLs de conexión o nombres internos sensibles.

## Reglas de agregación

- No exportar grupos con menos de 20 observaciones.
- Redondear conteos y cuantiles cuando la exactitud no sea necesaria.
- Agrupar categorías infrecuentes bajo `OTRA_CATEGORIA_SINTETIZABLE`.
- Usar intervalos temporales mensuales o mayores salvo justificación aprobada.
- Sustituir geografía real por regiones ficticias; nunca exportar centroides reales.
- Revisar manualmente el artefacto agregado antes de moverlo al proyecto.

## Procedimiento futuro de perfilado

1. Crear una credencial temporal con permisos `SELECT` sobre vistas aprobadas.
2. Confirmar entorno, tablas y consultas exactas.
3. Ejecutar el perfilador sin logging de valores.
4. Producir un manifiesto agregado sin secretos.
5. Revisarlo dentro del entorno controlado.
6. Transferir solo el manifiesto aprobado.
7. Revocar la credencial temporal.
8. Registrar fecha, responsable y versión del perfil, no sus datos de origen.

## Herramienta

El paquete `perfilador/` aplica estas reglas a archivos CSV o Excel: se ejecuta en la máquina donde están los archivos, los lee en memoria y escribe solo el perfil agregado en `perfiles/pendientes/`, que no se versiona. Un perfil pasa a `perfiles/aprobados/` únicamente con la revisión manual registrada (responsable y fecha). La página **Perfil de fuentes** de la aplicación solo acepta archivos cuando corre en la máquina local; en la aplicación publicada acepta perfiles ya generados. El procedimiento está en [perfiles/README.md](../perfiles/README.md).

## Criterio de detención

Si una estadística permite reconocer una persona, activo, lugar o evento, no sale del entorno controlado. Si existe duda, se considera sensible.
