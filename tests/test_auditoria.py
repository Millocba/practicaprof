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
        "PRECIO EMPRESA": (consumo["precio_unitario"] * 0.98).round(2),
        "IMP TOT EMPRESA": (consumo["importe_total"] * 0.98).round(2),
        "ORIGEN DE TRANSACCION": consumo["origen_transaccion"]})
    interno = pd.DataFrame({
        "Id": registro["id"], "Fecha": registro["fecha"], "Hora": registro["hora"], "Matricula": registro["vehiculo_id"],
        "Dominio": registro["dominio"], "OdometroRegistrado": registro["odometro"],
        "Solicitante": "AGENTE SINTETICO (DNI: " + documento(registro["solicitante"]) + ")",
        "Rendido": registro["rendido"], "Anulado": registro["anulado"],
        "LitrosAutorizados": registro["litros_autorizados"], "LitrosCargados": registro["litros_cargados"],
        "TarjetaDni": registro["tarjeta_personal"],
        "CapacidadTanque": registro["nivel_tanque"], "BanderaRendicion": registro["bandera_rendicion"],
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
    # dos partes chicas: 71 menos 60 da 11, que también las revela; la visible se oculta y el resto queda en 71
    assert _partes_sin_resta(71, {"a": 5, "b": 6, "c": 60}) == {"a": "1–19", "b": "1–19", "c": None}


def test_el_eje_no_devuelve_un_grupo_chico_restando_una_columna_o_el_total():
    """Supresión complementaria en el eje: si la resta de una columna (o de todas las celdas) contra
    el total publicado queda entre 1 y 19, se oculta la celda entera más chica."""
    from perfilador.auditoria import _eje_sin_resta

    eje = {"2026-01": {"banda": 50, "otra": 30}, "2026-02": {"banda": 40, "otra": 30}}
    _eje_sin_resta(eje, [("banda", 91), (None, 151)])
    assert eje["2026-02"]["banda"] is None          # 91 menos 90 da 1: la celda más chica se va
    assert eje["2026-01"] == {"banda": 50, "otra": 30} and eje["2026-02"]["otra"] == 30

    eje2 = {"2026-01": {"a": 50, "b": 40}, "2026-02": {"a": 40, "b": 40}}
    _eje_sin_resta(eje2, [("a", 91), (None, 139)])
    assert eje2["2026-02"]["a"] is None            # 91 menos 90 da 1: la celda más chica de "a" se va
    assert eje2["2026-01"]["b"] is None            # recién ahí el total contra el eje da 139 - 130 = 9: otra
    assert eje2["2026-01"]["a"] == 50 and eje2["2026-02"]["b"] == 40

    eje3 = {"2026-01": {"x": 40}}
    _eje_sin_resta(eje3, [("x", "1–19"), ("total", 41)])   # sin total entero ni celda "total" no hay resta
    assert eje3 == {"2026-01": {"x": 40}}


def test_el_bloque_protege_su_eje_con_los_totales_que_publica():
    from perfilador.auditoria import _protege_el_eje

    bloque = {"total": 141, "banda": 92, "otra": 50,
              "por_mes": {"2026-01": {"banda": 50, "otra": 30}, "2026-02": {"banda": 41, "otra": 20}}}
    _protege_el_eje(bloque, "por_mes")
    assert bloque["por_mes"]["2026-02"]["banda"] is None     # 92 menos 91 da 1
    assert bloque["por_mes"]["2026-01"]["banda"] == 50

    cruce = {"cargas_sin_pedido": {"total": 91},
             "por_tipo": {"camion": {"cargas_sin_pedido": 50}, "mixto": {"cargas_sin_pedido": 40}}}
    _protege_el_eje(cruce, "por_tipo")
    assert cruce["por_tipo"]["mixto"]["cargas_sin_pedido"] is None    # el total del hijo: 91 - 90 = 1
    assert cruce["por_tipo"]["camion"]["cargas_sin_pedido"] == 50


def test_un_grupo_con_total_sin_que_la_resta_de_sus_partes_devuelva_un_chico():
    from perfilador.auditoria import _protege_el_total

    leve = {"total": 288,
            "por_baja": {"menos_de_10": "1–19", "de_10_a_100": 67, "de_100_a_500": 204},
            "retoma_desde_el_nuevo": 37, "vuelve_al_valor_viejo": 245}
    _protege_el_total(leve)
    assert leve["retoma_desde_el_nuevo"] is None        # 288 - 37 - 245 = 6
    assert leve["por_baja"]["de_10_a_100"] is None      # 288 - 67 - 204 = 17
    assert leve["por_baja"]["de_100_a_500"] == 204 and leve["vuelve_al_valor_viejo"] == 245

    abajo = {"total": 68, "vehiculos": 30,
             "por_caida": {"de_500_a_5000": 50, "de_5000_a_50000": "1–19", "mas_de_50000": 0},
             "con_excepcion_vigente": 0, "continua_coherente": 18}
    _protege_el_total(abajo)
    assert abajo["por_caida"]["de_500_a_5000"] is None  # 68 - 50 = 18
    assert abajo["vehiculos"] == 30                      # 68 - 30 - 0 - 18 = 20: justo en el límite, se queda


def test_el_adaptador_expone_los_precios_del_reporte_con_nombres_genericos(sintetico):
    """H9: todas las columnas de precio del reporte quedan en `precios_reporte` como precio_a, precio_b, ..."""
    datos, _ = adaptar(con_forma_real(sintetico), proveedor="proveedor zeta")
    precios = datos["precios_reporte"]
    assert list(precios.columns) == ["id", "precio_a", "precio_b"]
    assert len(precios) == int((datos["consumo"]["litros"] > 0).sum())


def test_las_bandas_del_cruce_de_tiempo_dejan_el_corte_en_la_banda_de_abajo():
    from perfilador.auditoria import _bandas_cruce_de_tiempo

    assert list(_bandas_cruce_de_tiempo([0, 180, 181, 360, 361, 720, 1440, 1441, float("inf")])) == [
        "hasta_3_horas", "hasta_3_horas", "de_3_a_6_horas", "de_3_a_6_horas", "de_6_a_12_horas",
        "de_6_a_12_horas", "de_12_a_24_horas", "ninguno_a_menos_de_24_horas", "ninguno_a_menos_de_24_horas"]


def test_las_bandas_de_los_pares_que_cruzan_usan_el_valor_absoluto():
    from perfilador.auditoria import _bandas_de_que_cruzan

    assert list(_bandas_de_que_cruzan([-5, 5, 6, 30, 31, 60, 180, 181])) == [
        "hasta_5", "hasta_5", "de_5_a_30", "de_5_a_30", "de_30_a_60", "de_30_a_60", "de_1_a_3_horas", "mas_de_3_horas"]


def test_las_bandas_del_precio_facturado_incluyen_el_corte_de_arriba():
    from perfilador.auditoria import _bandas_de_precio_facturado

    assert list(_bandas_de_precio_facturado([0.94, 0.95, 0.979, 0.98, 0.999, 1.0, 1.02, 1.021])) == [
        "menos_de_0_95", "de_0_95_a_0_98", "de_0_95_a_0_98", "de_0_98_a_1_00", "de_0_98_a_1_00",
        "de_1_00_a_1_02", "de_1_00_a_1_02", "mas_de_1_02"]


def test_las_bandas_de_la_razon_entre_precios_tienen_una_banda_en_torno_a_0_98():
    from perfilador.auditoria import _bandas_de_razon_entre_precios

    assert list(_bandas_de_razon_entre_precios([0.96, 0.97, 0.9794, 0.9796, 0.98, 0.9804, 0.9806, 0.99, 0.991])) == [
        "menos_de_0_97", "de_0_97_a_0_98", "de_0_97_a_0_98", "exactamente_0_98", "exactamente_0_98",
        "exactamente_0_98", "de_0_98_a_0_99", "de_0_98_a_0_99", "mas_de_0_99"]


def test_las_bandas_de_la_diferencia_de_importes():
    from perfilador.auditoria import _bandas_diferencia

    assert list(_bandas_diferencia([0.0, 0.0005, 0.001, 0.002, 0.005, 0.006, 0.02, 0.021])) == [
        "exacta", "hasta_0_1_pct", "hasta_0_1_pct", "de_0_1_a_0_5_pct", "de_0_1_a_0_5_pct",
        "de_0_5_a_2_pct", "de_0_5_a_2_pct", "mas_de_2_pct"]


def test_la_auditoria_informa_el_cruce_de_ventanas_y_los_precios(resultado):
    """H8/H9 en la auditoría: los pedidos fuera de la ventana de horario y los precios del detalle."""
    from perfilador.auditoria import (BANDAS_CRUCE_QUE_CRUZAN, BANDAS_CRUCE_TIEMPO, BANDAS_DIFERENCIA_IMPORTES,
                                      BANDAS_PRECIO_FACTURADO, BANDAS_RAZON_ENTRE_PRECIOS)

    ventanas = resultado["diagnostico"]["cruce_registro_ventanas"]
    assert ventanas is not None
    assert set(ventanas["cargas_sin_pedido"]["con_pedido_del_mismo_vehiculo"]) == {"total", *BANDAS_CRUCE_TIEMPO}
    assert set(ventanas["minutos_de_los_pares_que_cruzan"]) == {"total", *BANDAS_CRUCE_QUE_CRUZAN}
    assert ventanas["por_mes"] and all(len(m) == 7 and m[4] == "-" for m in ventanas["por_mes"])

    precios = resultado["diagnostico"]["facturacion_detalle_precios"]
    assert precios is not None
    assert list(precios["precio_facturado_sobre_cada_precio_unitario"]) == ["precio_a", "precio_b"]
    ajuste = precios["precio_facturado_sobre_cada_precio_unitario"]["precio_a"]
    assert set(ajuste) == {"total", "por_mes", "por_producto", *BANDAS_PRECIO_FACTURADO}
    razon = precios["razon_entre_precios_unitarios"]
    assert set(razon) == {"total", "por_mes", *BANDAS_RAZON_ENTRE_PRECIOS}
    assert razon["exactamente_0_98"] != 0      # en el sintético el segundo precio es el 0,98 del primero
    assert set(precios["diferencias_entre_deuda_y_lineas"]) == {"total", "por_mes", *BANDAS_DIFERENCIA_IMPORTES}
    assert set(precios["diferencias_entre_pdf_y_deuda"]) == {"total", "por_mes", "sin_pdf", *BANDAS_DIFERENCIA_IMPORTES}
    assert set(precios["lineas"]) == {"cargas_facturadas_mas_de_una_vez", "lineas_sin_carga_en_el_reporte",
                                      "lineas_con_concepto_distinto_de_combustible", "mes_de_facturacion"}


def test_el_cruce_de_ventanas_y_los_precios_no_revelan_identificadores(resultado, sintetico):
    bloques = [resultado["diagnostico"]["cruce_registro_ventanas"],
               resultado["diagnostico"]["facturacion_detalle_precios"]]
    texto = json.dumps(bloques, ensure_ascii=False)
    for valor in [sintetico["consumo"]["id"].iloc[0], sintetico["solicitudes"]["id"].iloc[0],
                  sintetico["flota"]["Dominio"].iloc[0], sintetico["facturacion"]["numero_factura"].iloc[0]]:
        assert str(valor) not in texto

    def hojas(d):
        return [h for v in d.values() for h in (hojas(v) if isinstance(v, dict) else [v])]
    # Ningún conteo suelto entre 1 y 19: los chicos salen como "1–19"
    assert all(not (isinstance(h, int) and 0 < h < 20) for bloque in bloques for h in hojas(bloque))


def _residuos_chicos(datos):
    """Restas de un total publicado menos sus partes visibles que caen entre 1 y 19.

    Cada regla es una resta que alguien podría hacer con lo publicado: (a) un `total` entero menos
    sus hermanos enteros; (b) lo mismo contra las partes de un grupo hermano de conteos; (c) una
    clave entera del padre menos esa clave en todas las entradas de un eje (por_mes, por_producto,
    por_tipo); (d) el `total` del padre menos todas las celdas enteras del eje; (e) el `total` de un
    hijo menos la clave de ese hijo en cada entrada del eje. Devuelve la lista de restas sospechosas.
    """
    malos = []

    def enteros(d, ignora=()):
        return sum(v for k, v in d.items() if k not in ignora and isinstance(v, int)
                   and not isinstance(v, bool))

    def caminar(d, ruta):
        total = d.get("total")
        publicado = isinstance(total, int) and not isinstance(total, bool)
        hijos = {k: v for k, v in d.items() if isinstance(v, dict)}
        if publicado:
            resto = enteros(d, ignora=("total",))
            if 1 <= total - resto <= 19:
                malos.append(f"{ruta}.total - partes = {total - resto}")
            for nombre, hijo in hijos.items():
                if not any(isinstance(v, dict) for v in hijo.values()):
                    resto = enteros(hijo, ignora=("total",))
                    if 1 <= total - resto <= 19:
                        malos.append(f"{ruta}.total - {nombre} = {total - resto}")
        ejes = {k: v for k, v in hijos.items()
                if v and all(isinstance(entrada, dict) for entrada in v.values())}
        for nombre, eje in ejes.items():
            comunes = set.intersection(*(set(entrada) for entrada in eje.values()))
            for clave in sorted(comunes):
                if clave in d and isinstance(d[clave], int) and not isinstance(d[clave], bool):
                    suma = sum(v for v in (entrada[clave] for entrada in eje.values())
                               if isinstance(v, int) and not isinstance(v, bool))
                    if 1 <= d[clave] - suma <= 19:
                        malos.append(f"{ruta}.{clave} - {nombre} = {d[clave] - suma}")
                hijo = d.get(clave)
                if isinstance(hijo, dict) and isinstance(hijo.get("total"), int):
                    suma = sum(v for v in (entrada[clave] for entrada in eje.values())
                               if isinstance(v, int) and not isinstance(v, bool))
                    if 1 <= hijo["total"] - suma <= 19:
                        malos.append(f"{ruta}.{clave}.total - {nombre} = {hijo['total'] - suma}")
            if publicado:
                suma = enteros({k: v for entrada in eje.items() for k, v in entrada[1].items()})
                if 1 <= total - suma <= 19:
                    malos.append(f"{ruta}.total - {nombre} = {total - suma}")
        for nombre, hijo in hijos.items():
            caminar(hijo, f"{ruta}.{nombre}")

    caminar(datos, "raiz")
    return malos


def test_ningun_total_menos_sus_partes_visibles_da_un_grupo_chico(resultado):
    """Reidentificación por resta entre dimensiones: el total de cada bloque menos sus partes
    visibles (hermanos, eje completo o una columna del eje) nunca devuelve un conteo de 1 a 19."""
    violaciones = _residuos_chicos(resultado)
    assert not violaciones, "\n".join(violaciones)


CLAVES_DEL_DETALLE_DE_EXCESO = {
    "vehiculos", "cargas_con_exceso", "vehiculos_con_3_o_mas_cargas_con_exceso",
    "vehiculos_para_la_mitad_de_las_cargas",
    *(f"cociente_{b}" for b in ("1_02_a_1_05", "1_05_a_1_10", "1_10_a_1_25", "1_25_a_1_50", "mas_de_1_50")),
    *(f"vehiculos_con_fraccion_{b}" for b in ("menos_de_0_10", "0_10_a_0_30", "0_30_a_0_60", "mas_de_0_60")),
    *(f"vehiculos_con_cv_{b}" for b in ("menos_de_0_05", "0_05_a_0_15", "0_15_a_0_30", "mas_de_0_30")),
    *(f"rendimiento_{b}" for b in ("menos_de_0_5", "0_5_a_0_8", "0_8_a_1_2", "mas_de_1_2")),
    *(f"causa_probable_{c}" for c in ("dominio_equivocado", "proveedor_equivocado", "tarjeta_equivocada")),
}


def _detalle_de_exceso_sintetico():
    """Dos vehículos de tanque de 100 L: uno excede desde su primera carga y el otro después."""
    flota = pd.DataFrame({"Matricula": ["S1", "S2"], "CapacidadTanque": [100.0, 100.0]})
    filas = [{"id": f"E1-{i}", "vehiculo_id": "S1", "fecha": f"2024-05-{10 + i:02d}",
              "litros": 105.0, "odometro": 1000 + 100 * i} for i in range(10)]
    filas += [{"id": f"E2-{i}", "vehiculo_id": "S2", "fecha": f"2024-05-{10 + i:02d}",
               "litros": 50.0 if i < 5 else 130.0, "odometro": 5000 + 100 * i} for i in range(10)]
    consumo = pd.DataFrame(filas)
    alertas = pd.DataFrame({"id_registro": ["E2-5"], "causa_probable": ["tarjeta_equivocada"]})
    return consumo, flota, alertas


def test_el_detalle_de_exceso_clasifica_por_el_origen_y_abre_las_bandas(monkeypatch):
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_volumetrico_detalle

    consumo, flota, alertas = _detalle_de_exceso_sintetico()
    detalle = _exceso_volumetrico_detalle(consumo, flota, alertas)
    assert set(detalle) == {"desde_el_inicio", "despues"}
    assert set(detalle["desde_el_inicio"]) == CLAVES_DEL_DETALLE_DE_EXCESO

    desde = detalle["desde_el_inicio"]
    assert desde["vehiculos"] == 1 and desde["cargas_con_exceso"] == 10
    assert desde["cociente_1_02_a_1_05"] == 10     # 1,05 exacto: borde de la primera banda
    assert desde["cociente_1_05_a_1_10"] == 0 and desde["cociente_1_10_a_1_25"] == 0
    assert desde["vehiculos_con_fraccion_mas_de_0_60"] == 1   # 10 de 10 cargas evaluables
    assert desde["vehiculos_con_3_o_mas_cargas_con_exceso"] == 1
    assert desde["vehiculos_con_cv_menos_de_0_05"] == 1       # cociente constante: CV = 0
    assert desde["vehiculos_para_la_mitad_de_las_cargas"] == 1
    assert desde["rendimiento_0_8_a_1_2"] == 9               # la primera carga no tiene tramo
    assert desde["causa_probable_tarjeta_equivocada"] == 0

    despues = detalle["despues"]
    assert despues["vehiculos"] == 1 and despues["cargas_con_exceso"] == 5
    assert despues["cociente_1_25_a_1_50"] == 5              # 1,30: litros/capacidad
    assert despues["vehiculos_con_fraccion_0_30_a_0_60"] == 1  # 5 excesos sobre 10 evaluables: 50 %
    assert despues["vehiculos_con_3_o_mas_cargas_con_exceso"] == 1
    assert despues["vehiculos_con_cv_menos_de_0_05"] == 1
    assert despues["vehiculos_para_la_mitad_de_las_cargas"] == 1
    assert despues["rendimiento_0_8_a_1_2"] == 5
    assert despues["causa_probable_tarjeta_equivocada"] == 1
    assert despues["causa_probable_dominio_equivocado"] == 0
    assert despues["causa_probable_proveedor_equivocado"] == 0

    crudo = json.dumps(detalle)
    for secreto in ("S1", "S2", "E1-", "E2-", "vehiculo_id", "odometro", "fecha"):
        assert secreto not in crudo


def test_las_bandas_del_detalle_de_exceso_tienen_sus_bordes_fijos():
    from perfilador.auditoria import (_banda_de_la_fraccion, _banda_de_la_variacion, _banda_del_cociente,
                                      _banda_del_rendimiento)

    assert _banda_del_cociente(1.05) == "1_02_a_1_05"
    assert _banda_del_cociente(1.050001) == "1_05_a_1_10"
    assert _banda_del_cociente(1.10) == "1_05_a_1_10"
    assert _banda_del_cociente(1.100001) == "1_10_a_1_25"
    assert _banda_del_cociente(1.25) == "1_10_a_1_25"
    assert _banda_del_cociente(1.250001) == "1_25_a_1_50"
    assert _banda_del_cociente(1.50) == "1_25_a_1_50"
    assert _banda_del_cociente(1.500001) == "mas_de_1_50"

    assert _banda_de_la_fraccion(0.0999) == "menos_de_0_10"
    assert _banda_de_la_fraccion(0.10) == "0_10_a_0_30"
    assert _banda_de_la_fraccion(0.30) == "0_10_a_0_30"
    assert _banda_de_la_fraccion(0.300001) == "0_30_a_0_60"
    assert _banda_de_la_fraccion(0.599999) == "0_30_a_0_60"
    assert _banda_de_la_fraccion(0.60) == "mas_de_0_60"

    assert _banda_de_la_variacion(0.0499) == "menos_de_0_05"
    assert _banda_de_la_variacion(0.05) == "0_05_a_0_15"
    assert _banda_de_la_variacion(0.15) == "0_05_a_0_15"
    assert _banda_de_la_variacion(0.150001) == "0_15_a_0_30"
    assert _banda_de_la_variacion(0.30) == "0_15_a_0_30"
    assert _banda_de_la_variacion(0.300001) == "mas_de_0_30"

    assert _banda_del_rendimiento(0.4999) == "menos_de_0_5"
    assert _banda_del_rendimiento(0.5) == "0_5_a_0_8"
    assert _banda_del_rendimiento(0.8) == "0_5_a_0_8"
    assert _banda_del_rendimiento(0.800001) == "0_8_a_1_2"
    assert _banda_del_rendimiento(1.2) == "0_8_a_1_2"
    assert _banda_del_rendimiento(1.200001) == "mas_de_1_2"


def test_el_detalle_de_exceso_usa_el_historial_para_definir_el_origen(monkeypatch):
    """El exceso dentro de las primeras cargas (FRACCION_INICIAL) marca el origen del vehículo."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_volumetrico_detalle
    from deteccion.reglas import FRACCION_INICIAL

    flota = pd.DataFrame({"Matricula": ["S1", "S2"], "CapacidadTanque": [100.0, 100.0]})
    total = 8                                  # primeras cargas: posición < 8 * 0.25 = 2 (pos 0 y 1)
    filas = []
    for i in range(total):
        exceso_bajo = i == 1                    # exceso justo dentro de las iniciales
        exceso_tarde = i == 2                   # exceso solo después de las iniciales
        filas.append({"id": f"B1-{i}", "vehiculo_id": "S1", "fecha": f"2024-06-{10 + i:02d}",
                      "litros": 105.0 if exceso_bajo else 50.0, "odometro": 1000 + 100 * i})
        filas.append({"id": f"B2-{i}", "vehiculo_id": "S2", "fecha": f"2024-06-{10 + i:02d}",
                      "litros": 105.0 if exceso_tarde else 50.0, "odometro": 5000 + 100 * i})
    assert int(max(total * FRACCION_INICIAL, 1)) == 2   # el cálculo de las iniciales es el de la regla
    detalle = _exceso_volumetrico_detalle(pd.DataFrame(filas), flota, pd.DataFrame(
        columns=["id_registro", "causa_probable"]))
    assert detalle["desde_el_inicio"]["cargas_con_exceso"] == 1
    assert detalle["despues"]["cargas_con_exceso"] == 1


def _enteros_chicos_del_detalle(bloque):
    """Cualquier entero de 1 a 19 publicado en el bloque, sin importar dónde."""
    chicos = []

    def caminar(d, ruta):
        for clave, valor in d.items():
            if isinstance(valor, dict):
                caminar(valor, f"{ruta}.{clave}")
            elif isinstance(valor, int) and not isinstance(valor, bool) and 1 <= valor <= 19:
                chicos.append(f"{ruta}.{clave} = {valor}")

    caminar(bloque, "detalle")
    return chicos


def _restas_del_detalle(bloque):
    """Restas entre conteos de la misma unidad que publica cada clase: total menos partes visibles."""
    parejas = [(("cargas_con_exceso",), ("cociente_",)),
               (("cargas_con_exceso",), ("rendimiento_",)),
               (("cargas_con_exceso",), ("causa_probable_",)),
               (("vehiculos",), ("vehiculos_con_fraccion_",)),
               (("vehiculos",), ("vehiculos_con_cv_",)),
               (("vehiculos",), ("vehiculos_con_3_o_mas_cargas_con_exceso",)),
               (("vehiculos",), ("vehiculos_para_la_mitad_de_las_cargas",)),
               (("vehiculos_con_3_o_mas_cargas_con_exceso",), ("vehiculos_con_cv_",))]
    malos = []

    def suma(detalle, prefijos):
        return sum(v for k, v in detalle.items() if any(k.startswith(p) for p in prefijos)
                   and isinstance(v, int) and not isinstance(v, bool))

    for nombre, detalle in bloque.items():
        for totales, partes in parejas:
            for total in totales:
                valor = detalle.get(total)
                if not isinstance(valor, int) or isinstance(valor, bool):
                    continue
                resto = valor - suma(detalle, partes)
                if 1 <= resto <= 19:
                    malos.append(f"{nombre}.{total} - {partes} = {resto}")
    return malos


def test_el_detalle_de_exceso_no_publica_un_entero_del_1_al_19(resultado):
    bloque = resultado["diagnostico"]["exceso_volumetrico_detalle"]
    chicos = _enteros_chicos_del_detalle(bloque)
    assert not chicos, "\n".join(chicos)


def test_el_detalle_de_exceso_no_deja_restar_un_grupo_chico(resultado):
    bloque = resultado["diagnostico"]["exceso_volumetrico_detalle"]
    malos = _restas_del_detalle(bloque)
    assert not malos, "\n".join(malos)


def test_el_detalle_de_exceso_oculta_la_banda_que_delataria_un_grupo_chico():
    """Sin protección, 45 cargas con exceso menos una banda de 30 devolvería 15."""
    from perfilador.auditoria import _exceso_volumetrico_detalle

    flota = pd.DataFrame({"Matricula": ["S1", "S2"], "CapacidadTanque": [100.0, 100.0]})
    filas = [{"id": f"C1-{i}", "vehiculo_id": "S1", "fecha": f"2024-07-{1 + i:02d}",
              "litros": 130.0, "odometro": 1000 + 100 * i} for i in range(30)]
    filas += [{"id": f"C2-{i}", "vehiculo_id": "S2", "fecha": f"2024-07-{1 + i:02d}",
               "litros": 105.0, "odometro": 5000 + 100 * i} for i in range(15)]
    detalle = _exceso_volumetrico_detalle(pd.DataFrame(filas), flota, pd.DataFrame(
        columns=["id_registro", "causa_probable"]))
    desde = detalle["desde_el_inicio"]
    assert desde["cargas_con_exceso"] == 45
    assert desde["cociente_1_25_a_1_50"] is None   # 45 - 30 = 15: la banda se oculta
    assert desde["cociente_1_02_a_1_05"] == "1–19"
    assert not _enteros_chicos_del_detalle(detalle), "\n".join(_enteros_chicos_del_detalle(detalle))
    assert not _restas_del_detalle(detalle), "\n".join(_restas_del_detalle(detalle))


def test_la_flota_con_matriculas_repetidas_no_tumba_el_exceso(monkeypatch):
    """El padrón puede traer una matrícula repetida: el mapa de capacidad no puede reindexar."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_volumetrico, _exceso_volumetrico_detalle

    consumo = pd.DataFrame([{"id": f"C-{i}", "vehiculo_id": "S1", "fecha": f"2024-06-{1 + i:02d}",
                             "litros": 105.0, "odometro": 1000 + 100 * i} for i in range(10)])
    flota = pd.DataFrame({"Matricula": ["S1", "S1", "S2"], "CapacidadTanque": [100.0, 110.0, 100.0]})

    assert _exceso_volumetrico(consumo, flota)["cargas_evaluables"] == 10
    detalle = _exceso_volumetrico_detalle(consumo, flota, None)
    assert detalle["desde_el_inicio"]["cargas_con_exceso"] == 10


def test_un_bloque_de_diagnostico_que_falla_se_informa_sanitizado():
    """Un bloque no puede tumbar la corrida: si falla, solo el tipo y la función y línea, sin datos."""
    from perfilador.auditoria import _proteger

    def bloque_roto(consumo, flota):
        raise ValueError("dominio AB123CD de la matrícula XYZ-999")

    fallo = _proteger("bloque_roto", bloque_roto, "consumo", "flota")
    assert fallo["error"] == "ValueError"
    assert fallo["donde"].startswith("bloque_roto:")
    assert "AB123CD" not in json.dumps(fallo) and "XYZ" not in json.dumps(fallo)
    assert _proteger("bloque_roto", lambda: {"ok": True}) == {"ok": True}


def test_correr_solo_un_bloque_saltea_las_reglas_y_los_modelos(sintetico):
    """`solo` arma los datos con el adaptador y calcula un único bloque, sin reglas ni modelos."""
    resultado = auditar(con_forma_real(sintetico), proveedor="proveedor zeta",
                        solo="exceso_volumetrico_detalle")
    assert set(resultado["diagnostico"]) == {"exceso_volumetrico_detalle"}
    assert set(resultado["diagnostico"]["exceso_volumetrico_detalle"]) == {"desde_el_inicio", "despues"}
    assert "error" not in resultado["diagnostico"]["exceso_volumetrico_detalle"]
    assert resultado["reglas"] == {} and resultado["hipotesis"] == {}
    assert resultado["modelos"] == {} and resultado["cruce_registro"] == {}


def test_la_corrida_informa_un_bloque_que_falla_sin_exponer_el_mensaje(sintetico, monkeypatch):
    def roto(*argumentos, **opciones):
        raise KeyError("id 4712 del dominio AB123CD")

    monkeypatch.setattr("perfilador.auditoria._exceso_volumetrico_detalle", roto)
    resultado = auditar(con_forma_real(sintetico), proveedor="proveedor zeta",
                        solo="exceso_volumetrico_detalle")
    bloque = resultado["diagnostico"]["exceso_volumetrico_detalle"]
    assert bloque["error"] == "KeyError"
    assert bloque["donde"].startswith("roto:")
    assert "AB123CD" not in json.dumps(resultado)


def test_correr_solo_un_bloque_desconocido_no_arranca(sintetico):
    with pytest.raises(ValueError):
        auditar(con_forma_real(sintetico), proveedor="proveedor zeta", solo="no_existe")


def _datos_de_fraccionamiento(cargas, flota, pedidos=None, reclamos=None):
    """Un `datos` con lo justo para el bloque de fraccionamiento, con las etiquetas genéricas del adaptador."""
    consumo = pd.DataFrame(cargas)
    # El cruce con el registro lee columnas que las cargas armadas a mano no traen: se completan
    completo = {"hora": "08:00:00", "dominio": "AAA111", "tipo_identificacion": "PATENTE",
                "numero_tarjeta": None, "conductor": None}
    for columna, valor in completo.items():
        if columna not in consumo:
            consumo[columna] = valor
    padron = pd.DataFrame(flota)
    for columna in ("NumeroTarjeta", "Dominio", "NumeroMotor"):
        if columna not in padron:
            padron[columna] = None
    return {"consumo": consumo, "flota": padron,
            "solicitudes": pd.DataFrame(pedidos) if pedidos is not None else None,
            "reclamos": pd.DataFrame(reclamos) if reclamos is not None else None}


def test_el_fraccionamiento_abre_cada_banda_y_respeta_los_bordes(monkeypatch):
    """Días armados a mano: cada banda de cantidad, del tanque del día y del rendimiento, y sus bordes."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _fraccionamiento_detalle

    # C1: un día de 1 carga; C2: un día de 2; C3: un día de 3; C4: un día de 4 (borde de la 4ta banda)
    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "TipoVehiculo": "SEDAN"}]
    cargas = [
        {"id": "C1", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 100.0, "odometro": 1000},
        {"id": "C2a", "vehiculo_id": "S1", "fecha": "2024-05-11", "litros": 60.0, "odometro": 1100},
        {"id": "C2b", "vehiculo_id": "S1", "fecha": "2024-05-11", "litros": 61.0, "odometro": 1200},
        {"id": "C3a", "vehiculo_id": "S1", "fecha": "2024-05-12", "litros": 50.0, "odometro": 1300},
        {"id": "C3b", "vehiculo_id": "S1", "fecha": "2024-05-12", "litros": 50.0, "odometro": 1400},
        {"id": "C3c", "vehiculo_id": "S1", "fecha": "2024-05-12", "litros": 50.0, "odometro": 1500},
        {"id": "C4a", "vehiculo_id": "S2", "fecha": "2024-05-13", "litros": 26.0, "odometro": 2000},
        {"id": "C4b", "vehiculo_id": "S2", "fecha": "2024-05-13", "litros": 26.0, "odometro": 2100},
        {"id": "C4c", "vehiculo_id": "S2", "fecha": "2024-05-13", "litros": 26.0, "odometro": 2200},
        {"id": "C4d", "vehiculo_id": "S2", "fecha": "2024-05-13", "litros": 25.0, "odometro": 2300},
    ]
    detalle = _fraccionamiento_detalle(_datos_de_fraccionamiento(cargas, flota), None)

    assert detalle["por_cantidad_de_cargas"] == {"total": 4, "cargas_1": 1, "cargas_2": 1,
                                                 "cargas_3": 1, "cargas_4_o_mas": 1}
    assert detalle["dias_solo_con_una_carga"] == 1 and detalle["dias_con_dos_o_mas_cargas"] == 3

    # C2: 121 / 100 = 1,21 -> la banda 1,05 a 1,50; C3: 150 / 100 = 1,50 (borde, cae en esa banda);
    # C4: 103 / 100 = 1,03 (borde de la primera banda del día)
    assert detalle["litros_del_dia_sobre_la_capacidad"] == {"total": 3, "hasta_1_00": 0,
                                                             "1_00_a_1_05": 1, "1_05_a_1_50": 2,
                                                             "mas_de_1_50": 0}
    # Por tipo de vehículo, solo los días fragmentados: S1 tiene 2 y 3 cargas, S2 al menos 4
    assert detalle["fragmentados_por_tipo_de_vehiculo"] == {
        "PICK-UP": {"cargas_2": 1, "cargas_3": 1, "cargas_4_o_mas": 0},
        "SEDAN": {"cargas_2": 0, "cargas_3": 0, "cargas_4_o_mas": 1}}


def test_el_fraccionamiento_marca_los_dias_de_km_no_evaluables(monkeypatch):
    """Un día con odómetro que se repite o falta no entra al rendimiento y se cuenta aparte."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _fraccionamiento_detalle

    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "TipoVehiculo": "PICK-UP"}]
    cargas = [  # S1: km 100 (evaluable); S2: el odómetro no avanza -> no evaluable
        {"id": "A1", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 50.0, "odometro": 1000},
        {"id": "A2", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 50.0, "odometro": 1100},
        {"id": "B1", "vehiculo_id": "S2", "fecha": "2024-05-10", "litros": 50.0, "odometro": 5000},
        {"id": "B2", "vehiculo_id": "S2", "fecha": "2024-05-10", "litros": 50.0, "odometro": 5000},
    ]
    detalle = _fraccionamiento_detalle(_datos_de_fraccionamiento(cargas, flota), None)
    assert detalle["dias_con_dos_o_mas_cargas"] == 2
    assert detalle["rendimiento_del_dia"]["total"] == 1
    assert detalle["rendimiento_del_dia"]["km_no_evaluable"] == 1


