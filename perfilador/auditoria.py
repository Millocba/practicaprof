"""Corrida de las reglas y los modelos sobre las fuentes reales, con salida solo agregada.

Se ejecuta junto a los datos, como el perfilador. Traduce las fuentes al esquema del generador
(`perfilador.adaptador`), corre las reglas de las hipótesis y los modelos de priorización y devuelve
únicamente agregados: cantidades y porcentajes por regla e hipótesis (los de 1 a 19 casos, como
"1–19"), cuantiles redondeados de las variables del modelo, coincidencias entre métodos y
diagnósticos de la traducción. Ninguna carga, vehículo, persona ni identificador sale del entorno.

Sin etiquetas reales no hay precisión ni recall: lo que se mide es cuánto marca cada regla, cuánto
se parecen las variables reales a las sintéticas y cuánto coinciden los métodos.
"""
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from deteccion.datos import cargar_dataset
from deteccion.hipotesis import hipotesis_del_escenario, reglas_de
from deteccion.modelo import construir_variables, entrenar_isolation_forest, ids_con_anomalia_de_comportamiento
from deteccion.priorizacion import REGLAS_CONTEXTO, entrenar_supervisado
from deteccion.reglas import (ESTACION_AJENA, FRACCION_INICIAL, GRUPO_DEPOSITO, ORIGEN_CONTINGENCIA, _vecinos_de_odometro,
                              cargas_exceptuadas, cargas_fuera_del_reporte, cruzar_registro, detectar_doble_cobro,
                              detectar_duplicados, distancia_uno, leer_fecha, moviles_por_sufijo_de_motor,
                              normalizar_dominio, pares_de_contingencia, reglas_del_dataset, secuencia_odometro,
                              subforma_de_los_retrocesos, TOLERANCIA_EXCESO_TANQUE, vinculos_de_la_carga,
                              vinculos_del_pedido, vinculos_por_identificador)
from perfilador.adaptador import adaptar
from perfilador.controles import acotar
from perfilador.perfil import MINIMO_GRUPO, VERSION, cuantil_publicable, dos_cifras

SEMILLAS_ENTRENAMIENTO = (1001, 1002, 1003)
REVISION = 100          # tamaño de la cola con que se comparan los métodos
COBERTURA_MES_COMPLETO = 0.9   # un mes está completo si el reporte trae cargas en el 90% de sus días...
ULTIMOS_DIAS_DEL_MES = 3       # ...y en alguno de sus últimos 3 días (un mes en curso no está completo)

# Bandas de |Δ| (minutos) del cruce con el registro (H8): hasta 3 h, 3-6 h, 6-12 h, 12-24 h y nada
BANDAS_CRUCE_TIEMPO = ("hasta_3_horas", "de_3_a_6_horas", "de_6_a_12_horas", "de_12_a_24_horas",
                       "ninguno_a_menos_de_24_horas")
CORTES_CRUCE_MINUTOS = (180, 360, 720, 1440)
# Bandas de |Δ| de los pares que sí cruzan (H8)
BANDAS_CRUCE_QUE_CRUZAN = ("hasta_5", "de_5_a_30", "de_30_a_60", "de_1_a_3_horas", "mas_de_3_horas")
CORTES_QUE_CRUZAN = (5, 30, 60, 180)
# Bandas del cociente precio facturado / precio unitario del reporte (H9; el corte es de la banda de arriba)
BANDAS_PRECIO_FACTURADO = ("menos_de_0_95", "de_0_95_a_0_98", "de_0_98_a_1_00", "de_1_00_a_1_02", "mas_de_1_02")
CORTES_PRECIO_FACTURADO = (0.95, 0.98, 1.00, 1.02)
# Bandas de la razón entre los dos precios unitarios del reporte (el segundo sobre el primero)
BANDAS_RAZON_ENTRE_PRECIOS = ("menos_de_0_97", "de_0_97_a_0_98", "exactamente_0_98", "de_0_98_a_0_99",
                              "mas_de_0_99")
VALOR_RAZON_ENTRE_PRECIOS = 0.98
TOLERANCIA_RAZON_ENTRE_PRECIOS = 0.0005
# Bandas de la diferencia relativa de importes (H9)
BANDAS_DIFERENCIA_IMPORTES = ("exacta", "hasta_0_1_pct", "de_0_1_a_0_5_pct", "de_0_5_a_2_pct", "mas_de_2_pct")
CORTES_DIFERENCIA_IMPORTES = (0.001, 0.005, 0.02)


def meses_completos(fechas):
    """Meses que el reporte cubre de principio a fin, según los días con cargas."""
    dias = pd.Series(pd.to_datetime(fechas).dt.normalize().unique())
    mes = dias.dt.to_period("M")
    cubiertos = dias.groupby(mes).nunique()
    ultimo = dias.groupby(mes).max().dt.day
    largo = pd.Series([p.days_in_month for p in cubiertos.index], index=cubiertos.index)
    completos = (cubiertos >= COBERTURA_MES_COMPLETO * largo) & (ultimo > largo - ULTIMOS_DIAS_DEL_MES)
    return {str(p) for p in completos[completos].index}


def _pct(n, total):
    """Porcentaje con un decimal, solo si el grupo tiene al menos MINIMO_GRUPO casos."""
    return round(100 * n / total, 1) if total and n >= MINIMO_GRUPO else None


def _cuantiles(serie, cuantiles=(0.05, 0.5, 0.95)):
    """Cuantiles redondeados; los que dejarían menos de MINIMO_GRUPO casos de un lado quedan en None."""
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    if len(serie) < MINIMO_GRUPO:
        return None
    return {f"p{int(q * 100):02d}": dos_cifras(float(serie.quantile(q))) if cuantil_publicable(q, len(serie)) else None
            for q in cuantiles}


def _variables(datos):
    """Variables del modelo con las mismas fuentes que tiene la fuente real (sin estaciones ni GPS diario)."""
    return construir_variables(datos["flota"], datos["consumo"], None, None, datos.get("solicitudes"),
                               datos.get("excepciones_odometro"))


def _modelo_sintetico(semillas, n_flota):
    """Random Forest entrenado con datasets sintéticos, con las mismas fuentes disponibles que la real."""
    from generator_pipeline_maestro import GeneradorMaestro

    partes_x, partes_y, referencia = [], [], None
    for semilla in semillas:
        # En Windows, el antivirus puede tener abierto un archivo recién escrito justo cuando se
        # borra la carpeta: sin ignore_cleanup_errors eso cortaba la auditoría. Los datos ya se
        # leyeron a memoria, así que si la carpeta no se puede borrar se deja y se sigue.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as carpeta:
            resultado = GeneradorMaestro(n_flota=n_flota, seed=semilla, output_dir=carpeta, escenario="realista").ejecutar()
            if not resultado["exito"]:
                raise RuntimeError(resultado["error"])
            sintetico = cargar_dataset(carpeta)
        variables = _variables(sintetico)
        partes_x.append(variables)
        partes_y.append(pd.Series(variables.index.isin(list(ids_con_anomalia_de_comportamiento(
            sintetico["ground_truth"]))).astype(int), index=variables.index))
        referencia = variables if referencia is None else referencia
    return entrenar_supervisado(pd.concat(partes_x, ignore_index=True), pd.concat(partes_y, ignore_index=True)), referencia


def _unidad(ids, datos):
    """Tabla a la que pertenecen los ids alertados y su tamaño."""
    for tabla, columna in [("consumo", "id"), ("solicitudes", "id"), ("facturacion", "numero_factura"),
                           ("facturacion_detalle", "numero_linea"), ("telemetria", "Alias")]:
        df = datos.get(tabla)
        if df is not None and ids and set(ids) <= set(df[columna]):
            return tabla, len(df)
    return None, 0


def _odometro(datos, alertas):
    """Excepciones de odómetro (H12): cuántos vehículos están exceptuados y cuántas cargas cubren."""
    flota, consumo = datos["flota"], datos["consumo"]
    exceptuadas = cargas_exceptuadas(consumo, flota, datos.get("excepciones_odometro"))
    sin_avance = set(alertas.loc[alertas["regla"] == "odometro_sin_avance", "id_registro"])
    sin_excepcion = set(alertas.loc[alertas["regla"] == "sin_avance_sin_excepcion", "id_registro"])
    si = flota["ExcepcionOdometro"].astype("string").str.strip().str.upper().eq("SI") \
        if "ExcepcionOdometro" in flota.columns else pd.Series(False, index=flota.index)
    return {
        "vehiculos_exceptuados_hoy": acotar(int(si.sum())),
        "cargas_con_excepcion_vigente": acotar(len(exceptuadas)),
        "cargas_sin_avance": acotar(len(sin_avance)),
        "sin_avance_con_excepcion": acotar(len(sin_avance & exceptuadas)),
        "sin_avance_el_mismo_dia_o_con_excepcion": acotar(len(sin_avance - sin_excepcion)),
        "sin_avance_sin_excepcion": acotar(len(sin_excepcion)),
    }


def _retrocesos(consumo, alertas):
    """Retrocesos del odómetro según su forma (H2): cuántos son la otra cara de un salto mal tipeado.

    Se miran con la misma secuencia de las reglas (sin duplicados ni dobles cobros) y se cuentan todos, los
    que marca la regla ingenua y los que quedan con contexto, para ver qué hay detrás de los que quedan.
    `otro` se abre en leve, sin vecinos, se queda abajo y otro patrón.
    """
    excluidas = pd.concat([detectar_duplicados(consumo)["id_registro"], detectar_doble_cobro(consumo)["id_registro"]])
    secuencia = secuencia_odometro(consumo, excluir_ids=excluidas)
    formas = subforma_de_los_retrocesos(secuencia)
    ids = secuencia["id"].reindex(formas.index)
    vehiculos = secuencia["vehiculo_id"].reindex(formas.index)
    mismo_dia = (secuencia["dias"].reindex(formas.index) == 0)
    nombres = ("tras_un_salto", "lectura_baja_aislada", "leve", "sin_vecinos", "se_queda_abajo", "otro_patron")

    def contar(marca):
        return {"total": acotar(int(marca.sum())),
                **{n: acotar(int((marca & formas.eq(n)).sum())) for n in nombres},
                "de_la_carga_del_mismo_dia": acotar(int((marca & mismo_dia).sum())),
                "vehiculos": acotar(int(vehiculos[marca].nunique()))}

    de_la_regla = lambda nombre: ids.isin(set(alertas.loc[alertas["regla"] == nombre, "id_registro"]))
    return {"todos": contar(pd.Series(True, index=formas.index)),
            "regla_ingenua": contar(de_la_regla("odometro_disminuye")),
            "con_contexto": contar(de_la_regla("retroceso_con_contexto"))}


