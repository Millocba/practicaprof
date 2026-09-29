"""Tests de la auditoría agregada: el adaptador traduce fuentes con la forma de las reales y la
salida no contiene ningún identificador.

Las "fuentes reales" se arman con datos sintéticos del escenario realista, con los nombres de
columna y los formatos de la fuente.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from deteccion.datos import cargar_dataset  # noqa: E402
from deteccion.reglas import leer_fecha  # noqa: E402
from generator_pipeline_maestro import GeneradorMaestro  # noqa: E402
from perfilador.adaptador import adaptar  # noqa: E402
from perfilador.auditoria import auditar  # noqa: E402

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def documento(persona):
    return persona.astype(str).str.extract(r"(\d+)", expand=False).astype(str).str.zfill(8)


def con_forma_real(s):
    """Tablas con los nombres de columna y los formatos de las fuentes reales."""
    flota, consumo, registro = s["flota"], s["consumo"], s["solicitudes"]
    instante = pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(consumo["hora"])
    personal = consumo["tipo_identificacion"] == "DNI"
    padron = pd.DataFrame({
        "Matricula": flota["Matricula"], "Dominio": flota["Dominio"], "Estado": flota["Estado"].str.title(),
        "SubEstado": flota["SubEstado"], "TipoVehiculo": flota["TipoVehiculo"], "TipoCombustible": flota["TipoCombustible"],
        "CapacidadTanque": flota["CapacidadTanque"], "NumeroTarjeta": flota["NumeroTarjeta"],
        "NumeroContrato": flota["NumeroContrato"], "Cupo": flota["Cupo"], "Dependencia": flota["Dependencia"],
        "DireccionGral": flota["DireccionGral"]})
    reporte = pd.DataFrame({
        "FECHA": instante.dt.strftime("%d/%m/%Y ") + instante.dt.hour.astype(str) + instante.dt.strftime(":%M:%S"),
        "ESTABLECIMIENTO": consumo["estacion"].str.replace("EST-", "00") + " - ESTACION FICTICIA",
        "TARJETA": consumo["numero_tarjeta"], "CONDUCTOR": "PERSONA SINTETICA",
        "NRO IDENTIFICACION CONDUCTOR": documento(consumo["conductor"]),
        "TIPO IDENTIFICACION TARJETA": personal.map({True: "DNI", False: "PATENTE"}),
        "IDENTIFICACION TARJETA": consumo["dominio"].where(~personal, documento(consumo["conductor"])),
        "ODOMETRO": consumo["odometro"], "REMITO": consumo["id"], "PRODUCTO": consumo["producto"],
        "LITROS UNIDADES": consumo["litros"], "PRECIO PVP ESTABLECIMIENTO": consumo["precio_unitario"],
        "IMP TOT PVP ESTABLECIMIENTO": consumo["importe_total"]})
    interno = pd.DataFrame({
        "Id": registro["id"], "Fecha": registro["fecha"], "Hora": registro["hora"], "Matricula": registro["vehiculo_id"],
        "Dominio": registro["dominio"], "OdometroRegistrado": registro["odometro"],
        "Solicitante": "AGENTE SINTETICO (DNI: " + documento(registro["solicitante"]) + ")",
        "Rendido": registro["rendido"], "Anulado": registro["anulado"],
        "LitrosAutorizados": registro["litros_autorizados"], "LitrosCargados": registro["litros_cargados"],
        "TarjetaDni": registro["tarjeta_personal"],
        "EstacionServicio": registro["estacion_servicio"].where(registro["estacion_servicio"] == "ESTACION AJENA",
                                                                "PROVEEDOR ZETA").replace("ESTACION AJENA", "OTRA RED")})
    contratos = s["contratos"].assign(numero=lambda d: d["numero"].str.replace("CTO-", ""))
    periodos = pd.DataFrame({"id": range(1, 13), "fecha_inicio": [f"2024-{m:02d}-01" for m in range(1, 13)],
                             "fecha_fin": [f"2024-{m:02d}-28" for m in range(1, 13)]})
    facturas = s["facturacion"].reset_index(drop=True)
    fact = pd.DataFrame({
        "id": facturas.index + 1, "numero": facturas["numero_factura"],
        "numero_contrato": facturas["contrato"].map(contratos.set_index("indice")["numero"]),
        "periodo_id": facturas["periodo"].str[5:7].astype(int), "monto_facturado": facturas["total_monto"],
        "pdf_total": facturas["total_pdf"].fillna(0)})
    detalle = s["facturacion_detalle"]
    lineas = pd.DataFrame({
        "id": range(1, len(detalle) + 1), "factura_id": detalle["numero_factura"].map(fact.set_index("numero")["id"]),
        "remito": detalle["referencia_consumo"], "litros": detalle["litros"], "importe_yer": detalle["importe"],
        "es_combustible": (detalle["concepto"] != "LUBRICANTE").astype(int)})
    telemetria = s["telemetria"]
    ultima = pd.to_datetime(telemetria["UltimaConexion"], format="mixed")
    dispositivos = pd.DataFrame({
        "Placa": telemetria["Placa"], "Grupo": telemetria["Grupo"], "IMEI": telemetria["IMEI"],
        "Alias": telemetria["Alias"],
        "Hora de última transmisión": "viernes, " + ultima.dt.day.astype(str) + " de "
        + ultima.dt.month.map(lambda m: MESES[m - 1]) + " de " + ultima.dt.year.astype(str) + " "
        + ultima.dt.strftime("%H:%M:%S")})
    return {"padron": padron, "reporte": reporte, "interno": interno, "fact_contratos": contratos.rename(
        columns={"limite_mensual": "limite"})[["numero", "limite"]], "fact_periodos": periodos, "fact_facturas": fact,
        "fact_transacciones": lineas, "dispositivos": dispositivos}


@pytest.fixture(scope="module")
def sintetico(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("realista")
    assert GeneradorMaestro(n_flota=80, seed=42, output_dir=carpeta, escenario="realista").ejecutar()["exito"]
    return cargar_dataset(carpeta)


@pytest.fixture(scope="module")
def resultado(sintetico):
    return auditar(con_forma_real(sintetico), proveedor="proveedor zeta", semillas=(1001,), n_flota=60)


def test_el_adaptador_traduce_y_vincula(sintetico):
    datos, diagnostico = adaptar(con_forma_real(sintetico), proveedor="proveedor zeta")
    assert set(diagnostico["fuentes_encontradas"]) >= {"padron", "consumo", "registro", "facturas", "dispositivos"}
    assert diagnostico["consumo"]["fechas_legibles_pct"] == 100.0
    assert diagnostico["consumo"]["con_vehiculo_del_padron_pct"] > 95
    assert diagnostico["registro"]["estaciones_de_otra_red_pct"] > 3
    assert len(datos["consumo"]) == len(sintetico["consumo"])
    assert leer_fecha(datos["solicitudes"]["fecha"]).notna().all()
    assert diagnostico["facturacion"]["lineas_con_carga_del_reporte_pct"] > 95


def test_la_auditoria_corre_las_hipotesis_con_datos(resultado):
    assert {"H1", "H8", "H9", "H11"} <= set(resultado["hipotesis"])
    assert not {"H6", "H7", "H10"} & set(resultado["hipotesis"])   # faltan las fuentes que necesitan
    assert resultado["cruce_registro"]["cargas_con_pedido_cruce_con_contexto_pct"] > 90
    assert resultado["modelos"]["variables"]["ratio_litros_tanque"]["real"] is not None


def test_la_auditoria_informa_el_alcance_y_la_cobertura(resultado):
    cobertura = resultado["diagnostico"]["cobertura"]
    assert cobertura["alcance"]["registro_interno"] == "todas las redes"
    assert cobertura["vehiculos_con_pedidos_del_proveedor_en_el_reporte_pct"] > 90
    assert cobertura["cargas_de_otra_red_que_cierran_tramos"] != 0
    for mes in cobertura["por_mes"].values():
        assert all(v == 0 or v == "1–19" or (isinstance(v, int) and v >= 20) for v in mes.values())


def test_la_salida_no_tiene_identificadores(resultado, sintetico):
    texto = json.dumps(resultado, ensure_ascii=False)
    for valor in [sintetico["consumo"]["id"].iloc[0], sintetico["solicitudes"]["id"].iloc[0],
                  sintetico["flota"]["Dominio"].iloc[0], sintetico["flota"]["Matricula"].iloc[0],
                  sintetico["telemetria"]["Alias"].iloc[0], sintetico["facturacion"]["numero_factura"].iloc[0],
                  "proveedor zeta", "PROVEEDOR ZETA"]:
        assert str(valor) not in texto
    for regla in resultado["reglas"].values():
        assert isinstance(regla["alertas"], str) or regla["alertas"] == 0 or regla["alertas"] >= 20


def test_el_adaptador_tolera_tipos_y_tarjetas_repetidas_de_la_fuente(sintetico):
    """La fuente trae el documento del conductor como número y tarjetas repetidas en el padrón."""
    tablas = con_forma_real(sintetico)
    tablas["reporte"]["NRO IDENTIFICACION CONDUCTOR"] = pd.to_numeric(tablas["reporte"]["NRO IDENTIFICACION CONDUCTOR"],
                                                                     errors="coerce")   # un vacío llega como NaN
    padron = tablas["padron"]
    tablas["padron"] = pd.concat([padron, padron.head(3).assign(Matricula=lambda d: d["Matricula"] + "-B")],
                                 ignore_index=True)
    resultado = auditar(tablas, proveedor="proveedor zeta", semillas=(1001,), n_flota=60)
    assert "H8" in resultado["hipotesis"]


def test_los_meses_sin_reporte_se_informan_y_no_inflan_los_pedidos_sin_carga(sintetico):
    """El reporte puede tener meses sin descargar: sus pedidos se cuentan por mes pero no se cruzan."""
    tablas = con_forma_real(sintetico)
    fecha = pd.to_datetime(tablas["reporte"]["FECHA"], format="%d/%m/%Y %H:%M:%S")
    tablas["reporte"] = tablas["reporte"][fecha.dt.month != 4]
    resultado = auditar(tablas, proveedor="proveedor zeta", semillas=(1001,), n_flota=60)
    abril = resultado["diagnostico"]["cobertura"]["por_mes"]["2024-04"]
    assert abril["cargas_del_reporte"] == 0 and abril["pedidos_del_proveedor"] not in (0, "1–19")
    rendidas = resultado["reglas"].get("rendida_sin_carga", {"pct": 0})["pct"] or 0
    assert rendidas < 5


def test_solo_los_meses_completos_del_reporte_se_concilian():
    from perfilador.auditoria import meses_completos

    dias = pd.concat([pd.Series(pd.date_range("2026-07-16", "2026-09-27")),
                      pd.Series(pd.date_range("2026-02-20", "2026-02-22"))])
    assert meses_completos(dias) == {"2026-08"}      # julio empieza a mitad de mes y septiembre sigue en curso
