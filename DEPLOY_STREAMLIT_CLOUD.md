# 🚀 Guía de Deploy a Streamlit Cloud

## Resumen
Esta guía proporciona instrucciones paso a paso para desplegar la aplicación Streamlit a Streamlit Cloud (Community Cloud) de forma gratuita.

## ✅ Prerequisitos

### 1. Cuenta de GitHub
- Crear cuenta en https://github.com (si no tienes)
- Estar autenticado en GitHub

### 2. Cuenta de Streamlit Cloud
- Ir a https://share.streamlit.io
- Click en "Sign up with GitHub"
- Autorizar Streamlit Cloud a acceder a tu GitHub

### 3. Repositorio Git
- Repositorio público en GitHub con la estructura correcta
- Todos los archivos de la app deben estar en rama `main`

## 📁 Estructura Requerida

```
tu-repo/
├── streamlit_app/
│   ├── app.py                          # Archivo principal
│   ├── requirements.txt                # Dependencias Python
│   ├── .streamlit/
│   │   └── config.toml                # Configuración
│   ├── .gitignore                     # Ignorar archivos
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── data_loader.py
│   │   └── generator_runner.py
│   ├── pages/
│   │   ├── 01_generator.py
│   │   ├── 02_datasets.py
│   │   ├── 03_pipeline.py
│   │   └── 04_analysis.py
│   └── README.md
│
├── datasets/                           # ⚠️ Importante: estos datos también necesitan
│   └── defects_aware_v5/              # subirse al repo o usar Git LFS
│       ├── vehiculo.csv
│       ├── dispositivo.csv
│       ├── reporte_consumo_v5_vinculado.csv
│       └── ... (otros archivos)
│
├── results/
│   ├── integracion_cruces/
│   └── 4_encuentros/
│
└── data/
    └── consumo/
```

## 🔧 Paso a Paso

### Paso 1: Preparar el Repositorio

```bash
# En la raíz de tu repositorio local
# Asegúrate de que todo esté en git

git status
git add .
git commit -m "Add Streamlit app for Dataset v5 Integration Pipeline"
git push origin main
```

### Paso 2: Crear la App en Streamlit Cloud

1. Ir a https://share.streamlit.io
2. Click en **"New app"** (botón superior derecho)
3. Completar el formulario:

```
Repository (Repositorio):
└─ tu-usuario/tu-repo

Branch (Rama):
└─ main

Main file path (Archivo principal):
└─ streamlit_app/app.py
```

4. Click en **"Deploy"**

### Paso 3: Esperar el Despliegue

- Streamlit instalará las dependencias (primeras 1-2 minutos)
- La app se ejecutará automáticamente
- Verás un enlace como: `https://share.streamlit.io/tu-usuario/tu-repo`

### Paso 4: Compartir la App

Tu app estará disponible en:
```
https://share.streamlit.io/tu-usuario/tu-repo
```

Puedes:
- Compartir el enlace directamente
- Incrustarlo en un sitio web
- Agregarlo a tu portfolio

## ⚠️ Consideraciones Importantes

### Tamaño de Datos
- Streamlit Cloud tiene limite de 1GB de almacenamiento
- Los datasets v5 (~600KB) son pequeños
- Si necesitas más datos, usa Git LFS (Large File Storage)

### Alternativa con Git LFS
```bash
# Instalar Git LFS
git lfs install

# Trackear archivos grandes
git lfs track "datasets/**/*.csv"
git add .gitattributes

# Commit y push
git add .
git commit -m "Add large files with Git LFS"
git push origin main
```

### Performance
- La app cachea datos automáticamente
- Primer load: 10-15 segundos
- Siguientes loads: <1 segundo

## 🔄 Actualizaciones Posteriores

### Para actualizar la app:

```bash
# Hacer cambios localmente
# Ejemplo: editar app.py

# Subir cambios a GitHub
git add .
git commit -m "Update Streamlit app - nuevo feature"
git push origin main

# Streamlit detecta automáticamente los cambios
# y reinicia la app en 1-2 minutos
```

