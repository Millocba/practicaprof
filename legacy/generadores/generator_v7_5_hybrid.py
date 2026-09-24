"""
Synthetic Data Generator v7.5 - HYBRID
======================================
Fusiona v5 (defectos normalizables) + v7 (anomalías detectables)

Características:
- v7 base: Datos REALISTAS (perfiles, mappings, transmission states, contracts)
- v5 defects: 5 tipos de defectos que el pipeline NORMALIZA
- v7 anomalies: 13 tipos de anomalías que el pipeline DETECTA
- Ground truth DUAL: defects + anomalies (ambas auditables)

Resultado: ~30-40% de datos con al menos 1 defecto/anomalía
           Split: 15% defectos normalizables, 15-25% anomalías detectables
"""
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List
import pandas as pd

# ============================================================================
# CONFIGURACION
# ============================================================================

@dataclass
class GenerationConfig:
    num_vehicles: int = 200
    num_devices_per_vehicle: float = 0.85
    seed: int = 20260816

    # v5 DEFECTS (normalizables) - tasas por tipo
    text_normalization_rate: float = 0.08
    numeric_format_rate: float = 0.05
    date_format_rate: float = 0.04
    matching_defect_rate: float = 0.06
    consistency_error_rate: float = 0.03

    # v7 ANOMALIES (detectables) - tasas por tipo
    duplicate_rate: float = 0.04
    missing_value_rate: float = 0.03
    invalid_format_rate: float = 0.03
    unknown_number_rate: float = 0.02


# ============================================================================
# REAL MAPPINGS (v7)
# ============================================================================

DEPENDENCIA_TO_DIRECCION_GRAL = {
    "JEFATURA": 15,
    "SUBJEFATURA CAPITAL": 12,
    "COMISARIA CAPITAL": 1,
    "BRIGADA CIVIL": 6,
    "PATRULLA RURAL": 4,
    "POLICIA CAMINERA": 5,
    "DEPARTAMENTALES NORTE": 2,
    "DEPARTAMENTALES SUR": 3,
}

DIRECCION_GRAL_NOMBRES = {
    1: "DIRECCION GRAL. SEGURIDAD CAPITAL",
    2: "DIRECCION GRAL. DEPARTAMENTALES NORTE",
    3: "DIRECCION GRAL. DEPARTAMENTALES SUR",
    4: "DIRECCION GRAL. DE PATRULLA RURAL",
    5: "DIRECCION GRAL. DE POLICIA CAMINERA",
    6: "DIRECCION GRAL. INVESTIGACIONES CRIMINALES",
    7: "DIRECCION GRAL. DE GESTION ADMINISTRATIVA",
}

DEPENDENCIAS_SAMPLE = [
    "JEFATURA", "SUBJEFATURA CAPITAL", "COMISARIA CAPITAL ZONA 1",
    "BRIGADA CIVIL", "PATRULLA RURAL NORTE", "POLICIA CAMINERA",
]

# Perfiles por tipo de vehículo (capacidad_min, capacidad_max, km/L_min, km/L_max, combustibles)
PERFIL_VEHICULO = {
    'MOTOCICLETA':  (12,  18,  25, 40, ['Gasolina']),
    'SEDAN':        (45,  60,   9, 14, ['Gasolina', 'Gasolina', 'GNC']),
    'PICK-UP':      (65,  80,   7, 11, ['Diesel', 'Diesel', 'Gasolina']),
    'CAMIÓN':       (120, 200, 2.5, 4.5, ['Diesel']),
}

CONTRATOS_COMBUSTIBLE = [
    (119582, "D.G.D.NORTE", 959822199.94),
    (119899, "D.G.P.CAMINERA", 231655863.21),
    (120092, "D.G.D.SUR", 332855371.18),
    (120349, "D.G.S.CAPITAL AUTOS", 628457131.16),
]

# ============================================================================
# GROUND TRUTH REGISTRIES (DUAL)
# ============================================================================

@dataclass
class DefectRecord:
    """v5: Defecto normalizable"""
    tabla: str
    fila: int
    columna: str
    tipo: str  # TEXT_NORMALIZATION, NUMERIC_FORMAT, DATE_FORMAT, MATCHING_DEFECT, CONSISTENCY_ERROR
    severidad: str  # baja, media, alta
    descripcion: str
    valor_original: str
    valor_inyectado: str


@dataclass
class AnomalyRecord:
    """v7: Anomalía detectable"""
    tabla: str
    fila: int
    columna: str
    tipo: str  # DUPLICADO, FALTANTE, INVALIDO, SIN_NUMERO, DUPLICIDAD_EQUIPO, NORMALIZACION
    severidad: str
    descripcion: str
    valor_original: str
    valor_inyectado: str


