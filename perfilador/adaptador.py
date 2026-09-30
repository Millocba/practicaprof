"""Traduce las fuentes reales al esquema del generador, en memoria, para correr las reglas y los
modelos junto a los datos.

Cada fuente se reconoce por sus columnas, no por el nombre del archivo o de la tabla. Nada de lo
que se traduce sale del entorno: solo los agregados que arma `perfilador.auditoria`.

Las fuentes que faltan (ubicación de las estaciones, recorrido diario del GPS, fecha del cambio de
estado de los vehículos, transferencias de saldo) se dejan vacías y las reglas que las necesitan
no corren; el diagnóstico lo informa.
"""
import re

import pandas as pd

from deteccion.reglas import GRUPO_DEPOSITO
from perfilador.controles import acotar, leer_fecha_texto
from perfilador.perfil import _normalizar_valor

ESTACION_AJENA = "ESTACION AJENA"
FIRMAS = {
    "padron": {"Matricula", "Dominio", "CapacidadTanque", "NumeroTarjeta", "Estado"},
    "consumo": {"LITROS UNIDADES", "TIPO IDENTIFICACION TARJETA", "REMITO", "FECHA"},
    "registro": {"Rendido", "Anulado", "LitrosAutorizados", "Solicitante", "Fecha", "Hora"},
    "dispositivos": {"Placa", "Grupo", "IMEI"},
    "facturas": {"numero", "numero_contrato", "monto_facturado"},
    "transacciones_facturadas": {"factura_id", "remito", "importe_yer"},
    "contratos": {"numero", "limite"},
    "periodos": {"id", "fecha_inicio", "fecha_fin"},
    "excepciones_odometro": {"patente", "motivo", "activo", "fecha_hasta"},
    "reclamos": {"tipo_alerta", "estado_reclamo", "monto_reclamable", "nro_ticket"},
}
HASTA_SIN_FECHA = "2100-01-01"   # una excepción activa sin fecha hasta rige indefinidamente
MINUTOS_VINCULO_RECLAMO = 15     # un reclamo sin ticket se vincula con la carga del vehículo más cercana en el tiempo

# Tipos y estados de los reclamos, por palabras clave: cualquier otro valor queda como "otro", para
# que ningún texto de la fuente llegue a la salida
# En la fuente, el doble cobro se llama duplicidad_metodo (el medio habitual y la contingencia)
TIPOS_RECLAMO = {"doble_cobro": ("doble", "duplicidad"), "cargas_multiples": ("multiple",),
                 "odometro_estancado": ("odometro",)}
ESTADOS_RECLAMO = {"pendiente": ("pend",), "en_disputa": ("disput",), "nota_de_credito": ("nota", "credito"),
                   "rechazado": ("rechaz",)}


def _categoria(serie, categorias):
    """Cada valor en la primera categoría cuyas palabras clave contiene (sin acentos ni mayúsculas), o "otro"."""
    texto = (serie.astype("string").str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
             .str.lower().fillna(""))
    resultado = pd.Series("otro", index=serie.index, dtype="string")
    for nombre, claves in reversed(list(categorias.items())):
        resultado = resultado.mask(texto.apply(lambda t: any(c in t for c in claves)), nombre)
    return resultado


