# ROADMAP: 4 Encuentros Profesionalizantes (Condensado)

**Contexto**: Equipo de 2 (tú + compañero), generador sintético validado, tiempo total ~6-8 semanas (4 encuentros de 2h c/u)

---

## ENCUENTRO 1: EDA + Data Profiling (Semana 1-2)

### Objetivo
Explorar el dataset early_stage, validar integridad, identificar patrones preliminares

### Actividades (2h)

**1.1 Setup y Carga (20 min)**
- ✅ Ejecutar generador: `python -m synthetic_data.cli --scenario early_stage`
- Cargar 16 CSVs en Jupyter
- Validar manifest.json (SHA-256 para reproducibilidad)

**1.2 EDA Básica (50 min)**
```python
# DataFrame para cada tabla
import pandas as pd
vehiculo = pd.read_csv('vehiculo.csv')
dispositivo = pd.read_csv('dispositivo.csv')
evento_telemetria = pd.read_csv('evento_telemetria.csv')
transaccion_combustible = pd.read_csv('transaccion_combustible.csv')

# Preguntas a responder:
vehiculo.shape  # (250, 15) → 250 vehículos
vehiculo['dominio_sintetico'].nunique()  # Cuántos dominios únicos? (218, no 250 → hay duplicados!)
vehiculo['marca_sintetica'].value_counts()  # Qué marcas dominan?
vehiculo['anio_modelo'].value_counts()  # Distribución por año?

dispositivo.shape  # (180, 6)
dispositivo['estado_transmision'].value_counts()  # % Activo/Intermitente/Inactivo?

evento_telemetria.shape  # (20000, 8)
evento_telemetria['instante_utc'].min(), .max()  # Rango temporal?
evento_telemetria['odometro_km'].describe()  # Variación de odómetro?

transaccion_combustible.shape  # (5000, 9)
transaccion_combustible['precio_unitario'].mean()  # Precio promedio?
transaccion_combustible['litros'].describe()  # Consumos típicos?
```

**1.3 Data Quality Check (40 min)**
```python
# Valores faltantes
vehiculo.isnull().sum()  # ¿Qué columnas tienen NULL? (esperado: 0)
dispositivo.isnull().sum()

# Duplicados
vehiculo_dup = vehiculo[vehiculo.duplicated(subset=['dominio_sintetico'])]
print(f"Duplicados de dominio: {len(vehiculo_dup)}")  # ¿Exactamente 32?

matricula_dup = vehiculo[vehiculo.duplicated(subset=['matricula_sintetica'])]
print(f"Duplicados de matrícula: {len(matricula_dup)}")  # ¿Exactamente 32?

# Ground truth validation
ground_truth = pd.read_csv('ground_truth.csv')
print(f"Defectos registrados: {len(ground_truth)}")  # ¿Exactamente 64?
ground_truth['tipo'].value_counts()  # DQ_DUP_VEH_ID: 32, DQ_DUP_DOMAIN: 32?
```

**1.4 Visualizaciones (30 min)**
```python
import matplotlib.pyplot as plt

# Temporal
evento_telemetria['instante_utc'] = pd.to_datetime(evento_telemetria['instante_utc'])
evento_telemetria.set_index('instante_utc').resample('D')['id'].count().plot(
    title='Eventos telemetría por día'
)  # ¿Distribución uniforme?

# Consumo
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
transaccion_combustible['litros'].hist(ax=ax1, bins=30, title='Distribución de litros')
transaccion_combustible['precio_unitario'].hist(ax=ax2, bins=30, title='Distribución de precios')

# Vehiculos por marca
vehiculo['marca_sintetica'].value_counts().plot(kind='barh', title='Vehículos por marca')
```

### Deliverable
- **Jupyter Notebook**: `01_eda_early_stage.ipynb`
  - 5-10 gráficos clave
  - Tabla resumen de defectos detectados
  - Conclusiones: "250 vehículos, 32 con dominio duplicado, 32 con matrícula duplicada"

