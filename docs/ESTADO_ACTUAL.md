# Estado actual del proyecto

> Documento vivo: los valores entre `{{ }}` se completan con los datos en uso cuando se abre en la página **Documentación** de la aplicación, y así se descarga. En GitHub se ven los nombres de las variables. La lista de variables disponibles está en esa misma página.

**Actualizado al {{ hoy }}** · versión {{ version.commit }} ({{ version.fecha }}, rama {{ version.rama }}) · escenario **{{ escenario }}**, semilla {{ generacion.seed }}, {{ generacion.vehiculos }} vehículos, generado el {{ generacion.fecha }}.

## Datos en uso

| Tabla | Filas |
|---|---|
| flota | {{ filas.flota }} |
| consumo | {{ filas.consumo }} |
| solicitudes | {{ filas.solicitudes }} |
| facturacion | {{ filas.facturacion }} |
| facturacion_detalle | {{ filas.facturacion_detalle }} |
| telemetria | {{ filas.telemetria }} |
| telemetria_diaria | {{ filas.telemetria_diaria }} |
| estaciones | {{ filas.estaciones }} |

El detalle de cada tabla y sus relaciones está en el [diccionario de datos](DICCIONARIO_DATOS.md).

## Anomalías y casos legítimos

Hay **{{ anomalias.total }}** anomalías inyectadas de **{{ anomalias.tipos }}** tipos. Las de comportamiento afectan al **{{ anomalias.prevalencia }}** de las cargas.

{{ anomalias.tabla }}

Además hay **{{ legitimos.total }}** casos legítimos que se parecen a anomalías y sirven para medir las falsas alarmas:

{{ legitimos.tabla }}

## Hipótesis

Se sostienen **{{ hipotesis.sostenidas }} de {{ hipotesis.total }}** hipótesis con los datos en uso. Una hipótesis se sostiene cuando la regla con contexto mejora el F1 de la regla ingenua en al menos 0,10.

{{ hipotesis.tabla }}

Estos valores corresponden a una sola semilla; los promedios de referencia sobre 5 semillas están en el [README](../README.md).

## Últimos cambios

{{ bitacora.ultimos_cambios }}

La historia completa, con el motivo de cada cambio, está en la [bitácora](BITACORA.md).
