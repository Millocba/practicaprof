"""Priorización de la revisión: qué cargas y qué vehículos auditar primero.

Un auditor no revisa cientos de alertas: revisa las N más sospechosas. Por eso los
métodos se comparan por lo que encuentran con un presupuesto de revisión (curva de
esfuerzo), no solo por precision y recall.

Métodos:
- Reglas ingenuas / Reglas con contexto: marcan o no; se revisan primero las marcadas.
- Isolation Forest: no supervisado, puntaje de rareza sin ver etiquetas.
- Modelo supervisado: Random Forest entrenado con datasets de OTRAS semillas, como si
  aprendiera de auditorías anteriores ya resueltas, y aplicado al dataset actual.
- Combinado: primero lo que marcan las reglas con contexto, ordenado por la
  probabilidad del modelo supervisado; después el resto, por esa misma probabilidad.

Ninguna variable ni regla usa el ground truth del dataset evaluado.

Para qué sirve este archivo
---------------------------
Detectar no alcanza: en la práctica el tiempo de revisión es limitado. Este módulo
le asigna a cada carga un "puntaje de prioridad" según cada método (`puntuar`),
arma la lista ordenada de qué revisar primero (`cola_de_revision`,
`vehiculos_prioritarios`, `facturas_a_revisar`) y mide cuántas anomalías reales se
encuentran según cuántas cargas se revisan (`curva_de_esfuerzo`). Usa las reglas de
`reglas.py` y las variables e Isolation Forest de `modelo.py`. Lo usan `__main__.py`
(opción --ml) y la página de priorización de la aplicación.

Modelo supervisado y Random Forest
----------------------------------
- Un modelo "supervisado" aprende de ejemplos ya resueltos: se le muestran muchas
  cargas junto con la respuesta ("era anomalía" / "era normal") y aprende qué
  combinaciones de variables suelen indicar una anomalía. Después, ante cargas nuevas,
  estima la probabilidad de que cada una sea anómala.
- Random Forest ("bosque aleatorio") es un modelo de ese tipo formado por muchos
  árboles de decisión (secuencias de preguntas del estilo "¿cargó más de 1,05
  tanques?"). Cada árbol aprende con una parte distinta de los datos y la respuesta
  final es el promedio de todos, lo que lo hace más estable que un árbol solo.
- Para no hacer trampa, se entrena con datasets generados con otras semillas y se
  evalúa en el dataset actual, que el modelo nunca vio.
"""
import tempfile

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from deteccion.datos import cargar_dataset
from deteccion.modelo import (
    VARIABLES,
    VARIABLES_CONTEXTO,
    construir_variables,
    entrenar_isolation_forest,
    ids_con_anomalia_de_comportamiento,
)
from deteccion.reglas import ejecutar_reglas

# Qué reglas de `reglas.py` forman cada grupo: las ingenuas, sus versiones con
# contexto y las de conciliación de facturas (que se priorizan por factura, no por carga).
REGLAS_INGENUAS = ["litros_mayor_a_tanque", "odometro_disminuye", "salto_historial_vehiculo",
                   "fraccionamiento_diario", "rendimiento_bajo_odometro", "carga_lejos_de_base",
                   "carga_sin_solicitud_previa", "litros_superan_autorizado"]
REGLAS_CONTEXTO = ["exceso_sin_antecedente", "retroceso_con_contexto", "salto_con_contexto",
                   "fraccionamiento_sin_recorrido", "rendimiento_bajo_gps", "carga_vehiculo_inactivo",
                   "carga_lejos_del_gps", "carga_sin_autorizacion", "supera_autorizado_con_tolerancia"]
REGLAS_FACTURACION = ["factura_no_concilia", "linea_sin_consumo", "linea_duplicada", "sobreprecio"]

METODOS = ["Reglas ingenuas", "Reglas con contexto", "Isolation Forest", "Modelo supervisado", "Combinado"]
# "Presupuesto de revisión": cantidad de cargas que un auditor alcanzaría a revisar.
PRESUPUESTOS = [25, 50, 100, 200]

# Semillas de los datasets con los que aprende el modelo supervisado ("auditorías
# anteriores"); deben ser distintas de la del dataset que se evalúa.
SEMILLAS_ENTRENAMIENTO = [1001, 1002, 1003]


