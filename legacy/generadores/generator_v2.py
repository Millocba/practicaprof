"""Generador sintético v2: defectos expandidos, arquitectura modular."""

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


# ============================================================================
# HELPERS (funciones puras, sin estado)
# ============================================================================

def _id(prefix: str, number: int, width: int = 5) -> str:
    """Genera ID sintético con prefijo, número y ancho."""
    return f"{prefix}-SYN-{number:0{width}d}"


def _decimal(value: float, places: str = "0.01") -> str:
    """Convierte float a Decimal con precisión."""
    return str(Decimal(str(value)).quantize(Decimal(places)))


def _letters(number: int, width: int) -> str:
    """Mapea número a letras (A-Z)."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chars = []
    for _ in range(width):
        chars.append(alphabet[number % len(alphabet)])
        number //= len(alphabet)
    return "".join(reversed(chars))


def _argentine_domain(index: int, year: int) -> str:
    """Dominio argentino realista."""
    sequence = index - 1
    if year < 2016:
        return f"{_letters(sequence // 1000, 3)}{sequence % 1000:03d}"
    prefix_number = sequence // (1000 * 26 * 26)
    suffix_number = sequence // 1000
    return f"{_letters(prefix_number, 2)}{sequence % 1000:03d}{_letters(suffix_number, 2)}"


# ============================================================================
# GENERACIÓN DE TABLAS LIMPIAS
# ============================================================================

def _generate_clean_tables(config: GenerationConfig, rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    """Genera todas las 16 tablas sin defectos."""
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)

    units = [
        {"id": _id("UNI", i, 3), "codigo": _id("UNI", i, 3), "nombre": f"Unidad Ficticia {i:02d}"}
        for i in range(1, 11)
    ]

    subunits = [
        {
            "id": _id("SUB", i, 4),
            "unidad_id": units[(i - 1) % len(units)]["id"],
            "codigo": _id("SUB", i, 4),
            "nombre": f"Subunidad Ficticia {i:03d}",
        }
        for i in range(1, 41)
    ]

    vehicle_types = [
        {"id": _id("TV", i, 2), "nombre": name}
        for i, name in enumerate(("Utilitario A", "Utilitario B", "Transporte A", "Especial A", "Apoyo A"), 1)
    ]

    vehicle_states = [
        {"id": _id("EV", i, 2), "nombre": name}
        for i, name in enumerate(("En servicio", "Fuera de servicio", "Baja"), 1)
    ]

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
        {
            "id": _id("DEV", i),
            "codigo_sintetico": _id("DEV", i),
            "vehiculo_id": vehicles[i - 1]["id"],
            "estado_transmision": rng.choices(("Activo", "Intermitente", "Inactivo"), (82, 13, 5), k=1)[0],
            "fecha_alta": (start.date() - timedelta(days=i % 900)).isoformat(),
        }
        for i in range(1, config.devices + 1)
    ]

    people = [
        {
            "id": _id("PER", i),
            "codigo_sintetico": _id("PER", i),
            "nombre_sintetico": f"Persona Sintética {i:05d}",
            "subunidad_id": rng.choice(subunits)["id"],
            "rol_sintetico": f"Rol Ficticio {(i % 6) + 1}",
        }
        for i in range(1, config.people + 1)
    ]

    contract_count = max(10, min(100, config.vehicles // 20))
    contracts = [
        {
            "id": _id("CTR", i, 4),
            "codigo_sintetico": _id("CTR", i, 4),
            "subunidad_id": subunits[(i - 1) % len(subunits)]["id"],
            "limite_importe": _decimal(500_000 + i * 10_000),
            "limite_litros": _decimal(5_000 + i * 100),
        }
        for i in range(1, contract_count + 1)
    ]

    cards = [
        {
            "id": _id("CARD", i),
            "codigo_sintetico": _id("CARD", i),
            "contrato_id": contracts[(i - 1) % contract_count]["id"],
            "vehiculo_id": vehicles[i - 1]["id"],
            "estado": "Activa" if i % 20 else "Suspendida",
        }
        for i in range(1, config.vehicles + 1)
    ]

    telemetry = []
    odometers = {row["id"]: 10_000.0 + n * 13 for n, row in enumerate(devices)}
    for i in range(1, config.telemetry_events + 1):
        device = devices[(i - 1) % len(devices)]
        odometers[device["id"]] += rng.uniform(0.2, 8.0)
        instant = start + timedelta(
            minutes=i * max(1, config.months * 43800 // config.telemetry_events)
        )
        telemetry.append({
            "id": _id("TEL", i, 7),
            "dispositivo_id": device["id"],
            "instante_utc": instant.isoformat(),
            "latitud_simulada": _decimal(0.10 + rng.random() * 0.80, "0.000001"),
            "longitud_simulada": _decimal(0.10 + rng.random() * 0.80, "0.000001"),
            "odometro_km": _decimal(odometers[device["id"]], "0.1"),
            "horometro_h": _decimal(500 + i / 20, "0.1"),
            "bateria_pct": _decimal(rng.uniform(25, 100), "0.1"),
        })

    transactions = []
    for i in range(1, config.fuel_transactions + 1):
        card = cards[(i * 37) % len(cards)]
        vehicle = vehicles[int(card["vehiculo_id"].split("-")[-1]) - 1]
        liters = rng.uniform(8, float(vehicle["capacidad_tanque_l"]) * 0.85)
        price = 900 + ((i // 5000) * 35) + rng.uniform(-12, 12)
        instant = start + timedelta(
            minutes=i * max(1, config.months * 43800 // config.fuel_transactions)
        )
        transactions.append({
            "id": _id("TX", i, 7),
            "tarjeta_id": card["id"],
            "persona_id": people[(i * 17) % len(people)]["id"],
            "instante_utc": instant.isoformat(),
            "producto": vehicle["tipo_combustible"],
            "litros": _decimal(liters),
            "precio_unitario": _decimal(price),
            "importe_total": _decimal(liters * price),
            "odometro_declarado_km": _decimal(10_000 + i * 2.7, "0.1"),
        })

    periods = []
    invoices = []
    for month in range(config.months):
        period_id = _id("PERIOD", month + 1, 3)
        period_start = start.date() + timedelta(days=30 * month)
        periods.append({
            "id": period_id,
            "desde": period_start.isoformat(),
            "hasta": (period_start + timedelta(days=29)).isoformat(),
        })
        for contract_index, contract in enumerate(contracts, 1):
            amount = 350_000 + month * 12_000 + contract_index * 2_500
            invoices.append({
                "id": _id("INV", month * contract_count + contract_index, 6),
                "periodo_id": period_id,
                "contrato_id": contract["id"],
                "importe_facturado": _decimal(amount),
                "importe_conciliado": _decimal(amount * 0.98),
            })

    request_count = max(config.vehicles, config.fuel_transactions // 20)
    requests = [
        {
            "id": _id("REQ", i, 6),
            "vehiculo_id": vehicles[(i * 11) % len(vehicles)]["id"],
            "persona_id": people[(i * 19) % len(people)]["id"],
            "fecha": (start.date() + timedelta(days=i % (config.months * 30))).isoformat(),
            "litros_solicitados": _decimal(15 + (i % 35)),
            "estado": ("Pendiente", "Rendida", "Anulada")[i % 3],
        }
        for i in range(1, request_count + 1)
    ]

    return {
        "unidad": units,
        "subunidad": subunits,
        "tipo_vehiculo": vehicle_types,
        "estado_vehiculo": vehicle_states,
        "vehiculo": vehicles,
        "dispositivo": devices,
        "evento_telemetria": telemetry,
        "persona": people,
        "contrato": contracts,
        "tarjeta": cards,
        "transaccion_combustible": transactions,
        "periodo_facturacion": periods,
        "factura": invoices,
        "solicitud_combustible": requests,
    }


# ============================================================================
# INYECCIÓN DE DEFECTOS (modular por tipo)
# ============================================================================

def _inject_format_drift_vehicles(
    vehicles: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_FORMAT_DRIFT en tabla vehiculo (espacios, mayúsculas)."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    # Espacios en marca_sintetica (8 registros)
    sample_indices = rng.sample(range(8), min(8, len(vehicles)))
    for idx in sample_indices:
        vehicles[idx]["marca_sintetica"] = f" {vehicles[idx]['marca_sintetica']} "
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "vehiculo",
            "registro_id": vehicles[idx]["id"],
            "tipo": "DQ_FORMAT_DRIFT",
            "severidad": "media",
            "parametros": '{"campo":"marca_sintetica","problema":"espacios_inicio_final"}',
        })

    # Mayúsculas inconsistentes en marca_sintetica (6 registros)
    sample_indices = rng.sample(range(8, min(14, len(vehicles))), min(6, len(vehicles) - 8))
    for idx in sample_indices:
        current = vehicles[idx]["marca_sintetica"]
        # Hacer lowercase o mixed case
        vehicles[idx]["marca_sintetica"] = current.lower() if idx % 2 else "".join(
            c.upper() if i % 2 else c.lower() for i, c in enumerate(current)
        )
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "vehiculo",
            "registro_id": vehicles[idx]["id"],
            "tipo": "DQ_FORMAT_DRIFT",
            "severidad": "media",
            "parametros": '{"campo":"marca_sintetica","problema":"mayusculas_inconsistentes"}',
        })

    # Formato inconsistente en tipo_combustible (8 registros)
    sample_indices = rng.sample(range(14, min(22, len(vehicles))), min(8, len(vehicles) - 14))
    for idx in sample_indices:
        current = vehicles[idx]["tipo_combustible"]
        # Variar formato
        formats = [current.lower(), current.lower() + " ", "syn-diesel" if "DIESEL" in current else "syn-nafta"]
        vehicles[idx]["tipo_combustible"] = rng.choice(formats)
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "vehiculo",
            "registro_id": vehicles[idx]["id"],
            "tipo": "DQ_FORMAT_DRIFT",
            "severidad": "media",
            "parametros": '{"campo":"tipo_combustible","problema":"formato_heterogeneo"}',
        })


def _inject_invalid_dates_devices(
    devices: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_INVALID_DATE en tabla dispositivo."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    sample_indices = rng.sample(range(len(devices)), min(6, len(devices)))
    invalid_dates = ["15/03/2025", "2025-13-01", "fecha_error", "S/D", None, "99/99/9999"]

    for idx in sample_indices:
        devices[idx]["fecha_alta"] = rng.choice(invalid_dates)
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "dispositivo",
            "registro_id": devices[idx]["id"],
            "tipo": "DQ_INVALID_DATE",
            "severidad": "alta",
            "parametros": '{"campo":"fecha_alta","problema":"fecha_invalida_o_heterogenea"}',
        })


def _inject_missing_values_telemetry(
    telemetry: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_MISSING_VALUE en evento_telemetria."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    sample_indices = rng.sample(range(len(telemetry)), min(10, len(telemetry)))
    for idx in sample_indices:
        telemetry[idx]["odometro_km"] = None
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "evento_telemetria",
            "registro_id": telemetry[idx]["id"],
            "tipo": "DQ_MISSING_VALUE",
            "severidad": "alta",
            "parametros": '{"campo":"odometro_km","problema":"valor_faltante"}',
        })


def _inject_invalid_types_telemetry(
    telemetry: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_INVALID_TYPE en evento_telemetria (valores no numéricos)."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    start_idx = min(10, len(telemetry))
    sample_indices = rng.sample(range(start_idx, len(telemetry)), min(10, len(telemetry) - start_idx))
    invalid_values = ["S/D", "ERROR", "N/A", "??", "SIN_DATO"]

    for idx in sample_indices:
        telemetry[idx]["odometro_km"] = rng.choice(invalid_values)
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "evento_telemetria",
            "registro_id": telemetry[idx]["id"],
            "tipo": "DQ_INVALID_TYPE",
            "severidad": "alta",
            "parametros": '{"campo":"odometro_km","problema":"valor_no_numerico"}',
        })


def _inject_missing_values_transactions(
    transactions: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_MISSING_VALUE en transaccion_combustible."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    sample_indices = rng.sample(range(len(transactions)), min(10, len(transactions)))
    for idx in sample_indices:
        transactions[idx]["litros"] = None
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "transaccion_combustible",
            "registro_id": transactions[idx]["id"],
            "tipo": "DQ_MISSING_VALUE",
            "severidad": "alta",
            "parametros": '{"campo":"litros","problema":"valor_faltante"}',
        })


def _inject_invalid_types_transactions(
    transactions: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_INVALID_TYPE en transaccion_combustible (valores no numéricos)."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    start_idx = min(10, len(transactions))
    sample_indices = rng.sample(
        range(start_idx, len(transactions)), min(10, len(transactions) - start_idx)
    )
    invalid_values = ["ERROR", "N/A", "SIN_DATO", "??"]

    for idx in sample_indices:
        transactions[idx]["litros"] = rng.choice(invalid_values)
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "transaccion_combustible",
            "registro_id": transactions[idx]["id"],
            "tipo": "DQ_INVALID_TYPE",
            "severidad": "alta",
            "parametros": '{"campo":"litros","problema":"valor_no_numerico"}',
        })


def _inject_temporal_anomalies(
    transactions: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_TEMPORAL: fechas fuera de secuencia."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    sample_indices = rng.sample(range(len(transactions)), min(8, len(transactions)))
    for idx in sample_indices:
        # Reemplazar con fecha de formato heterogéneo o fuera de orden
        transactions[idx]["instante_utc"] = rng.choice([
            "03/05/2025 14:30",  # formato DD/MM/YYYY
            "2024-12-31T23:59:59Z",  # año anterior
            "sin_fecha",  # inválida
            "2025-13-01T00:00:00Z",  # mes inválido
        ])
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "transaccion_combustible",
            "registro_id": transactions[idx]["id"],
            "tipo": "DQ_TEMPORAL",
            "severidad": "alta",
            "parametros": '{"campo":"instante_utc","problema":"fecha_fuera_secuencia"}',
        })


def _inject_consistency_violations(
    transactions: list[dict],
    vehicles: list[dict],
    cards: list[dict],
    ground_truth: list[dict],
    rng: random.Random,
    config: GenerationConfig,
) -> None:
    """Inyecta DQ_INCONSISTENCY: litros > capacidad y odometro inconsistencias."""
    if config.scenario not in {"early_stage", "stress"}:
        return

    # Construir mapa de vehicle_id → capacidad
    vehicle_map = {v["id"]: float(v["capacidad_tanque_l"]) for v in vehicles}
    card_map = {c["id"]: c["vehiculo_id"] for c in cards}

    # DQ_INCONSISTENCY: litros sobre capacidad (10 registros)
    sample_indices = rng.sample(range(len(transactions)), min(10, len(transactions)))
    for idx in sample_indices:
        card_id = transactions[idx]["tarjeta_id"]
        if card_id in card_map:
            vehicle_id = card_map[card_id]
            if vehicle_id in vehicle_map:
                capacity = vehicle_map[vehicle_id]
                # Establecer litros > capacidad
                transactions[idx]["litros"] = _decimal(capacity * 1.5)  # 150% de capacidad
                ground_truth.append({
                    "id": _id("GT", len(ground_truth) + 1, 6),
                    "ejecucion_id": _id("RUN", 1, 3),
                    "entidad": "transaccion_combustible",
                    "registro_id": transactions[idx]["id"],
                    "tipo": "DQ_INCONSISTENCY",
                    "severidad": "media",
                    "parametros": '{"campo":"litros","problema":"supera_capacidad_tanque"}',
                })

    # DQ_INCONSISTENCY: odometro inconsistente (saltos o regresiones)
    start_idx = min(10, len(transactions))
    sample_indices = rng.sample(
        range(start_idx, len(transactions)), min(10, len(transactions) - start_idx)
    )
    for idx in sample_indices:
        current = float(transactions[idx]["odometro_declarado_km"])
        # Crear regresión o salto
        transactions[idx]["odometro_declarado_km"] = _decimal(current - 500)  # regresión
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "transaccion_combustible",
            "registro_id": transactions[idx]["id"],
            "tipo": "DQ_INCONSISTENCY",
            "severidad": "media",
            "parametros": '{"campo":"odometro_declarado_km","problema":"regresion_respecto_anterior"}',
        })


# ============================================================================
# ORQUESTACIÓN PRINCIPAL
# ============================================================================

def generate_dataset(config: GenerationConfig) -> dict[str, list[dict[str, Any]]]:
    """Genera dataset con defectos inyectados según escenario."""
    config.validate()
    rng = random.Random(config.seed)

    # Generar tablas limpias
    tables = _generate_clean_tables(config, rng)
    ground_truth: list[dict[str, Any]] = []

    # Inyectar defectos (solo en early_stage y stress)
    if config.scenario in {"early_stage", "stress"}:
        # Defectos MVP (32 + 32)
        _inject_duplicate_vehicle_ids(tables["vehiculo"], ground_truth, rng, config)
        _inject_duplicate_domains(tables["vehiculo"], ground_truth, rng, config)

        # Defectos nuevos (expandidos)
        _inject_format_drift_vehicles(tables["vehiculo"], ground_truth, rng, config)
        _inject_invalid_dates_devices(tables["dispositivo"], ground_truth, rng, config)
        _inject_missing_values_telemetry(tables["evento_telemetria"], ground_truth, rng, config)
        _inject_invalid_types_telemetry(tables["evento_telemetria"], ground_truth, rng, config)
        _inject_missing_values_transactions(tables["transaccion_combustible"], ground_truth, rng, config)
        _inject_invalid_types_transactions(tables["transaccion_combustible"], ground_truth, rng, config)
        _inject_temporal_anomalies(tables["transaccion_combustible"], ground_truth, rng, config)
        _inject_consistency_violations(
            tables["transaccion_combustible"],
            tables["vehiculo"],
            tables["tarjeta"],
            ground_truth,
            rng,
            config,
        )

    # Agregar ejecucion_dataset y ground_truth
    tables["ejecucion_dataset"] = [{"id": _id("RUN", 1, 3), **{k: str(v) for k, v in asdict(config).items()}}]
    tables["ground_truth"] = ground_truth

    return tables


def _inject_duplicate_vehicle_ids(
    vehicles: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_DUP_VEH_ID (MVP, 32 duplicados)."""
    duplicate_count = min(32, config.vehicles // 3)
    for offset in range(duplicate_count):
        target = vehicles[offset]
        source = vehicles[duplicate_count + offset]
        target["matricula_sintetica"] = source["matricula_sintetica"]
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "vehiculo",
            "registro_id": target["id"],
            "tipo": "DQ_DUP_VEH_ID",
            "severidad": "alta",
            "parametros": '{"unidad":"count","escenario":"early_stage"}',
        })


def _inject_duplicate_domains(
    vehicles: list[dict], ground_truth: list[dict], rng: random.Random, config: GenerationConfig
) -> None:
    """Inyecta DQ_DUP_DOMAIN (MVP, 32 duplicados)."""
    duplicate_count = min(32, config.vehicles // 3)
    domain_start = duplicate_count
    source_start = duplicate_count * 2
    for offset in range(duplicate_count):
        target = vehicles[domain_start + offset]
        source = vehicles[source_start + offset]
        target["dominio_sintetico"] = source["dominio_sintetico"]
        ground_truth.append({
            "id": _id("GT", len(ground_truth) + 1, 6),
            "ejecucion_id": _id("RUN", 1, 3),
            "entidad": "vehiculo",
            "registro_id": target["id"],
            "tipo": "DQ_DUP_DOMAIN",
            "severidad": "alta",
            "parametros": '{"unidad":"count","escenario":"early_stage"}',
        })
