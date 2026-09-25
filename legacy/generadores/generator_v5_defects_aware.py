"""
Synthetic Data Generator v5 - Defects-Aware with Ground Truth Registry
Replicates all 4 input sources with defects that match pipeline normalization expectations

Defect categories (matching what the pipeline validates & fixes):
1. TEXT_NORMALIZATION: Extra spaces, punctuation, case inconsistencies
2. NUMERIC_FORMAT: Non-numeric chars in DNI/matricula, decimal issues
3. DATE_FORMAT: Invalid dates, inconsistent formats, missing values
4. MATCHING_DEFECTS: Domain duplicates, liters discrepancies, coverage gaps
5. CONSISTENCY_ERRORS: Cross-table key mismatches, logical inconsistencies
6. FIELD_NULLABILITY: Strategic nulls matching real data patterns

Generates ground_truth.csv tracking: row_id, table, column, type, severity, description
"""

import random
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import pandas as pd
import re

# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class GenerationConfig:
    num_vehicles: int = 200
    num_devices_per_vehicle: float = 0.85
    num_fuel_reports: int = 400
    num_fuel_requests: int = 420
    seed: int = 20260816
    scenario: str = "defects_aware_v5"

    # Defect injection rates by category (%)
    text_normalization_rate: float = 0.08
    numeric_format_rate: float = 0.05
    date_format_rate: float = 0.04
    matching_defect_rate: float = 0.06
    consistency_error_rate: float = 0.03

@dataclass
class DefectRecord:
    """Track each injected defect for ground truth"""
    row_id: str
    table: str
    column: str
    defect_type: str
    severity: str  # "baja", "media", "alta"
    description: str
    original_value: Optional[str] = None
    injected_value: Optional[str] = None

# ============================================================================
# GLOBAL REGISTRY
# ============================================================================

defects_registry = []

def record_defect(row_id: str, table: str, column: str, defect_type: str,
                  severity: str, description: str, original: Optional[str] = None,
                  injected: Optional[str] = None):
    """Record a defect for ground truth tracking"""
    defects_registry.append(DefectRecord(
        row_id=row_id,
        table=table,
        column=column,
        defect_type=defect_type,
        severity=severity,
        description=description,
        original_value=original,
        injected_value=injected
    ))

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
    """Generate valid domain XX###XX"""
    return _letters(2) + _digits(3) + _letters(2)

def _argentine_domain_with_defects(row_id: str, defect_rate: float) -> Tuple[str, bool]:
    """Generate domain with potential defects (spaces, punctuation, case)"""
    domain = _argentine_domain()
    if random.random() < defect_rate:
        defect_choice = random.choice(['spaces', 'punctuation', 'mixed_case', 'dash'])
        if defect_choice == 'spaces':
            domain = f"{domain[:2]} {domain[2:5]} {domain[5:]}"
            record_defect(row_id, 'vehiculo', 'Dominio', 'TEXT_NORMALIZATION',
                         'baja', 'Extra spaces in domain', domain.replace(' ', ''), domain)
        elif defect_choice == 'punctuation':
            domain = f"{domain[:2]}.{domain[2:]}"
            record_defect(row_id, 'vehiculo', 'Dominio', 'TEXT_NORMALIZATION',
                         'baja', 'Punctuation in domain', domain.replace('.', ''), domain)
        elif defect_choice == 'mixed_case':
            domain = domain.lower()
            record_defect(row_id, 'vehiculo', 'Dominio', 'TEXT_NORMALIZATION',
                         'baja', 'Lowercase domain', domain.upper(), domain)
        elif defect_choice == 'dash':
            domain = f"{domain[:2]}-{domain[2:]}"
            record_defect(row_id, 'vehiculo', 'Dominio', 'TEXT_NORMALIZATION',
                         'baja', 'Dash in domain', domain.replace('-', ''), domain)
        return domain, True
    return domain, False