def _variables_y_reglas(dataset):
    """Calcula, para un dataset, la tabla de variables del modelo y las alertas de todas las reglas.

    Recibe el diccionario que devuelve `datos.cargar_dataset` y devuelve (variables, alertas).
    """
    variables = construir_variables(dataset["flota"], dataset["consumo"], dataset.get("estaciones"),
                                    dataset.get("telemetria_diaria"), dataset.get("solicitudes"))
    alertas = ejecutar_reglas(dataset["flota"], dataset["consumo"], dataset.get("estaciones"),
                              dataset.get("telemetria_diaria"), dataset.get("solicitudes"),
                              dataset.get("facturacion"), dataset.get("facturacion_detalle"))
    return variables, alertas


def datos_de_entrenamiento(semillas=SEMILLAS_ENTRENAMIENTO, n_flota=200):
    """Genera datasets realistas con otras semillas y devuelve (variables, etiqueta).

    Simula "auditorías anteriores ya resueltas": para cada semilla genera un dataset
    nuevo en una carpeta temporal (que se borra al terminar), calcula sus variables y
    toma de su ground truth la etiqueta (1 = anomalía de comportamiento, 0 = normal).
    Recibe la lista de semillas y la cantidad de vehículos por dataset.
    Devuelve dos objetos alineados fila por fila: la tabla de variables y la etiqueta.
    """
    # Se importa acá adentro porque generar datos solo hace falta para entrenar
    from generator_pipeline_maestro import GeneradorMaestro

    partes_x, partes_y = [], []
    for semilla in semillas:
        with tempfile.TemporaryDirectory() as directorio:
            resultado = GeneradorMaestro(n_flota=n_flota, seed=semilla, output_dir=directorio,
                                         escenario="realista").ejecutar()
            if not resultado["exito"]:
                raise RuntimeError(resultado["error"])
            dataset = cargar_dataset(directorio)
        variables = construir_variables(dataset["flota"], dataset["consumo"], dataset["estaciones"],
                                        dataset["telemetria_diaria"], dataset["solicitudes"])
        anomalas = ids_con_anomalia_de_comportamiento(dataset["ground_truth"])
        partes_x.append(variables)
        partes_y.append(pd.Series(variables.index.isin(list(anomalas)).astype(int), index=variables.index))
    return pd.concat(partes_x, ignore_index=True), pd.concat(partes_y, ignore_index=True)


def entrenar_supervisado(variables, etiqueta, seed=42):
    """Entrena el modelo supervisado (Random Forest) con ejemplos ya etiquetados.

    Recibe: la tabla de variables, la etiqueta (1 = anomalía, 0 = normal) y una semilla.
    Devuelve: el modelo entrenado, listo para estimar probabilidades en otro dataset.
    """
    # min_samples_leaf=2: cada "hoja" del árbol necesita al menos 2 ejemplos, para que
    # no memorice casos sueltos. class_weight="balanced_subsample": como las anomalías
    # son muy pocas (cerca del 1%), se les da más peso; si no, el modelo aprendería que
    # decir siempre "normal" casi nunca falla. n_jobs=-1 usa todos los núcleos del procesador.
    modelo = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                    random_state=seed, n_jobs=-1)
    modelo.fit(variables, etiqueta)
    return modelo


def importancia_de_variables(modelo, columnas):
    """Qué variables usó más el modelo supervisado para decidir, de mayor a menor.

    Recibe el modelo entrenado y los nombres de sus columnas. Devuelve una tabla con
    cada variable, su importancia (las importancias suman 1) y su descripción en
    palabras. Sirve para explicar el modelo: un auditor necesita saber en qué se basa.
    """
    descripciones = {**VARIABLES, **VARIABLES_CONTEXTO}
    return (pd.DataFrame({"variable": columnas, "importancia": modelo.feature_importances_})
            .assign(descripcion=lambda d: d["variable"].map(descripciones))
            .sort_values("importancia", ascending=False, ignore_index=True))


