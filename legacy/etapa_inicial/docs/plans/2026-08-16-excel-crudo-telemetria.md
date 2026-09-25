# Excel crudo de telemetría Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear una exportación sintética de estado de dispositivos sin relaciones explícitas.

**Architecture:** Se deriva una fila por dispositivo desde la última observación sintética. Alias, placa y motor funcionan como claves crudas imperfectas; el builder tabular exporta una sola hoja con manifiesto y hash.

**Tech Stack:** Python, `unittest`, Node.js y `@oai/artifact-tool`.

- [x] Probar columnas, ausencia de IDs, conteos, duplicados y dispositivos sin correspondencia.
- [x] Implementar filas crudas deterministas.
- [x] Crear y renderizar `telemetria_dispositivos.xlsx`.
- [x] Validar estructura, hash y pruebas; conservarlo fuera de Git.
