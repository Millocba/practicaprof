"""Tests de la detección por reglas y de la evaluación contra el ground truth.

Qué prueba este archivo
-----------------------
Dos piezas centrales del proyecto:

1. La evaluación (`deteccion/evaluacion.py`): las cuentas que dicen qué tan bien
   detecta un método. Se comparan las alertas emitidas contra el "ground truth"
   (la lista de anomalías que el generador inyectó a propósito y que, por eso,
   sabemos que existen). De ahí salen los verdaderos positivos (tp: alertas
   correctas), falsos positivos (fp: alertas sobre registros sanos), falsos
   negativos (fn: anomalías que nadie alertó), la precisión, el recall y el F1.
2. Las reglas (`deteccion/reglas.py`): los controles que revisan los datos de
   flota y consumo y emiten alertas.

Por qué importa: si las métricas estuvieran mal calculadas, todas las
conclusiones del proyecto ("esta regla detecta el 100 %", "el modelo es mejor
que el azar") serían falsas aunque el resto del código funcionara.

Guía rápida para quien nunca usó tests
--------------------------------------
- Un *test* es una función pequeña que ejecuta una parte del programa con datos
  conocidos y verifica que el resultado sea el esperado. La verificación se
  escribe con `assert condición`: si la condición es falsa, el test "falla" y
  avisa que algo se rompió. Así, cada vez que se cambia el código, se puede
  comprobar en segundos que lo que ya funcionaba sigue funcionando.
- *pytest* es la herramienta que busca y ejecuta los tests. Encuentra solo los
  archivos cuyo nombre empieza con `test_` y, dentro de ellos, las funciones
  que empiezan con `test_`. Al final muestra cuántos pasaron y cuáles fallaron.
- Un *fixture* es una función marcada con `@pytest.fixture` que prepara algo que
  varios tests necesitan (por ejemplo, un conjunto de datos generado). Un test
  lo pide simplemente escribiendo el nombre del fixture como parámetro; pytest
  lo ejecuta y le pasa el resultado.
- Cómo se corren, desde la carpeta raíz del proyecto y con el entorno virtual:
      python -m pytest                   (todos los tests)
      python -m pytest tests/test_deteccion.py   (solo este archivo)
      python -m pytest -q                (salida resumida)
      python -m pytest -k metricas       (solo los tests cuyo nombre contiene "metricas")
"""
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

# Agrega la carpeta raíz del proyecto a la lista de lugares donde Python busca
# módulos, para poder importar `deteccion` y el generador desde esta subcarpeta.
sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion.evaluacion import evaluar_binario, evaluar_por_regla, evaluar_por_tipo
from deteccion.reglas import ejecutar_reglas, secuencia_odometro
from generator_pipeline_maestro import GeneradorMaestro


# --- Métricas (casos calculados a mano) -------------------------------------

# Funciones auxiliares (no son tests: no empiezan con `test_`). Arman tablas
# mínimas de ground truth y de alertas para poder escribir casos a mano.
def gt(*pares):
    return pd.DataFrame([{"id_registro": i, "tipo_anomalia": t, "columna": "x"} for i, t in pares])


def alertas(*ternas):
    return pd.DataFrame([{"id_registro": i, "tipo_anomalia": t, "regla": r, "detalle": ""}
                         for i, t, r in ternas])


def test_metricas_por_tipo():
    """Comprueba tp, fp, fn, precisión, recall y F1 en un caso calculado a mano.

    Si falla, las fórmulas de las métricas por tipo de anomalía están mal y
    todos los resultados de evaluación del proyecto serían incorrectos.
    """
    verdad = gt(("a", "T"), ("b", "T"), ("c", "T"), ("d", "U"))
    pred = alertas(("a", "T", "r1"), ("b", "T", "r1"), ("z", "T", "r1"))
    fila = evaluar_por_tipo(pred, verdad).set_index("tipo_anomalia").loc["T"]
    assert (fila.tp, fila.fp, fila.fn) == (2, 1, 1)
    # pytest.approx compara números decimales con una pequeña tolerancia, porque
    # 2/3 no se puede representar exactamente en la computadora.
    assert fila.precision == pytest.approx(2 / 3)
    assert fila.recall == pytest.approx(2 / 3)
    assert fila.f1 == pytest.approx(2 / 3)


def test_tipo_sin_alertas_tiene_recall_cero_y_precision_indefinida():
    """Un tipo de anomalía que nadie alertó debe tener recall 0 y precisión NaN.

    Si falla, un tipo nunca detectado podría aparecer con una precisión
    inventada (por ejemplo 0 o 1) o hacer que el cálculo se rompa por dividir por cero.
    """
    fila = evaluar_por_tipo(alertas(("a", "T", "r1")), gt(("a", "T"), ("d", "U"))).set_index(
        "tipo_anomalia").loc["U"]
    assert (fila.tp, fila.fn, fila.recall, fila.f1) == (0, 1, 0.0, 0.0)
    assert math.isnan(fila.precision)