def test_el_fraccionamiento_cuenta_los_pedidos_por_dia(monkeypatch):
    """Con cruce por dominio y día: un día con pedido para todas, uno para algunas y uno para ninguna."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _fraccionamiento_detalle

    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": "A1", "vehiculo_id": "S1", "fecha": "2024-05-10", "hora": "08:00:00",
               "litros": 50.0, "odometro": 1000},
              {"id": "A2", "vehiculo_id": "S1", "fecha": "2024-05-10", "hora": "18:00:00",
               "litros": 50.0, "odometro": 1100},
              {"id": "B1", "vehiculo_id": "S1", "fecha": "2024-05-11", "hora": "08:00:00",
               "litros": 50.0, "odometro": 1200},
              {"id": "B2", "vehiculo_id": "S1", "fecha": "2024-05-11", "hora": "18:00:00",
               "litros": 50.0, "odometro": 1300},
              {"id": "C1", "vehiculo_id": "S1", "fecha": "2024-05-12", "hora": "08:00:00",
               "litros": 50.0, "odometro": 1400},
              {"id": "C2", "vehiculo_id": "S1", "fecha": "2024-05-12", "hora": "18:00:00",
               "litros": 50.0, "odometro": 1500}]
    pedidos = [{"id": "P-A1", "vehiculo_id": "S1", "dominio": "AAA111", "fecha": "2024-05-10", "hora": "08:00:00",
                "litros_cargados": 50.0, "litros_autorizados": 50.0, "rendido": "SI", "anulado": "NO",
                "tarjeta_personal": False, "estacion_servicio": "ESTACION UNO", "solicitante": "1",
                "bandera_rendicion": "Verde", "nivel_tanque": "TANQUE LLENO"},
               {"id": "P-A2", "vehiculo_id": "S1", "dominio": "AAA111", "fecha": "2024-05-10", "hora": "18:00:00",
                "litros_cargados": 50.0, "litros_autorizados": 60.0, "rendido": "SI", "anulado": "NO",
                "tarjeta_personal": False, "estacion_servicio": "ESTACION UNO", "solicitante": "1",
                "bandera_rendicion": "Amarillo", "nivel_tanque": "1/2 TANQUE"},
               {"id": "P-B1", "vehiculo_id": "S1", "dominio": "AAA111", "fecha": "2024-05-11", "hora": "08:00:00",
                "litros_cargados": 50.0, "litros_autorizados": 50.0, "rendido": "SI", "anulado": "NO",
                "tarjeta_personal": False, "estacion_servicio": "ESTACION UNO", "solicitante": "1",
                "bandera_rendicion": "Verde", "nivel_tanque": "TANQUE LLENO"}]
    datos = _datos_de_fraccionamiento(cargas, flota, pedidos=pedidos)
    detalle = _fraccionamiento_detalle(datos, None)
    assert detalle["pedido_para"]["total"] == 3
    assert detalle["pedido_para"]["para_todas_las_cargas"] == 1     # el día de A
    assert detalle["pedido_para"]["para_algunas_cargas"] == 1       # el día de B (uno de dos)
    assert detalle["pedido_para"]["para_ninguna_carga"] == 1        # el día de C


def test_el_fraccionamiento_informa_no_disponible_si_falta_la_columna(monkeypatch):
    """Sin las columnas de bandera y nivel en el registro, (e) sale `no_disponible` y el bloque sigue."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _fraccionamiento_detalle

    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": "A1", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 50.0, "odometro": 1000},
              {"id": "A2", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 50.0, "odometro": 1100}]
    sin_columnas = [{"id": "P-A1", "vehiculo_id": "S1", "dominio": "AAA111", "fecha": "2024-05-10",
                     "hora": "08:00:00", "litros_cargados": 50.0, "litros_autorizados": 50.0,
                     "rendido": "SI", "anulado": "NO", "tarjeta_personal": False,
                     "estacion_servicio": "ESTACION UNO", "solicitante": "1"}]
    detalle = _fraccionamiento_detalle(_datos_de_fraccionamiento(cargas, flota, pedidos=sin_columnas), None)
    assert detalle["bandera_de_rendicion"] == "no_disponible"
    assert detalle["nivel_del_tanque"] == "no_disponible"
    assert detalle["km_por_hora_de_motor"] == "no_disponible"


