"""Transforma el modelo relacional sintético en una exportación cruda de flota."""

from __future__ import annotations

import random


FLOTA_COLUMNS = [
    "MATRICULA", "DOMINIO", "NUMERO MOTOR", "NUMERO CHASIS",
    "DIRECCION GENERAL", "DEPENDENCIA", "TIPO VEHICULO", "MARCA",
    "MODELO", "COLOR", "AÑO", "ESTADO", "SUBESTADO", "PROCEDENCIA",
    "TIPO COMBUSTIBLE", "CAPACIDAD TANQUE", "RELACION CONSUMO",
    "IDENTIFICABLE", "EXCEPCION ODOMETRO", "FECHA EXCEPCION ODOMETRO",
    "NUMERO TARJETA", "NUMERO CONTRATO", "LIMITE SALDO", "LIMITE LITROS",
    "RETIRA DOCUMENTO", "RETIRA NOMBRE", "CUPO",
]


def _suffix(value: str) -> int:
    return int(value.rsplit("-", 1)[-1])


def _domain_variant(domain: str, index: int) -> str:
    if index % 17 == 0:
        return domain.lower()
    if index % 11 == 0:
        return f" {domain} "
    if index % 7 == 0:
        if len(domain) == 7:
            return f"{domain[:2]} {domain[2:5]} {domain[5:]}"
        return f"{domain[:3]} {domain[3:]}"
    return domain


def build_raw_flota_rows(tables: dict[str, list[dict]], seed: int) -> list[dict]:
    rng = random.Random(seed)
    subunits = {row["id"]: row for row in tables["subunidad"]}
    units = {row["id"]: row for row in tables["unidad"]}
    types = {row["id"]: row["nombre"] for row in tables["tipo_vehiculo"]}
    states = {row["id"]: row["nombre"] for row in tables["estado_vehiculo"]}
    cards = {row["vehiculo_id"]: row for row in tables["tarjeta"]}
    contracts = {row["id"]: row for row in tables["contrato"]}
    bool_variants = ("SI", "Sí", "1", "NO", "0", "")
    colors = ("Blanco", "Gris", "Negro", "Azul", "Rojo")
    rows = []

    for index, vehicle in enumerate(tables["vehiculo"], 1):
        subunit = subunits[vehicle["subunidad_id"]]
        unit = units[subunit["unidad_id"]]
        card = cards[vehicle["id"]]
        contract = contracts[card["contrato_id"]]
        matricula_number = _suffix(vehicle["matricula_sintetica"])
        matricula = matricula_number if index % 4 == 0 else f"{matricula_number:05d}"
        dependency = subunit["nombre"]
        if index % 13 == 0:
            dependency = dependency.upper()
        elif index % 9 == 0:
            dependency = f" {dependency} "
        state = states[vehicle["estado_vehiculo_id"]]
        if index % 15 == 0:
            state = state.upper().replace(" ", "_")
        capacity = None if index % 19 == 0 else float(vehicle["capacidad_tanque_l"])
        year = str(vehicle["anio_modelo"]) if index % 10 == 0 else int(vehicle["anio_modelo"])
        card_number = f"880000{_suffix(card['id']):010d}"
        contract_number = f"{_suffix(contract['id']):04d}" if index % 8 else _suffix(contract["id"])
        row = {
            "MATRICULA": matricula,
            "DOMINIO": _domain_variant(vehicle["dominio_sintetico"], index),
            "NUMERO MOTOR": "" if index % 23 == 0 else f"MOT-SYN-{index:07d}",
            "NUMERO CHASIS": "" if index % 29 == 0 else f"CHA-SYN-{index:09d}",
            "DIRECCION GENERAL": unit["nombre"],
            "DEPENDENCIA": dependency,
            "TIPO VEHICULO": types[vehicle["tipo_vehiculo_id"]],
            "MARCA": vehicle["marca_sintetica"],
            "MODELO": vehicle["modelo_sintetico"],
            "COLOR": colors[index % len(colors)],
            "AÑO": year,
            "ESTADO": state,
            "SUBESTADO": "Operativo" if index % 12 else "A revisar",
            "PROCEDENCIA": "Propia" if index % 5 else "Asignada",
            "TIPO COMBUSTIBLE": vehicle["tipo_combustible"].removeprefix("SYN-"),
            "CAPACIDAD TANQUE": capacity,
            "RELACION CONSUMO": vehicle["consumo_esperado"],
            "IDENTIFICABLE": bool_variants[index % len(bool_variants)],
            "EXCEPCION ODOMETRO": bool_variants[(index + 2) % len(bool_variants)],
            "FECHA EXCEPCION ODOMETRO": "" if index % 14 else f"{1 + index % 27:02d}/01/2025",
            "NUMERO TARJETA": card_number if index % 6 else int(card_number),
            "NUMERO CONTRATO": contract_number,
            "LIMITE SALDO": float(contract["limite_importe"]),
            "LIMITE LITROS": float(contract["limite_litros"]),
            "RETIRA DOCUMENTO": f"DOC-SYN-{(index % max(1, len(tables['persona']))) + 1:05d}",
            "RETIRA NOMBRE": tables["persona"][(index * 7) % len(tables["persona"])]["nombre_sintetico"],
            "CUPO": rng.choice(("Mensual", "Semanal", "Sin cupo", "")),
        }
        rows.append({column: row[column] for column in FLOTA_COLUMNS})
    return rows
