# Generador de dataset MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generar un dataset sintético reproducible, relacionado y validado para el escenario `early_stage`.

**Architecture:** Un paquete Python sin dependencias externas crea primero entidades limpias, luego hechos relacionados y finalmente inyecta defectos registrados en una verdad separada. Una CLI exporta CSV UTF-8 y un manifiesto JSON con hashes, conteos y parámetros.

**Tech Stack:** Python 3.11+, biblioteca estándar, `unittest`, CSV y JSON.

## Global Constraints

- No conectarse a servicios o bases externas.
- No consumir archivos ni valores reales.
- Identificadores inequívocamente sintéticos.
- Semilla obligatoria y resultados reproducibles.
- Rama exclusivamente local.

---

### Task 1: Contrato del generador

**Files:** Create: `tests/test_generator.py`, `synthetic_data/__init__.py`, `synthetic_data/generator.py`

**Interfaces:**
- Produces: `GenerationConfig`, `generate_dataset(config)` y diccionario de tablas.

- [x] **Step 1:** Escribir pruebas que exijan conteos, prefijos, relaciones y reproducibilidad.
- [x] **Step 2:** Ejecutar las pruebas y observar fallo por módulo inexistente.
- [x] **Step 3:** Implementar generación mínima de maestros y hechos.
- [x] **Step 4:** Ejecutar la suite hasta obtener verde.

### Task 2: Escenario y verdad sintética

**Files:** Modify: `tests/test_generator.py`, `synthetic_data/generator.py`

**Interfaces:**
- Produces: inyección determinista y tabla `ground_truth`.

- [x] **Step 1:** Escribir pruebas para 32 duplicados de matrícula y 32 de dominio.
- [x] **Step 2:** Confirmar el fallo esperado.
- [x] **Step 3:** Implementar inyección y registro de defectos.
- [x] **Step 4:** Ejecutar todas las pruebas.

### Task 3: Exportación y manifiesto

**Files:** Create: `synthetic_data/cli.py`; Modify: `tests/test_generator.py`

**Interfaces:**
- Produces: `export_dataset(tables, config, output_dir)` y CLI `python -m synthetic_data.cli`.

- [x] **Step 1:** Escribir pruebas para CSV, manifiesto, hashes y bloqueo de sobrescritura.
- [x] **Step 2:** Confirmar el fallo esperado.
- [x] **Step 3:** Implementar exportación atómica sin sobrescritura implícita.
- [x] **Step 4:** Ejecutar suite completa.

### Task 4: Dataset y verificación

**Files:** Create: `datasets/early_stage/*`; Modify: `README.md`, `.gitignore`

- [x] **Step 1:** Generar el perfil inicial con semilla `20260816`.
- [x] **Step 2:** Verificar conteos, relaciones, defectos y hashes.
- [x] **Step 3:** Documentar el comando y el contenido.
- [x] **Step 4:** Revisar secretos, referencias prohibidas y estado de Git.