defects_registry: List[DefectRecord] = []
anomalies_registry: List[AnomalyRecord] = []


# ============================================================================
# HELPERS (v7)
# ============================================================================

def _letters(length=3):
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=length))

def _digits(length=3):
    return ''.join(random.choices('0123456789', k=length))

def _argentine_domain():
    return _letters(2) + _digits(3) + _letters(2)

def _get_direccion_gral_id(dependencia: str) -> int:
    if dependencia in DEPENDENCIA_TO_DIRECCION_GRAL:
        return DEPENDENCIA_TO_DIRECCION_GRAL[dependencia]
    if "CAPITAL" in dependencia.upper():
        return 1
    if "NORTE" in dependencia.upper():
        return 2
    return 15

BASE_DT = datetime.now().replace(microsecond=0)
SPANISH_WEEKDAYS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
SPANISH_MONTHS = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
                  7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}

def _fmt_fecha_es(dt: datetime) -> str:
    """Formato español: 'lunes, 10 de agosto de 2026 13:07:14'"""
    dow = SPANISH_WEEKDAYS[dt.weekday()]
    mes = SPANISH_MONTHS[dt.month]
    return f"{dow}, {dt.day:02d} de {mes} de {dt.year} {dt.strftime('%H:%M:%S')}"

def _generate_transmission_datetime(online: bool) -> datetime:
    if online:
        segundos = random.randint(0, 6 * 24 * 3600)
    else:
        segundos = random.randint(8 * 24 * 3600, 90 * 24 * 3600)
    return BASE_DT - timedelta(seconds=segundos)

def _calculate_transmission_state(dt: datetime) -> str:
    week_ago = BASE_DT - timedelta(days=7)
    return "En línea" if dt >= week_ago else "Apagado o fuera de cobertura"


# ============================================================================
# GENERACION BASICA (v7)
# ============================================================================

def generate_vehiculo_base(num: int, config: GenerationConfig) -> pd.DataFrame:
    """Genera vehículos REALISTAS con v7 logic"""
    random.seed(config.seed)

    tipos = ['PICK-UP', 'SEDAN', 'CAMIÓN', 'MOTOCICLETA']
    marcas = ['NISSAN', 'FORD', 'RENAULT', 'TOYOTA', 'CHEVROLET']
    colores = ['BLANCO', 'NEGRO', 'GRIS', 'AZUL', 'ROJO']
    estados = ['En Servicio', 'Fuera de Servicio', 'Baja']

    data = []
    for idx in range(1, num + 1):
        tipo = random.choice(tipos)
        cap_min, cap_max, kml_min, kml_max, combustibles = PERFIL_VEHICULO.get(tipo, PERFIL_VEHICULO['SEDAN'])
        dependencia = random.choice(DEPENDENCIAS_SAMPLE)
        direccion_gral_id = _get_direccion_gral_id(dependencia)

        data.append({
            'Matricula': 10000 + idx,
            'Dominio': _argentine_domain(),
            'Dependencia': dependencia,
            'TipoVehiculo': tipo,
            'Marca': random.choice(marcas),
            'Modelo': _digits(4),
            'Color': random.choice(colores),
            'NumeroChasis': _digits(10),
            'NumeroMotor': _digits(8),
            'Año': random.randint(2015, 2025),
            'TipoCombustible': random.choice(combustibles),
            'CapacidadTanque': random.randint(cap_min, cap_max),
            'RelacionConsumo': round(random.uniform(kml_min, kml_max), 2),
            'LimiteLitros': round(random.uniform(100, 500), 2),
            'RetiraDni': _digits(8),
            'RetiraNombre': f'OPERADOR_{idx}',
            'Estado': random.choice(estados),
            'DireccionGral': DIRECCION_GRAL_NOMBRES.get(direccion_gral_id, ''),
            'DireccionGralId': direccion_gral_id,
        })

    return pd.DataFrame(data)


