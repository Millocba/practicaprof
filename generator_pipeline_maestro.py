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
}

# Anomalías que siguen presentes en una fila duplicada (las de odómetro no: la copia
# repite fecha y lectura, así que no hay cambio que detectar)
ANOMALIAS_HEREDABLES = {"EXCESO_VOLUMETRICO", "DOMINIO_INVALIDO", "VALOR_NULO"}

COLUMNAS_GROUND_TRUTH = [
    "tabla", "id_registro", "vehiculo_id", "tipo_anomalia",
    "columna", "hipotesis", "severidad", "descripcion",
]


class GeneradorMaestro:
    """Orquesta la generación de todas las entidades"""

    def __init__(self, n_flota=200, seed=SEED, output_dir=None):
        self.n_flota = n_flota
        self.seed = seed
        self.output_dir = Path(output_dir) if output_dir else DATASETS_DIR
        # Generador propio: no depende del estado global de `random`
        self.rng = random.Random(seed)
        self.datasets = {}
        self.anomalias = []
        self.metadata = {
            "fecha_generacion": datetime.now().isoformat(),
            "fecha_referencia": FECHA_REFERENCIA.isoformat(),
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

    def construir_ground_truth(self):
        """Tabla con una fila por anomalía inyectada (un registro puede tener varias)."""
        return pd.DataFrame(self.anomalias, columns=COLUMNAS_GROUND_TRUTH)

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
        '--output',
        type=Path,
        default=DATASETS_DIR,
        help='Directorio de salida (default: datasets/synthetics_maestro)'
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

    generador = GeneradorMaestro(n_flota=args.n_flota, seed=args.seed, output_dir=args.output)
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
