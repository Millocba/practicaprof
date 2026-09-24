# Estrategia de Inyección de Defectos - Generator v5

## Visión General

El generador v5 inyecta defectos **intencionalmente replicando** lo que el pipeline de normalización (`src/config/normalizacion.py`, `src/config/comparador.py`) valida y corrige.

Cada defecto inyectado es **registrado en `ground_truth.csv`** con:
- Tabla y columna donde se inyectó
- Tipo de defecto (categoría)
- Severidad (baja/media/alta)
- Descripción del problema
- Valor original vs. valor inyectado

---

## 5 Categorías de Defectos

### 1. TEXT_NORMALIZATION (8% de inyección)
**Lo que corrige el pipeline:** `norm_text()` en `normalizacion.py`

```python
def norm_text(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.upper()
        .str.strip()
        .str.replace(" ", "", regex=False)      # Quita espacios
        .str.replace("-", "", regex=False)       # Quita guiones
        .str.replace(".", "", regex=False)       # Quita puntos
        .str.replace("/", "", regex=False)       # Quita slashes
    )
```

**Defectos inyectados:**
- **Espacios extras**: `"AB 123 CD"` en dominio (pipeline quita espacios)
- **Puntuación**: `"AB.123CD"` (pipeline quita puntos)
- **Guiones**: `"AB-123CD"` (pipeline quita guiones)
- **Minúsculas**: `"ab123cd"` (pipeline convierte a upper)

