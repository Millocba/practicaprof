"""Tests del generador oficial (`generator_pipeline_maestro.py`)."""
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from generator_pipeline_maestro import (
    CATALOGO_ANOMALIAS, COLUMNAS_GROUND_TRUTH, TIPOS_POR_ESCENARIO, GeneradorMaestro,
)

ENTIDADES = ["flota", "telemetria", "consumo", "solicitudes", "facturacion"]
N_FLOTA = 80


def generar(directorio, seed=42):
    resultado = GeneradorMaestro(n_flota=N_FLOTA, seed=seed, output_dir=directorio).ejecutar()
    assert resultado["exito"], resultado.get("error")
    return directorio


def hashes(directorio):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(directorio.glob("*.csv"))}


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    d = generar(tmp_path_factory.mktemp("maestro"))
    tablas = {n: pd.read_csv(d / f"{n}.csv") for n in ENTIDADES}
    tablas["consumo"]["fecha"] = pd.to_datetime(tablas["consumo"]["fecha"])
    tablas["ground_truth"] = pd.read_csv(d / "ground_truth.csv")
    return tablas


def anomalias(datos, tipo):
    gt = datos["ground_truth"]
    return set(gt.loc[gt["tipo_anomalia"] == tipo, "id_registro"])


# --- Reproducibilidad -------------------------------------------------------

def test_misma_semilla_produce_archivos_identicos(tmp_path):
    a = hashes(generar(tmp_path / "a"))
    b = hashes(generar(tmp_path / "b"))
    assert a == b
    assert set(a) == {f"{n}.csv" for n in ENTIDADES} | {"ground_truth.csv"}


def test_otra_semilla_produce_datos_distintos(tmp_path):
    assert hashes(generar(tmp_path / "a", seed=42)) != hashes(generar(tmp_path / "b", seed=7))


# --- Esquema e integridad ---------------------------------------------------

def test_volumenes(datos):
    assert len(datos["flota"]) == N_FLOTA
    assert len(datos["telemetria"]) == int(N_FLOTA * 0.88)
    assert len(datos["consumo"]) >= N_FLOTA * 5


def test_ids_unicos(datos):
    assert datos["flota"]["Matricula"].is_unique
    assert datos["flota"]["Dominio"].is_unique
    assert datos["consumo"]["id"].is_unique
    assert datos["solicitudes"]["id"].is_unique


def test_claves_foraneas(datos):
    matriculas = set(datos["flota"]["Matricula"])
    dominios = set(datos["flota"]["Dominio"])
    assert set(datos["consumo"]["vehiculo_id"]) <= matriculas
    assert set(datos["solicitudes"]["vehiculo_id"]) <= matriculas
    assert set(datos["telemetria"]["Placa"]) <= dominios


def test_facturacion_suma_el_consumo_de_cada_periodo(datos):
    consumo = datos["consumo"]
    por_mes = consumo.groupby(consumo["fecha"].dt.to_period("M").astype(str))
    fact = datos["facturacion"].set_index("periodo")
    assert set(fact.index) == set(por_mes.groups)
    for periodo, grupo in por_mes:
        assert fact.loc[periodo, "numero_transacciones"] == len(grupo)
        assert fact.loc[periodo, "total_monto"] == pytest.approx(grupo["importe_total"].sum())


# --- Ground truth -----------------------------------------------------------

def test_ground_truth_tiene_el_esquema_y_catalogo_esperados(datos):
    gt = datos["ground_truth"]
    assert list(gt.columns) == COLUMNAS_GROUND_TRUTH
    assert set(gt["tipo_anomalia"]) == set(TIPOS_POR_ESCENARIO["didactico"])
    for tipo in TIPOS_POR_ESCENARIO["didactico"]:
        hipotesis, severidad = CATALOGO_ANOMALIAS[tipo]
        filas = gt[gt["tipo_anomalia"] == tipo]
        assert (filas["hipotesis"] == hipotesis).all()
        assert (filas["severidad"] == severidad).all()


def test_ground_truth_referencia_registros_existentes(datos):
    gt = datos["ground_truth"]
    consumo = datos["consumo"].set_index("id")
    assert gt["id_registro"].isin(consumo.index).all()
    assert (consumo.loc[gt["id_registro"], "vehiculo_id"].values == gt["vehiculo_id"].values).all()


def test_exceso_volumetrico_coincide_con_la_capacidad(datos):
    capacidad = datos["flota"].set_index("Matricula")["CapacidadTanque"]
    consumo = datos["consumo"].assign(capacidad=lambda d: d["vehiculo_id"].map(capacidad))
    etiquetadas = consumo["id"].isin(anomalias(datos, "EXCESO_VOLUMETRICO"))
    assert (consumo.loc[etiquetadas, "litros"] > consumo.loc[etiquetadas, "capacidad"]).all()
    assert (consumo.loc[~etiquetadas, "litros"] <= consumo.loc[~etiquetadas, "capacidad"]).all()


def _cambios_de_odometro(datos):
    duplicados = anomalias(datos, "DUPLICADO")
    consumo = datos["consumo"][~datos["consumo"]["id"].isin(duplicados)]
    consumo = consumo.sort_values(["vehiculo_id", "fecha", "id"])
    return consumo.assign(cambio=consumo.groupby("vehiculo_id")["odometro"].diff())


def test_todo_retroceso_de_odometro_esta_etiquetado(datos):
    cambios = _cambios_de_odometro(datos)
    assert set(cambios.loc[cambios["cambio"] < 0, "id"]) == anomalias(datos, "ODOMETRO_REGRESIVO")


def test_saltos_de_odometro_etiquetados_superan_el_uso_normal(datos):
    cambios = _cambios_de_odometro(datos).set_index("id")
    saltos = anomalias(datos, "ODOMETRO_SALTO")
    assert saltos
    assert (cambios.loc[list(saltos), "cambio"] >= 1500).all()


def test_todo_dominio_sin_vinculo_esta_etiquetado(datos):
    consumo = datos["consumo"]
    sin_vinculo = set(consumo.loc[~consumo["dominio"].isin(datos["flota"]["Dominio"]), "id"])
    assert sin_vinculo == anomalias(datos, "DOMINIO_INVALIDO")


def test_todo_valor_nulo_esta_etiquetado(datos):
    gt = datos["ground_truth"]
    nulos_gt = set(zip(gt.loc[gt["tipo_anomalia"] == "VALOR_NULO", "id_registro"],
                       gt.loc[gt["tipo_anomalia"] == "VALOR_NULO", "columna"]))
    consumo = datos["consumo"]
    nulos = {(i, col) for col in ["estacion", "conductor", "odometro"]
             for i in consumo.loc[consumo[col].isna(), "id"]}
    assert nulos == nulos_gt


def test_los_datos_no_incluyen_la_etiqueta(datos):
    for nombre in ENTIDADES:
        assert not any("anomal" in c.lower() for c in datos[nombre].columns), nombre
