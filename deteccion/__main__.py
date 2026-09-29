"""Evalúa la detección sobre un dataset del pipeline maestro.

Uso:
    python -m deteccion                              # datasets/synthetics_maestro (didáctico)
    python -m deteccion --escenario realista         # datasets/synthetics_realista, con hipótesis
    python -m deteccion --escenario realista --ml    # además, priorización por presupuesto
    python -m deteccion --datos otra/carpeta
    python -m deteccion --salida results/deteccion   # guarda métricas y alertas
"""
# Nota: el texto de arriba (el docstring del módulo) se muestra tal cual como ayuda
# cuando se ejecuta `python -m deteccion --help`, por eso las explicaciones para
# quien lee el código van en estos comentarios y no dentro de él.
#
# Para qué sirve este archivo
# ---------------------------
# Un archivo llamado `__main__.py` dentro de un paquete es el que Python ejecuta
# cuando se escribe `python -m deteccion` en la terminal. Es el "programa principal":
# no define reglas ni modelos, sino que usa los demás módulos en orden:
#   1. `datos.py` para leer el dataset,
#   2. `reglas.py` para generar las alertas,
#   3. `evaluacion.py` para compararlas con el ground truth,
#   4. `hipotesis.py` (escenario realista) para decidir qué hipótesis se sostienen,
#   5. `priorizacion.py` (opción --ml) para comparar métodos de priorización.
# Al final imprime tablas con los resultados y, si se pide, las guarda en CSV.
#
# Escenarios: el "didáctico" tiene anomalías muy evidentes (para explicar el método)
# y el "realista" tiene anomalías sutiles y casos legítimos que se parecen a ellas.
import argparse
from pathlib import Path

import pandas as pd

from deteccion.datos import cargar_dataset
from deteccion.evaluacion import evaluar_por_regla, evaluar_por_tipo
from deteccion.reglas import ejecutar_reglas

# Carpeta raíz del proyecto (dos niveles arriba de este archivo) y la carpeta de
# datos que corresponde a cada escenario por defecto.
RAIZ = Path(__file__).parent.parent
DIRECTORIOS = {"didactico": RAIZ / "datasets" / "synthetics_maestro",
               "realista": RAIZ / "datasets" / "synthetics_realista"}


