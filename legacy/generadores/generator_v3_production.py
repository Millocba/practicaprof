"""
Synthetic Data Generator v3 - Production Grade
Complete schema matching Auditoria3 real data structure (6560 vehicles × 27 base fields)

Generates:
- vehiculo: 27 columns (flota)
- dispositivo: 21 columns (telemetría)
- evento_telemetria: device events/transactions
- transaccion_combustible: fuel transactions
- ground_truth: defect registry (160+ injected defects)

Reproducible via seed (seed=20260816)
"""

import random
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
import pandas as pd

# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class GenerationConfig:
    """Configuration for dataset generation"""
    num_vehicles: int = 200  # Subset of 6560 for testing
    num_devices_per_vehicle: float = 0.85  # 85% have devices
    num_events_per_device: int = 50
    num_fuel_transactions: int = 500
    seed: int = 20260816
    scenario: str = "early_stage_v2"

    # Defect injection rates
    defect_duplicate_domain_pct: float = 0.02
    defect_duplicate_matricula_pct: float = 0.02
    defect_invalid_domain_pct: float = 0.03
    defect_missing_values_pct: float = 0.05
    defect_invalid_type_pct: float = 0.02
    defect_format_drift_pct: float = 0.04
    defect_date_anomalies_pct: float = 0.03
    defect_inconsistency_pct: float = 0.04

# ============================================================================
# HELPERS
# ============================================================================

def _id(min_val: int = 1, max_val: int = 65535) -> int:
    return random.randint(min_val, max_val)

def _decimal(min_val: float, max_val: float, decimals: int = 2) -> float:
    return round(random.uniform(min_val, max_val), decimals)

def _letters(length: int = 3) -> str:
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=length))

def _digits(length: int = 3) -> str:
    return ''.join(random.choices('0123456789', k=length))

def _argentine_domain() -> str:
    """Generate Argentine license plate (new format: XX###XX)"""
    return _letters(2) + _digits(3) + _letters(2)

def _vin() -> str:
    """Generate VIN-like number (17 chars)"""
    return ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789', k=17))

def _motor_number() -> str:
    """Generate motor number"""
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=10))

def _date_str(start_offset_days: int = -365, end_offset_days: int = 0) -> str:
    """Generate date string"""
    base = datetime(2026, 9, 4)
    start = base + timedelta(days=start_offset_days)
    end = base + timedelta(days=end_offset_days)
    random_date = start + timedelta(days=random.random() * (end - start).days)
    return random_date.strftime('%Y-%m-%d')

def _datetime_str(start_offset_days: int = -30, end_offset_days: int = 0) -> str:
    """Generate datetime string"""
    base = datetime(2026, 9, 4, 12, 0, 0)
    start = base + timedelta(days=start_offset_days)
    end = base + timedelta(days=end_offset_days)
    random_dt = start + timedelta(seconds=random.random() * (end - start).total_seconds())
    return random_dt.strftime('%Y-%m-%d %H:%M:%S')

# ============================================================================
# CLEAN DATA GENERATION
# ============================================================================

