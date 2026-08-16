# Arquitectura conceptual

La arquitectura se organiza alrededor del flujo y la calidad de los datos. Backend y frontend son capas de soporte, no el centro del proyecto.

```text
Generadores sintéticos
        |
Datos crudos y metadatos
        |
Validación y perfilado
        |
Limpieza, normalización e integración
        |
Datos analíticos y trazabilidad
        |
EDA, KPIs, reglas, estadística y ML
        |
Evaluación e interpretación
        |
API, reportes y visualización
```

## Unidades previstas

- **Generación:** crea entidades y eventos artificiales reproducibles junto con semilla y versión.
- **Calidad:** valida esquemas, rangos, claves, faltantes, duplicados, coherencia temporal e integridad referencial.
- **Integración:** normaliza fuentes y conserva trazabilidad de las variables derivadas.
- **Análisis:** produce perfilado, EDA, indicadores y visualizaciones reproducibles.
- **Detección:** compara reglas, estadística robusta y ML contra etiquetas sintéticas separadas.
- **Presentación:** expone resultados mediante reportes, API o interfaz sin duplicar lógica analítica.

## Persistencia y reproducibilidad

Datos crudos, procesados, analíticos y resultados tendrán ubicaciones diferenciadas. Los esquemas evolucionarán mediante migraciones versionadas y los entornos estarán separados.

Cada ejecución deberá asociarse con versión de código, esquema, semilla, parámetros, dependencias y artefactos resultantes.
