# Aplicación Streamlit

Interfaz para generar, explorar y evaluar los datos sintéticos del pipeline maestro. La lógica no está en la app: los datos salen de [`generator_pipeline_maestro.py`](../generator_pipeline_maestro.py) y la detección de [`deteccion/`](../deteccion/).

## Ejecutar localmente

Desde la raíz del repositorio, con Python 3.12:

```bash
pip install -r requirements.txt
streamlit run streamlit_app/app.py
```

Se abre en http://localhost:8501. No hace falta generar datos antes: si no existen, la app los crea con la semilla por defecto (200 vehículos, semilla 42) la primera vez que se abre una página.

En la barra lateral se elige el **escenario**, y la elección vale para todas las páginas:

- **Realista** (predeterminado): uso simulado día por día, anomalías sutiles y casos legítimos que se parecen a anomalías.
- **Didáctico**: anomalías inconfundibles, para explicar el método.

## Páginas

| Página | Archivo | Qué muestra |
|---|---|---|
| Inicio | `app.py` | KPIs (vehículos, transacciones, vinculación consumo ↔ flota, facturación), estado de la generación y resumen de datasets |
| Generador | `pages/01_generador.py` | Genera un dataset nuevo con otra cantidad de vehículos o semilla; **🔄 Refrescar** recarga los datos |
| Datasets | `pages/02_datasets.py` | Explorar, filtrar y exportar cada tabla; muestra el grano, la clave y el diccionario de columnas de la tabla elegida |
| Diccionario de datos | `pages/03_diccionario_de_datos.py` | Tablas (rol, grano, clave, filas), diagrama y tabla de relaciones, columnas de cada tabla (descargable en JSON) y catálogos de anomalías y casos legítimos del escenario, a partir del `diccionario.json` del generador |
| Análisis por hipótesis | `pages/05_analisis_por_hipotesis.py` | Qué encuentran las reglas en los datos, sin usar el ground truth: calidad de datos y una pestaña por hipótesis del escenario (H1 a H9 en el realista; H1, H2 y H3a en el didáctico) con el antes y después de la regla ingenua a la regla con contexto y los casos concretos |
| Detección | `pages/06_deteccion.py` | Reglas evaluadas contra el ground truth; en el escenario realista, el origen de cada falso positivo (caso legítimo, otra anomalía o carga normal) y un explorador de errores |
| Hipótesis | `pages/07_hipotesis.py` | Validación contra el ground truth, siempre en el escenario realista: para cada hipótesis compara la regla ingenua con la regla con contexto y da el veredicto calculado, las falsas alarmas y casos concretos |
| Documentación | `pages/09_documentacion.py` | Los `.md` del proyecto con variables que toman los valores actuales (`docs/ESTADO_ACTUAL.md`), la bitácora (`docs/BITACORA.md`) más el historial de git, y descarga de un documento o de todos en `.zip` |
| Modelo de ML | `pages/08_modelo_ml.py` | Realista: qué revisar primero según un presupuesto de revisión, curva de esfuerzo de cinco métodos, cola de revisión con motivos (descargable), vehículos a auditar y facturas a revisar ordenadas por importe en juego. Didáctico: Isolation Forest comparado con las reglas |

## Datos

- Las páginas leen `datasets/synthetics_realista/` o `datasets/synthetics_maestro/` (didáctico), según el escenario; ver el [diccionario de datos](../docs/DICCIONARIO_DATOS.md).
- La primera vez que se abre la página de ML en el escenario realista, el modelo supervisado se entrena con tres datasets de otras semillas. Tarda unos 10 segundos y queda en memoria.
- Los datos se cachean. Después de generar desde la página Generador, la caché se limpia sola.
- Si en disco hay datos de una versión anterior del generador, sin `ground_truth.csv`, se regeneran automáticamente.

## Documentación viva

Cualquier `.md` de la lista de `utils/documentacion.py` (`DOCUMENTOS`) se muestra en la página **Documentación**. Dentro del texto se pueden usar variables con la forma `{{ nombre }}`, por ejemplo `{{ filas.consumo }}` o `{{ hipotesis.tabla }}`: al mostrarlo o descargarlo se reemplazan por los valores de los datos en uso. La vista **🔣 Variables** lista todas las disponibles.

- Para sumar un documento, agregalo a `DOCUMENTOS`.
- Para sumar una variable, agregala en `construir_contexto`.
- Un test verifica que ningún documento quede con variables sin valor.
- La bitácora (`docs/BITACORA.md`) se actualiza a mano: una fila nueva arriba de todo por cada cambio importante, con el motivo.

## Desplegar en Streamlit Community Cloud

1. En https://share.streamlit.io, **Create app** y elegir el repositorio.
2. **Main file path**: `streamlit_app/app.py`.
3. En **Advanced settings**, elegir **Python 3.12**: es la versión con la que se verificaron las dependencias.
4. **Deploy**. Las dependencias se instalan desde `streamlit_app/requirements.txt`.

Tener en cuenta:

- El disco del despliegue se borra en cada reinicio o suspensión. La app regenera el dataset por defecto al volver a abrirse; un dataset generado con otros parámetros se pierde.
- Cada push a la rama desplegada redespliega la app.
- Los errores de instalación o ejecución se ven en **Manage app → Logs**.

## Verificar cambios

```bash
python -m pytest tests/test_streamlit_pages.py
```

Abre cada página sin navegador, partiendo de un disco vacío, y falla si alguna lanza una excepción.