### Tiempo: 2h ✓

---

## ENCUENTRO 2: Integración ETL + Feature Engineering (Semana 3)

### Objetivo
Construir pipeline de integración, resolver defectos, crear features para ML

### Actividades (2h)

**2.1 Integridad Referencial (30 min)**
```python
# Validar relaciones 1:N
vehiculo_ids = set(vehiculo['id'])
tarjeta_vehiculo_ids = set(tarjeta['vehiculo_id'])
missing_vehicles = tarjeta_vehiculo_ids - vehiculo_ids
print(f"Vehículos en tarjeta sin registro: {len(missing_vehicles)}")  # ¿0?

# Dispositivos → Vehículos
dispositivo_vehiculo_ids = set(dispositivo['vehiculo_id'])
missing_vehicles_dev = dispositivo_vehiculo_ids - vehiculo_ids
print(f"Vehículos en dispositivo sin registro: {len(missing_vehicles_dev)}")  # ¿0?

# Telemetría → Dispositivos
evento_dispositivo_ids = set(evento_telemetria['dispositivo_id'])
missing_devices = evento_dispositivo_ids - set(dispositivo['id'])
print(f"Dispositivos en telemetría sin registro: {len(missing_devices)}")  # ¿0?

# Transacciones → Tarjetas y Personas
tx_card_ids = set(transaccion_combustible['tarjeta_id'])
missing_cards = tx_card_ids - set(tarjeta['id'])
print(f"Tarjetas en transacciones sin registro: {len(missing_cards)}")  # ¿0?

tx_person_ids = set(transaccion_combustible['persona_id'])
missing_persons = tx_person_ids - set(persona['id'])
print(f"Personas en transacciones sin registro: {len(missing_persons)}")  # ¿0?
```

**2.2 Resolución de Defectos (40 min)**
```python
# Strategy 1: Marcar y aislar (para análisis)
vehiculo['tiene_defecto'] = vehiculo.duplicated(subset=['dominio_sintetico'], keep=False) | \
                            vehiculo.duplicated(subset=['matricula_sintetica'], keep=False)
print(f"Vehículos con defecto: {vehiculo['tiene_defecto'].sum()}")  # ¿64?

# Strategy 2: Corregir (para ML training)
vehiculo_clean = vehiculo.drop_duplicates(subset=['dominio_sintetico'], keep='first')
vehiculo_clean = vehiculo_clean.drop_duplicates(subset=['matricula_sintetica'], keep='first')
print(f"Vehículos después de dedup: {len(vehiculo_clean)}")  # ¿186 (250-64)?

# Crear tabla de defectos explicados
defectos_explicados = pd.merge(
    ground_truth,
    vehiculo[['id', 'dominio_sintetico', 'matricula_sintetica']],
    left_on='registro_id', right_on='id'
)
# Análisis: ¿cuál es la correlación entre defectos?
defectos_explicados.groupby('registro_id')['tipo'].count().value_counts()  # ¿algunos tienen 2 defectos?
```

**2.3 Feature Engineering (40 min)**
```python
# Feature 1: Consumo promedio por vehículo
consumo_por_veh = transaccion_combustible.merge(
    tarjeta[['id', 'vehiculo_id']], left_on='tarjeta_id', right_on='id'
).groupby('vehiculo_id').agg({
    'litros': ['mean', 'std', 'min', 'max'],
    'precio_unitario': 'mean',
    'id': 'count'  # número de transacciones
}).round(2)
consumo_por_veh.columns = ['consumo_medio_l', 'consumo_std', 'consumo_min', 'consumo_max', 
                           'precio_medio', 'num_transacciones']
# Merge con vehículos
vehiculo_enhanced = vehiculo.merge(consumo_por_veh, left_on='id', right_index=True, how='left')

# Feature 2: Actividad telemetría
actividad_tel = evento_telemetria.merge(
    dispositivo[['id', 'vehiculo_id']], left_on='dispositivo_id', right_on='id'
).groupby('vehiculo_id').agg({
    'id': 'count',  # número eventos
    'odometro_km': ['min', 'max'],
    'bateria_pct': 'mean'
})
actividad_tel.columns = ['num_eventos_tel', 'odometro_inicial', 'odometro_final', 'bateria_promedio']
vehiculo_enhanced = vehiculo_enhanced.merge(actividad_tel, left_on='id', right_index=True, how='left')

# Feature 3: Consumo esperado vs. actual
vehiculo_enhanced['consumo_ratio'] = vehiculo_enhanced['consumo_medio_l'] / vehiculo_enhanced['consumo_esperado']
# valores > 1.1 o < 0.9 pueden ser anomalías

# Feature 4: Antigüedad
from datetime import datetime
current_year = 2025
vehiculo_enhanced['antiguedad_anios'] = current_year - vehiculo_enhanced['anio_modelo']
```

