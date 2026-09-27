"""Documentación viva: variables, diagramas, descarga y que ningún documento quede con variables sin valor."""
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "streamlit_app" / "utils"))
import documentacion  # noqa: E402
from deteccion.datos import cargar_dataset  # noqa: E402
from deteccion.hipotesis import contrastar_hipotesis  # noqa: E402
from deteccion.reglas import reglas_del_dataset  # noqa: E402
from generator_pipeline_maestro import GeneradorMaestro  # noqa: E402


def test_renderizar_reemplaza_y_avisa_las_desconocidas():
    texto, desconocidas = documentacion.renderizar("Hay {{ a }} y {{b.c}} y {{ nada }}.", {"a": 1, "b.c": "dos"})
    assert texto == "Hay 1 y dos y {{ nada }}."
    assert desconocidas == ["nada"]


def test_mermaid_se_convierte_a_dot():
    bloque = 'flowchart LR\n  a -->|"x (N:1)"| b\n  c -.->|"y"| a\n  class c evaluacion\n'
    dot = documentacion.mermaid_a_dot(bloque)
    assert '"a" -> "b" [label="x (N:1)"]' in dot
    assert '"c" -> "a" [label="y", style=dashed]' in dot
    assert '"c" [fillcolor="#fdf1dc"]' in dot


def test_partes_separa_texto_y_diagramas():
    texto = "antes\n```mermaid\nflowchart LR\n  a --> |\"x\"| b\n```\ndespués"
    tipos = [tipo for tipo, _ in documentacion.partes(texto)]
    assert tipos == ["markdown", "diagrama", "markdown"]


@pytest.fixture(scope="module", params=["realista", "didactico"])
def contexto(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(request.param)
    assert GeneradorMaestro(n_flota=60, seed=42, output_dir=d, escenario=request.param).ejecutar()["exito"]
    datos = cargar_dataset(d)
    veredictos = None
    if datos["casos_legitimos"] is not None:
        alertas = reglas_del_dataset(datos)
        _, veredictos = contrastar_hipotesis(alertas, datos["ground_truth"], datos["casos_legitimos"],
                                             datos["facturacion_detalle"])
    metadata = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    return documentacion.construir_contexto(request.param, datos, metadata, veredictos)


def test_ningun_documento_queda_con_variables_sin_valor(contexto):
    for _, titulo, ruta in documentacion.documentos_disponibles():
        _, desconocidas = documentacion.renderizar(documentacion.leer(ruta), contexto)
        assert not desconocidas, (titulo, desconocidas)


def test_estado_actual_muestra_valores_reales(contexto):
    texto, _ = documentacion.renderizar(documentacion.leer("docs/ESTADO_ACTUAL.md"), contexto)
    assert "{{" not in texto.split("> Documento vivo")[1].split("\n", 1)[1]
    assert f"| consumo | {contexto['filas.consumo']} |" in texto


def test_todos_los_documentos_listados_existen():
    assert len(documentacion.documentos_disponibles()) == len(documentacion.DOCUMENTOS)


def test_el_zip_trae_cada_documento_con_valores(contexto):
    archivo = zipfile.ZipFile(io.BytesIO(documentacion.zip_de_documentos(contexto)))
    assert sorted(archivo.namelist()) == sorted(ruta for _, _, ruta in documentacion.DOCUMENTOS)
    assert "{{ filas.consumo }}" not in archivo.read("docs/ESTADO_ACTUAL.md").decode("utf-8")


def test_las_variables_escritas_como_codigo_no_se_reemplazan():
    texto, desconocidas = documentacion.renderizar("Valor {{ a }}; ejemplo `{{ a }}` y\n```\n{{ b }}\n```", {"a": 7})
    assert texto == "Valor 7; ejemplo `{{ a }}` y\n```\n{{ b }}\n```"
    assert desconocidas == []