def test_el_fraccionamiento_no_publica_un_entero_del_1_al_19_ni_deja_restarlo(sintetico):
    """El bloque real, en agregado: ningún entero de 1 a 19 suelto y ninguna resta lo recupera."""
    bloque = auditar(con_forma_real(sintetico), proveedor="proveedor zeta", semillas=(1001,),
                     solo="fraccionamiento_detalle")["diagnostico"]["fraccionamiento_detalle"]
    assert "error" not in bloque
    chicos = _enteros_chicos_del_detalle(bloque)
    assert not chicos, "\n".join(chicos)
    malos = _residuos_chicos({"fraccionamiento_detalle": bloque})
    assert not malos, "\n".join(malos)


def _datos_de_causa(cargas, flota, pedidos=None, alertas=None):
    """Un `datos` con lo justo para el bloque de causa del exceso, con las columnas que lee el adaptador."""
    consumo = pd.DataFrame(cargas)
    completo = {"hora": "08:00:00", "dominio": "AAA111", "tipo_identificacion": "PATENTE",
                "numero_tarjeta": None, "conductor": None, "odometro": None}
    for columna, valor in completo.items():
        if columna not in consumo:
            consumo[columna] = valor
    padron = pd.DataFrame(flota)
    for columna in ("NumeroTarjeta", "Dominio", "NumeroMotor", "Marca", "Modelo", "TipoVehiculo"):
        if columna not in padron:
            padron[columna] = None
    return {"consumo": consumo, "flota": padron,
            "solicitudes": pd.DataFrame(pedidos) if pedidos is not None else None,
            "reclamos": None, "alertas": pd.DataFrame(alertas) if alertas is not None else None}


