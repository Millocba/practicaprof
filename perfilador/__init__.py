"""Perfilador de fuentes: estructura y calidad agregadas, sin filas ni valores reales.

Ver docs/REAL_DATA_BOUNDARY.md y perfiles/README.md.

Qué es este paquete
-------------------
Un "paquete" de Python es una carpeta con varios archivos de código que se usan juntos.
Este archivo (__init__.py) es el que convierte a la carpeta `perfilador/` en un paquete:
Python lo lee primero cuando alguien escribe `import perfilador`. No tiene código propio,
solo esta descripción.

Para qué sirve el perfilador
----------------------------
El proyecto trabaja con datos sintéticos (inventados) de una flota de vehículos. Para que
esos datos se parezcan a los de una fuente real sin traer nunca datos reales al proyecto,
el perfilador lee archivos (CSV o Excel) y produce un "perfil agregado": un resumen de su
estructura y su calidad (qué columnas hay, de qué tipo, cuántos vacíos, qué formatos...)
sin copiar ninguna fila ni ningún valor que permita reconocer a alguien o algo.

Cómo se reparte el trabajo entre los archivos
---------------------------------------------
- `perfil.py`: arma el perfil agregado de un conjunto de tablas y aplica las reglas de
  privacidad (bandas, redondeos, agrupación de casos infrecuentes, columnas sensibles).
- `comparar.py`: compara el perfil de una fuente real con el de los datos sintéticos y
  arma la lista de "brechas" (diferencias) con sugerencias para mejorar el generador.
- `__main__.py`: permite usar todo lo anterior desde la línea de comandos con
  `python -m perfilador ...` (perfilar, aprobar y comparar).

La aplicación Streamlit (página "Perfil de fuentes") usa estas mismas funciones.
"""
