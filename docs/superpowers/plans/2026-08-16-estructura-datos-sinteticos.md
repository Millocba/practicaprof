# Estructura de datos sintéticos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comunicar al equipo el modelo de datos, sus problemáticas históricas y el proceso seguro para generar escenarios sintéticos.

**Architecture:** La documentación separa estructura, semántica, límites de privacidad, escenarios de calidad y método de generación. Ningún documento contiene valores, credenciales o referencias de sistemas reales.

**Tech Stack:** Markdown y Mermaid.

## Global Constraints

- No conectarse a servicios ni bases externas durante esta etapa.
- No copiar filas, muestras, valores, credenciales o nombres reales.
- Documentar un modelo objetivo genérico con identificadores inequívocamente sintéticos.
- Mantener la rama exclusivamente local.

---

### Task 1: Modelo y diccionario

**Files:** Create: `docs/DATA_MODEL.md`, `docs/DATA_DICTIONARY.md`

- [x] **Step 1:** Definir entidades, claves, relaciones y cardinalidades.
- [x] **Step 2:** Documentar campos, tipos, nulabilidad, semántica y validaciones.

### Task 2: Seguridad y método sintético

**Files:** Create: `docs/REAL_DATA_BOUNDARY.md`, `docs/SYNTHETIC_DATA_METHOD.md`

- [x] **Step 1:** Establecer qué metadatos agregados pueden salir del entorno controlado.
- [x] **Step 2:** Definir fases reproducibles de generación y verdad sintética.

### Task 3: Escenarios de calidad

**Files:** Create: `docs/DATA_QUALITY_SCENARIOS.md`

- [x] **Step 1:** Definir escenarios `clean`, `early_stage`, `transition`, `mature` y `stress`.
- [x] **Step 2:** Modelar duplicados históricos y otras problemáticas sin presentarlos como mediciones exactas.

### Task 4: Navegación y verificación

**Files:** Modify: `README.md`

- [x] **Step 1:** Enlazar la documentación nueva desde el README.
- [x] **Step 2:** Validar enlaces, referencias prohibidas, placeholders y `git diff --check`.
- [x] **Step 3:** Revisar que no existan valores ni archivos de datos.