def _retrocesos_estudio(datos, alertas):
    """Qué hay detrás de los retrocesos que quedan con contexto (H2), solo en agregado.

    Se mira la misma secuencia de `_retrocesos` (sin duplicados ni dobles cobros) y se abren los dos
    patrones que quedan: las bajas leves de días distintos (por tamaño y por si la lectura siguiente
    retoma el nivel nuevo o vuelve al viejo) y los que se quedan abajo (por tamaño de la caída, si
    tenían una excepción vigente ese día y si continúan de forma coherente desde el nivel nuevo).
    """
    consumo, flota = datos["consumo"], datos["flota"]
    excluidas = pd.concat([detectar_duplicados(consumo)["id_registro"], detectar_doble_cobro(consumo)["id_registro"]])
    secuencia = secuencia_odometro(consumo, excluir_ids=excluidas)
    s = _vecinos_de_odometro(secuencia)
    s["forma"] = subforma_de_los_retrocesos(secuencia).reindex(s.index)
    con_contexto = set(alertas.loc[alertas["regla"] == "retroceso_con_contexto", "id_registro"])
    s = s[s["id"].isin(con_contexto)]

    leve = s[(s["forma"] == "leve") & (s["dias"] > 0)]
    baja = -leve["km"]
    abajo = s[s["forma"] == "se_queda_abajo"]
    caida = -abajo["km"]
    exceptuadas = cargas_exceptuadas(consumo, flota, datos.get("excepciones_odometro"))
    # La lectura siguiente avanza de forma coherente si no retrocede y no pasa del doble de lo esperado,
    # con un piso de 500 km para no ser más estricto que eso en tramos cortos.
    avance_siguiente = abajo["siguiente"] - abajo["odometro"]
    tope = (2 * abajo["km_esperados"]).clip(lower=500)
    por_vehiculo = abajo.groupby("vehiculo_id").size()

    grupos = {
        "leve_en_dias_distintos": {
            "total": acotar(len(leve)),
            "por_baja": {"menos_de_10": acotar(int((baja < 10).sum())),
                         "de_10_a_100": acotar(int(baja.between(10, 100, inclusive="left").sum())),
                         "de_100_a_500": acotar(int(baja.between(100, 500).sum()))},
            "retoma_desde_el_nuevo": acotar(int((leve["siguiente"] < leve["anterior"]).sum())),
            "vuelve_al_valor_viejo": acotar(int((leve["siguiente"] >= leve["anterior"]).sum())),
        },
        "se_queda_abajo": {
            "total": acotar(len(abajo)),
            "vehiculos": acotar(int(abajo["vehiculo_id"].nunique())),
            "por_caida": {"de_500_a_5000": acotar(int(caida.between(500, 5000, inclusive="right").sum())),
                          "de_5000_a_50000": acotar(int(caida.between(5000, 50000, inclusive="right").sum())),
                          "mas_de_50000": acotar(int((caida > 50000).sum()))},
            "con_excepcion_vigente": acotar(int(abajo["id"].isin(exceptuadas).sum())),
            "continua_coherente": acotar(int(avance_siguiente.between(0, tope).sum())),
            "vehiculos_por_casos": {"1": acotar(int((por_vehiculo == 1).sum())),
                                    "2": acotar(int((por_vehiculo == 2).sum())),
                                    "3_o_mas": acotar(int((por_vehiculo >= 3).sum()))},
        },
    }
    return {nombre: _protege_el_total(grupo) for nombre, grupo in grupos.items()}


# Cómo coinciden los litros de cada contingencia con su carga habitual cercana más parecida (H13), en orden:
# la contingencia se clasifica por el primero que cumple con alguna de sus cargas cercanas
LITROS_DE_CONTINGENCIA = ("iguales", "hasta_2_pct", "decimal_movido", "de_2_a_10_pct", "de_10_a_50_pct",
                          "mas_de_50_pct")


def _contingencias(consumo):
    """Contingencias por mes (H13), solo en cantidades: cuántas hay, cuántas tienen una carga habitual del
    mismo vehículo a menos de 12 horas y, de esas, cómo coinciden los litros con la más parecida: iguales,
    hasta 2% de diferencia, con el decimal movido (×10, ×100, ÷10, ÷100) u otra diferencia, en bandas.
    """
    pares = pares_de_contingencia(consumo)
    if pares is None:
        return None
    es = consumo["origen_transaccion"].astype("string").str.upper() == ORIGEN_CONTINGENCIA
    mes = leer_fecha(consumo.loc[es, "fecha"].astype("string")).dt.strftime("%Y-%m")
    diferencia = (pares["litros"] - pares["litros_habitual"]).abs() / pares["litros_habitual"]
    clase = np.select(
        [pares["litros"].round(2) == pares["litros_habitual"].round(2), pares["mismos_litros"], pares["decimal_movido"],
         diferencia <= 0.10, diferencia <= 0.50],
        list(range(5)), default=5)
    mejor = pd.Series(clase, index=pares.index).groupby(pares["id"]).min()
    mes_de = pd.Series(mes.values, index=consumo.loc[es, "id"].values)
    mejor = pd.DataFrame({"mes": mes_de.reindex(mejor.index).values,
                          "clase": [LITROS_DE_CONTINGENCIA[c] for c in mejor.values]})

    def contar(contingencias, con_par):
        return {"contingencias": acotar(int(contingencias)),
                "con_carga_habitual_a_menos_de_12_horas": acotar(len(con_par)),
                "litros_con_la_carga_mas_parecida": {c: acotar(int((con_par["clase"] == c).sum()))
                                                     for c in LITROS_DE_CONTINGENCIA}}

    return {"total": contar(es.sum(), mejor),
            "por_mes": {m: contar((mes == m).sum(), mejor[mejor["mes"] == m]) for m in sorted(mes.unique())}}


def _proteger(nombre, bloque, *argumentos):
    """Corre un bloque de diagnóstico sin que una falla tumbe la corrida (#75).

    Si el bloque falla devuelve solo el tipo de excepción y la función y línea del paquete donde se
    originó: ni el mensaje ni los valores, que podrían traer datos de la fuente.
    """
    try:
        return bloque(*argumentos)
    except Exception as error:  # noqa: BLE001 - un bloque de diagnóstico no puede tumbar la corrida
        marcos = traceback.extract_tb(error.__traceback__)
        propios = [m for m in marcos if Path(m.filename).parent.name in ("perfilador", "deteccion")
                   and m.name not in ("_proteger", "<lambda>")]
        ultimo = propios[-1] if propios else (marcos[-1] if marcos else None)
        return {"error": type(error).__name__,
                "donde": f"{ultimo.name}:{ultimo.lineno}" if ultimo else f"{nombre}:0"}


def _capacidad_registrada(consumo, flota):
    """Capacidad de cada carga según el padrón, sin depender de que la matrícula sea única."""
    por_matricula = flota.drop_duplicates("Matricula").set_index("Matricula")["CapacidadTanque"]
    return pd.to_numeric(consumo["vehiculo_id"].map(por_matricula), errors="coerce")


def _exceso_volumetrico(consumo, flota):
    """Diagnóstico agregado de H3b: ratios, cobertura y momento en que aparece el exceso."""
    capacidad = _capacidad_registrada(consumo, flota)
    litros = pd.to_numeric(consumo["litros"], errors="coerce")
    evaluable = capacidad.notna() & capacidad.gt(0) & litros.notna()
    datos = consumo.loc[evaluable, ["id", "vehiculo_id", "fecha"]].copy()
    datos["ratio"] = (litros[evaluable] / capacidad[evaluable]).values
    datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    posicion = datos.groupby("vehiculo_id").cumcount()
    total = datos.groupby("vehiculo_id")["id"].transform("count")
    datos["inicial"] = posicion < (total * FRACCION_INICIAL).clip(lower=1)
    supera = datos[datos["ratio"] > 1.02]
    iniciales = set(supera.loc[supera["inicial"], "vehiculo_id"])
    posteriores = set(supera["vehiculo_id"]) - iniciales
    return {
        "cargas_evaluables": acotar(int(evaluable.sum())),
        "cargas_sin_capacidad_registrada": acotar(int((~capacidad.notna() | capacidad.le(0)).sum())),
        "cargas_sobre_umbral": {f"mas_de_{str(t).replace('.', '_')}": acotar(int((datos["ratio"] > t).sum()))
                                 for t in (1.00, 1.02, 1.05, 1.10)},
        "vehiculos_con_exceso_mayor_al_2_pct": acotar(int(supera["vehiculo_id"].nunique())),
        "vehiculos_con_exceso_desde_las_primeras_cargas": acotar(len(iniciales)),
        "vehiculos_con_exceso_despues_de_un_historial_normal": acotar(len(posteriores)),
    }


CAUSAS_DE_ERROR_DE_CARGA = ("dominio_equivocado", "proveedor_equivocado", "tarjeta_equivocada")

# Bandas del diagnóstico ampliado (#75): el límite cae en la banda cuyo texto lo contiene
BANDAS_DE_EXCESO = {"cociente_": ("1_02_a_1_05", "1_05_a_1_10", "1_10_a_1_25", "1_25_a_1_50",
                                  "mas_de_1_50"),
                    "vehiculos_con_fraccion_": ("menos_de_0_10", "0_10_a_0_30", "0_30_a_0_60",
                                                "mas_de_0_60"),
                    "vehiculos_con_cv_": ("menos_de_0_05", "0_05_a_0_15", "0_15_a_0_30",
                                          "mas_de_0_30"),
                    "rendimiento_": ("menos_de_0_5", "0_5_a_0_8", "0_8_a_1_2", "mas_de_1_2")}


def _banda_del_cociente(cociente):
    """Banda de litros sobre capacidad: el límite superior pertenece a la banda que lo nombra."""
    if cociente <= 1.05:
        return "1_02_a_1_05"
    if cociente <= 1.10:
        return "1_05_a_1_10"
    if cociente <= 1.25:
        return "1_10_a_1_25"
    if cociente <= 1.50:
        return "1_25_a_1_50"
    return "mas_de_1_50"


def _banda_de_la_fraccion(fraccion):
    """Banda de la fracción de cargas evaluables del vehículo que excede el 2 %: `≥60 %` es propio."""
    if fraccion < 0.10:
        return "menos_de_0_10"
    if fraccion <= 0.30:
        return "0_10_a_0_30"
    if fraccion < 0.60:
        return "0_30_a_0_60"
    return "mas_de_0_60"


def _banda_de_la_variacion(variacion):
    """Banda del coeficiente de variación del cociente entre las cargas con exceso del vehículo."""
    if variacion < 0.05:
        return "menos_de_0_05"
    if variacion <= 0.15:
        return "0_05_a_0_15"
    if variacion <= 0.30:
        return "0_15_a_0_30"
    return "mas_de_0_30"


def _banda_del_rendimiento(relacion):
    """Banda del rendimiento del tramo frente a la mediana del propio vehículo."""
    if relacion < 0.5:
        return "menos_de_0_5"
    if relacion <= 0.8:
        return "0_5_a_0_8"
    if relacion <= 1.2:
        return "0_8_a_1_2"
    return "mas_de_1_2"


