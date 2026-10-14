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
from deteccion.reglas import leer_fecha, reglas_del_dataset  # noqa: E402
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
                      "baja_con_dispositivo_activo", "excepcion_vigente", "odometro_sin_avance_sin_excepcion"}


def test_la_carga_trae_todo_y_respeta_las_claves(base, directorio):
    datos = cargar_dataset(directorio)
    filas = contar(base)
    assert filas["carga"] == len(datos["consumo"])
    assert filas["pedido"] == len(datos["solicitudes"])
    assert filas["factura_linea"] == len(datos["facturacion_detalle"])
    assert filas["vehiculo"] == len(datos["flota"]) and filas["dispositivo"] == len(datos["telemetria"])
    assert filas["excepcion_odometro"] == len(datos["excepciones_odometro"]) > 0
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


def test_las_excepciones_vigentes_son_las_del_padron(base, directorio):
    flota = cargar_dataset(directorio)["flota"]
    con = flota[flota["ExcepcionOdometro"] == "SI"]
    padron = dict(zip(con["Matricula"], leer_fecha(con["FechaHastaExcepcionOdometro"]).dt.strftime("%Y-%m-%d")))
    assert dict(base.execute("SELECT matricula, hasta FROM excepcion_vigente").fetchall()) == padron
    # Una excepción puede durar un solo día
    assert base.execute("SELECT COUNT(*) FROM excepcion_odometro WHERE desde = hasta").fetchone()[0] > 0


def test_verificar_controla_las_excepciones(directorio, tmp_path):
    conexion = conectar(tmp_path / "excepciones.db")
    migrar(conexion)
    cargar(conexion, directorio)
    matricula, desde = conexion.execute("SELECT matricula, desde FROM excepcion_vigente LIMIT 1").fetchone()
    conexion.execute("INSERT INTO excepcion_odometro VALUES ('EXC-X', ?, 'MOTIVO', 'SI', ?, ?)",
                     (matricula, desde, desde))
    assert verificar(conexion) == [f"excepcion_odometro: el vehículo {matricula} tiene 2 excepciones activas"]
    with pytest.raises(sqlite3.IntegrityError):         # vehículo que no está en el padrón
        conexion.execute("INSERT INTO excepcion_odometro VALUES ('EXC-Y', 'VEH-NO-EXISTE', 'M', 'NO', ?, ?)",
                         (desde, desde))
    with pytest.raises(sqlite3.IntegrityError):         # misma clave natural
        conexion.execute("INSERT INTO excepcion_odometro VALUES ('EXC-Z', ?, 'M', 'SI', ?, ?)", (matricula, desde, desde))
    with pytest.raises(sqlite3.IntegrityError):         # termina antes de empezar
        conexion.execute("INSERT INTO excepcion_odometro VALUES ('EXC-W', ?, 'M', 'NO', '2024-02-02', '2024-02-01')",
                         (matricula,))


def test_una_patente_fuera_del_padron_hace_fallar_la_carga(directorio, tmp_path):
    copia = tmp_path / "datos"
    copia.mkdir()
    for archivo in Path(directorio).iterdir():
        (copia / archivo.name).write_bytes(archivo.read_bytes())
    excepciones = pd.read_csv(copia / "excepciones_odometro.csv")
    excepciones.loc[0, "patente"] = "ZZ999ZZ"
    excepciones.to_csv(copia / "excepciones_odometro.csv", index=False)
    conexion = conectar(tmp_path / "patente.db")
    migrar(conexion)
    with pytest.raises(sqlite3.IntegrityError):
        cargar(conexion, copia)
    assert conexion.execute("SELECT COUNT(*) FROM carga").fetchone()[0] == 0     # la transacción se deshizo


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_la_vista_de_sin_avance_coincide_con_la_regla(seed, tmp_path):
    datos_dir = tmp_path / "datos"
    assert GeneradorMaestro(n_flota=120, seed=seed, output_dir=datos_dir, escenario="realista").ejecutar()["exito"]
    conexion = conectar(tmp_path / "base.db")
    migrar(conexion)
    cargar(conexion, datos_dir)
    alertas = reglas_del_dataset(cargar_dataset(datos_dir))
    regla = set(alertas.loc[alertas["regla"] == "sin_avance_sin_excepcion", "id_registro"])
    vista = {i for (i,) in conexion.execute("SELECT id FROM odometro_sin_avance_sin_excepcion")}
    assert regla and vista == regla
