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
from perfilador.controles import leer_fecha_texto
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
}


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
            "conductor": _digitos(identificacion.where(personal, fuente.get("NRO IDENTIFICACION CONDUCTOR"))),
            "odometro": _numero(fuente["ODOMETRO"]).round().astype("Int64"),
            "tipo_identificacion": personal.map({True: "DNI", False: "PATENTE"}),
            "contrato": matricula.map(flota.set_index("Matricula")["NumeroContrato"]).astype("Int64"),
        }).dropna(subset=["fecha", "litros"])
        datos["consumo"] = consumo[consumo["litros"] > 0]
        diagnostico["consumo"] = {
            "fechas_legibles_pct": round(100 * instante.notna().mean(), 1),
            "con_vehiculo_del_padron_pct": round(100 * consumo["vehiculo_id"].notna().mean(), 1),
            "con_contrato_pct": round(100 * consumo["contrato"].notna().mean(), 1),
            "tarjetas_personales_pct": round(100 * personal.mean(), 1),
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