def test_un_acierto_requiere_el_mismo_tipo():
    """Alertar el registro correcto pero con otro tipo de anomalía no cuenta como acierto.

    Si falla, la evaluación premiaría alertas que señalan el problema equivocado.
    """
    fila = evaluar_por_tipo(alertas(("a", "U", "r1")), gt(("a", "T"))).set_index("tipo_anomalia")
    assert fila.loc["T", "fn"] == 1 and fila.loc["U", "fp"] == 1


def test_varias_reglas_del_mismo_tipo_se_evaluan_por_separado():
    """Cada regla se mide por su cuenta, y al agrupar por tipo cada anomalía se cuenta una sola vez.

    Si falla, dos reglas que encuentran la misma anomalía la contarían doble e
    inflarían los resultados.
    """
    verdad = gt(("a", "T"), ("b", "T"))
    pred = alertas(("a", "T", "r1"), ("a", "T", "r2"), ("b", "T", "r2"))
    por_regla = evaluar_por_regla(pred, verdad).set_index("regla")
    assert por_regla.loc["r1", "recall"] == 0.5
    assert por_regla.loc["r2", "recall"] == 1.0
    assert evaluar_por_tipo(pred, verdad).iloc[0].tp == 2  # la unión cuenta una vez cada anomalía


def test_evaluacion_binaria():
    """Comprueba la matriz de confusión (tp, fp, fn, tn) de la evaluación "anómalo sí/no".

    Si falla, están mal contados los aciertos o los registros sanos (tn) sobre
    el total de registros.
    """
    m = evaluar_binario(ids_alertados={"a", "b", "c"}, ids_anomalos={"a", "b", "d"}, universo="abcdefgh")
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 4)


# --- Reglas -----------------------------------------------------------------

def test_secuencia_de_odometro_salta_lecturas_vacias():
    """Los km recorridos se calculan contra la última lectura de odómetro válida, saltando las vacías.

    Si falla, una lectura faltante cortaría la secuencia y dejaría sin detectar
    un odómetro que retrocede.
    """
    consumo = pd.DataFrame({
        "id": ["c1", "c2", "c3"],
        "vehiculo_id": ["V1"] * 3,
        "fecha": ["2024-01-01", "2024-01-05", "2024-01-10"],
        "odometro": [1000, None, 800],
    })
    seq = secuencia_odometro(consumo).set_index("id")
    assert seq.loc["c3", "km"] == -200  # se compara con c1, la última lectura válida


# Fixture: prepara datos que usan varios tests de abajo.
# - scope="module" hace que se ejecute una sola vez para todo este archivo (y no
#   una vez por test), porque generar el dataset lleva tiempo.
# - `tmp_path_factory` es un fixture que trae pytest: crea carpetas temporales
#   que se borran solas, así los tests no ensucian las carpetas del proyecto.
@pytest.fixture(scope="module")
def evaluacion(tmp_path_factory):
    d = tmp_path_factory.mktemp("maestro")
    assert GeneradorMaestro(n_flota=200, seed=42, output_dir=d).ejecutar()["exito"]
    flota, consumo, verdad = (pd.read_csv(d / f) for f in ["flota.csv", "consumo.csv", "ground_truth.csv"])
    return evaluar_por_regla(ejecutar_reglas(flota, consumo), verdad).set_index("regla")


# `parametrize` repite el mismo test una vez por cada valor de la lista: acá se
# generan 8 tests, uno por regla, y si falla uno solo el reporte dice cuál.
@pytest.mark.parametrize("regla", [
    "duplicado_exacto", "nulo_estacion", "nulo_conductor", "nulo_odometro",
    "dominio_sin_vinculo", "litros_mayor_a_tanque", "odometro_disminuye",
    "salto_historial_vehiculo",
])
def test_reglas_detectan_todas_sus_anomalias_sin_falsos_positivos(evaluacion, regla):
    """Cada regla determinística encuentra todas sus anomalías (recall 1) sin alertas falsas (precisión 1).

    Si falla, la regla o el generador cambiaron: la regla deja pasar anomalías,
    alerta registros sanos, o no hay anomalías de ese tipo en los datos.
    """
    fila = evaluacion.loc[regla]
    assert fila.reales > 0
    assert (fila.precision, fila.recall) == (1.0, 1.0)


def test_historial_del_vehiculo_supera_al_umbral_fijo_en_saltos(evaluacion):
    """Comparar con el historial de cada vehículo detecta más saltos de odómetro que un umbral fijo.

    Si falla, se perdió la ventaja que justifica usar el historial por vehículo.
    """
    assert evaluacion.loc["salto_historial_vehiculo", "recall"] > evaluacion.loc["salto_umbral_fijo", "recall"]