def main():
    """Ejecuta la evaluación completa desde la línea de comandos.

    No recibe parámetros directamente: lee las opciones que se escribieron en la
    terminal (--escenario, --datos, --ml, --salida). No devuelve nada; imprime en
    pantalla las métricas por tipo de anomalía, por regla, el veredicto de las
    hipótesis y, opcionalmente, la comparación de métodos de priorización.
    """
    # argparse es la herramienta estándar de Python para leer las opciones que el
    # usuario escribe después del comando (por ejemplo `--escenario realista`).
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--escenario", choices=list(DIRECTORIOS), default="didactico")
    parser.add_argument("--datos", type=Path, help="carpeta del dataset (por defecto, la del escenario)")
    parser.add_argument("--ml", action="store_true", help="compara los métodos de priorización (escenario realista)")
    parser.add_argument("--salida", type=Path, help="carpeta donde guardar métricas y alertas")
    args = parser.parse_args()
    carpeta = args.datos or DIRECTORIOS[args.escenario]

    # Si faltan los archivos mínimos, se corta con un mensaje que explica cómo generarlos.
    faltantes = [f for f in ["flota.csv", "consumo.csv", "ground_truth.csv"] if not (carpeta / f).exists()]
    if faltantes:
        parser.error(f"faltan {', '.join(faltantes)} en {carpeta}; generá los datos con "
                     f"`python generator_pipeline_maestro.py --escenario {args.escenario}`")

    # Paso 1 y 2: leer los datos y aplicar todas las reglas. Las reglas no ven el
    # ground truth; solo reciben las tablas "operativas".
    datos = cargar_dataset(carpeta)
    flota, consumo, ground_truth = datos["flota"], datos["consumo"], datos["ground_truth"]
    alertas = ejecutar_reglas(flota, consumo, datos["estaciones"], datos["telemetria_diaria"],
                              datos["solicitudes"], datos["facturacion"], datos["facturacion_detalle"])
    # Paso 3: recién ahora se compara lo alertado con el ground truth.
    por_tipo = evaluar_por_tipo(alertas, ground_truth)
    por_regla = evaluar_por_regla(alertas, ground_truth)

    pd.set_option("display.width", 180)
    pd.set_option("display.float_format", "{:.3f}".format)
    print(f"Datos: {carpeta}  ({len(consumo)} transacciones, {len(ground_truth)} anomalías)\n")
    print("Por tipo de anomalía (todas las reglas del tipo juntas):")
    print(por_tipo.to_string(index=False))
    print("\nPor regla:")
    print(por_regla.to_string(index=False))

    # Paso 4: el archivo de casos legítimos solo existe en el escenario realista;
    # si está, se contrastan las hipótesis (regla ingenua contra regla con contexto).
    veredictos = None
    if datos["casos_legitimos"] is not None:
        from deteccion.hipotesis import contrastar_hipotesis
        _, veredictos = contrastar_hipotesis(alertas, ground_truth, datos["casos_legitimos"],
                                             datos["facturacion_detalle"])
        print("\nHipótesis (regla ingenua vs. regla con contexto):")
        print(veredictos.to_string(index=False))

    # Paso 5 (opcional, --ml): entrenar un modelo supervisado y ver cuántas
    # anomalías encuentra cada método si solo se pueden revisar N cargas.
    resumen_ml = None
    if args.ml:
        if datos["casos_legitimos"] is None:
            parser.error("--ml requiere el escenario realista")
        import json
        from deteccion import priorizacion
        # La "semilla" es el número que usó el generador para producir este dataset;
        # la misma semilla siempre produce los mismos datos.
        metadata = carpeta / "metadata.json"
        semilla = json.loads(metadata.read_text(encoding="utf-8")).get("seed") if metadata.exists() else None
        # El modelo se entrena con otras semillas: nunca con el dataset que se evalúa
        # (si aprendiera de las mismas respuestas con que se lo califica, el resultado
        # sería engañosamente bueno).
        semillas = [s for s in priorizacion.SEMILLAS_ENTRENAMIENTO + [1004] if s != semilla][:3]
        variables, etiqueta = priorizacion.datos_de_entrenamiento(semillas)
        modelo = priorizacion.entrenar_supervisado(variables, etiqueta)
        puntajes, _, _ = priorizacion.puntuar(datos, modelo)
        curva = priorizacion.curva_de_esfuerzo(puntajes, ground_truth, datos["casos_legitimos"], maximo=200)
        resumen_ml = priorizacion.resumen_por_presupuesto(curva)
        print("\nPriorización: anomalías encontradas según cuántas cargas se revisan")
        print(resumen_ml.pivot(index="metodo", columns="revisadas", values="encontradas").to_string())
        print("\nCasos legítimos revisados en vano")
        print(resumen_ml.pivot(index="metodo", columns="revisadas", values="legitimos_revisados").to_string())

    # Si se indicó --salida, se guardan todas las tablas como CSV para usarlas después.
    if args.salida:
        args.salida.mkdir(parents=True, exist_ok=True)
        por_tipo.to_csv(args.salida / "metricas_por_tipo.csv", index=False)
        por_regla.to_csv(args.salida / "metricas_por_regla.csv", index=False)
        alertas.to_csv(args.salida / "alertas.csv", index=False)
        if veredictos is not None:
            veredictos.to_csv(args.salida / "hipotesis.csv", index=False)
        if resumen_ml is not None:
            resumen_ml.to_csv(args.salida / "priorizacion.csv", index=False)
        print(f"\nResultados guardados en {args.salida}")


# Esta condición es verdadera solo cuando el archivo se ejecuta como programa
# (y no cuando otro módulo lo importa).
if __name__ == "__main__":
    main()
