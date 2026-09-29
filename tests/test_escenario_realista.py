"""Tests del escenario realista: generador, reglas con contexto, hipótesis y priorización.

Qué prueba: el escenario "realista" completo, que es el más cercano a una
auditoría de verdad (siempre con datos sintéticos). Se revisa en cuatro bloques:

- Generador: que los datos sean reproducibles y coherentes (cargas dentro del
  tanque, rendimientos creíbles, GPS solo en vehículos con dispositivo).
- Circuito solicitud -> carga -> factura: que cada carga sana tenga su
  autorización previa y que cada factura sume sus líneas, salvo las anomalías
  inyectadas a propósito.
- Reglas e hipótesis: que las reglas que usan contexto (por ejemplo, casos
  legítimos conocidos) generen menos falsas alarmas que las reglas "ingenuas".
- Priorización: que el método combinado ordene los casos de modo que quien
  audita encuentre más anomalías revisando menos registros.

Por qué importa: estas pruebas sostienen las afirmaciones principales del
proyecto. Si el generador produjera datos incoherentes, las hipótesis se
"sostendrían" o no por un error y no por el método.

Para una explicación general de qué es un test, pytest y un fixture, ver el
docstring de `test_deteccion.py`.
"""
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
            "facturacion", "facturacion_detalle", "ground_truth", "casos_legitimos"]


def generar(directorio, seed=42, n_flota=200):
    resultado = GeneradorMaestro(n_flota=n_flota, seed=seed, output_dir=directorio, escenario="realista").ejecutar()
    assert resultado["exito"], resultado.get("error")
    return directorio


# Los fixtures pueden depender de otros fixtures: `alertas` recibe `dataset`,
# así que pytest primero genera el dataset y después corre las reglas sobre él.
# Con scope="module" ambos se calculan una sola vez para todo el archivo.
@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    return cargar_dataset(generar(tmp_path_factory.mktemp("realista")))


@pytest.fixture(scope="module")
def alertas(dataset):
    return ejecutar_reglas(dataset["flota"], dataset["consumo"], dataset["estaciones"], dataset["telemetria_diaria"],
                           dataset["solicitudes"], dataset["facturacion"], dataset["facturacion_detalle"])


def _contraste(dataset, alertas):
    return contrastar_hipotesis(alertas, dataset["ground_truth"], dataset["casos_legitimos"],
                                dataset["facturacion_detalle"])


# --- Generador --------------------------------------------------------------

# `tmp_path` es un fixture de pytest que le da a este test su propia carpeta
# temporal, vacía y exclusiva, que se descarta al terminar.
def test_reproducible_con_la_misma_semilla(tmp_path):
    """Dos generaciones con la misma semilla producen archivos idénticos byte a byte.

    Compara la "huella" (hash SHA-256) de cada CSV. Si falla, el generador usa
    azar no controlado por la semilla y los resultados no se pueden reproducir.
    """
    def huella(d):
        return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.glob("*.csv"))}
    a, b = huella(generar(tmp_path / "a", n_flota=60)), huella(generar(tmp_path / "b", n_flota=60))
    assert a == b
    assert set(a) == {f"{n}.csv" for n in ARCHIVOS}


def test_estan_todos_los_tipos_de_anomalia_y_de_caso_legitimo(dataset):
    """El dataset contiene todos los tipos de anomalía y de caso legítimo del catálogo.

    Si falla, algún tipo nunca se inyecta y no se podría evaluar su detección.
    """
    assert set(dataset["ground_truth"]["tipo_anomalia"]) == set(TIPOS_POR_ESCENARIO["realista"])
    assert set(dataset["casos_legitimos"]["tipo_caso"]) == set(CATALOGO_LEGITIMOS)


def test_etiquetas_referencian_registros_existentes_y_no_se_superponen(dataset):
    """Las etiquetas apuntan a registros que existen y ningún registro es a la vez anómalo y legítimo.

    Si falla, la verdad de referencia estaría corrupta y la evaluación no sería confiable.
    """
    ids = {"consumo": set(dataset["consumo"]["id"]),
           "facturacion": set(dataset["facturacion"]["numero_factura"]),
           "facturacion_detalle": set(dataset["facturacion_detalle"]["numero_linea"])}
    for tabla_etiquetas in [dataset["ground_truth"], dataset["casos_legitimos"]]:
        for tabla, grupo in tabla_etiquetas.groupby("tabla"):
            assert set(grupo["id_registro"]) <= ids[tabla], tabla
    anomalas = set(dataset["ground_truth"]["id_registro"])
    assert not anomalas & set(dataset["casos_legitimos"]["id_registro"])