def _generate_vehicles(num: int, config: GenerationConfig) -> pd.DataFrame:
    """Generate clean vehiculo table (27 columns - matches real schema)"""

    dependencias = ['JEFATURA', 'OPERACIONES', 'LOGISTICA', 'APOYO', 'DIRECCIÓN']
    tipos_vehiculo = ['PICK-UP', 'PICK-UP 4X4', 'AUTO', 'CAMIÓN', 'MINIBUS', 'MOTO']
    marcas = ['NISSAN', 'TOYOTA', 'FORD', 'VOLKSWAGEN', 'CHEVROLET', 'HONDA', 'YAMAHA']
    colores = ['BLANCO', 'NEGRO', 'GRIS', 'AZUL', 'ROJO', 'VERDE', None]
    combustibles = ['GASOIL', 'NAFTA', 'GASOLINA', 'GNC']
    relacion_consumo = ['A', 'B', 'C', 'D', 'E', 'J', 'K']
    procedencias = ['Original', 'Secuestro', 'Donación', None]
    estados = ['En Servicio', 'Fuera de Servicio', 'Baja', 'Mantenimiento']

    data = []
    for i in range(num):
        matricula = _id(10000, 11999)
        dominio = _argentine_domain()

        data.append({
            'Matricula': str(matricula),
            'Dominio': dominio,
            'Dependencia': random.choice(dependencias),
            'Identificable': random.choice(['SI', 'NO']),
            'TipoVehiculo': random.choice(tipos_vehiculo),
            'Marca': random.choice(marcas),
            'Modelo': random.choice(['FRONTIER', 'HILUX', 'RANGER', 'F100', 'CROSSFOX', 'GUSTER']),
            'Color': random.choice(colores),
            'NumeroChasis': _vin() if random.random() > 0.45 else None,
            'NumeroMotor': _motor_number() if random.random() > 0.45 else None,
            'Año': random.randint(2000, 2026),
            'Procedencia': random.choice(procedencias),
            'TipoCombustible': random.choice(combustibles),
            'CapacidadTanque': random.randint(40, 120),
            'RelacionConsumo': random.choice(relacion_consumo),
            'ExcepcionOdometro': random.choice(['SI', 'NO']),
            'FechaHastaExcepcionOdometro': _date_str(-180, 90) if random.random() > 0.98 else None,
            'NumeroTarjeta': f'{_digits(20)}' if random.random() > 0.05 else None,
            'NumeroContrato': random.randint(1, 7),
            'LimiteSaldo': _decimal(1000000, 10000000, 2),
            'LimiteLitros': random.randint(500, 5000),
            'RetiraDni': _id(10000000, 45000000),
            'RetiraNombre': f'{_letters(6)} {_letters(8)}' if random.random() > 0.05 else None,
            'Cupo': random.randint(20, 200),
            'Estado': random.choice(estados),
            'SubEstado': random.choice(['ACTIVO', 'INACTIVO', None]) if random.random() > 0.51 else None,
            'DireccionGral': random.choice(['JEFATURA', 'OPERACIONES']),
        })

    return pd.DataFrame(data)

def _generate_devices(vehicles: pd.DataFrame, config: GenerationConfig) -> pd.DataFrame:
    """Generate clean dispositivo table (21 columns)"""

    device_types = ['Automotor', 'Motocicleta']
    modelos = ['Starlink ER-01', 'Starlink ER-02', 'Tracker X1', 'Tracker X2']
    grupos = ['ACTIVOS', 'BAJAS / REM', 'MANTENIMIENTO']
    estados_trans = ['Activo', 'Apagado o falla', 'Inactivo']
    estados_ign = ['Vehículo apagado', 'Vehículo encendido']
    estados_mov = ['Detenido', 'Movimiento lento', 'Movimiento rápido']

    data = []
    device_id = 1

    for _, veh in vehicles.iterrows():
        # 85% de vehículos tienen dispositivos, algunos tienen 2
        if random.random() < config.num_devices_per_vehicle:
            num_devices = 1 if random.random() > 0.1 else 2

            for _ in range(num_devices):
                imei = _id(100000000000000, 999999999999999)
                msisdn = _decimal(34.0, 35.0, 10)

                data.append({
                    'Secuencia': device_id,
                    'Tipo Dispositivo': random.choice(device_types),
                    'Grupo': random.choice(grupos),
                    'Modelo equipo': random.choice(modelos),
                    'Placa': veh['Dominio'],
                    'MSISDN': msisdn,
                    'Alias': f"{veh['Matricula']} {_id(1000, 9999)}",
                    'IMEI': imei,
                    'Latitud': _decimal(-34.8, -29.7, 6),
                    'Longitud': _decimal(-65.5, -58.7, 6),
                    'Hora de última transmisión': _datetime_str(-7, 0),
                    'Hora de última posición válida': _datetime_str(-7, 0),
                    'Estado candado': None,  # 100% null in real data
                    'Estado de transmisión': random.choice(estados_trans),
                    'Estado de ignición': random.choice(estados_ign),
                    'Estado de movimiento': random.choice(estados_mov),
                    '% Batería': random.randint(10, 100),
                    'Odómetro (Km)': _decimal(1000, 500000, 2),
                    '% Batería Externa': random.randint(0, 100),
                    'Valor Batería Externa': random.randint(0, 15000),
                    'Horómetro (hrs)': _decimal(100, 10000, 2),
                })
                device_id += 1

    return pd.DataFrame(data)