def _dni_with_defects(row_id: str, table: str, column: str, defect_rate: float) -> Tuple[str, bool]:
    """Generate DNI with potential format defects (letters, spaces, dashes)"""
    dni = str(_id(10000000, 45000000))
    if random.random() < defect_rate:
        defect_choice = random.choice(['spaces', 'dashes', 'letters'])
        if defect_choice == 'spaces':
            dni = f"{dni[:2]} {dni[2:5]} {dni[5:]}"
            record_defect(row_id, table, column, 'NUMERIC_FORMAT',
                         'baja', 'Spaces in DNI', dni.replace(' ', ''), dni)
        elif defect_choice == 'dashes':
            dni = f"{dni[:2]}-{dni[2:5]}-{dni[5:]}"
            record_defect(row_id, table, column, 'NUMERIC_FORMAT',
                         'baja', 'Dashes in DNI', dni.replace('-', ''), dni)
        elif defect_choice == 'letters':
            dni = f"DNI{dni}"
            record_defect(row_id, table, column, 'NUMERIC_FORMAT',
                         'media', 'Letters in DNI', dni[3:], dni)
        return dni, True
    return dni, False

def _date_str_with_defects(row_id: str, table: str, column: str,
                           defect_rate: float, start_offset_days: int = -30) -> Tuple[str, bool]:
    """Generate date with potential format defects"""
    base = datetime(2026, 8, 15)
    start = base + timedelta(days=start_offset_days)
    end = base
    random_date = start + timedelta(days=random.random() * (end - start).days)

    if random.random() < defect_rate:
        defect_choice = random.choice(['wrong_format', 'invalid_date', 'slash_dash'])

        if defect_choice == 'wrong_format':
            # YYYY/MM/DD instead of DD/MM/YYYY
            date_str = random_date.strftime('%Y/%m/%d')
            record_defect(row_id, table, column, 'DATE_FORMAT',
                         'media', 'Wrong date format (YYYY/MM/DD)',
                         random_date.strftime('%d/%m/%Y'), date_str)
        elif defect_choice == 'invalid_date':
            # Non-existent date like 31/02/2026
            date_str = "31/02/2026"
            record_defect(row_id, table, column, 'DATE_FORMAT',
                         'media', 'Invalid date (31/02)',
                         random_date.strftime('%d/%m/%Y'), date_str)
        elif defect_choice == 'slash_dash':
            # DD-MM-YYYY instead of DD/MM/YYYY
            date_str = random_date.strftime('%d-%m-%Y')
            record_defect(row_id, table, column, 'DATE_FORMAT',
                         'baja', 'Dashes instead of slashes in date',
                         random_date.strftime('%d/%m/%Y'), date_str)

        return date_str, True

    return random_date.strftime('%d/%m/%Y'), False

def _vin() -> str:
    return ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789', k=17))

