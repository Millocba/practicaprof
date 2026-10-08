"""Observaciones de las alertas (#36): la corrección se documenta y el dato de origen no se altera."""
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion import priorizacion
from deteccion.datos import cargar_dataset
from deteccion.reglas import asignar_observacion, reglas_del_dataset
from generator_pipeline_maestro import (
    COLUMNAS_OBSERVACIONES,
    ERRORES_DE_CARGA,
    REGLA_DE_ANOMALIA,
    RESULTADOS_OBSERVACION,
    TABLAS_DE_FACTURACION,
    GeneradorMaestro,
)


def generar(directorio, escenario="realista", seed=42, n_flota=200):
    resultado = GeneradorMaestro(n_flota=n_flota, seed=seed, output_dir=directorio, escenario=escenario).ejecutar()
    assert resultado["exito"], resultado.get("error")
    return directorio


def huellas(directorio):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(Path(directorio).glob("*.csv"))}


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    return cargar_dataset(generar(tmp_path_factory.mktemp("obs")))


@pytest.fixture(scope="module")
def alertas(dataset):
    return reglas_del_dataset(dataset)


def test_las_fuentes_son_iguales_con_y_sin_observaciones(tmp_path, monkeypatch):
    con = huellas(generar(tmp_path / "con", n_flota=60))
    monkeypatch.setattr(GeneradorMaestro, "aplicar_observaciones", lambda self: None)
    sin = huellas(generar(tmp_path / "sin", n_flota=60))
    assert set(con) - set(sin) == {"observaciones_alertas.csv"}
    assert {k: v for k, v in con.items() if k != "observaciones_alertas.csv"} == sin


def test_el_escenario_didactico_no_tiene_observaciones(tmp_path):
    assert "observaciones_alertas.csv" not in huellas(generar(tmp_path, escenario="didactico", n_flota=60))


def test_reproducible_con_la_misma_semilla(tmp_path):
    assert huellas(generar(tmp_path / "a", n_flota=60)) == huellas(generar(tmp_path / "b", n_flota=60))


def test_la_tabla_tiene_las_columnas_y_resultados_declarados(dataset):
    obs = dataset["observaciones_alertas"]
    assert list(obs.columns) == COLUMNAS_OBSERVACIONES
    assert obs["id"].is_unique and obs["observacion"].notna().all()
    assert set(obs["resultado"]) <= set(RESULTADOS_OBSERVACION)
    assert not (obs["resultado"] == "pendiente").any()      # lo no investigado no tiene fila


def test_cada_observacion_documenta_un_registro_etiquetado_y_una_alerta_que_existe(dataset, alertas):
    obs, gt = dataset["observaciones_alertas"], dataset["ground_truth"]
    assert set(zip(obs["tabla"], obs["id_registro"])) <= set(zip(gt["tabla"], gt["id_registro"]))
    emitidas = set(zip(alertas["id_registro"], alertas["regla"]))
    faltan = [(i, r) for i, r in zip(obs["id_registro"], obs["regla"]) if (i, r) not in emitidas]
    # El pedido de un ERROR_PROVEEDOR no alerta; ese caso no se documenta
    assert not faltan, faltan[:5]


def test_las_reglas_del_mapa_existen(alertas):
    reglas = set(alertas["regla"])
    assert {r for r in REGLA_DE_ANOMALIA.values()} <= reglas


def test_resultados_segun_el_tipo_de_registro(dataset):
    obs = dataset["observaciones_alertas"]
    tipos = dataset["ground_truth"].groupby(["tabla", "id_registro"])["tipo_anomalia"].agg(set)
    for fila in obs.itertuples():
        tipo = tipos[(fila.tabla, fila.id_registro)]
        if tipo & set(ERRORES_DE_CARGA):
            assert fila.resultado == "error_humano"
        elif fila.tabla in TABLAS_DE_FACTURACION:
            assert fila.resultado == "facturacion_del_proveedor"
        else:
            assert fila.resultado == "faltante"
    assert 0 < (obs["resultado"] == "error_humano").sum() and (obs["resultado"] == "faltante").sum() > 0


def test_el_error_de_carga_sigue_visible_en_las_fuentes(dataset):
    """Documentar no corrige: la carga de un error documentado sigue sin su pedido en el cruce."""
    obs = dataset["observaciones_alertas"]
    documentados = obs[obs["resultado"] == "error_humano"]["id_registro"]
    assert documentados.isin(dataset["ground_truth"]["id_registro"]).all()


def test_una_alerta_documentada_sigue_en_los_conteos(dataset, alertas):
    sin = reglas_del_dataset({**dataset, "observaciones_alertas": None})
    assert len(alertas) == len(sin)
    assert alertas["documentada"].sum() > 0
    assert alertas.loc[alertas["documentada"], "resultado_observacion"].notna().all()
    assert "observacion" not in alertas.columns
    assert list(alertas[["id_registro", "regla"]].itertuples(index=False)) == \
        list(sin[["id_registro", "regla"]].itertuples(index=False))


def test_pendiente_equivale_a_no_investigada():
    alertas = pd.DataFrame({"id_registro": ["A", "B"], "tipo_anomalia": "X", "regla": "r", "detalle": ""})
    obs = pd.DataFrame({"id_registro": ["A", "B"], "regla": ["r", "r"], "resultado": ["faltante", "pendiente"]})
    r = asignar_observacion(alertas, obs)
    assert list(r["documentada"]) == [True, False]
    assert r["resultado_observacion"].tolist()[0] == "faltante" and pd.isna(r["resultado_observacion"].iloc[1])


def test_en_la_cola_van_primero_las_no_investigadas_y_la_documentada_sigue_ahi(dataset, alertas):
    variables, _ = priorizacion._variables_y_reglas(dataset)
    documentadas = priorizacion.cargas_documentadas(alertas) & set(variables.index)
    explicadas = priorizacion.cargas_explicadas(alertas)
    assert documentadas
    # Las documentadas tienen el puntaje más alto: sin la regla de la cola irían primero
    puntajes = pd.DataFrame({"Combinado": [10.0 if i in documentadas else 1.0 for i in variables.index]},
                            index=variables.index)
    cola = priorizacion.cola_de_revision(puntajes, "Combinado", dataset["consumo"], variables, alertas,
                                         cantidad=len(variables))
    posicion = cola.set_index("id")["prioridad"]
    sin_investigar = [i for i in variables.index if i not in documentadas and i not in explicadas]
    assert posicion[list(documentadas)].min() > posicion[sin_investigar].max()
    assert (cola.loc[cola["id"].isin(documentadas), "documentada"] != "").all()
    assert set(documentadas) <= set(cola["id"])