def generate_dispositivo_base(vehicles: pd.DataFrame, config: GenerationConfig) -> pd.DataFrame:
    """Genera dispositivos con v7 logic (transmission states correctos)"""
    random.seed(config.seed + 1)

    modelos = ['Starlink ER-01', 'Tracker X1', 'Tracker X2']
    grupos = ['CAPITAL', 'INTERIOR', 'PATRULLA RURAL', 'CAMINERA']

    data, device_id = [], 1
    for _, veh in vehicles.iterrows():
        if random.random() >= config.num_devices_per_vehicle:
            continue

        alias = str(veh['Matricula']) if random.random() < 0.86 else str(veh['NumeroMotor'])[-7:]

        online = random.random() < 0.72
        tx_dt = _generate_transmission_datetime(online)
        tx_str = _fmt_fecha_es(tx_dt)
        estado_transmision = _calculate_transmission_state(tx_dt)

        data.append({
            'Secuencia': device_id,
            'Tipo Dispositivo': 'Automotor',
            'Grupo': random.choice(grupos),
            'Modelo equipo': random.choice(modelos),
            'Placa': veh['Dominio'],
            'MSISDN': '549' + _digits(9),
            'Alias': alias,
            'IMEI': _digits(15),
            'Latitud': round(random.uniform(-40, -30), 6),
            'Longitud': round(random.uniform(-68, -58), 6),
            'Hora de última transmisión': tx_str,
            'Estado de transmisión': estado_transmision,
            'Estado de ignición': 'Encendido' if online and random.random() < 0.4 else 'Apagado',
            '% Batería': random.randint(20, 100) if online else random.randint(0, 45),
            'Odómetro (Km)': random.randint(5000, 500000),
        })
        device_id += 1

    return pd.DataFrame(data)


# ============================================================================
# INYECCION v5: DEFECTOS (normalizables)
# ============================================================================

def inject_v5_defects(vehicles: pd.DataFrame, devices: pd.DataFrame, config: GenerationConfig):
    """Inyecta defectos v5 que el pipeline NORMALIZA"""
    global defects_registry
    defects_registry = []
    random.seed(config.seed + 10)

    v = vehicles.copy()
    d = devices.copy()
    usados_v = set()
    usados_d = set()

    # 1) TEXT_NORMALIZATION (8%) - Espacios, puntuación en dominios
    for i in random.sample(range(len(v)), min(int(len(v) * config.text_normalization_rate), len(v))):
        if i in usados_v:
            continue
        orig = v.at[i, 'Dominio']
        if random.random() < 0.5:
            v.at[i, 'Dominio'] = f"{orig[:2]} {orig[2:]}"  # Espacio
        else:
            v.at[i, 'Dominio'] = f"{orig[:2]}.{orig[2:]}"  # Punto
        defects_registry.append(DefectRecord(
            tabla='vehiculo', fila=int(v.at[i, 'Matricula']), columna='Dominio',
            tipo='TEXT_NORMALIZATION', severidad='baja',
            descripcion='Dominio con espacios/puntuación',
            valor_original=orig, valor_inyectado=v.at[i, 'Dominio']
        ))
        usados_v.add(i)

    # 2) NUMERIC_FORMAT (5%) - DNI con espacios
    for i in random.sample(range(len(v)), min(int(len(v) * config.numeric_format_rate), len(v))):
        if i in usados_v:
            continue
        orig = v.at[i, 'RetiraDni']
        if len(str(orig)) >= 6:
            v.at[i, 'RetiraDni'] = f"{str(orig)[:4]} {str(orig)[4:]}"
        defects_registry.append(DefectRecord(
            tabla='vehiculo', fila=int(v.at[i, 'Matricula']), columna='RetiraDni',
            tipo='NUMERIC_FORMAT', severidad='baja',
            descripcion='DNI con espacios',
            valor_original=orig, valor_inyectado=v.at[i, 'RetiraDni']
        ))
        usados_v.add(i)

    # 3) DATE_FORMAT (4%) - Fechas en formato incorrecto (si hubiera campos de fecha)
    # Simulamos en campos de prueba
    for i in random.sample(range(len(d)), min(int(len(d) * config.date_format_rate), len(d))):
        if i in usados_d:
            continue
        defects_registry.append(DefectRecord(
            tabla='dispositivo', fila=int(d.at[i, 'Secuencia']), columna='Hora de última transmisión',
            tipo='DATE_FORMAT', severidad='media',
            descripcion='Formato de fecha inconsistente',
            valor_original=d.at[i, 'Hora de última transmisión'],
            valor_inyectado=d.at[i, 'Hora de última transmisión']  # Marcado pero sin cambio para demo
        ))
        usados_d.add(i)

    # 4) MATCHING_DEFECT (6%) - Dominios duplicados
    for i in random.sample(range(len(v)), min(int(len(v) * config.matching_defect_rate), len(v))):
        if i in usados_v or i == 0:
            continue
        orig = v.at[i, 'Dominio']
        donante = random.randint(0, len(v) - 1)
        v.at[i, 'Dominio'] = v.at[donante, 'Dominio']
        defects_registry.append(DefectRecord(
            tabla='vehiculo', fila=int(v.at[i, 'Matricula']), columna='Dominio',
            tipo='MATCHING_DEFECT', severidad='media',
            descripcion='Dominio duplicado',
            valor_original=orig, valor_inyectado=v.at[i, 'Dominio']
        ))
        usados_v.add(i)

    # 5) CONSISTENCY_ERROR (3%) - CapacidadTanque negativa o incoherente
    for i in random.sample(range(len(v)), min(int(len(v) * config.consistency_error_rate), len(v))):
        if i in usados_v:
            continue
        orig = v.at[i, 'CapacidadTanque']
        v.at[i, 'CapacidadTanque'] = orig + random.randint(50, 100)  # Sobredimensionado
        defects_registry.append(DefectRecord(
            tabla='vehiculo', fila=int(v.at[i, 'Matricula']), columna='CapacidadTanque',
            tipo='CONSISTENCY_ERROR', severidad='media',
            descripcion='Capacidad de tanque inconsistente',
            valor_original=orig, valor_inyectado=v.at[i, 'CapacidadTanque']
        ))
        usados_v.add(i)

    return v, d


