# Exceles crudos de consumo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear dos libros sintéticos reproducibles de consumo diario, uno interno y otro externo, relacionados con la flota y entre sí.

**Architecture:** Un módulo común deriva eventos de consumo desde la verdad relacional existente y conserva una clave de trazabilidad solo en memoria. Dos adaptadores proyectan esos eventos a contratos crudos independientes sin IDs internos; los builders de `@oai/artifact-tool` producen libros y manifiestos separados.

**Tech Stack:** Python 3, `unittest`, Node.js y `@oai/artifact-tool`.

## Global Constraints

- Usar exclusivamente datos sintéticos generados desde cero.
- Mantener el período entre 2025-01-01 y 2025-12-31, coherente con telemetría.
- Mantener al menos 95 % de cobertura de los 250 vehículos.
- No exponer IDs internos ni claves foráneas en los Excel.
- Mantener relaciones auditables mediante la semilla y la verdad base, fuera de los libros crudos.
- Conservar los artefactos fuera de Git hasta autorización humana explícita.

---

### Task 1: Proyección cruda de consumo interno

**Files:**
- Create: `tests/test_raw_consumo.py`
- Create: `raw_sources/consumo.py`
- Create: `raw_sources/prepare_consumo.py`

**Interfaces:**
- Consumes: `generate_dataset(GenerationConfig)`.
- Produces: `build_raw_consumo_rows(tables, seed)` y payloads JSON para ambos orígenes.

- [x] **Step 1: Write the failing tests** for exact columns, no IDs, 4,760 rows, daily coverage, 95 % vehicle coverage, shared event counts, tank limits and deterministic output.
- [x] **Step 2: Run `python -m unittest tests.test_raw_consumo -v`** and verify failure because `raw_sources.consumo` does not exist.
- [x] **Step 3: Implement minimal projections** using `FECHA`, `HORA`, `LITROSCARGADOS`, `DOMINIO`, `MATRICULA` internally and the external transaction contract independently.
- [x] **Step 4: Run the test module** and verify all assertions pass.

### Task 2: Construcción y verificación de los libros

**Files:**
- Create: `tools/build_consumo_workbooks.mjs`
- Modify: `README.md`

**Interfaces:**
- Consumes: `.tmp/consumo_rows.json`.
- Produces: `datasets/raw/early_stage/consumo_interno/consumo_interno.xlsx` and `datasets/raw/early_stage/consumo_externo/consumo_externo.xlsx`, each with a manifest.

- [x] **Step 1: Build both workbooks** with one styled, filtered and frozen data sheet each.
- [x] **Step 2: Inspect key ranges and scan formula errors** with the artifact API.
- [x] **Step 3: Render both sheets and visually verify headers, types, widths and readability.**
- [x] **Step 4: Run the complete unit test suite and validate both manifests and SHA-256 hashes.**
- [x] **Step 5: Commit code and documentation locally** with a Conventional Commit in Spanish; do not publish datasets or branch.