def _generate_telemetry_events(devices: pd.DataFrame, config: GenerationConfig) -> pd.DataFrame:
    """Generate evento_telemetria table"""

    data = []
    event_id = 1

    for _, device in devices.iterrows():
        for _ in range(config.num_events_per_device):
            data.append({
                'id': event_id,
                'dispositivo_id': device['Secuencia'],
                'fecha_evento': _datetime_str(-30, 0),
                'tipo_evento': random.choice(['ENCENDIDO', 'APAGADO', 'MOVIMIENTO', 'RECARGA', 'ALERTA']),
                'latitud': device['Latitud'] + _decimal(-0.1, 0.1, 6),
                'longitud': device['Longitud'] + _decimal(-0.1, 0.1, 6),
                'velocidad_kmh': _decimal(0, 120, 1),
                'odometro_km': _decimal(1000, 500000, 2),
                'bateria_pct': random.randint(10, 100),
            })
            event_id += 1

    return pd.DataFrame(data)

def _generate_fuel_transactions(vehicles: pd.DataFrame, config: GenerationConfig) -> pd.DataFrame:
    """Generate transaccion_combustible table"""

    data = []
    for trans_id in range(config.num_fuel_transactions):
        veh = random.choice(vehicles.values)

        data.append({
            'id': trans_id + 1,
            'vehiculo_id': veh[0],  # Matricula
            'fecha': _datetime_str(-90, 0),
            'estacion': random.choice(['YPF', 'Shell', 'Axion', 'Puma']),
            'litros': _decimal(10, 100, 2),
            'precio_unitario': _decimal(1.0, 2.5, 2),
            'importe_total': _decimal(100, 250, 2),
            'numero_tarjeta': f"{_digits(20)}",
        })

    return pd.DataFrame(data)

# ============================================================================
# DEFECT INJECTION
# ============================================================================

def _inject_duplicate_dominios(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject duplicate domain defects"""
    if len(vehicles) < 2:
        return vehicles

    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles) - 1))

    for idx in indices:
        # Copy dominio from another vehicle
        source_idx = random.choice([i for i in range(len(vehicles)) if i != idx])
        vehicles.at[idx, 'Dominio'] = vehicles.at[source_idx, 'Dominio']

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_DUP_DOMAIN',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'alta',
            'parametros': json.dumps({'dominio': vehicles.at[idx, 'Dominio']}),
            'descripcion': f"Dominio duplicado: {vehicles.at[idx, 'Dominio']}"
        })

    return vehicles

def _inject_duplicate_matriculas(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject duplicate matricula defects"""
    if len(vehicles) < 2:
        return vehicles

    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles) - 1))

    for idx in indices:
        source_idx = random.choice([i for i in range(len(vehicles)) if i != idx])
        vehicles.at[idx, 'Matricula'] = vehicles.at[source_idx, 'Matricula']

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_DUP_VEH_ID',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'alta',
            'parametros': json.dumps({'matricula': vehicles.at[idx, 'Matricula']}),
            'descripcion': f"Matrícula duplicada: {vehicles.at[idx, 'Matricula']}"
        })

    return vehicles

def _inject_invalid_domains(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject invalid format domain defects"""
    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles)))

    for idx in indices:
        # Generate malformed domains
        bad_domains = [
            _digits(6),  # Only numbers
            _letters(6),  # Only letters
            'XX9999XX',  # Wrong format
            '',  # Empty
        ]
        vehicles.at[idx, 'Dominio'] = random.choice(bad_domains)

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_INVALID_FORMAT',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'media',
            'parametros': json.dumps({'campo': 'Dominio', 'formato': 'XX###XX'}),
            'descripcion': f"Dominio en formato inválido: {vehicles.at[idx, 'Dominio']}"
        })

    return vehicles

def _inject_missing_values(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject missing value defects in required fields"""
    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles)))
    nullable_fields = ['Marca', 'Modelo', 'TipoCombustible', 'NumeroTarjeta']

    for idx in indices:
        field = random.choice(nullable_fields)
        vehicles.at[idx, field] = None

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_MISSING_VALUE',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'media',
            'parametros': json.dumps({'campo': field}),
            'descripcion': f"Valor faltante en {field}"
        })

    return vehicles

def _inject_invalid_types(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject type mismatch defects"""
    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles)))

    # Convert column to object to allow mixed types
    vehicles['Año'] = vehicles['Año'].astype('object')

    for idx in indices:
        bad_value = _letters(4)
        vehicles.at[idx, 'Año'] = bad_value

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_INVALID_TYPE',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'alta',
            'parametros': json.dumps({'campo': 'Año', 'tipo_esperado': 'int', 'tipo_actual': 'str'}),
            'descripcion': f"Tipo de dato inválido en Año: {bad_value}"
        })

    return vehicles

def _inject_format_drift(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject format inconsistencies"""
    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles)))

    for idx in indices:
        vehicles.at[idx, 'Dominio'] = vehicles.at[idx, 'Dominio'].lower()  # Inconsistent case

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_FORMAT_DRIFT',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'baja',
            'parametros': json.dumps({'campo': 'Dominio', 'problema': 'case_inconsistency'}),
            'descripcion': f"Formato inconsistente en Dominio: {vehicles.at[idx, 'Dominio']}"
        })

    return vehicles