def _exceso_volumetrico_detalle(consumo, flota, alertas):
    """Diagnóstico ampliado de H3b (#75): cada carga con exceso, clasificada por su origen.

    Clasifica con la regla de `detectar_exceso_sin_antecedente`: si el vehículo ya excedía el
    tanque dentro de sus primeras cargas (FRACCION_INICIAL), todos sus excesos son
    `desde_el_inicio` (capacidad mal registrada); si el exceso aparece después de un historial
    normal, es `despues` (posible uso indebido). Por clase informa (a) vehículos y cargas con
    exceso; (b) la banda del cociente litros/capacidad; (c) la estabilidad del vehículo: la
    fracción de sus cargas evaluables que excede el 2 % y el coeficiente de variación del
    cociente entre sus cargas con exceso (solo con 3 o más); (d) cuántos vehículos reúnen la
    mitad de las cargas de la clase; (e) la banda del rendimiento del tramo (km desde la carga
    anterior evaluable, dividido por los litros) frente a la mediana del propio vehículo; y
    (f) las cargas con causa probable de error de carga. Sin identificadores y sin restas entre
    los conteos publicados que devuelvan un grupo de 1 a 19.
    """
    capacidad = _capacidad_registrada(consumo, flota)
    litros = pd.to_numeric(consumo["litros"], errors="coerce")
    evaluable = capacidad.notna() & capacidad.gt(0) & litros.notna()
    columnas = ["id", "vehiculo_id", "fecha", "litros"] + (["odometro"] if "odometro" in consumo else [])
    datos = consumo.loc[evaluable, columnas].copy()
    datos["cociente"] = (litros[evaluable] / capacidad[evaluable]).values
    datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    if "odometro" in datos:
        odometro = pd.to_numeric(datos["odometro"], errors="coerce")
        km = odometro - odometro.groupby(datos["vehiculo_id"]).shift(1)
        datos["rendimiento"] = (km / datos["litros"]).where(km.notna() & datos["litros"].gt(0))
    else:
        datos["rendimiento"] = float("nan")
    posicion = datos.groupby("vehiculo_id").cumcount()
    total = datos.groupby("vehiculo_id")["id"].transform("count")
    iniciales = posicion < (total * FRACCION_INICIAL).clip(lower=1)
    excede = datos["cociente"] > 1 + TOLERANCIA_EXCESO_TANQUE
    con_antecedente = set(datos.loc[iniciales & excede, "vehiculo_id"])
    exceso = datos[excede].copy()
    exceso["desde_el_inicio"] = exceso["vehiculo_id"].isin(con_antecedente)
    evaluables = datos.groupby("vehiculo_id").size()
    centrales = datos.groupby("vehiculo_id")["rendimiento"].median()

    error_de = {}
    if alertas is not None and len(alertas) and "causa_probable" in alertas.columns:
        firmas = alertas.loc[alertas["causa_probable"].isin(CAUSAS_DE_ERROR_DE_CARGA),
                             ["id_registro", "causa_probable"]].drop_duplicates("id_registro")
        error_de = dict(zip(firmas["id_registro"], firmas["causa_probable"]))

    detalle = {}
    for clave, desde_el_inicio in (("desde_el_inicio", True), ("despues", False)):
        clase = exceso[exceso["desde_el_inicio"] == desde_el_inicio]
        detalle[clave] = _detalle_de_exceso_de_la_clase(clase, evaluables, centrales, error_de)
    return detalle


def _detalle_de_exceso_de_la_clase(clase, evaluables, centrales, error_de):
    """Una clase del detalle: conteos, bandas y las protecciones de resta entre los publicados."""
    conteo = {prefijo + banda: 0 for prefijo, bandas in BANDAS_DE_EXCESO.items() for banda in bandas}
    causas = {f"causa_probable_{c}": 0 for c in CAUSAS_DE_ERROR_DE_CARGA}
    por_vehiculo = clase.groupby("vehiculo_id")
    excesos = por_vehiculo.size()
    for vehiculo, grupo in por_vehiculo:
        conteo["vehiculos_con_fraccion_" + _banda_de_la_fraccion(
            len(grupo) / evaluables[vehiculo])] += 1
        if len(grupo) >= 3:
            cociente = grupo["cociente"]
            conteo["vehiculos_con_cv_" + _banda_de_la_variacion(cociente.std(ddof=0) / cociente.mean())] += 1
        central = centrales.get(vehiculo)
        if central is not None and not pd.isna(central) and central > 0:
            for rendimiento in grupo["rendimiento"].dropna():
                conteo["rendimiento_" + _banda_del_rendimiento(rendimiento / central)] += 1
        for id_registro in grupo["id"]:
            causa = error_de.get(id_registro)
            if causa is not None:
                causas[f"causa_probable_{causa}"] += 1
    for cociente in clase["cociente"]:
        conteo["cociente_" + _banda_del_cociente(cociente)] += 1

    cargas = len(clase)
    orden = excesos.sort_values(ascending=False, kind="stable")
    acumulado, mitad = 0, 0
    for cantidad in orden:
        acumulado += cantidad
        mitad += 1
        if acumulado * 2 >= cargas:
            break
    vehiculos = len(excesos)
    con_3 = int((excesos >= 3).sum())

    def grupo_de(prefijo):
        return {k: v for k, v in conteo.items() if k.startswith(prefijo)}

    salida = {"vehiculos": acotar(vehiculos), "cargas_con_exceso": acotar(cargas),
              "vehiculos_con_3_o_mas_cargas_con_exceso": con_3,
              "vehiculos_para_la_mitad_de_las_cargas": mitad}
    for partes, totales in ((grupo_de("cociente_"), (cargas,)),
                            (grupo_de("rendimiento_"), (cargas,)),
                            (causas, (cargas,)),
                            (grupo_de("vehiculos_con_fraccion_"), (vehiculos,)),
                            (grupo_de("vehiculos_con_cv_"), (vehiculos, con_3)),
                            ({"vehiculos_con_3_o_mas_cargas_con_exceso": con_3}, (vehiculos,)),
                            ({"vehiculos_para_la_mitad_de_las_cargas": mitad}, (vehiculos,))):
        salida.update(_partes_sin_resta_de(totales, partes))
    return salida


# Bandas del diagnóstico de fraccionamiento (#75): el límite superior cae en la banda que lo nombra
BANDAS_DE_CANTIDAD_DE_CARGAS = ("cargas_1", "cargas_2", "cargas_3", "cargas_4_o_mas")
BANDAS_DE_TANQUE_DEL_DIA = ("hasta_1_00", "1_00_a_1_05", "1_05_a_1_50", "mas_de_1_50")
BANDAS_DE_RENDIMIENTO_DEL_DIA = ("menos_de_0_5", "0_5_a_0_8", "0_8_a_1_2", "mas_de_1_2")
BANDAS_DE_DIFERENCIA_DE_LITROS = ("menos_de_0_8", "0_8_a_1_0", "1_0_a_1_2", "mas_de_1_2")
PEDIDOS_POR_DIA = ("para_todas_las_cargas", "para_algunas_cargas", "para_ninguna_carga")
BANDERAS_DE_RENDICION = ("amarillo", "verde", "rojo")
NIVELES_DE_TANQUE = ("tanque lleno", "3/4 tanque", "1/2 tanque", "1/4 tanque", "reserva")


def _banda_de_la_cantidad(cantidad):
    """Banda de la cantidad de cargas de un día-vehículo: la cuarta junta 4 o más."""
    if cantidad == 1:
        return "cargas_1"
    if cantidad == 2:
        return "cargas_2"
    if cantidad == 3:
        return "cargas_3"
    return "cargas_4_o_mas"


def _banda_del_tanque_del_dia(cociente):
    """Banda de los litros del día sobre la capacidad del tanque: el límite cae en la banda de abajo."""
    if cociente <= 1.00:
        return "hasta_1_00"
    if cociente <= 1.05:
        return "1_00_a_1_05"
    if cociente <= 1.50:
        return "1_05_a_1_50"
    return "mas_de_1_50"


def _banda_de_la_diferencia_de_litros(cociente):
    """Banda del cociente litros cargados / litros autorizados del pedido: 1 es lo autorizado."""
    if cociente < 0.8:
        return "menos_de_0_8"
    if cociente <= 1.0:
        return "0_8_a_1_0"
    if cociente <= 1.2:
        return "1_0_a_1_2"
    return "mas_de_1_2"


def _banda_de_la_bandera(valor):
    """La bandera de rendición de la fuente como etiqueta genérica, o None si no es una conocida."""
    texto = str(valor).strip().lower()
    return texto if texto in BANDERAS_DE_RENDICION else None


def _banda_del_nivel(valor):
    """El nivel del tanque de la fuente como etiqueta genérica, o None si no es uno de los conocidos."""
    texto = str(valor).strip().lower()
    return texto if texto in NIVELES_DE_TANQUE else None


def _fraccionamiento_detalle(datos, alertas):
    """Diagnóstico de H4 (#75): qué son los días con dos o más cargas del mismo vehículo.

    Por día-vehículo (misma fecha y vehículo) informa (a) cuántos tienen 1, 2, 3 y 4 o más cargas,
    y los de 2 o más por tipo de vehículo; (b) en los de 2 o más, los litros del día sobre la
    capacidad del tanque en bandas; (c) el rendimiento del día (km entre la primera y la última
    carga, o hasta la primera del día siguiente, sobre los litros) frente a la mediana del propio
    vehículo, con los días de km no evaluables aparte; (d) cuántos tienen pedido propio en el
    registro para todas, algunas o ninguna de sus cargas (cruce con contexto); (e) frente a los
    días de una sola carga, la distribución de la bandera de rendición, del nivel del tanque
    declarado y de la diferencia entre litros autorizados y cargados, en bandas; (f) cuántos
    tienen al menos un reclamo vinculado con alguna de sus cargas; y (g) los km por hora de motor
    por tipo de vehículo, si la fuente los trae. Todo en agregado y sin restas que recuperen un
    grupo de 1 a 19.
    """
    consumo, flota = datos["consumo"], datos["flota"]
    registro = datos.get("solicitudes")
    litros = pd.to_numeric(consumo["litros"], errors="coerce")
    capacidad = _capacidad_registrada(consumo, flota)
    tipo_de = flota.dropna(subset=["Matricula"]).drop_duplicates("Matricula").set_index("Matricula")["TipoVehiculo"]
    odometro = pd.to_numeric(consumo.get("odometro", pd.Series(pd.NA, index=consumo.index)), errors="coerce")

    cargas = pd.DataFrame({
        "id": consumo["id"].values, "vehiculo_id": consumo["vehiculo_id"].values,
        "fecha": pd.to_datetime(consumo["fecha"]).dt.normalize().values,
        "litros": litros.values, "capacidad": capacidad.values, "odometro": odometro.values,
    }).dropna(subset=["vehiculo_id", "fecha"]).sort_values(["vehiculo_id", "fecha", "id"])

    # (a) Cantidad de cargas por día-vehículo
    dias = cargas.groupby(["vehiculo_id", "fecha"], sort=False).agg(
        cargas=("id", "size"), litros=("litros", "sum"), capacidad=("capacidad", "first"),
        odometro_primera=("odometro", "first"), odometro_ultima=("odometro", "last"),
        ids=("id", list)).reset_index()
    dias["tipo"] = dias["vehiculo_id"].map(tipo_de).fillna("sin_dato")
    dias["banda"] = dias["cargas"].map(_banda_de_la_cantidad)

    # (b) Litros del día sobre la capacidad del tanque (solo los días con capacidad registrada)
    dias["cociente"] = (dias["litros"] / dias["capacidad"]).where(dias["capacidad"].gt(0))
    dias["banda_tanque"] = dias["cociente"].map(
        lambda c: _banda_del_tanque_del_dia(c) if pd.notna(c) else None)

    # (c) Rendimiento del día contra la mediana del propio vehículo; los km no evaluables, aparte.
    # El día de una sola carga cierra su tramo en la primera carga del día siguiente.
    dias = dias.sort_values(["vehiculo_id", "fecha"])
    siguiente = dias.groupby("vehiculo_id")["odometro_primera"].shift(-1)
    km = (dias["odometro_ultima"] - dias["odometro_primera"]).astype(float).where(
        dias["cargas"] >= 2, (siguiente - dias["odometro_primera"]).astype(float))
    dias["km_evaluable"] = km.notna() & km.gt(0)
    rendimiento = (km / dias["litros"]).where(dias["km_evaluable"])
    mediana = rendimiento.groupby(dias["vehiculo_id"].values).transform("median")
    dias["relacion"] = (rendimiento / mediana).replace([np.inf, -np.inf], np.nan)
    dias["banda_rendimiento"] = dias["relacion"].map(
        lambda r: _banda_del_rendimiento(r) if pd.notna(r) else None)
    dias["rendimiento_evaluable"] = dias["km_evaluable"] & mediana.gt(0)

    # (d) Pedido propio del registro para cada carga del día (cruce con contexto), y (e) lo que el
    # propio pedido declara: bandera de rendición, nivel del tanque y litros cargados/autorizados
    del_registro = _datos_del_registro_por_carga(consumo, registro, flota)
    dias["pedidos"] = dias["ids"].map(
        lambda ids: _clase_de_pedidos(sum(bool(del_registro["pedido"].get(i, False)) for i in ids), len(ids)))
    dias["banderas"] = dias["ids"].map(lambda ids: [del_registro["bandera"].get(i) for i in ids])
    dias["niveles"] = dias["ids"].map(lambda ids: [del_registro["nivel"].get(i) for i in ids])
    dias["diferencias"] = dias["ids"].map(
        lambda ids: [d for d in (del_registro["cociente"].get(i) for i in ids) if d is not None])

    # (f) Reclamos vinculados con alguna carga del día
    con_reclamo = _cargas_con_reclamo(datos.get("reclamos"))
    dias["con_reclamo"] = dias["ids"].map(lambda ids: any(i in con_reclamo for i in ids))

    return _resumen_de_fraccionamiento(dias)


