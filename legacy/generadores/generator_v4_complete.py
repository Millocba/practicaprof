"""
Synthetic Data Generator v4 - Complete Multi-Source Replication
Replicates all input sources from Auditoria3 with realistic defect injection

Generates 4 independent tables matching real schema:
1. vehiculo (27 cols) - Fleet data from flota/*.xlsx
2. dispositivo (21 cols) - Telemetry from telemetria/*.xlsx
3. reporte_consumo (31 cols) - Fuel reports from consumo/ReporteConsumo/*.xlsx
4. solicitud_combustible (24 cols) - Fuel requests from consumo/Solicitudes/*.xlsx

Reproducible via seed=20260816
Defects injected match normalization pipeline expectations
"""

import random
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Tuple
import pandas as pd

# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class GenerationConfig:
    num_vehicles: int = 200
    num_devices_per_vehicle: float = 0.85
    num_events_per_device: int = 50
    num_fuel_transactions: int = 500
    num_fuel_reports: int = 400
    num_fuel_requests: int = 420
    seed: int = 20260816
    scenario: str = "complete_v4"

    # Defect injection rates (%)
    defect_rate: float = 0.05  # ~5% defect rate across tables

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
    return _letters(2) + _digits(3) + _letters(2)

def _vin() -> str:
    return ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789', k=17))

def _motor_number() -> str:
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=10))

def _date_str(start_offset_days: int = -365, end_offset_days: int = 0) -> str:
    base = datetime(2026, 8, 15)  # Mid-August for realism
    start = base + timedelta(days=start_offset_days)
    end = base + timedelta(days=end_offset_days)
    random_date = start + timedelta(days=random.random() * (end - start).days)
    return random_date.strftime('%d/%m/%Y')

def _datetime_str(start_offset_days: int = -30, end_offset_days: int = 0) -> str:
    base = datetime(2026, 8, 15, 12, 0, 0)
    start = base + timedelta(days=start_offset_days)
    end = base + timedelta(days=end_offset_days)
    random_dt = start + timedelta(seconds=random.random() * (end - start).total_seconds())
    return random_dt.strftime('%d/%m/%Y %H:%M:%S')

def _time_str() -> str:
    return f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"

# ============================================================================
# TABLE 1: VEHICULO (27 cols)
# ============================================================================

