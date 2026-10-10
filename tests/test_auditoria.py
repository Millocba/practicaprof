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
        "DireccionGral": flota["DireccionGral"], "ExcepcionOdometro": flota["ExcepcionOdometro"],
        "FechaHastaExcepcionOdometro": flota["FechaHastaExcepcionOdometro"]})
    excepciones = s["excepciones_odometro"]
    exceptuados = pd.DataFrame({
        "id": range(1, len(excepciones) + 1), "patente": excepciones["patente"], "motivo": "MOTIVO SINTETICO",
        "activo": excepciones["activo"].map({"SI": 1, "NO": 0}),
        "fecha_creacion": excepciones["fecha_creacion"] + " 10:00:00", "fecha_hasta": excepciones["fecha_hasta"]})
    reporte = pd.DataFrame({
        "FECHA": instante.dt.strftime("%d/%m/%Y ") + instante.dt.hour.astype(str) + instante.dt.strftime(":%M:%S"),
        "ESTABLECIMIENTO": consumo["estacion"].str.replace("EST-", "00") + " - ESTACION FICTICIA",
        "TARJETA": consumo["numero_tarjeta"], "CONDUCTOR": "PERSONA SINTETICA",
        "NRO IDENTIFICACION CONDUCTOR": documento(consumo["conductor"]),
        "TIPO IDENTIFICACION TARJETA": personal.map({True: "DNI", False: "PATENTE"}),
        "IDENTIFICACION TARJETA": consumo["dominio"].where(~personal, documento(consumo["conductor"])),
        "ODOMETRO": consumo["odometro"], "REMITO": consumo["id"], "PRODUCTO": consumo["producto"],
        "LITROS UNIDADES": consumo["litros"], "PRECIO PVP ESTABLECIMIENTO": consumo["precio_unitario"],
        "IMP TOT PVP ESTABLECIMIENTO": consumo["importe_total"],
        "ORIGEN DE TRANSACCION": consumo["origen_transaccion"]})
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
        "fact_transacciones": lineas, "dispositivos": dispositivos, "moviles_exceptuados": exceptuados,
        "base.reclamos_combustible": reclamos_con_forma_real(consumo, reporte, flota),
        "base.observaciones_alertas": s["observaciones_alertas"]}


def reclamos_con_forma_real(consumo, reporte, flota):
    """Reclamos al proveedor como los de la fuente: cargas del mismo día y lecturas que se repiten.

    El ticket falta en dos de cada tres (en la fuente falta en casi todos): se vinculan por patente
    y hora. Tipos y estados como en la fuente, unos pocos de doble cobro (duplicidad_metodo), un tipo
    desconocido y el texto libre del mensaje.
    """
    orden = consumo.sort_values(["vehiculo_id", "fecha", "hora"])
    mismo_dia = orden.duplicated(["vehiculo_id", "fecha"], keep=False)
    repetida = orden["odometro"].eq(orden.groupby("vehiculo_id")["odometro"].shift(1))
    elegidas = pd.concat([orden[mismo_dia].assign(tipo_alerta="cargas_multiples"),
                          orden[repetida & ~mismo_dia].assign(tipo_alerta="odometro_estancado"),
                          orden[~mismo_dia & ~repetida].head(3).assign(tipo_alerta="duplicidad_metodo"),
                          orden[~mismo_dia & ~repetida].iloc[3:5].assign(tipo_alerta="TIPO RARO DE LA FUENTE")])
    n = len(elegidas)
    fecha = reporte.set_index(consumo["id"])["FECHA"]
    estados = ["pendiente", "en_disputa", "nota_credito_recibida", "rechazado"]    # los de la fuente
    return pd.DataFrame({
        "id": range(1, n + 1), "dia": elegidas["fecha"].values,
        "patente": elegidas["dominio"].values, "matricula": elegidas["vehiculo_id"].values,
        "fecha_hora": fecha.reindex(elegidas["id"]).values, "tipo_alerta": elegidas["tipo_alerta"].values,
        "mensaje": "MENSAJE SINTETICO DE TEXTO LIBRE 4321", "litros": elegidas["litros"].values,
        "monto_reclamable": (elegidas["litros"] * 10).values, "establecimiento": "00001 - ESTACION FICTICIA",
        "nro_ticket": [t if i % 3 == 0 else None for i, t in enumerate(elegidas["id"])],
        "estado_reclamo": [estados[i % 4] for i in range(n)],
        "nro_reclamo_proveedor": [f"RPZ-{i:06d}" for i in range(n)], "fecha_reclamo": None,
        "created_at": "2024-06-01 10:00:00", "updated_at": "2024-06-01 10:00:00",
        "numero_tarjeta": elegidas["numero_tarjeta"].values})


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
    assert diagnostico["consumo"]["contingencias_pct"] > 0
    assert set(datos["consumo"]["origen_transaccion"]) == {"POSNET", "CONTINGENCIA"}
    assert diagnostico["registro"]["estaciones_de_otra_red_pct"] > 3
    assert len(datos["consumo"]) == len(sintetico["consumo"])
    assert leer_fecha(datos["solicitudes"]["fecha"]).notna().all()
    assert diagnostico["facturacion"]["lineas_con_carga_del_reporte_pct"] > 95


