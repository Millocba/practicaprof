**H3b** (EXCESO_VOLUMETRICO, CAPACIDAD_MAL_REGISTRADA), unidad: carga. Diseño con las semillas [1001, 1002, 1003]; evaluación con [42, 7, 123, 2024, 99] (375 anomalías en total). Umbral fijo 0.5. Variables excluidas en el segundo escenario: ratio_litros_tanque, litros_vs_habitual, tanques_en_el_dia.

| Método | Precisión | Recall | F1 | F1 por semilla (media ± desvío) | Precisión promedio (sin umbral) | Precisión en las primeras k | TP | FP | FN | TN |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Línea base ingenua | 0.71 | 1.00 | 0.83 | 0.82 ± 0.05 | 0.69 | 0.71 | 375 | 153 | 0 | 34298 |
| Regla con contexto | 0.95 | 1.00 | 0.98 | 0.97 ± 0.01 | 0.94 | 0.97 | 375 | 19 | 0 | 34432 |
| Isolation Forest (sin etiquetas) | 0.06 | 0.42 | 0.10 | 0.10 ± 0.03 | 0.06 | 0.04 | 157 | 2585 | 218 | 31866 |
| Regresión logística, todas las variables | 0.30 | 1.00 | 0.46 | 0.46 ± 0.14 | 0.77 | 0.74 | 375 | 875 | 0 | 33576 |
| Random Forest, todas las variables | 1.00 | 0.99 | 1.00 | 1.00 ± 0.01 | 1.00 | 1.00 | 373 | 1 | 2 | 34450 |
| Regresión logística, sin las variables de la regla | 0.03 | 0.70 | 0.06 | 0.06 ± 0.02 | 0.06 | 0.15 | 262 | 8121 | 113 | 26330 |
| Random Forest, sin las variables de la regla | 0.52 | 0.08 | 0.14 | 0.16 ± 0.07 | 0.31 | 0.34 | 31 | 29 | 344 | 34422 |