def puntuar(dataset, modelo_supervisado, seed=42):
    """Puntaje de prioridad de cada transacción según cada método (más alto = revisar antes).

    Recibe: el dataset a evaluar y el modelo supervisado ya entrenado (con otras semillas).
    Devuelve: (puntajes, variables, alertas). `puntajes` es una tabla con una fila por
    carga y una columna por método de METODOS.
    """
    variables, alertas = _variables_y_reglas(dataset)
    # Las reglas solo marcan sí/no: se convierten en puntaje 1 (marcada) o 0 (no marcada)
    ingenuas = variables.index.isin(list(alertas.loc[alertas["regla"].isin(REGLAS_INGENUAS), "id_registro"]))
    contexto = variables.index.isin(list(alertas.loc[alertas["regla"].isin(REGLAS_CONTEXTO), "id_registro"]))
    rareza, _ = entrenar_isolation_forest(variables, seed=seed)
    # predict_proba da, para cada carga, la probabilidad de cada clase; [:, 1] toma la
    # de "anomalía". Se pasan las columnas en el mismo orden con que se entrenó.
    probabilidad = modelo_supervisado.predict_proba(variables[modelo_supervisado.feature_names_in_])[:, 1]

    puntajes = pd.DataFrame({
        "Reglas ingenuas": ingenuas.astype(float),
        "Reglas con contexto": contexto.astype(float),
        "Isolation Forest": rareza.values,
        "Modelo supervisado": probabilidad,
        # La probabilidad está entre 0 y 1: sumar 1 a las marcadas por las reglas con
        # contexto las pone siempre primero, ordenadas entre sí por la probabilidad.
        "Combinado": contexto.astype(float) + probabilidad,
    }, index=variables.index)
    return puntajes, variables, alertas


def _orden(puntaje):
    """Índice ordenado de mayor a menor puntaje; los empates se resuelven por id.

    Resolver los empates siempre igual hace que el orden sea reproducible: con las
    reglas hay muchas cargas con el mismo puntaje (1 o 0).
    """
    # "mergesort" es un ordenamiento estable: ante empates respeta el orden previo (por id)
    return puntaje.sort_index().sort_values(ascending=False, kind="mergesort").index


def curva_de_esfuerzo(puntajes, ground_truth, casos_legitimos=None, maximo=None):
    """Para cada método y cada cantidad k de cargas revisadas: anomalías encontradas y
    casos legítimos revisados en vano.

    La "curva de esfuerzo" responde: si reviso las k cargas con mayor puntaje, ¿cuántas
    anomalías encuentro? Para cada k da también el recall (qué parte del total
    encontré) y la precision (qué parte de lo revisado era anomalía). Un buen método
    encuentra muchas anomalías con k chico.

    Recibe: los puntajes de `puntuar`, el ground truth, los casos legítimos y hasta qué
    k calcular. Devuelve una tabla con una fila por método y por k.
    """
    anomalas = ids_con_anomalia_de_comportamiento(ground_truth)
    legitimos = set(casos_legitimos["id_registro"]) if casos_legitimos is not None else set()
    maximo = min(maximo or len(puntajes), len(puntajes))
    total = len(anomalas)
    filas = []
    for metodo in puntajes.columns:
        orden = _orden(puntajes[metodo])[:maximo]
        es_anomala = np.fromiter((i in anomalas for i in orden), dtype=int)
        es_legitima = np.fromiter((i in legitimos for i in orden), dtype=int)
        k = np.arange(1, maximo + 1)
        # cumsum = suma acumulada: en la posición k, cuántas anomalías hubo entre las primeras k
        encontradas = es_anomala.cumsum()
        filas.append(pd.DataFrame({
            "metodo": metodo, "revisadas": k, "encontradas": encontradas,
            "recall": encontradas / total if total else np.nan,
            "precision": encontradas / k, "legitimos_revisados": es_legitima.cumsum(),
        }))
    return pd.concat(filas, ignore_index=True)


def resumen_por_presupuesto(curva, presupuestos=PRESUPUESTOS):
    """Filas de la curva en cada presupuesto de revisión.

    Resume la curva completa quedándose solo con k = 25, 50, 100 y 200 (u otros
    valores que se pasen), para comparar los métodos en una tabla chica.
    """
    return curva[curva["revisadas"].isin(presupuestos)].reset_index(drop=True)