def test_la_causa_del_exceso_clasifica_por_capacidad_del_padron(monkeypatch):
    """Un vehículo muy apartado de la mediana de sus pares va a capacidad del padrón inconsistente."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_por_causa

    # S1 registra 50 L pero sus pares (mismo marca+modelo) tienen 100 L: se aparta 50 % (inconsistente).
    # Sus cargas exceden el 2 % en forma repetida y de cociente parecido.
    flota = [{"Matricula": "S1", "CapacidadTanque": 50.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S3", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S4", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": f"S1-{i}", "vehiculo_id": "S1", "fecha": f"2024-05-{10 + i:02d}", "litros": 52.0}
              for i in range(4)]
    cargas += [{"id": f"S2-{i}", "vehiculo_id": "S2", "fecha": f"2024-05-{10 + i:02d}", "litros": 50.0}
               for i in range(4)]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert bloque["por_categoria"]["total"] == 1
    assert bloque["por_categoria"]["capacidad_del_padron_inconsistente"] == 1
    assert bloque["por_categoria"]["error_de_vinculacion"] == 0


def test_la_causa_del_exceso_marca_el_error_de_vinculacion(monkeypatch):
    """La misma tarjeta cargando a dos vehículos el mismo día es error de vinculación."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_por_causa

    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": "S1-a", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 130.0, "numero_tarjeta": "T-9"},
              {"id": "S2-a", "vehiculo_id": "S2", "fecha": "2024-05-10", "litros": 130.0, "numero_tarjeta": "T-9"}]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert bloque["por_categoria"]["error_de_vinculacion"] == 2


