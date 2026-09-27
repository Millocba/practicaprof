"""Tests de la base de datos: migraciones, carga repetible e incremental, restricciones y vistas.

Usan un dataset sintético generado en una carpeta temporal y una base temporal.
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from base_datos.carga import TABLAS, cargar  # noqa: E402
from base_datos.esquema import conectar, migraciones_disponibles, migrar, verificar  # noqa: E402
from deteccion.datos import cargar_dataset  # noqa: E402
from generator_pipeline_maestro import GeneradorMaestro  # noqa: E402


@pytest.fixture(scope="module")
def directorio(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("realista")
    resultado = GeneradorMaestro(n_flota=120, seed=42, output_dir=carpeta, escenario="realista").ejecutar()
    assert resultado["exito"], resultado.get("error")
    return carpeta


@pytest.fixture(scope="module")
def base(directorio, tmp_path_factory):
    conexion = conectar(tmp_path_factory.mktemp("base") / "auditoria.db")
    migrar(conexion)
    cargar(conexion, directorio)
    return conexion


def contar(conexion):
    return {t: conexion.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLAS}


def test_migraciones_se_aplican_una_sola_vez(tmp_path):
    conexion = conectar(tmp_path / "vacia.db")
    assert len(migrar(conexion)) == len(migraciones_disponibles())
    assert migrar(conexion) == []
    vistas = {n for (n,) in conexion.execute("SELECT name FROM sqlite_master WHERE type = 'view'")}
    assert vistas == {"saldo_diario_contrato", "cargas_con_saldo_agotado", "conciliacion_factura", "linea_sin_carga",
                      "baja_con_dispositivo_activo"}


def test_la_carga_trae_todo_y_respeta_las_claves(base, directorio):
    datos = cargar_dataset(directorio)
    filas = contar(base)
    assert filas["carga"] == len(datos["consumo"])
    assert filas["pedido"] == len(datos["solicitudes"])
    assert filas["factura_linea"] == len(datos["facturacion_detalle"])
    assert filas["vehiculo"] == len(datos["flota"]) and filas["dispositivo"] == len(datos["telemetria"])
    assert verificar(base) == []
    # El registro interno llega en DD/MM/AAAA y se guarda en AAAA-MM-DD
    assert pd.read_sql("SELECT fecha FROM pedido", base)["fecha"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()


def test_cargar_dos_veces_no_duplica(directorio, tmp_path):
    conexion = conectar(tmp_path / "doble.db")
    migrar(conexion)
    primera = cargar(conexion, directorio)
    segunda = cargar(conexion, directorio)
    assert primera == segunda == contar(conexion)
    assert conexion.execute("SELECT COUNT(*) FROM carga_de_datos").fetchone()[0] == 2


def test_la_carga_incremental_llega_a_lo_mismo_que_la_completa(directorio, base, tmp_path):
    conexion = conectar(tmp_path / "incremental.db")
    migrar(conexion)
    parcial = cargar(conexion, directorio, hasta="2024-04-30")
    assert 0 < parcial["carga"] < contar(base)["carga"]
    assert conexion.execute("SELECT MAX(fecha) FROM carga").fetchone()[0] <= "2024-04-30"
    assert cargar(conexion, directorio) == contar(base)
    consulta = "SELECT id, fecha, litros, importe FROM carga ORDER BY id"
    assert pd.read_sql(consulta, conexion).equals(pd.read_sql(consulta, base))


def test_las_restricciones_rechazan_datos_imposibles(base):
    with pytest.raises(sqlite3.IntegrityError):
        base.execute("INSERT INTO transferencia VALUES ('TRF-X', '2024-01-10', 1, 1, 100)")
    with pytest.raises(sqlite3.IntegrityError):
        base.execute("INSERT INTO transferencia VALUES ('TRF-Y', '2024-01-10', 1, 99, 100)")  # contrato inexistente
    with pytest.raises(sqlite3.IntegrityError):
        base.execute("INSERT INTO carga (id, fecha, tarjeta, producto, litros, precio_unitario, importe, contrato) "
                     "VALUES ('CONS-X', '2024-01-10', 'NO-EXISTE', 'INFINIA', 30, 2, 60, 1)")
    base.rollback()


def test_las_vistas_de_control_encuentran_lo_inyectado(base, directorio):
    datos = cargar_dataset(directorio)
    gt = datos["ground_truth"]

    def de_tipo(tipo):
        return set(gt.loc[gt["tipo_anomalia"] == tipo, "id_registro"])

    agotados = pd.read_sql("SELECT contrato, mes FROM cargas_con_saldo_agotado", base)
    assert {f"CTO-{c}|{m}" for c, m in zip(agotados["contrato"], agotados["mes"])} == de_tipo("CARGA_CON_CUPO_AGOTADO")
    lubricante = set(datos["facturacion_detalle"].query("concepto == 'LUBRICANTE'")["numero_factura"])
    observadas = set(pd.read_sql("SELECT numero FROM conciliacion_factura WHERE observada = 1", base)["numero"])
    assert observadas == de_tipo("TOTAL_INFLADO") | de_tipo("DIFERENCIA_DEUDA_PDF") | lubricante
    assert set(pd.read_sql("SELECT numero_linea FROM linea_sin_carga", base)["numero_linea"]) == de_tipo("LINEA_SIN_CONSUMO")
    activos = set(pd.read_sql("SELECT dispositivo FROM baja_con_dispositivo_activo", base)["dispositivo"])
    assert activos == de_tipo("DISPOSITIVO_ACTIVO_EN_BAJA")


def test_el_saldo_diario_parte_del_tope_y_suma_transferencias(base):
    saldo = pd.read_sql("SELECT * FROM saldo_diario_contrato ORDER BY contrato, dia", base)
    primeros = saldo.groupby(["contrato", "mes"]).head(1)
    assert (primeros["saldo_para_cargar"] - primeros["transferido"] - primeros["tope"]).abs().max() < 1e-6
    cierre = saldo.groupby(["contrato", "mes"]).tail(1).set_index(["contrato", "mes"])["saldo_al_cierre"]
    total = saldo.groupby(["contrato", "mes"]).agg(tope=("tope", "first"), t=("transferido", "sum"), c=("consumo", "sum"))
    assert ((total["tope"] + total["t"] - total["c"]) - cierre).abs().max() < 1e-6