def _inject_inconsistencies(vehicles: pd.DataFrame, count: int, gt: List[Dict]) -> pd.DataFrame:
    """Inject logical inconsistencies (e.g., future dates, invalid year)"""
    vehicles = vehicles.copy()
    indices = random.sample(range(len(vehicles)), min(count, len(vehicles)))

    for idx in indices:
        # Future year
        vehicles.at[idx, 'Año'] = 2030

        gt.append({
            'id': len(gt),
            'tipo': 'DQ_INCONSISTENCY',
            'entidad': 'vehiculo',
            'registro_id': vehicles.at[idx, 'Matricula'],
            'severidad': 'media',
            'parametros': json.dumps({'problema': 'year_in_future'}),
            'descripcion': f"Año de vehículo en el futuro: {vehicles.at[idx, 'Año']}"
        })

    return vehicles

# ============================================================================
# ORCHESTRATION
# ============================================================================

def generate_dataset(config: GenerationConfig) -> Dict[str, pd.DataFrame]:
    """Main orchestration function"""

    random.seed(config.seed)

    print(f"\n{'='*80}")
    print(f"🚀 SYNTHETIC DATA GENERATION v3 (Production Grade)")
    print(f"{'='*80}\n")

    # Generate clean tables
    print("📊 Generating clean data...")
    vehicles = _generate_vehicles(config.num_vehicles, config)
    devices = _generate_devices(vehicles, config)
    telemetry = _generate_telemetry_events(devices, config)
    combustible = _generate_fuel_transactions(vehicles, config)

    print(f"  ✓ vehiculo:               {len(vehicles):6d} rows")
    print(f"  ✓ dispositivo:            {len(devices):6d} rows")
    print(f"  ✓ evento_telemetria:      {len(telemetry):6d} rows")
    print(f"  ✓ transaccion_combustible: {len(combustible):6d} rows")

    # Inject defects
    print(f"\n🔴 Injecting defects...")
    gt = []

    vehicles = _inject_duplicate_dominios(vehicles,
        int(len(vehicles) * config.defect_duplicate_domain_pct), gt)
    vehicles = _inject_duplicate_matriculas(vehicles,
        int(len(vehicles) * config.defect_duplicate_matricula_pct), gt)
    vehicles = _inject_invalid_domains(vehicles,
        int(len(vehicles) * config.defect_invalid_domain_pct), gt)
    vehicles = _inject_missing_values(vehicles,
        int(len(vehicles) * config.defect_missing_values_pct), gt)
    vehicles = _inject_invalid_types(vehicles,
        int(len(vehicles) * config.defect_invalid_type_pct), gt)
    vehicles = _inject_format_drift(vehicles,
        int(len(vehicles) * config.defect_format_drift_pct), gt)
    vehicles = _inject_inconsistencies(vehicles,
        int(len(vehicles) * config.defect_inconsistency_pct), gt)

    ground_truth = pd.DataFrame(gt)

    print(f"  ✓ Total defects injected: {len(ground_truth)}")
    if len(ground_truth) > 0:
        print(f"\n  Defects by type:")
        for tipo, count in ground_truth['tipo'].value_counts().items():
            print(f"    - {tipo:30s}: {count:3d}")

    return {
        'vehiculo': vehicles,
        'dispositivo': devices,
        'evento_telemetria': telemetry,
        'transaccion_combustible': combustible,
        'ground_truth': ground_truth,
        'ejecucion_dataset': pd.DataFrame([{
            'timestamp': datetime.now().isoformat(),
            'seed': config.seed,
            'scenario': config.scenario,
            'num_vehicles': len(vehicles),
            'num_defects': len(ground_truth),
        }])
    }

if __name__ == '__main__':
    config = GenerationConfig(num_vehicles=200)
    tables = generate_dataset(config)

    print(f"\n{'='*80}")
    print(f"✅ DATASET GENERATED SUCCESSFULLY")
    print(f"{'='*80}\n")

    for name, df in tables.items():
        print(f"{name:30s}: {len(df):6d} rows × {len(df.columns):2d} cols")
