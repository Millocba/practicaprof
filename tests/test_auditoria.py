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
from perfilador.auditoria import _contingencias, auditar  # noqa: E402

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
        "NumeroMotor": flota["NumeroMotor"], "NumeroContrato": flota["NumeroContrato"], "Cupo": flota["Cupo"], "Dependencia": flota["Dependencia"],
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
    assert resultado["cruce_registro"]["minutos_de_la_carga_despues_del_pedido"] is not None  # el desfase pedido-carga (H8)
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
                  sintetico["flota"]["NumeroMotor"].dropna().iloc[0], sintetico["flota"]["NumeroTarjeta"].iloc[0],
                  "proveedor zeta", "PROVEEDOR ZETA"]:
        assert str(valor) not in texto
    for regla in resultado["reglas"].values():
        assert isinstance(regla["alertas"], str) or regla["alertas"] == 0 or regla["alertas"] >= 20


def test_las_contingencias_se_informan_por_mes_y_en_bandas_de_litros(resultado):
    """H13 en la auditoría: contingencias por mes, con carga habitual cercana y cómo coinciden los litros."""
    c = resultado["diagnostico"]["contingencias"]
    assert c["total"]["contingencias"] != 0 and c["total"]["con_carga_habitual_a_menos_de_12_horas"] != 0
    assert list(c["total"]["litros_con_la_carga_mas_parecida"]) == [
        "iguales", "hasta_2_pct", "decimal_movido", "de_2_a_10_pct", "de_10_a_50_pct", "mas_de_50_pct"]
    assert c["por_mes"] and all(len(m) == 7 and m[4] == "-" for m in c["por_mes"])     # solo el mes, AAAA-MM

    def hojas(d):
        return [h for v in d.values() for h in (hojas(v) if isinstance(v, dict) else [v])]
    # Solo cantidades acotadas: 0, 20 o más, o "1–19"
    assert all(h == 0 or h == "1–19" or (isinstance(h, int) and h >= 20) for h in hojas(c))


def test_el_exceso_volumetrico_se_informa_solo_en_agregado(resultado):
    h3b = resultado["diagnostico"]["exceso_volumetrico"]
    assert list(h3b["cargas_sobre_umbral"]) == ["mas_de_1_0", "mas_de_1_02", "mas_de_1_05", "mas_de_1_1"]
    assert h3b["cargas_evaluables"] != 0
    assert h3b["vehiculos_con_exceso_mayor_al_2_pct"] != 0
    assert "vehiculo_id" not in json.dumps(h3b)


def test_las_contingencias_se_clasifican_por_la_carga_mas_parecida():
    """Cada contingencia se clasifica por su carga habitual cercana más parecida: iguales, ±2%, decimal o banda."""
    litros_contingencia = {"iguales": 40.0, "hasta_2_pct": 40.5, "decimal_movido": 4000.0, "de_2_a_10_pct": 42.0,
                           "de_10_a_50_pct": 50.0, "mas_de_50_pct": 90.0}
    filas = []
    for k, (clase, litros) in enumerate(litros_contingencia.items()):
        for v in range(20):
            vehiculo = f"VEH-{k}-{v}"
            filas += [{"id": f"H-{k}-{v}", "vehiculo_id": vehiculo, "fecha": "2024-03-05", "hora": "10:00:00",
                       "litros": 40.0, "origen_transaccion": "POSNET"},
                      {"id": f"C-{k}-{v}", "vehiculo_id": vehiculo, "fecha": "2024-03-05", "hora": "10:30:00",
                       "litros": litros, "origen_transaccion": "CONTINGENCIA"}]
    # Contingencias sin carga habitual cercana (la habitual está a más de 12 horas)
    for v in range(20):
        filas += [{"id": f"H-x-{v}", "vehiculo_id": f"VEH-x-{v}", "fecha": "2024-04-01", "hora": "06:00:00",
                   "litros": 40.0, "origen_transaccion": "POSNET"},
                  {"id": f"C-x-{v}", "vehiculo_id": f"VEH-x-{v}", "fecha": "2024-04-01", "hora": "20:00:00",
                   "litros": 40.0, "origen_transaccion": "CONTINGENCIA"}]
    r = _contingencias(pd.DataFrame(filas))
    assert r["total"]["contingencias"] == 140 and r["total"]["con_carga_habitual_a_menos_de_12_horas"] == 120
    assert r["total"]["litros_con_la_carga_mas_parecida"] == {clase: 20 for clase in litros_contingencia}
    assert r["por_mes"]["2024-04"] == {"contingencias": 20, "con_carga_habitual_a_menos_de_12_horas": 0,
                                       "litros_con_la_carga_mas_parecida": {c: 0 for c in litros_contingencia}}
    assert _contingencias(pd.DataFrame(filas).drop(columns="origen_transaccion")) is None