def test_prevalencia_de_anomalias_de_comportamiento_es_baja(dataset):
    """Las anomalías de comportamiento son pocas (entre 0,3 % y 3 % de las cargas), como en la práctica.

    Si falla, el escenario dejaría de ser realista: con demasiadas anomalías
    cualquier método parecería bueno.
    """
    tasa = len(ids_con_anomalia_de_comportamiento(dataset["ground_truth"])) / len(dataset["consumo"])
    assert 0.003 < tasa < 0.03


def test_cargas_limpias_no_superan_el_tanque(dataset):
    """Ninguna carga sin etiqueta supera la capacidad del tanque de su vehículo.

    Si falla, el generador crea excesos de litros no etiquetados, que la regla
    contaría como falsos positivos.
    """
    consumo = dataset["consumo"]
    capacidad = consumo["vehiculo_id"].map(dataset["flota"].set_index("Matricula")["CapacidadTanque"])
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    limpias = ~consumo["id"].isin(etiquetadas)
    assert (consumo.loc[limpias, "litros"] <= capacidad[limpias]).all()


def test_rendimiento_de_cargas_limpias_coincide_con_el_perfil_del_vehiculo(dataset):
    """El rendimiento mediano (km por litro) de cada tipo de vehículo cae en su rango esperado (con 20 % de margen).

    Si falla, los datos sanos tendrían consumos poco creíbles para ese tipo de vehículo.
    """
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
    """Toda carga de un vehículo fuera de servicio, posterior a su baja, está etiquetada como anomalía.

    Si falla, aparecen cargas de vehículos inactivos sin etiqueta (o etiquetas
    sobre cargas que no lo son).
    """
    consumo, flota = dataset["consumo"], dataset["flota"]
    inactivos = flota[flota["Estado"] != "EN SERVICIO"].set_index("Matricula")["FechaEstado"]
    desde = pd.to_datetime(consumo["vehiculo_id"].map(inactivos))
    posteriores = set(consumo.loc[pd.to_datetime(consumo["fecha"]) >= desde, "id"])
    gt = dataset["ground_truth"]
    esperadas = set(gt.loc[gt["tipo_anomalia"] == "CARGA_VEHICULO_INACTIVO", "id_registro"])
    duplicados = set(gt.loc[gt["tipo_anomalia"] == "DUPLICADO", "id_registro"])
    assert posteriores - duplicados == esperadas


def test_gps_solo_de_vehiculos_con_dispositivo(dataset):
    """Solo hay datos de GPS de vehículos que tienen dispositivo y pertenecen a la flota, y nunca con km negativos.

    Si falla, la telemetría estaría desvinculada de la flota o tendría valores imposibles.
    """
    assert set(dataset["telemetria_diaria"]["Placa"]) <= set(dataset["telemetria"]["Placa"])
    assert set(dataset["telemetria"]["Placa"]) <= set(dataset["flota"]["Dominio"])
    assert (dataset["telemetria_diaria"]["km_gps"] >= 0).all()


# --- Circuito solicitud -> carga -> factura ---------------------------------

def test_cada_carga_limpia_tiene_su_solicitud_aprobada_previa(dataset):
    """Cada carga sana tiene una solicitud aprobada de hasta 2 días antes y con litros suficientes.

    Si falla, el generador rompe el circuito de autorización y las reglas que lo
    controlan alertarían cargas normales.
    """
    consumo, solicitudes = dataset["consumo"].copy(), dataset["solicitudes"].copy()
    etiquetadas = set(dataset["ground_truth"]["id_registro"]) | set(dataset["casos_legitimos"]["id_registro"])
    consumo["fecha"] = pd.to_datetime(consumo["fecha"])
    solicitudes["fecha_solicitud"] = pd.to_datetime(solicitudes["fecha_solicitud"])
    limpias = consumo[~consumo["id"].isin(etiquetadas)]
    pares = limpias.merge(solicitudes[solicitudes["estado"] == "APROBADA"], on="vehiculo_id", suffixes=("", "_sol"))
    dias = (pares["fecha"] - pares["fecha_solicitud"]).dt.days
    validas = pares[dias.between(0, 2) & (pares["litros_autorizados"] >= pares["litros"])]
    assert set(validas["id"]) == set(limpias["id"])


def test_facturas_limpias_suman_sus_lineas(dataset):
    """El total de cada factura coincide con la suma de sus líneas, salvo las infladas a propósito.

    Si falla, hay diferencias de importes no etiquetadas o facturas infladas que
    no difieren de sus líneas.
    """
    lineas = dataset["facturacion_detalle"].groupby("numero_factura")["importe"].sum()
    facturas = dataset["facturacion"].set_index("numero_factura")
    diferencia = (facturas["total_monto"] - lineas.reindex(facturas.index)).abs()
    gt = dataset["ground_truth"]
    infladas = set(gt.loc[gt["tipo_anomalia"] == "TOTAL_INFLADO", "id_registro"])
    assert set(diferencia[diferencia > 0.05].index) == infladas