def test_la_auditoria_corre_las_hipotesis_con_datos(resultado):
    assert {"H1", "H8", "H9", "H11", "H12", "H13"} <= set(resultado["hipotesis"])
    odometro = resultado["diagnostico"]["odometro"]
    assert odometro["sin_avance_con_excepcion"] not in (0, "1–19")      # el historial cubre las repetidas
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


def test_los_reclamos_se_vinculan_y_se_comparan_con_las_reglas(resultado):
    """Cada reclamo se vincula con su carga (por ticket o por patente y hora) y se compara con las reglas de su tipo."""
    r = resultado["diagnostico"]["reclamos"]
    assert r["vinculados_con_una_carga_pct"] == 100.0
    assert r["vinculados_por_ticket"] != 0 and r["vinculados_por_patente_y_hora"] != 0
    assert set(r["por_tipo"]) == {"cargas_multiples", "odometro_estancado", "doble_cobro", "otro"}
    assert set(r["por_estado"]) == {"pendiente", "en_disputa", "nota_de_credito", "rechazado"}
    multiples = r["por_tipo_de_alerta"]["cargas_multiples"]
    assert multiples["hipotesis"] == "H4" and "fraccionamiento_diario" in multiples["reglas"]
    assert "sin_avance_sin_excepcion" in r["por_tipo_de_alerta"]["odometro_estancado"]["reglas"]
    # Los reclamos de lecturas repetidas son justamente las que marca la regla ingenua de H12
    assert r["por_tipo_de_alerta"]["odometro_estancado"]["reglas"]["odometro_sin_avance"]["anticipa_pct"] > 90
    for tipo in r["por_tipo_de_alerta"].values():
        for regla in (tipo["reglas"].values() if isinstance(tipo["reglas"], dict) else []):
            assert all(v is None or isinstance(v, (int, float, str)) for v in regla.values())


def test_la_salida_no_tiene_datos_de_los_reclamos(resultado, sintetico):
    """Ni tickets, ni patentes, ni números de reclamo, ni el texto libre del mensaje o de un tipo desconocido."""
    texto = json.dumps(resultado, ensure_ascii=False)
    reclamos = con_forma_real(sintetico)["base.reclamos_combustible"]
    for valor in ["MENSAJE SINTETICO", "4321", "RPZ-", "TIPO RARO", "ESTACION FICTICIA",
                  reclamos["nro_ticket"].dropna().iloc[0], reclamos["patente"].iloc[0],
                  reclamos["numero_tarjeta"].iloc[0]]:
        assert str(valor) not in texto


def test_las_observaciones_se_informan_solo_en_agregado(resultado, sintetico):
    """Por regla, qué parte de las alertas tiene resultado y su distribución; nunca el texto (#36)."""
    reglas = resultado["reglas"]
    con_resultado = {r: v for r, v in reglas.items() if v.get("resultado_pct")}
    assert con_resultado, "alguna regla debería tener alertas documentadas"
    for v in con_resultado.values():
        # Los grupos de menos de 20 casos no se publican (None), como el resto de la auditoría
        assert v["con_resultado_pct"] is None or 0 < v["con_resultado_pct"] <= 100
        assert set(v["resultado_pct"]) <= {"error_humano", "facturacion_del_proveedor", "faltante",
                                           "sin_irregularidad", "otro"}
        assert all(p is None or 0 < p <= 100 for p in v["resultado_pct"].values())
    texto = json.dumps(resultado, ensure_ascii=False)
    for observacion in set(sintetico["observaciones_alertas"]["observacion"]):
        assert observacion not in texto
    datos, _ = adaptar(con_forma_real(sintetico), proveedor="proveedor zeta")
    assert "observacion" not in datos["observaciones_alertas"].columns


