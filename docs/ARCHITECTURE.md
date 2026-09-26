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

## Implementación actual

| Unidad | Dónde está | Estado |
|---|---|---|
| Generación | `generator_pipeline_maestro.py` | Cinco entidades más `ground_truth.csv`, reproducible por semilla. Escenario realista: simulación diaria, estaciones, GPS diario y `casos_legitimos.csv` |
| Perfilado | `perfilador/` | Perfil agregado de fuentes externas (estructura, formatos, calidad, relaciones) sin filas ni valores sensibles, y su comparación con los datos sintéticos; ver [perfiles/README.md](../perfiles/README.md) |
| Calidad | `deteccion/reglas.py` | Duplicados, nulos y dominios sin vínculo, tal como llegan y normalizados (H1) |
| Integración | `deteccion/reglas.py` (`cruzar_registro`) | Registro interno y cargas se cruzan por dominio (o persona, en las tarjetas personales) y horario, sin clave común (asignación óptima); facturas y cargas, por la referencia de cada línea. Normalización de dominios (`normalizar_dominio`) y lectura de fechas en `AAAA-MM-DD` y `DD/MM/AAAA` (`leer_fecha`) |
| Análisis | `streamlit_app/pages/05_analisis_por_hipotesis.py` | Hallazgos de las reglas por hipótesis, sin ground truth; usa el catálogo único de `deteccion/hipotesis.py` |
| Detección | `deteccion/reglas.py`, `deteccion/modelo.py`, `deteccion/evaluacion.py` | Reglas ingenuas y con contexto, Isolation Forest y modelo supervisado, evaluados contra el ground truth |
| Hipótesis | `deteccion/hipotesis.py` | Contraste de cada hipótesis del escenario realista con veredicto calculado |
| Priorización | `deteccion/priorizacion.py` | Cola de revisión con motivos, curva de esfuerzo y vehículos a auditar |
| Persistencia | `base_datos/` | SQLite con migraciones versionadas: maestros con vigencia, operativos cargados por día de forma repetible y vistas de control (saldo diario, conciliación triple, bajas con dispositivo activo); ver [BASE_DE_DATOS.md](BASE_DE_DATOS.md) |
| Presentación | `streamlit_app/` | Aplicación Streamlit; no duplica la lógica de detección, la importa de `deteccion/` |