def generate_vehiculo(num: int, config: GenerationConfig) -> pd.DataFrame:
    """Generate vehiculo table - matches flota/*.xlsx"""

    dependencias = ['JEFATURA', 'OPERACIONES', 'LOGISTICA', 'APOYO', 'DIRECCIÓN']
    tipos = ['PICK-UP', 'PICK-UP 4X4', 'AUTO', 'CAMIÓN', 'MINIBUS', 'MOTO']
    marcas = ['NISSAN', 'TOYOTA', 'FORD', 'VOLKSWAGEN', 'CHEVROLET', 'HONDA']
    colores = ['BLANCO', 'NEGRO', 'GRIS', 'AZUL', 'ROJO', 'VERDE', None]
    combustibles = ['GASOIL', 'NAFTA', 'GASOLINA', 'GNC']
    relacion = ['A', 'B', 'C', 'D', 'E', 'J', 'K']
    estados = ['En Servicio', 'Fuera de Servicio', 'Baja', 'Mantenimiento']
    procedencias = ['Original', 'Secuestro', 'Donación', None]

    data = []
    for i in range(num):
        matricula = str(_id(10000, 11999))
        dominio = _argentine_domain()

        data.append({
            'Matricula': matricula,
            'Dominio': dominio,
            'Dependencia': random.choice(dependencias),
            'Identificable': random.choice(['SI', 'NO']),
            'TipoVehiculo': random.choice(tipos),
            'Marca': random.choice(marcas),
            'Modelo': random.choice(['FRONTIER', 'HILUX', 'RANGER', 'F100', 'GUSTER']),
            'Color': random.choice(colores),
            'NumeroChasis': _vin() if random.random() > 0.45 else None,
            'NumeroMotor': _motor_number() if random.random() > 0.45 else None,
            'Año': random.randint(2000, 2026),
            'Procedencia': random.choice(procedencias),
            'TipoCombustible': random.choice(combustibles),
            'CapacidadTanque': random.randint(40, 120),
            'RelacionConsumo': random.choice(relacion),
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

# ============================================================================
# TABLE 2: DISPOSITIVO (21 cols)
# ============================================================================

def generate_dispositivo(vehicles: pd.DataFrame, config: GenerationConfig) -> pd.DataFrame:
    """Generate dispositivo table - matches telemetria/*.xlsx"""

    device_types = ['Automotor', 'Motocicleta']
    modelos = ['Starlink ER-01', 'Starlink ER-02', 'Tracker X1', 'Tracker X2']
    grupos = ['ACTIVOS', 'BAJAS / REM', 'MANTENIMIENTO']
    estados_trans = ['Activo', 'Apagado o falla', 'Inactivo']
    estados_ign = ['Vehículo apagado', 'Vehículo encendido']
    estados_mov = ['Detenido', 'Movimiento lento', 'Movimiento rápido']

    data = []
    device_id = 1

    for _, veh in vehicles.iterrows():
        if random.random() < config.num_devices_per_vehicle:
            num_devices = 1 if random.random() > 0.1 else 2
            for _ in range(num_devices):
                data.append({
                    'Secuencia': device_id,
                    'Tipo Dispositivo': random.choice(device_types),
                    'Grupo': random.choice(grupos),
                    'Modelo equipo': random.choice(modelos),
                    'Placa': veh['Dominio'],
                    'MSISDN': _decimal(34.0, 35.0, 10),
                    'Alias': f"{veh['Matricula']} {_id(1000, 9999)}",
                    'IMEI': _id(100000000000000, 999999999999999),
                    'Latitud': _decimal(-34.8, -29.7, 6),
                    'Longitud': _decimal(-65.5, -58.7, 6),
                    'Hora de última transmisión': _datetime_str(-7, 0),
                    'Hora de última posición válida': _datetime_str(-7, 0),
                    'Estado candado': None,  # 100% null
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

# ============================================================================
# TABLE 3: REPORTE_CONSUMO (31 cols)
# ============================================================================

def generate_reporte_consumo(vehicles: pd.DataFrame, num: int, config: GenerationConfig) -> pd.DataFrame:
    """Generate reporte_consumo table - matches consumo/ReporteConsumo/*.xlsx"""

    establecimientos = [
        '02286 - DEMATOR S.A.',
        '31038 - ESTACION FERREYRA SRL',
        '10145 - YPF ESTACION',
        '05020 - SHELL ESTACION',
        '08015 - AXION ESTACION',
    ]
    productos = ['NAFTA', 'GASOIL', 'GNC', 'SUPER']
    origenes = ['BOMBA', 'MANUAL', 'APP', 'TERMINAL']
    divisas = ['ARS', 'USD']

    data = []
    for i in range(num):
        veh = random.choice(vehicles.values)
        litros = _decimal(10, 100, 2)
        precio_pvp = _decimal(1.0, 2.5, 2)
        importe = litros * precio_pvp
        iva_amount = importe * 0.21

        data.append({
            'FECHA': _datetime_str(-30, 0),
            'CONTRATO': 'CRE POLICIA DE LA PROV DE CORDOBA OP',
            'SUBCUENTA': None,  # 100% null
            'CENTRO COSTO': None,  # 100% null
            'ESTABLECIMIENTO': random.choice(establecimientos),
            'DOMICILIO': f'{_letters(10)} {_digits(4)}',
            'LOCALIDAD': random.choice(['CORDOBA', 'LAS PERDICES', 'VILLA MERCEDES']),
            'PROVINCIA': 'CORDOBA',
            'TARJETA': int(veh[18]) if pd.notna(veh[18]) else _id(100000, 999999),
            'CONDUCTOR': veh[23] if pd.notna(veh[23]) else f'{_letters(6)} {_letters(8)}',
            'TIPO IDENTIFICACION CONDUCTOR': random.choice(['DNI', 'PASAPORTE']),
            'NRO IDENTIFICACION CONDUCTOR': veh[21] if pd.notna(veh[21]) else _id(10000000, 45000000),
            'TIPO IDENTIFICACION TARJETA': 'DNI',
            'IDENTIFICACION TARJETA': f'{_digits(8)}',
            'ODOMETRO': _decimal(1000, 500000, 0),
            'ORIGEN DE TRANSACCION': random.choice(origenes),
            'TRX FACTURABLE': random.choice(['SI', 'NO']),
            'REMITO': f'{_digits(8)}' if random.random() > 0.2 else None,
            'PRODUCTO': random.choice(productos),
            'LITROS UNIDADES': litros,
            'PRECIO PVP ESTABLECIMIENTO': int(precio_pvp * 100),
            'IMP TOT PVP ESTABLECIMIENTO': importe,
            'PRECIO YER': _decimal(1.0, 2.5, 2),
            'IMP TOT YER': importe * 0.95,
            'DIVISA': random.choice(divisas),
            'IVA': int(iva_amount * 100),
            'IMP CO2': _decimal(0.5, 5.0, 2),
            'TASA VIAL': _decimal(0.1, 2.0, 2),
            'IMP COMB LIQ': importe + iva_amount,
            'FACTURA': None,  # 100% null
            'EXTRACTO': f'EXT{_digits(6)}' if random.random() > 0.05 else None,
        })

    return pd.DataFrame(data)

# ============================================================================
# TABLE 4: SOLICITUD_COMBUSTIBLE (24 cols)
# ============================================================================

def generate_solicitud_combustible(vehicles: pd.DataFrame, num: int, config: GenerationConfig) -> pd.DataFrame:
    """Generate solicitud_combustible table - matches consumo/Solicitudes/*.xlsx"""

    dependencias = ['JEFATURA', 'OPERACIONES', 'LOGISTICA', 'APOYO']
    estaciones = ['YPF', 'Shell', 'Axion', 'Puma', 'Esso']
    relacion = ['A', 'B', 'C', 'D', 'E', 'J', 'K']

    data = []
    for i in range(num):
        veh = random.choice(vehicles.values)
        litros_auth = random.randint(20, 100)
        litros_loaded = int(litros_auth * random.uniform(0.8, 1.05))  # Small discrepancies

        data.append({
            'Id': 1837245 + i,
            'Fecha': _date_str(-30, 0),
            'Hora': _time_str(),
            'Matricula': veh[0] if pd.notna(veh[0]) else str(_id(10000, 11999)),
            'Dominio': veh[1] if pd.notna(veh[1]) else _argentine_domain(),
            'OdometroRegistrado': int(_decimal(1000, 500000, 0)),
            'Solicitante': f'{_letters(6)} {_letters(8)} (DNI: {_id(10000000, 45000000)})',
            'Rendido': random.choice(['SI', 'NO']),
            'LitrosAutorizados': float(litros_auth),
            'LitrosCargados': float(litros_loaded),
            'CapacidadTanque': veh[14] if pd.notna(veh[14]) else random.randint(40, 120),
            'FechaRendicion': _date_str(-25, 0) if random.random() > 0.1 else None,
            'HoraRendicion': _time_str() if random.random() > 0.1 else None,
            'NumeroTicket': f'{_digits(10)}' if random.random() > 0.1 else None,
            'TarjetaDni': random.choice([True, False]),
            'Dependencia': random.choice(dependencias),
            'DependeciaMovil': random.choice(dependencias) if random.random() > 0.98 else None,
            'BanderaRendicion': random.choice(['PENDIENTE', 'RENDIDO', 'ANULADO']),
            'Cargador': f'{_letters(6)} {_letters(8)}' if random.random() > 0.1 else None,
            'RelacionConsumo': veh[15] if pd.notna(veh[15]) else random.choice(relacion),
            'Anulado': random.choice(['SI', 'NO']),
            'FechaAnulado': _date_str(-20, 0) if random.random() > 0.99 else None,
            'EstacionServicio': random.choice(estaciones) if random.random() > 0.1 else None,
            'DireccionGral': veh[26] if pd.notna(veh[26]) else random.choice(['JEFATURA', 'OPERACIONES']),
        })

    return pd.DataFrame(data)

# ============================================================================
# ORCHESTRATION
# ============================================================================

def generate_dataset(config: GenerationConfig) -> Dict[str, pd.DataFrame]:
    """Main orchestration function"""

    random.seed(config.seed)

    print(f"\n{'='*80}")
    print(f"🚀 SYNTHETIC DATA GENERATION v4 - Complete Multi-Source")
    print(f"{'='*80}\n")

    # Generate all tables
    print("📊 Generating synthetic data sources...\n")

    vehiculo = generate_vehiculo(config.num_vehicles, config)
    print(f"  ✓ vehiculo:                {len(vehiculo):6d} rows × 27 cols")

    dispositivo = generate_dispositivo(vehiculo, config)
    print(f"  ✓ dispositivo:             {len(dispositivo):6d} rows × 21 cols")

    reporte_consumo = generate_reporte_consumo(vehiculo, config.num_fuel_reports, config)
    print(f"  ✓ reporte_consumo:         {len(reporte_consumo):6d} rows × 31 cols")

    solicitud_combustible = generate_solicitud_combustible(vehiculo, config.num_fuel_requests, config)
    print(f"  ✓ solicitud_combustible:   {len(solicitud_combustible):6d} rows × 24 cols")

    ejecucion = pd.DataFrame([{
        'timestamp': datetime.now().isoformat(),
        'seed': config.seed,
        'scenario': config.scenario,
        'num_vehicles': len(vehiculo),
        'num_devices': len(dispositivo),
        'num_fuel_reports': len(reporte_consumo),
        'num_fuel_requests': len(solicitud_combustible),
    }])

    print(f"\n{'='*80}")
    print(f"✅ DATASET GENERATED SUCCESSFULLY")
    print(f"{'='*80}\n")

    return {
        'vehiculo': vehiculo,
        'dispositivo': dispositivo,
        'reporte_consumo': reporte_consumo,
        'solicitud_combustible': solicitud_combustible,
        'ejecucion_dataset': ejecucion,
    }

if __name__ == '__main__':
    config = GenerationConfig(num_vehicles=200)
    tables = generate_dataset(config)

    for name, df in tables.items():
        print(f"{name:30s}: {len(df):6d} rows × {len(df.columns):2d} cols")
