# Diagnóstico agregado H8 (ventanas del cruce) y H9 (precios del detalle) — Plan

**Goal:** Sumar dos bloques de diagnóstico al JSON de la auditoría agregada:
`diagnostico.cruce_registro_ventanas` (H8) y `diagnostico.facturacion_detalle_precios` (H9), sin
cambiar reglas ni las cifras existentes. Spec: `docs/superpowers/specs/2026-10-18-consultas-h8-h9-design.md`.

**Architecture:** El adaptador expone las columnas de precio unitario del reporte con nombres
genéricos (`precio_a`, `precio_b`, ...) en `datos["precios_reporte"]`, sin tocar `datos["consumo"]`.
Dos funciones nuevas en `perfilador/auditoria.py` arman los bloques y `auditar` los engancha en
`diagnostico`. Todo aditivo; ninguna regla cambia.

**Tech Stack:** Python 3.12, pandas 2.x, numpy, pytest. Sin librerías nuevas.

**Privacidad:** solo conteos (`acotar`) y porcentajes; particiones con total visible con
`_partes_sin_resta`; meses como `AAAA-MM`. Ningún nombre real de columna ni sigla del proveedor.

---

## File Structure

- `perfilador/adaptador.py` — **modificar:** detectar columnas de precio por patrón y exponerlas en
  `datos["precios_reporte"]`.
- `perfilador/auditoria.py` — **modificar:** `_cruce_registro_ventanas`, `_facturacion_detalle_precios`
  y el enganche en `auditar`.
- `tests/test_auditoria.py` — **modificar:** segunda columna de precio en la fuente sintética; tests de
  los dos bloques.

---

### Task 1: Exponer las columnas de precio del reporte

**Files:** Modify `perfilador/adaptador.py` (dentro de `adaptar`, rama del reporte de consumo).

- [ ] **Step 1: Detectar y exponer los precios.**

Después de armar `consumo` (y antes de `datos["consumo"] = consumo[consumo["litros"] > 0]`), agregar:

```python
        # Todas las columnas de precio unitario del reporte, en su orden, con nombres genéricos
        # (en el dominio no se escribe ningún nombre real de columna)
        columnas_precio = [c for c in fuente.columns if "PRECIO" in str(c).upper()]
        if columnas_precio:
            precios = pd.DataFrame({"id": consumo["id"].values})
            for i, columna in enumerate(columnas_precio):
                precios[f"precio_{chr(ord('a') + i)}"] = _numero(fuente[columna].values)
            datos["precios_reporte"] = precios.loc[consumo["litros"] > 0].reset_index(drop=True)
```

- [ ] **Step 2: Comprobar en la sintética.**

Run: `python -c "..."` o el test de la Task 4.
Expected: `datos["precios_reporte"]` con `id`, `precio_a`, `precio_b` (o solo `precio_a`).

- [ ] **Step 3: Commit.**

`analysis: expone las columnas de precio del reporte con nombres genericos`

---

### Task 2: Bloque H8 `diagnostico.cruce_registro_ventanas`

**Files:** Modify `perfilador/auditoria.py`.

- [ ] **Step 1: Escribir `_cruce_registro_ventanas(datos)`** según el spec §2 (bandas absolutas,
  dominio normalizado del vehículo, `_partes_sin_resta`, agrupación por dominio con búsqueda binaria;
  por mes y por `TipoVehiculo`). Devuelve `None` si no hay registro.

- [ ] **Step 2: Enganchar en `auditar`** dentro del bloque `if registro is not None and len(registro):`
  que ya corre el cruce, o inmediatamente después:
  `diagnostico["cruce_registro_ventanas"] = _cruce_registro_ventanas(datos)`.

- [ ] **Step 3: Commit.**

`analysis: agrega el diagnostico de ventanas del cruce con el registro (H8)`

---

### Task 3: Bloque H9 `diagnostico.facturacion_detalle_precios`

**Files:** Modify `perfilador/auditoria.py`.

- [ ] **Step 1: Escribir `_facturacion_detalle_precios(datos)`** según el spec §3 (cocientes por
  columna de precio, la razón entre los dos precios, diferencias deuda/líneas/PDF y conteos de líneas).
  Devuelve `None` si no hay detalle.

- [ ] **Step 2: Enganchar en `auditar`:** `diagnostico["facturacion_detalle_precios"] = _facturacion_detalle_precios(datos)`
  (después del filtrado de meses completos).

- [ ] **Step 3: Commit.**

`analysis: agrega el diagnostico de precios del detalle de facturacion (H9)`

---

### Task 4: Tests

**Files:** Modify `tests/test_auditoria.py`.

- [ ] **Step 1: Segunda columna de precio en la fuente sintética.** En `con_forma_real`, agregar al
  `reporte` una segunda columna de precio con nombre genérico (contiene "PRECIO"), igual a
  `precio_unitario * 0.98`.

- [ ] **Step 2: Test de H8** sobre un `datos` sintético armado a mano (como `test_las_contingencias_...`):
  cargas y pedidos que caigan en cada banda, con un par justo a 3 h y otro a 3 h + 1 min; verificar el
  total de cargas sin pedido, cada banda, los pares que cruzan, y que no quede ningún entero de 1 a 19
  suelto.

- [ ] **Step 3: Test de H9** con líneas y facturas sintéticas: un cociente exactamente en 0.98, un borde
  de diferencia (0.1 %), una duplicada, una sin carga y una de otro mes; verificar bandas y las dos
  columnas de precio.

- [ ] **Step 4:** `python -m pytest -q tests/test_auditoria.py`
  Expected: PASS.

- [ ] **Step 5: Commit.**

`test: cubre los diagnosticos de H8 y H9`

---

### Task 5: Suite, corrida real y PR

- [ ] **Step 1:** `python -m pytest -q` (suite completa). Expected: PASS.
- [ ] **Step 2:** Correr la auditoría en el server con `/tmp/venv2`; dejar el JSON en
  `perfiles/pendientes/auditoria_AAAA-MM-DD.json` (sin aprobar); verificar privacidad (sin correos,
  URLs, dominios, ids; conteos 1–19 suprimidos) y el diff con el aprobado de referencia.
- [ ] **Step 3:** Push de la rama y PR contra `main` (sin fusionar). Informar tests, commits y los
  conteos de los dos bloques.
