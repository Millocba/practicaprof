# Sprint 3 — Análisis exploratorio reproducible

## Propósito

El Sprint 3 incorpora una lectura exploratoria de las fuentes operativas antes de emitir veredictos sobre las hipótesis. El artefacto responde preguntas sobre composición de la flota, comportamiento de las cargas, distribución temporal, calidad, posibilidad de cruzar fuentes y correspondencia entre el escenario sintético y los agregados reales aprobados.

La vista se encuentra en **Exploración de Datasets → Análisis exploratorio** y utiliza el mismo selector de escenario que el resto de la aplicación.

## Alcance

El EDA presenta seis bloques:

1. **Flota:** estados, tipos de vehículo, combustible y cobertura de telemetría.
2. **Cargas:** litros, proporción del tanque, distancia entre cargas y rendimiento descriptivo.
3. **Tiempo:** cargas y volumen por mes, día de la semana y hora.
4. **Calidad:** completitud, unicidad, formatos de dominio y vinculación antes/después de normalizar H1.
5. **Cruce entre fuentes:** cobertura del circuito pedido → carga → GPS diario → línea facturada.
6. **Sintético frente a real:** p05, mediana y p95 de variables aprobadas en la auditoría agregada.

Los cálculos se implementan en `streamlit_app/utils/eda.py` y la interfaz solo los representa. Se reutilizan las reglas de normalización, secuencia de odómetro, cargas por día y cruce con el registro interno existentes en `deteccion/reglas.py`.

## Criterio de interpretación

- Un valor observado describe la fuente o la relación disponible.
- Una diferencia orienta una pregunta de análisis; no demuestra por sí sola una anomalía ni su causa.
- Las comparaciones entre reglas simples y reglas con contexto permanecen en las páginas de análisis e hipótesis.
- El EDA no utiliza `ground_truth.csv` ni `casos_legitimos.csv` como entradas.
- La comparación con datos reales utiliza únicamente agregados aprobados y no expone registros ni identificadores.
- El escenario didáctico tiene un alcance parcial porque no posee GPS diario ni el circuito relacional completo del escenario realista.

## Reproducción y verificación

```bash
pip install -r requirements.txt
pytest -q tests/test_eda.py tests/test_streamlit_pages.py
streamlit run streamlit_app/app.py
```

Para la revisión visual se deben abrir ambos escenarios y verificar que los gráficos, tablas y mensajes de alcance se muestren sin excepciones. La pestaña se limita al análisis exploratorio descriptivo y no entrena modelos ni emite decisiones finales.