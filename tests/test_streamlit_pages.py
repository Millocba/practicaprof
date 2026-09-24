"""Cada página de la app abre sin excepciones partiendo de un disco vacío.

Reproduce la situación de un despliegue recién reiniciado: no hay datos y la app
debe generarlos por su cuenta.
"""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parent.parent / "streamlit_app"
sys.path.insert(0, str(APP_DIR / "utils"))
import data_loader  # noqa: E402

PAGINAS = sorted(["app.py"] + [f"pages/{p.name}" for p in (APP_DIR / "pages").glob("*.py")])


@pytest.fixture(scope="module", autouse=True)
def disco_vacio(tmp_path_factory):
    original = data_loader.SYNTHETICS_DIR
    data_loader.SYNTHETICS_DIR = tmp_path_factory.mktemp("synthetics_maestro")
    yield data_loader.SYNTHETICS_DIR
    data_loader.SYNTHETICS_DIR = original


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_sin_excepciones(pagina):
    at = AppTest.from_file(str(APP_DIR / pagina), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]


def test_la_app_genera_los_datos_si_no_existen(disco_vacio):
    AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=120).run()
    generados = {f.name for f in disco_vacio.iterdir()}
    assert {"flota.csv", "consumo.csv", "ground_truth.csv", "metadata.json"} <= generados


def test_la_pagina_principal_muestra_kpis_con_datos():
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=120).run()
    valores = {m.label: m.value for m in at.metric}
    assert valores["Vehículos"] == "200"
    assert valores["Transacciones de consumo"] != "—"
