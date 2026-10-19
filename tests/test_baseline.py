"""Evaluación por hipótesis (Sprint 4): línea base ingenua, regla con contexto y modelo baseline."""
import pytest

from deteccion import baseline
from deteccion.modelo import VARIABLES, VARIABLES_CONTEXTO


def test_metricas_con_una_matriz_armada_a_mano():
    real = [True, True, True, False, False, False, False, False]
    predicho = [True, True, False, True, False, False, False, False]
    m = baseline.metricas(real, predicho)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 4)
    assert m["precision"] == pytest.approx(2 / 3) and m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)


def test_metricas_sin_predicciones_ni_positivos_no_dividen_por_cero():
    m = baseline.metricas([False, False], [False, False])
    assert (m["precision"], m["recall"], m["f1"]) == (0.0, 0.0, 0.0)


def test_las_semillas_de_diseno_y_de_evaluacion_no_pueden_compartirse():
    with pytest.raises(ValueError, match="no pueden compartirse"):
        baseline.evaluar("H3b", semillas_de_diseno=[1, 2], semillas_de_evaluacion=[2, 3])


def test_una_hipotesis_desconocida_se_rechaza_con_la_lista():
    with pytest.raises(ValueError, match="H3b"):
        baseline.evaluar("H99")


def test_las_semillas_por_defecto_son_las_del_readme_y_no_se_mezclan_con_el_diseno():
    assert baseline.SEMILLAS_DE_EVALUACION == [42, 7, 123, 2024, 99]
    assert not set(baseline.SEMILLAS_DE_DISENO) & set(baseline.SEMILLAS_DE_EVALUACION)


def test_las_variables_que_definen_la_regla_existen_en_el_modelo():
    """Un error de tipeo en el nombre dejaría pasar justo la variable que hace trampa."""
    conocidas = set(VARIABLES) | set(VARIABLES_CONTEXTO)
    for hipotesis, variables in baseline.VARIABLES_DE_LA_REGLA.items():
        assert set(variables) <= conocidas, hipotesis


def test_evaluar_h3b_compara_todos_los_metodos_con_la_misma_unidad():
    resultado = baseline.evaluar("H3b", semillas_de_diseno=[1001], semillas_de_evaluacion=[42], n_flota=60)
    assert set(resultado["metodos"]) == {
        "linea_base_ingenua", "regla_con_contexto", "isolation_forest",
        "regresion_logistica__todas", "regresion_logistica__sin_las_de_la_regla",
        "random_forest__todas", "random_forest__sin_las_de_la_regla"}
    # Mismo universo de cargas para todos los métodos: la matriz de confusión suma lo mismo
    totales = {sum(m[k] for k in ("tp", "fp", "fn", "tn")) for m in resultado["metodos"].values()}
    assert len(totales) == 1
    # El target es el mismo para todos: las anomalías reales son tp + fn
    reales = {m["tp"] + m["fn"] for m in resultado["metodos"].values()}
    assert reales == {resultado["anomalias_en_evaluacion"]}
    assert resultado["variables_excluidas"] == list(baseline.VARIABLES_DE_LA_REGLA["H3b"])


def test_la_tabla_en_markdown_nombra_cada_metodo():
    resultado = baseline.evaluar("H1", semillas_de_diseno=[1001], semillas_de_evaluacion=[42], n_flota=60)
    tabla = baseline.a_markdown(resultado)
    for etiqueta in baseline.ETIQUETAS.values():
        assert etiqueta in tabla
    assert "Variables excluidas en el segundo escenario: ninguna" in tabla