### Versioning
Es recomendable tagear releases importantes:
```bash
git tag -a v1.0.0 -m "First Streamlit Cloud deployment"
git push origin v1.0.0
```

## 🎯 Monitoreo y Debugging

### Ver logs en Streamlit Cloud:
1. Ir a tu app en https://share.streamlit.io
2. Click en los "⋮ kebab menu" (arriba a la derecha)
3. Seleccionar "View logs"

### Errores comunes:

**Error: Module not found**
```
→ Falta dependencia en requirements.txt
→ Solución: agregar y hacer git push
```

**Error: File not found**
```
→ Rutas relativas incorrectas
→ Solución: usar Path(__file__).parent para rutas correctas
```

**Error: Out of memory**
```
→ Datos muy grandes
→ Solución: usar caché, Git LFS, o API externa
```

## 💡 Tips Avanzados

### 1. Secretos (API keys, contraseñas)
```python
import streamlit as st

# En .streamlit/secrets.toml (local)
# [production]
# api_key = "tu_clave_secreta"

# En Streamlit Cloud: Settings > Secrets
# Acceder desde el código:
api_key = st.secrets["api_key"]
```

### 2. URLs Personalizadas
En Streamlit Cloud puedes customizar el subdominio:
- Settings > Custom subdomain
- Cambiar de `share.streamlit.io/usuario/repo`
- A `tu-app-custom.streamlit.app`

### 3. Dominio Personalizado
- Planes pagos permiten dominio personalizado
- Ej: `myapp.miempresa.com`

## 📊 Próximas Fases

### Fase 2: Agregar ML Models
```python
# En pages/05_ml_models.py
# - Entrenamiento de clasificadores
# - Evaluación de modelos
# - Predicciones en tiempo real
```

### Fase 3: Base de Datos
```python
# Usar Streamlit Secrets + API externa
# - Guardar predicciones
# - Histórico de análisis
# - Resultados por usuario
```

### Fase 4: Autenticación
```python
# Usar streamlit-authenticator
# - Login de usuarios
# - Permisos por rol
# - Análisis personalizados
```

## 📝 Ejemplo de Deploy Completo

```bash
# 1. Crear/clonar repo
git clone https://github.com/tu-usuario/tu-repo.git
cd tu-repo

# 2. Crear rama para la app (opcional)
git checkout -b streamlit-app

# 3. Copiar archivos de la app
cp -r /ruta/a/streamlit_app .

# 4. Verificar estructura
ls -la streamlit_app/

# 5. Commit y push
git add streamlit_app/
git commit -m "Add Streamlit app for Dataset v5"
git push origin streamlit-app  # O main

# 6. En GitHub: crear Pull Request
# 7. Merge a main
# 8. En Streamlit Cloud: Deploy

# 9. ¡Listo! App disponible en:
# https://share.streamlit.io/tu-usuario/tu-repo
```

## 🎓 Para la Tesis

### Ventajas de usar Streamlit Cloud:
✅ Despliegue gratuito  
✅ No requiere servidor  
✅ HTTPS automático  
✅ Escalable automáticamente  
✅ Perfecto para demostración de tesis  
✅ Compartible por enlace  

### En el documento de tesis:
```
"La aplicación está disponible en línea:
https://share.streamlit.io/tu-usuario/tu-repo

El usuario puede interactuar en tiempo real con:
- Ejecución del generador
- Visualización de 1749 transacciones
- Análisis de 104 defectos inyectados
- Pipeline ETL completo
```

## ✅ Checklist Pre-Deploy

- [ ] Repositorio GitHub público
- [ ] Rama main actualizada
- [ ] Estructura de carpetas correcta
- [ ] requirements.txt con dependencias
- [ ] .streamlit/config.toml presente
- [ ] app.py y pages/ listos
- [ ] Datos en datasets/ o Git LFS
- [ ] .gitignore configurado
- [ ] Prueba local: `streamlit run app.py`
- [ ] Todos los cambios commiteados y pusheados

---

**Estado:** ✅ LISTO PARA DEPLOY  
**Tiempo estimado:** 5-10 minutos  
**Costo:** $0 (Streamlit Community Cloud)  
**Soporte:** https://discuss.streamlit.io