def motivos(variables, alertas):
    """Explicación legible de por qué una carga es sospechosa, por transacción.

    Traduce los números de las variables a frases ("cargó 130% del tanque", "vehículo
    inactivo") y agrega qué reglas con contexto la marcaron. Es la parte de
    "explicabilidad": un modelo que solo da un puntaje no le dice al auditor qué mirar.
    Devuelve una tabla por id de carga con las columnas `motivos` y `reglas`.
    """
    v = variables
    partes = pd.DataFrame(index=v.index)

    def agregar(condicion, texto):
        """Agrega una columna de texto que solo aparece en las cargas donde se cumple `condicion`."""
        partes[len(partes.columns)] = np.where(condicion, texto, "")

    agregar(v["ratio_litros_tanque"] > 1,
            "cargó " + (v["ratio_litros_tanque"] * 100).round().astype(int).astype(str) + "% del tanque")
    if "litros_vs_habitual" in v:
        agregar(v["litros_vs_habitual"] > 2,
                v["litros_vs_habitual"].round(1).astype(str) + "× su carga habitual")
        agregar((v["cargas_en_el_dia"] >= 2) & (v["tanques_en_el_dia"] > 1.05),
                v["cargas_en_el_dia"].astype(int).astype(str) + " cargas el mismo día ("
                + v["tanques_en_el_dia"].round(1).astype(str) + " tanques)")
        agregar(v["rendimiento_relativo"] < 0.4,
                "rendimiento " + (v["rendimiento_relativo"] * 100).round().astype(int).astype(str)
                + "% del habitual")
        agregar(v["retroceso_km"] > 0, "odómetro retrocede " + v["retroceso_km"].round().astype(int).astype(str) + " km")
        agregar(v["vehiculo_inactivo"] == 1, "vehículo inactivo")
    if "sin_solicitud" in v:
        agregar(v["sin_solicitud"] == 1, "sin solicitud aprobada")
        agregar(v["litros_vs_autorizado"] > 1.05,
                "cargó " + (v["litros_vs_autorizado"] * 100).round().astype(int).astype(str) + "% de lo autorizado")
    agregar(v["exceso_km"] > 1000,
            v["exceso_km"].round().astype(int).astype(str) + " km más de lo habitual")
    if "distancia_gps_km" in v:
        agregar(v["distancia_gps_km"] > 50,
                "a " + v["distancia_gps_km"].round().astype(int).astype(str) + " km del recorrido del GPS")
    if "distancia_zona_km" in v:
        sin_gps = v["sin_gps"] == 1 if "sin_gps" in v else True
        agregar((v["distancia_zona_km"] > 50) & sin_gps,
                "a " + v["distancia_zona_km"].round().astype(int).astype(str) + " km de su zona habitual (sin GPS)")

    # Une, para cada carga, todas las frases que no quedaron vacías
    texto = partes.apply(lambda fila: "; ".join(t for t in fila if t), axis=1)
    reglas = (alertas[alertas["regla"].isin(REGLAS_CONTEXTO)]
              .groupby("id_registro")["regla"].apply(lambda r: ", ".join(sorted(set(r)))))
    return pd.DataFrame({"motivos": texto, "reglas": reglas.reindex(v.index).fillna("")})


def cola_de_revision(puntajes, metodo, consumo, variables, alertas, cantidad=50):
    """Las `cantidad` cargas a revisar primero según `metodo`, con sus motivos.

    Es la "lista de trabajo" del auditor: una tabla con los datos básicos de cada
    carga (vehículo, fecha, estación, litros, odómetro), su posición en la cola
    (`prioridad`), su puntaje y la explicación de `motivos`.
    """
    orden = _orden(puntajes[metodo])[:cantidad]
    datos = consumo.set_index("id").loc[orden, ["vehiculo_id", "fecha", "estacion", "litros", "odometro"]]
    return (datos.join(motivos(variables.loc[orden], alertas))
            .assign(prioridad=range(1, len(orden) + 1), puntaje=puntajes.loc[orden, metodo].round(3))
            .reset_index().rename(columns={"index": "id"}))


