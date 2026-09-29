"""Documentación viva: variables, diagramas, descarga y que ningún documento quede con variables sin valor.

Qué prueba: el módulo `streamlit_app/utils/documentacion.py`, que toma los
documentos Markdown de `docs/` y reemplaza marcas como `{{ filas.consumo }}` por
valores calculados con los datos generados (por eso se llama documentación
"viva": los números se actualizan solos). También convierte diagramas Mermaid
al formato DOT de Graphviz y arma un ZIP para descargar todos los documentos.

Por qué importa: si una variable queda sin reemplazar, el documento mostraría
texto como `{{ algo }}` en lugar del número; y si el reemplazo toca ejemplos de
código, se romperían las explicaciones.

Para una explicación general de qué es un test, pytest y un fixture, ver el
docstring de `test_deteccion.py`.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "streamlit_app" / "utils"))
# `# noqa: E402` le indica al revisor de estilo que ignore que estos imports no
# están al principio del archivo (tienen que ir después de ajustar `sys.path`).
import documentacion  # noqa: E402
from deteccion.datos import cargar_dataset  # noqa: E402
from deteccion.hipotesis import contrastar_hipotesis  # noqa: E402
from deteccion.reglas import ejecutar_reglas  # noqa: E402
from generator_pipeline_maestro import GeneradorMaestro  # noqa: E402


def test_renderizar_reemplaza_y_avisa_las_desconocidas():
    """Las variables conocidas se reemplazan y las desconocidas quedan intactas y se informan.

    Si falla, el reemplazo de `{{ variable }}` no funciona o esconde variables
    que no tienen valor.
    """
    texto, desconocidas = documentacion.renderizar("Hay {{ a }} y {{b.c}} y {{ nada }}.", {"a": 1, "b.c": "dos"})
    assert texto == "Hay 1 y dos y {{ nada }}."
    assert desconocidas == ["nada"]


def test_mermaid_se_convierte_a_dot():
    """Un diagrama Mermaid se traduce a DOT con flechas, etiquetas, líneas punteadas y colores.

    Si falla, los diagramas de la documentación se verían mal o no se dibujarían en la app.
    """
    bloque = 'flowchart LR\n  a -->|"x (N:1)"| b\n  c -.->|"y"| a\n  class c evaluacion\n'
    dot = documentacion.mermaid_a_dot(bloque)
    assert '"a" -> "b" [label="x (N:1)"]' in dot
    assert '"c" -> "a" [label="y", style=dashed]' in dot
    assert '"c" [fillcolor="#fdf1dc"]' in dot


def test_partes_separa_texto_y_diagramas():
    """Un documento se divide en tramos de texto y de diagrama en el orden correcto.

    Si falla, los diagramas aparecerían como texto crudo o fuera de lugar.
    """
    texto = "antes\n```mermaid\nflowchart LR\n  a --> |\"x\"| b\n```\ndespués"
    tipos = [tipo for tipo, _ in documentacion.partes(texto)]
    assert tipos == ["markdown", "diagrama", "markdown"]


# Fixture que se prepara para cada escenario: genera un dataset chico, corre
# las reglas y el contraste de hipótesis (solo si el escenario tiene casos
# legítimos, es decir, el realista) y arma el diccionario de variables.
@pytest.fixture(scope="module", params=["realista", "didactico"])
def contexto(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(request.param)
    assert GeneradorMaestro(n_flota=60, seed=42, output_dir=d, escenario=request.param).ejecutar()["exito"]
    datos = cargar_dataset(d)
    veredictos = None
    if datos["casos_legitimos"] is not None:
        alertas = ejecutar_reglas(datos["flota"], datos["consumo"], datos["estaciones"], datos["telemetria_diaria"],
                                  datos["solicitudes"], datos["facturacion"], datos["facturacion_detalle"])
        _, veredictos = contrastar_hipotesis(alertas, datos["ground_truth"], datos["casos_legitimos"],
                                             datos["facturacion_detalle"])
    metadata = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    return documentacion.construir_contexto(request.param, datos, metadata, veredictos)


def test_ningun_documento_queda_con_variables_sin_valor(contexto):
    """Todos los documentos publicados tienen valor para cada una de sus variables.

    Si falla, algún documento usa una variable nueva o mal escrita que el
    contexto no calcula (el mensaje dice el documento y la variable).
    """
    for _, titulo, ruta in documentacion.documentos_disponibles():
        _, desconocidas = documentacion.renderizar(documentacion.leer(ruta), contexto)
        assert not desconocidas, (titulo, desconocidas)


def test_estado_actual_muestra_valores_reales(contexto):
    """El documento de estado actual muestra los números calculados, no las marcas `{{ }}`.

    Si falla, la tabla de volúmenes del estado actual no se completa con los datos generados.
    """
    texto, _ = documentacion.renderizar(documentacion.leer("docs/ESTADO_ACTUAL.md"), contexto)
    assert "{{" not in texto.split("> Documento vivo")[1].split("\n", 1)[1]
    assert f"| consumo | {contexto['filas.consumo']} |" in texto


def test_todos_los_documentos_listados_existen():
    """Cada documento de la lista `DOCUMENTOS` existe en disco.

    Si falla, se borró o renombró un archivo de `docs/` sin actualizar la lista.
    """
    assert len(documentacion.documentos_disponibles()) == len(documentacion.DOCUMENTOS)


def test_el_zip_trae_cada_documento_con_valores(contexto):
    """El ZIP de descarga contiene todos los documentos, ya con las variables reemplazadas.

    Si falla, la descarga vendría incompleta o con marcas `{{ }}` sin valor.
    """
    # io.BytesIO permite tratar los bytes en memoria como si fueran un archivo,
    # para abrir el ZIP sin guardarlo en disco.
    archivo = zipfile.ZipFile(io.BytesIO(documentacion.zip_de_documentos(contexto)))
    assert sorted(archivo.namelist()) == sorted(ruta for _, _, ruta in documentacion.DOCUMENTOS)
    assert "{{ filas.consumo }}" not in archivo.read("docs/ESTADO_ACTUAL.md").decode("utf-8")


def test_las_variables_escritas_como_codigo_no_se_reemplazan():
    """Las marcas `{{ }}` dentro de código (entre acentos graves o bloques ```) se dejan como están.

    Si falla, se arruinarían los ejemplos que muestran cómo escribir una variable.
    """
    texto, desconocidas = documentacion.renderizar("Valor {{ a }}; ejemplo `{{ a }}` y\n```\n{{ b }}\n```", {"a": 7})
    assert texto == "Valor 7; ejemplo `{{ a }}` y\n```\n{{ b }}\n```"
    assert desconocidas == []
