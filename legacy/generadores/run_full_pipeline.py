#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline Completo: Generador Sintético Auditoria en D:\Integrador
==================================================================

Ejecuta la secuencia completa:
  1. v7.5 Hybrid Generator (flota base)
  2. Generador Combustible (YPF + RIGCOM)
  3. Generador Consumo Diario
  4. Generador Facturas

Uso:
    python run_full_pipeline.py [--vehicles 200] [--periodo 202609]

Salida:
    data/synthetic/           (flota + defectos)
    data/combustible/         (YPF + RIGCOM)
    data/consumo/             (ReporteConsumos)
    data/facturacion/         (PDF + Deuda)
    data/anomalias_*.csv      (ground truth)
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Importar generadores
try:
    from generator_v7_5_hybrid import generate_dataset, GenerationConfig
    from generator_combustible_standalone import generar as generar_combustible
    from generator_consumo_diario_standalone import generar as generar_consumo
    from generator_facturas_standalone import generar as generar_facturas
except ImportError as e:
    print(f"❌ Error: {e}")
    print("Asegurate de que todos los generators estén en D:\\Integrador")
    sys.exit(1)


def print_header(titulo):
    print("\n" + "=" * 80)
    print(f"🚀 {titulo}")
    print("=" * 80)


def print_section(titulo):
    print(f"\n>>> {titulo}")


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Completo: Flota + Combustible + Consumo + Facturas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Ejecución estándar (200 vehículos, mes 202609)
  python run_full_pipeline.py

  # Escala mayor
  python run_full_pipeline.py --vehicles 500 --periodo 202610
        """
    )

    parser.add_argument(
        '--vehicles',
        type=int,
        default=200,
        help='Número de vehículos (default 200)'
    )
    parser.add_argument(
        '--periodo',
        type=str,
        default='202609',
        help='Período AAAAMMM (default 202609 = septiembre 2026)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=20260909,
        help='Seed para reproducibilidad (default 20260909 = hoy)'
    )
    parser.add_argument(
        '--skip-combustible',
        action='store_true',
        help='Saltar generador de combustible'
    )
    parser.add_argument(
        '--skip-consumo',
        action='store_true',
        help='Saltar generador de consumo'
    )
    parser.add_argument(
        '--skip-facturas',
        action='store_true',
        help='Saltar generador de facturas'
    )

    args = parser.parse_args()

    print_header("PIPELINE SINTÉTICO AUDITORIA - D:\\Integrador")
    print(f"\n📋 Configuración:")
    print(f"   Vehículos: {args.vehicles}")
    print(f"   Período: {args.periodo}")
    print(f"   Seed: {args.seed}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ===================================================================
    # PASO 1: Generador v7.5 Hybrid
    # ===================================================================
    print_section("PASO 1: Generador v7.5 Hybrid (Flota Base)")
    try:
        config = GenerationConfig(
            num_vehicles=args.vehicles,
            num_devices_per_vehicle=0.85,
            seed=args.seed,
        )
        dataset = generate_dataset(config)

        # Guardar CSVs
        data_dir = Path("data") / "synthetic"
        data_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files_saved = 0

        for name, df in [
            ('vehiculos', dataset['vehiculo']),
            ('dispositivos', dataset['dispositivo']),
            ('defectos', dataset['defects']),
            ('anomalias', dataset['anomalies']),
            ('ground_truth', dataset['ground_truth']),
        ]:
            filepath = data_dir / f"{name}_{timestamp}.csv"
            df.to_csv(filepath, index=False)
            files_saved += 1

        print(f"✅ Flota generada:")
        print(f"   Vehículos: {len(dataset['vehiculo'])}")
        print(f"   Dispositivos: {len(dataset['dispositivo'])}")
        print(f"   Defectos inyectados: {len(dataset['defects'])}")
        print(f"   Anomalías inyectadas: {len(dataset['anomalies'])}")
        print(f"   Ground truth: {len(dataset['ground_truth'])}")
        print(f"   Archivos: {files_saved} CSVs guardados en data/synthetic/")

    except Exception as e:
        print(f"❌ Error en v7.5: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ===================================================================
    # PASO 2: Generador Combustible
    # ===================================================================
    if not args.skip_combustible:
        print_section("PASO 2: Generador Combustible (YPF + RIGCOM)")
        try:
            from generator_combustible_standalone import ConfigCombustible
            cfg = ConfigCombustible(seed=args.seed)
            res, ano = generar_combustible(cfg)
            print(f"✅ Combustible generado:")
            print(f"   Transacciones YPF: {res['ypf'].sum()}")
            print(f"   Solicitudes RIGCOM: {res['rigcom'].sum()}")
            print(f"   Anomalías: {len(ano)}")
            print(f"   Archivo: data/anomalias_combustible.csv")
        except Exception as e:
            print(f"❌ Error en combustible: {e}")
            import traceback
            traceback.print_exc()
            return 1
    else:
        print_section("⏭️ PASO 2: Combustible OMITIDO")

    # ===================================================================
    # PASO 3: Generador Consumo
    # ===================================================================
    if not args.skip_consumo:
        print_section("PASO 3: Generador Consumo Diario")
        try:
            resumen = generar_consumo(meses=2)
            print(f"✅ Consumo generado:")
            print(f"   Meses: {len(resumen)}")
            print(f"   Transacciones: {sum(r['transacciones'] for r in resumen)}")
            print(f"   Anomalías odometro: {sum(r['anomalias_odometro'] for r in resumen)}")
        except Exception as e:
            print(f"❌ Error en consumo: {e}")
            import traceback
            traceback.print_exc()
            return 1
    else:
        print_section("⏭️ PASO 3: Consumo OMITIDO")

    # ===================================================================
    # PASO 4: Generador Facturas
    # ===================================================================
    if not args.skip_facturas:
        print_section("PASO 4: Generador Facturas")
        try:
            filas = generar_facturas(args.periodo)
            print(f"✅ Facturas generadas:")
            print(f"   Total: {len(filas)}")
            print(f"   Importe: ${sum(f['total'] for f in filas):,.0f}")
            anomalias_fact = sum(1 for f in filas if f['desvio'])
            print(f"   Anomalías: {anomalias_fact}")
        except Exception as e:
            print(f"⚠️ Advertencia en facturas: {e}")
            print("   (Esto es normal si faltan datos de consumo)")
    else:
        print_section("⏭️ PASO 4: Facturas OMITIDO")

    # ===================================================================
    # RESUMEN FINAL
    # ===================================================================
    print_header("✅ PIPELINE COMPLETADO")
    print(f"\n📁 Estructura generada:")
    print(f"""
    D:\\Integrador\\
    ├── data/
    │   ├── synthetic/           (v7.5 Hybrid)
    │   │   ├── vehiculos_*.csv
    │   │   ├── dispositivos_*.csv
    │   │   ├── defectos_*.csv
    │   │   ├── anomalias_*.csv
    │   │   └── ground_truth_*.csv
    │   ├── combustible/         (YPF)
    │   ├── rigcom/              (RIGCOM)
    │   ├── consumo/             (Consumo diario)
    │   ├── facturacion/         (Facturas)
    │   └── anomalias_combustible.csv
    └── ...
    """)

    print(f"🎯 Próximos pasos:")
    print(f"   1. Revisar CSVs en data/synthetic/")
    print(f"   2. Ejecutar pytest test_generator_v7_5.py -v")
    print(f"   3. Cargar datos en pipeline de auditoría")
    print(f"   4. Medir precision/recall vs ground_truth")

    return 0


if __name__ == "__main__":
    sys.exit(main())
