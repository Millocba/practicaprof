"""El diccionario que escribe el generador describe exactamente lo que genera.

Qué prueba: el archivo `diccionario.json` que el generador
(`generator_pipeline_maestro.py`) escribe junto a los CSV. Ese diccionario
explica cada tabla y cada columna, y las relaciones entre tablas; la app lo
muestra en la página del diccionario de datos.

Por qué importa: si el diccionario no coincide con los datos (una columna que
falta, una relación hacia una tabla que no existe), quien lea la documentación
sacaría conclusiones equivocadas sobre los datos.

Para una explicación general de qué es un test, pytest y un fixture, ver el
docstring de `test_deteccion.py`.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from generator_pipeline_maestro import GeneradorMaestro, diagrama_relaciones


# Fixture parametrizado: con `params` el fixture se prepara una vez por cada
# escenario ("didactico" y "realista"), y cada test que lo usa se ejecuta dos
# veces, una con cada escenario. `request.param` indica cuál toca en cada vuelta.
@pytest.fixture(scope="module", params=["didactico", "realista"])
def generado(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(request.param)
    assert GeneradorMaestro(n_flota=60, seed=42, output_dir=d, escenario=request.param).ejecutar()["exito"]
    return d, json.loads((d / "diccionario.json").read_text(encoding="utf-8"))


def test_describe_cada_archivo_y_cada_columna_en_orden(generado):
    """El diccionario lista exactamente los CSV generados y sus columnas, en el mismo orden.

    Si falla, se agregó, quitó o reordenó una columna o tabla en el generador
    sin actualizar el diccionario.
    """
    d, diccionario = generado
    archivos = {f.stem: list(pd.read_csv(f, nrows=1).columns) for f in d.glob("*.csv")}
    assert set(diccionario["tablas"]) == set(archivos)
    for tabla, columnas in archivos.items():
        assert [c["nombre"] for c in diccionario["tablas"][tabla]["columnas"]] == columnas, tabla


def test_cada_columna_tiene_tipo_y_descripcion(generado):
    """Cada tabla declara su grano y su clave, y cada columna su tipo y descripción.

    Si falla, hay una tabla o columna documentada a medias (campos vacíos).
    """
    _, diccionario = generado
    for tabla in diccionario["tablas"].values():
        assert tabla["grano"] and tabla["clave"]
        assert all(c["tipo"] and c["descripcion"] for c in tabla["columnas"])


def test_las_relaciones_usan_tablas_y_columnas_que_existen(generado):
    """Cada relación declarada apunta a columnas y tablas que existen en el diccionario.

    Si falla, hay una relación con un nombre mal escrito o hacia una tabla eliminada.
    """
    _, diccionario = generado
    tablas = diccionario["tablas"]
    for r in diccionario["relaciones"]:
        columnas_origen = {c["nombre"] for c in tablas[r["origen"]]["columnas"]}
        assert all(c.strip() in columnas_origen for c in r["columna_origen"].split("+")), r
        for destino in r["destino"].split("/"):
            assert destino.strip() in tablas, r


def test_el_diagrama_incluye_cada_tabla(generado):
    """El diagrama de relaciones (formato DOT de Graphviz) dibuja todas las tablas.

    Si falla, el diagrama que muestra la app quedaría incompleto o mal formado.
    """
    _, diccionario = generado
    dot = diagrama_relaciones(diccionario)
    assert dot.startswith("digraph") and all(f'"{t}"' in dot for t in diccionario["tablas"])
