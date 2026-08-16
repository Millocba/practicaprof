# Fundación documental Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establecer identidad académica, gobierno de datos, reglas para IA y flujo de contribución.

**Architecture:** La documentación se divide por responsabilidad. Las plantillas de GitHub convierten las reglas en controles visibles durante issues y pull requests.

**Tech Stack:** Markdown, YAML y funciones nativas de GitHub.

## Global Constraints

- Usar exclusivamente datos sintéticos generados desde cero.
- No mencionar proyectos, organizaciones, datos ni sistemas externos reales.
- Mantener autoridad humana final sobre `main`.
- No instalar dependencias ni conectar servicios externos sin aprobación humana.
- No realizar operaciones destructivas sobre persistencias compartidas sin aprobación humana explícita.

---

### Task 1: Identidad y narrativa académica

**Files:** Create: `README.md`

**Interfaces:**
- Consumes: diseño fundacional aprobado.
- Produces: puerta de entrada autocontenida al proyecto.

- [x] **Step 1:** Documentar contexto, objetivos, alcance, hipótesis y hoja de ruta.
- [x] **Step 2:** Declarar el uso exclusivo de datos sintéticos.

### Task 2: Gobierno humano y de agentes

**Files:** Create: `AGENTS.md`, `CONTRIBUTING.md`, `docs/AI_PLAYBOOK.md`

**Interfaces:**
- Consumes: prioridades y responsabilidades aprobadas.
- Produces: reglas obligatorias y flujo de PR.

- [x] **Step 1:** Definir autoridad, permisos, pausas y verificaciones.
- [x] **Step 2:** Definir ramas, commits, PRs y revisión humana.
- [x] **Step 3:** Documentar capacidades recomendadas sin dependencia de proveedor.

### Task 3: Datos, persistencia y arquitectura

**Files:** Create: `docs/DATA_GOVERNANCE.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`

**Interfaces:**
- Consumes: dominio ficticio y restricciones de privacidad.
- Produces: políticas y estructura futura.

- [x] **Step 1:** Definir validaciones contra filtraciones.
- [x] **Step 2:** Definir migraciones, backups y operaciones destructivas.
- [x] **Step 3:** Describir flujo conceptual y entorno futuro.

### Task 4: Controles de GitHub

**Files:** Create: `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/feature.yml`, `.github/ISSUE_TEMPLATE/config.yml`, `.github/CODEOWNERS`

**Interfaces:**
- Consumes: `CONTRIBUTING.md`.
- Produces: plantillas y propiedad visible.

- [x] **Step 1:** Exigir evidencia, privacidad y persistencia en PRs.
- [x] **Step 2:** Exigir criterios de aceptación en requerimientos.
- [x] **Step 3:** Asignar propiedad humana.

### Task 5: Verificación y publicación

**Files:** Verify: todos los Markdown y YAML.

**Interfaces:**
- Consumes: documentación completa.
- Produces: rama publicada y PR revisable.

- [x] **Step 1:** Buscar placeholders y referencias prohibidas.
- [x] **Step 2:** Validar enlaces, YAML y espacios.
- [x] **Step 3:** Revisar diff contra criterios de aceptación.
- [x] **Step 4:** Crear commit, publicar rama y abrir PR.