def _motor_number() -> str:
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=10))

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
    """Generate vehiculo table with defect injection"""

    dependencias = ['JEFATURA', 'OPERACIONES', 'LOGISTICA', 'APOYO', 'DIRECCIÓN']
    tipos = ['PICK-UP', 'PICK-UP 4X4', 'AUTO', 'CAMIÓN', 'MINIBUS', 'MOTO']
    marcas = ['NISSAN', 'TOYOTA', 'FORD', 'VOLKSWAGEN', 'CHEVROLET', 'HONDA']
    colores = ['BLANCO', 'NEGRO', 'GRIS', 'AZUL', 'ROJO', 'VERDE', None]
    combustibles = ['GASOIL', 'NAFTA', 'GASOLINA', 'GNC']
    relacion = ['A', 'B', 'C', 'D', 'E', 'J', 'K']
    estados = ['En Servicio', 'Fuera de Servicio', 'Baja', 'Mantenimiento']
    procedencias = ['Original', 'Secuestro', 'Donación', None]

    data = []
    domains_generated = set()

    for i in range(num):
        row_id = f"vehiculo_{i:06d}"
        matricula = str(_id(10000, 11999))

        # Intentionally create some duplicate domains to test matching
        if random.random() < 0.03 and len(domains_generated) > 10:
            # Reuse an existing domain (defect)
            dominio = random.choice(list(domains_generated))
            record_defect(row_id, 'vehiculo', 'Dominio', 'MATCHING_DEFECT',
                         'media', 'Duplicate domain', dominio, dominio)
        else:
            dominio, had_defect = _argentine_domain_with_defects(row_id, config.text_normalization_rate)
            if dominio not in domains_generated:
                domains_generated.add(dominio.replace(' ', '').replace('-', '').replace('.', '').upper())

        # DNI defects
        retry_dni, dni_defect = _dni_with_defects(row_id, 'vehiculo', 'RetiraDni',
                                                    config.numeric_format_rate)

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
            'Año': str(random.randint(2000, 2026)) if random.random() > 0.95 else random.randint(2000, 2026),  # Inject string year
            'Procedencia': random.choice(procedencias),
            'TipoCombustible': random.choice(combustibles),
            'CapacidadTanque': random.randint(40, 120),
            'RelacionConsumo': random.choice(relacion),
            'ExcepcionOdometro': random.choice(['SI', 'NO']),
            'FechaHastaExcepcionOdometro': _date_str_with_defects(row_id, 'vehiculo',
                                                                   'FechaHastaExcepcionOdometro',
                                                                   config.date_format_rate, -180)[0]
                                                                   if random.random() > 0.98 else None,
            'NumeroTarjeta': f'{_digits(20)}' if random.random() > 0.05 else None,
            'NumeroContrato': random.randint(1, 7),
            'LimiteSaldo': _decimal(1000000, 10000000, 2),
            'LimiteLitros': random.randint(500, 5000),
            'RetiraDni': retry_dni,
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
    """Generate dispositivo table with defect injection"""

    device_types = ['Automotor', 'Motocicleta']
    modelos = ['Starlink ER-01', 'Starlink ER-02', 'Tracker X1', 'Tracker X2']
    grupos = ['ACTIVOS', 'BAJAS / REM', 'MANTENIMIENTO']
    estados_trans = ['Activo', 'Apagado o falla', 'Inactivo']
    estados_ign = ['Vehículo apagado', 'Vehículo encendido']
    estados_mov = ['Detenido', 'Movimiento lento', 'Movimiento rápido']

    data = []
    device_id = 1

    for idx, veh in vehicles.iterrows():
        if random.random() < config.num_devices_per_vehicle:
            num_devices = 1 if random.random() > 0.1 else 2
            for _ in range(num_devices):
                row_id = f"dispositivo_{device_id:06d}"
                placa = veh['Dominio']

                # Apply text normalization defects to placa
                if random.random() < config.text_normalization_rate:
                    defect = random.choice(['space', 'lower'])
                    if defect == 'space':
                        placa = f"{placa[:2]} {placa[2:]}"
                    else:
                        placa = placa.lower()

                data.append({
                    'Secuencia': device_id,
                    'Tipo Dispositivo': random.choice(device_types),
                    'Grupo': random.choice(grupos),
                    'Modelo equipo': random.choice(modelos),
                    'Placa': placa,
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
    """Generate reporte_consumo with defect injection"""

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
        row_id = f"reporte_consumo_{i:06d}"
        veh = random.choice(vehicles.values)
        litros = _decimal(10, 100, 2)
        precio_pvp = _decimal(1.0, 2.5, 2)
        importe = litros * precio_pvp
        iva_amount = importe * 0.21

        # Inject matching defects (liters discrepancies for later solicitud comparison)
        if random.random() < config.matching_defect_rate:
            # Over/under report liters
            litros = litros * random.uniform(0.5, 1.5)
            record_defect(row_id, 'reporte_consumo', 'LITROS UNIDADES', 'MATCHING_DEFECT',
                         'media', 'Liters discrepancy for matching', str(litros * 2), str(litros))

        date_str, date_defect = _date_str_with_defects(row_id, 'reporte_consumo', 'FECHA',
                                                        config.date_format_rate, -30)

        data.append({
            'FECHA': date_str,
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
    """Generate solicitud_combustible with defect injection"""

    dependencias = ['JEFATURA', 'OPERACIONES', 'LOGISTICA', 'APOYO']
    estaciones = ['YPF', 'Shell', 'Axion', 'Puma', 'Esso']
    relacion = ['A', 'B', 'C', 'D', 'E', 'J', 'K']

    data = []
    for i in range(num):
        row_id = f"solicitud_combustible_{i:06d}"
        veh = random.choice(vehicles.values)
        litros_auth = random.randint(20, 100)
        litros_loaded = int(litros_auth * random.uniform(0.8, 1.05))

        # Inject consistency defects (loaded > authorized)
        if random.random() < config.consistency_error_rate:
            litros_loaded = int(litros_auth * 1.15)  # Over-charge
            record_defect(row_id, 'solicitud_combustible', 'LitrosCargados', 'CONSISTENCY_ERROR',
                         'media', 'Liters charged exceed authorized', str(litros_auth), str(litros_loaded))

        data.append({
            'Id': 1837245 + i,
            'Fecha': _date_str_with_defects(row_id, 'solicitud_combustible', 'Fecha',
                                           config.date_format_rate, -30)[0],
            'Hora': _time_str(),
            'Matricula': veh[0] if pd.notna(veh[0]) else str(_id(10000, 11999)),
            'Dominio': veh[1] if pd.notna(veh[1]) else _argentine_domain(),
            'OdometroRegistrado': int(_decimal(1000, 500000, 0)),
            'Solicitante': f'{_letters(6)} {_letters(8)} (DNI: {_id(10000000, 45000000)})',
            'Rendido': random.choice(['SI', 'NO']),
            'LitrosAutorizados': float(litros_auth),
            'LitrosCargados': float(litros_loaded),
            'CapacidadTanque': veh[14] if pd.notna(veh[14]) else random.randint(40, 120),
            'FechaRendicion': _date_str_with_defects(row_id, 'solicitud_combustible', 'FechaRendicion',
                                                      config.date_format_rate, -25)[0]
                                                      if random.random() > 0.1 else None,
            'HoraRendicion': _time_str() if random.random() > 0.1 else None,
            'NumeroTicket': f'{_digits(10)}' if random.random() > 0.1 else None,
            'TarjetaDni': random.choice([True, False]),
            'Dependencia': random.choice(dependencias),
            'DependeciaMovil': random.choice(dependencias) if random.random() > 0.98 else None,
            'BanderaRendicion': random.choice(['PENDIENTE', 'RENDIDO', 'ANULADO']),
            'Cargador': f'{_letters(6)} {_letters(8)}' if random.random() > 0.1 else None,
            'RelacionConsumo': veh[15] if pd.notna(veh[15]) else random.choice(relacion),
            'Anulado': random.choice(['SI', 'NO']),
            'FechaAnulado': _date_str_with_defects(row_id, 'solicitud_combustible', 'FechaAnulado',
                                                    config.date_format_rate, -20)[0]
                                                    if random.random() > 0.99 else None,
            'EstacionServicio': random.choice(estaciones) if random.random() > 0.1 else None,
            'DireccionGral': veh[26] if pd.notna(veh[26]) else random.choice(['JEFATURA', 'OPERACIONES']),
        })

    return pd.DataFrame(data)

# ============================================================================
# GROUND TRUTH REGISTRY
# ============================================================================

def create_ground_truth_dataframe() -> pd.DataFrame:
    """Convert defects registry to DataFrame"""
    if not defects_registry:
        return pd.DataFrame(columns=['row_id', 'table', 'column', 'defect_type', 'severity', 'description', 'original_value', 'injected_value'])

    return pd.DataFrame([
        {
            'row_id': d.row_id,
            'table': d.table,
            'column': d.column,
            'defect_type': d.defect_type,
            'severity': d.severity,
            'description': d.description,
            'original_value': d.original_value,
            'injected_value': d.injected_value,
        }
        for d in defects_registry
    ])

# ============================================================================
# ORCHESTRATION
# ============================================================================

def generate_dataset(config: GenerationConfig) -> Dict[str, pd.DataFrame]:
    """Main orchestration function with defect-aware generation"""

    global defects_registry
    defects_registry = []  # Reset registry
    random.seed(config.seed)

    print(f"\n{'='*100}")
    print(f"🚀 SYNTHETIC DATA GENERATION v5 - Defects-Aware with Ground Truth")
    print(f"{'='*100}\n")

    print("📊 Generating synthetic data sources with injected defects...\n")

    vehiculo = generate_vehiculo(config.num_vehicles, config)
    print(f"  ✓ vehiculo:                {len(vehiculo):6d} rows × 27 cols")

    dispositivo = generate_dispositivo(vehiculo, config)
    print(f"  ✓ dispositivo:             {len(dispositivo):6d} rows × 21 cols")

    reporte_consumo = generate_reporte_consumo(vehiculo, config.num_fuel_reports, config)
    print(f"  ✓ reporte_consumo:         {len(reporte_consumo):6d} rows × 31 cols")

    solicitud_combustible = generate_solicitud_combustible(vehiculo, config.num_fuel_requests, config)
    print(f"  ✓ solicitud_combustible:   {len(solicitud_combustible):6d} rows × 24 cols")

    # Create ground truth registry
    ground_truth = create_ground_truth_dataframe()
    print(f"  ✓ ground_truth:            {len(ground_truth):6d} rows × 8 cols (defects tracked)")

    ejecucion = pd.DataFrame([{
        'timestamp': datetime.now().isoformat(),
        'seed': config.seed,
        'scenario': config.scenario,
        'num_vehicles': len(vehiculo),
        'num_devices': len(dispositivo),
        'num_fuel_reports': len(reporte_consumo),
        'num_fuel_requests': len(solicitud_combustible),
        'num_defects': len(ground_truth),
        'defect_coverage': f"{100*len(ground_truth)/(len(vehiculo)+len(dispositivo)+len(reporte_consumo)+len(solicitud_combustible)):.1f}%",
    }])

    # Summary by defect type
    if len(ground_truth) > 0:
        print(f"\n📊 DEFECT INJECTION SUMMARY:")
        for dtype in ground_truth['defect_type'].unique():
            count = len(ground_truth[ground_truth['defect_type'] == dtype])
            print(f"  {dtype:30s} {count:4d} defects")

        print(f"\n  By severity:")
        for sev in ['alta', 'media', 'baja']:
            count = len(ground_truth[ground_truth['severity'] == sev])
            if count > 0:
                print(f"    {sev:10s} {count:4d} ({100*count/len(ground_truth):5.1f}%)")

    print(f"\n{'='*100}")
    print(f"✅ DATASET GENERATED WITH DEFECTS")
    print(f"{'='*100}\n")

    return {
        'vehiculo': vehiculo,
        'dispositivo': dispositivo,
        'reporte_consumo': reporte_consumo,
        'solicitud_combustible': solicitud_combustible,
        'ground_truth': ground_truth,
        'ejecucion_dataset': ejecucion,
    }

if __name__ == '__main__':
    config = GenerationConfig(num_vehicles=200)
    tables = generate_dataset(config)

    for name, df in tables.items():
        print(f"{name:30s}: {len(df):6d} rows × {len(df.columns):2d} cols")
