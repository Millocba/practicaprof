"""Cada página de la app abre sin excepciones partiendo de un disco vacío, en ambos escenarios.

Reproduce la situación de un despliegue recién reiniciado: no hay datos y la app
debe generarlos por su cuenta.
"""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parent.parent / "streamlit_app"
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))
import data_loader  # noqa: E402

PAGINAS = sorted(["app.py"] + [f"pages/{p.name}" for p in (APP_DIR / "pages").glob("*.py")])
ESCENARIOS = ["realista", "didactico"]


@pytest.fixture(scope="module", autouse=True)
def discos_vacios(tmp_path_factory):
    originales = dict(data_loader.DIRECTORIOS)
    for escenario in ESCENARIOS:
        data_loader.DIRECTORIOS[escenario] = tmp_path_factory.mktemp(f"synthetics_{escenario}")
    yield data_loader.DIRECTORIOS
    data_loader.DIRECTORIOS.update(originales)


def abrir(pagina, escenario):
    at = AppTest.from_file(str(APP_DIR / pagina), default_timeout=300)
    at.session_state["escenario"] = escenario
    return at.run()


@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_sin_excepciones(pagina, escenario):
    at = abrir(pagina, escenario)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_la_app_genera_los_datos_si_no_existen(discos_vacios, escenario):
    abrir("app.py", escenario)
    generados = {f.name for f in discos_vacios[escenario].iterdir()}
    assert {"flota.csv", "consumo.csv", "ground_truth.csv", "metadata.json"} <= generados
    if escenario == "realista":
        assert {"casos_legitimos.csv", "estaciones.csv", "telemetria_diaria.csv"} <= generados


def test_la_pagina_principal_muestra_kpis_con_datos():
    at = abrir("app.py", "realista")
    valores = {m.label: m.value for m in at.metric}
    assert valores["Vehículos"] == "200"
    assert valores["Transacciones de consumo"] != "—"


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_analisis_ofrece_cada_hipotesis_del_catalogo_y_todas_abren(escenario):
    from deteccion.hipotesis import hipotesis_del_escenario
    at = abrir("pages/05_analisis_por_hipotesis.py", escenario)
    at.radio(key="vista_analisis").set_value("🔍 Por hipótesis").run()
    selector = at.selectbox(key="hipotesis_analisis")
    codigos = [h["codigo"] for h in hipotesis_del_escenario(escenario)]
    assert list(selector.options) == [f"{c} · {h['titulo']}" for c, h in
                                      zip(codigos, hipotesis_del_escenario(escenario))]
    for codigo in codigos:
        at.selectbox(key="hipotesis_analisis").set_value(codigo).run()
        assert not at.exception, (codigo, [e.value for e in at.exception])
        assert at.markdown[0] is not None and any(m.value.startswith(f"## {codigo} ") for m in at.markdown)


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_diccionario_describe_cada_tabla_generada(escenario, discos_vacios):
    at = abrir("pages/03_diccionario_de_datos.py", escenario)
    tablas = {f.stem for f in discos_vacios[escenario].glob("*.csv")}
    assert {o.split(" — ")[0] for o in at.selectbox(key="tabla_diccionario").options} == tablas
    assert len(at.get("graphviz_chart")) == 1


def test_hipotesis_muestra_un_veredicto_por_hipotesis():
    at = abrir("pages/07_hipotesis.py", "realista")
    assert any("Se sostiene" in e.label or "No se sostiene" in e.label for e in at.expander)
    assert len([e for e in at.expander if e.label.startswith(("✅", "❌"))]) == 10  # H1 a H9, con H2b, H2c y H3b


def test_modelo_ml_realista_arma_la_cola_de_revision():
    at = abrir("pages/08_modelo_ml.py", "realista")
    assert at.slider(key="presupuesto").value == 50
    assert any(m.label.startswith("Encontradas revisando 50") for m in at.metric)
    assert any(m.label == "Facturas con hallazgos" for m in at.metric)
    assert len(at.dataframe) >= 4  # resumen, cola, vehículos y facturas
