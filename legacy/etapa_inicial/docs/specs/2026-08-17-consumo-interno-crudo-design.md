# Diseño de la fuente cruda de consumo interno

## Objetivo

Crear un Excel sintético que represente las cargas diarias registradas por un sistema propio, conservando la coherencia temporal y relacional con la flota y la telemetría ya generadas.

## Alcance

- El período será el mismo de la base sintética: desde enero de 2025 y durante doce meses.
- Se generarán consumos todos los días del período, sin exigir que cada vehículo cargue diariamente.
- Al menos el 95 % de los 250 vehículos tendrá una o más cargas durante el período.
- Cada transacción válida tendrá como verdad base un vehículo de la tabla sintética de flota.
- Hasta el 5 % restante de la flota podrá no registrar consumos, simulando unidades inactivas, fuera de servicio o sin actividad.

## Contrato del archivo crudo

El libro contendrá una única hoja con las columnas `FECHA`, `HORA`, `LITROSCARGADOS`, `DOMINIO` y `MATRICULA`. No expondrá IDs internos ni relaciones explícitas.

Las claves naturales se derivarán del vehículo relacionado. Los errores inyectados se limitarán a representación y calidad de captura —espacios, mayúsculas/minúsculas, ceros, tipos mixtos y faltantes controlados—. La semilla y la verdad base permitirán reconstruir la asociación original y medir el desempeño de la limpieza.

## Coherencia y reglas

- Las fechas de consumo estarán dentro del intervalo cubierto por telemetría.
- Habrá registros en cada fecha calendario del período.
- Los litros serán positivos y respetarán la capacidad sintética del tanque del vehículo relacionado.
- Un mismo vehículo podrá tener múltiples consumos, pero no se simularán cargas físicamente incompatibles en una misma franja horaria.
- La cobertura por vehículo será de al menos 95 % antes de aplicar errores de formato.
- Los registros que no se vinculen directamente desde el Excel deberán seguir siendo auditables contra la verdad base del generador.

## Salidas y validación

Se producirán `consumo_interno.xlsx` y un manifiesto JSON local con semilla, período, conteos, cobertura, errores inyectados y hash. Las pruebas verificarán contrato, ausencia de IDs, cobertura, continuidad diaria, rango temporal, capacidad de tanque y reproducibilidad.

Los artefactos permanecerán fuera de Git hasta recibir una instrucción humana explícita para publicarlos.
