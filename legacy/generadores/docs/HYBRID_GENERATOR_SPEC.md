# Especificación: Generador Sintético Híbrido v7.5
## Integración de Defectos (v5) + Anomalías (v7)

**Fecha**: 2026-09-09  
**Proyecto**: Prácticas Profesionalizantes  
**Origen**: Lecciones del Proyecto PRESENTACION-Auditoria (v5 + v7)

---

## 📋 Resumen Ejecutivo

El generador híbrido v7.5 produce **datos sintéticos reproducibles** que combinan:
- **Datos base realistas** (v7): vehículos con perfiles coherentes, transmisión de telemetría 7-día, mappings organizacionales reales
- **Defectos normalizables** (v5): 5 categorías que el pipeline ETL debe **limpiar/normalizar**
- **Anomalías detectables** (v7): 13 categorías que el motor de auditoría debe **identificar y reportar**

**Resultado**: ~30-40% de datos con al menos un defecto o anomalía, con **ground truth dual auditable**.

---

## 🏗️ Arquitectura

### Componentes

```
generator_v7_5_hybrid.py
├── GenerationConfig          # Configuración de tasas
├── Real Mappings (v7)        # DEPENDENCIA_TO_DIRECCION_GRAL, PERFIL_VEHICULO, CONTRATOS
├── Registries (Ground Truth) # DefectRecord + AnomalyRecord dataclasses
├── Generation Functions      # generate_vehiculo_base(), generate_dispositivo_base()
├── Injection Functions       # inject_v5_defects(), inject_v7_anomalies()
└── Main API                  # generate_dataset(config) → Dataset Dict
```

### Salida: Dataset Dict

```python
{
  'vehiculo': DataFrame        # 200 vehículos con defectos inyectados
  'dispositivo': DataFrame     # ~170 dispositivos con anomalías inyectadas
  'defects': DataFrame         # Ground truth v5 (50-60 registros)
  'anomalies': DataFrame       # Ground truth v7 (30-40 registros)
  'ground_truth': DataFrame    # Merge de ambos para análisis combinado
}
```

---

## 🔧 Defectos v5 (Normalizables)

El pipeline ETL **DEBE poder limpiar/normalizar** estos defectos.

### 1. TEXT_NORMALIZATION (8%)
**Qué es**: Dominio con espacios, puntuación o caracteres no estándar  
**Ejemplo**: `"AB 123 CD"` (con espacios) → debería ser `"AB123CD"`  
**Tasa**: 8% de vehículos afectados  
**Detección**: Expresión regular `[^A-Z0-9]`  
**Normalización**: `re.sub(r'[^A-Z0-9]', '', valor)`

### 2. NUMERIC_FORMAT (5%)
**Qué es**: Número con formato no estándar (DNI con puntos/guiones)  
**Ejemplo**: `"12.345.678"` → debería ser `"12345678"`  
**Tasa**: 5% de vehículos  
**Detección**: Buscar caracteres especiales en campos numéricos  
**Normalización**: Remover puntos, guiones, espacios

### 3. DATE_FORMAT (4%)
**Qué es**: Fecha en formato no esperado  
**Ejemplo**: `"31/12/2025"` en campo que espera `"YYYY-MM-DD"`  
**Tasa**: 4% de fechas de transmisión  
**Detección**: Parse fallido con strptime(fmt_esperado)  
**Normalización**: Re-parsear con formato detectable y reformatear

### 4. MATCHING_DEFECT (6%)
**Qué es**: Dominio duplicado en múltiples vehículos (FK constraint violation)  
**Ejemplo**: Dos vehículos con Dominio="AA123BB"  
**Tasa**: 6% de vehículos (2-3 pares duplicados en dataset de 200)  
**Detección**: `df.Dominio.nunique() < len(df)`  
**Resolución**: Identificar registro incorrecto y reasignarlo

