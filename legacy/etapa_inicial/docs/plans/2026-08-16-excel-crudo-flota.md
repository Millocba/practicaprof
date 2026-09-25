# Excel crudo de flota Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derivar un Excel crudo de flota desde la verdad sintética, sin IDs ni relaciones explícitas.

**Architecture:** Python construye filas crudas deterministas y registra defectos; un builder JavaScript usa `@oai/artifact-tool` para crear, dar formato, renderizar y exportar el `.xlsx`. El manifiesto publica conteos y hash, no la verdad por fila.

**Tech Stack:** Python 3.11+, `unittest`, Node.js y `@oai/artifact-tool`.

## Global Constraints

- No leer archivos ni datos reales.
- No incluir IDs internos o claves foráneas.
- Conservar exactamente 250 filas, 32 duplicados normalizados de matrícula y 32 de dominio.
- Generar solo la fuente flota.

---

### Task 1: Filas crudas

- [x] Escribir y observar fallar pruebas de columnas, ausencia de IDs, conteos y defectos.
- [x] Implementar `build_raw_flota_rows(tables, seed)`.
- [x] Ejecutar la suite completa.

### Task 2: Libro y manifiesto

- [x] Crear JSON intermedio local ignorado por Git.
- [x] Crear `flota_vehicular.xlsx` con una hoja `Flota`, filtros, encabezado congelado y formatos tipados.
- [x] Crear manifiesto con semilla, filas, columnas, defectos y SHA-256.

### Task 3: Verificación

- [x] Inspeccionar rangos clave y ausencia de IDs.
- [x] Renderizar y revisar visualmente la hoja.
- [x] Ejecutar pruebas, validar hash y mantener la rama local.
