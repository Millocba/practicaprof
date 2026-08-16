# Guía de contribución

Todo cambio comienza con un requerimiento comprensible, se desarrolla en una rama y llega a `main` mediante un pull request aprobado por una persona responsable.

## Flujo

1. Crear o seleccionar un issue con contexto y criterios de aceptación.
2. Acordar alcance, supuestos y responsable humano.
3. Crear una rama desde `main` actualizada.
4. Diseñar o planificar antes de cambios sustanciales.
5. Implementar y verificar en commits pequeños.
6. Revisar privacidad, persistencia y diff completo.
7. Publicar la rama y abrir un PR no ambiguo.
8. Corregir observaciones en la misma rama.
9. Una persona responsable acepta y fusiona el PR.

## Ramas y commits

Usar nombres como `docs/definicion-proyecto`, `data/generador-flota`, `analysis/eda-consumo`, `feat/pipeline-integracion`, `ml/deteccion-anomalias` o `fix/validacion-consumo`.

Usar Conventional Commits en español, por ejemplo:

```text
docs: define alcance y objetivos
data: agrega esquema sintético de vehículos
analysis: incorpora perfilado de consumo
feat: implementa integración de telemetría
ml: agrega línea base estadística
test: valida integridad referencial
```

Un commit debe contener una sola intención verificable. No trabajar directamente en `main` ni reutilizar una rama para objetivos diferentes.

## Pull requests

Cada PR debe explicar problema, alcance, decisiones, persistencias afectadas, verificaciones, privacidad, riesgos, supuestos y limitaciones. Los agentes de IA no aprueban ni fusionan sus propios PRs. La aprobación final siempre es humana.

## Bases de datos

Los cambios de esquema requieren migración versionada, revisión, estrategia de recuperación y prueba aislada. Las operaciones destructivas o cargas masivas sobre persistencias compartidas requieren aprobación humana explícita.

## Definición de terminado

Un cambio está listo para revisión cuando cumple sus criterios de aceptación, pasa verificaciones recientes, no introduce datos o referencias reales, documenta sus efectos y puede ser explicado por la persona que solicitó el trabajo.