### 5. CONSISTENCY_ERROR (3%)
**Qué es**: Datos inconsistentes entre campos (ej: capacidad < consumo esperado)  
**Ejemplo**: Vehículo CAMIÓN con CapacidadTanque=50L pero RelacionConsumo=0.2 km/L (insostenible)  
**Tasa**: 3% de vehículos  
**Detección**: Lógica de negocio (rango válido por tipo)  
**Resolución**: Ajustar valor a rango coherente

---

## ⚠️ Anomalías v7 (Detectables)

El motor de auditoría **DEBE poder reportar** estas anomalías.

### 1. DUPLICADO (4%)
**Qué es**: Valor repetido en campo único  
**Ejemplos**:
- Matricula duplicada en vehículos
- IMEI duplicada en dispositivos
- Alias duplicado

**Tasa**: 4% de registros afectados  
**Detección**: `df[col].value_counts() > 1`  
**Reporte**: "Matricula XX123YY aparece en vehículos IDs 101 y 102"

### 2. FALTANTE (3%)
**Qué es**: Campo requerido está vacío  
**Ejemplos**:
- Dominio vacío
- MSISDN ausente
- Hora de última transmisión faltante

**Tasa**: 3% de registros  
**Detección**: `df[col].isna() | (df[col] == "")`  
**Reporte**: "Fila 105: Dominio está vacío"

### 3. INVALIDO (3%)
**Qué es**: Valor no cumple formato esperado  
**Ejemplos**:
- Dominio="S/D" (sin datos)
- IMEI no es número
- Estado de transmisión="Desconocido" (no en lista válida)

**Tasa**: 3% de registros  
**Detección**: Validación contra esquema/enum  
**Reporte**: "Fila 87: Dominio='S/D' no es dominio válido"

### 4. SIN_NUMERO (2%)
**Qué es**: Alias o identificador no tiene mapping a número conocido  
**Ejemplo**: Dispositivo con Alias="UNKNOWN_123" que no existe en tabla de dispositivos  
**Tasa**: 2% de dispositivos  
**Detección**: Cruce Flota↔Telemetría falla (LEFT JOIN sin match)  
**Reporte**: "Dispositivo Alias=UNKNOWN_123 no tiene vehículo asociado"

### 5. DUPLICIDAD_EQUIPO (2%)
**Qué es**: Un vehículo con múltiples dispositivos del mismo tipo o vehículo sin dispositivo  
**Ejemplo**: Vehículo ID=101 tiene 2 dispositivos pero el cruce detecta 3  
**Tasa**: 2% de vehículos  
**Detección**: Contar dispositivos por vehículo  
**Reporte**: "Vehículo ID=101 (Dominio=XX123YY) tiene discrepancia en conteo de dispositivos"

---

## 🎯 Configuración de Tasas

```python
config = GenerationConfig(
    num_vehicles=200,
    num_devices_per_vehicle=0.85,
    seed=20260909,
    
    # Defects (v5)
    text_normalization_rate=0.08,      # 8%
    numeric_format_rate=0.05,          # 5%
    date_format_rate=0.04,             # 4%
    matching_defect_rate=0.06,         # 6%
    consistency_error_rate=0.03,       # 3%
    
    # Anomalies (v7)
    duplicate_rate=0.04,               # 4%
    missing_value_rate=0.03,           # 3%
    invalid_format_rate=0.03,          # 3%
    unknown_number_rate=0.02,          # 2%
)

dataset = generate_dataset(config)
```

**Tasas Totales Esperadas**:
- ~25-30% de vehículos con al menos 1 defecto
- ~15-20% de dispositivos con al menos 1 anomalía
- ~35-40% de datos "problemáticos" en total

---

## 📊 Ground Truth: Estructura de Registros

### DefectRecord (v5)
```python
{
    'tabla': 'vehiculo',
    'fila': 10025,
    'columna': 'Dominio',
    'tipo': 'TEXT_NORMALIZATION',
    'severidad': 'media',
    'descripcion': 'Dominio contiene espacios/puntuación',
    'valor_original': 'AA 123 BB',
    'valor_inyectado': 'AA123BB'  # Lo que está en el CSV
}
```

