# Sprint 3 — Análisis exploratorio reproducible

## Propósito

El Sprint 3 incorpora una lectura exploratoria de las fuentes operativas antes de emitir veredictos sobre las hipótesis. El artefacto responde preguntas sobre composición de la flota, comportamiento de las cargas, distribución temporal, calidad, posibilidad de cruzar fuentes y correspondencia entre el escenario sintético y los agregados reales aprobados.

La vista se encuentra en **Exploración de Datasets → Análisis exploratorio** y utiliza el mismo selector de escenario que el resto de la aplicación.

## Continuidad con el Sprint 2

El Sprint 2 dejó las fuentes estructuradas, perfiladas y vinculables. El Sprint 3 pasa de preguntar
si los datos pueden integrarse a preguntar qué describen cuando se observan en conjunto. La lectura
incorpora solicitudes, GPS diario, facturación, contratos, transferencias y excepciones
administrativas sin reemplazar las fuentes iniciales de flota, consumo y telemetría.

Las tablas poseen granos y periodicidades diferentes: algunas describen entidades o estados, otras
registran eventos y otras documentan condiciones con vigencia temporal. Por eso los cruces se
expresan como cobertura y correspondencia, no como veredictos.

## Alcance

El EDA presenta seis bloques:

1. **Flota:** estados, tipos de vehículo, combustible y cobertura de telemetría.
2. **Cargas:** litros, proporción del tanque, distancia entre cargas y rendimiento descriptivo.
3. **Tiempo:** cargas y volumen por mes, día de la semana y hora.
4. **Calidad:** completitud, unicidad, formatos de dominio y vinculación antes/después de normalizar H1.
5. **Cruce entre fuentes:** cobertura del circuito pedido → carga → GPS diario → línea facturada.
6. **Sintético frente a real:** p05, mediana y p95 de variables aprobadas en la auditoría agregada.

Los cálculos se implementan en `streamlit_app/utils/eda.py` y la interfaz solo los representa. Se reutilizan las reglas de normalización, secuencia de odómetro, cargas por día y cruce con el registro interno existentes en `deteccion/reglas.py`.

## La historia que cuentan los datos

Con el escenario realista por defecto (semilla 42 y 200 vehículos), el código observa:

- 7.094 operaciones de carga.
- 109 vehículos en servicio, equivalentes al 54,5% de la flota.
- 88 de esos 109 vehículos en servicio tienen telemetría asociada.
- El 99,5% de las cargas encuentra un pedido del registro interno.
- El 69,5% encuentra GPS diario para el vehículo y la fecha.
- El 99,7% encuentra una línea de facturación relacionada.
- La mediana de litros sobre capacidad del tanque es 0,64.
- La mediana de distancia desde la carga anterior válida es 336 km.

La cobertura alta del pedido y de la línea facturada muestra que el circuito administrativo puede
reconstruirse en la mayoría de las operaciones. La cobertura del GPS es menor y delimita qué casos
pueden interpretarse con información de recorrido. Todas estas cifras se calculan sobre el escenario
seleccionado y no están escritas como constantes en la interfaz.

## Criterio de interpretación

- **Evidencia observada:** conteos, distribuciones, percentiles y coberturas producidos por el código.
- **Interpretación:** lectura de negocio que propone qué significa un patrón dentro del circuito.
- **Hipótesis:** explicación comprobable que todavía puede sostenerse, ajustarse o descartarse.
- Una diferencia orienta una pregunta de análisis; no demuestra por sí sola una anomalía ni su causa.
- Las comparaciones entre reglas simples y reglas con contexto permanecen en las páginas de análisis e hipótesis.
- El EDA no utiliza `ground_truth.csv` ni `casos_legitimos.csv` como entradas.
- La comparación con datos reales utiliza únicamente agregados aprobados y no expone registros ni identificadores.
- El escenario didáctico tiene un alcance parcial porque no posee GPS diario ni el circuito relacional completo del escenario realista.

## Limitaciones

- Los registros explorados son sintéticos; los agregados reales aprobados solo permiten contrastar
  escalas y no prueban representatividad completa.
- Consumo y facturación representan un proveedor, mientras el registro interno incluye otras redes.
- El GPS diario no cubre todas las cargas ni todos los estados de la flota.
- Las fuentes no comparten siempre un identificador: algunos cruces dependen de dominio o persona,
  fecha, hora y tolerancias documentadas.
- Una fila sin vínculo puede responder a calidad, alcance o periodicidad; no es automáticamente una anomalía.

## Reproducción y verificación

```bash
pip install -r requirements.txt
pytest -q tests/test_eda.py tests/test_streamlit_pages.py
streamlit run streamlit_app/app.py
```

Para la revisión visual se deben abrir ambos escenarios y verificar que los gráficos, tablas y mensajes de alcance se muestren sin excepciones. La pestaña se limita al análisis exploratorio descriptivo y no entrena modelos ni emite decisiones finales.