def vehiculos_prioritarios(puntajes, metodo, consumo, cantidad_cargas=100):
    """Vehículos ordenados por cuántas de sus cargas quedan entre las `cantidad_cargas` más sospechosas.

    Sirve para auditar por vehículo en lugar de carga por carga: un vehículo con
    varias cargas sospechosas suele merecer más atención que uno con una sola. Los
    empates se desempatan por el puntaje más alto de sus cargas.
    """
    orden = _orden(puntajes[metodo])[:cantidad_cargas]
    vehiculo = consumo.set_index("id")["vehiculo_id"]
    top = pd.DataFrame({"vehiculo_id": vehiculo.loc[orden].values, "puntaje": puntajes.loc[orden, metodo].values})
    return (top.groupby("vehiculo_id")
            .agg(cargas_sospechosas=("puntaje", "size"), puntaje_maximo=("puntaje", "max"))
            .sort_values(["cargas_sospechosas", "puntaje_maximo"], ascending=False)
            .reset_index())


def recall_por_tipo(puntajes, ground_truth, presupuesto):
    """Qué fracción de cada tipo de anomalía encuentra cada método revisando `presupuesto` cargas.

    Muestra en qué tipo de problema es bueno cada método (por ejemplo, uno puede
    encontrar todos los excesos de tanque pero ningún fraccionamiento). Devuelve una
    tabla con una fila por método y tipo de anomalía.
    """
    comportamiento = ground_truth[ground_truth["id_registro"].isin(ids_con_anomalia_de_comportamiento(ground_truth))]
    filas = []
    for metodo in puntajes.columns:
        revisadas = set(_orden(puntajes[metodo])[:presupuesto])
        for tipo, grupo in comportamiento.groupby("tipo_anomalia"):
            ids = set(grupo["id_registro"])
            filas.append({"metodo": metodo, "tipo_anomalia": tipo, "reales": len(ids),
                          "encontradas": len(ids & revisadas), "recall": len(ids & revisadas) / len(ids)})
    return pd.DataFrame(filas)


def facturas_a_revisar(facturacion, facturacion_detalle, alertas):
    """Facturas con hallazgos de conciliación, ordenadas por el importe comprometido.

    Resume por factura las alertas del encabezado y de sus líneas (sin consumo,
    duplicadas, sobreprecio) y estima el importe en juego.

    Recibe: las facturas (encabezados), sus líneas y las alertas de las reglas.
    Devuelve: una tabla con una fila por factura con hallazgos (proveedor, período,
    total, cantidad de hallazgos, qué reglas la marcaron e importe en juego), o una
    tabla vacía si no hay datos de facturación. Ordenar por dinero comprometido
    ayuda a revisar primero lo de mayor impacto.
    """
    if facturacion is None or facturacion_detalle is None:
        return pd.DataFrame()
    # Las alertas de líneas traen el número de línea; se traducen a su factura. Las
    # alertas del encabezado ya traen el número de factura y quedan como están.
    factura_de = dict(zip(facturacion_detalle["numero_linea"], facturacion_detalle["numero_factura"]))
    importe_linea = facturacion_detalle.set_index("numero_linea")["importe"]
    hallazgos = alertas[alertas["regla"].isin(REGLAS_FACTURACION)].copy()
    hallazgos["numero_factura"] = hallazgos["id_registro"].map(factura_de).fillna(hallazgos["id_registro"])
    lineas = facturacion_detalle.groupby("numero_factura")["importe"].sum()
    encabezado = facturacion.set_index("numero_factura")
    diferencia = (encabezado["total_monto"] - lineas.reindex(encabezado.index)).round(2)

    def en_juego(grupo):
        """Importe comprometido de una factura: sus líneas alertadas más la diferencia
        entre el total y la suma de líneas, si el encabezado no concilia."""
        propias = grupo[grupo["id_registro"].isin(importe_linea.index)]
        monto = importe_linea.loc[propias["id_registro"]].sum()
        if (grupo["regla"] == "factura_no_concilia").any():
            monto += abs(diferencia.get(grupo.name, 0))
        return round(monto, 2)

    resumen = hallazgos.groupby("numero_factura").apply(lambda g: pd.Series({
        "hallazgos": len(g),
        "detalle": "; ".join(sorted(set(g["regla"]))),
        "importe_en_juego": en_juego(g),
    }), include_groups=False)
    return (encabezado[["proveedor", "periodo", "total_monto"]].join(resumen, how="inner")
            .sort_values("importe_en_juego", ascending=False).reset_index())
