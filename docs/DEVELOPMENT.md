# Entorno de desarrollo

La etapa fundacional no instala dependencias. Las tecnologías se elegirán cuando exista una necesidad aprobada y quedarán fijadas en archivos reproducibles.

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

## Requisitos futuros

Cuando se incorpore código, el repositorio proporcionará versiones soportadas, dependencias bloqueadas, variables de ejemplo sin secretos, un comando de verificación, persistencias aisladas y un procedimiento para generar todos los datos sintéticos.

Antes de ejecutar un agente: limitar accesos, pedirle leer `AGENTS.md`, asignarle rama e issue, confirmar operaciones sensibles y revisar personalmente su PR.
