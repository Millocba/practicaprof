"""Detección de anomalías: reglas base, modelo de ML y evaluación contra el ground truth.

Qué es este paquete
-------------------
Un "paquete" de Python es una carpeta con varios archivos de código (módulos) que
trabajan juntos. Este paquete, `deteccion`, toma los datos sintéticos de una flota
ficticia (vehículos, cargas de combustible, GPS, solicitudes y facturas) y busca
situaciones que merecen revisión: las "anomalías".

Una anomalía es un registro que se aparta de lo esperado: por ejemplo, cargar más
litros de los que entran en el tanque o que el odómetro (el cuentakilómetros)
marque menos que la vez anterior. Como los datos son sintéticos, el generador
sabe exactamente qué anomalías inyectó y las guarda en `ground_truth.csv`
("verdad de referencia"). Eso permite medir qué tan bien funciona cada método.

Cómo se organizan los archivos
------------------------------
- `datos.py`: lee los archivos CSV del dataset y los deja listos en memoria.
- `reglas.py`: las reglas de control. Cada regla es un criterio explícito
  ("si pasa X, alertar") que produce alertas. Hay reglas "ingenuas" (miran un solo
  dato) y reglas "con contexto" (cruzan varias fuentes o el historial del vehículo).
- `evaluacion.py`: compara las alertas con el ground truth y calcula métricas
  (aciertos, falsas alarmas, precision, recall, F1).
- `hipotesis.py`: define las hipótesis del proyecto y decide, con los datos, si
  cada una se sostiene (si la regla con contexto mejora a la ingenua).
- `modelo.py`: detección con aprendizaje automático no supervisado (Isolation
  Forest) y su comparación con las reglas.
- `priorizacion.py`: ordena las cargas de más a menos sospechosa para que un
  auditor revise primero las más probables; agrega un modelo supervisado.
- `__main__.py`: permite ejecutar todo desde la terminal con `python -m deteccion`.

Importante: ninguna regla ni modelo "espía" el ground truth del dataset que se
evalúa. El ground truth solo se usa al final, para calificar los resultados.
"""