**Columnas afectadas:**
- `vehiculo.Dominio` (XX###XX con defectos)
- `dispositivo.Placa` (referencia a dominio con defectos)
- `Solicitante` en solicitud (nombres con espacios extra)

---

### 2. NUMERIC_FORMAT (5% de inyección)
**Lo que corrige el pipeline:** `norm_dni()` y `norm_matricula()` en `comparador.py`

```python
def norm_dni(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.replace(r"\D", "", regex=True)  # Quita todo no-numérico
    out = out.replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    return out

def norm_matricula(s: pd.Series) -> pd.Series:
    out = (
        s.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)  # Quita todo no-numérico
    )
    return out
```

**Defectos inyectados:**
- **DNI con espacios**: `"12 345 678"` → pipeline extrae `"12345678"`
- **DNI con guiones**: `"12-345-678"` → pipeline extrae `"12345678"`
- **DNI con prefijo**: `"DNI12345678"` → pipeline extrae `"12345678"`
- **Matrícula con decimales**: `"10375.0"` → pipeline limpia a `"10375"`

**Columnas afectadas:**
- `vehiculo.RetiraDni`
- `reporte_consumo.NRO IDENTIFICACION CONDUCTOR`
- `solicitud_combustible.Id` (si viene malformado)

---

### 3. DATE_FORMAT (4% de inyección)
**Lo que corrige el pipeline:** `to_datetime(errors="coerce", dayfirst=True)` en `validadores.py`

```python
def to_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def parse_period_from_date_series(s: pd.Series, *, df_name: str) -> tuple[int, int]:
    """Valida que todas las fechas sean del mismo mes/año"""
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if dt.isna().all():
        raise ValidationError(f"[{df_name}] No pude parsear fechas.")
    periods = dt.dropna().dt.to_period("M").unique()
    if len(periods) != 1:
        raise ValidationError(f"[{df_name}] Múltiples meses: {periods}. Un archivo = un mes.")
```

**Defectos inyectados:**
- **Formato YYYY/MM/DD** (en lugar de DD/MM/YYYY): `"2026/08/15"` → pipeline parsea como `dayfirst=True`
- **Fecha inválida**: `"31/02/2026"` → pipeline marca como `NaT`
- **Separadores inconsistentes**: `"15-08-2026"` en lugar de `"/"`
- **Formatos mixtos**: Algunos `"15/08/2026"`, otros `"2026-08-15"`

**Columnas afectadas:**
- `reporte_consumo.FECHA`
- `solicitud_combustible.Fecha`
- `solicitud_combustible.FechaRendicion`
- `vehiculo.FechaHastaExcepcionOdometro`

---

### 4. MATCHING_DEFECTS (6% de inyección)
**Lo que valida el pipeline:** Comparación entre fuentes (YPF/RIG, flota/telemetría)

```python
def _outer_compare(left: pd.DataFrame, right: pd.DataFrame, on: list[str]) -> pd.DataFrame:
    return left.merge(right, how="outer", on=on, suffixes=("_YPF", "_RIG"), indicator=True)
    # Genera: "both", "left_only", "right_only"

def _estado_merge(merge_val: str, dif_litros: float | None, tol: float) -> str:
    if merge_val == "left_only": return "SOLO_YPF"
    if merge_val == "right_only": return "SOLO_RIG"
    if dif_litros is None: return "DESACUERDO"
    return "COINCIDENCIA" if abs(dif_litros) <= tol else "DESACUERDO"
```

**Defectos inyectados:**
- **Dominios duplicados**: Reutilizar dominio en múltiples vehículos → detecta inconsistencias
- **Discrepancias en litros**: `reporte_consumo` reporta 50L pero `solicitud_combustible` carga 75L → genera estado `"DESACUERDO"`
- **Dominios en solicitud sin match en vehiculo**: Crea `"SOLO_RIG"` (requiere fallback a matrícula)
- **Matricula missing**: Referencias rotas entre tablas

**Columnas afectadas:**
- `vehiculo.Dominio` (duplicados intencionales)
- `reporte_consumo.LITROS UNIDADES` (discrepancias 50-150% del valor)
- `solicitud_combustible.Dominio` (no matches en vehiculo)
- `solicitud_combustible.LitrosCargados` vs `LitrosAutorizados`

---

### 5. CONSISTENCY_ERRORS (3% de inyección)
**Lo que valida el pipeline:** Lógica transaccional

**Defectos inyectados:**
- **Litros cargados > autorizados**: `LitrosAutorizados=100` pero `LitrosCargados=115` → cumplimiento incorrecto
- **Odómetro regresivo**: No implementado pero identificable (regresión entre transacciones)
- **Fecha rendición anterior a fecha solicitud**: Inconsistencia temporal

**Columnas afectadas:**
- `solicitud_combustible.LitrosCargados` (> LitrosAutorizados en 3% de casos)

---

## Tasas de Inyección por Defecto

```yaml
text_normalization_rate: 0.08        # 8% de registros
numeric_format_rate: 0.05            # 5% de registros
date_format_rate: 0.04               # 4% de registros
matching_defect_rate: 0.06           # 6% de registros
consistency_error_rate: 0.03         # 3% de registros
```

**Cobertura esperada:** ~20-25% de registros tienen al menos 1 defecto

---

## Ground Truth Registry

Cada defecto es registrado en `ground_truth.csv`:

```csv
row_id,table,column,defect_type,severity,description,original_value,injected_value
vehiculo_000042,vehiculo,Dominio,TEXT_NORMALIZATION,baja,Extra spaces in domain,AB123CD,"AB 123 CD"
vehiculo_000115,vehiculo,RetiraDni,NUMERIC_FORMAT,baja,Spaces in DNI,12345678,"12 345 678"
reporte_consumo_000087,reporte_consumo,FECHA,DATE_FORMAT,media,Wrong date format (YYYY/MM/DD),15/08/2026,2026/08/15
solicitud_combustible_000312,solicitud_combustible,LitrosCargados,CONSISTENCY_ERROR,media,Liters charged exceed authorized,100,115
```

**Campos:**
- `row_id`: ID único del registro (ej: `vehiculo_000042`)
- `table`: Tabla donde se inyectó (`vehiculo`, `dispositivo`, `reporte_consumo`, `solicitud_combustible`)
- `column`: Columna específica
- `defect_type`: Categoría del defecto (uno de los 5 tipos)
- `severity`: `baja` (2-3 puntos), `media` (5-10 puntos), `alta` (20+ puntos)
- `description`: Explicación human-readable del defecto
- `original_value`: Valor sin defecto
- `injected_value`: Valor con defecto

---

## Alineación con Pipeline

### `normalizacion.py` → TEXT_NORMALIZATION defects
Pipeline function: `norm_text()`
- Quita espacios, puntuación, case-normaliza
- Defectos inyectados reflejan exactamente lo que esta función corrige

### `comparador.py` → NUMERIC_FORMAT defects
Pipeline functions: `norm_dni()`, `norm_matricula()`
- Extrae dígitos, quita caracteres no-numéricos
- Defectos inyectados son exactamente lo que estas funciones limpian

### `validators.py` → DATE_FORMAT defects
Pipeline function: `to_datetime(errors="coerce", dayfirst=True)`
- Parsea fechas con múltiples formatos
- Valida período único por archivo
- Defectos inyectados son formatos que el parser debe manejar

### `comparador.py` → MATCHING_DEFECT defects
Pipeline functions: `_outer_compare()`, `_estado_merge()`, `_apply_flota_fallback()`
- Compara YPF vs RIG por DNI y dominio
- Tolera discrepancias en litros (tol_litros_ok)
- Mapea dominio → matrícula vía flota
- Defectos inyectados generan estados: `SOLO_YPF`, `SOLO_RIG`, `DESACUERDO`

### Cross-table validation → CONSISTENCY_ERROR defects
Pipeline function: `_compute_dni_comparison()`, `_compute_dom_comparison()`
- Valida que litros cargados ≤ autorizados (tolerancia)
- Detecta transacciones sin match
- Defectos inyectados violan estas reglas lógicas

---

## Cómo Usar Ground Truth

### Para EDA/Análisis:
```python
gt = pd.read_csv('ground_truth.csv')

# ¿Qué defectos hay en vehiculo?
gt[gt['table'] == 'vehiculo'].groupby('defect_type').size()

# ¿Cuántos dominios tienen espacios?
gt[(gt['table'] == 'vehiculo') & (gt['column'] == 'Dominio')].shape[0]

# ¿Todos los defectos de media/alta severidad?
gt[gt['severity'].isin(['media', 'alta'])]
```

### Para Pipeline Testing:
```python
# Verificar que el pipeline normaliza cada defecto
for _, row in gt.iterrows():
    original = row['original_value']
    injected = row['injected_value']
    
    # El pipeline debería convertir injected → original
    normalized = pipeline_normalize(row['table'], row['column'], injected)
    assert normalized == original, f"Pipeline didn't fix {row['row_id']}"
```

### Para Validation Reports:
```python
# Reporte de éxito del pipeline
success = 0
for _, row in gt.iterrows():
    normalized = pipeline_normalize(row['table'], row['column'], row['injected_value'])
    if normalized == row['original_value']:
        success += 1

print(f"Pipeline fixed {success}/{len(gt)} defects ({100*success/len(gt):.1f}%)")
```

---

## Resumen

| Categoría | Tasa | Ejemplo | Pipeline Aligns |
|-----------|------|---------|-----------------|
| TEXT_NORMALIZATION | 8% | `"AB 123 CD"` → `norm_text()` | ✓ `norm_text()` |
| NUMERIC_FORMAT | 5% | `"DNI12345678"` → `norm_dni()` | ✓ `norm_dni()` |
| DATE_FORMAT | 4% | `"2026/08/15"` → `to_datetime()` | ✓ `to_datetime(dayfirst=True)` |
| MATCHING_DEFECT | 6% | Dominio duplicado → `_outer_compare()` | ✓ Matching logic |
| CONSISTENCY_ERROR | 3% | `LitrosCargados > Autorizados` | ✓ Validation rules |

**Total coverage: ~20-25% de registros tienen defectos**

Cada defecto es **identificable, registrable y verificable** contra el pipeline.
