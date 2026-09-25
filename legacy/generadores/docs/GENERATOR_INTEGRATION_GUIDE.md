# Guía de Integración: Generador Híbrido v7.5
## Para el Proyecto Prácticas Profesionalizantes

**Preparado**: 2026-09-09  
**Versión**: 1.0  
**Responsable**: Sistema de Auditoría (basado en experiencia del proyecto PRESENTACION-Auditoria)

---

## 📦 Archivos Entregables

```
generator_v7_5_hybrid.py          # Código principal (21 KB, ~500 líneas)
HYBRID_GENERATOR_SPEC.md          # Especificación detallada de defectos/anomalías
GENERATOR_INTEGRATION_GUIDE.md    # Este archivo
```

---

## 🚀 Integración en 5 Pasos

### Paso 1: Crear Estructura de Carpetas

```bash
cd tu_proyecto_practicas_profesionalizantes

# Crear carpeta para generadores
mkdir -p generators/synthetic
cd generators/synthetic

# Copiar archivos
cp /ruta/descargados/generator_v7_5_hybrid.py .
cp /ruta/descargados/HYBRID_GENERATOR_SPEC.md .
```

**Estructura final esperada**:
```
tu_proyecto/
├── generators/
│   └── synthetic/
│       ├── __init__.py
│       ├── generator_v7_5_hybrid.py
│       ├── HYBRID_GENERATOR_SPEC.md
│       └── README.md
├── data/
│   └── synthetic/          # Aquí irán los CSVs generados
├── tests/
│   └── test_synthetic_data.py
└── scripts/
    └── generate_synthetic_data.py
```

---

### Paso 2: Crear `__init__.py`

```python
# generators/synthetic/__init__.py
from .generator_v7_5_hybrid import generate_dataset, GenerationConfig

__all__ = ['generate_dataset', 'GenerationConfig']
```

---

### Paso 3: Crear Script de Generación

```python
# scripts/generate_synthetic_data.py
#!/usr/bin/env python3
"""
Genera dataset sintético para pruebas/auditoría
Uso: python scripts/generate_synthetic_data.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Agregar proyecto al path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generators.synthetic import generate_dataset, GenerationConfig

def main():
    print("=" * 80)
    print("GENERADOR SINTÉTICO v7.5 - Prácticas Profesionalizantes")
    print("=" * 80)
    
    # Crear carpeta de output
    output_dir = PROJECT_ROOT / "data" / "synthetic"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar con configuración estándar
    config = GenerationConfig(
        num_vehicles=200,
        num_devices_per_vehicle=0.85,
        seed=20260909,  # Fecha como seed para reproducibilidad
    )
    
    print(f"\n🔧 Configuración:")
    print(f"   Vehículos: {config.num_vehicles}")
    print(f"   Cobertura de dispositivos: {config.num_devices_per_vehicle * 100:.0f}%")
    print(f"   Seed: {config.seed}")
    
    print(f"\n⏳ Generando dataset...")
    dataset = generate_dataset(config)
    
    # Extraer DataFrames
    vehiculos = dataset['vehiculo']
    dispositivos = dataset['dispositivo']
    defectos = dataset['defects']
    anomalias = dataset['anomalies']
    ground_truth = dataset['ground_truth']
    
    # Timestamp para archivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Guardar archivos
    print(f"\n💾 Guardando archivos...")
    
    veh_file = output_dir / f"vehiculos_{timestamp}.csv"
    dev_file = output_dir / f"dispositivos_{timestamp}.csv"
    defects_file = output_dir / f"defectos_{timestamp}.csv"
    anomalies_file = output_dir / f"anomalias_{timestamp}.csv"
    gt_file = output_dir / f"ground_truth_{timestamp}.csv"
    
    vehiculos.to_csv(veh_file, index=False)
    print(f"   ✅ {veh_file.name}")
    
    dispositivos.to_csv(dev_file, index=False)
    print(f"   ✅ {dev_file.name}")
    
    defectos.to_csv(defects_file, index=False)
    print(f"   ✅ {defects_file.name}")
    
    anomalias.to_csv(anomalies_file, index=False)
    print(f"   ✅ {anomalies_file.name}")
    
    ground_truth.to_csv(gt_file, index=False)
    print(f"   ✅ {gt_file.name}")
    
    # Estadísticas
    print(f"\n📊 ESTADÍSTICAS GENERADAS:")
    print(f"   Vehículos: {len(vehiculos)}")
    print(f"   Dispositivos: {len(dispositivos)} ({len(dispositivos)/len(vehiculos)*100:.1f}%)")
    print(f"   Defectos inyectados: {len(defectos)} ({len(defectos)/len(vehiculos)*100:.1f}%)")
    print(f"   Anomalías inyectadas: {len(anomalias)} ({len(anomalias)/len(dispositivos)*100:.1f}%)")
    print(f"   Problemas totales: {len(ground_truth)} ({len(ground_truth)/(len(vehiculos)+len(dispositivos))*100:.1f}%)")
    
    # Ground truth summary
    print(f"\n📈 RESUMEN DE DEFECTOS:")
    if len(defectos) > 0:
        for tipo, count in defectos['tipo'].value_counts().items():
            print(f"   {tipo}: {count}")
    
    print(f"\n⚠️  RESUMEN DE ANOMALÍAS:")
    if len(anomalias) > 0:
        for tipo, count in anomalias['tipo'].value_counts().items():
            print(f"   {tipo}: {count}")
    
    print(f"\n✅ Dataset sintético generado exitosamente")
    print(f"   Ubicación: {output_dir}")
    print(f"   Archivos: {len(list(output_dir.glob(f'*_{timestamp}.csv')))}")
    
    return 0

if __name__ == "__main__":
    exit(main())
```

