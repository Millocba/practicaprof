# Entorno de desarrollo

Las dependencias están fijadas en archivos reproducibles. Toda dependencia nueva requiere aprobación humana y se justifica en el PR.

## Capacidades recomendadas

- Git y acceso autorizado a GitHub.
- Una IA capaz de leer `AGENTS.md`, trabajar con Git y verificar resultados.
- Integración con GitHub mediante app, CLI `gh` o equivalente.
- Skills de ideación, planificación, depuración, pruebas y verificación; Superpowers es una opción recomendada.
- Soporte futuro para Python, SQL, notebooks, pruebas de datos y visualización.

Plugins, skills, extensiones y servidores MCP se instalan solo con aprobación humana, desde fuentes confiables y según su documentación oficial. Nunca se comparten tokens por Git.

## Flujo local

Clonar el repositorio, confirmar el estado y crear una rama para cada objetivo:

```bash
git status --short --branch
git switch -c docs/objetivo-acotado
```

No trabajar directamente sobre `main`.

## Entorno de trabajo

- **Python 3.12**. Es la versión con la que se verifican los tests y la que usa CI.
- `pip install -r requirements.txt` instala la aplicación y las herramientas de test. El despliegue usa solo `streamlit_app/requirements.txt`.
- El `requirements.txt` de la raíz no lista `scikit-learn`, `streamlit`, `plotly` ni `openpyxl`, que los tests necesitan (están en `streamlit_app/requirements.txt`; pendiente). Con pandas 3 fallan algunos tests de fechas: usar `pandas<3`.
- `python generator_pipeline_maestro.py` genera todos los datos sintéticos con la semilla por defecto; `--seed` y `--output` permiten otros escenarios sin pisar los datos locales.
- `python -m perfilador perfilar archivo.xlsx` genera el perfil agregado de una fuente externa en `perfiles/pendientes/`; `aprobar` y `comparar` completan el procedimiento de [perfiles/README.md](../perfiles/README.md). Se ejecuta junto a los datos: los archivos no se copian al repositorio.
- `python -m base_datos cargar` crea la base SQLite local del escenario realista (`datasets/auditoria_realista.db`, fuera de Git) y carga el dataset; `--hasta AAAA-MM-DD` hace una carga parcial, como una carga diaria.
- `python -m pytest` es el comando de verificación: debe pasar antes de abrir un PR. GitHub Actions lo ejecuta en cada push a `main` o `dev-*` y en cada PR.
- Los tests escriben en carpetas temporales; nunca usan `datasets/` ni una persistencia compartida.

Antes de ejecutar un agente: limitar accesos, pedirle leer `AGENTS.md`, asignarle rama e issue, confirmar operaciones sensibles y revisar personalmente su PR.