def _reclamos(fuente, consumo, por_dominio):
    """Tipo, estado, monto y la carga de cada reclamo; ni el mensaje ni los números de reclamo se copian.

    Se vincula por el ticket, que es el REMITO del reporte; si falta, por el vehículo (patente o
    matrícula) y la carga más cercana a la fecha y hora del reclamo, a menos de MINUTOS_VINCULO_RECLAMO.
    Las cargas con tarjeta personal no tienen vehículo en el reporte: esas se buscan por la tarjeta.
    El ticket puede traer el remito entero (9999-99999999) o solo su segunda parte, y llegar como
    número decimal (1234.0) cuando la columna tiene muchos vacíos.
    """
    base = consumo["id"].str.split("#").str[0]

    def sin_ceros(digitos):
        # Un ticket que llegó como número perdió los ceros de adelante: se comparan sin ellos
        return digitos.str.lstrip("0").replace({"": pd.NA})

    def mapa(claves, repetidas):
        m = pd.Series(consumo["id"].values, index=sin_ceros(claves).values)
        return m[~m.index.isna() & ~m.index.duplicated(keep=repetidas)]

    ticket = sin_ceros(_digitos(_texto(fuente["nro_ticket"])))
    # Un remito repetido en el reporte va con su primera carga; una segunda parte que comparten dos
    # remitos distintos es ambigua y no se usa
    carga = ticket.map(mapa(_digitos(base), "first")).fillna(
        ticket.map(mapa(_digitos(base.str.split("-").str[-1]), False)))
    vinculo = pd.Series(pd.NA, index=fuente.index, dtype="string").mask(carga.notna(), "ticket")

    matricula = fuente["patente"].astype("string").map(
        lambda d: _normalizar_valor(d) if pd.notna(d) else None).map(por_dominio["Matricula"])
    if "matricula" in fuente.columns:
        matricula = matricula.fillna(_texto(fuente["matricula"]))
    instante = leer_fecha_texto(fuente["fecha_hora"]) if "fecha_hora" in fuente.columns else pd.Series(pd.NaT, index=fuente.index)
    tarjeta = _texto(fuente["numero_tarjeta"]) if "numero_tarjeta" in fuente.columns else pd.Series(pd.NA, index=fuente.index)
    cargas = consumo.assign(instante=pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(consumo["hora"]))
    for clave, valores, nombre in [("vehiculo_id", matricula, "patente_y_hora"),
                                   ("numero_tarjeta", tarjeta, "tarjeta_y_hora")]:
        pendientes = pd.DataFrame({"fila": fuente.index, clave: valores.astype("string").values,
                                   "instante": instante.values})
        pendientes = pendientes[carga.isna().values].dropna(subset=[clave, "instante"])
        if not len(pendientes) or clave not in cargas.columns:
            continue
        destino = cargas[["id", clave, "instante"]].dropna().astype({clave: "string"}).sort_values("instante")
        cercana = pd.merge_asof(pendientes.sort_values("instante"), destino, on="instante", by=clave,
                                direction="nearest", tolerance=pd.Timedelta(minutes=MINUTOS_VINCULO_RECLAMO))
        encontradas = cercana.set_index("fila")["id"].dropna()
        carga.loc[encontradas.index] = encontradas
        vinculo.loc[encontradas.index] = nombre
    return pd.DataFrame({
        "tipo": _categoria(fuente["tipo_alerta"], TIPOS_RECLAMO),
        "estado": _categoria(fuente["estado_reclamo"], ESTADOS_RECLAMO),
        "monto": _numero(fuente["monto_reclamable"]), "carga_id": carga, "vinculo": vinculo,
        # Solo para acotar el período que cubren los reclamos; no sale en la auditoría
        "fecha": (leer_fecha_texto(fuente["dia"]) if "dia" in fuente.columns else instante).fillna(instante).dt.normalize(),
    })


def _texto(serie):
    """Texto limpio, sin el '.0' de los números leídos como decimales."""
    return serie.astype("string").str.strip().str.replace(r"\.0$", "", regex=True).replace({"": pd.NA, "nan": pd.NA})


def _numero(serie):
    return pd.to_numeric(serie, errors="coerce")


def _digitos(serie):
    return serie.astype("string").str.replace(r"\D", "", regex=True).replace({"": pd.NA})


def buscar(tablas, fuente):
    """La tabla con las columnas de `fuente` y la menor cantidad de columnas (la más cruda), o None."""
    firma = FIRMAS[fuente]
    candidatas = [(len(df.columns), nombre) for nombre, df in tablas.items() if firma <= set(map(str, df.columns))]
    return tablas[min(candidatas)[1]] if candidatas else None