def test_lineas_referencian_cargas_reales_salvo_las_inexistentes(dataset):
    """Las líneas de combustible sin carga asociada son exactamente las etiquetadas como tales.

    Si falla, hay líneas facturadas sin carga que no están en la verdad de referencia.
    """
    lineas = dataset["facturacion_detalle"]
    combustible = lineas[lineas["concepto"] == "COMBUSTIBLE"]
    sin_carga = set(combustible.loc[~combustible["referencia_consumo"].isin(dataset["consumo"]["id"]), "numero_linea"])
    gt = dataset["ground_truth"]
    assert sin_carga == set(gt.loc[gt["tipo_anomalia"] == "LINEA_SIN_CONSUMO", "id_registro"])


def test_cada_carga_real_se_factura_al_menos_una_vez(dataset):
    """Toda carga que no es un duplicado aparece en alguna línea de facturación.

    Si falla, hay cargas que nunca se facturan y el circuito queda incompleto.
    """
    gt = dataset["ground_truth"]
    reales = set(dataset["consumo"]["id"]) - set(gt.loc[gt["tipo_anomalia"] == "DUPLICADO", "id_registro"])
    assert reales <= set(dataset["facturacion_detalle"]["referencia_consumo"])


# --- Reglas e hipótesis -----------------------------------------------------

def test_todas_las_reglas_con_contexto_emiten_alertas(alertas):
    """Cada regla con contexto emite al menos una alerta.

    Si falla, alguna regla dejó de ejecutarse o nunca encuentra nada.
    """
    assert set(priorizacion.REGLAS_CONTEXTO) <= set(alertas["regla"])


def test_las_hipotesis_se_sostienen(dataset, alertas):
    """Se evalúan todas las hipótesis del catálogo, en orden, y todas se sostienen.

    Si falla, alguna hipótesis dejó de cumplirse; el mensaje muestra los F1 de
    la versión ingenua y de la versión con contexto para ver cuál.
    """
    _, veredictos = _contraste(dataset, alertas)
    assert list(veredictos["hipotesis"]) == [h["codigo"] for h in HIPOTESIS]
    assert (veredictos["veredicto"] == "Se sostiene").all(), veredictos[["hipotesis", "f1_ingenua", "f1_contexto"]]


def test_el_contexto_reduce_las_falsas_alarmas_por_casos_legitimos(dataset, alertas):
    """Usar contexto reduce a menos de la quinta parte las falsas alarmas sobre casos legítimos.

    Si falla, el contexto ya no filtra bien los casos legítimos conocidos.
    """
    _, veredictos = _contraste(dataset, alertas)
    assert veredictos["fp_legitimos_contexto"].sum() < veredictos["fp_legitimos_ingenua"].sum() / 5


# --- Priorización -----------------------------------------------------------

# Entrena el modelo de priorización con datos de otras semillas (así no ve el
# dataset que después puntúa) y devuelve los puntajes de cada registro.
@pytest.fixture(scope="module")
def puntajes(dataset):
    variables, etiqueta = priorizacion.datos_de_entrenamiento(semillas=[1001, 1002], n_flota=120)
    modelo = priorizacion.entrenar_supervisado(variables, etiqueta)
    return priorizacion.puntuar(dataset, modelo)


def test_combinado_prioriza_mejor_que_las_reglas_ingenuas(dataset, puntajes):
    """Revisando 50 casos, el método combinado encuentra más anomalías y menos casos legítimos que las reglas ingenuas.

    Si falla, la priorización dejó de aportar ventaja frente a la línea base.
    """
    curva = priorizacion.curva_de_esfuerzo(puntajes[0], dataset["ground_truth"], dataset["casos_legitimos"], maximo=100)
    en50 = curva[curva["revisadas"] == 50].set_index("metodo")
    assert en50.loc["Combinado", "encontradas"] > en50.loc["Reglas ingenuas", "encontradas"]
    assert en50.loc["Combinado", "legitimos_revisados"] < en50.loc["Reglas ingenuas", "legitimos_revisados"]


def test_la_cola_de_revision_explica_cada_caso(dataset, puntajes):
    """La cola de revisión trae los casos pedidos, numerados del 1 en adelante, y cada uno con motivo o regla.

    Si falla, algún caso aparecería en la cola sin explicación de por qué revisarlo.
    """
    pun, variables, alertas_ = puntajes
    cola = priorizacion.cola_de_revision(pun, "Combinado", dataset["consumo"], variables, alertas_, cantidad=20)
    assert len(cola) == 20 and list(cola["prioridad"]) == list(range(1, 21))
    assert (cola["motivos"].str.len() + cola["reglas"].str.len() > 0).all()