---

### Paso 4: Crear Tests de Validación

```python
# tests/test_synthetic_data.py
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generators.synthetic import generate_dataset, GenerationConfig


class TestSyntheticDataGeneration:
    """Tests para validar generador sintético"""
    
    def test_basic_generation(self):
        """Genera dataset sin errores"""
        config = GenerationConfig(num_vehicles=50, seed=12345)
        dataset = generate_dataset(config)
        
        assert 'vehiculo' in dataset
        assert 'dispositivo' in dataset
        assert 'defects' in dataset
        assert 'anomalies' in dataset
        assert len(dataset['vehiculo']) > 0
    
    def test_reproducibility(self):
        """Mismo seed produce mismo dataset"""
        config = GenerationConfig(num_vehicles=50, seed=12345)
        
        dataset1 = generate_dataset(config)
        dataset2 = generate_dataset(config)
        
        assert dataset1['vehiculo'].equals(dataset2['vehiculo'])
        assert dataset1['dispositivo'].equals(dataset2['dispositivo'])
    
    def test_transmission_states(self):
        """Estados de transmisión son válidos"""
        config = GenerationConfig(num_vehicles=100, seed=12345)
        dataset = generate_dataset(config)
        
        dispositivos = dataset['dispositivo']
        valid_states = ['En línea', 'Apagado o fuera de cobertura']
        
        assert dispositivos['Estado de transmisión'].isin(valid_states).all()
        
        # Distribución realista: ~70% online, ~30% offline
        online_pct = (dispositivos['Estado de transmisión'] == 'En línea').sum() / len(dispositivos)
        assert 0.6 < online_pct < 0.8  # Entre 60-80%
    
    def test_vehicle_types(self):
        """Tipos de vehículos son válidos"""
        config = GenerationConfig(num_vehicles=100, seed=12345)
        dataset = generate_dataset(config)
        
        vehiculos = dataset['vehiculo']
        valid_types = ['MOTOCICLETA', 'SEDAN', 'PICK-UP', 'CAMIÓN']
        
        assert vehiculos['TipoVehiculo'].isin(valid_types).all()
    
    def test_defects_injection(self):
        """Defectos se inyectan correctamente"""
        config = GenerationConfig(
            num_vehicles=200, 
            seed=12345,
            text_normalization_rate=0.20,  # Tasa alta para test
        )
        dataset = generate_dataset(config)
        
        defectos = dataset['defects']
        assert len(defectos) > 0
        assert 'TEXT_NORMALIZATION' in defectos['tipo'].values
    
    def test_ground_truth_completeness(self):
        """Ground truth contiene toda la información"""
        config = GenerationConfig(num_vehicles=100, seed=12345)
        dataset = generate_dataset(config)
        
        gt = dataset['ground_truth']
        
        # Debe tener columnas de auditoría
        required_cols = ['tabla', 'fila', 'columna', 'tipo', 'severidad']
        for col in required_cols:
            assert col in gt.columns
        
        # No debe haber NaNs en columnas críticas
        assert not gt['tabla'].isna().any()
        assert not gt['fila'].isna().any()
        assert not gt['tipo'].isna().any()


def test_generation_with_realistic_config():
    """Test con configuración realista"""
    config = GenerationConfig(
        num_vehicles=500,
        num_devices_per_vehicle=0.85,
        seed=20260909
    )
    
    dataset = generate_dataset(config)
    
    # Validaciones
    assert len(dataset['vehiculo']) == 500
    assert 400 < len(dataset['dispositivo']) < 450  # ~85%
    assert len(dataset['defects']) > 0
    assert len(dataset['anomalies']) > 0
```