def adaptar(tablas, proveedor=None):
    """Devuelve (datos con el esquema del generador, diagnóstico) a partir de las tablas reales."""
    diagnostico = {"fuentes_encontradas": [f for f in FIRMAS if buscar(tablas, f) is not None]}
    padron = buscar(tablas, "padron")
    if padron is None:
        raise ValueError("no se encontró el padrón de la flota")
    flota = pd.DataFrame({
        "Matricula": _texto(padron["Matricula"]), "Dominio": _texto(padron["Dominio"]),
        "Estado": padron["Estado"].astype("string").str.strip().str.upper(),
        "SubEstado": padron.get("SubEstado"), "TipoVehiculo": padron.get("TipoVehiculo"),
        "TipoCombustible": padron.get("TipoCombustible"),
        "CapacidadTanque": _numero(padron["CapacidadTanque"]).where(lambda s: s > 0),
        "NumeroTarjeta": _texto(padron["NumeroTarjeta"]), "NumeroContrato": _numero(padron.get("NumeroContrato")),
        "Dependencia": padron.get("Dependencia"), "DireccionGral": padron.get("DireccionGral"),
        "FechaEstado": pd.NaT,     # la fuente no trae la fecha del cambio de estado
        "ExcepcionOdometro": padron.get("ExcepcionOdometro"),
        "FechaHastaExcepcionOdometro": padron.get("FechaHastaExcepcionOdometro"),
    }).dropna(subset=["Matricula"]).drop_duplicates("Matricula")
    por_tarjeta = flota.dropna(subset=["NumeroTarjeta"]).drop_duplicates("NumeroTarjeta").set_index("NumeroTarjeta")
    por_dominio = flota.assign(clave=flota["Dominio"].map(lambda d: _normalizar_valor(d) if pd.notna(d) else None)
                               ).dropna(subset=["clave"]).drop_duplicates("clave").set_index("clave")

    datos = {"flota": flota, "estaciones": None, "telemetria_diaria": None, "transferencias": None}
    fuente = buscar(tablas, "consumo")
    if fuente is not None:
        instante = pd.to_datetime(fuente["FECHA"].astype("string").str.strip(), format="%d/%m/%Y %H:%M:%S",
                                  errors="coerce")
        personal = fuente["TIPO IDENTIFICACION TARJETA"].astype("string").str.upper().str.contains("DNI", na=False)
        identificacion = _texto(fuente["IDENTIFICACION TARJETA"])
        tarjeta = _texto(fuente["TARJETA"])
        dominio = identificacion.where(~personal)
        matricula = tarjeta.map(por_tarjeta["Matricula"]).fillna(
            dominio.map(lambda d: _normalizar_valor(d) if pd.notna(d) else None).map(por_dominio["Matricula"]))
        remito = _texto(fuente["REMITO"])
        # POSNET (medio de pago habitual) o CONTINGENCIA; vacío si el reporte no trae el origen
        origen = fuente["ORIGEN DE TRANSACCION"].astype("string").str.strip().str.upper() \
            if "ORIGEN DE TRANSACCION" in fuente.columns else pd.Series(pd.NA, index=fuente.index, dtype="string")
        repeticion = remito.groupby(remito).cumcount()
        consumo = pd.DataFrame({
            "id": remito.where(repeticion == 0, remito + "#" + (repeticion + 1).astype(str)),
            "vehiculo_id": matricula, "dominio": dominio,
            "fecha": instante.dt.strftime("%Y-%m-%d"), "hora": instante.dt.strftime("%H:%M:%S"),
            "estacion": fuente["ESTABLECIMIENTO"].astype("string").str.extract(r"^(\d+)", expand=False),
            "producto": fuente["PRODUCTO"], "litros": _numero(fuente["LITROS UNIDADES"]),
            "precio_unitario": _numero(fuente["PRECIO PVP ESTABLECIMIENTO"]),
            "importe_total": _numero(fuente["IMP TOT PVP ESTABLECIMIENTO"]),
            "numero_tarjeta": tarjeta,
            # La persona se identifica por su documento, para cruzarla con el registro interno
            "conductor": _digitos(identificacion.where(personal, _texto(fuente.get(
                "NRO IDENTIFICACION CONDUCTOR", pd.Series(pd.NA, index=fuente.index))))),
            "odometro": _numero(fuente["ODOMETRO"]).round().astype("Int64"),
            "tipo_identificacion": personal.map({True: "DNI", False: "PATENTE"}),
            "origen_transaccion": origen,
            "contrato": matricula.map(flota.set_index("Matricula")["NumeroContrato"]).astype("Int64"),
        }).dropna(subset=["fecha", "litros"])
        datos["consumo"] = consumo[consumo["litros"] > 0]
        diagnostico["consumo"] = {
            "fechas_legibles_pct": round(100 * instante.notna().mean(), 1),
            "con_vehiculo_del_padron_pct": round(100 * consumo["vehiculo_id"].notna().mean(), 1),
            "con_contrato_pct": round(100 * consumo["contrato"].notna().mean(), 1),
            "tarjetas_personales_pct": round(100 * personal.mean(), 1),
            "contingencias_pct": round(100 * (origen == "CONTINGENCIA").mean(), 1) if origen.notna().any() else None,
        }
    else:
        raise ValueError("no se encontró el reporte de consumo del proveedor")

    registro = buscar(tablas, "registro")
    if registro is not None:
        estacion = registro.get("EstacionServicio", pd.Series(pd.NA, index=registro.index)).astype("string")
        if proveedor:
            ajena = estacion.notna() & (estacion.str.strip() != "") & ~estacion.str.contains(
                re.escape(proveedor), case=False, na=False)
            estacion = estacion.where(~ajena, ESTACION_AJENA)
        datos["solicitudes"] = pd.DataFrame({
            "id": _texto(registro["Id"]), "vehiculo_id": _texto(registro["Matricula"]),
            "dominio": _texto(registro["Dominio"]), "fecha": registro["Fecha"].astype("string").str.strip(),
            "hora": registro["Hora"].astype("string").str.strip(), "odometro": _numero(registro.get("OdometroRegistrado")),
            "solicitante": registro["Solicitante"].astype("string").str.extract(r"DNI:\s*(\d+)", expand=False),
            "tarjeta_personal": registro.get("TarjetaDni", pd.Series(False, index=registro.index))
            .astype("string").str.upper().isin(["TRUE", "SI", "1"]),
            "litros_autorizados": _numero(registro["LitrosAutorizados"]),
            "litros_cargados": _numero(registro.get("LitrosCargados")),
            "rendido": registro["Rendido"].astype("string").str.strip().str.upper(),
            "anulado": registro["Anulado"].astype("string").str.strip().str.upper(),
            "estacion_servicio": estacion,
        })
        diagnostico["registro"] = {"con_proveedor_informado": bool(proveedor),
                                   "estaciones_de_otra_red_pct": round(100 * (estacion == ESTACION_AJENA).mean(), 1)}

    contratos = buscar(tablas, "contratos")
    if contratos is not None:
        ordenados = contratos.assign(numero=_texto(contratos["numero"])).sort_values("numero").reset_index(drop=True)
        datos["contratos"] = pd.DataFrame({"indice": range(1, len(ordenados) + 1), "numero": ordenados["numero"],
                                           "limite_mensual": _numero(ordenados["limite"])})
    facturas, transacciones = buscar(tablas, "facturas"), buscar(tablas, "transacciones_facturadas")
    if facturas is not None and transacciones is not None and contratos is not None:
        indice = datos["contratos"].set_index("numero")["indice"]
        periodos = buscar(tablas, "periodos")
        mes = pd.Series(pd.NA, index=facturas.index, dtype="string")
        if periodos is not None and "periodo_id" in facturas.columns:
            inicio = pd.to_datetime(periodos.set_index(periodos["id"])["fecha_inicio"], errors="coerce")
            mes = facturas["periodo_id"].map(inicio).dt.strftime("%Y-%m").astype("string")
        pdf = _numero(facturas.get("pdf_total"))
        datos["facturacion"] = pd.DataFrame({
            "numero_factura": _texto(facturas["numero"]), "contrato": _texto(facturas["numero_contrato"]).map(indice),
            "periodo": mes, "total_monto": _numero(facturas["monto_facturado"]),
            "total_pdf": pdf.where(pdf > 0),
        })
        numero_de = pd.Series(_texto(facturas["numero"]).values, index=facturas["id"])
        litros = _numero(transacciones.get("litros"))
        importe = _numero(transacciones["importe_yer"])
        combustible = _numero(transacciones.get("es_combustible")).fillna(1) == 1
        datos["facturacion_detalle"] = pd.DataFrame({
            "numero_linea": "T" + _texto(transacciones["id"]), "numero_factura": transacciones["factura_id"].map(numero_de),
            "referencia_consumo": _texto(transacciones["remito"]),
            "concepto": combustible.map({True: "COMBUSTIBLE", False: "OTRO"}),
            "litros": litros, "precio_unitario": (importe / litros).round(2), "importe": importe,
        }).dropna(subset=["numero_factura"])
        diagnostico["facturacion"] = {
            "facturas_con_periodo_pct": round(100 * datos["facturacion"]["periodo"].notna().mean(), 1),
            "facturas_con_contrato_pct": round(100 * datos["facturacion"]["contrato"].notna().mean(), 1),
            "lineas_con_carga_del_reporte_pct": round(
                100 * datos["facturacion_detalle"]["referencia_consumo"].isin(datos["consumo"]["id"]).mean(), 1),
        }

    excepciones = buscar(tablas, "excepciones_odometro")
    if excepciones is not None:
        def dia(serie):
            return pd.to_datetime(serie.astype("string").str.strip(), errors="coerce", format="mixed",
                                  dayfirst=True).dt.strftime("%Y-%m-%d")
        activo = excepciones["activo"].astype("string").str.strip().str.upper().isin(["SI", "1", "TRUE"])
        hasta = dia(excepciones["fecha_hasta"])
        datos["excepciones_odometro"] = pd.DataFrame({
            "patente": _texto(excepciones["patente"]),
            "activo": activo.map({True: "SI", False: "NO"}),
            "fecha_creacion": dia(excepciones.get("fecha_creacion", pd.Series(pd.NA, index=excepciones.index))
                                  ).fillna("1900-01-01"),
            "fecha_hasta": hasta.where(hasta.notna() | ~activo, HASTA_SIN_FECHA),
        })
        diagnostico["excepciones_odometro"] = {
            "excepciones": acotar(len(excepciones)),
            "con_vehiculo_del_padron_pct": round(100 * datos["excepciones_odometro"]["patente"].map(
                lambda d: _normalizar_valor(d) if pd.notna(d) else None).isin(por_dominio.index).mean(), 1),
        }

    reclamos = buscar(tablas, "reclamos")
    if reclamos is not None:
        datos["reclamos"] = _reclamos(reclamos, datos["consumo"], por_dominio)

    dispositivos = buscar(tablas, "dispositivos")
    if dispositivos is not None:
        grupo = dispositivos["Grupo"].astype("string")
        ultima = leer_fecha_texto(dispositivos.get("Hora de última transmisión",
                                                   pd.Series(pd.NA, index=dispositivos.index)))
        datos["telemetria"] = pd.DataFrame({
            "IMEI": _texto(dispositivos["IMEI"]), "Alias": _texto(dispositivos.get("Alias", dispositivos["IMEI"])),
            "Placa": _texto(dispositivos["Placa"]),
            "Grupo": grupo.where(~grupo.str.upper().str.contains("BAJA|REEMPLAZ|DEPOSITO|DEPÓSITO", na=False),
                                 GRUPO_DEPOSITO),
            "UltimaConexion": ultima.dt.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        diagnostico["telemetria"] = {"fechas_de_transmision_legibles_pct": round(100 * ultima.notna().mean(), 1)}

    diagnostico["no_disponible"] = {
        "ubicacion_de_estaciones": "H7 no corre",
        "recorrido_diario_gps": "H5 con GPS y la confirmación por GPS de H2c no corren",
        "fecha_del_cambio_de_estado": "H6 no corre",
        "transferencias_de_saldo": "H10 no corre",
    }
    return datos, diagnostico