def _clase_de_pedidos(con_pedido, cantidad):
    """Para todas, algunas o ninguna carga del día tienen pedido propio en el registro."""
    if con_pedido == 0:
        return PEDIDOS_POR_DIA[2]
    if con_pedido == cantidad:
        return PEDIDOS_POR_DIA[0]
    return PEDIDOS_POR_DIA[1]


def _datos_del_registro_por_carga(consumo, registro, flota):
    """Por id de carga, qué trae el cruce con el registro: si tiene pedido y lo que el pedido declara.

    Devuelve tres diccionarios por id de carga: `pedido` (si el cruce con contexto le encontró un
    pedido propio), `bandera` (la bandera de rendición como etiqueta genérica o None), `nivel` (el
    nivel del tanque declarado o None) y `cociente` (litros cargados sobre autorizados o None).
    """
    vacios = {"pedido": {}, "bandera": {}, "nivel": {}, "cociente": {}}
    if registro is None or not len(registro):
        return vacios
    pares, _ = cruzar_registro(consumo, registro, flota=flota)
    pedidos = registro.set_index("id")
    bandera = _texto_categorias(registro, "bandera_rendicion", _banda_de_la_bandera)
    nivel = _texto_categorias(registro, "nivel_tanque", _banda_del_nivel)
    cargados = pd.to_numeric(pedidos.get("litros_cargados"), errors="coerce")
    autorizados = pd.to_numeric(pedidos.get("litros_autorizados"), errors="coerce")
    cociente = (cargados / autorizados.where(autorizados > 0))
    salida = {"pedido": {}, "bandera": {}, "nivel": {}, "cociente": {}}
    for carga_id, pedido_id in pares["registro_id"].items():
        tiene = pd.notna(pedido_id)
        salida["pedido"][carga_id] = tiene
        if not tiene or pedido_id not in pedidos.index:
            continue
        salida["bandera"][carga_id] = bandera.get(pedido_id)
        salida["nivel"][carga_id] = nivel.get(pedido_id)
        valor = cociente.get(pedido_id)
        salida["cociente"][carga_id] = float(valor) if pd.notna(valor) else None
    return salida


def _texto_categorias(registro, columna, traductor):
    """La columna del registro como etiquetas genéricas por id de pedido, o vacío si no está."""
    if columna not in registro.columns:
        return {}
    return dict(zip(registro["id"], registro[columna].map(traductor)))


def _cargas_con_reclamo(reclamos):
    """Los ids de carga que tienen al menos un reclamo vinculado."""
    if reclamos is None:
        return set()
    return set(reclamos["carga_id"].dropna())


def _resumen_de_fraccionamiento(dias):
    """Arma el bloque de H4 a partir de los días-vehículo ya clasificados, sin restas que recuperen 1–19.

    El eje del bloque es la cantidad de cargas del día-vehículo, contra el que se protegen los
    demás conteos. El total del bloque es la cantidad de días-vehículo con vehículo y fecha
    conocidos: ninguna banda ni ninguna resta entre bandas publicadas puede dejar al descubierto un
    grupo de 1 a 19.
    """
    fragmentados = dias[dias["cargas"] >= 2]
    de_una = dias[dias["cargas"] == 1]
    salida = {
        "por_cantidad_de_cargas": _partes_bandas(BANDAS_DE_CANTIDAD_DE_CARGAS, dias["banda"], len(dias)),
        "dias_solo_con_una_carga": acotar(len(de_una)),
        "dias_con_dos_o_mas_cargas": acotar(len(fragmentados)),
    }

    # (a) Por tipo de vehículo, solo los días fragmentados
    salida["fragmentados_por_tipo_de_vehiculo"] = _partes_bandas_por(
        BANDAS_DE_CANTIDAD_DE_CARGAS[1:], fragmentados["banda"], fragmentados["tipo"])

    # (b) Litros del día sobre la capacidad del tanque
    con_capacidad = fragmentados[fragmentados["banda_tanque"].notna()]
    salida["litros_del_dia_sobre_la_capacidad"] = _partes_bandas(
        BANDAS_DE_TANQUE_DEL_DIA, con_capacidad["banda_tanque"], len(con_capacidad))

    # (c) Rendimiento del día frente a la mediana del propio vehículo, con los no evaluables aparte
    evaluables = fragmentados[fragmentados["rendimiento_evaluable"]]
    salida["rendimiento_del_dia"] = _partes_bandas(
        BANDAS_DE_RENDIMIENTO_DEL_DIA, evaluables["banda_rendimiento"], len(evaluables))
    salida["rendimiento_del_dia"]["km_no_evaluable"] = acotar(len(fragmentados) - len(evaluables))

    # (d) Pedido propio del registro para todas, algunas o ninguna carga del día
    salida["pedido_para"] = _partes_bandas(PEDIDOS_POR_DIA, fragmentados["pedidos"], len(fragmentados))

    # (e) Distribución de la bandera, del nivel del tanque y de los litros cargados sobre los
    # autorizados, en los días fragmentados frente a los de una sola carga
    salida["bandera_de_rendicion"] = _banderas_de_los_dias(dias, "banderas", BANDERAS_DE_RENDICION)
    salida["nivel_del_tanque"] = _banderas_de_los_dias(dias, "niveles", NIVELES_DE_TANQUE)
    salida["litros_cargados_sobre_autorizados"] = _bandas_de_las_diferencias(dias)

    # (f) Días fragmentados con al menos un reclamo vinculado con alguna de sus cargas
    salida["con_reclamo_vinculado"] = _partes_bandas(
        ("si", "no"), fragmentados["con_reclamo"].map({True: "si", False: "no"}), len(fragmentados))

    # (g) Kilómetros por hora de motor: la fuente no trae el horómetro
    salida["km_por_hora_de_motor"] = "no_disponible"
    _protege_el_eje(salida, "fragmentados_por_tipo_de_vehiculo")
    return salida


def _banderas_de_los_dias(dias, columna, etiquetas):
    """Distribución de una etiqueta categórica de las cargas, en los días fragmentados y en los de una.

    Cuenta las cargas (no los días) por etiqueta, porque la etiqueta es del pedido de cada carga;
    solo aparecen las etiquetas conocidas. Si en la fuente no había columna, devuelve `no_disponible`.
    """
    valores = {}
    for nombre, sub in (("fragmentados", dias[dias["cargas"] >= 2]), ("de_una_carga", dias[dias["cargas"] == 1])):
        series = [e for lista in sub[columna] for e in lista if e is not None]
        if not series:
            continue
        total = len(series)
        valores[nombre] = {"cargas_con_el_dato": acotar(total),
                           **_partes_sin_resta(total, {e: series.count(e) for e in etiquetas})}
    return valores if valores else "no_disponible"


def _bandas_de_las_diferencias(dias):
    """Litros cargados sobre autorizados en bandas, en los días fragmentados y en los de una carga."""
    valores = {}
    for nombre, sub in (("fragmentados", dias[dias["cargas"] >= 2]), ("de_una_carga", dias[dias["cargas"] == 1])):
        series = [d for lista in sub["diferencias"] for d in lista]
        if not series:
            continue
        bandas = pd.Series(series).map(_banda_de_la_diferencia_de_litros)
        partes = {e: int((bandas == e).sum()) for e in BANDAS_DE_DIFERENCIA_DE_LITROS}
        valores[nombre] = {"cargas_con_el_dato": acotar(len(series)), **_partes_sin_resta(len(series), partes)}
    return valores if valores else "no_disponible"


CAUSAS_SIN_VINCULO = ("ultimos_8_del_motor", "distancia_1_de_un_dominio", "otra_fuente", "forma_del_identificador",
                      "sin_explicacion")
EDICIONES = ("confusion_visual", "letra_cambiada", "transposicion", "letra_de_mas_o_de_menos")
FORMAS = ("vacio", "solo_digitos", "solo_letras", "largo_distinto", "forma_de_dominio")


def _forma(identificador, largos):
    """Forma del identificador normalizado, sin su valor: vacío, solo dígitos, solo letras, largo distinto
    al de los dominios de la flota, o forma de dominio."""
    if pd.isna(identificador) or identificador == "":
        return "vacio"
    if identificador.isdigit():
        return "solo_digitos"
    if identificador.isalpha():
        return "solo_letras"
    return "largo_distinto" if len(identificador) not in largos else "forma_de_dominio"


def _dominios(serie):
    """Dominios normalizados de una fuente, sin vacíos."""
    return set(normalizar_dominio(serie).dropna()) - {""} if serie is not None else set()


def _partes_sin_resta(total, partes):
    """Las partes de un total que se informa, sin que un grupo chico se pueda recuperar por resta.

    Un conteo de 1 a 19 sale como "1–19"; pero si el total sale entero, restarle las partes visibles
    devuelve la suma de las ocultas y, mientras esa suma dé entre 1 y 19, las revela. Por eso se
    oculta también la parte visible más chica (`None`): quien resta solo obtiene 20 o más.
    """
    if total < MINIMO_GRUPO:
        return {k: acotar(v) for k, v in partes.items()}
    publicadas = {k: v for k, v in partes.items() if v == 0 or v >= MINIMO_GRUPO}
    salida = {k: acotar(v) for k, v in partes.items()}
    ocultas = set()
    while True:
        resto = total - sum(v for k, v in publicadas.items() if k not in ocultas)
        visibles = {k: v for k, v in publicadas.items() if k not in ocultas and v >= MINIMO_GRUPO}
        if not visibles or not 0 < resto < MINIMO_GRUPO:
            break
        ocultas.add(min(visibles, key=visibles.get))
    for clave in ocultas:
        salida[clave] = None
    return salida


def _partes_sin_resta_de(totales, partes):
    """Las partes, sin que la resta contra ninguno de los totales devuelva un conteo de 1 a 19.

    Como `_partes_sin_resta`, pero contra varios totales a la vez (por ejemplo, las bandas de
    estabilidad se restan tanto de los vehículos de la clase como de los que llevan 3 o más
    excesos): mientras alguna resta dé entre 1 y 19 se oculta la parte visible más chica y se
    vuelve a restar. Los totales de 1 a 19 no se publican enteros, así que no se protegen.
    """
    publicables = {k: v for k, v in partes.items() if v == 0 or v >= MINIMO_GRUPO}
    protegibles = [t for t in totales if isinstance(t, int) and not isinstance(t, bool)
                   and t >= MINIMO_GRUPO]
    ocultas = set()
    while protegibles:
        activos = {k: v for k, v in publicables.items() if k not in ocultas}
        visibles = {k: v for k, v in activos.items() if v >= MINIMO_GRUPO}
        if not visibles or not any(0 < t - sum(activos.values()) < MINIMO_GRUPO for t in protegibles):
            break
        ocultas.add(min(visibles, key=visibles.get))
    return {k: (None if k in ocultas else acotar(v)) for k, v in partes.items()}