def test_un_reclamo_sin_ticket_se_vincula_por_patente_y_hora():
    """Sin ticket, el reclamo va con la carga del mismo vehículo más cercana, a menos de 15 minutos."""
    from perfilador.adaptador import _reclamos

    consumo = pd.DataFrame({"id": ["R1", "R2", "R2#2", "0001-00001234", "0002-00005678"],
                            "vehiculo_id": ["M1", "M1", "M2", "M2", "M2"],
                            "fecha": ["2024-03-01", "2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04"],
                            "hora": ["08:00:00", "14:00:00", "09:00:00", "09:00:00", "09:00:00"]})
    por_dominio = pd.DataFrame({"Matricula": ["M1", "M2"]}, index=["ZA001AA", "ZA002AA"])
    fuente = pd.DataFrame({"patente": ["za 001 aa", "ZA001AA", "ZA002AA", "ZA001AA", None, None],
                           "fecha_hora": ["01/03/2024 8:05:00", "01/03/2024 11:00:00", None, None, None, None],
                           "tipo_alerta": ["cargas_multiples", "Odómetro estancado", "duplicidad_metodo", "otra cosa",
                                           "cargas_multiples", "cargas_multiples"],
                           "estado_reclamo": ["pendiente", "NC recibida", "en_disputa", "nota_credito_recibida",
                                              "rechazado", "pendiente"],
                           "monto_reclamable": [100, 200, 300, 400, 0, -5],
                           # un ticket que llegó como decimal y otro con solo la segunda parte del remito
                           "nro_ticket": [None, None, None, "R2", 1234.0, "00005678"]})
    r = _reclamos(fuente, consumo, por_dominio)
    assert list(r["carga_id"].fillna("—")) == ["R1", "—", "—", "R2", "0001-00001234", "0002-00005678"]
    assert list(r["vinculo"].fillna("—")) == ["patente_y_hora", "—", "—", "ticket", "ticket", "ticket"]
    assert list(r["tipo"]) == ["cargas_multiples", "odometro_estancado", "doble_cobro", "otro",
                               "cargas_multiples", "cargas_multiples"]
    assert list(r["estado"]) == ["pendiente", "otro", "en_disputa", "nota_de_credito", "rechazado", "pendiente"]


def test_montos_y_periodo_de_los_reclamos():
    """El monto suma solo los positivos, con dos cifras; las alertas fuera del período de los reclamos no cuentan."""
    from perfilador.auditoria import _monto, _reclamos as agregados

    reclamos = pd.DataFrame({"tipo": "cargas_multiples", "estado": "pendiente",
                             "monto": [123_456.0] * 25 + [0.0, -10.0], "carga_id": [f"C{i}" for i in range(27)],
                             "vinculo": "ticket", "fecha": pd.Timestamp("2024-03-10")})
    assert _monto(reclamos) == 3_100_000       # 25 × 123.456 = 3.086.400
    assert _monto(reclamos.head(5)) is None     # menos de 20 reclamos
    consumo = pd.DataFrame({"id": [f"C{i}" for i in range(27)] + [f"F{i}" for i in range(30)],
                            "fecha": ["2024-03-10"] * 27 + ["2024-06-01"] * 30})
    alertas = pd.DataFrame({"id_registro": consumo["id"], "regla": "fraccionamiento_diario"})
    r = agregados({"reclamos": reclamos, "consumo": consumo}, alertas, {"fraccionamiento_diario"})
    assert r["montos_no_positivos"] == "1–19"
    regla = r["por_tipo_de_alerta"]["cargas_multiples"]["reglas"]["fraccionamiento_diario"]
    # Las 30 alertas de junio quedan fuera del período de los reclamos: 27 de 27 terminaron en reclamo
    assert regla["alertas"] == 27 and regla["alertas_con_reclamo_pct"] == 100.0


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