---

### Paso 5: Agregar a CI Pipeline (opcional)

Si usas GitHub Actions:

```yaml
# .github/workflows/test-synthetic-data.yml
name: Synthetic Data Tests

on:
  push:
    branches: [ main, develop ]
    paths:
      - 'generators/synthetic/**'
      - 'tests/test_synthetic_data.py'
      - 'scripts/generate_synthetic_data.py'

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pandas
    
    - name: Run tests
      run: pytest tests/test_synthetic_data.py -v
    
    - name: Generate synthetic data
      run: python scripts/generate_synthetic_data.py
```

---

## ✅ Checklist de Integración

- [ ] Crear carpeta `generators/synthetic/`
- [ ] Copiar `generator_v7_5_hybrid.py`
- [ ] Crear `__init__.py`
- [ ] Crear `scripts/generate_synthetic_data.py`
- [ ] Crear `tests/test_synthetic_data.py`
- [ ] Ejecutar `python scripts/generate_synthetic_data.py`
- [ ] Verificar que genera CSV sin errores
- [ ] Ejecutar `pytest tests/test_synthetic_data.py`
- [ ] Agregar a `.gitignore`: `data/synthetic/`
- [ ] Documentar en README principal del proyecto

---

## 🔍 Verificación Rápida

Una vez integrado, ejecuta:

```bash
# 1. Generar datos
python scripts/generate_synthetic_data.py

# 2. Verificar estructura
ls -la data/synthetic/

# 3. Ejecutar tests
pytest tests/test_synthetic_data.py -v

# 4. Inspeccionar datos (Python REPL)
import pandas as pd
df_veh = pd.read_csv('data/synthetic/vehiculos_*.csv')
print(df_veh.head())
print(df_veh.columns)
```

---

## 📞 Próximos Pasos

1. **Adaptar a tu dominio**: Si no trabajas con vehículos/dispositivos, adaptar:
   - `PERFIL_VEHICULO` → tus entidades
   - `DEPENDENCIA_TO_DIRECCION_GRAL` → tus mappings
   - Defectos/anomalías específicas de tu caso de uso

2. **Integrar con pipeline de ETL**: 
   - Cargar CSVs sintéticos
   - Ejecutar tu pipeline de validación
   - Medir si detecta defectos/anomalías

3. **Medir precisión**:
   - Defectos inyectados vs defectos detectados
   - Anomalías inyectadas vs anomalías reportadas
   - Calcular precision/recall del pipeline

4. **Documentar resultados** en tu tesis

---

**Preparado por**: Sistema de Auditoría Sintética  
**Basado en**: Experiencia del proyecto PRESENTACION-Auditoria (v5 + v7)  
**Fecha**: 2026-09-09