def test_la_auditoria_explica_las_cargas_sin_vinculo(resultado):
    vinculacion = resultado["diagnostico"]["vinculacion"]
    assert vinculacion["sin_vinculo_normalizado"] != 0
    # En el sintético, la tarjeta de una carga identificada por el motor o con el dominio mal tipeado es
    # la del vehículo; las cargas sin móvil traen un dominio bien formado y una tarjeta fuera del padrón
    assert vinculacion["por_causa"]["tarjeta_del_padron"] != 0
    assert vinculacion["por_causa"]["sin_explicacion"] != 0
    assert vinculacion["vinculadas_pct"]["tarjeta"] > vinculacion["vinculadas_pct"]["normalizado"]


def _flota_y_cargas_sin_vinculo():
    """Flota y cargas inventadas, una por cada causa de una carga sin vínculo."""
    flota = pd.DataFrame({"Matricula": ["S1", "S2", "S3", "S4"], "Dominio": ["AAA001", "AAA002", "AB123CD", "CCC333"],
                          "NumeroTarjeta": ["T1", "T2", "T3", "T4"],
                          "NumeroMotor": ["XX99A999A12345678", "999999987654321", None, "ZZ12345678"]})
    filas = [("ZZZ999", "T1"),        # la tarjeta es de un móvil del padrón
             ("12345678", "TX"),      # últimos 8 del motor, compartidos por dos móviles
             ("87654321", "TX"),      # últimos 8 dígitos del motor
             ("AAA0O1", "TX"),        # confusión de 0 con O
             ("AAA010", "TX"),        # transposición
             ("AB123CDX", "TX"),      # letra de más
             ("QQQ111", "TX"),        # solo en la telemetría
             (None, "TX"),            # sin identificador
             ("123", "TX"),           # solo dígitos
             ("ZZZ888", "TX"),        # bien formado y en ninguna fuente
             ("aaa-001", "T1"),       # se vincula normalizado
             ("AAA001", "T1")]        # se vincula tal como llega
    consumo = pd.DataFrame(filas, columns=["dominio", "numero_tarjeta"]).assign(tipo_identificacion="PATENTE")
    personal = pd.DataFrame({"dominio": [None], "numero_tarjeta": ["TX"], "tipo_identificacion": ["DNI"]})
    return flota, pd.concat([consumo, personal], ignore_index=True), pd.DataFrame({"Placa": ["QQQ-111"]})


def test_vinculacion_explica_cada_carga_sin_vinculo_por_una_causa(monkeypatch):
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _vinculacion

    flota, consumo, telemetria = _flota_y_cargas_sin_vinculo()
    vinculacion = _vinculacion(consumo, flota, telemetria)
    assert vinculacion["cargas_evaluadas"] == 12
    assert vinculacion["sin_vinculo_exacto"] == 11
    assert vinculacion["sin_vinculo_normalizado"] == 10
    assert vinculacion["por_causa"] == {"tarjeta_del_padron": 1, "ultimos_8_del_motor": 2,
                                        "distancia_1_de_un_dominio": 3, "otra_fuente": 1,
                                        "forma_del_identificador": 2, "sin_explicacion": 1}
    assert vinculacion["distancia_1_por_edicion"] == {"confusion_visual": 1, "letra_cambiada": 0,
                                                      "transposicion": 1, "letra_de_mas_o_de_menos": 1}
    assert vinculacion["motor_con_mas_de_un_movil"] == 1
    assert vinculacion["forma_del_identificador"] == {"vacio": 1, "solo_digitos": 1, "solo_letras": 0,
                                                      "largo_distinto": 0}