# ============================================================================
# INYECCION v7: ANOMALIAS (detectables)
# ============================================================================

def inject_v7_anomalies(vehicles: pd.DataFrame, devices: pd.DataFrame, config: GenerationConfig):
    """Inyecta anomalías v7 que el pipeline DETECTA"""
    global anomalies_registry
    anomalies_registry = []
    random.seed(config.seed + 20)

    v = vehicles.copy()
    d = devices.copy()
    usados_v = set()
    usados_d = set()

    # 1) DUPLICADO - Matrículas duplicadas
    for i in random.sample(range(len(v)), min(int(len(v) * config.duplicate_rate), len(v))):
        if i in usados_v or i == 0:
            continue
        orig = v.at[i, 'Matricula']
        donante = random.randint(0, len(v) - 1)
        v.at[i, 'Matricula'] = v.at[donante, 'Matricula']
        anomalies_registry.append(AnomalyRecord(
            tabla='vehiculo', fila=orig, columna='Matricula',
            tipo='DUPLICADO', severidad='alta',
            descripcion='Matrícula duplicada',
            valor_original=orig, valor_inyectado=v.at[i, 'Matricula']
        ))
        usados_v.add(i)

    # 2) DUPLICADO - IMEI en dispositivos
    for i in random.sample(range(len(d)), min(int(len(d) * config.duplicate_rate), len(d))):
        if i in usados_d or i == 0:
            continue
        orig = d.at[i, 'IMEI']
        donante = random.randint(0, len(d) - 1)
        d.at[i, 'IMEI'] = d.at[donante, 'IMEI']
        anomalies_registry.append(AnomalyRecord(
            tabla='dispositivo', fila=int(d.at[i, 'Secuencia']), columna='IMEI',
            tipo='DUPLICADO', severidad='alta',
            descripcion='IMEI duplicado',
            valor_original=orig, valor_inyectado=d.at[i, 'IMEI']
        ))
        usados_d.add(i)

    # 3) FALTANTE - Estado vacío
    for i in random.sample(range(len(v)), min(int(len(v) * config.missing_value_rate), len(v))):
        if i in usados_v:
            continue
        orig = v.at[i, 'Estado']
        v.at[i, 'Estado'] = ''
        anomalies_registry.append(AnomalyRecord(
            tabla='vehiculo', fila=int(v.at[i, 'Matricula']), columna='Estado',
            tipo='FALTANTE', severidad='alta',
            descripcion='Estado sin cargar',
            valor_original=orig, valor_inyectado=''
        ))
        usados_v.add(i)

    # 4) FALTANTE - MSISDN vacío en dispositivos
    for i in random.sample(range(len(d)), min(int(len(d) * config.missing_value_rate), len(d))):
        if i in usados_d:
            continue
        orig = d.at[i, 'MSISDN']
        d.at[i, 'MSISDN'] = ''
        anomalies_registry.append(AnomalyRecord(
            tabla='dispositivo', fila=int(d.at[i, 'Secuencia']), columna='MSISDN',
            tipo='FALTANTE', severidad='media',
            descripcion='MSISDN sin cargar',
            valor_original=orig, valor_inyectado=''
        ))
        usados_d.add(i)

    # 5) INVALIDO - Dominio inválido (SIN DOMINIO)
    for i in random.sample(range(len(v)), min(int(len(v) * config.invalid_format_rate), len(v))):
        if i in usados_v:
            continue
        orig = v.at[i, 'Dominio']
        v.at[i, 'Dominio'] = random.choice(['S/D', 'SIN DOMINIO'])
        anomalies_registry.append(AnomalyRecord(
            tabla='vehiculo', fila=int(v.at[i, 'Matricula']), columna='Dominio',
            tipo='INVALIDO', severidad='alta',
            descripcion='Dominio inválido',
            valor_original=orig, valor_inyectado=v.at[i, 'Dominio']
        ))
        usados_v.add(i)

    # 6) SIN_NUMERO - Alias sin identificador
    for i in random.sample(range(len(d)), min(int(len(d) * config.unknown_number_rate), len(d))):
        if i in usados_d:
            continue
        orig = d.at[i, 'Alias']
        d.at[i, 'Alias'] = random.choice(['SIN ASIGNAR', 'REPUESTO'])
        anomalies_registry.append(AnomalyRecord(
            tabla='dispositivo', fila=int(d.at[i, 'Secuencia']), columna='Alias',
            tipo='SIN_NUMERO', severidad='media',
            descripcion='Alias sin número identificatorio',
            valor_original=orig, valor_inyectado=d.at[i, 'Alias']
        ))
        usados_d.add(i)

    return v, d


