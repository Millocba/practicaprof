# Diseño fundacional del proyecto de datos

## Propósito

Crear un proyecto académico colaborativo, centrado en el ciclo de vida de los datos, que muestre cómo una pregunta exploratoria puede evolucionar hacia un sistema integral de generación, limpieza, integración, análisis, visualización y detección de anomalías.

El dominio será la gestión y auditoría de una flota, su telemetría y su consumo de combustible dentro de una organización completamente ficticia.

## Principios no negociables

- El repositorio utilizará exclusivamente datos sintéticos generados desde cero.
- No se incorporarán nombres, marcas, archivos, credenciales, ubicaciones, identificadores ni referencias de organizaciones reales.
- Los datos se describirán como sintéticos, nunca como anonimizados.
- Los generadores deberán ser reproducibles mediante semillas configurables.
- Las anomalías destinadas a evaluación se inyectarán deliberadamente y conservarán una verdad de referencia separada.
- Las personas integrantes conservarán la autoridad final sobre alcance, interpretación, aceptación y rama principal.
- Los agentes de IA actuarán como colaboradores técnicos y no como propietarios autónomos del producto.

## Narrativa académica

La documentación seguirá un enfoque híbrido: estructura académica formal y relato de evolución del proyecto. Explicará cómo una curiosidad inicial sobre calidad y consumo de datos conduce a integrar fuentes, formular nuevas hipótesis, automatizar controles y evaluar métodos estadísticos y de aprendizaje automático.

## Alcance de la etapa fundacional

La primera entrega será exclusivamente documental. No incluirá todavía implementación, datasets, notebooks ni aplicaciones. Estará compuesta por:

- `README.md`: presentación académica, alcance, características, hipótesis y hoja de ruta.
- `AGENTS.md`: reglas obligatorias para agentes de IA.
- `CONTRIBUTING.md`: flujo de ramas, commits, revisiones y pull requests.
- `docs/AI_PLAYBOOK.md`: procedimiento detallado de colaboración con IA y herramientas recomendadas.
- `docs/DATA_GOVERNANCE.md`: política de generación y validación de datos sintéticos.
- `docs/ARCHITECTURE.md`: arquitectura conceptual centrada en datos.
- `docs/DEVELOPMENT.md`: preparación reproducible del entorno y capacidades recomendadas.
- `.github/pull_request_template.md`: evidencia mínima exigida en cada cambio.
- `.github/ISSUE_TEMPLATE/feature.yml`: plantilla para requerimientos con criterios de aceptación.
- `.github/ISSUE_TEMPLATE/config.yml`: configuración de formularios de trabajo.
- `.github/CODEOWNERS`: propiedad humana de los cambios.

## Hipótesis iniciales

1. Los datos operativos contienen inconsistencias que afectan la calidad de los indicadores.
2. La integración de fuentes permite detectar situaciones invisibles en análisis aislados.
3. El consumo puede explicarse parcialmente por características, actividad e historial del vehículo.
4. Las reglas de control identifican una parte relevante de los eventos irregulares.

## Hipótesis emergentes

1. Algunos aparentes problemas de consumo provienen de errores de identificación o vinculación.
2. La ausencia de telemetría constituye una señal analítica.
3. Un mismo umbral fijo no resulta apropiado para todos los tipos de vehículo.
4. El comportamiento histórico individual puede ser una referencia superior a un umbral general.
5. Combinar reglas, estadística robusta y aprendizaje automático puede mejorar la detección y reducir falsas alertas.
6. La trazabilidad es tan importante como la precisión en un sistema de auditoría.

Estas hipótesis se presentarán como afirmaciones contrastables, no como conclusiones anticipadas.

## Responsabilidades

### Personas integrantes

- Formular y aprobar preguntas, hipótesis y criterios de éxito.
- Definir el significado y la coherencia esperada de las variables sintéticas.
- Interpretar resultados y revisar limitaciones o sesgos.
- Revisar pull requests y decidir su aceptación.
- Conservar la propiedad y autoridad final sobre `main`.

### Agentes de IA

- Proponer alternativas y explicitar sus supuestos.
- Preparar planes antes de realizar cambios sustanciales.
- Implementar generadores, pipelines, pruebas, análisis y capas de soporte.
- Trabajar en ramas asignadas y entregar cambios mediante pull requests.
- Presentar evidencia de pruebas y verificaciones.
- Detenerse ante riesgos de privacidad, ambigüedad o ampliaciones de alcance.

Ningún resultado generado por IA se considerará aceptado hasta que una persona integrante pueda explicar su propósito, entradas, salidas, supuestos y validación.

## Gobierno de Git

- `main` será una rama protegida y de propiedad humana.
- Después del commit fundacional no se permitirán pushes directos a `main`.
- Cada cambio se desarrollará en una rama de alcance acotado.
- Todo cambio entrará mediante pull request.
- Los agentes no aprobarán ni fusionarán su propio trabajo.
- Los commits serán pequeños, descriptivos y seguirán Conventional Commits.
- No se permitirán force-pushes ni eliminaciones de `main`.
- Las protecciones técnicas de GitHub complementarán, y no reemplazarán, estas reglas.

## Prioridades

1. Privacidad y corrección de los datos.
2. Reproducibilidad.
3. Claridad metodológica.
4. Trazabilidad.
5. Calidad técnica.
6. Presentación visual.

## Herramientas y portabilidad

El proyecto recomendará flujos de trabajo con GitHub, skills de planificación y verificación como Superpowers, y conectores o servidores MCP cuando aporten capacidades concretas. Las reglas expresarán capacidades requeridas y ofrecerán alternativas equivalentes, evitando depender obligatoriamente de un proveedor o una IA determinados.

Las dependencias futuras se declararán en archivos reproducibles del proyecto. Ningún agente instalará dependencias, conectará servicios externos ni modificará configuraciones compartidas sin aprobación humana.

## Persistencia y bases de datos

- Los entornos local, prueba y producción deberán estar separados y ser identificables antes de ejecutar operaciones.
- Ningún agente borrará, truncará, recreará, migrará o sobrescribirá una persistencia compartida sin aprobación humana explícita.
- Toda migración deberá ser versionada, revisable y acompañada por un plan de reversión o recuperación.
- Antes de una operación destructiva se verificarán destino, entorno, alcance y existencia de un respaldo recuperable.
- Los tests utilizarán persistencias efímeras o aisladas y nunca se ejecutarán contra producción.
- No se registrarán credenciales, cadenas de conexión, volcados ni archivos de bases de datos.
- Las cargas y transformaciones deberán ser idempotentes cuando resulte viable y declarar sus efectos laterales.
- Las copias de seguridad solo se considerarán válidas si existe un procedimiento de restauración comprobable.

## Criterios de aceptación de la etapa

- La documentación describe el proyecto sin depender de contexto externo.
- Declara inequívocamente el uso exclusivo de datos sintéticos.
- Distingue hipótesis iniciales, emergentes y conclusiones futuras.
- Define autoridad humana y comportamiento de agentes.
- Define ramas, commits, PRs y controles de `main`.
- No contiene referencias a proyectos, organizaciones o datos reales.
- Los enlaces internos y plantillas de GitHub son coherentes.

## Fuera de alcance

- Generar el primer dataset sintético.
- Elegir librerías definitivas de análisis o aprendizaje automático.
- Implementar backend o frontend.
- Entrenar modelos o presentar resultados experimentales.
- Afirmar que alguna hipótesis ha sido confirmada.