def _eje_sin_resta(eje, publicados):
    """Un eje (por_mes, por_producto, por_tipo) sin que la resta contra un total publicado devuelva un conteo de 1 a 19.

    `publicados` es la lista de (campo, total) contra los que alguien podría restar: `None` suma
    todas las celdas enteras del eje (el total del bloque), un nombre de campo toma esa clave en
    cada entrada (la columna de una banda o la de un hijo con total). Si la resta queda entre 1 y 19
    se oculta la celda entera más chica (`None`) y el resto salta a 20 o más; se repite hasta que
    ninguna resta deje un grupo chico al descubierto.
    """
    while True:
        for campo, total in publicados:
            if not isinstance(total, int) or isinstance(total, bool):
                continue
            celdas = [(clave, valor, entrada) for entrada in eje.values()
                      for clave, valor in entrada.items()
                      if (campo is None or clave == campo) and isinstance(valor, int)
                      and not isinstance(valor, bool)]
            if not celdas or not 0 < total - sum(valor for _, valor, _ in celdas) < MINIMO_GRUPO:
                continue
            elegibles = [celda for celda in celdas if celda[1] >= MINIMO_GRUPO]
            if not elegibles:
                continue
            clave, _, entrada = min(elegibles, key=lambda celda: celda[1])
            entrada[clave] = None
            break
        else:
            return


def _protege_el_eje(bloque, nombre_eje):
    """El eje de un bloque contra los totales que el bloque publica.

    Deja en (campo, total) los enteros sueltos del bloque (cada banda), el total de cada hijo con
    total (la columna de ese hijo en el eje) y, al final, el total del bloque contra todas las
    celdas. Las entradas del eje y los ejes hermanos no publican total y quedan fuera.
    """
    publicados = []
    for clave, valor in bloque.items():
        if clave == nombre_eje:
            continue
        if isinstance(valor, dict):
            hijo_total = valor.get("total")
            if isinstance(hijo_total, int) and not isinstance(hijo_total, bool):
                publicados.append((clave, hijo_total))
        elif isinstance(valor, int) and not isinstance(valor, bool):
            publicados.append((clave, valor))
    publicados.append((None, bloque.get("total")))
    _eje_sin_resta(bloque[nombre_eje], publicados)


def _protege_el_total(grupo):
    """Un grupo armado a mano con su total, sin que la resta de sus partes visibles devuelva un conteo de 1 a 19.

    Mira las partes sueltas del grupo y, por cada bloque de conteos anidado (por_baja, por_caida),
    las suyas: mientras la resta dé entre 1 y 19 se oculta la parte entera más chica y se vuelve a
    mirar. Los grupos sin total entero no se tocan.
    """
    total = grupo.get("total")
    if not isinstance(total, int) or isinstance(total, bool) or total < MINIMO_GRUPO:
        return grupo
    bloques = [grupo] + [v for v in grupo.values()
                         if isinstance(v, dict) and not any(isinstance(x, dict) for x in v.values())]
    for bloque in bloques:
        while True:
            enteros = {k: v for k, v in bloque.items()
                       if k != "total" and isinstance(v, int) and not isinstance(v, bool)}
            if not 0 < total - sum(enteros.values()) < MINIMO_GRUPO:
                break
            visibles = {k: v for k, v in enteros.items() if v >= MINIMO_GRUPO}
            if not visibles:
                break
            bloque[min(visibles, key=visibles.get)] = None
    return grupo


def _sin_vinculo(identificador, flota, otras, clave=None, nombre_clave=None):
    """Por qué los identificadores sin vínculo normalizado no se vinculan con la flota, solo en agregado.

    Cada uno se explica por la primera causa que corresponde, en este orden: la clave propia de la
    fuente (`clave`, serie booleana: la tarjeta o la matrícula es de un móvil del padrón); los últimos
    8 dígitos (o caracteres) del número de motor de un móvil; la distancia de edición 1 de un dominio
    de la flota; el dominio está en otra fuente (`otras`) pero no en el padrón; el identificador no
    tiene forma de dominio. Lo que queda es `sin_explicacion`: un dominio bien formado que no está en
    ninguna fuente, a investigar aparte.
    """
    dominios = _dominios(flota["Dominio"])
    normalizado = normalizar_dominio(identificador)
    sin_vinculo = normalizado[~normalizado.isin(dominios)]
    explicada = clave.reindex(sin_vinculo.index).fillna(False) if clave is not None \
        else pd.Series(False, index=sin_vinculo.index)
    # Un sufijo que comparten dos motores de móviles distintos no identifica a ninguno: se cuenta aparte
    moviles_por_sufijo = moviles_por_sufijo_de_motor(flota)
    por_largo = {}
    for d in dominios:
        por_largo.setdefault(len(d), []).append(d)
    largos = set(por_largo)

    causas, ediciones, formas = [], [], []
    motor_ambiguo = dist_ambigua = 0
    for i, ident in sin_vinculo.items():
        forma = _forma(ident, largos)
        formas.append(forma)
        if explicada[i]:
            causas.append(nombre_clave)
            continue
        if forma != "vacio" and ident in moviles_por_sufijo:
            causas.append("ultimos_8_del_motor")
            motor_ambiguo += int(len(moviles_por_sufijo[ident]) > 1)
            continue
        cerca = [] if forma == "vacio" else [t for n in (len(ident) - 1, len(ident), len(ident) + 1)
                                             for d in por_largo.get(n, []) if (t := distancia_uno(ident, d))]
        if cerca:
            causas.append("distancia_1_de_un_dominio")
            ediciones.append(cerca[0])
            dist_ambigua += int(len(cerca) > 1)
            continue
        if forma != "vacio" and ident in otras:
            causas.append("otra_fuente")
            continue
        causas.append("forma_del_identificador" if forma != "forma_de_dominio" else "sin_explicacion")

    causas, formas = pd.Series(causas, dtype="string"), pd.Series(formas, dtype="string")
    sin_forma = formas[causas.eq("forma_del_identificador").values]
    nombres = ((nombre_clave,) if nombre_clave else ()) + CAUSAS_SIN_VINCULO
    por_causa = {c: int(causas.eq(c).sum()) for c in nombres}
    return {
        "sin_vinculo_exacto": acotar(int((~identificador.isin(set(flota["Dominio"].dropna()))).sum())),
        "sin_vinculo_normalizado": acotar(len(sin_vinculo)),
        "por_causa": _partes_sin_resta(len(sin_vinculo), por_causa),
        "distancia_1_por_edicion": _partes_sin_resta(por_causa.get("distancia_1_de_un_dominio", 0),
                                                     {e: ediciones.count(e) for e in EDICIONES}),
        "distancia_1_con_mas_de_un_dominio": acotar(dist_ambigua),
        "motor_con_mas_de_un_movil": acotar(motor_ambiguo),
        "forma_del_identificador": _partes_sin_resta(por_causa.get("forma_del_identificador", 0),
                                                     {f: int(sin_forma.eq(f).sum()) for f in FORMAS[:-1]}),
        "forma_de_todas_las_sin_vinculo": _partes_sin_resta(len(sin_vinculo),
                                                            {f: int(formas.eq(f).sum()) for f in FORMAS}),
    }


def _vinculacion(consumo, flota, telemetria=None, registro=None):
    """Vinculación con la flota de las cargas, la placa de la telemetría y el registro interno (H1, #41).

    Por fuente: cuántos registros se evalúan, qué porcentaje se vincula en cada nivel (acumulado) y
    por qué no se vinculan los que quedan sin vínculo normalizado (`_sin_vinculo`). Las cargas se
    explican primero por la tarjeta y los pedidos por la matrícula; la telemetría no tiene otra clave.
    Las tarjetas personales no se cuentan (traen la persona) y los dispositivos del grupo de depósito
    tampoco (están retirados). Solo conteos, sin ningún identificador.
    """
    placas = telemetria["Placa"] if telemetria is not None and "Placa" in telemetria.columns else None
    del_registro = registro["dominio"] if registro is not None and "dominio" in registro.columns else None

    personal = consumo.get("tipo_identificacion", pd.Series("PATENTE", index=consumo.index)).eq("DNI")
    evaluadas = consumo[~personal]
    niveles = vinculos_de_la_carga(evaluadas, flota)
    vinculacion = {
        "cargas_evaluadas": acotar(len(evaluadas)),
        # Niveles de H1, acumulados: cuánto sube la vinculación con cada camino
        "vinculadas_pct": {n: _pct(int(niveles[n].sum()), len(evaluadas))
                           for n in ("exacto", "normalizado", "motor", "tarjeta")},
        **_sin_vinculo(evaluadas["dominio"], flota, _dominios(placas) | _dominios(del_registro),
                       evaluadas.get("numero_tarjeta", pd.Series(pd.NA, index=evaluadas.index)).isin(
                           set(flota["NumeroTarjeta"].dropna()) if "NumeroTarjeta" in flota.columns else set()),
                       "tarjeta_del_padron"),
    }
    if placas is not None:
        instalados = telemetria[telemetria.get("Grupo", pd.Series(pd.NA, index=telemetria.index)) != GRUPO_DEPOSITO]
        niveles = vinculos_por_identificador(instalados["Placa"], flota)
        vinculacion["telemetria"] = {
            "dispositivos_evaluados": acotar(len(instalados)),
            "vinculados_pct": {n: _pct(int(niveles[n].sum()), len(instalados)) for n in ("exacto", "normalizado", "motor")},
            **_sin_vinculo(instalados["Placa"], flota, _dominios(consumo["dominio"]) | _dominios(del_registro)),
        }
    if del_registro is not None:
        niveles = vinculos_del_pedido(registro, flota)
        vinculacion["registro"] = {
            "pedidos_evaluados": acotar(len(registro)),
            "vinculados_pct": {n: _pct(int(niveles[n].sum()), len(registro))
                               for n in ("exacto", "normalizado", "motor", "matricula")},
            **_sin_vinculo(registro["dominio"], flota, _dominios(consumo["dominio"]) | _dominios(placas),
                           registro.get("vehiculo_id", pd.Series(pd.NA, index=registro.index)).isin(
                               set(flota["Matricula"].dropna())), "matricula_del_padron"),
        }
    return vinculacion


# Qué hipótesis anticipa cada tipo de reclamo de la fuente
HIPOTESIS_DEL_RECLAMO = {"doble_cobro": "H13", "cargas_multiples": "H4", "odometro_estancado": "H12"}
RESUELTOS = {"nota_de_credito", "rechazado"}


def _monto(reclamos):
    """Suma de los montos positivos, con dos cifras significativas, si son al menos MINIMO_GRUPO reclamos."""
    positivos = reclamos.loc[reclamos["monto"] > 0, "monto"]
    return dos_cifras(float(positivos.sum())) if len(positivos) >= MINIMO_GRUPO else None