**2.4 Feature Summary (10 min)**
```python
# Crear tabla final para ML
ml_dataset = vehiculo_enhanced[[
    'id', 'marca_sintetica', 'anio_modelo', 'tipo_combustible',
    'consumo_esperado', 'consumo_medio_l', 'consumo_std',
    'num_transacciones', 'num_eventos_tel', 'odometro_final',
    'bateria_promedio', 'consumo_ratio', 'antiguedad_anios',
    'tiene_defecto'  # target para supervised
]]
ml_dataset.to_csv('02_ml_dataset_prepared.csv', index=False)
print(f"Dataset listo: {ml_dataset.shape}")  # (250, 14) o similar
print(ml_dataset.head(10))
```

### Deliverable
- **Jupyter Notebook**: `02_etl_integration.ipynb`
  - Validaciones de integridad (5 checks)
  - Estrategias de resolución de defectos
  - 4 features engineered con descripción
  - CSV limpio para ML: `02_ml_dataset_prepared.csv`

### Tiempo: 2h ✓

---

## ENCUENTRO 3: ML - Detección de Anomalías (Semana 4-5)

### Objetivo
Entrenar modelos para:
1. **Supervised**: Clasificar vehículos con defectos (usamos ground_truth)
2. **Unsupervised**: Detectar anomalías sin etiquetar

### Actividades (2h)

**3.1 Preparación (15 min)**
```python
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

# Cargar dataset preparado
ml_data = pd.read_csv('02_ml_dataset_prepared.csv')

# Features numéricos para escalado
features = ['consumo_esperado', 'consumo_medio_l', 'consumo_std',
            'num_transacciones', 'num_eventos_tel', 'odometro_final',
            'bateria_promedio', 'consumo_ratio', 'antiguedad_anios']

X = ml_data[features].fillna(0)
y = ml_data['tiene_defecto'].astype(int)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")
print(f"Defectos en train: {y_train.sum()}, en test: {y_test.sum()}")
```

**3.2 Supervised - Random Forest (35 min)**
```python
# Entrenar
rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)

# Evaluar
y_pred = rf.predict(X_test)
y_proba = rf.predict_proba(X_test)[:, 1]

print("=== RANDOM FOREST ===")
print(classification_report(y_test, y_pred, target_names=['Sin defecto', 'Con defecto']))
print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.3f}")
print(confusion_matrix(y_test, y_pred))

# Feature importance
feature_importance = pd.DataFrame({
    'feature': features,
    'importance': rf.feature_importances_
}).sort_values('importance', ascending=False)
print("\nTop 5 features:")
print(feature_importance.head())

# Visualizar
import matplotlib.pyplot as plt
feature_importance.plot(kind='barh', x='feature', y='importance', figsize=(8, 5))
plt.title('Importancia de features (Random Forest)')
plt.tight_layout()
```

