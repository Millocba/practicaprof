"""El diccionario que escribe el generador describe exactamente lo que genera."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from generator_pipeline_maestro import GeneradorMaestro, diagrama_relaciones


@pytest.fixture(scope="module", params=["didactico", "realista"])
def generado(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(request.param)
    assert GeneradorMaestro(n_flota=60, seed=42, output_dir=d, escenario=request.param).ejecutar()["exito"]
    return d, json.loads((d / "diccionario.json").read_text(encoding="utf-8"))


def test_describe_cada_archivo_y_cada_columna_en_orden(generado):
    d, diccionario = generado
    archivos = {f.stem: list(pd.read_csv(f, nrows=1).columns) for f in d.glob("*.csv")}
    assert set(diccionario["tablas"]) == set(archivos)
    for tabla, columnas in archivos.items():
        assert [c["nombre"] for c in diccionario["tablas"][tabla]["columnas"]] == columnas, tabla


def test_cada_columna_tiene_tipo_y_descripcion(generado):
    _, diccionario = generado
    for tabla in diccionario["tablas"].values():
        assert tabla["grano"] and tabla["clave"]
        assert all(c["tipo"] and c["descripcion"] for c in tabla["columnas"])


def test_las_relaciones_usan_tablas_y_columnas_que_existen(generado):
    _, diccionario = generado
    tablas = diccionario["tablas"]
    for r in diccionario["relaciones"]:
        columnas_origen = {c["nombre"] for c in tablas[r["origen"]]["columnas"]}
        assert all(c.strip() in columnas_origen for c in r["columna_origen"].split("+")), r
        for destino in r["destino"].split("/"):
            assert destino.strip() in tablas, r


def test_el_diagrama_incluye_cada_tabla(generado):
    _, diccionario = generado
    dot = diagrama_relaciones(diccionario)
    assert dot.startswith("digraph") and all(f'"{t}"' in dot for t in diccionario["tablas"])