def _reclamos(datos, alertas, corrieron):
    """Reclamos al proveedor frente a nuestras reglas, solo en agregado.

    Sin etiquetas reales, los reclamos son la mejor referencia: qué parte de los reclamos de cada
    tipo anticipa cada regla de su hipótesis (una estimación de lo que se escapa), qué parte de las
    alertas de cada regla terminó en un reclamo y, entre los resueltos, qué parte terminó en nota de
    crédito (la mejor estimación de precisión disponible).

    Las alertas se cuentan solo en el período que cubren los reclamos: fuera de él no pudieron
    terminar en un reclamo. Los montos, redondeados a dos cifras y solo los positivos.
    """
    reclamos = datos["reclamos"]
    vinculados = reclamos.dropna(subset=["carga_id"])
    fecha_de = pd.to_datetime(datos["consumo"].set_index("id")["fecha"]).dt.normalize()
    desde, hasta = reclamos["fecha"].min(), reclamos["fecha"].max()
    en_periodo = set(fecha_de.index[fecha_de.between(desde, hasta)]) if pd.notna(desde) else set(fecha_de.index)
    salida = {
        "reclamos": acotar(len(reclamos)),
        "por_tipo": {t: acotar(n) for t, n in reclamos["tipo"].value_counts().items()},
        "por_estado": {e: acotar(n) for e, n in reclamos["estado"].value_counts().items()},
        "vinculados_con_una_carga_pct": _pct(len(vinculados), len(reclamos)),
        "vinculados_por_ticket": acotar(int((reclamos["vinculo"] == "ticket").sum())),
        "vinculados_por_patente_y_hora": acotar(int((reclamos["vinculo"] == "patente_y_hora").sum())),
        "vinculados_por_tarjeta_y_hora": acotar(int((reclamos["vinculo"] == "tarjeta_y_hora").sum())),
        "montos_no_positivos": acotar(int((reclamos["monto"] <= 0).sum())),
        "dias_del_periodo_de_reclamos": acotar((hasta - desde).days + 1) if pd.notna(desde) else 0,
        "por_tipo_de_alerta": {},
    }
    catalogo = {h["codigo"]: h for h in hipotesis_del_escenario("realista")}
    for tipo, codigo in HIPOTESIS_DEL_RECLAMO.items():
        del_tipo = vinculados[vinculados["tipo"] == tipo]
        resueltos = del_tipo[del_tipo["estado"].isin(RESUELTOS)]
        detalle = {"hipotesis": codigo, "reclamos_vinculados": acotar(len(del_tipo)),
                   "resueltos": acotar(len(resueltos)),
                   "nota_de_credito_pct": _pct(int((resueltos["estado"] == "nota_de_credito").sum()), len(resueltos)),
                   "monto_reclamable": _monto(del_tipo)}
        reglas = [r for regla, _ in catalogo[codigo]["reglas"] for r in reglas_de(regla) if r in corrieron] \
            if codigo in catalogo else []
        if not reglas:
            detalle["reglas"] = "no corre"
        else:
            detalle["reglas"] = {}
            con_reclamo = set(del_tipo["carga_id"])
            for regla in dict.fromkeys(reglas):
                marcadas = set(alertas.loc[alertas["regla"] == regla, "id_registro"]) & en_periodo
                anticipados = del_tipo[del_tipo["carga_id"].isin(marcadas)]
                resueltos_regla = anticipados[anticipados["estado"].isin(RESUELTOS)]
                detalle["reglas"][regla] = {
                    "anticipa_pct": _pct(len(anticipados), len(del_tipo)),
                    "alertas": acotar(len(marcadas)),
                    "alertas_con_reclamo_pct": _pct(len(marcadas & con_reclamo), len(marcadas)),
                    "nota_de_credito_pct": _pct(int((resueltos_regla["estado"] == "nota_de_credito").sum()),
                                                len(resueltos_regla)),
                    "monto_reclamable_cubierto": _monto(anticipados),
                }
        salida["por_tipo_de_alerta"][tipo] = detalle
    return salida


def _cobertura(datos, alertas, registro_del_periodo=None):
    """Qué parte del consumo ve la auditoría.

    El reporte de consumo, la facturación y los contratos son de un solo proveedor; el registro
    interno anota las cargas de todas las redes. Por mes, cuántas cargas trae el reporte frente a
    los pedidos del registro, y si los pedidos rendidos sin carga son de vehículos que el reporte
    no trae ese mes (falta cobertura) o que sí trae (falta la carga). Los meses cuentan todos los
    pedidos del período (`registro_del_periodo`), también los de días sin cargas en el reporte.
    """
    consumo, registro = datos["consumo"], datos.get("solicitudes")
    mes_carga = pd.to_datetime(consumo["fecha"]).dt.strftime("%Y-%m")
    cobertura = {"alcance": {"reporte_de_consumo": "un proveedor", "facturacion": "un proveedor",
                             "contratos": "un proveedor", "registro_interno": "todas las redes"}}
    por_mes = {"cargas_del_reporte": mes_carga.value_counts()}
    if registro is not None and len(registro):
        todos = registro if registro_del_periodo is None else registro_del_periodo
        mes_todos = leer_fecha(todos["fecha"]).dt.strftime("%Y-%m")
        otra_red_todos = todos["estacion_servicio"] == ESTACION_AJENA
        por_mes["pedidos_del_proveedor"] = mes_todos[~otra_red_todos].value_counts()
        por_mes["pedidos_de_otra_red"] = mes_todos[otra_red_todos].value_counts()
        mes_pedido = leer_fecha(registro["fecha"]).dt.strftime("%Y-%m")
        otra_red = registro["estacion_servicio"] == ESTACION_AJENA
        del_proveedor = registro[~otra_red]
        con_carga = set(zip(consumo["vehiculo_id"], mes_carga))
        sin_carga = set(alertas.loc[alertas["regla"] == "rendida_sin_carga", "id_registro"])
        huerfanos = del_proveedor[del_proveedor["id"].isin(sin_carga)]
        en_el_reporte = [(v, m) in con_carga for v, m in zip(huerfanos["vehiculo_id"], mes_pedido[huerfanos.index])]
        vehiculos = set(del_proveedor["vehiculo_id"].dropna())
        fuera = cargas_fuera_del_reporte(registro)
        cobertura |= {
            "pedidos_del_proveedor_por_carga_del_reporte": dos_cifras(len(del_proveedor) / max(len(consumo), 1)),
            "vehiculos_con_pedidos_del_proveedor_en_el_reporte_pct": _pct(
                len(vehiculos & set(consumo["vehiculo_id"])), len(vehiculos)),
            "rendidos_sin_carga_con_el_vehiculo_en_el_reporte_ese_mes_pct": _pct(sum(en_el_reporte), len(en_el_reporte)),
            "cargas_de_otra_red_que_cierran_tramos": acotar(int(fuera["odometro"].notna().sum()) if fuera is not None else 0),
        }
    facturas, detalle = datos.get("facturacion"), datos.get("facturacion_detalle")
    if facturas is not None and detalle is not None:
        por_mes["lineas_facturadas"] = detalle["numero_factura"].map(
            facturas.set_index("numero_factura")["periodo"]).value_counts()
    # concat y no asignación de columnas: así quedan también los meses sin cargas en el reporte
    tabla = pd.concat(por_mes, axis=1).fillna(0).sort_index()
    cobertura["por_mes"] = {mes: {c: acotar(int(v)) for c, v in fila.items()} for mes, fila in tabla.iterrows()}
    return cobertura


def _bandas_diferencia(valores):
    """Bandas de la diferencia relativa (ya en valor absoluto): exacta, ≤0,1 %, ≤0,5 %, ≤2 %, más."""
    valores = np.asarray(valores, dtype=float)
    return np.select([valores == 0, valores <= CORTES_DIFERENCIA_IMPORTES[0],
                      valores <= CORTES_DIFERENCIA_IMPORTES[1], valores <= CORTES_DIFERENCIA_IMPORTES[2]],
                     list(BANDAS_DIFERENCIA_IMPORTES[:4]), default=BANDAS_DIFERENCIA_IMPORTES[4])


def _bandas_cruce_de_tiempo(minutos):
    """Banda de |Δ| en minutos de las cargas sin pedido: el corte queda en la banda de abajo (≤)."""
    minutos = np.asarray(minutos, dtype=float)
    return np.select([minutos <= CORTES_CRUCE_MINUTOS[0], minutos <= CORTES_CRUCE_MINUTOS[1],
                      minutos <= CORTES_CRUCE_MINUTOS[2], minutos <= CORTES_CRUCE_MINUTOS[3]],
                     list(BANDAS_CRUCE_TIEMPO[:4]), default=BANDAS_CRUCE_TIEMPO[4])


def _bandas_de_que_cruzan(minutos):
    """Banda de |Δ| en minutos de los pares que cruzan: el corte queda en la banda de abajo (≤)."""
    minutos = np.abs(np.asarray(minutos, dtype=float))
    return np.select([minutos <= CORTES_QUE_CRUZAN[0], minutos <= CORTES_QUE_CRUZAN[1],
                      minutos <= CORTES_QUE_CRUZAN[2], minutos <= CORTES_QUE_CRUZAN[3]],
                     list(BANDAS_CRUCE_QUE_CRUZAN[:4]), default=BANDAS_CRUCE_QUE_CRUZAN[4])


def _bandas_de_precio_facturado(razones):
    """Banda del cociente precio unitario facturado / precio unitario del reporte."""
    r = np.asarray(razones, dtype=float)
    return np.select([r < CORTES_PRECIO_FACTURADO[0],
                      (r >= CORTES_PRECIO_FACTURADO[0]) & (r < CORTES_PRECIO_FACTURADO[1]),
                      (r >= CORTES_PRECIO_FACTURADO[1]) & (r < CORTES_PRECIO_FACTURADO[2]),
                      (r >= CORTES_PRECIO_FACTURADO[2]) & (r <= CORTES_PRECIO_FACTURADO[3])],
                     list(BANDAS_PRECIO_FACTURADO[:4]), default=BANDAS_PRECIO_FACTURADO[4])


def _bandas_de_razon_entre_precios(razones):
    """Banda de la razón entre los dos precios unitarios del reporte, con tolerancia en 0,98."""
    r = np.asarray(razones, dtype=float)
    bajo = VALOR_RAZON_ENTRE_PRECIOS - TOLERANCIA_RAZON_ENTRE_PRECIOS
    alto = VALOR_RAZON_ENTRE_PRECIOS + TOLERANCIA_RAZON_ENTRE_PRECIOS
    return np.select([r < 0.97, (r >= 0.97) & (r < bajo), (r >= bajo) & (r <= alto),
                      (r > alto) & (r <= 0.99)],
                     list(BANDAS_RAZON_ENTRE_PRECIOS[:4]), default=BANDAS_RAZON_ENTRE_PRECIOS[4])


def _partes_bandas(etiquetas, serie, total):
    """Conteo por banda con el total visible: ninguna parte chica se puede recuperar por resta."""
    partes = {e: int((np.asarray(serie) == e).sum()) for e in etiquetas}
    return {"total": acotar(total), **_partes_sin_resta(total, partes)}


def _partes_bandas_por(etiquetas, serie, claves):
    """Conteo por banda para cada valor de `claves` (sin nulos), con `acotar`.

    La entrada no publica total, así que no hay resta que impedir adentro: la protección contra los
    totales del bloque (el global, los de las bandas y los de los hijos) vive en `_protege_el_eje`.
    """
    serie, claves = np.asarray(serie, dtype=object), pd.Series(claves)
    salida = {}
    for clave in sorted(set(claves.dropna())):
        elegidas = (claves == clave).to_numpy()
        salida[str(clave)] = {e: acotar(int((serie[elegidas] == e).sum())) for e in etiquetas}
    return salida