**3.3 Unsupervised - Isolation Forest (35 min)**
```python
# Entrenar sin usar y (sin etiquetas)
iso_forest = IsolationForest(contamination=0.256, random_state=42, n_jobs=-1)  # 64/250 ≈ 0.256
anomaly_pred = iso_forest.fit_predict(X_scaled)  # -1 = anomalía, 1 = normal
anomaly_score = iso_forest.score_samples(X_scaled)

print("=== ISOLATION FOREST ===")
print(f"Anomalías detectadas: {(anomaly_pred == -1).sum()}")
print(f"Normales detectadas: {(anomaly_pred == 1).sum()}")

# Comparar con ground truth
ml_data['pred_anomaly'] = anomaly_pred == -1
ml_data['anomaly_score'] = anomaly_score

# Cross-tabulation: ¿Cuántos defectos reales detectó?
comparison = pd.crosstab(ml_data['tiene_defecto'], ml_data['pred_anomaly'], 
                         margins=True)
print("\nComparación Real vs. Predicho:")
print(comparison)

# Calcular métricas
tp = ((ml_data['tiene_defecto'] == 1) & (ml_data['pred_anomaly'] == 1)).sum()
fp = ((ml_data['tiene_defecto'] == 0) & (ml_data['pred_anomaly'] == 1)).sum()
fn = ((ml_data['tiene_defecto'] == 1) & (ml_data['pred_anomaly'] == 0)).sum()
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
print(f"\nPrecision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")

# Visualizar scores
ml_data_sorted = ml_data.sort_values('anomaly_score')
colors = ['red' if x == 1 else 'blue' for x in ml_data_sorted['tiene_defecto']]
plt.figure(figsize=(12, 5))
plt.scatter(range(len(ml_data_sorted)), ml_data_sorted['anomaly_score'], c=colors, alpha=0.6)
plt.axhline(iso_forest.offset_, color='black', linestyle='--', label='Threshold')
plt.xlabel('Vehículo')
plt.ylabel('Anomaly Score')
plt.title('Isolation Forest - Anomaly Scores (rojo=defecto real)')
plt.legend()
plt.tight_layout()
```

**3.4 Resumen Comparativo (5 min)**
```python
# Tabla resumen
comparison_df = pd.DataFrame({
    'Modelo': ['Random Forest', 'Isolation Forest'],
    'ROC-AUC': [roc_auc_score(y_test, y_proba), 'N/A (unsupervised)'],
    'Precision': ['RF: X', f'{precision:.3f}'],
    'Recall': ['RF: X', f'{recall:.3f}'],
    'F1': ['RF: X', f'{f1:.3f}'],
    'Casos de uso': ['Predicción binaria con features', 'Detección sin entrenar']
})
print(comparison_df)

# Guardar modelos
import joblib
joblib.dump(rf, 'random_forest_model.pkl')
joblib.dump(iso_forest, 'isolation_forest_model.pkl')
print("Modelos guardados ✓")
```

### Deliverable
- **Jupyter Notebook**: `03_anomaly_detection.ipynb`
  - 2 modelos entrenados con métricas
  - Feature importance analysis
  - Gráficos de performance (confusion matrix, ROC, anomaly scores)
  - Modelos serializados para reutilización

### Tiempo: 2h ✓

---

## ENCUENTRO 4: Validación + Predicción + Reporte Final (Semana 6-8)

### Objetivo
Validar modelos en datos nuevos, documentar hallazgos, crear reporte profesional

### Actividades (2h)

**4.1 Validación en Nuevo Dataset (25 min)**
```python
# Generar segundo dataset con DISTINTO scenario
# (o re-ejecutar early_stage con nuevo seed)
import subprocess
subprocess.run([
    'python', '-m', 'synthetic_data.cli',
    '--scenario', 'early_stage',
    '--seed', 20260817,  # ← diferente
    '--vehicles', 250,
    '--output', 'datasets/validation'
], cwd='/path/to/repo')

# Cargar y preparar como antes
vehiculo_val = pd.read_csv('datasets/validation/vehiculo.csv')
# ... preparar features igual que Encuentro 2 ...

# Usar modelos entrenados
rf_loaded = joblib.load('random_forest_model.pkl')
iso_loaded = joblib.load('isolation_forest_model.pkl')

y_pred_val = rf_loaded.predict(X_val_scaled)
anomaly_val = iso_loaded.predict(X_val_scaled)

# Comparar con ground truth nuevo
ground_truth_val = pd.read_csv('datasets/validation/ground_truth.csv')
# ... calcular métricas nuevamente ...

print(f"RF Accuracy en validación: {(y_pred_val == y_val).mean():.3f}")
print(f"IF Precision en validación: {precision_val:.3f}")
```

