#!/usr/bin/env python3
"""
Pipeline Maestro - Ejecuta todos los generadores de datos
Genera: Flota, Telemetría, Consumo, Facturación, Solicitudes
"""

import os
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
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# Seed para reproducibilidad
SEED = 42
random.seed(SEED)
import numpy as np
np.random.seed(SEED)


class GeneradorMaestro:
    """Orquesta la generación de todas las entidades"""

    def __init__(self, n_flota=200, seed=SEED):
        self.n_flota = n_flota
        self.seed = seed
        random.seed(seed)
        self.datasets = {}
        self.metadata = {
            "fecha_generacion": datetime.now().isoformat(),
            "seed": seed,
            "n_flota": n_flota,
            "generadores_ejecutados": []
        }

    def generar_flota(self):
        """Genera tabla FLOTA (200 vehículos)"""
        logger.info("Generando FLOTA...")

        dg = [
            "DIRECCION GRAL. SEGURIDAD CAPITAL",
            "DIRECCION GRAL. SEGURIDAD PROVINCIA",
            "DIRECCION GRAL. LOGISTICA",
            "DIRECCION GRAL. OBRAS",
            "DIRECCION GRAL. SALUD",
        ]

        dependencias = {
            "DIRECCION GRAL. SEGURIDAD CAPITAL": ["DEP A", "DEP B", "DEP C"],
            "DIRECCION GRAL. SEGURIDAD PROVINCIA": ["DEP D", "DEP E"],
            "DIRECCION GRAL. LOGISTICA": ["DEP F", "DEP G"],
            "DIRECCION GRAL. OBRAS": ["DEP H"],
            "DIRECCION GRAL. SALUD": ["DEP I", "DEP J"],
        }

        marcas = ["FORD", "TOYOTA", "VOLKSWAGEN", "RENAULT", "HONDA", "FIAT", "IVECO", "CHEVROLET"]
        tipos = ["SEDAN", "PICK-UP", "MOTOCICLETA", "CAMIONETA", "CAMION", "AMBULANCIA", "UTILITARIO", "BOMBERO"]
        combustible = ["GASOIL", "GASOIL", "GASOIL", "GASOIL", "GASOIL", "NAFTA", "NAFTA", "NAFTA", "GLP"]
        estados = ["EN SERVICIO", "EN SERVICIO", "EN SERVICIO", "EN REPARACION", "FUERA DE SERVICIO", "BAJA"]

        rows = []
        for i in range(1, self.n_flota + 1):
            dg_sel = random.choice(dg)
            dep = random.choice(dependencias[dg_sel])
            estado = random.choice(estados)
            identificable = "SI" if random.random() < 0.94 else "NO"
            annio = random.randint(2005, 2024)

            rows.append({
                "Matricula": f"VEH-{i:06d}",
                "Dominio": f"AB{i:04d}CD",
                "Estado": estado,
                "DireccionGral": dg_sel,
                "Dependencia": dep,
                "Identificable": identificable,
                "TipoVehiculo": random.choice(tipos),
                "Marca": random.choice(marcas),
                "Modelo": f"MODEL-{random.randint(2010, 2024)}",
                "Año": annio,
                "TipoCombustible": random.choice(combustible),
                "CapacidadTanque": random.uniform(40, 120),
                "NumeroMotor": f"M{i:08d}",
                "NumeroChasis": f"CH{i:08d}",
                "NumeroTarjeta": f"TARJ{i:08d}",
                "LimiteSaldo": random.uniform(1000, 10000),
                "LimiteLitros": random.uniform(100, 500),
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

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        n_dispositivos = int(self.n_flota * 0.88)  # 88% cobertura

        rows = []
        ahora = datetime.now()
        for i in range(1, n_dispositivos + 1):
            online = random.random() < 0.88
            bateria = round(random.uniform(20, 100), 1)
            last = ahora - timedelta(minutes=random.randint(0, 15 if online else 600))

            # Link a un vehículo de la flota
            vehiculo = random.choice(flota_df['Dominio'].values)

            rows.append({
                "IMEI": f"{random.randint(350000000000000, 359999999999999)}",
                "Alias": f"DEV-{i:06d}",
                "Placa": vehiculo,
                "MSISDN": f"54911{random.randint(1000000, 9999999)}",
                "Modelo": f"GPS-{random.choice(['A', 'B', 'C'])}-{random.randint(1, 5)}",
                "Tipo": "GPS",
                "Estado": "ONLINE" if online else "OFFLINE",
                "Bateria": bateria,
                "UltimaConexion": last.isoformat(),
                "Latitud": round(random.uniform(-34.9, -34.4), 6),
                "Longitud": round(random.uniform(-58.8, -58.2), 6),
                "Odometro": random.randint(10000, 300000),
            })

        df = pd.DataFrame(rows)
        self.datasets['telemetria'] = df
        self.metadata['generadores_ejecutados'].append('telemetria')
        logger.info(f"✓ TELEMETRIA generada: {len(df)} dispositivos")
        return df

    def generar_consumo(self):
        """Genera tabla CONSUMO (transacciones de combustible)

        Incluye inyección de defectos:
        - ~5-10% de vehículos con consumos anómalos (superen capacidad)
        - Para validar H3a (Exceso Volumétrico)
        """
        logger.info("Generando CONSUMO...")

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        productos = ["GASOIL", "NAFTA", "INFINIA", "SUPER", "GLP"]
        estaciones = ["YPF", "SHELL", "AXION", "PUMA", "ESTACION LOCAL"]

        # Seleccionar vehículos anómalos (~7% de la flota para H3a)
        n_anomalos = max(5, int(self.n_flota * 0.07))
        indices_anomalos = set(random.sample(range(len(flota_df)), min(n_anomalos, len(flota_df))))

        rows = []
        fecha_inicio = datetime(2024, 1, 1)

        for veh_idx, veh_row in flota_df.iterrows():
            # Cada vehículo genera 5-12 transacciones
            n_transacciones = random.randint(5, 12)
            es_anomalo = veh_idx in indices_anomalos

            for _ in range(n_transacciones):
                fecha = fecha_inicio + timedelta(days=random.randint(0, 270))
                capacidad = veh_row.get('CapacidadTanque', 100)

                # DEFECTO H3a: Vehículos anómalos consumen más que la capacidad del tanque
                if es_anomalo:
                    # Generar consumos que superen la capacidad (1.1x a 1.8x)
                    litros = round(random.uniform(capacidad * 1.1, capacidad * 1.8), 2)
                else:
                    # Vehículos normales: consumo prudente
                    litros = round(random.uniform(5, min(80, capacidad * 0.8)), 2)

                rows.append({
                    "id": f"CONS-{len(rows)+1:08d}",
                    "vehiculo_id": veh_row['Matricula'],
                    "dominio": veh_row['Dominio'],
                    "fecha": fecha,
                    "estacion": random.choice(estaciones),
                    "producto": random.choice(productos),
                    "litros": litros,
                    "precio_unitario": round(random.uniform(1.5, 3.5), 2),
                    "importe_total": 0.0,  # Calculado después
                    "numero_tarjeta": veh_row['NumeroTarjeta'],
                    "conductor": f"CONDUCTOR-{random.randint(1, 500)}",
                    "odometro": random.randint(10000, 300000),
                    "_es_anomalo": es_anomalo,  # Flag para análisis
                })

        df = pd.DataFrame(rows)
        # Calcular importe
        df['importe_total'] = (df['litros'] * df['precio_unitario']).round(2)

        # Remover flag (solo para generación)
        df = df.drop('_es_anomalo', axis=1)

        self.datasets['consumo'] = df
        self.metadata['generadores_ejecutados'].append('consumo')
        logger.info(f"✓ CONSUMO generado: {len(df)} transacciones ({n_anomalos} vehículos con anomalías H3a)")
        return df

    def generar_solicitudes(self):
        """Genera tabla SOLICITUDES (solicitudes de combustible)"""
        logger.info("Generando SOLICITUDES...")

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        estados_solicitud = ["APROBADA", "PENDIENTE", "RECHAZADA", "APROBADA"]

        rows = []
        fecha_inicio = datetime(2024, 1, 1)

        for veh_idx, veh_row in flota_df.iterrows():
            # Cada vehículo genera 1-4 solicitudes
            n_solicitudes = random.randint(1, 4)

            for sol_idx in range(n_solicitudes):
                fecha = fecha_inicio + timedelta(days=random.randint(0, 270))

                rows.append({
                    "id": f"SOL-{len(rows)+1:08d}",
                    "vehiculo_id": veh_row['Matricula'],
                    "dominio": veh_row['Dominio'],
                    "fecha_solicitud": fecha,
                    "litros_solicitados": round(random.uniform(20, 100), 2),
                    "litros_autorizados": round(random.uniform(20, 100), 2),
                    "estado": random.choice(estados_solicitud),
                    "centro_costo": f"CC-{random.randint(1, 50):03d}",
                    "responsable": f"RESP-{random.randint(1, 100)}",
                    "observaciones": random.choice(["OK", "REVISADO", "PENDIENTE", ""]),
                })

        df = pd.DataFrame(rows)
        self.datasets['solicitudes'] = df
        self.metadata['generadores_ejecutados'].append('solicitudes')
        logger.info(f"✓ SOLICITUDES generada: {len(df)} solicitudes")
        return df

    def generar_facturacion(self):
        """Genera tabla FACTURACION (facturas)"""
        logger.info("Generando FACTURACION...")

        consumo_df = self.datasets.get('consumo')
        if consumo_df is None:
            logger.error("CONSUMO debe generarse primero")
            return None

        # Agrupar consumo por mes y generar facturas
        consumo_df_copy = consumo_df.copy()
        consumo_df_copy['mes'] = consumo_df_copy['fecha'].dt.to_period('M')

        rows = []
        for (mes, grupo) in consumo_df_copy.groupby('mes'):
            factura_num = f"FAC-{mes.year}{mes.month:02d}-{random.randint(1000, 9999)}"
            total_monto = grupo['importe_total'].sum()

            rows.append({
                "numero_factura": factura_num,
                "fecha_factura": mes.end_time.date(),
                "periodo": str(mes),
                "total_litros": grupo['litros'].sum(),
                "total_monto": total_monto,
                "iva": total_monto * 0.21,
                "monto_total_con_iva": total_monto * 1.21,
                "estado": random.choice(["PAGADA", "PENDIENTE", "VENCIDA"]),
                "numero_transacciones": len(grupo),
            })

        df = pd.DataFrame(rows)
        self.datasets['facturacion'] = df
        self.metadata['generadores_ejecutados'].append('facturacion')
        logger.info(f"✓ FACTURACION generada: {len(df)} facturas")
        return df

    def guardar_datasets(self):
        """Guarda todos los datasets en CSV"""
        logger.info("Guardando datasets...")

        archivos = {}
        for nombre, df in self.datasets.items():
            filepath = DATASETS_DIR / f"{nombre}.csv"
            df.to_csv(filepath, index=False)
            archivos[nombre] = str(filepath)
            logger.info(f"  ✓ {nombre}.csv guardado ({len(df)} filas)")

        # Guardar metadatos
        metadata_file = DATASETS_DIR / "metadata.json"
        self.metadata['archivos'] = archivos
        self.metadata['directorio_salida'] = str(DATASETS_DIR)

        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)

        logger.info(f"✓ Metadatos guardados en {metadata_file}")
        return archivos

    def ejecutar(self):
        """Ejecuta todo el pipeline"""
        logger.info("=" * 60)
        logger.info("INICIANDO PIPELINE MAESTRO DE GENERACIÓN")
        logger.info("=" * 60)

        try:
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
                "directorio": str(DATASETS_DIR),
                "archivos": archivos,
                "metadata": self.metadata
            }

        except Exception as e:
            logger.error(f"❌ Error en pipeline: {e}", exc_info=True)
            return {
                "exito": False,
                "error": str(e),
                "directorio": str(DATASETS_DIR)
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
        default=42,
        help='Seed para reproducibilidad (default: 42)'
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

    generador = GeneradorMaestro(n_flota=args.n_flota, seed=args.seed)
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
            print("\n✅ ÉXITO - Todos los datos fueron generados correctamente")
        print(json.dumps(resultado, indent=2, default=str))
    else:
        print(f"❌ ERROR: {resultado['error']}")

    sys.exit(0 if resultado['exito'] else 1)