def _cruce_registro_ventanas(datos, pares=None, sin_carga=None):
    """Diagnóstico del cruce con el registro (H8): qué queda fuera por la ventana de horario.

    De las cargas que el cruce con contexto deja sin pedido, cuántas tienen un pedido del mismo
    vehículo por dominio (normalizado) a menos de 3, 6, 12 y 24 horas; cuántos pedidos rendidos quedan
    sin carga; cómo se reparten los minutos de los pares que sí cruzan; y todo por mes y por tipo de
    vehículo. Se agrupa por dominio, sin producto cartesiano.
    """
    consumo, flota = datos["consumo"], datos["flota"]
    registro = datos.get("solicitudes")
    if registro is None or not len(registro):
        return None
    pedidos = registro[registro["estacion_servicio"] != ESTACION_AJENA]
    if pares is None or sin_carga is None:
        pares, sin_carga = cruzar_registro(consumo, registro, flota=flota)

    instante_carga = (pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(
        consumo["hora"].astype("string").fillna("00:00:00"))).to_numpy()
    instante_pedido = (leer_fecha(pedidos["fecha"]) + pd.to_timedelta(
        pedidos["hora"].astype("string").fillna("00:00:00"))).to_numpy()
    tipo_de_matricula = flota.dropna(subset=["Matricula"]).drop_duplicates("Matricula").set_index(
        "Matricula")["TipoVehiculo"]
    dominio_de_matricula = flota.dropna(subset=["Matricula"]).drop_duplicates("Matricula").set_index(
        "Matricula")["Dominio"]

    def series(ids, valores):
        return pd.Series(np.asarray(valores), index=ids).pipe(
            lambda s: s[s.index.notna() & ~s.index.duplicated()])

    ic = series(consumo["id"], instante_carga)
    ip = series(pedidos["id"], instante_pedido)

    # (a) De las cargas sin pedido, la más cercana por dominio del mismo vehículo, en bandas de |Δ|
    sin_pedido = pares["registro_id"].isna().to_numpy()
    dominio_carga = normalizar_dominio(consumo["vehiculo_id"].map(dominio_de_matricula).fillna(consumo["dominio"]))
    por_dominio = {}
    for dom, sub in pd.DataFrame({"dom": normalizar_dominio(pedidos["dominio"]).values,
                                  "instante": instante_pedido}).dropna(subset=["dom"]).groupby("dom"):
        por_dominio[dom] = np.sort(sub["instante"].to_numpy())
    bandas_carga = np.empty(len(consumo), dtype=object)
    bandas_carga[:] = BANDAS_CRUCE_TIEMPO[-1]
    for fila in np.flatnonzero(sin_pedido):
        instantes = por_dominio.get(dominio_carga.iloc[fila])
        if instantes is None or not len(instantes):
            continue
        ubicacion = int(np.searchsorted(instantes, instante_carga[fila]))
        minutos = np.inf
        if ubicacion < len(instantes):
            minutos = min(minutos, (instantes[ubicacion] - instante_carga[fila]) / np.timedelta64(1, "m"))
        if ubicacion > 0:
            minutos = min(minutos, (instante_carga[fila] - instantes[ubicacion - 1]) / np.timedelta64(1, "m"))
        bandas_carga[fila] = str(_bandas_cruce_de_tiempo([minutos])[0])
    total_sin_pedido = int(sin_pedido.sum())

    # (c) Minutos de los pares que cruzan, en bandas de |Δ|
    cruzadas = pares["registro_id"].dropna()
    minutos = ((ic.reindex(cruzadas.index).to_numpy() - ip.reindex(cruzadas.values).to_numpy())
               / np.timedelta64(1, "m"))
    bandas_pares = _bandas_de_que_cruzan(minutos)

    # (d) Cargas sin pedido y pedidos sin carga, por mes y por tipo de vehículo
    mes_carga = leer_fecha(consumo["fecha"]).dt.strftime("%Y-%m").to_numpy()
    tipo_carga = consumo["vehiculo_id"].map(tipo_de_matricula).fillna("sin_dato").to_numpy()
    mes_pedido = leer_fecha(sin_carga["fecha"]).dt.strftime("%Y-%m").to_numpy() if len(sin_carga) else np.array([])
    tipo_pedido = sin_carga["vehiculo_id"].map(tipo_de_matricula).fillna("sin_dato").to_numpy() if len(sin_carga) else np.array([])

    def por_clave(claves_carga, claves_pedido):
        salida = {}
        for clave in sorted(set(np.asarray(claves_carga, dtype=object)) | set(np.asarray(claves_pedido, dtype=object)),
                            key=str):
            propias = int((np.asarray(claves_carga, dtype=object) == clave).sum())
            ajenas = int((np.asarray(claves_pedido, dtype=object) == clave).sum())
            salida[str(clave)] = {"cargas_sin_pedido": acotar(propias), "pedidos_sin_carga": acotar(ajenas)}
        return salida

    salida = {
        "cargas_sin_pedido": {
            "total": acotar(total_sin_pedido),
            "con_pedido_del_mismo_vehiculo": _partes_bandas(
                BANDAS_CRUCE_TIEMPO, bandas_carga[sin_pedido], total_sin_pedido),
        },
        "pedidos_sin_carga": {"total": acotar(len(sin_carga))},
        "minutos_de_los_pares_que_cruzan": _partes_bandas(
            BANDAS_CRUCE_QUE_CRUZAN, bandas_pares, len(bandas_pares)),
        "por_mes": por_clave(mes_carga[sin_pedido], mes_pedido),
        "por_tipo_de_vehiculo": por_clave(tipo_carga[sin_pedido], tipo_pedido),
    }
    _protege_el_eje(salida, "por_mes")
    _protege_el_eje(salida, "por_tipo_de_vehiculo")
    return salida


def _facturacion_detalle_precios(datos):
    """Diagnóstico del detalle de facturación (H9): precios, importes y líneas.

    Cociente del precio unitario facturado sobre cada precio unitario del reporte, la razón entre los
    dos precios unitarios del reporte, la diferencia de la deuda con la suma de las líneas y con el
    total del PDF, y los conteos de líneas duplicadas, sin carga, de otro concepto o de otro mes.
    """
    detalle = datos.get("facturacion_detalle")
    if detalle is None or not len(detalle):
        return None
    consumo, facturas = datos["consumo"], datos.get("facturacion")
    precios = datos.get("precios_reporte")
    referencia = detalle["referencia_consumo"]
    mes_factura = (detalle["numero_factura"].map(facturas.set_index("numero_factura")["periodo"])
                   if facturas is not None else pd.Series(pd.NA, index=detalle.index))
    mes_carga = pd.Series(leer_fecha(consumo["fecha"]).dt.strftime("%Y-%m").values,
                          index=consumo["id"]).pipe(lambda s: s[~s.index.duplicated()])
    resultado = {}

    # (a) El precio facturado contra cada precio unitario del reporte: el cociente, en bandas
    if precios is not None:
        columnas = [c for c in precios.columns if c.startswith("precio_")]
        cargas = precios.set_index("id").pipe(lambda d: d[~d.index.duplicated()])
        producto = pd.Series(consumo["producto"].values, index=consumo["id"]).pipe(
            lambda s: s[~s.index.duplicated()])
        cocientes = {}
        for columna in columnas:
            razon = detalle["precio_unitario"].to_numpy() / referencia.map(cargas[columna]).to_numpy()
            valido = np.isfinite(razon)
            r = razon[valido]
            etiquetas = _bandas_de_precio_facturado(r)
            bloque = {
                **_partes_bandas(BANDAS_PRECIO_FACTURADO, etiquetas, int(valido.sum())),
                "por_mes": _partes_bandas_por(BANDAS_PRECIO_FACTURADO, etiquetas, mes_factura.to_numpy()[valido]),
                "por_producto": _partes_bandas_por(BANDAS_PRECIO_FACTURADO, etiquetas,
                                                   referencia.map(producto).to_numpy()[valido]),
            }
            _protege_el_eje(bloque, "por_mes")
            _protege_el_eje(bloque, "por_producto")
            cocientes[columna] = bloque
        resultado["precio_facturado_sobre_cada_precio_unitario"] = cocientes

        # La razón entre los dos precios unitarios del reporte (el segundo sobre el primero), por carga
        if len(columnas) >= 2:
            razon = (cargas[columnas[1]] / cargas[columnas[0]]).replace([np.inf, -np.inf], np.nan).dropna()
            etiquetas = _bandas_de_razon_entre_precios(razon)
            bloque = {
                **_partes_bandas(BANDAS_RAZON_ENTRE_PRECIOS, etiquetas, len(etiquetas)),
                "por_mes": _partes_bandas_por(BANDAS_RAZON_ENTRE_PRECIOS, etiquetas,
                                              mes_carga.reindex(razon.index).to_numpy()),
            }
            _protege_el_eje(bloque, "por_mes")
            resultado["razon_entre_precios_unitarios"] = bloque

    # (b) Deuda contra la suma de las líneas y contra el total del PDF, en bandas de diferencia relativa
    if facturas is not None and len(facturas) and "importe" in detalle.columns:
        facturas = facturas.set_index("numero_factura")
        mes_de_factura = facturas["periodo"]
        suma = detalle.groupby("numero_factura")["importe"].sum().reindex(facturas.index)
        deuda, pdf = facturas["total_monto"], facturas["total_pdf"]

        con_lineas = suma.notna() & suma.ne(0) & deuda.notna()
        etiquetas_lineas = _bandas_diferencia(((deuda - suma) / suma).abs()[con_lineas])
        bloque = {
            **_partes_bandas(BANDAS_DIFERENCIA_IMPORTES, etiquetas_lineas, int(con_lineas.sum())),
            "por_mes": _partes_bandas_por(BANDAS_DIFERENCIA_IMPORTES, etiquetas_lineas,
                                          mes_de_factura[con_lineas].to_numpy()),
        }
        _protege_el_eje(bloque, "por_mes")
        resultado["diferencias_entre_deuda_y_lineas"] = bloque

        sin_pdf = pdf.isna().to_numpy()
        con_deuda = (deuda.notna() & deuda.ne(0) & ~pdf.isna()).to_numpy()
        etiquetas_pdf = pd.Series("sin_pdf", index=facturas.index, dtype=object)
        etiquetas_pdf[con_deuda] = _bandas_diferencia(((pdf - deuda) / deuda).abs()[con_deuda])
        con_sin_pdf = (*BANDAS_DIFERENCIA_IMPORTES, "sin_pdf")
        bloque = {
            **_partes_bandas(con_sin_pdf, etiquetas_pdf.to_numpy(), len(facturas)),
            "por_mes": _partes_bandas_por(con_sin_pdf, etiquetas_pdf.to_numpy(), mes_de_factura.to_numpy()),
        }
        _protege_el_eje(bloque, "por_mes")
        resultado["diferencias_entre_pdf_y_deuda"] = bloque

    # (c) Líneas: duplicadas, sin carga en el reporte, de otro concepto y de otro mes que su carga
    repetidas = referencia.dropna().value_counts()
    mes_carga_linea = referencia.map(mes_carga)
    con_carga = mes_carga_linea.notna()
    resultado["lineas"] = {
        "cargas_facturadas_mas_de_una_vez": acotar(int((repetidas > 1).sum())),
        "lineas_sin_carga_en_el_reporte": acotar(int((~referencia.isin(set(consumo["id"]))).sum())),
        "lineas_con_concepto_distinto_de_combustible": acotar(int((detalle["concepto"] != "COMBUSTIBLE").sum())),
        "mes_de_facturacion": {
            "en_el_mismo_mes_que_su_carga": acotar(int((con_carga & (mes_factura == mes_carga_linea)).sum())),
            "en_otro_mes": acotar(int((con_carga & (mes_factura != mes_carga_linea)).sum())),
        },
    }
    return resultado


BLOQUES_DE_DIAGNOSTICO = {
    "exceso_volumetrico": lambda datos, alertas: _exceso_volumetrico(datos["consumo"], datos["flota"]),
    "exceso_volumetrico_detalle": lambda datos, alertas: _exceso_volumetrico_detalle(
        datos["consumo"], datos["flota"], alertas),
    "fraccionamiento_detalle": lambda datos, alertas: _fraccionamiento_detalle(datos, alertas),
}