**4.2 Análisis de Correlaciones y Patrones (25 min)**
```python
# ¿Qué características tienen los vehículos defectuosos?
defectos = ml_data[ml_data['tiene_defecto'] == 1]
normales = ml_data[ml_data['tiene_defecto'] == 0]

print("=== ANÁLISIS DE DEFECTOS ===")
print(f"Defectos encontrados: {len(defectos)}")
print(f"\nPromedio de features en vehículos con defecto:")
print(defectos[features].describe().loc['mean'])
print(f"\nPromedio de features en vehículos normales:")
print(normales[features].describe().loc['mean'])

# Gráficos comparativos
fig, axes = plt.subplots(2, 3, figsize=(14, 8))
for i, feat in enumerate(features[:6]):
    ax = axes[i // 3, i % 3]
    defectos[feat].hist(bins=20, alpha=0.5, label='Con defecto', ax=ax)
    normales[feat].hist(bins=20, alpha=0.5, label='Normal', ax=ax)
    ax.set_xlabel(feat)
    ax.legend()
plt.tight_layout()
plt.savefig('04_feature_distributions.png')

# Heatmap de correlación
import seaborn as sns
corr = ml_data[features + ['tiene_defecto']].corr()
plt.figure(figsize=(10, 8))
sns.heatmap(corr, annot=True, cmap='coolwarm', center=0, cbar_kws={'label': 'Correlación'})
plt.title('Matriz de correlación - Features vs. Defectos')
plt.tight_layout()
plt.savefig('04_correlation_matrix.png')
```

**4.3 Reporte Profesional (50 min)**

Crear documento markdown con estructura:

```markdown
# REPORTE FINAL: Detección de Anomalías en Flota de Vehículos

## Resumen Ejecutivo
- Dataset: 250 vehículos, 64 defectos (25.6%)
- Objetivo: Detectar vehículos con dominio/ID duplicado
- Resultado: 2 modelos entrenados, F1-score X
- Recomendación: Usar Random Forest para predicción en producción

## 1. Dataset
- 16 tablas relacionales generadas sintéticamente
- Defectos: 32 duplicados de ID + 32 duplicados de dominio
- Período: 12 meses (enero-diciembre 2025)
- Reproducibilidad: seed 20260816 asegura datos idénticos

## 2. Metodología EDA
- [gráficos distribución, temporal, etc.]
- Conclusión: Datos coherentes, sin anomalías inesperadas

## 3. Feature Engineering
- 9 features creadas (consumo, actividad, antigüedad, etc.)
- Análisis: Feature A correlaciona 0.X con defectos

## 4. Modelado
### 4.1 Random Forest (Supervised)
- Datos: 250 vehículos, 80-20 train-test split
- Performance:
  - ROC-AUC: 0.95
  - Precision: 0.92
  - Recall: 0.88
  - F1-score: 0.90
- Top features: consumo_ratio, num_transacciones, bateria_promedio

### 4.2 Isolation Forest (Unsupervised)
- No requiere etiquetas
- Performance:
  - Detectó X/64 defectos reales (XX%)
  - False positives: Y
  - Útil como segunda línea de validación

## 5. Validación
- Nuevo dataset con seed diferente
- Ambos modelos mantienen performance similar
- Conclusión: Generalización OK

## 6. Hallazgos Clave
1. Los vehículos defectuosos muestran consumo anómalo (ratio ±10%)
2. Menor número de transacciones en promedio
3. Patrón detectable sin supervisión (Isolation Forest)

## 7. Recomendaciones
1. Implementar RF en sistema de monitoreo
2. Revisar manualmente flageos de IF como control
3. Expandir a detección de anomalías de consumo

## 8. Limitaciones
- Dataset sintético (sin datos reales)
- Solo 2 tipos de defectos (extensible)
- Coordenadas GPS simplificadas

## Apéndice
- [código fuente completo]
- [gráficos adicionales]
- [métricas detalladas]
```

