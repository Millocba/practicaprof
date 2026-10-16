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
from datetime import datetime, timezone

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
                              subforma_de_los_retrocesos, vinculos_de_la_carga, vinculos_del_pedido,
                              vinculos_por_identificador)
from perfilador.adaptador import adaptar
from perfilador.controles import acotar
from perfilador.perfil import MINIMO_GRUPO, VERSION, cuantil_publicable, dos_cifras

SEMILLAS_ENTRENAMIENTO = (1001, 1002, 1003)
REVISION = 100          # tamaño de la cola con que se comparan los métodos
COBERTURA_MES_COMPLETO = 0.9   # un mes está completo si el reporte trae cargas en el 90% de sus días...
ULTIMOS_DIAS_DEL_MES = 3       # ...y en alguno de sus últimos 3 días (un mes en curso no está completo)


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

    return {
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


def _exceso_volumetrico(consumo, flota):
    """Diagnóstico agregado de H3b: ratios, cobertura y momento en que aparece el exceso."""
    capacidad = pd.to_numeric(consumo["vehiculo_id"].map(
        flota.set_index("Matricula")["CapacidadTanque"]), errors="coerce")
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

    Un conteo de 1 a 19 sale como "1–19"; pero si el total sale entero y esa es la única parte oculta, restarle
    las otras lo devolvería. Por eso se oculta también la parte visible más chica (`None`): quien resta solo
    obtiene la suma de las dos, que no revela ninguna.
    """
    salida = {k: acotar(v) for k, v in partes.items()}
    chicas = [k for k, v in partes.items() if 0 < v < MINIMO_GRUPO]
    visibles = {k: v for k, v in partes.items() if v >= MINIMO_GRUPO}
    if len(chicas) == 1 and total >= MINIMO_GRUPO and visibles:
        salida[min(visibles, key=visibles.get)] = None
    return salida


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


def auditar(tablas, proveedor=None, semillas=SEMILLAS_ENTRENAMIENTO, n_flota=200):
    datos, diagnostico = adaptar(tablas, proveedor)
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

    alertas = reglas_del_dataset(datos)
    diagnostico["odometro"] = _odometro(datos, alertas)
    diagnostico["odometro"]["retrocesos"] = _retrocesos(datos["consumo"], alertas)
    diagnostico["odometro"]["retrocesos_estudio"] = _retrocesos_estudio(datos, alertas)
    diagnostico["contingencias"] = _contingencias(datos["consumo"])
    diagnostico["exceso_volumetrico"] = _exceso_volumetrico(datos["consumo"], datos["flota"])
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
    if registro is not None and len(registro):
        voraz, _ = cruzar_registro(consumo, registro, voraz=True)
        contexto, _ = cruzar_registro(consumo, registro, flota=datos["flota"])
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
    return {
        "perfilador_version": VERSION, "tipo": "auditoria_agregada",
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "revision": {"revisado": False, "responsable": None, "fecha": None, "notas": None},
        "reglas_de_privacidad": f"solo agregados; grupos de menos de {MINIMO_GRUPO} como 1–{MINIMO_GRUPO - 1}",
        "diagnostico": diagnostico, "reglas": por_regla, "hipotesis": hipotesis, "cruce_registro": cruce,
        "modelos": modelos,
    }
