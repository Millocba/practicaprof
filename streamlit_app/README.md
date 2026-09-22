# 📊 Dataset v5 Integration Pipeline - Streamlit App

Interfaz integral para gestión, visualización y análisis del dataset integrado v5 con 104 defectos inyectados.

## 🚀 Inicio Rápido

### Instalación local

```bash
# Clonar o descargar el repositorio
cd streamlit_app

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
streamlit run app.py
```

### Acceder a la aplicación

La aplicación se abrirá automáticamente en `http://localhost:8501`

## 📋 Estructura de la Aplicación

### Página Principal (`app.py`)
- Dashboard con métricas principales
- Estado del pipeline
- Resumen de datasets
- Información de consolidación

### 🎯 Generador (`pages/01_generator.py`)
Ejecuta el generador de reportes de consumo:
- Configura número de meses a generar
- Visualiza resultados en tiempo real
- Descarga archivos Excel generados
- Previsualiza datos

### 📋 Datasets (`pages/02_datasets.py`)
Exploración interactiva de todos los datos:
- Búsqueda por texto completo
- Filtros por columna
- Estadísticas automáticas
- Exportación (CSV, Excel, JSON)

### 🔄 Pipeline (`pages/03_pipeline.py`)
Visualización del flujo ETL:
- 5 pasos de transformación
- Métricas de validación
- Estadísticas de cruces
- Información de outputs

### 📈 Análisis (`pages/04_analysis.py`)
Visualizaciones interactivas:
- Análisis de consumo
- Distribución de vehículos
- Estadísticas de defectos
- Información de dispositivos

## 🔑 Características Principales

### ✅ Funcionalidades
- ✅ Ejecución del generador desde la UI
- ✅ Visualización en tiempo real de datos
- ✅ Búsqueda y filtrado avanzado
- ✅ Gráficos interactivos (Plotly)
- ✅ Exportación de datos múltiples formatos
- ✅ Caché de datos para rendimiento
- ✅ Responsivo y mobile-friendly

### 📊 Datasets Soportados
1. **Vehículos** - 200 registros con 104 defectos
2. **Dispositivos** - 197 GPS/GPRS
3. **Consumo Vinculado** - 1749 transacciones
4. **Solicitudes Combustible** - 449 autorizaciones
5. **Ground Truth** - 104 defectos inyectados
6. **Consumo Enriquecido** - 1749 con fields extras

## 🌐 Deploy a Streamlit Cloud

### Prerequisitos
- Cuenta de GitHub (repositorio público)
- Cuenta de Streamlit Cloud

### Pasos

1. **Subir a GitHub:**
```bash
git add streamlit_app/
git commit -m "Add Streamlit app for Dataset v5"
git push origin main
```

2. **Crear app en Streamlit Cloud:**
   - Ir a https://share.streamlit.io
   - Click en "New app"
   - Conectar con GitHub
   - Seleccionar repositorio
   - Configurar:
     - **Repository**: tu-usuario/tu-repo
     - **Branch**: main
     - **Main file path**: `streamlit_app/app.py`

3. **Configurar URL de enlace:**
   La app estará disponible en: `https://share.streamlit.io/tu-usuario/tu-repo`

### Archivos necesarios

La estructura debe ser:
```
tu-repo/
├── streamlit_app/
│   ├── app.py
│   ├── requirements.txt
│   ├── .streamlit/
│   │   └── config.toml
│   ├── utils/
│   │   ├── data_loader.py
│   │   └── generator_runner.py
│   ├── pages/
│   │   ├── 01_generator.py
│   │   ├── 02_datasets.py
│   │   ├── 03_pipeline.py
│   │   └── 04_analysis.py
│   └── README.md
└── ... (otros archivos del proyecto)
```

## 🎯 Próximas Fases

### Fase 2: ML Models
- Integración de modelos de clasificación
- Dashboard de métricas (Precision, Recall, F1)
- Comparativa de algoritmos
- Feature importance visualization

### Fase 3: Análisis Profundo
- PCA y reducción dimensional
- Clustering interactivo
- Análisis de correlaciones
- Predicciones en tiempo real

### Fase 4: Documentación Tesis
- Exportación de reportes PDF
- Gráficos para tesis
- Conclusiones automáticas
- Referencias y métricas

## 📝 Requisitos Técnicos

### Python
- Python 3.8+
- Streamlit 1.28+
- Pandas 2.0+
- Plotly 5.17+

### Hardware
- CPU: 1 core (mínimo)
- RAM: 512MB (mínimo)
- Storage: 100MB (aplicación + datos)

## 🔐 Seguridad

- ✅ Sin credenciales almacenadas
- ✅ Sin datos sensibles en código
- ✅ Caché local solamente
- ✅ HTTPS en Streamlit Cloud

## 📞 Soporte

Para reportar problemas:
1. Verifica que todos los datos estén en `../datasets/`
2. Revisa los logs en la consola
3. Reinicia la aplicación: `streamlit run app.py`

## 📄 Licencia

Proyecto académico - Tesis de Grado
Dirección General de Gestión Administrativa

---

**Estado:** ✅ LISTO PARA DEPLOY  
**Última actualización:** 2026-09-22  
**Versión:** 1.0.0