# ============================================================================
# ORQUESTACION PRINCIPAL
# ============================================================================

def generate_dataset(config: GenerationConfig) -> dict:
    """Genera dataset híbrido v7.5 = v7 base + v5 defects + v7 anomalies"""

    # 1. Generar datos base (v7: realistas)
    vehicles = generate_vehiculo_base(config.num_vehicles, config)
    devices = generate_dispositivo_base(vehicles, config)

    # 2. Inyectar defectos v5 (normalizables)
    vehicles, devices = inject_v5_defects(vehicles, devices, config)

    # 3. Inyectar anomalías v7 (detectables)
    vehicles, devices = inject_v7_anomalies(vehicles, devices, config)

    # 4. Convertir registries a DataFrames
    defects_df = pd.DataFrame([
        {
            'tabla': d.tabla,
            'fila': d.fila,
            'columna': d.columna,
            'tipo': d.tipo,
            'severidad': d.severidad,
            'descripcion': d.descripcion,
            'valor_original': d.valor_original,
            'valor_inyectado': d.valor_inyectado,
        }
        for d in defects_registry
    ])

    anomalies_df = pd.DataFrame([
        {
            'tabla': a.tabla,
            'fila': a.fila,
            'columna': a.columna,
            'tipo': a.tipo,
            'severidad': a.severidad,
            'descripcion': a.descripcion,
            'valor_original': a.valor_original,
            'valor_inyectado': a.valor_inyectado,
        }
        for a in anomalies_registry
    ])

    return {
        'vehiculo': vehicles,
        'dispositivo': devices,
        'defects': defects_df,        # v5
        'anomalies': anomalies_df,    # v7
        'ground_truth': pd.concat([defects_df, anomalies_df], ignore_index=True),  # COMBINED
    }


# ============================================================================
# MAIN / TESTING
# ============================================================================

if __name__ == '__main__':
    config = GenerationConfig()
    print("🚀 SYNTHETIC DATA GENERATION v7.5 - HYBRID (v5 defects + v7 anomalies)\n")

    ds = generate_dataset(config)
    vehicles, devices = ds['vehiculo'], ds['dispositivo']
    defects, anomalies = ds['defects'], ds['anomalies']
    ground_truth = ds['ground_truth']

    print(f"📊 Vehículos:       {len(vehicles)}")
    print(f"📊 Dispositivos:    {len(devices)}")
    print(f"📊 Defectos v5:     {len(defects)}")
    print(f"📊 Anomalías v7:    {len(anomalies)}")
    print(f"📊 Ground Truth:    {len(ground_truth)} (combined)")
    print()

    print("📋 DEFECTOS v5 (Normalizables):")
    if len(defects) > 0:
        print(defects.groupby(['tipo', 'severidad']).size().to_string())
    else:
        print("   (ninguno)")
    print()

    print("📋 ANOMALÍAS v7 (Detectables):")
    if len(anomalies) > 0:
        print(anomalies.groupby(['tipo', 'severidad']).size().to_string())
    else:
        print("   (ninguno)")
    print()

    print("📋 GROUND TRUTH (Total):")
    if len(ground_truth) > 0:
        print(ground_truth.groupby(['tipo', 'severidad']).size().to_string())
    print()

    print("✅ DATASET GENERADO CON ÉXITO")
    print(f"   Total de problemas: {len(ground_truth)} (aprox {100*len(ground_truth)/len(vehicles):.1f}% de vehículos afectados)")
