#!/usr/bin/env python3
"""
Pipeline Maestro - Ejecuta todos los generadores de datos
Genera: Flota, Telemetría, Consumo, Facturación, Solicitudes

Además registra en `ground_truth.csv` cada anomalía inyectada. Ese archivo es la
verdad de referencia para evaluar la detección y no debe usarse como entrada de
los modelos.

Reproducibilidad: la misma semilla produce exactamente los mismos datos. Todas las
fechas se calculan desde FECHA_REFERENCIA, nunca desde la hora actual.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import random

import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rutas
BASE_DIR = Path(__file__).parent
DATASETS_DIR = BASE_DIR / "datasets" / "synthetics_maestro"
DIRECTORIOS_ESCENARIO = {
    "didactico": DATASETS_DIR,
    "realista": BASE_DIR / "datasets" / "synthetics_realista",
}

# Seed para reproducibilidad
SEED = 42

# Ventana temporal de los datos: consumos y solicitudes entre FECHA_INICIO y
# FECHA_INICIO + DIAS_VENTANA. FECHA_REFERENCIA hace de "ahora" para la telemetría.
FECHA_INICIO = datetime(2024, 1, 1)
DIAS_VENTANA = 270
FECHA_REFERENCIA = FECHA_INICIO + timedelta(days=DIAS_VENTANA + 1)

# Tasas de inyección de anomalías en CONSUMO
TASA_VEHICULOS_EXCESO = 0.07      # vehículos que cargan más que su tanque (H3a)
TASA_ODOMETRO_REGRESIVO = 0.012   # transacciones con retroceso de odómetro (H2)
TASA_ODOMETRO_SALTO = 0.012       # transacciones con salto de odómetro (H2)
TASA_DOMINIO_INVALIDO = 0.01      # dominios mal formados (H1)
TASA_NULOS = 0.02                 # campos vacíos (calidad)
TASA_DUPLICADOS = 0.01            # filas duplicadas (calidad)

# tipo_anomalia -> (hipótesis, severidad)
CATALOGO_ANOMALIAS = {
    "EXCESO_VOLUMETRICO": ("H3a", "ALTA"),
    "ODOMETRO_REGRESIVO": ("H2", "ALTA"),
    "ODOMETRO_SALTO": ("H2", "ALTA"),
    "DOMINIO_INVALIDO": ("H1", "MEDIA"),
    "VALOR_NULO": ("CALIDAD", "BAJA"),
    "DUPLICADO": ("CALIDAD", "MEDIA"),
    # Solo en el escenario realista
    "ODOMETRO_REGRESIVO_LEVE": ("H2", "MEDIA"),
    "FRACCIONAMIENTO": ("H4", "ALTA"),
    "RENDIMIENTO_IMPOSIBLE": ("H5", "ALTA"),
    "CARGA_VEHICULO_INACTIVO": ("H6", "ALTA"),
    "CARGA_FUERA_DE_ZONA": ("H7", "ALTA"),
}

ESCENARIOS = ("didactico", "realista")

TIPOS_POR_ESCENARIO = {
    "didactico": ["EXCESO_VOLUMETRICO", "ODOMETRO_REGRESIVO", "ODOMETRO_SALTO",
                  "DOMINIO_INVALIDO", "VALOR_NULO", "DUPLICADO"],
    "realista": list(CATALOGO_ANOMALIAS),
}

# Casos legítimos que se parecen a una anomalía (escenario realista). No van al
# ground truth: se registran en casos_legitimos.csv para medir las falsas alarmas.
CATALOGO_LEGITIMOS = {
    "TANQUE_AUXILIAR": "el vehículo tiene más capacidad que la registrada y carga por encima del tanque",
    "VIAJE_LARGO": "carga en estaciones de ruta durante un viaje real",
    "CAMBIO_ODOMETRO": "el odómetro se reemplazó y vuelve a contar desde un valor bajo",
    "ERROR_TIPEO_ODOMETRO": "la lectura del odómetro se cargó con un error de tipeo",
}

COLUMNAS_CASOS_LEGITIMOS = ["tabla", "id_registro", "vehiculo_id", "tipo_caso", "descripcion"]

# Anomalías que siguen presentes en una fila duplicada (las de odómetro no: la copia
# repite fecha y lectura, así que no hay cambio que detectar)
ANOMALIAS_HEREDABLES = {"EXCESO_VOLUMETRICO", "DOMINIO_INVALIDO", "VALOR_NULO"}

COLUMNAS_GROUND_TRUTH = [
    "tabla", "id_registro", "vehiculo_id", "tipo_anomalia",
    "columna", "hipotesis", "severidad", "descripcion",
]

# Catálogos de la flota (compartidos por ambos escenarios; el orden importa para
# la reproducibilidad)
DIRECCIONES = [
    "DIRECCION GRAL. SEGURIDAD CAPITAL",
    "DIRECCION GRAL. SEGURIDAD PROVINCIA",
    "DIRECCION GRAL. LOGISTICA",
    "DIRECCION GRAL. OBRAS",
    "DIRECCION GRAL. SALUD",
]
DEPENDENCIAS = {
    "DIRECCION GRAL. SEGURIDAD CAPITAL": ["DEP A", "DEP B", "DEP C"],
    "DIRECCION GRAL. SEGURIDAD PROVINCIA": ["DEP D", "DEP E"],
    "DIRECCION GRAL. LOGISTICA": ["DEP F", "DEP G"],
    "DIRECCION GRAL. OBRAS": ["DEP H"],
    "DIRECCION GRAL. SALUD": ["DEP I", "DEP J"],
}
MARCAS = ["FORD", "TOYOTA", "VOLKSWAGEN", "RENAULT", "HONDA", "FIAT", "IVECO", "CHEVROLET"]
TIPOS_VEHICULO = ["SEDAN", "PICK-UP", "MOTOCICLETA", "CAMIONETA", "CAMION", "AMBULANCIA", "UTILITARIO", "BOMBERO"]
COMBUSTIBLES = ["GASOIL", "GASOIL", "GASOIL", "GASOIL", "GASOIL", "NAFTA", "NAFTA", "NAFTA", "GLP"]
MARCAS_ESTACION = ["YPF", "SHELL", "AXION", "PUMA", "ESTACION LOCAL"]

# ============================================================================
# Parámetros del escenario realista
# ============================================================================

# tipo: (capacidad del tanque en L, rendimiento en km/L, km por día hábil)
PERFILES_VEHICULO = {
    "MOTOCICLETA": ((10, 18), (25, 35), (20, 60)),
    "SEDAN": ((45, 60), (10, 14), (30, 70)),
    "PICK-UP": ((70, 80), (7, 10), (40, 90)),
    "CAMIONETA": ((60, 80), (7, 10), (40, 90)),
    "UTILITARIO": ((55, 70), (8, 11), (40, 80)),
    "AMBULANCIA": ((70, 90), (6, 8), (50, 120)),
    "CAMION": ((150, 300), (2.5, 4), (60, 150)),
    "BOMBERO": ((150, 250), (2, 3.5), (10, 40)),
}
# 75% en servicio, 10% en reparación, 5% fuera de servicio, 10% de baja
ESTADOS_REALISTA = ["EN SERVICIO"] * 15 + ["EN REPARACION"] * 2 + ["FUERA DE SERVICIO"] + ["BAJA"] * 2
PRODUCTOS_POR_COMBUSTIBLE = {
    "GASOIL": ["GASOIL", "INFINIA DIESEL"],
    "NAFTA": ["NAFTA", "SUPER", "INFINIA"],
    "GLP": ["GLP"],
}
PRECIO_BASE = {"GASOIL": 2.0, "INFINIA DIESEL": 2.4, "NAFTA": 2.1, "SUPER": 2.3, "INFINIA": 2.6, "GLP": 1.2}
AUMENTO_MENSUAL_PRECIO = 0.02

ZONA_BASE = {"lat": (-34.9, -34.4), "lon": (-58.8, -58.2)}
N_ESTACIONES_LOCALES = 40
N_RUTAS = 5
FRACCIONES_RUTA = [0.25, 0.45, 0.65, 0.85, 1.0]  # una estación en cada tramo de la ruta
COBERTURA_GPS = 0.88            # vehículos con dispositivo
TASA_DIAS_SIN_SENAL = 0.03      # días en que el dispositivo no reporta
PROB_DIA_SIN_USO = 0.25
PROB_CARGA_PARCIAL = 0.25
RESERVA_TANQUE = 0.05           # fracción del tanque en la que el vehículo obliga a cargar

# Cantidad de casos por cada 200 vehículos (escala con n_flota)
EVENTOS_REALISTA = {
    "EXCESO_VOLUMETRICO": 2,        # vehículos que empiezan a cargar más que su tanque
    "RENDIMIENTO_IMPOSIBLE": 2,     # vehículos con cargas que no se corresponden con su uso
    "FRACCIONAMIENTO": 6,           # vehículos con un día de cargas repartidas
    "CARGA_VEHICULO_INACTIVO": 3,   # vehículos fuera de servicio o de baja con cargas
    "CARGA_FUERA_DE_ZONA": 6,       # vehículos con una carga lejos de donde está el vehículo
    "ODOMETRO_REGRESIVO": 3,
    "ODOMETRO_REGRESIVO_LEVE": 4,
    "ODOMETRO_SALTO": 3,
    "TANQUE_AUXILIAR": 3,           # legítimos
    "VIAJE_LARGO": 4,
    "CAMBIO_ODOMETRO": 2,
    "ERROR_TIPEO_ODOMETRO": 5,
}
TASAS_CALIDAD_REALISTA = {"DOMINIO_INVALIDO": 0.003, "VALOR_NULO": 0.005, "DUPLICADO": 0.003}


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia sobre la superficie terrestre (fórmula del haversine)."""
    from math import asin, cos, radians, sin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def _interpolar(origen, destino, fraccion):
    return (origen[0] + (destino[0] - origen[0]) * fraccion,
            origen[1] + (destino[1] - origen[1]) * fraccion)


