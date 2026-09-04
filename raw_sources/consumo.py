"""Proyecciones crudas de consumo desde una verdad sintética relacionada."""

from __future__ import annotations

from datetime import datetime
import random


CONSUMO_INTERNO_COLUMNS = [
    "Id", "Fecha", "Hora", "Dominio", "LitrosCargados",
    "OdometroRegistrado", "NumeroTicket", "Conductor", "Rendido", "Anulado",
]

CONSUMO_EXTERNO_COLUMNS = [
    "FECHA", "TIPO IDENTIFICACION TARJETA", "IDENTIFICACION TARJETA",
    "TARJETA", "CONDUCTOR", "ODOMETRO", "LITROS UNIDADES",
    "PRECIO PVP ESTABLECIMIENTO", "IMP TOT PVP ESTABLECIMIENTO",
    "ESTABLECIMIENTO", "PRODUCTO", "ORIGEN DE TRANSACCION",
]


def _number(identifier: str) -> int:
    return int(identifier.rsplit("-", 1)[-1])


def _raw_domain(value: str, index: int) -> str:
    if index % 17 == 0:
        return f" {value.lower()} "
    if index % 13 == 0:
        return value[:3] + " " + value[3:]
    return value

def _safe_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _safe_datetime(value):
    if value is None:
        return None

    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    
def build_raw_consumo(tables: dict[str, list[dict]], seed: int) -> dict[str, list[dict]]:
    """Construye dos vistas crudas del mismo conjunto de eventos sintéticos."""
    rng = random.Random(seed)
    vehicles = {row["id"]: row for row in tables["vehiculo"]}
    cards = {row["id"]: row for row in tables["tarjeta"]}
    people = {row["id"]: row for row in tables["persona"]}
    allowed_vehicle_ids = {f"VEH-SYN-{index:05d}" for index in range(1, 239)}
    internal: list[dict] = []
    external: list[dict] = []
    truth: list[dict] = []
    liters_mismatch_count = 0
    
    for transaction in tables["transaccion_combustible"]:
        card = cards[transaction["tarjeta_id"]]
        vehicle_id = card["vehiculo_id"]
        if vehicle_id not in allowed_vehicle_ids:
            continue
        vehicle = vehicles[vehicle_id]
        person = people[transaction["persona_id"]]
        instant = _safe_datetime(transaction["instante_utc"])
        index = _number(transaction["id"])
        liters = _safe_float(transaction["litros"])
        price = float(transaction["precio_unitario"])
        domain = _raw_domain(vehicle["dominio_sintetico"], index)
        ticket_number = index - 1 if index % 113 == 0 else index
        internal_row = {
            "Id": f"OP-SIN-{index:07d}",
            "Fecha": instant.strftime("%d/%m/%Y") if instant is not None else None,
            "Hora": instant.strftime("%H:%M:%S") if instant is not None else None,
            "Dominio": domain,
            "LitrosCargados": round(liters, 2) if liters is not None else None,
            "OdometroRegistrado": round(float(transaction["odometro_declarado_km"])),
            "NumeroTicket": f"TCK-SIN-{ticket_number:07d}",
            "Conductor": person["nombre_sintetico"],
            "Rendido": "NO" if index % 10 == 0 else "SI",
            "Anulado": "SI" if index % 47 == 0 else "NO",
        }
        external_row = {
            "FECHA": instant.strftime("%d/%m/%Y %H:%M:%S") if instant is not None else None,
            "TIPO IDENTIFICACION TARJETA": "PATENTE",
            "IDENTIFICACION TARJETA": domain or vehicle["dominio_sintetico"],
            "TARJETA": f"TAR-SIN-{_number(card['id']):05d}",
            "CONDUCTOR": person["nombre_sintetico"],
            "ODOMETRO": round(float(transaction["odometro_declarado_km"])),
            "LITROS UNIDADES": round(liters, 2) if liters is not None else None,
            "PRECIO PVP ESTABLECIMIENTO": round(price, 2),
            "IMP TOT PVP ESTABLECIMIENTO": (
                round(liters * price, 2) if liters is not None else None
                ),
            "ESTABLECIMIENTO": f"ESTACION FICTICIA {(index % 18) + 1:02d}",
            "PRODUCTO": vehicle["tipo_combustible"],
            "ORIGEN DE TRANSACCION": "NORMAL" if rng.random() > 0.04 else "CONTINGENCIA",
        }
        # -------------------------------------------------
        # Inconsistencia entre fuentes: litros
        # -------------------------------------------------
        liters_mismatch = False

        if (
            liters is not None
            and liters_mismatch_count < 10
            and index > 28
        ):
            external_row["LITROS UNIDADES"] = round(liters + 1.25, 2)
            liters_mismatch = True
            liters_mismatch_count += 1
            
        internal.append({column: internal_row[column] for column in CONSUMO_INTERNO_COLUMNS})
        external.append({column: external_row[column] for column in CONSUMO_EXTERNO_COLUMNS})
        truth.append({
            "evento_id": transaction["id"],
            "vehiculo_id": vehicle_id,
            "fecha": instant.date().isoformat() if instant is not None else None,
            "litros": liters,
            "dq_liters_source_mismatch": liters_mismatch,
            "litros_interno": internal_row["LitrosCargados"],
            "litros_externo": external_row["LITROS UNIDADES"],
})

    return {"interno": internal, "externo": external, "truth": truth}
