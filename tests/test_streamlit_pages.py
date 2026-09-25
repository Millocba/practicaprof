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
def test_analisis_tiene_una_pestana_por_hipotesis_del_catalogo(escenario):
    from deteccion.hipotesis import hipotesis_del_escenario
    at = abrir("pages/05_analisis_por_hipotesis.py", escenario)
    codigos = [t.label.split(" · ")[0] for t in at.tabs][2:]
    assert codigos == [h["codigo"] for h in hipotesis_del_escenario(escenario)]


def test_hipotesis_muestra_un_veredicto_por_hipotesis():
    at = abrir("pages/07_hipotesis.py", "realista")
    assert any("Se sostiene" in e.label or "No se sostiene" in e.label for e in at.expander)
    assert len([e for e in at.expander if e.label.startswith(("✅", "❌"))]) == 9


def test_modelo_ml_realista_arma_la_cola_de_revision():
    at = abrir("pages/08_modelo_ml.py", "realista")
    assert at.slider(key="presupuesto").value == 50
    assert any(m.label.startswith("Encontradas revisando 50") for m in at.metric)
    assert any(m.label == "Facturas con hallazgos" for m in at.metric)
    assert len(at.dataframe) >= 4  # resumen, cola, vehículos y facturas