def test_vinculacion_de_la_telemetria_y_del_registro(monkeypatch):
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _vinculacion

    flota, consumo, _ = _flota_y_cargas_sin_vinculo()
    telemetria = pd.DataFrame({"Alias": ["D1", "D2", "D3", "D4"], "Placa": ["aaa-001", "AAA0O2", "ZZZ999", "QQQ777"],
                               "Grupo": ["G1", "G1", "G1", "BAJA / REEMPLAZOS"]})
    registro = pd.DataFrame({"id": ["P1", "P2", "P3"], "vehiculo_id": ["S1", "SX", "SX"],
                             "dominio": ["ZZZ777", "AAA002", "4567"]})
    vinculacion = _vinculacion(consumo, flota, telemetria, registro)
    t = vinculacion["telemetria"]
    assert t["dispositivos_evaluados"] == 3     # el del depósito no se cuenta
    assert t["vinculados_pct"] is not None and t["sin_vinculo_normalizado"] == 2
    # AAA0O2 está a distancia 1 de AAA002; ZZZ999 es una carga sin vínculo: está en otra fuente
    assert t["por_causa"] == {"ultimos_8_del_motor": 0, "distancia_1_de_un_dominio": 1, "otra_fuente": 1,
                              "forma_del_identificador": 0, "sin_explicacion": 0}
    r = vinculacion["registro"]
    assert r["pedidos_evaluados"] == 3 and r["sin_vinculo_normalizado"] == 2
    assert r["por_causa"] == {"matricula_del_padron": 1, "ultimos_8_del_motor": 0, "distancia_1_de_un_dominio": 0,
                              "otra_fuente": 0, "forma_del_identificador": 1, "sin_explicacion": 0}


def test_vinculacion_suprime_los_grupos_pequenos_y_no_tiene_identificadores():
    from perfilador.auditoria import _vinculacion

    flota, consumo, telemetria = _flota_y_cargas_sin_vinculo()
    vinculacion = _vinculacion(consumo, flota, telemetria)
    assert vinculacion["sin_vinculo_normalizado"] == "1–19"
    texto = json.dumps(vinculacion, ensure_ascii=False)
    for valor in ["ZZZ", "AAA", "1234", "8765", "QQQ", "T1", "S1"]:
        assert valor not in texto


def test_distancia_uno():
    from deteccion.reglas import distancia_uno as _distancia_uno

    assert _distancia_uno("AB1C", "AB1C") is None
    assert _distancia_uno("AAB8", "AAB9") == "letra_cambiada"
    assert _distancia_uno("AI23", "A123") == "confusion_visual"
    assert _distancia_uno("AB12", "BA12") == "transposicion"
    assert _distancia_uno("AB12", "AB123") == "letra_de_mas_o_de_menos"
    assert _distancia_uno("AB12", "BA21") is None
    assert _distancia_uno("AB12", "AB1234") is None


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


def _lecturas(vehiculo, lecturas):
    fechas = pd.date_range("2026-01-01", periods=len(lecturas), freq="D")
    return pd.DataFrame({"id": [f"{vehiculo}#{i}" for i in range(len(lecturas))],
                         "vehiculo_id": vehiculo, "fecha": fechas, "odometro": lecturas})


