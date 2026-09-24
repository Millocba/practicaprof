#!/usr/bin/env python3
"""
SCRIPT DE INSTALACIÓN: Generador Híbrido v7.5
==============================================

Este script crea la estructura completa en D:\Integrador
Uso: python setup_integrador.py

Crea:
- Carpeta data/synthetic
- Genera dataset de prueba (200 vehículos)
- Valida la instalación
"""

import os
import sys
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("INSTALACIÓN: Generador Híbrido v7.5 en D:\\Integrador")
print("=" * 80)

# Detectar D:\Integrador
integrador_path = Path("D:\\Integrador") if Path("D:\\Integrador").exists() else Path(".")

print(f"\n📍 Ubicación detectada: {integrador_path}")

# 1. Crear carpeta data/synthetic
data_dir = integrador_path / "data" / "synthetic"
try:
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Carpeta creada: {data_dir}")
except Exception as e:
    print(f"❌ Error creando carpeta: {e}")
    sys.exit(1)

# 2. Verificar que generator_v7_5_hybrid.py existe
generator_file = integrador_path / "generator_v7_5_hybrid.py"
if not generator_file.exists():
    print(f"❌ CRÍTICO: generator_v7_5_hybrid.py no encontrado en {integrador_path}")
    print("   Descárgalo desde Claude y cópialo a D:\\Integrador")
    sys.exit(1)

print(f"✅ Generador encontrado: {generator_file.name}")

# 3. Importar y generar datos
print("\n⏳ Generando dataset de prueba...")
try:
    sys.path.insert(0, str(integrador_path))
    from generator_v7_5_hybrid import generate_dataset, GenerationConfig

    config = GenerationConfig(
        num_vehicles=200,
        num_devices_per_vehicle=0.85,
        seed=20260909,
    )

    dataset = generate_dataset(config)
    print("✅ Dataset generado exitosamente")

except Exception as e:
    print(f"❌ Error generando dataset: {e}")
    sys.exit(1)

# 4. Guardar CSVs
print("\n💾 Guardando CSVs...")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

try:
    import pandas as pd

    files = {
        'vehiculos': dataset['vehiculo'],
        'dispositivos': dataset['dispositivo'],
        'defectos': dataset['defects'],
        'anomalias': dataset['anomalies'],
        'ground_truth': dataset['ground_truth'],
    }

    for name, df in files.items():
        filepath = data_dir / f"{name}_{timestamp}.csv"
        df.to_csv(filepath, index=False)
        print(f"   ✅ {filepath.name}")

except Exception as e:
    print(f"❌ Error guardando CSVs: {e}")
    sys.exit(1)

# 5. Mostrar estadísticas
print("\n📊 ESTADÍSTICAS GENERADAS:")
print(f"   Vehículos: {len(dataset['vehiculo'])}")
print(f"   Dispositivos: {len(dataset['dispositivo'])}")
print(f"   Defectos inyectados: {len(dataset['defects'])}")
print(f"   Anomalías inyectadas: {len(dataset['anomalies'])}")
print(f"   Ground truth total: {len(dataset['ground_truth'])}")

# 6. Verificar archivos
print("\n🔍 VERIFICACIÓN:")
csv_files = list(data_dir.glob("*.csv"))
print(f"   CSVs creados: {len(csv_files)}")
for f in csv_files:
    print(f"      ✅ {f.name}")

# 7. Resumen
print("\n" + "=" * 80)
print("✅ INSTALACIÓN COMPLETADA")
print("=" * 80)
print(f"\n📁 Ubicación: {data_dir}")
print(f"📄 Archivos: {len(csv_files)} CSVs")
print(f"🎯 Seed: 20260909 (reproducible)")
print("\n💡 Próximos pasos:")
print("   1. Revisar CSVs en data/synthetic/")
print("   2. Ejecutar: pytest test_generator_v7_5.py -v")
print("   3. Integrar con tu pipeline ETL")
print("\n" + "=" * 80)