def test_la_causa_del_exceso_marca_el_exceso_repetido_con_capacidad_consistente(monkeypatch):
    """Coincide con sus pares pero excede en forma repetida: capacidad consistente con exceso repetido."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_por_causa

    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S3", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": f"S1-{i}", "vehiculo_id": "S1", "fecha": f"2024-05-{10 + i:02d}", "litros": 103.0}
              for i in range(4)]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert bloque["por_categoria"]["capacidad_consistente_con_exceso_repetido"] == 1


def test_la_causa_del_exceso_marca_el_exceso_aislado(monkeypatch):
    """Una sola carga con exceso y cociente irregular, sin explicación: exceso aislado."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_por_causa

    flota = [{"Matricula": "S1", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S3", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": "S1-0", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 130.0},
              {"id": "S1-1", "vehiculo_id": "S1", "fecha": "2024-05-11", "litros": 50.0}]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert bloque["por_categoria"]["exceso_aislado"] == 1


def test_la_causa_del_exceso_marca_no_evaluable_sin_capacidad(monkeypatch):
    """Sin capacidad en el padrón no se puede evaluar: no evaluable, y el bloque sigue."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_por_causa

    flota = [{"Matricula": "S1", "CapacidadTanque": None, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": None, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": "S1-0", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 130.0}]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert "error" not in bloque
    assert bloque["por_categoria"]["total"] == 1
    assert bloque["por_categoria"]["no_evaluable"] == 1


def test_la_causa_del_exceso_resume_explicados_y_no_explicados(monkeypatch):
    """El resumen junta las categorías 1 y 2 como explicados y las 3, 4 y 5 como no explicados."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 1)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 1)
    from perfilador.auditoria import _exceso_por_causa

    flota = [{"Matricula": "S1", "CapacidadTanque": 50.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S2", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S3", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S4", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"},
             {"Matricula": "S5", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}]
    cargas = [{"id": "S1-a", "vehiculo_id": "S1", "fecha": "2024-05-10", "litros": 52.0},
              {"id": "S2-a", "vehiculo_id": "S2", "fecha": "2024-05-10", "litros": 130.0},
              {"id": "S2-b", "vehiculo_id": "S2", "fecha": "2024-05-11", "litros": 50.0}]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert bloque["resumen"]["explicados"] == 1
    assert bloque["resumen"]["no_explicados"] == 1