def _leve(inicio, baja, vuelve, casos):
    """Lecturas con un retroceso leve por caso; devuelve las lecturas y la posición de cada uno."""
    lecturas, bajas = [inicio], []
    odo = inicio
    for _ in range(casos):
        alto = odo + 10_000
        lecturas += [alto, alto - baja]
        bajas.append(len(lecturas) - 1)
        odo = alto + 1_000 if vuelve else alto - baja + max(baja // 2, 1)
        lecturas.append(odo)
    return lecturas, bajas


def _se_queda_abajo(inicio, salto, caida, avance, casos, continua=True):
    """Lecturas con un retroceso que sigue desde el nivel nuevo por caso; devuelve lecturas y posiciones."""
    lecturas, bajas = [inicio], []
    odo = inicio
    for _ in range(casos):
        alto = odo + salto
        lecturas += [alto, alto - caida]
        bajas.append(len(lecturas) - 1)
        odo = alto - caida + avance if continua else alto - caida - avance
        lecturas.append(odo)
    return lecturas, bajas


def _consumo_y_alertas_de_retrocesos():
    partes, marcadas = [], []

    def agregar(vehiculo, lecturas, bajas):
        tabla = _lecturas(vehiculo, lecturas)
        partes.append(tabla)
        marcadas.extend(tabla["id"].iloc[b] for b in bajas)

    agregar("L1", *_leve(100_000, 5, True, 1))       # leve < 10 km, vuelve al valor viejo
    agregar("L2", *_leve(200_000, 5, False, 1))      # leve < 10 km, retoma desde el nuevo
    agregar("L3", *_leve(300_000, 50, True, 1))      # leve 10–100 km, vuelve
    agregar("L4", *_leve(400_000, 300, False, 1))    # leve 100–500 km, retoma
    agregar("S1", *_se_queda_abajo(1_000_000, 100, 1_000, 200, 1))
    agregar("S2", *_se_queda_abajo(2_000_000, 1_000, 20_000, 1_500, 1))       # exceptuado
    agregar("S3", *_se_queda_abajo(3_000_000, 1_000, 60_000, 5_000, 1, continua=False))
    agregar("P2", *_se_queda_abajo(4_000_000, 100, 1_000, 200, 2))
    agregar("M3", *_se_queda_abajo(5_000_000, 100, 1_000, 200, 3))
    consumo = pd.concat(partes, ignore_index=True)
    alertas = pd.DataFrame({"id_registro": marcadas, "regla": "retroceso_con_contexto"})
    flota = pd.DataFrame({"Matricula": ["S2"], "ExcepcionOdometro": ["SI"],
                          "FechaHastaExcepcionOdometro": ["2030-01-01"]})
    return {"consumo": consumo, "flota": flota}, alertas


def test_retrocesos_estudio_abre_las_bajas_leves_por_tamano_y_continuidad(monkeypatch):
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _retrocesos_estudio

    datos, alertas = _consumo_y_alertas_de_retrocesos()
    estudio = _retrocesos_estudio(datos, alertas)
    assert estudio["leve_en_dias_distintos"] == {
        "total": 4,
        "por_baja": {"menos_de_10": 2, "de_10_a_100": 1, "de_100_a_500": 1},
        "retoma_desde_el_nuevo": 2,
        "vuelve_al_valor_viejo": 2,
    }


def test_retrocesos_estudio_abre_los_que_se_quedan_abajo(monkeypatch):
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _retrocesos_estudio

    datos, alertas = _consumo_y_alertas_de_retrocesos()
    estudio = _retrocesos_estudio(datos, alertas)
    assert estudio["se_queda_abajo"] == {
        "total": 8,
        "vehiculos": 5,
        "por_caida": {"de_500_a_5000": 6, "de_5000_a_50000": 1, "mas_de_50000": 1},
        "con_excepcion_vigente": 1,
        "continua_coherente": 7,
        "vehiculos_por_casos": {"1": 3, "2": 1, "3_o_mas": 1},
    }


def test_retrocesos_estudio_suprime_los_grupos_pequenos():
    from perfilador.auditoria import _retrocesos_estudio

    datos, alertas = _consumo_y_alertas_de_retrocesos()
    estudio = _retrocesos_estudio(datos, alertas)
    assert estudio["leve_en_dias_distintos"]["total"] == "1–19"
    assert estudio["se_queda_abajo"]["por_caida"]["de_5000_a_50000"] == "1–19"


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


def test_la_firma_del_consumo_exige_las_columnas_que_usa_el_adaptador():
    """Un reporte viejo o incompleto que conserva las columnas mínimas no debe desplazar al bueno.

    La selección prefiere la tabla más cruda (menos columnas): si la firma no exige todas las
    columnas que el adaptador lee, un export viejo al que le falta alguna gana por tener menos
    columnas y la traducción falla al pedir una que no está.
    """
    from perfilador.adaptador import buscar

    columnas = ["FECHA", "TIPO IDENTIFICACION TARJETA", "IDENTIFICACION TARJETA", "TARJETA", "REMITO",
                "ESTABLECIMIENTO", "PRODUCTO", "LITROS UNIDADES", "PRECIO PVP ESTABLECIMIENTO",
                "IMP TOT PVP ESTABLECIMIENTO", "ODOMETRO"]
    bueno = pd.DataFrame(columns=columnas)
    viejo = bueno.drop(columns=["IDENTIFICACION TARJETA"])
    tablas = {"reporte": bueno, "reporte_viejo": viejo}
    assert buscar(tablas, "consumo") is bueno


def test_el_adaptador_ignora_un_reporte_de_consumo_incompleto(sintetico):
    """Con un export viejo presente, el adaptador sigue leyendo el reporte completo."""
    tablas = con_forma_real(sintetico)
    tablas["reporte_viejo"] = tablas["reporte"].drop(columns=["IDENTIFICACION TARJETA"])
    datos, diagnostico = adaptar(tablas, proveedor="proveedor zeta")
    assert "consumo" in diagnostico["fuentes_encontradas"]
    assert len(datos["consumo"]) == len(sintetico["consumo"])


def test_el_adaptador_cuenta_las_fechas_de_transmision_ilegibles_sin_descartar_el_dispositivo(sintetico):
    """H11: la normalización informa cuántas fechas de última conexión no pudo leer (en bandas) y deja el
    dispositivo en la telemetría, con la fecha vacía, para que se verifique a mano."""
    tablas = con_forma_real(sintetico)
    dispositivos = tablas["dispositivos"].copy()
    dispositivos.loc[dispositivos.index[:3], "Hora de última transmisión"] = "no se pudo leer"
    tablas["dispositivos"] = dispositivos
    datos, diagnostico = adaptar(tablas, proveedor="proveedor zeta")
    assert diagnostico["telemetria"]["fechas_de_transmision_ilegibles"] == "1–19"
    assert len(datos["telemetria"]) == len(sintetico["telemetria"])
    assert datos["telemetria"]["UltimaConexion"].isna().sum() == 3


def test_un_grupo_chico_no_se_recupera_restando_a_las_demas_partes_del_total():
    """Reidentificación por diferencia (#41): con el total a la vista y una sola parte oculta, restar las otras la
    devolvía (37 menos 23 daba el 14 oculto). Se oculta también la parte visible más chica."""
    from perfilador.auditoria import _partes_sin_resta

    assert _partes_sin_resta(37, {"a": 23, "b": 14, "c": 0}) == {"a": None, "b": "1–19", "c": 0}
    assert _partes_sin_resta(100, {"a": 50, "b": 50}) == {"a": 50, "b": 50}              # nada que ocultar
    assert _partes_sin_resta(10, {"a": 10}) == {"a": "1–19"}                           # el total ya está oculto
    # dos partes chicas: restar solo da su suma, que no revela ninguna
    assert _partes_sin_resta(71, {"a": 5, "b": 6, "c": 60}) == {"a": "1–19", "b": "1–19", "c": 60}

