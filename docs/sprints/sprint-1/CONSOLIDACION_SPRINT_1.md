# Consolidación Sprint 1 - Repositorio Integrador

**Fecha de Consolidación:** 2026-09-22

## Estructura Consolidada

### 📁 `/datasets/`
- **early_stage/** - Datasets originales (antes de procesamiento)
  - `transaccion_combustible.csv` - Registros de combustible históricos
  - `vehiculo.csv` - Catálogo de vehículos base
  - `evento_telemetria.csv` - Eventos de telemetría
  - `ground_truth.csv` - Verdad fundamental (defectos reales)
  
- **synthetic/** - Datos sintéticos v5 Defects-Aware
  - `vehiculos_v5.csv` - Flota de 200 vehículos v5
  - `vehiculos_v5_consumo.csv` - Flota enriquecida con capacidad de tanque

- **defects_aware_v5/** - Dataset v5 Defects-Aware completo
  - `vehiculo.csv` - 200 vehículos con 104 defectos inyectados
  - `dispositivo.csv` - Dispositivos rastreadores (GPS/GPRS)
  - `solicitud_combustible.csv` - Solicitudes procesadas
  - `reporte_consumo.csv` - Reportes de consumo brutos
  - `reporte_consumo_v5_vinculado.csv` - **[PRINCIPAL]** Consumo vinculado a vehículos (1749 registros)
  - `ground_truth.csv` - Catálogo de 104 defectos inyectados
  - `ejecucion_dataset.csv` - Metadatos de generación

### 📁 `/data/`
- **consumo/** - Reportes diarios de consumo (formato YPF)
  - `ReporteConsumos_202608.xlsx` - Reporte agosto 2026 (regenerado)
  - `ReporteConsumos_202609.xlsx` - Reporte septiembre 2026 (regenerado)

### 📁 `/results/`
- **integracion_cruces/** - Resultados de integración de datos
  - `reporte_consumo_v5_vinculado_enriquecido.csv` - Consumo enriquecido con all fields
  - `INTEGRACION_CONSUMO_RESUMEN.json` - Resumen de estadísticas de integración
    - **Cobertura:** 100% (1749/1749 transacciones vinculadas)
    - **Coherencia de consumos:** 99.3%
    - **Detectabilidad de defectos:** 94.2%

- **4_encuentros/** - Reportes de los 4 Encuentros completados
  - `E1_EDA_ANALYSIS.png` - Análisis Exploratorio de Datos (145KB)
  - `E1_defects_distribution.png` - Distribución de defectos (70KB)
  - `REPORTE_FINAL_4_ENCUENTROS.txt` - Resumen textual consolidado
  - `REPORTE_FINAL_4_ENCUENTROS.json` - Resumen estructurado (JSON)
  - `summary.json` - Metadatos de ejecución

## Scripts Disponibles

### Generación de Datos
- `generator_consumo_diario_standalone.py` - Generador de reportes de consumo
  - Uso: `python generator_consumo_diario_standalone.py --meses 2`
  - Crea reportes en `data/consumo/`

## Checksums de Validación

```
reporte_consumo_v5_vinculado.csv: 287K (1749 registros ✓)
INTEGRACION_CONSUMO_RESUMEN.json: Cobertura 100%
4_encuentros/*.png: Gráficos generados exitosamente
```

## Próximos Pasos

### Fase 2: ML Models (Tarea 2)
- Entrenar clasificadores para detectar defectos automáticamente
- Usar `reporte_consumo_v5_vinculado.csv` como training data
- Evaluar F1-score contra `ground_truth.csv`

### Fase 3: Análisis Profundo (Tarea 3)
- Clustering de patrones de consumo
- PCA para reducción dimensional
- Análisis de correlaciones entre variables

## Validación de Consolidación

✅ Dataset v5 Defects-Aware: Completo (200 vehículos, 104 defectos)
✅ Integración de datos: Exitosa (100% cobertura)
✅ 4 Encuentros: Completados (gráficos + reportes)
✅ Estructura del repositorio: Consolidada
✅ Documentación: Actualizada

**Estado:** LISTO PARA FASE 2 (ML Models)