def _restas_de_las_causas(bloque):
    """Restas entre las tres vistas del bloque que podrían revelar un grupo de 1 a 19.

    Las vistas salen del mismo conteo y se solapan: total menos cualquier suma de partes visibles de la
    misma unidad (por categoría de vehículos, por categoría de cargas y el resumen), y el total de una
    vista menos la clave de esa categoría en la otra.
    """
    chicas = []
    de_vehiculos = bloque["por_categoria"]
    de_cargas = bloque["cargas_por_categoria"]
    resumen = bloque["resumen"]
    vistas = {"por_categoria": (de_vehiculos["total"], de_vehiculos),
              "cargas_por_categoria": (de_cargas["total"], de_cargas),
              "resumen": (resumen["total"], resumen)}
    for nombre, (total, vista) in vistas.items():
        if not isinstance(total, int) or isinstance(total, bool):
            continue
        visibles = [valor for clave, valor in vista.items()
                    if clave != "total" and isinstance(valor, int) and not isinstance(valor, bool)]
        for combinacion in range(1 << len(visibles)):
            suma = sum(v for indice, v in enumerate(visibles) if combinacion & (1 << indice))
            if 0 < total - suma < 20:
                chicas.append(f"{nombre}.total - partes = {total - suma}")
    for clave in bloque["por_categoria"]:
        if clave == "total":
            continue
        en_vehiculos = de_vehiculos[clave]
        en_cargas = de_cargas[clave]
        if isinstance(en_vehiculos, int) and isinstance(en_cargas, int):
            if 0 < en_vehiculos - en_cargas < 20:
                chicas.append(f"por_categoria.{clave} - cargas_por_categoria.{clave} = {en_vehiculos - en_cargas}")
    return chicas


