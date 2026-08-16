# Reglas para agentes de IA

Estas instrucciones se aplican a todo el repositorio. Las instrucciones humanas explícitas tienen prioridad. Ante conflicto, ambigüedad o riesgo, detenerse y solicitar una decisión.

## Autoridad

- Las personas integrantes son Product Owners y propietarias de `main`.
- La IA propone, planifica, implementa, prueba y documenta; no decide el alcance final.
- Ningún resultado se considera aceptado hasta recibir aprobación humana.
- Un agente nunca aprueba ni fusiona su propio pull request.

## Privacidad y datos

- Usar exclusivamente datos sintéticos generados desde cero.
- No copiar, transformar, anonimizar ni usar como muestra registros reales.
- Se permiten catálogos públicos generales, como marcas y modelos comerciales, cuando aporten realismo analítico y no reproduzcan asignaciones reales.
- No incorporar nombres de personas, logos, identificadores, coordenadas, credenciales, dominios web o referencias de organizaciones reales.
- Los dominios vehiculares sintéticos pueden respetar un formato público, pero nunca se obtienen de padrones ni se asocian con unidades reales y deben marcarse como sintéticos.
- Antes de versionar datos, ejecutar las validaciones de `docs/DATA_GOVERNANCE.md`.
- Si aparece información potencialmente real, detener el trabajo, no imprimirla ni copiarla y avisar a una persona responsable.

## Forma de trabajo

1. Leer `README.md`, `CONTRIBUTING.md` y la documentación relevante.
2. Confirmar objetivo, restricciones y criterios de aceptación.
3. Inspeccionar el estado y los cambios existentes antes de editar.
4. Presentar un diseño o plan para cambios sustanciales.
5. Trabajar solamente en una rama asignada y de alcance acotado.
6. Implementar el cambio mínimo necesario, preservando trabajo ajeno.
7. Ejecutar verificaciones proporcionales al riesgo.
8. Revisar el diff completo y buscar datos sensibles antes de hacer commit.
9. Preparar un PR con evidencia, supuestos, riesgos y limitaciones.

## Git y commits

- No hacer push directo a `main`, force-push sobre ramas compartidas ni reescribir historia sin autorización.
- No usar operaciones destructivas como `reset --hard` o eliminaciones masivas sin alcance exacto y aprobación humana.
- Usar ramas como `docs/...`, `data/...`, `analysis/...`, `feat/...`, `ml/...`, `fix/...` o `test/...`.
- Mantener commits pequeños y con una sola intención.
- Usar Conventional Commits en español: `docs:`, `data:`, `analysis:`, `feat:`, `ml:`, `fix:`, `test:`, `refactor:` o `chore:`.
- No mencionar sistemas, instituciones, repositorios o datos externos en ramas, commits, PRs o documentación.
- No incluir cambios ajenos o no relacionados en un commit.

## Bases de datos y persistencia

- Identificar entorno, motor, host lógico y base objetivo antes de ejecutar una escritura.
- Considerar compartida cualquier persistencia cuyo carácter local y efímero no esté demostrado.
- No borrar, truncar, recrear, migrar, restaurar, sobrescribir ni cargar masivamente una persistencia compartida sin aprobación humana explícita.
- Antes de una operación destructiva, mostrar objetivo, tablas afectadas, impacto, respaldo disponible y procedimiento de recuperación.
- No ejecutar tests contra producción ni contra una base compartida. Usar persistencias temporales, contenedores aislados o transacciones reversibles.
- Toda modificación de esquema debe realizarse mediante migraciones versionadas y revisables.
- Las migraciones deben declarar compatibilidad, bloqueo esperado, estrategia de rollback y verificación posterior.
- Diseñar cargas y sincronizaciones idempotentes cuando sea viable. Documentar claves, conflictos y efectos laterales.
- No versionar `.db`, dumps, backups, logs con filas, archivos de conexión ni secretos.
- No asumir que un backup es recuperable: exigir un procedimiento de restauración comprobable.
- Usar consultas parametrizadas y privilegios mínimos. No registrar datos sensibles ni cadenas de conexión.

## Dependencias y servicios

- No instalar paquetes, plugins, skills, servidores MCP o extensiones sin aprobación humana.
- No conectar servicios externos, publicar despliegues ni transmitir datos sin autorización.
- Declarar dependencias en archivos reproducibles y justificar cada incorporación.
- Preferir capacidades portables: GitHub puede utilizarse mediante app, `gh` o una integración equivalente.

## Calidad y verificación

- No afirmar que un cambio funciona sin ejecutar verificaciones recientes y citar su resultado.
- Separar resultados observados de inferencias y recomendaciones.
- Mantener notebooks reproducibles y evitar estado oculto.
- Fijar semillas cuando corresponda y registrar versiones, entradas, parámetros y métricas.
- Comparar ML con una línea base y documentar errores, limitaciones y posibles sesgos.

## Prioridades

1. Privacidad y corrección de datos.
2. Reproducibilidad.
3. Claridad metodológica.
4. Trazabilidad.
5. Calidad técnica.
6. Presentación visual.