**4.4 Presentación (20 min)**
```
- Abrir los 4 notebooks en order
- Mostrar transición: EDA → ETL → ML → Validación
- Énfasis en reproducibilidad (mismo seed = mismo resultado)
- Demostración en vivo: re-ejecutar generador + modelos
```

### Deliverable
- **Jupyter Notebook**: `04_validation_and_conclusions.ipynb`
- **Reporte PDF**: `REPORTE_FINAL_Deteccion_Anomalias.pdf`
- **Modelos serializados**: `*.pkl`
- **Presentación**: Slides o HTML

### Tiempo: 2h ✓

---

## TIMELINE GENERAL

| Encuentro | Tema | Fecha | Entregables |
|-----------|------|-------|-------------|
| 1 | EDA | Semana 1-2 | `01_eda_early_stage.ipynb` + 10 gráficos |
| 2 | ETL + Features | Semana 3 | `02_etl_integration.ipynb` + `02_ml_dataset_prepared.csv` |
| 3 | ML Models | Semana 4-5 | `03_anomaly_detection.ipynb` + 2 modelos `.pkl` |
| 4 | Validación + Reporte | Semana 6-8 | `04_validation.ipynb` + Reporte PDF + Presentación |

---

## DISTRIBUCIÓN DE ROLES (Sugerencia)

**Millo (Tú - Líder Código)**:
- Encuentro 1: Montar infrastructure Jupyter, validaciones de integridad
- Encuentro 2: Feature engineering, ETL pipeline
- Encuentro 3: Implementación de modelos ML
- Encuentro 4: Integración final, presentación técnica

**Compañero (Análisis + Documentación)**:
- Encuentro 1: EDA gráficos y conclusiones
- Encuentro 2: Documentación de decisiones ETL
- Encuentro 3: Análisis de importancia de features
- Encuentro 4: Redacción del reporte final

---

## CHECKLIST PRE-ENCUENTRO

**Antes de E1**:
- ✅ Generador ejecutado y validado
- ✅ Dataset early_stage en disco
- ✅ Ambos con Jupyter + pandas instalado

**Antes de E2**:
- ✅ Notebook E1 completo
- ✅ Validaciones de integridad pensadas

**Antes de E3**:
- ✅ Dataset ML preparado
- ✅ Scikit-learn instalado

**Antes de E4**:
- ✅ Modelos entrenados
- ✅ Métrica de validación lista

---

## EXTENSIONES FUTURAS (Post-Encuentro 4)

Si queda tiempo o tienen interés:

1. **Detección de anomalías de consumo**: ¿Qué vehículos consumen más/menos de lo esperado?
2. **Análisis geoespacial**: Usar coordenadas reales, detectar rutas anómalas
3. **Series temporales**: Forecasting de consumo futuro
4. **Clustering**: Agrupar vehículos por comportamiento similar
5. **API REST**: Exponer modelos como servicio (Flask/FastAPI)

---

## RECOMENDACIONES FINALES

✅ **El generador está listo.** No hay cambios necesarios para E1.

🎯 **Foco en E1-E2**: Asegurar que entienden los datos antes de modelar.

📊 **Presentación**: Al final, mostrar reproducibilidad ejecutando generador en vivo.

🚀 **Tesis**: Este flujo (EDA → ETL → ML → Validación) es un buen esqueleto para cualquier proyecto de datos.