def test_la_causa_del_exceso_no_deja_restar_entre_sus_vistas(monkeypatch):
    """Con explicados chico y no explicados grande, ninguna resta entre vistas revela el grupo chico."""
    monkeypatch.setattr("perfilador.controles.MINIMO_GRUPO", 20)
    monkeypatch.setattr("perfilador.auditoria.MINIMO_GRUPO", 20)
    from perfilador.auditoria import _exceso_por_causa

    # Un vehículo aislado (explicados = 0) y 21 vehículos con exceso aislado (no explicados = 21)
    flota = [{"Matricula": f"S{i}", "CapacidadTanque": 100.0, "Marca": "M", "Modelo": "X", "TipoVehiculo": "PICK-UP"}
             for i in range(30)]
    cargas = [{"id": f"S{i}-0", "vehiculo_id": f"S{i}", "fecha": "2024-05-10", "litros": 130.0}
              for i in range(21)]
    cargas += [{"id": "S29-0", "vehiculo_id": "S29", "fecha": "2024-05-10", "litros": 130.0},
               {"id": "S29-1", "vehiculo_id": "S29", "fecha": "2024-05-11", "litros": 50.0}]
    bloque = _exceso_por_causa(_datos_de_causa(cargas, flota), None)
    assert "error" not in bloque
    chicas = _restas_de_las_causas(bloque)
    assert not chicas, "\n".join(chicas)


def test_la_causa_del_exceso_no_publica_un_entero_del_1_al_19(sintetico):
    """El bloque real, en agregado: ningún entero de 1 a 19 suelto ni recuperable por resta."""
    bloque = auditar(con_forma_real(sintetico), proveedor="proveedor zeta", semillas=(1001,),
                     solo="exceso_por_causa")["diagnostico"]["exceso_por_causa"]
    assert "error" not in bloque
    chicos = _enteros_chicos_del_detalle(bloque)
    assert not chicos, "\n".join(chicos)
    malos = _residuos_chicos({"exceso_por_causa": bloque}) + _restas_de_las_causas(bloque)
    assert not malos, "\n".join(malos)

