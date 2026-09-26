"""Carga de un dataset del escenario realista en la base, repetible e incremental.

Cada fila se inserta o se actualiza por su clave (`INSERT ... ON CONFLICT DO UPDATE`): cargar dos
veces el mismo dataset no duplica nada. Con `hasta`, los datos operativos se cargan solo hasta
esa fecha, como una carga diaria; una carga posterior agrega lo que falta. Los maestros se cargan
completos, con sus vigencias.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from deteccion.datos import cargar_dataset
from deteccion.reglas import leer_fecha

DESDE_SIEMPRE = "1900-01-01"
TABLAS = ["contrato", "dependencia", "vehiculo", "estado_vehiculo", "tarjeta", "asignacion_tarjeta", "estacion",
          "dispositivo", "asignacion_dispositivo", "carga", "pedido", "transferencia", "factura", "factura_linea",
          "posicion_diaria"]
CLAVES = {
    "contrato": ["indice"], "dependencia": ["codigo"], "vehiculo": ["matricula"],
    "estado_vehiculo": ["matricula", "estado", "desde"], "tarjeta": ["numero"],
    "asignacion_tarjeta": ["tarjeta", "desde"], "estacion": ["codigo"], "dispositivo": ["alias"],
    "asignacion_dispositivo": ["dispositivo", "desde"], "carga": ["id"], "pedido": ["id"],
    "transferencia": ["id"], "factura": ["numero"], "factura_linea": ["numero_linea"],
    "posicion_diaria": ["matricula", "fecha"],
}


def _fecha_iso(serie):
    return leer_fecha(serie).dt.strftime("%Y-%m-%d").where(serie.notna(), None)


def tablas_de_la_base(datos):
    """Transforma el dataset del generador ({nombre: DataFrame}) en las tablas de la base."""
    flota, consumo = datos["flota"], datos["consumo"]
    matricula_de = flota.set_index("Dominio")["Matricula"]
    t = {}
    t["contrato"] = datos["contratos"][["indice", "numero", "etiqueta", "limite_mensual"]]
    t["dependencia"] = (flota[["Dependencia", "DireccionGral"]].drop_duplicates("Dependencia")
                        .rename(columns={"Dependencia": "codigo", "DireccionGral": "direccion_general"}))
    t["vehiculo"] = flota.rename(columns={
        "Matricula": "matricula", "Dominio": "dominio", "TipoVehiculo": "tipo", "Marca": "marca", "Modelo": "modelo",
        "Año": "anio", "TipoCombustible": "combustible", "CapacidadTanque": "capacidad_tanque",
        "Identificable": "identificable", "Dependencia": "dependencia"})[
        ["matricula", "dominio", "tipo", "marca", "modelo", "anio", "combustible", "capacidad_tanque",
         "identificable", "dependencia"]]
    estados = []
    for v in flota.itertuples():
        cambio = None if pd.isna(v.FechaEstado) else str(v.FechaEstado)[:10]
        if cambio:
            estados.append((v.Matricula, "EN SERVICIO", None, DESDE_SIEMPRE, cambio))
        estados.append((v.Matricula, v.Estado, None if pd.isna(v.SubEstado) else v.SubEstado,
                        cambio or DESDE_SIEMPRE, None))
    t["estado_vehiculo"] = pd.DataFrame(estados, columns=["matricula", "estado", "subestado", "desde", "hasta"])

    de_vehiculo = flota.rename(columns={"NumeroTarjeta": "numero", "NumeroContrato": "contrato", "Cupo": "cupo_litros",
                                        "LimiteLitros": "limite_litros", "LimiteSaldo": "limite_saldo"}).assign(
        tipo="VEHICULO")
    personales = (consumo[consumo["tipo_identificacion"] == "DNI"].drop_duplicates("numero_tarjeta")
                  .rename(columns={"numero_tarjeta": "numero"}).assign(tipo="PERSONAL"))
    t["tarjeta"] = pd.concat([de_vehiculo[["numero", "tipo", "contrato", "cupo_litros", "limite_litros", "limite_saldo"]],
                              personales[["numero", "tipo", "contrato"]]], ignore_index=True)
    t["asignacion_tarjeta"] = pd.concat([
        de_vehiculo.assign(tarjeta=de_vehiculo["numero"], matricula=de_vehiculo["Matricula"], persona=None),
        personales.assign(tarjeta=personales["numero"], matricula=None, persona=personales["conductor"]),
    ], ignore_index=True).assign(desde=DESDE_SIEMPRE, hasta=None)[["tarjeta", "matricula", "persona", "desde", "hasta"]]
    t["estacion"] = datos["estaciones"][["codigo", "marca", "ubicacion", "latitud", "longitud"]]

    telemetria = datos["telemetria"]
    t["dispositivo"] = telemetria.rename(columns={
        "Alias": "alias", "IMEI": "imei", "MSISDN": "msisdn", "Modelo": "modelo", "Grupo": "grupo", "Estado": "estado",
        "UltimaConexion": "ultima_conexion", "Bateria": "bateria"})[
        ["alias", "imei", "msisdn", "modelo", "grupo", "estado", "ultima_conexion", "bateria"]].astype(
        {"imei": str, "msisdn": str})
    t["asignacion_dispositivo"] = pd.DataFrame({
        "dispositivo": telemetria["Alias"], "matricula": telemetria["Placa"].map(matricula_de),
        "desde": DESDE_SIEMPRE, "hasta": None})

    t["carga"] = consumo.rename(columns={
        "numero_tarjeta": "tarjeta", "vehiculo_id": "matricula", "dominio": "dominio_informado",
        "importe_total": "importe"})[
        ["id", "fecha", "hora", "tarjeta", "matricula", "tipo_identificacion", "dominio_informado", "conductor",
         "estacion", "producto", "litros", "precio_unitario", "importe", "odometro", "contrato"]]
    registro = datos["solicitudes"]
    t["pedido"] = registro.rename(columns={"vehiculo_id": "matricula"}).assign(
        fecha=_fecha_iso(registro["fecha"]), fecha_rendicion=_fecha_iso(registro["fecha_rendicion"]),
        fecha_anulado=_fecha_iso(registro["fecha_anulado"]),
        tarjeta_personal=registro["tarjeta_personal"].astype(str).str.upper().eq("TRUE").astype(int),
        numero_ticket=registro["numero_ticket"].map(lambda x: None if pd.isna(x) else str(int(x))))[
        ["id", "matricula", "dominio", "fecha", "hora", "odometro", "solicitante", "tarjeta_personal",
         "litros_autorizados", "litros_cargados", "nivel_tanque", "rendido", "fecha_rendicion", "hora_rendicion",
         "numero_ticket", "anulado", "fecha_anulado", "estacion_servicio", "bandera_rendicion", "relacion_consumo"]]
    t["transferencia"] = datos["transferencias"][["id", "fecha", "contrato_origen", "contrato_destino", "monto"]]
    t["factura"] = datos["facturacion"].rename(columns={"numero_factura": "numero", "fecha_factura": "fecha"})[
        ["numero", "contrato", "proveedor", "producto", "periodo", "fecha", "vencimiento", "total_monto", "total_pdf",
         "total_litros", "estado"]]
    t["factura_linea"] = datos["facturacion_detalle"].rename(columns={
        "numero_factura": "factura", "referencia_consumo": "referencia_carga"})[
        ["numero_linea", "factura", "referencia_carga", "concepto", "fecha", "litros", "precio_unitario", "importe",
         "descripcion"]]
    diaria = datos["telemetria_diaria"]
    t["posicion_diaria"] = diaria.assign(matricula=diaria["Placa"].map(matricula_de))[
        ["matricula", "fecha", "km_gps", "lat_inicio", "lon_inicio", "lat_fin", "lon_fin"]]
    return t


def _hasta(tablas, hasta):
    """Deja solo los datos operativos hasta la fecha `hasta` (AAAA-MM-DD)."""
    t = dict(tablas)
    for nombre in ["carga", "pedido", "transferencia", "posicion_diaria"]:
        t[nombre] = t[nombre][t[nombre]["fecha"].astype(str) <= hasta]
    t["factura"] = t["factura"][t["factura"]["fecha"].astype(str) <= hasta]
    t["factura_linea"] = t["factura_linea"][t["factura_linea"]["factura"].isin(t["factura"]["numero"])]
    return t


def _valor(v):
    """Valor nativo para SQLite: None para faltantes, int/float/str para el resto."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if hasattr(v, "item"):          # tipos de numpy
        return v.item()
    return v if isinstance(v, (int, float, str)) else str(v)