### AnomalyRecord (v7)
```python
{
    'tabla': 'dispositivo',
    'fila': 43,
    'columna': 'IMEI',
    'tipo': 'DUPLICADO',
    'severidad': 'alta',
    'descripcion': 'IMEI 123456789012345 duplicada en dispositivos',
    'valor_original': '123456789012345',
    'valor_inyectado': '123456789012345'  # Mismo valor, pero duplicado
}
```

### Ground Truth Merge
```python
ground_truth_df = pd.concat([defects_df, anomalies_df])
# Columnas comunes: tabla, fila, columna, tipo, severidad, descripcion
# Uso: comparar "detectadas" vs "inyectadas" para medir precisión del pipeline
```

---

## 🚀 Integración: Próximos Pasos

### Paso 3.1: Copiar a Repositorio
```bash
mkdir -p tu_proyecto/generators/hybrid_v7_5
cp generator_v7_5_hybrid.py tu_proyecto/generators/hybrid_v7_5/
cp HYBRID_GENERATOR_SPEC.md tu_proyecto/generators/hybrid_v7_5/
```

### Paso 3.2: Crear Script de Uso
```python
# tu_proyecto/scripts/generate_synthetic_data.py
from generators.hybrid_v7_5.generator_v7_5_hybrid import generate_dataset, GenerationConfig

config = GenerationConfig(
    num_vehicles=1000,
    seed=20260909
)

dataset = generate_dataset(config)
dataset['vehiculo'].to_csv('data/vehiculos_synthetic.csv', index=False)
dataset['dispositivo'].to_csv('data/dispositivos_synthetic.csv', index=False)
dataset['ground_truth'].to_csv('data/ground_truth.csv', index=False)
```

### Paso 4.1: Crear Test Suite
```bash
tu_proyecto/tests/test_synthetic_data.py
  - test_vehicles_valid_schema()
  - test_devices_link_to_vehicles()
  - test_defects_injection()
  - test_anomalies_injection()
  - test_ground_truth_audit()
```

### Paso 4.2: Crear CI Pipeline (GitHub Actions / GitLab CI)
```yaml
name: Synthetic Data Validation
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Generate synthetic data
        run: python scripts/generate_synthetic_data.py
      - name: Validate schema
        run: python -m pytest tests/test_synthetic_data.py
      - name: Measure defects/anomalies
        run: python scripts/measure_injection_rates.py
```

---

## 📋 Métricas de Validación

Una vez integrado, medir:

| Métrica | Objetivo | Cómo Medir |
|---------|----------|-----------|
| **Reproducibilidad** | Mismo seed → mismo dataset | `dataset1 = generate_dataset(config); dataset2 = generate_dataset(config); assert dataset1.equals(dataset2)` |
| **Tasa de defectos** | ~25-30% de vehículos | `len(defects_df) / len(vehiculos_df)` |
| **Tasa de anomalías** | ~15-20% de dispositivos | `len(anomalies_df) / len(dispositivos_df)` |
| **Ground truth completo** | Defects + Anomalies auditables | `ground_truth_df.notna().all()` |
| **Validez de datos base** | Datos no defectuosos son válidos | Ejecutar pipeline de validación |

---

## 🔗 Referencias

- **v5 Analysis**: `claude/GENERADOR_V5_DEFECTS_AWARE.md` (Prácticas Profesionalizantes)
- **v7 Source**: `D:/presentacion/PRESENTACION-Auditoria/scripts/db_etl/generator_v7_telemetry_states.py`
- **v7 Analysis**: `ANALISIS_GENERADOR_V7_REUTILIZABLE.md` (creado 2026-09-09)

---

**Documento Preparado**: 2026-09-09  
**Estado**: Listo para Integración
