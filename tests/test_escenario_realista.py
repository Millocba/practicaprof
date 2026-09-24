"""Tests del escenario realista: generador, reglas con contexto, hipótesis y priorización."""
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion import priorizacion
from deteccion.datos import cargar_dataset
from deteccion.hipotesis import HIPOTESIS, contrastar_hipotesis
from deteccion.modelo import ids_con_anomalia_de_comportamiento
from deteccion.reglas import ejecutar_reglas
from generator_pipeline_maestro import (
    CATALOGO_LEGITIMOS,
    PERFILES_VEHICULO,
    TIPOS_POR_ESCENARIO,
    GeneradorMaestro,
)

ARCHIVOS = ["flota", "estaciones", "telemetria", "telemetria_diaria", "consumo", "solicitudes",
            "facturacion", "ground_truth", "casos_legitimos"]


def generar(directorio, seed=42, n_flota=200):
    resultado = GeneradorMaestro(n_flota=n_flota, seed=seed, output_dir=directorio, escenario="realista").ejecutar()
    assert resultado["exito"], resultado.get("error")
    return directorio


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    return cargar_dataset(generar(tmp_path_factory.mktemp("realista")))


@pytest.fixture(scope="module")
def alertas(dataset):
    return ejecutar_reglas(dataset["flota"], dataset["consumo"], dataset["estaciones"], dataset["telemetria_diaria"])


# --- Generador --------------------------------------------------------------

def test_reproducible_con_la_misma_semilla(tmp_path):
    def huella(d):
        return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.glob("*.csv"))}
    a, b = huella(generar(tmp_path / "a", n_flota=60)), huella(generar(tmp_path / "b", n_flota=60))
    assert a == b
    assert set(a) == {f"{n}.csv" for n in ARCHIVOS}


def test_estan_todos_los_tipos_de_anomalia_y_de_caso_legitimo(dataset):
    assert set(dataset["ground_truth"]["tipo_anomalia"]) == set(TIPOS_POR_ESCENARIO["realista"])
    assert set(dataset["casos_legitimos"]["tipo_caso"]) == set(CATALOGO_LEGITIMOS)


def test_etiquetas_referencian_cargas_existentes_y_no_se_superponen(dataset):
    ids = set(dataset["consumo"]["id"])
    anomalas = set(dataset["ground_truth"]["id_registro"])
    legitimas = set(dataset["casos_legitimos"]["id_registro"])
    assert anomalas <= ids and legitimas <= ids
    assert not anomalas & legitimas


def test_prevalencia_de_anomalias_de_comportamiento_es_baja(dataset):
    tasa = len(ids_con_anomalia_de_comportamiento(dataset["ground_truth"])) / len(dataset["consumo"])
    assert 0.003 < tasa < 0.03


def test_cargas_limpias_no_superan_el_tanque(dataset):
    consumo = dataset["consumo"]
    capacidad = consumo["vehiculo_id"].map(dataset["flota"].set_index("Matricula")["CapacidadTanque"])
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    limpias = ~consumo["id"].isin(etiquetadas)
    assert (consumo.loc[limpias, "litros"] <= capacidad[limpias]).all()


def test_rendimiento_de_cargas_limpias_coincide_con_el_perfil_del_vehiculo(dataset):
    consumo, flota = dataset["consumo"].copy(), dataset["flota"]
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    consumo["fecha"] = pd.to_datetime(consumo["fecha"])
    consumo = consumo.sort_values(["vehiculo_id", "fecha", "id"])
    consumo["km"] = consumo.groupby("vehiculo_id")["odometro"].diff()
    limpias = consumo[~consumo["id"].isin(etiquetadas) & consumo["km"].notna()]
    tipo = limpias["vehiculo_id"].map(flota.set_index("Matricula")["TipoVehiculo"])
    mediana = (limpias["km"] / limpias["litros"]).groupby(tipo).median()
    for t, valor in mediana.items():
        minimo, maximo = PERFILES_VEHICULO[t][1]
        assert minimo * 0.8 <= valor <= maximo * 1.2, t


def test_vehiculos_inactivos_solo_cargan_de_forma_anomala(dataset):
    consumo, flota = dataset["consumo"], dataset["flota"]
    inactivos = flota[flota["Estado"] != "EN SERVICIO"].set_index("Matricula")["FechaEstado"]
    desde = pd.to_datetime(consumo["vehiculo_id"].map(inactivos))
    posteriores = set(consumo.loc[pd.to_datetime(consumo["fecha"]) >= desde, "id"])
    gt = dataset["ground_truth"]
    esperadas = set(gt.loc[gt["tipo_anomalia"] == "CARGA_VEHICULO_INACTIVO", "id_registro"])
    duplicados = set(gt.loc[gt["tipo_anomalia"] == "DUPLICADO", "id_registro"])
    assert posteriores - duplicados == esperadas


def test_gps_solo_de_vehiculos_con_dispositivo(dataset):
    assert set(dataset["telemetria_diaria"]["Placa"]) <= set(dataset["telemetria"]["Placa"])
    assert set(dataset["telemetria"]["Placa"]) <= set(dataset["flota"]["Dominio"])
    assert (dataset["telemetria_diaria"]["km_gps"] >= 0).all()


# --- Reglas e hipótesis -----------------------------------------------------

def test_todas_las_reglas_con_contexto_emiten_alertas(alertas):
    assert set(priorizacion.REGLAS_CONTEXTO) <= set(alertas["regla"])


def test_las_hipotesis_se_sostienen(dataset, alertas):
    _, veredictos = contrastar_hipotesis(alertas, dataset["ground_truth"], dataset["casos_legitimos"])
    assert list(veredictos["hipotesis"]) == [h["codigo"] for h in HIPOTESIS]
    assert (veredictos["veredicto"] == "Se sostiene").all(), veredictos[["hipotesis", "f1_ingenua", "f1_contexto"]]


def test_el_contexto_reduce_las_falsas_alarmas_por_casos_legitimos(dataset, alertas):
    _, veredictos = contrastar_hipotesis(alertas, dataset["ground_truth"], dataset["casos_legitimos"])
    assert veredictos["fp_legitimos_contexto"].sum() < veredictos["fp_legitimos_ingenua"].sum() / 5


# --- Priorización -----------------------------------------------------------

@pytest.fixture(scope="module")
def puntajes(dataset):
    variables, etiqueta = priorizacion.datos_de_entrenamiento(semillas=[1001, 1002], n_flota=120)
    modelo = priorizacion.entrenar_supervisado(variables, etiqueta)
    return priorizacion.puntuar(dataset, modelo)


def test_combinado_prioriza_mejor_que_las_reglas_ingenuas(dataset, puntajes):
    curva = priorizacion.curva_de_esfuerzo(puntajes[0], dataset["ground_truth"], dataset["casos_legitimos"], maximo=100)
    en50 = curva[curva["revisadas"] == 50].set_index("metodo")
    assert en50.loc["Combinado", "encontradas"] > en50.loc["Reglas ingenuas", "encontradas"]
    assert en50.loc["Combinado", "legitimos_revisados"] < en50.loc["Reglas ingenuas", "legitimos_revisados"]


def test_la_cola_de_revision_explica_cada_caso(dataset, puntajes):
    pun, variables, alertas_ = puntajes
    cola = priorizacion.cola_de_revision(pun, "Combinado", dataset["consumo"], variables, alertas_, cantidad=20)
    assert len(cola) == 20 and list(cola["prioridad"]) == list(range(1, 21))
    assert (cola["motivos"].str.len() + cola["reglas"].str.len() > 0).all()