def upsert(conexion, tabla, df):
    """Inserta o actualiza cada fila por su clave."""
    if df.empty:
        return
    columnas = list(df.columns)
    clave = CLAVES[tabla]
    actualizar = [c for c in columnas if c not in clave]
    sql = (f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))}) "
           f"ON CONFLICT ({', '.join(clave)}) DO "
           + (f"UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in actualizar)}" if actualizar else "NOTHING"))
    conexion.executemany(sql, [tuple(_valor(v) for v in fila) for fila in df.itertuples(index=False, name=None)])


def cargar(conexion, directorio, hasta=None, semilla=None):
    """Carga el dataset de `directorio` en la base (en una transacción). Devuelve las filas por tabla."""
    tablas = tablas_de_la_base(cargar_dataset(directorio))
    if hasta:
        tablas = _hasta(tablas, hasta)
    with conexion:
        for nombre in TABLAS:
            upsert(conexion, nombre, tablas[nombre])
        filas = {nombre: conexion.execute(f"SELECT COUNT(*) FROM {nombre}").fetchone()[0] for nombre in TABLAS}
        conexion.execute("INSERT INTO carga_de_datos (instante, origen, hasta, semilla, filas_por_tabla) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (datetime.now(timezone.utc).isoformat(timespec="seconds"), str(Path(directorio)), hasta,
                          semilla, json.dumps(filas)))
    return filas
