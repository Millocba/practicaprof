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

## Revisión y aprobación

### Reglas de `main`

GitHub las aplica solas; no hace falta recordarlas:

- No se puede subir directo a `main` ni forzar su historia: todo entra por un PR.
- Los tests (`pytest`) tienen que pasar para poder fusionar.
- Cada PR necesita la aprobación del dueño del código (ver `.github/CODEOWNERS`).
- Si entran commits nuevos después de una aprobación, la aprobación se descarta y hay que volver a aprobar.
- Los comentarios de revisión tienen que estar resueltos antes de fusionar.
- La rama se borra sola al fusionar.

Los administradores del repositorio pueden fusionar sin aprobación. Los PR que abre la IA salen con la cuenta del dueño, así que su revisión es la de la persona que los fusiona.

### Procedimiento

1. **El autor** abre el PR desde una rama creada sobre `main` actualizada, completa la plantilla y escribe `Closes #N` para cerrar el issue que resuelve.
2. **La IA hace una prerrevisión** y deja sus observaciones como comentarios del PR:
   - verifica las cifras y afirmaciones contra el código y la documentación;
   - corre los tests en una copia aparte de la rama;
   - busca datos reales, identificadores o nombres de organizaciones;
   - si el PR toca la app, la levanta en local para verla.
3. **El autor corrige** en la misma rama y resuelve los comentarios. Las correcciones de un PR van en ese PR; un issue aparte es solo para trabajo que queda fuera de su alcance.
4. **El dueño del código aprueba y fusiona.** Si el cambio toca `deteccion/`, `perfilador/`, `base_datos/` o el generador, después se actualiza `dev-hector` con `main` y se reinicia la app publicada, que despliega desde esa rama.

### Qué revisar en cada PR

- [ ] Resuelve lo que pide su issue y nada más.
- [ ] Parte de `main` actualizada y no tiene conflictos.
- [ ] Los tests pasan; si cambia comportamiento, hay un test que lo cubre.
- [ ] Las cifras que cita (F1, porcentajes, cantidades) coinciden con lo que produce el código hoy.
- [ ] Si toca el generador: las hipótesis se siguen sosteniendo con 5 semillas y el escenario didáctico genera CSV idénticos.
- [ ] No tiene datos reales, identificadores, nombres de personas u organizaciones, ni referencias a sistemas externos.
- [ ] La documentación afectada (README, diccionario, bitácora) está actualizada.
- [ ] La plantilla está completa y marca una sola opción de persistencia.

## Bases de datos

Los cambios de esquema requieren migración versionada, revisión, estrategia de recuperación y prueba aislada. Las operaciones destructivas o cargas masivas sobre persistencias compartidas requieren aprobación humana explícita.

## Definición de terminado

Un cambio está listo para revisión cuando cumple sus criterios de aceptación, pasa verificaciones recientes, no introduce datos o referencias reales, documenta sus efectos y puede ser explicado por la persona que solicitó el trabajo.
