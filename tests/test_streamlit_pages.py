"""Cada página de la app abre sin excepciones partiendo de un disco vacío, en ambos escenarios.

Reproduce la situación de un despliegue recién reiniciado: no hay datos y la app
debe generarlos por su cuenta.

Qué prueba: la aplicación web hecha con Streamlit (`streamlit_app/`), página por
página y en los dos escenarios ("realista" y "didactico"). Además de que ninguna
página se rompa, revisa algunos contenidos clave: los indicadores de la página
principal, el selector de hipótesis, el diccionario de datos, los veredictos de
las hipótesis y la cola de revisión del modelo.

Por qué importa: es la parte que ve quien usa el proyecto. Un error en una
página solo se notaría al abrirla; estos tests la abren automáticamente con
AppTest (ver comentarios más abajo) y avisan antes de publicar.

Para una explicación general de qué es un test, pytest y un fixture, ver el
docstring de `test_deteccion.py`.
"""
import sys
from pathlib import Path

import pytest
# AppTest es la herramienta de Streamlit para probar páginas sin navegador:
# ejecuta el script de una página y permite leer lo que mostraría (métricas,
# tablas, avisos) y manejar sus controles (selectores, botones, deslizadores).
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parent.parent / "streamlit_app"
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))
import data_loader  # noqa: E402

# Lista de todas las páginas: la principal (app.py) y cada archivo de pages/.
PAGINAS = sorted(["app.py"] + [f"pages/{p.name}" for p in (APP_DIR / "pages").glob("*.py")])
ESCENARIOS = ["realista", "didactico"]


# Fixture con autouse=True: se aplica automáticamente a todos los tests del
# archivo, aunque no lo pidan como parámetro. Redirige las carpetas de datos de
# la app a carpetas temporales vacías, para simular un servidor recién iniciado
# y no tocar los datos reales del proyecto.
# El `yield` divide el fixture en dos: lo de antes se ejecuta al comenzar los
# tests y lo de después (restaurar las carpetas originales) al terminarlos.
@pytest.fixture(scope="module", autouse=True)
def discos_vacios(tmp_path_factory):
    originales = dict(data_loader.DIRECTORIOS)
    for escenario in ESCENARIOS:
        data_loader.DIRECTORIOS[escenario] = tmp_path_factory.mktemp(f"synthetics_{escenario}")
    yield data_loader.DIRECTORIOS
    data_loader.DIRECTORIOS.update(originales)


# Auxiliar: abre una página con el escenario elegido ya cargado en la memoria de
# la sesión (session_state) y la ejecuta. default_timeout está en segundos y es
# amplio porque la primera apertura tiene que generar los datos.
def abrir(pagina, escenario):
    at = AppTest.from_file(str(APP_DIR / pagina), default_timeout=300)
    at.session_state["escenario"] = escenario
    return at.run()


# Dos `parametrize` apilados combinan todos los valores entre sí: se genera un
# test por cada par (página, escenario).
@pytest.mark.parametrize("escenario", ESCENARIOS)
@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_sin_excepciones(pagina, escenario):
    """Cada página abre sin errores en cada escenario.

    Si falla, esa página muestra un error al abrirla; el mensaje incluye el detalle.
    """
    at = abrir(pagina, escenario)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_la_app_genera_los_datos_si_no_existen(discos_vacios, escenario):
    """Al abrir la página principal sin datos, la app genera los archivos necesarios.

    Si falla, un despliegue recién reiniciado quedaría sin datos o con archivos faltantes.
    """
    abrir("app.py", escenario)
    generados = {f.name for f in discos_vacios[escenario].iterdir()}
    assert {"flota.csv", "consumo.csv", "ground_truth.csv", "metadata.json"} <= generados
    if escenario == "realista":
        assert {"casos_legitimos.csv", "estaciones.csv", "telemetria_diaria.csv"} <= generados


def test_la_pagina_principal_muestra_kpis_con_datos():
    """La página principal muestra los indicadores con valores reales (200 vehículos y transacciones).

    Si falla, los indicadores aparecen vacíos ("—") o con cantidades incorrectas.
    """
    at = abrir("app.py", "realista")
    valores = {m.label: m.value for m in at.metric}
    assert valores["Vehículos"] == "200"
    assert valores["Transacciones de consumo"] != "—"


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_analisis_ofrece_cada_hipotesis_del_catalogo_y_todas_abren(escenario):
    """El análisis por hipótesis ofrece todas las del catálogo, y cada una se muestra sin errores y con su título.

    Si falla, falta una hipótesis en el selector o alguna rompe la página al elegirla.
    """
    from deteccion.hipotesis import hipotesis_del_escenario
    at = abrir("pages/05_analisis_por_hipotesis.py", escenario)
    # Simula elegir una opción del control de radio y volver a ejecutar la página.
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
    """La página del diccionario ofrece exactamente las tablas generadas y dibuja un diagrama de relaciones.

    Si falla, el diccionario de la app no coincide con los archivos o falta el diagrama.
    """
    at = abrir("pages/03_diccionario_de_datos.py", escenario)
    tablas = {f.stem for f in discos_vacios[escenario].glob("*.csv")}
    assert {o.split(" — ")[0] for o in at.selectbox(key="tabla_diccionario").options} == tablas
    assert len(at.get("graphviz_chart")) == 1


def test_hipotesis_muestra_un_veredicto_por_hipotesis():
    """La página de hipótesis muestra un veredicto (se sostiene o no) para cada una de las 9 hipótesis.

    Si falla, falta algún veredicto o cambió la cantidad de hipótesis.
    """
    at = abrir("pages/07_hipotesis.py", "realista")
    assert any("Se sostiene" in e.label or "No se sostiene" in e.label for e in at.expander)
    assert len([e for e in at.expander if e.label.startswith(("✅", "❌"))]) == 9


def test_modelo_ml_realista_arma_la_cola_de_revision():
    """La página del modelo arma la cola de revisión con un presupuesto inicial de 50 casos y sus tablas de resultados.

    Si falla, cambió el presupuesto por defecto o faltan métricas o tablas de la cola de revisión.
    """
    at = abrir("pages/08_modelo_ml.py", "realista")
    assert at.slider(key="presupuesto").value == 50
    assert any(m.label.startswith("Encontradas revisando 50") for m in at.metric)
    assert any(m.label == "Facturas con hallazgos" for m in at.metric)
    assert len(at.dataframe) >= 4  # resumen, cola, vehículos y facturas
