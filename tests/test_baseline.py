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


def test_todas_las_hipotesis_por_carga_tienen_su_lista_de_variables_de_la_regla():
    conocidas = set(VARIABLES) | set(VARIABLES_CONTEXTO)
    assert set(baseline.HIPOTESIS_POR_CARGA) <= set(baseline.VARIABLES_DE_LA_REGLA)
    for hipotesis, variables in baseline.VARIABLES_DE_LA_REGLA.items():
        assert set(variables) <= conocidas, hipotesis


def test_excluir_solo_se_puede_pedir_con_una_hipotesis():
    with pytest.raises(ValueError, match="solo se puede usar con una hipótesis"):
        baseline.evaluar_varias(["H1", "H3b"], excluir=["km"])


def test_evaluar_varias_comparte_los_datos_y_devuelve_una_entrada_por_hipotesis():
    resultados = baseline.evaluar_varias(["H1", "H3b"], semillas_de_diseno=[1001], semillas_de_evaluacion=[42],
                                         n_flota=60, n_arboles=20)
    assert list(resultados) == ["H1", "H3b"]
    # Cada hipótesis tiene su propio target y las mismas cargas
    universos = {sum(m[k] for k in ("tp", "fp", "fn", "tn")) for r in resultados.values()
                 for m in r["metodos"].values()}
    assert len(universos) == 1
    assert resultados["H1"]["variables_excluidas"] == []
    assert resultados["H3b"]["variables_excluidas"] == list(baseline.VARIABLES_DE_LA_REGLA["H3b"])
    resumen = baseline.resumen_markdown(resultados)
    assert "| H1 |" in resumen and "| H3b |" in resumen


def test_explicar_informa_las_variables_del_modelo_sin_las_de_la_regla_y_la_ablacion():
    resultado = baseline.explicar("H4", semillas_de_diseno=[1001], semillas_de_evaluacion=[42], n_flota=60,
                                  n_arboles=20)
    usadas = set(resultado["importancia_por_permutacion_del_random_forest"])
    assert usadas.isdisjoint(baseline.VARIABLES_DE_LA_REGLA["H4"])      # las de la regla no entran
    assert usadas == set(resultado["coeficientes_de_la_regresion_logistica"])
    assert set(resultado["f1_del_random_forest_al_quitar_las_mas_importantes"]) == {
        "sin_ninguna", "sin_las_1_mas_importantes", "sin_las_2_mas_importantes", "sin_las_3_mas_importantes"}
    tabla = baseline.explicar_a_markdown(resultado)
    assert "| Variable |" in tabla and "F1 del Random Forest" in tabla


def test_ordenamiento_mide_la_precision_promedio_y_la_precision_en_las_primeras_k():
    real = [True, True, False, False, False]
    perfecto = baseline.ordenamiento(real, [0.9, 0.8, 0.3, 0.2, 0.1])
    assert perfecto["ap"] == pytest.approx(1.0) and perfecto["precision_en_k"] == pytest.approx(1.0)
    peor = baseline.ordenamiento(real, [0.1, 0.2, 0.3, 0.8, 0.9])
    assert peor["precision_en_k"] == 0.0 and peor["ap"] < 0.5
    assert baseline.ordenamiento([False, False], [0.5, 0.4]) == {"ap": 0.0, "precision_en_k": 0.0}