def _error_de_tipeo(valor, rng):
    """Lectura con dos dígitos intercambiados (o uno cambiado) que difiere en ≥1000 km."""
    texto = str(int(valor))
    for _ in range(20):
        i = rng.randint(0, len(texto) - 4)
        if texto[i] != texto[i + 1]:
            nuevo = int(texto[:i] + texto[i + 1] + texto[i] + texto[i + 2:])
            if abs(nuevo - valor) >= 1000:
                return nuevo
    i = rng.randint(0, len(texto) - 4)
    digito = str((int(texto[i]) + rng.randint(1, 8)) % 10)
    return int(texto[:i] + digito + texto[i + 1:])


class GeneradorMaestro:
    """Orquesta la generación de todas las entidades"""

    def __init__(self, n_flota=200, seed=SEED, output_dir=None, escenario="didactico"):
        if escenario not in ESCENARIOS:
            raise ValueError(f"escenario debe ser uno de {ESCENARIOS}")
        self.n_flota = n_flota
        self.seed = seed
        self.escenario = escenario
        self.output_dir = Path(output_dir) if output_dir else DIRECTORIOS_ESCENARIO[escenario]
        # Generador propio: no depende del estado global de `random`
        self.rng = random.Random(seed)
        self.datasets = {}
        self.anomalias = []
        self.casos_legitimos = []
        self.metadata = {
            "fecha_generacion": datetime.now().isoformat(),
            "fecha_referencia": FECHA_REFERENCIA.isoformat(),
            "escenario": escenario,
            "seed": seed,
            "n_flota": n_flota,
            "generadores_ejecutados": []
        }

    def _registrar_anomalia(self, tabla, id_registro, vehiculo_id, tipo, columna, descripcion):
        hipotesis, severidad = CATALOGO_ANOMALIAS[tipo]
        self.anomalias.append({
            "tabla": tabla,
            "id_registro": id_registro,
            "vehiculo_id": vehiculo_id,
            "tipo_anomalia": tipo,
            "columna": columna,
            "hipotesis": hipotesis,
            "severidad": severidad,
            "descripcion": descripcion,
        })

    def generar_flota(self):
        """Genera tabla FLOTA (200 vehículos)"""
        logger.info("Generando FLOTA...")
        rng = self.rng

        dg = DIRECCIONES
        dependencias = DEPENDENCIAS
        marcas = MARCAS
        tipos = TIPOS_VEHICULO
        combustible = COMBUSTIBLES
        estados = ["EN SERVICIO", "EN SERVICIO", "EN SERVICIO", "EN REPARACION", "FUERA DE SERVICIO", "BAJA"]

        rows = []
        for i in range(1, self.n_flota + 1):
            dg_sel = rng.choice(dg)
            dep = rng.choice(dependencias[dg_sel])
            estado = rng.choice(estados)
            identificable = "SI" if rng.random() < 0.94 else "NO"
            annio = rng.randint(2005, 2024)

            rows.append({
                "Matricula": f"VEH-{i:06d}",
                "Dominio": f"AB{i:04d}CD",
                "Estado": estado,
                "DireccionGral": dg_sel,
                "Dependencia": dep,
                "Identificable": identificable,
                "TipoVehiculo": rng.choice(tipos),
                "Marca": rng.choice(marcas),
                "Modelo": f"MODEL-{rng.randint(2010, 2024)}",
                "Año": annio,
                "TipoCombustible": rng.choice(combustible),
                "CapacidadTanque": rng.uniform(40, 120),
                "NumeroMotor": f"M{i:08d}",
                "NumeroChasis": f"CH{i:08d}",
                "NumeroTarjeta": f"TARJ{i:08d}",
                "LimiteSaldo": rng.uniform(1000, 10000),
                "LimiteLitros": rng.uniform(100, 500),
                "SubEstado": "ACTIVO" if estado == "EN SERVICIO" else "INACTIVO",
            })

        df = pd.DataFrame(rows)
        self.datasets['flota'] = df
        self.metadata['generadores_ejecutados'].append('flota')
        logger.info(f"✓ FLOTA generada: {len(df)} vehículos")
        return df

    def generar_telemetria(self):
        """Genera tabla TELEMETRIA (dispositivos GPS)"""
        logger.info("Generando TELEMETRIA...")
        rng = self.rng

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        n_dispositivos = int(self.n_flota * 0.88)  # 88% cobertura

        rows = []
        for i in range(1, n_dispositivos + 1):
            online = rng.random() < 0.88
            bateria = round(rng.uniform(20, 100), 1)
            last = FECHA_REFERENCIA - timedelta(minutes=rng.randint(0, 15 if online else 600))

            # Link a un vehículo de la flota
            vehiculo = rng.choice(list(flota_df['Dominio'].values))

            rows.append({
                "IMEI": f"{rng.randint(350000000000000, 359999999999999)}",
                "Alias": f"DEV-{i:06d}",
                "Placa": vehiculo,
                "MSISDN": f"54911{rng.randint(1000000, 9999999)}",
                "Modelo": f"GPS-{rng.choice(['A', 'B', 'C'])}-{rng.randint(1, 5)}",
                "Tipo": "GPS",
                "Estado": "ONLINE" if online else "OFFLINE",
                "Bateria": bateria,
                "UltimaConexion": last.isoformat(),
                "Latitud": round(rng.uniform(-34.9, -34.4), 6),
                "Longitud": round(rng.uniform(-58.8, -58.2), 6),
                "Odometro": rng.randint(10000, 300000),
            })

        df = pd.DataFrame(rows)
        self.datasets['telemetria'] = df
        self.metadata['generadores_ejecutados'].append('telemetria')
        logger.info(f"✓ TELEMETRIA generada: {len(df)} dispositivos")
        return df

    def generar_consumo(self):
        """Genera tabla CONSUMO (transacciones de combustible)

        El odómetro avanza de forma monótona según los días entre cargas. Sobre esa
        base se inyectan anomalías, todas registradas en el ground truth:
        - ~7% de vehículos cargan más litros que su tanque (EXCESO_VOLUMETRICO, H3a)
        - ~1.2% de transacciones con retroceso de odómetro (ODOMETRO_REGRESIVO, H2)
        - ~1.2% de transacciones con salto de odómetro (ODOMETRO_SALTO, H2)
        - ~1% de dominios mal formados (DOMINIO_INVALIDO, H1)
        - ~2% de campos vacíos (VALOR_NULO)
        - ~1% de filas duplicadas (DUPLICADO)
        Las anomalías de odómetro persisten: las cargas siguientes continúan desde el
        valor alterado, por lo que solo la transacción anómala muestra el cambio.
        """
        logger.info("Generando CONSUMO...")
        rng = self.rng

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        productos = ["GASOIL", "NAFTA", "INFINIA", "SUPER", "GLP"]
        estaciones = ["YPF", "SHELL", "AXION", "PUMA", "ESTACION LOCAL"]

        n_anomalos = max(5, int(self.n_flota * TASA_VEHICULOS_EXCESO))
        indices_anomalos = set(rng.sample(range(len(flota_df)), min(n_anomalos, len(flota_df))))

        rows = []
        anomalias_por_id = {}
        contador_total = 0

        def registrar(row, tipo, columna, descripcion):
            self._registrar_anomalia("consumo", row["id"], row["vehiculo_id"], tipo, columna, descripcion)
            anomalias_por_id.setdefault(row["id"], []).append((tipo, columna, descripcion))

        for veh_idx, veh_row in flota_df.iterrows():
            # Cada vehículo genera 5-12 transacciones, en orden cronológico
            n_transacciones = rng.randint(5, 12)
            es_anomalo = veh_idx in indices_anomalos
            capacidad = veh_row['CapacidadTanque']
            fechas = sorted(FECHA_INICIO + timedelta(days=rng.randint(0, DIAS_VENTANA))
                            for _ in range(n_transacciones))

            odometro_real = rng.randint(10000, 250000)
            km_por_dia = rng.uniform(20, 60)
            fecha_previa = None

            for fecha in fechas:
                if fecha_previa is not None:
                    dias = (fecha - fecha_previa).days
                    odometro_real += int(km_por_dia * dias + rng.uniform(0, 30))

                # H3a: los vehículos anómalos cargan más que la capacidad del tanque
                if es_anomalo:
                    litros = round(rng.uniform(capacidad * 1.1, capacidad * 1.8), 2)
                else:
                    litros = round(rng.uniform(5, min(80, capacidad * 0.8)), 2)

                row = {
                    "id": f"CONS-{contador_total+1:08d}",
                    "vehiculo_id": veh_row['Matricula'],
                    "dominio": veh_row['Dominio'],
                    "fecha": fecha,
                    "estacion": rng.choice(estaciones),
                    "producto": rng.choice(productos),
                    "litros": litros,
                    "precio_unitario": round(rng.uniform(1.5, 3.5), 2),
                    "importe_total": 0.0,
                    "numero_tarjeta": veh_row['NumeroTarjeta'],
                    "conductor": f"CONDUCTOR-{rng.randint(1, 500)}",
                    "odometro": odometro_real,
                }
                contador_total += 1

                if es_anomalo:
                    registrar(row, "EXCESO_VOLUMETRICO", "litros",
                              f"{litros:.2f} L con tanque de {capacidad:.2f} L")

                # H2: retroceso o salto de odómetro (nunca en la primera carga)
                odometro_alterado = False
                if fecha_previa is not None:
                    r = rng.random()
                    if r < TASA_ODOMETRO_REGRESIVO:
                        retroceso = min(rng.randint(3000, 40000), odometro_real - 1000)
                        odometro_real -= retroceso
                        row["odometro"] = odometro_real
                        odometro_alterado = True
                        registrar(row, "ODOMETRO_REGRESIVO", "odometro", f"retroceso de {retroceso} km")
                    elif r < TASA_ODOMETRO_REGRESIVO + TASA_ODOMETRO_SALTO:
                        salto = rng.randint(1500, 9000)
                        odometro_real += salto
                        row["odometro"] = odometro_real
                        odometro_alterado = True
                        registrar(row, "ODOMETRO_SALTO", "odometro", f"salto de {salto} km")
                fecha_previa = fecha

                # H1: dominio mal formado
                if rng.random() < TASA_DOMINIO_INVALIDO:
                    original = row["dominio"]
                    row["dominio"] = f"XX{rng.randint(0, 999)}XX"
                    registrar(row, "DOMINIO_INVALIDO", "dominio", f"{original} registrado como {row['dominio']}")

                # Calidad: campo vacío (no se vacía un odómetro alterado, para que
                # la anomalía de H2 siga siendo observable)
                if rng.random() < TASA_NULOS:
                    candidatos = ['estacion', 'conductor'] + ([] if odometro_alterado else ['odometro'])
                    campo_nulo = rng.choice(candidatos)
                    row[campo_nulo] = None
                    registrar(row, "VALOR_NULO", campo_nulo, f"{campo_nulo} vacío")

                rows.append(row)

        # Calidad: filas duplicadas con un id nuevo
        n_duplicados = max(1, int(len(rows) * TASA_DUPLICADOS))
        for _ in range(n_duplicados):
            row_original = rng.choice(rows)
            row_copia = row_original.copy()
            row_copia['id'] = f"CONS-{contador_total+1:08d}"
            contador_total += 1
            rows.append(row_copia)
            registrar(row_copia, "DUPLICADO", "id", f"copia de {row_original['id']}")
            for tipo, columna, descripcion in anomalias_por_id.get(row_original['id'], []):
                if tipo in ANOMALIAS_HEREDABLES:
                    registrar(row_copia, tipo, columna, f"{descripcion} (heredado de {row_original['id']})")

        df = pd.DataFrame(rows)
        df['importe_total'] = (df['litros'] * df['precio_unitario']).round(2)
        df['odometro'] = df['odometro'].astype('Int64')

        self.datasets['consumo'] = df
        self.metadata['generadores_ejecutados'].append('consumo')
        logger.info(f"✓ CONSUMO generado: {len(df)} transacciones, "
                    f"{len(self.anomalias)} anomalías registradas en ground truth")
        return df

    def generar_solicitudes(self):
        """Genera tabla SOLICITUDES (solicitudes de combustible)"""
        logger.info("Generando SOLICITUDES...")
        rng = self.rng

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        estados_solicitud = ["APROBADA", "PENDIENTE", "RECHAZADA", "APROBADA"]

        rows = []
        for veh_idx, veh_row in flota_df.iterrows():
            # Cada vehículo genera 1-4 solicitudes
            n_solicitudes = rng.randint(1, 4)

            for sol_idx in range(n_solicitudes):
                fecha = FECHA_INICIO + timedelta(days=rng.randint(0, DIAS_VENTANA))

                rows.append({
                    "id": f"SOL-{len(rows)+1:08d}",
                    "vehiculo_id": veh_row['Matricula'],
                    "dominio": veh_row['Dominio'],
                    "fecha_solicitud": fecha,
                    "litros_solicitados": round(rng.uniform(20, 100), 2),
                    "litros_autorizados": round(rng.uniform(20, 100), 2),
                    "estado": rng.choice(estados_solicitud),
                    "centro_costo": f"CC-{rng.randint(1, 50):03d}",
                    "responsable": f"RESP-{rng.randint(1, 100)}",
                    "observaciones": rng.choice(["OK", "REVISADO", "PENDIENTE", ""]),
                })

        df = pd.DataFrame(rows)
        self.datasets['solicitudes'] = df
        self.metadata['generadores_ejecutados'].append('solicitudes')
        logger.info(f"✓ SOLICITUDES generada: {len(df)} solicitudes")
        return df

    def generar_facturacion(self):
        """Genera tabla FACTURACION (facturas)"""
        logger.info("Generando FACTURACION...")
        rng = self.rng

        consumo_df = self.datasets.get('consumo')
        if consumo_df is None:
            logger.error("CONSUMO debe generarse primero")
            return None

        # Agrupar consumo por mes y generar facturas
        consumo_df_copy = consumo_df.copy()
        consumo_df_copy['mes'] = consumo_df_copy['fecha'].dt.to_period('M')

        rows = []
        for (mes, grupo) in consumo_df_copy.groupby('mes'):
            factura_num = f"FAC-{mes.year}{mes.month:02d}-{rng.randint(1000, 9999)}"
            total_monto = grupo['importe_total'].sum()

            rows.append({
                "numero_factura": factura_num,
                "fecha_factura": mes.end_time.date(),
                "periodo": str(mes),
                "total_litros": grupo['litros'].sum(),
                "total_monto": total_monto,
                "iva": total_monto * 0.21,
                "monto_total_con_iva": total_monto * 1.21,
                "estado": rng.choice(["PAGADA", "PENDIENTE", "VENCIDA"]),
                "numero_transacciones": len(grupo),
            })

        df = pd.DataFrame(rows)
        self.datasets['facturacion'] = df
        self.metadata['generadores_ejecutados'].append('facturacion')
        logger.info(f"✓ FACTURACION generada: {len(df)} facturas")
        return df

    # ========================================================================
    # ESCENARIO REALISTA
    #
    # Cada vehículo se simula día por día: recorre kilómetros según su perfil,
    # consume según su rendimiento y carga cuando el tanque baja de su umbral.
    # Así litros, odómetro y GPS son coherentes entre sí, y las anomalías (y los
    # casos legítimos que se les parecen) se inyectan sobre ese uso realista.
    # ========================================================================

    def _cantidad(self, clave):
        return max(1, round(EVENTOS_REALISTA[clave] * self.n_flota / 200))

    def _registrar_legitimo(self, id_registro, vehiculo_id, tipo, descripcion):
        self.casos_legitimos.append({"tabla": "consumo", "id_registro": id_registro,
                                     "vehiculo_id": vehiculo_id, "tipo_caso": tipo,
                                     "descripcion": descripcion})

    def generar_flota_realista(self):
        """FLOTA con capacidad acorde al tipo de vehículo y fecha del último cambio de estado."""
        logger.info("Generando FLOTA (escenario realista)...")
        rng = self.rng
        rows, self._perfiles = [], {}
        for i in range(1, self.n_flota + 1):
            dg_sel = rng.choice(DIRECCIONES)
            estado = rng.choice(ESTADOS_REALISTA)
            tipo = rng.choice(TIPOS_VEHICULO)
            (cap_min, cap_max), rendimiento, km_dia = PERFILES_VEHICULO[tipo]
            capacidad = round(rng.uniform(cap_min, cap_max), 1)
            fecha_estado = (None if estado == "EN SERVICIO"
                            else FECHA_INICIO + timedelta(days=rng.randint(60, DIAS_VENTANA - 20)))
            matricula = f"VEH-{i:06d}"
            rows.append({
                "Matricula": matricula,
                "Dominio": f"AB{i:04d}CD",
                "Estado": estado,
                "DireccionGral": dg_sel,
                "Dependencia": rng.choice(DEPENDENCIAS[dg_sel]),
                "Identificable": "SI" if rng.random() < 0.94 else "NO",
                "TipoVehiculo": tipo,
                "Marca": rng.choice(MARCAS),
                "Modelo": f"MODEL-{rng.randint(2010, 2024)}",
                "Año": rng.randint(2005, 2024),
                "TipoCombustible": "NAFTA" if tipo == "MOTOCICLETA" else rng.choice(COMBUSTIBLES),
                "CapacidadTanque": capacidad,
                "NumeroMotor": f"M{i:08d}",
                "NumeroChasis": f"CH{i:08d}",
                "NumeroTarjeta": f"TARJ{i:08d}",
                "LimiteSaldo": round(rng.uniform(1000, 10000), 2),
                "LimiteLitros": round(capacidad * rng.uniform(3, 6), 1),
                "SubEstado": "ACTIVO" if estado == "EN SERVICIO" else "INACTIVO",
                "FechaEstado": fecha_estado.date() if fecha_estado else None,
            })
            # Uso real del vehículo: guía la simulación pero no forma parte de los datos
            self._perfiles[matricula] = {
                "rendimiento": rng.uniform(*rendimiento),
                "km_dia": rng.uniform(*km_dia),
                "base": (rng.uniform(*ZONA_BASE["lat"]), rng.uniform(*ZONA_BASE["lon"])),
                "umbral_carga": rng.uniform(0.15, 0.35),
            }

        df = pd.DataFrame(rows)
        self.datasets['flota'] = df
        self.metadata['generadores_ejecutados'].append('flota')
        logger.info(f"✓ FLOTA generada: {len(df)} vehículos")
        return df

    def generar_estaciones(self):
        """ESTACIONES con coordenadas: locales en la zona de operación y otras sobre rutas."""
        logger.info("Generando ESTACIONES...")
        rng = self.rng
        rows = []
        for _ in range(N_ESTACIONES_LOCALES):
            rows.append({
                "codigo": f"EST-{len(rows) + 1:03d}",
                "marca": rng.choice(MARCAS_ESTACION),
                "ubicacion": "LOCAL",
                "latitud": round(rng.uniform(*ZONA_BASE["lat"]), 5),
                "longitud": round(rng.uniform(*ZONA_BASE["lon"]), 5),
            })

        centro = (sum(ZONA_BASE["lat"]) / 2, sum(ZONA_BASE["lon"]) / 2)
        self._destinos = []
        while len(self._destinos) < N_RUTAS:
            destino = (centro[0] + rng.uniform(-4, 3.5), centro[1] + rng.uniform(-6.5, -1.5))
            if distancia_km(*centro, *destino) >= 250:
                self._destinos.append(destino)
        for destino in self._destinos:
            for fraccion in FRACCIONES_RUTA:
                lat, lon = _interpolar(centro, destino, fraccion)
                rows.append({
                    "codigo": f"EST-{len(rows) + 1:03d}",
                    "marca": rng.choice(MARCAS_ESTACION),
                    "ubicacion": "RUTA",
                    "latitud": round(lat + rng.uniform(-0.05, 0.05), 5),
                    "longitud": round(lon + rng.uniform(-0.05, 0.05), 5),
                })

        self._coords_estaciones = [(r["codigo"], r["latitud"], r["longitud"], r["ubicacion"]) for r in rows]
        self._ubicacion_estacion = {r["codigo"]: r["ubicacion"] for r in rows}
        df = pd.DataFrame(rows)
        self.datasets['estaciones'] = df
        self.metadata['generadores_ejecutados'].append('estaciones')
        logger.info(f"✓ ESTACIONES generadas: {len(df)}")
        return df

    def _estacion_cercana(self, pos, excluir=None, solo=None):
        """Una de las tres estaciones más cercanas a una posición."""
        candidatas = sorted(
            (distancia_km(pos[0], pos[1], lat, lon), codigo)
            for codigo, lat, lon, ubicacion in self._coords_estaciones
            if codigo != excluir and (solo is None or ubicacion == solo)
        )
        return self.rng.choice(candidatas[:3])[1]

    def _asignar_roles(self, vehiculos, con_gps):
        """Elige qué vehículos protagonizan cada anomalía o caso legítimo (a lo sumo uno cada uno)."""
        rng = self.rng
        roles = {}

        def asignar(rol, candidatos):
            libres = [m for m in candidatos if m not in roles]
            for m in rng.sample(libres, min(self._cantidad(rol), len(libres))):
                roles[m] = rol

        en_servicio = [v["Matricula"] for v in vehiculos if v["Estado"] == "EN SERVICIO"]
        tipo = {v["Matricula"]: v["TipoVehiculo"] for v in vehiculos}
        asignar("TANQUE_AUXILIAR", [m for m in en_servicio
                                    if tipo[m] in ("CAMION", "BOMBERO", "PICK-UP", "CAMIONETA")])
        asignar("EXCESO_VOLUMETRICO", en_servicio)
        asignar("RENDIMIENTO_IMPOSIBLE", en_servicio)
        asignar("VIAJE_LARGO", en_servicio)
        asignar("FRACCIONAMIENTO", en_servicio)
        asignar("CARGA_FUERA_DE_ZONA", [m for m in en_servicio if m in con_gps])
        limite = (FECHA_REFERENCIA - timedelta(days=20)).date()
        asignar("CARGA_VEHICULO_INACTIVO", [v["Matricula"] for v in vehiculos
                                            if v["Estado"] != "EN SERVICIO" and v["FechaEstado"] <= limite])
        return roles

    def _simular_vehiculo(self, v, rol, cargas, gps):
        """Simula el uso diario de un vehículo y agrega sus cargas y sus registros de GPS."""
        rng = self.rng
        m = v["Matricula"]
        perfil = self._perfiles[m]
        cap_reg = v["CapacidadTanque"]
        cap_real = cap_reg * rng.uniform(1.3, 1.6) if rol == "TANQUE_AUXILIAR" else cap_reg
        base = perfil["base"]
        fin_activo = datetime.combine(v["FechaEstado"], datetime.min.time()) if v["FechaEstado"] else None
        productos = PRODUCTOS_POR_COMBUSTIBLE[v["TipoCombustible"]]
        odo = float(rng.randint(10000, 250000))
        combustible = cap_real * rng.uniform(0.4, 0.9)
        dia_inicio_fraude = rng.randint(90, 200)

        viaje = (rng.randint(30, DIAS_VENTANA - 10), rng.choice(self._destinos)) if rol == "VIAJE_LARGO" else None
        dias_inactivo = set()
        if rol == "CARGA_VEHICULO_INACTIVO":
            desde = (fin_activo - FECHA_INICIO).days + 5
            dias_inactivo = set(rng.sample(range(desde, DIAS_VENTANA + 1), rng.randint(1, 3)))
        dia_fuera_de_zona = rng.randint(30, DIAS_VENTANA) if rol == "CARGA_FUERA_DE_ZONA" else None
        cargas_sin_uso = rng.randint(3, 6) if rol == "RENDIMIENTO_IMPOSIBLE" else 0
        fraccionado = False

        def registrar(fecha, estacion, litros, odometro, etiqueta=None, legitimo=None):
            cargas.append({
                "vehiculo_id": m, "dominio": v["Dominio"], "fecha": fecha, "estacion": estacion,
                "producto": rng.choice(productos), "litros": round(litros, 2),
                "numero_tarjeta": v["NumeroTarjeta"], "conductor": f"CONDUCTOR-{rng.randint(1, 500)}",
                "_odo_real": odometro, "_etiqueta": etiqueta, "_legitimo": legitimo,
                "_capacidad": cap_reg, "_orden": len(cargas),
            })

        def cargar(fecha, pos, dia):
            nonlocal combustible, fraccionado
            if rng.random() < PROB_CARGA_PARCIAL:
                objetivo = cap_real * rng.uniform(0.6, 0.9)
            else:
                objetivo = cap_real * rng.uniform(0.95, 1.0)
            al_tanque = max(objetivo - combustible, 0.08 * cap_real)
            litros, etiqueta, legitimo = al_tanque, None, None
            estacion = self._estacion_cercana(pos)
            if rol == "TANQUE_AUXILIAR":
                legitimo = "TANQUE_AUXILIAR"
            elif rol == "VIAJE_LARGO" and self._ubicacion_estacion[estacion] == "RUTA":
                legitimo = "VIAJE_LARGO"
            elif rol == "EXCESO_VOLUMETRICO" and dia >= dia_inicio_fraude and rng.random() < 0.3:
                # Se factura más de lo que entra en el tanque; el excedente no llega al vehículo
                litros = max(litros, cap_reg * rng.uniform(1.05, 1.4))
                etiqueta = "EXCESO_VOLUMETRICO"
            fraccionar = rol == "FRACCIONAMIENTO" and not fraccionado and dia >= 30 and rng.random() < 0.3
            if fraccionar:
                etiqueta = "FRACCIONAMIENTO"
            registrar(fecha, estacion, litros, odo, etiqueta, legitimo)
            combustible += al_tanque

            if fraccionar:
                # Cargas adicionales el mismo día en otras estaciones: cada una parece normal,
                # pero entre todas superan el tanque. El combustible extra no llega al vehículo.
                fraccionado = True
                total = litros
                lectura = odo
                extras = rng.randint(1, 2)
                for k in range(extras):
                    extra = cap_reg * rng.uniform(0.4, 0.7)
                    if k == extras - 1 and total + extra <= 1.1 * cap_reg:
                        extra = 1.1 * cap_reg - total + cap_reg * rng.uniform(0.05, 0.2)
                    total += extra
                    lectura += rng.uniform(0.5, 5)  # la estación siguiente queda a pocos km
                    registrar(fecha, self._estacion_cercana(pos, excluir=estacion), extra,
                              lectura, "FRACCIONAMIENTO")

        for dia in range(DIAS_VENTANA + 1):
            fecha = FECHA_INICIO + timedelta(days=dia)
            activo = fin_activo is None or fecha < fin_activo
            origen = destino = base
            km = 0.0
            if viaje and dia == viaje[0]:
                destino = viaje[1]
                km = distancia_km(*base, *destino) * 1.2
            elif viaje and dia == viaje[0] + 1:
                origen = destino = viaje[1]
                km = rng.uniform(20, 80)
            elif viaje and dia == viaje[0] + 2:
                origen, destino = viaje[1], base
                km = distancia_km(*base, *viaje[1]) * 1.2
            elif activo and rng.random() >= PROB_DIA_SIN_USO:
                km = perfil["km_dia"] * rng.uniform(0.5, 1.5)

            cargas_previas = len(cargas)
            rendimiento_dia = perfil["rendimiento"] * rng.uniform(0.9, 1.1)
            recorrido = 0.0
            while km - recorrido > 1e-6:
                tramo = min(km - recorrido, max(combustible - RESERVA_TANQUE * cap_real, 0) * rendimiento_dia)
                combustible -= tramo / rendimiento_dia
                odo += tramo
                recorrido += tramo
                if km - recorrido > 1e-6:  # llegó a la reserva a mitad de camino
                    cargar(fecha, _interpolar(origen, destino, recorrido / km), dia)
            if activo and combustible < perfil["umbral_carga"] * cap_real:
                cargar(fecha, destino, dia)
            hubo_carga = len(cargas) > cargas_previas

            # Cargas que no llegan al tanque del vehículo: el combustible no cambia
            if (cargas_sin_uso and activo and dia >= dia_inicio_fraude and not hubo_carga
                    and combustible > 0.7 * cap_real and rng.random() < 0.15):
                registrar(fecha, self._estacion_cercana(base, solo="LOCAL"),
                          cap_reg * rng.uniform(0.8, 0.95), odo, "RENDIMIENTO_IMPOSIBLE")
                cargas_sin_uso -= 1
            if dia in dias_inactivo:
                registrar(fecha, self._estacion_cercana(base, solo="LOCAL"),
                          cap_reg * rng.uniform(0.5, 0.9), odo, "CARGA_VEHICULO_INACTIVO")
            if dia == dia_fuera_de_zona:
                lejanas = [codigo for codigo, lat, lon, _ in self._coords_estaciones
                           if distancia_km(*base, lat, lon) > 100]
                registrar(fecha, rng.choice(lejanas), cap_reg * rng.uniform(0.5, 0.9), odo, "CARGA_FUERA_DE_ZONA")

            if m in self._con_gps and rng.random() >= TASA_DIAS_SIN_SENAL:
                gps.append({
                    "Placa": v["Dominio"],
                    "fecha": fecha.date(),
                    "km_gps": round(km * rng.uniform(0.97, 1.03), 1),
                    "lat_inicio": round(origen[0] + rng.uniform(-0.01, 0.01), 5),
                    "lon_inicio": round(origen[1] + rng.uniform(-0.01, 0.01), 5),
                    "lat_fin": round(destino[0] + rng.uniform(-0.01, 0.01), 5),
                    "lon_fin": round(destino[1] + rng.uniform(-0.01, 0.01), 5),
                })
        self._odometro_final[m] = odo

    def _alterar_odometros(self, por_vehiculo, roles):
        """Adulteraciones de odómetro (anomalías) y cambios o errores de lectura (legítimos).

        Retrocesos y saltos se miden contra la lectura anterior y persisten: las cargas
        siguientes continúan desde el valor alterado. El error de tipeo afecta una sola
        lectura; el cambio de odómetro reinicia la cuenta desde un valor bajo.
        """
        rng = self.rng
        candidatos = sorted(m for m, lista in por_vehiculo.items() if m not in roles and len(lista) >= 6)
        eventos = {}
        for tipo in ["ODOMETRO_REGRESIVO", "ODOMETRO_REGRESIVO_LEVE", "ODOMETRO_SALTO",
                     "CAMBIO_ODOMETRO", "ERROR_TIPEO_ODOMETRO"]:
            libres = [m for m in candidatos if m not in eventos]
            for m in rng.sample(libres, min(self._cantidad(tipo), len(libres))):
                eventos[m] = (tipo, rng.randint(2, len(por_vehiculo[m]) - 2))

        for m, lista in por_vehiculo.items():
            tipo, posicion = eventos.get(m, (None, None))
            desplazamiento = 0
            anterior = None
            for j, c in enumerate(lista):
                lectura = int(round(c["_odo_real"])) + desplazamiento
                if j == posicion:
                    if tipo == "ODOMETRO_REGRESIVO":
                        nueva = max(anterior - rng.randint(3000, 40000), 500)
                        c.update(_etiqueta=tipo, _detalle=f"retroceso de {anterior - nueva} km")
                    elif tipo == "ODOMETRO_REGRESIVO_LEVE":
                        nueva = anterior - rng.randint(50, 200)
                        c.update(_etiqueta=tipo, _detalle=f"retroceso de {anterior - nueva} km")
                    elif tipo == "ODOMETRO_SALTO":
                        nueva = lectura + rng.randint(1500, 9000)
                        c.update(_etiqueta=tipo, _detalle=f"salto de {nueva - lectura} km")
                    elif tipo == "CAMBIO_ODOMETRO":
                        nueva = rng.randint(0, 3000)
                        c.update(_legitimo=tipo, _detalle=f"odómetro nuevo desde {nueva} km")
                    else:  # ERROR_TIPEO_ODOMETRO: una sola lectura, no cambia las siguientes
                        c["odometro"] = _error_de_tipeo(lectura, rng)
                        c.update(_legitimo=tipo, _detalle=f"{lectura} registrado como {c['odometro']}")
                        anterior = lectura
                        continue
                    desplazamiento += nueva - lectura
                    lectura = nueva
                c["odometro"] = lectura
                anterior = lectura

    def _defectos_de_calidad(self, cargas, siguiente_id):
        """Dominios inválidos, nulos y duplicados, solo sobre cargas sin otra anomalía."""
        rng = self.rng
        n = len(cargas)
        limpias = [c for c in cargas if not c["_etiqueta"] and not c["_legitimo"]]
        rng.shuffle(limpias)
        n_dominio = round(n * TASAS_CALIDAD_REALISTA["DOMINIO_INVALIDO"])
        n_nulos = round(n * TASAS_CALIDAD_REALISTA["VALOR_NULO"])
        n_duplicados = round(n * TASAS_CALIDAD_REALISTA["DUPLICADO"])

        for c in limpias[:n_dominio]:
            original = c["dominio"]
            c["dominio"] = f"XX{rng.randint(0, 999)}XX"
            self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], "DOMINIO_INVALIDO", "dominio",
                                     f"{original} registrado como {c['dominio']}")
        for c in limpias[n_dominio:n_dominio + n_nulos]:
            campo = rng.choice(["estacion", "conductor", "odometro"])
            c[campo] = None
            self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], "VALOR_NULO", campo, f"{campo} vacío")
        copias = []
        for c in limpias[n_dominio + n_nulos:n_dominio + n_nulos + n_duplicados]:
            copia = dict(c, id=f"CONS-{siguiente_id:08d}")
            siguiente_id += 1
            copias.append(copia)
            self._registrar_anomalia("consumo", copia["id"], copia["vehiculo_id"], "DUPLICADO", "id",
                                     f"copia de {c['id']}")
        return copias

    def generar_consumo_realista(self):
        """CONSUMO, TELEMETRIA y TELEMETRIA_DIARIA a partir de la simulación de la flota."""
        logger.info("Simulando el uso diario de la flota (escenario realista)...")
        rng = self.rng
        vehiculos = self.datasets['flota'].to_dict("records")
        matriculas = [v["Matricula"] for v in vehiculos]
        self._con_gps = set(rng.sample(matriculas, int(len(matriculas) * COBERTURA_GPS)))
        self._odometro_final = {}
        roles = self._asignar_roles(vehiculos, self._con_gps)

        cargas, gps = [], []
        for v in vehiculos:
            self._simular_vehiculo(v, roles.get(v["Matricula"]), cargas, gps)

        cargas.sort(key=lambda c: (c["vehiculo_id"], c["fecha"], c["_orden"]))
        por_vehiculo = {}
        for i, c in enumerate(cargas, 1):
            c["id"] = f"CONS-{i:08d}"
            por_vehiculo.setdefault(c["vehiculo_id"], []).append(c)
        self._alterar_odometros(por_vehiculo, roles)

        columnas_etiqueta = {
            "EXCESO_VOLUMETRICO": "litros", "FRACCIONAMIENTO": "litros", "RENDIMIENTO_IMPOSIBLE": "litros",
            "CARGA_VEHICULO_INACTIVO": "fecha", "CARGA_FUERA_DE_ZONA": "estacion",
        }
        for c in cargas:
            meses = (c["fecha"].year - FECHA_INICIO.year) * 12 + c["fecha"].month - FECHA_INICIO.month
            c["precio_unitario"] = round(PRECIO_BASE[c["producto"]] * (1 + AUMENTO_MENSUAL_PRECIO * meses)
                                         * rng.uniform(0.98, 1.02), 2)
            c["importe_total"] = round(c["litros"] * c["precio_unitario"], 2)
            if c["_etiqueta"]:
                tipo = c["_etiqueta"]
                detalle = c.get("_detalle") or {
                    "EXCESO_VOLUMETRICO": f"{c['litros']:.2f} L con tanque de {c['_capacidad']:.1f} L",
                    "FRACCIONAMIENTO": "carga repartida en el mismo día",
                    "RENDIMIENTO_IMPOSIBLE": f"{c['litros']:.2f} L sin recorrido que los justifique",
                    "CARGA_VEHICULO_INACTIVO": "carga posterior a la baja o salida de servicio",
                    "CARGA_FUERA_DE_ZONA": f"carga en {c['estacion']}, lejos de la ubicación del vehículo",
                }[tipo]
                self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], tipo,
                                         columnas_etiqueta.get(tipo, "odometro"), detalle)
            if c["_legitimo"]:
                self._registrar_legitimo(c["id"], c["vehiculo_id"], c["_legitimo"],
                                         c.get("_detalle") or CATALOGO_LEGITIMOS[c["_legitimo"]])

        cargas += self._defectos_de_calidad(cargas, siguiente_id=len(cargas) + 1)

        columnas = ["id", "vehiculo_id", "dominio", "fecha", "estacion", "producto", "litros",
                    "precio_unitario", "importe_total", "numero_tarjeta", "conductor", "odometro"]
        df = pd.DataFrame(cargas)[columnas]
        df['odometro'] = df['odometro'].astype('Int64')
        self.datasets['consumo'] = df
        self.metadata['generadores_ejecutados'].append('consumo')

        self._generar_telemetria_realista(vehiculos, gps)
        logger.info(f"✓ CONSUMO generado: {len(df)} transacciones, {len(self.anomalias)} anomalías y "
                    f"{len(self.casos_legitimos)} casos legítimos registrados")
        return df

    def _generar_telemetria_realista(self, vehiculos, gps):
        """Un dispositivo por vehículo con GPS y su registro diario de recorrido."""
        rng = self.rng
        rows = []
        for i, v in enumerate([v for v in vehiculos if v["Matricula"] in self._con_gps], 1):
            online = v["Estado"] == "EN SERVICIO" and rng.random() < 0.95
            base = self._perfiles[v["Matricula"]]["base"]
            minutos = rng.randint(0, 15) if online else rng.randint(60, 600)
            rows.append({
                "IMEI": f"{rng.randint(350000000000000, 359999999999999)}",
                "Alias": f"DEV-{i:06d}",
                "Placa": v["Dominio"],
                "MSISDN": f"54911{rng.randint(1000000, 9999999)}",
                "Modelo": f"GPS-{rng.choice(['A', 'B', 'C'])}-{rng.randint(1, 5)}",
                "Tipo": "GPS",
                "Estado": "ONLINE" if online else "OFFLINE",
                "Bateria": round(rng.uniform(20, 100), 1),
                "UltimaConexion": (FECHA_REFERENCIA - timedelta(minutes=minutos)).isoformat(),
                "Latitud": round(base[0], 6),
                "Longitud": round(base[1], 6),
                "Odometro": int(round(self._odometro_final[v["Matricula"]])),
            })
        self.datasets['telemetria'] = pd.DataFrame(rows)
        self.datasets['telemetria_diaria'] = pd.DataFrame(gps)
        self.metadata['generadores_ejecutados'] += ['telemetria', 'telemetria_diaria']
        logger.info(f"✓ TELEMETRIA generada: {len(rows)} dispositivos, {len(gps)} registros diarios")

    def construir_ground_truth(self):
        """Tabla con una fila por anomalía inyectada (un registro puede tener varias)."""
        return pd.DataFrame(self.anomalias, columns=COLUMNAS_GROUND_TRUTH)

    def construir_casos_legitimos(self):
        """Casos que se parecen a una anomalía pero no lo son (solo escenario realista)."""
        return pd.DataFrame(self.casos_legitimos, columns=COLUMNAS_CASOS_LEGITIMOS)

    def guardar_datasets(self):
        """Guarda todos los datasets en CSV"""
        logger.info("Guardando datasets...")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        archivos = {}
        for nombre, df in self.datasets.items():
            filepath = self.output_dir / f"{nombre}.csv"
            df.to_csv(filepath, index=False)
            archivos[nombre] = str(filepath)
            logger.info(f"  ✓ {nombre}.csv guardado ({len(df)} filas)")

        # La verdad de referencia va aparte: no forma parte de las entidades
        ground_truth = self.construir_ground_truth()
        gt_file = self.output_dir / "ground_truth.csv"
        ground_truth.to_csv(gt_file, index=False)
        logger.info(f"  ✓ ground_truth.csv guardado ({len(ground_truth)} anomalías)")
        if self.escenario == "realista":
            legitimos = self.construir_casos_legitimos()
            legitimos_file = self.output_dir / "casos_legitimos.csv"
            legitimos.to_csv(legitimos_file, index=False)
            self.metadata['casos_legitimos'] = str(legitimos_file)
            self.metadata['casos_legitimos_por_tipo'] = legitimos['tipo_caso'].value_counts().to_dict()
            logger.info(f"  ✓ casos_legitimos.csv guardado ({len(legitimos)} casos)")

        # Guardar metadatos
        metadata_file = self.output_dir / "metadata.json"
        self.metadata['archivos'] = archivos
        self.metadata['ground_truth'] = str(gt_file)
        self.metadata['anomalias_por_tipo'] = ground_truth['tipo_anomalia'].value_counts().to_dict()
        self.metadata['directorio_salida'] = str(self.output_dir)

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"✓ Metadatos guardados en {metadata_file}")
        return archivos

    def ejecutar(self):
        """Ejecuta todo el pipeline"""
        logger.info("=" * 60)
        logger.info(f"INICIANDO PIPELINE MAESTRO DE GENERACIÓN (escenario {self.escenario})")
        logger.info("=" * 60)

        try:
            if self.escenario == "realista":
                self.generar_flota_realista()
                self.generar_estaciones()
                self.generar_consumo_realista()  # también genera la telemetría
            else:
                self.generar_flota()
                self.generar_telemetria()
                self.generar_consumo()
            self.generar_solicitudes()
            self.generar_facturacion()

            archivos = self.guardar_datasets()

            logger.info("=" * 60)
            logger.info("✅ PIPELINE COMPLETADO EXITOSAMENTE")
            logger.info("=" * 60)

            return {
                "exito": True,
                "directorio": str(self.output_dir),
                "archivos": archivos,
                "ground_truth": self.metadata['ground_truth'],
                "metadata": self.metadata
            }

        except Exception as e:
            logger.error(f"❌ Error en pipeline: {e}", exc_info=True)
            return {
                "exito": False,
                "error": str(e),
                "directorio": str(self.output_dir)
            }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Maestro - Generador de datos sintéticos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python generator_pipeline_maestro.py                    # Usa valores por defecto (200 vehículos, seed 42)
  python generator_pipeline_maestro.py --n_flota 100      # Genera 100 vehículos
  python generator_pipeline_maestro.py --seed 123         # Usa seed 123 para reproducibilidad
  python generator_pipeline_maestro.py --n_flota 500 --seed 99
  python generator_pipeline_maestro.py --escenario realista
        """
    )

    parser.add_argument(
        '--n_flota',
        type=int,
        default=200,
        help='Número de vehículos a generar (default: 200)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=SEED,
        help=f'Seed para reproducibilidad (default: {SEED})'
    )

    parser.add_argument(
        '--escenario',
        choices=ESCENARIOS,
        default='didactico',
        help='didactico: anomalías inconfundibles; realista: uso simulado día por día, '
             'anomalías sutiles y casos legítimos que se les parecen (default: didactico)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Directorio de salida (default: datasets/synthetics_maestro o datasets/synthetics_realista)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Modo silencioso (menos output)'
    )

    args = parser.parse_args()

    # Validar parámetros
    if args.n_flota < 10:
        print("❌ Error: n_flota debe ser al menos 10")
        sys.exit(1)
    if args.n_flota > 5000:
        print("⚠️  Advertencia: Generar más de 5000 vehículos puede tomar mucho tiempo")

    generador = GeneradorMaestro(n_flota=args.n_flota, seed=args.seed, output_dir=args.output,
                                 escenario=args.escenario)
    resultado = generador.ejecutar()

    # Imprimir resumen
    if not args.quiet:
        print("\n" + "=" * 60)
        print("RESUMEN FINAL")
        print("=" * 60)

    if resultado['exito']:
        if not args.quiet:
            for nombre, ruta in resultado['archivos'].items():
                df = pd.read_csv(ruta)
                print(f"  {nombre:20} | {len(df):6} filas | {ruta}")
            print(f"  {'ground_truth':20} | {len(generador.anomalias):6} filas | {resultado['ground_truth']}")
            print("\n✅ ÉXITO - Todos los datos fueron generados correctamente")
        print(json.dumps(resultado, indent=2, default=str))
    else:
        print(f"❌ ERROR: {resultado['error']}")

    sys.exit(0 if resultado['exito'] else 1)