def _sobre_agregado(diagnostico, reglas, hipotesis, cruce, modelos):
    """El sobre común de la salida: versión, fecha, revisión pendiente y los bloques."""
    return {"perfilador_version": VERSION, "tipo": "auditoria_agregada",
            "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "revision": {"revisado": False, "responsable": None, "fecha": None, "notas": None},
            "reglas_de_privacidad": f"solo agregados; grupos de menos de {MINIMO_GRUPO} como 1–{MINIMO_GRUPO - 1}",
            "diagnostico": diagnostico, "reglas": reglas, "hipotesis": hipotesis, "cruce_registro": cruce,
            "modelos": modelos}


def auditar(tablas, proveedor=None, semillas=SEMILLAS_ENTRENAMIENTO, n_flota=200, solo=None):
    """Corre las reglas y los modelos y devuelve la auditoría agregada.

    Con `solo`, en cambio, arma los datos con el adaptador y calcula únicamente ese bloque de
    diagnóstico, salteando las reglas y los modelos: sirve para probar una tanda sin esperar la
    corrida entera.
    """
    if solo is not None and solo not in BLOQUES_DE_DIAGNOSTICO:
        raise ValueError(f"bloque desconocido: {solo}. Los disponibles son: "
                         f"{', '.join(sorted(BLOQUES_DE_DIAGNOSTICO))}.")
    datos, diagnostico = adaptar(tablas, proveedor)
    if solo is not None:
        valores = _proteger(solo, BLOQUES_DE_DIAGNOSTICO[solo], datos, None)
        return _sobre_agregado({solo: valores}, {}, {}, {}, {})
    consumo = datos["consumo"]
    registro = datos.get("solicitudes")
    # Con el registro entero: un dominio que figura en un pedido de otro mes también es de un móvil
    diagnostico["vinculacion"] = _vinculacion(consumo, datos["flota"], datos.get("telemetria"), registro)
    if registro is not None:
        # Solo los días con cargas en el reporte: en un día que el reporte no trae, todo pedido
        # quedaría "sin carga" (el reporte puede tener meses enteros sin descargar)
        fechas = leer_fecha(registro["fecha"]).dt.normalize()
        dias = pd.to_datetime(consumo["fecha"]).dt.normalize()
        registro_del_periodo = registro[fechas.between(dias.min(), dias.max())]
        # Las cargas de otra red no están en el reporte en ningún día: se conservan todas las del
        # período, porque cierran los tramos del odómetro entre cargas del reporte
        otra_red = registro["estacion_servicio"] == ESTACION_AJENA
        registro = registro[fechas.between(dias.min(), dias.max()) & (fechas.isin(set(dias)) | otra_red)]
        datos["solicitudes"] = registro
        diagnostico["registro"] |= {
            "pedidos_en_el_periodo_del_reporte": acotar(len(registro_del_periodo)),
            "pedidos_en_dias_con_cargas_del_reporte": acotar(len(registro)),
            "dias_con_cargas_del_reporte": acotar(dias.nunique()),
            "dias_del_periodo": acotar((dias.max() - dias.min()).days + 1),
        }

    facturas = datos.get("facturacion")
    diagnostico["facturacion_detalle_precios"] = None
    if facturas is not None:
        # Solo las facturas de los meses que el reporte cubre completos: en un mes parcial, las
        # líneas de los días que falta descargar quedarían "sin carga" y el total no conciliaría
        meses = meses_completos(consumo["fecha"])
        antes = len(facturas)
        facturas = facturas[facturas["periodo"].isin(meses)]
        datos["facturacion"] = facturas
        datos["facturacion_detalle"] = datos["facturacion_detalle"][
            datos["facturacion_detalle"]["numero_factura"].isin(facturas["numero_factura"])]
        diagnostico["facturacion"]["meses_completos_del_reporte"] = sorted(meses)
        diagnostico["facturacion"]["facturas_en_meses_completos"] = acotar(len(facturas))
        diagnostico["facturacion"]["facturas_fuera_de_meses_completos"] = acotar(antes - len(facturas))
        diagnostico["facturacion"]["lineas_con_carga_del_reporte_en_meses_completos_pct"] = _pct(
            int(datos["facturacion_detalle"]["referencia_consumo"].isin(consumo["id"]).sum()),
            len(datos["facturacion_detalle"])) if len(datos["facturacion_detalle"]) else None
        diagnostico["facturacion_detalle_precios"] = _facturacion_detalle_precios(datos)

    alertas = reglas_del_dataset(datos)
    diagnostico["odometro"] = _odometro(datos, alertas)
    diagnostico["odometro"]["retrocesos"] = _retrocesos(datos["consumo"], alertas)
    diagnostico["odometro"]["retrocesos_estudio"] = _retrocesos_estudio(datos, alertas)
    diagnostico["contingencias"] = _contingencias(datos["consumo"])
    diagnostico["exceso_volumetrico"] = _proteger("exceso_volumetrico", _exceso_volumetrico,
                                                  datos["consumo"], datos["flota"])
    diagnostico["exceso_volumetrico_detalle"] = _proteger("exceso_volumetrico_detalle",
                                                          _exceso_volumetrico_detalle, datos["consumo"],
                                                          datos["flota"], alertas)
    diagnostico["fraccionamiento_detalle"] = _proteger("fraccionamiento_detalle", _fraccionamiento_detalle,
                                                       datos, alertas)
    diagnostico["cobertura"] = _cobertura(datos, alertas, registro_del_periodo if registro is not None else None)
    por_regla = {}
    for regla, grupo in alertas.groupby("regla"):
        ids = set(grupo["id_registro"])
        tabla, total = _unidad(ids, datos)
        por_regla[regla] = {"alertas": acotar(len(ids)), "pct": _pct(len(ids), total), "sobre": tabla}
        if "causa_probable" in grupo.columns and grupo["causa_probable"].notna().any():
            # Qué parte de las alertas tiene la firma de un error de carga (#24)
            causas = grupo.drop_duplicates("id_registro")["causa_probable"].value_counts()
            por_regla[regla]["causa_probable_pct"] = {c: _pct(int(n), len(ids)) for c, n in causas.items()}
        if "documentada" in grupo.columns:
            # Qué parte de las alertas ya se investigó y con qué resultado (#36): solo en agregado
            con_resultado = grupo[grupo["documentada"]].drop_duplicates("id_registro")
            por_regla[regla]["con_resultado_pct"] = _pct(len(con_resultado), len(ids))
            por_regla[regla]["resultado_pct"] = {r: _pct(int(n), len(con_resultado))
                                                 for r, n in con_resultado["resultado_observacion"].value_counts().items()}

    if datos.get("reclamos") is not None:
        diagnostico["reclamos"] = _reclamos(datos, alertas, set(alertas["regla"]))

    factura_de = dict(zip(datos["facturacion_detalle"]["numero_linea"], datos["facturacion_detalle"]["numero_factura"])) \
        if datos.get("facturacion_detalle") is not None else {}
    hipotesis = {}
    corrieron = set(alertas["regla"])
    for h in hipotesis_del_escenario("realista"):
        ingenua = reglas_de(h["reglas"][0][0])
        # El nivel más contextual que corrió: sin GPS diario, por ejemplo, H5 usa el odómetro
        niveles = [(regla, descripcion) for regla, descripcion in h["reglas"][1:] if set(reglas_de(regla)) & corrieron]
        if not niveles and not set(ingenua) & corrieron:
            continue
        regla_contexto, descripcion = niveles[-1] if niveles else (None, "no corrió")
        contexto = reglas_de(regla_contexto)

        def marcadas(reglas):
            ids = set(alertas.loc[alertas["regla"].isin(reglas), "id_registro"])
            return {factura_de.get(i, i) for i in ids} if h.get("nivel") == "factura" else ids

        a, b = marcadas(ingenua), marcadas(contexto)
        hipotesis[h["codigo"]] = {"regla_con_contexto": descripcion, "ingenua": acotar(len(a)), "con_contexto": acotar(len(b)),
                                  "en_ambas": acotar(len(a & b)), "solo_con_contexto": acotar(len(b - a))}

    # Cruce con el registro interno: cuántas cargas cruzan y con qué diferencia de horario
    cruce = {}
    diagnostico["cruce_registro_ventanas"] = None
    if registro is not None and len(registro):
        voraz, _ = cruzar_registro(consumo, registro, voraz=True)
        contexto, sin_carga_contexto = cruzar_registro(consumo, registro, flota=datos["flota"])
        instante_carga = pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(consumo["hora"])
        instante_pedido = leer_fecha(registro["fecha"]) + pd.to_timedelta(registro["hora"].fillna("00:00:00"))
        pares = voraz["registro_id"].dropna()
        # Por id, sin los ids nulos ni repetidos (una carga sin remito no tiene id): un eje con etiquetas
        # duplicadas no se puede reindexar
        ic = pd.Series(instante_carga.values, index=consumo["id"]).pipe(lambda s: s[s.index.notna() & ~s.index.duplicated()])
        ip = pd.Series(instante_pedido.values, index=registro["id"]).pipe(lambda s: s[s.index.notna() & ~s.index.duplicated()])
        minutos = ((ic.reindex(pares.index).values
                    - ip.reindex(pares.values).values) / np.timedelta64(1, "m"))
        cruce = {"cargas_con_pedido_cruce_voraz_pct": _pct(voraz["registro_id"].notna().sum(), len(voraz)),
                 "cargas_con_pedido_cruce_con_contexto_pct": _pct(contexto["registro_id"].notna().sum(), len(contexto)),
                 "minutos_de_la_carga_despues_del_pedido": _cuantiles(pd.Series(minutos))}
        diagnostico["cruce_registro_ventanas"] = _cruce_registro_ventanas(datos, contexto, sin_carga_contexto)

    # Modelos: el supervisado se entrena con datos sintéticos (no hay etiquetas reales)
    variables = _variables(datos)
    modelo, referencia = _modelo_sintetico(semillas, n_flota)
    probabilidad = pd.Series(modelo.predict_proba(variables[modelo.feature_names_in_])[:, 1], index=variables.index)
    rareza, anomala = entrenar_isolation_forest(variables)
    marcadas_contexto = set(alertas.loc[alertas["regla"].isin(REGLAS_CONTEXTO), "id_registro"]) & set(variables.index)
    top = {"modelo_supervisado": set(probabilidad.nlargest(REVISION).index),
           "isolation_forest": set(rareza.nlargest(REVISION).index)}
    modelos = {
        "cargas_puntuadas": acotar(len(variables)),
        "supervisado_probabilidad": _cuantiles(probabilidad, (0.05, 0.5, 0.95, 0.99)),
        "supervisado_mayor_a_0_5_pct": _pct(int((probabilidad > 0.5).sum()), len(probabilidad)),
        "isolation_forest_anomalas_pct": _pct(int(anomala.sum()), len(anomala)),
        f"coincidencia_top_{REVISION}": {
            "supervisado_e_isolation_forest": acotar(len(top["modelo_supervisado"] & top["isolation_forest"])),
            "supervisado_y_reglas_con_contexto": acotar(len(top["modelo_supervisado"] & marcadas_contexto)),
            "isolation_forest_y_reglas_con_contexto": acotar(len(top["isolation_forest"] & marcadas_contexto)),
        },
        "variables": {c: {"real": _cuantiles(variables[c]), "sintetico": _cuantiles(referencia[c])}
                      for c in variables.columns},
    }
    return _sobre_agregado(diagnostico, por_regla, hipotesis, cruce, modelos)
