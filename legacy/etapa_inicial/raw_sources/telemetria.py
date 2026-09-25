"""Deriva un estado crudo de dispositivos desde telemetría sintética."""

from __future__ import annotations

from datetime import datetime
import random


TELEMETRIA_COLUMNS = [
    "Alias", "Placa", "IMEI", "MSISDN", "Grupo", "Modelo equipo",
    "Estado transmisión", "Hora de última transmisión", "Batería",
    "Batería externa", "Odómetro", "Horómetro", "Latitud", "Longitud",
]


def _number(value: str) -> int:
    return int(value.rsplit("-", 1)[-1])


def build_raw_telemetria_rows(tables: dict[str, list[dict]], seed: int) -> list[dict]:
    rng = random.Random(seed)
    vehicles = {row["id"]: row for row in tables["vehiculo"]}
    latest = {}
    for event in tables["evento_telemetria"]:
        latest[event["dispositivo_id"]] = event
    rows = []
    for index, device in enumerate(tables["dispositivo"], 1):
        vehicle = vehicles[device["vehiculo_id"]]
        event = latest[device["id"]]
        if index <= 15:
            alias, plate = "SIN ASIGNAR", ""
        elif index % 4 == 0:
            alias, plate = f"MOTOR {index:07d}", vehicle["dominio_sintetico"]
        else:
            alias, plate = f"MOVIL {_number(vehicle['matricula_sintetica']):05d}", vehicle["dominio_sintetico"]
        if index % 11 == 0 and plate:
            plate = f" {plate.lower()} "
        imei_number = index if index > 6 else index + 6
        instant = datetime.fromisoformat(event["instante_utc"])
        date_value = instant.strftime("%d/%m/%Y %H:%M") if index % 3 else instant.isoformat()
        if index % 37 == 0:
            date_value = ""
        row = {
            "Alias": alias,
            "Placa": plate,
            "IMEI": f"99000000{imei_number:07d}",
            "MSISDN": f"5491100{index:06d}",
            "Grupo": "Flota activa" if index % 20 else "BAJAS / REMPLAZOS/ OTROS",
            "Modelo equipo": ("Tracker A", "Tracker B", "Tracker C")[index % 3],
            "Estado transmisión": device["estado_transmision"] if index % 9 else device["estado_transmision"].upper(),
            "Hora de última transmisión": date_value,
            "Batería": "" if index % 31 == 0 else float(event["bateria_pct"]),
            "Batería externa": round(rng.uniform(11.2, 14.4), 1),
            "Odómetro": float(event["odometro_km"]),
            "Horómetro": float(event["horometro_h"]),
            "Latitud": round(-31.0 - float(event["latitud_simulada"]) * 3.0, 6),
            "Longitud": round(-62.0 - float(event["longitud_simulada"]) * 3.0, 6),
        }
        rows.append({column: row[column] for column in TELEMETRIA_COLUMNS})
    return rows
