"""Generador relacional sin dependencias ni entradas externas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
from typing import Any


@dataclass(frozen=True)
class GenerationConfig:
    scenario: str = "early_stage"
    seed: int = 20260816
    vehicles: int = 250
    devices: int = 180
    people: int = 500
    telemetry_events: int = 20_000
    fuel_transactions: int = 5_000
    months: int = 12

    def validate(self) -> None:
        if self.scenario not in {"clean", "early_stage", "transition", "mature", "stress"}:
            raise ValueError(f"Escenario no soportado: {self.scenario}")
        for name in ("vehicles", "devices", "people", "telemetry_events", "fuel_transactions", "months"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} debe ser mayor que cero")
        if self.devices > self.vehicles:
            raise ValueError("devices no puede superar vehicles en el MVP")


def _id(prefix: str, number: int, width: int = 5) -> str:
    return f"{prefix}-SYN-{number:0{width}d}"


def _decimal(value: float, places: str = "0.01") -> str:
    return str(Decimal(str(value)).quantize(Decimal(places)))


def _letters(number: int, width: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chars = []
    for _ in range(width):
        chars.append(alphabet[number % len(alphabet)])
        number //= len(alphabet)
    return "".join(reversed(chars))


def _argentine_domain(index: int, year: int) -> str:
    sequence = index - 1
    if year < 2016:
        return f"{_letters(sequence // 1000, 3)}{sequence % 1000:03d}"
    prefix_number = sequence // (1000 * 26 * 26)
    suffix_number = sequence // 1000
    return f"{_letters(prefix_number, 2)}{sequence % 1000:03d}{_letters(suffix_number, 2)}"


def generate_dataset(config: GenerationConfig) -> dict[str, list[dict[str, Any]]]:
    config.validate()
    rng = random.Random(config.seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)

    units = [{"id": _id("UNI", i, 3), "codigo": _id("UNI", i, 3), "nombre": f"Unidad Ficticia {i:02d}"} for i in range(1, 11)]
    subunits = [
        {"id": _id("SUB", i, 4), "unidad_id": units[(i - 1) % len(units)]["id"], "codigo": _id("SUB", i, 4), "nombre": f"Subunidad Ficticia {i:03d}"}
        for i in range(1, 41)
    ]
    vehicle_types = [{"id": _id("TV", i, 2), "nombre": name} for i, name in enumerate(("Utilitario A", "Utilitario B", "Transporte A", "Especial A", "Apoyo A"), 1)]
    vehicle_states = [{"id": _id("EV", i, 2), "nombre": name} for i, name in enumerate(("En servicio", "Fuera de servicio", "Baja"), 1)]

    public_catalog = (
        ("Toyota", "Hilux"), ("Ford", "Ranger"), ("Renault", "Kangoo"),
        ("Fiat", "Fiorino"), ("Volkswagen", "Amarok"), ("Chevrolet", "S10"),
        ("Iveco", "Daily"),
    )
    vehicles = []
    for i in range(1, config.vehicles + 1):
        vtype = vehicle_types[(i - 1) % len(vehicle_types)]
        fuel = "SYN-DIESEL" if i % 3 else "SYN-NAFTA"
        year = 2008 + (i % 18)
        brand, model = public_catalog[(i - 1) % len(public_catalog)]
        vehicles.append({
            "id": _id("VEH", i),
            "matricula_sintetica": _id("VEH", i),
            "dominio_sintetico": _argentine_domain(i, year),
            "subunidad_id": rng.choice(subunits)["id"],
            "tipo_vehiculo_id": vtype["id"],
            "estado_vehiculo_id": rng.choices(vehicle_states, weights=(85, 12, 3), k=1)[0]["id"],
            "marca_sintetica": brand,
            "modelo_sintetico": model,
            "anio_modelo": year,
            "tipo_combustible": fuel,
            "capacidad_tanque_l": _decimal(45 + (i % 6) * 10),
            "consumo_esperado": _decimal(7 + (i % 9) * 0.8),
            "identificable": "true",
            "origen": "SINTETICO",
        })

    devices = [
        {"id": _id("DEV", i), "codigo_sintetico": _id("DEV", i), "vehiculo_id": vehicles[i - 1]["id"], "estado_transmision": rng.choices(("Activo", "Intermitente", "Inactivo"), (82, 13, 5), k=1)[0], "fecha_alta": (start.date() - timedelta(days=i % 900)).isoformat()}
        for i in range(1, config.devices + 1)
    ]
    people = [
        {"id": _id("PER", i), "codigo_sintetico": _id("PER", i), "nombre_sintetico": f"Persona Sintética {i:05d}", "subunidad_id": rng.choice(subunits)["id"], "rol_sintetico": f"Rol Ficticio {(i % 6) + 1}"}
        for i in range(1, config.people + 1)
    ]
    contract_count = max(10, min(100, config.vehicles // 20))
    contracts = [
        {"id": _id("CTR", i, 4), "codigo_sintetico": _id("CTR", i, 4), "subunidad_id": subunits[(i - 1) % len(subunits)]["id"], "limite_importe": _decimal(500_000 + i * 10_000), "limite_litros": _decimal(5_000 + i * 100)}
        for i in range(1, contract_count + 1)
    ]
    cards = [
        {"id": _id("CARD", i), "codigo_sintetico": _id("CARD", i), "contrato_id": contracts[(i - 1) % contract_count]["id"], "vehiculo_id": vehicles[i - 1]["id"], "estado": "Activa" if i % 20 else "Suspendida"}
        for i in range(1, config.vehicles + 1)
    ]

    telemetry = []
    odometers = {row["id"]: 10_000.0 + n * 13 for n, row in enumerate(devices)}
    for i in range(1, config.telemetry_events + 1):
        device = devices[(i - 1) % len(devices)]
        odometers[device["id"]] += rng.uniform(0.2, 8.0)
        instant = start + timedelta(minutes=i * max(1, config.months * 43800 // config.telemetry_events))
        telemetry.append({"id": _id("TEL", i, 7), "dispositivo_id": device["id"], "instante_utc": instant.isoformat(), "latitud_simulada": _decimal(0.10 + rng.random() * 0.80, "0.000001"), "longitud_simulada": _decimal(0.10 + rng.random() * 0.80, "0.000001"), "odometro_km": _decimal(odometers[device["id"]], "0.1"), "horometro_h": _decimal(500 + i / 20, "0.1"), "bateria_pct": _decimal(rng.uniform(25, 100), "0.1")})

    transactions = []
    for i in range(1, config.fuel_transactions + 1):
        card = cards[(i * 37) % len(cards)]
        vehicle = vehicles[int(card["vehiculo_id"].split("-")[-1]) - 1]
        liters = rng.uniform(8, float(vehicle["capacidad_tanque_l"]) * 0.85)
        price = 900 + ((i // 5000) * 35) + rng.uniform(-12, 12)
        instant = start + timedelta(minutes=i * max(1, config.months * 43800 // config.fuel_transactions))
        transactions.append({"id": _id("TX", i, 7), "tarjeta_id": card["id"], "persona_id": people[(i * 17) % len(people)]["id"], "instante_utc": instant.isoformat(), "producto": vehicle["tipo_combustible"], "litros": _decimal(liters), "precio_unitario": _decimal(price), "importe_total": _decimal(liters * price), "odometro_declarado_km": _decimal(10_000 + i * 2.7, "0.1")})

    periods = []
    invoices = []
    for month in range(config.months):
        period_id = _id("PERIOD", month + 1, 3)
        period_start = start.date() + timedelta(days=30 * month)
        periods.append({"id": period_id, "desde": period_start.isoformat(), "hasta": (period_start + timedelta(days=29)).isoformat()})
        for contract_index, contract in enumerate(contracts, 1):
            amount = 350_000 + month * 12_000 + contract_index * 2_500
            invoices.append({"id": _id("INV", month * contract_count + contract_index, 6), "periodo_id": period_id, "contrato_id": contract["id"], "importe_facturado": _decimal(amount), "importe_conciliado": _decimal(amount * 0.98)})

    request_count = max(config.vehicles, config.fuel_transactions // 20)
    requests = [
        {"id": _id("REQ", i, 6), "vehiculo_id": vehicles[(i * 11) % len(vehicles)]["id"], "persona_id": people[(i * 19) % len(people)]["id"], "fecha": (start.date() + timedelta(days=i % (config.months * 30))).isoformat(), "litros_solicitados": _decimal(15 + (i % 35)), "estado": ("Pendiente", "Rendida", "Anulada")[i % 3]}
        for i in range(1, request_count + 1)
    ]

    ground_truth: list[dict[str, Any]] = []
    if config.scenario in {"early_stage", "stress"}:
        duplicate_count = min(32, config.vehicles // 3)
        for offset in range(duplicate_count):
            target = vehicles[offset]
            source = vehicles[duplicate_count + offset]
            target["matricula_sintetica"] = source["matricula_sintetica"]
            ground_truth.append({"id": _id("GT", len(ground_truth) + 1, 6), "ejecucion_id": _id("RUN", 1, 3), "entidad": "vehiculo", "registro_id": target["id"], "tipo": "DQ_DUP_VEH_ID", "severidad": "alta", "parametros": '{"unidad":"count","escenario":"early_stage"}'})
        domain_start = duplicate_count
        source_start = duplicate_count * 2
        for offset in range(duplicate_count):
            target = vehicles[domain_start + offset]
            source = vehicles[source_start + offset]
            target["dominio_sintetico"] = source["dominio_sintetico"]
            ground_truth.append({"id": _id("GT", len(ground_truth) + 1, 6), "ejecucion_id": _id("RUN", 1, 3), "entidad": "vehiculo", "registro_id": target["id"], "tipo": "DQ_DUP_DOMAIN", "severidad": "alta", "parametros": '{"unidad":"count","escenario":"early_stage"}'})
        
        # -------------------------------------------------
        # Defecto de normalización: espacios en marca
        # -------------------------------------------------
        whitespace_count = min(8, len(vehicles)) 
        for offset in range(whitespace_count): 
            target = vehicles[64 + offset]
            target["marca_sintetica"] = f" {target['marca_sintetica']} "
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "vehiculo",
                "registro_id": target["id"],
                "tipo": "DQ_WHITESPACE_MARCA",
                "severidad": "baja",
                "parametros": '{"campo":"marca_sintetica","tratamiento":"strip"}'
            })
            
        # -------------------------------------------------
        # Defecto de normalización: mayúsculas/minúsculas
        # inconsistentes en marca
        # -------------------------------------------------
        case_count = min(6, len(vehicles))
        for offset in range(case_count):
            target = vehicles[72 + offset]
            if offset % 2 == 0:
                target["marca_sintetica"] = target["marca_sintetica"].lower()
            else:
                target["marca_sintetica"] = target["marca_sintetica"].swapcase()
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "vehiculo",
                "registro_id": target["id"],
                "tipo": "DQ_CASE_MARCA",
                "severidad": "baja",
                "parametros": '{"campo":"marca_sintetica","tratamiento":"normalizar_case"}'
            })
            
        # -------------------------------------------------
        # Defecto de normalización: formato inconsistente
        # en tipo_combustible
        # -------------------------------------------------
        fuel_format_count = min(8, len(vehicles))
        for offset in range(fuel_format_count):
            target = vehicles[78 + offset]
            if offset % 2 == 0:
                target["tipo_combustible"] = target["tipo_combustible"].lower()
            else:
                target["tipo_combustible"] = f"{target['tipo_combustible']} "
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "vehiculo",
                "registro_id": target["id"],
                "tipo": "DQ_FORMAT_COMBUSTIBLE",
                "severidad": "baja",
                "parametros": '{"campo":"tipo_combustible","tratamiento":"normalizar_texto"}'
            })     
               
        # -------------------------------------------------
        # Defecto de validez: fechas heterogéneas o inválidas
        # en fecha_alta de dispositivo
        # -------------------------------------------------
        date_format_count = min(6, len(devices))
        for offset in range(date_format_count):
            target = devices[offset]
            if offset % 2 == 0:
                # Formato alternativo: DD/MM/YYYY
                fecha_original = datetime.fromisoformat(target["fecha_alta"])
                target["fecha_alta"] = fecha_original.strftime("%d/%m/%Y")
            else:
                # Fecha inválida
                target["fecha_alta"] = "fecha_error"
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "dispositivo",
                "registro_id": target["id"],
                "tipo": "DQ_INVALID_DATE_FORMAT",
                "severidad": "media",
                "parametros": '{"campo":"fecha_alta","tratamiento":"parsear_fecha"}'
            })   
            
        # -------------------------------------------------
        # Defecto de completitud: odometro_km faltante
        # en evento_telemetria
        # -------------------------------------------------
        null_odometer_count = min(10, len(telemetry))
        for offset in range(null_odometer_count):
            target = telemetry[offset]
            target["odometro_km"] = None
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "evento_telemetria",
                "registro_id": target["id"],
                "tipo": "DQ_NULL_ODOMETRO",
                "severidad": "media",
                "parametros": '{"campo":"odometro_km","tratamiento":"control_completitud"}'
            })
        
        # -------------------------------------------------
        # Defecto de validez: odometro_km no numérico
        # en evento_telemetria
        # -------------------------------------------------
        invalid_odometer_count = min(10, len(telemetry) - 10)

        for offset in range(invalid_odometer_count):
            target = telemetry[10 + offset]
            target["odometro_km"] = "S/D"
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "evento_telemetria",
                "registro_id": target["id"],
                "tipo": "DQ_INVALID_ODOMETRO",
                "severidad": "media",
                "parametros": '{"campo":"odometro_km","tratamiento":"conversion_numerica"}'
            })
        # -------------------------------------------------
        # Defecto de completitud: litros faltantes
        # en transaccion_combustible
        # -------------------------------------------------
        null_liters_count = min(10, len(transactions))
        for offset in range(null_liters_count):
            target = transactions[offset]
            target["litros"] = None
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "transaccion_combustible",
                "registro_id": target["id"],
                "tipo": "DQ_NULL_LITROS",
                "severidad": "media",
                "parametros": '{"campo":"litros","tratamiento":"control_completitud"}'
            })            

        # -------------------------------------------------
        # Defecto de validez: litros no numéricos
        # en transaccion_combustible
        # -------------------------------------------------
        invalid_liters_count = min(10, max(0, len(transactions) - 10))
        for offset in range(invalid_liters_count):
            target = transactions[10 + offset]
            target["litros"] = "ERROR"
            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "transaccion_combustible",
                "registro_id": target["id"],
                "tipo": "DQ_INVALID_LITROS",
                "severidad": "media",
                "parametros": '{"campo":"litros","tratamiento":"conversion_numerica"}'
            })
            
        # -------------------------------------------------
        # Defecto de validez: fecha/hora inválida o
        # heterogénea en transaccion_combustible
        # -------------------------------------------------
        invalid_datetime_count = min(8, max(0, len(transactions) - 20))

        for offset in range(invalid_datetime_count):
            target = transactions[20 + offset]

            if offset % 2 == 0:
                target["instante_utc"] = "03/05/2025 14:30"
            else:
                target["instante_utc"] = "sin fecha"

            ground_truth.append({
                "id": _id("GT", len(ground_truth) + 1, 6),
                "ejecucion_id": _id("RUN", 1, 3),
                "entidad": "transaccion_combustible",
                "registro_id": target["id"],
                "tipo": "DQ_INVALID_DATETIME",
                "severidad": "media",
                "parametros": '{"campo":"instante_utc","tratamiento":"parsear_fecha"}'
            })
        
        
    tables = {
        "unidad": units, "subunidad": subunits, "tipo_vehiculo": vehicle_types, "estado_vehiculo": vehicle_states,
        "vehiculo": vehicles, "dispositivo": devices, "evento_telemetria": telemetry, "persona": people,
        "contrato": contracts, "tarjeta": cards, "transaccion_combustible": transactions,
        "periodo_facturacion": periods, "factura": invoices, "solicitud_combustible": requests,
        "ejecucion_dataset": [{"id": _id("RUN", 1, 3), **{k: str(v) for k, v in asdict(config).items()}}],
        "ground_truth": ground_truth,
    }
    return tables
