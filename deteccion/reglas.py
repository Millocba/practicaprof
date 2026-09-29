"""Línea base de detección por reglas.

Cada regla recibe solo las entidades generadas (flota y consumo) y devuelve alertas.
Ninguna regla lee el ground truth: la evaluación contra la verdad de referencia se
hace aparte, en `deteccion.evaluacion`.

Una alerta es una fila con:
- id_registro: id de la transacción de consumo alertada
- tipo_anomalia: tipo que la regla atribuye (mismo vocabulario que el ground truth)
- regla: nombre de la regla que la produjo
- detalle: explicación legible del motivo

Para qué sirve este archivo
---------------------------
Es el corazón de la detección. Una "regla" es un control escrito a mano con un
criterio explícito, como los que aplicaría un auditor: "si los litros cargados
superan la capacidad del tanque, alertar". Su gran ventaja es que siempre se puede
explicar por qué se generó cada alerta. Sirven como "línea base": el punto de
comparación contra el que se miden los modelos de `modelo.py` y `priorizacion.py`.

Organización del archivo
------------------------
1. Reglas de calidad de datos: duplicados, campos vacíos y dominios (patentes) que
   no existen en la flota.
2. Reglas básicas de comportamiento: exceso de litros y problemas de odómetro.
3. Reglas con contexto (escenario realista): usan historial, GPS, estado de la flota.
4. Circuito solicitud -> carga -> factura: cruzan cada carga con su autorización y
   cada factura con las cargas registradas.
5. `ejecutar_reglas`: aplica todas las reglas disponibles y junta las alertas.

Regla ingenua vs. regla con contexto
------------------------------------
Muchas reglas vienen en pares. La "ingenua" usa un criterio simple y fijo; la "con
contexto" agrega información para descartar casos que parecen sospechosos pero
tienen explicación (un odómetro que se cambió, un viaje largo real, una solicitud
que se aprobó un día después). Cada alerta de un caso normal es un "falso
positivo" o falsa alarma: le hace perder tiempo a quien revisa. Comparar ambas
versiones (ver `hipotesis.py`) mide cuánto ayuda el contexto a reducir esas falsas
alarmas sin dejar escapar anomalías reales.

Nota sobre el código: se usa pandas, que trabaja con tablas completas de una vez
(operaciones "vectorizadas") en lugar de recorrer fila por fila. Por eso muchas
líneas del estilo `consumo[consumo["litros"] > x]` significan "quedarse con las
filas de consumo que cumplen la condición".
"""
import numpy as np
import pandas as pd

# Columnas que tiene toda tabla de alertas, sea cual sea la regla que la produjo
COLUMNAS_ALERTA = ["id_registro", "tipo_anomalia", "regla", "detalle"]

# Campos que toda transacción debería traer completos
CAMPOS_OBLIGATORIOS = ["estacion", "conductor", "odometro"]

# Umbrales
# Un umbral es el valor límite a partir del cual una regla alerta. Se definen todos
# juntos acá, con nombre, para poder ajustarlos sin buscar números sueltos en el código.
SALTO_FIJO_KM = 500            # km entre dos cargas...
SALTO_FIJO_DIAS = 7            # ...en esta cantidad de días o menos
SALTO_HISTORIAL_EXCESO_KM = 1000  # km por encima de lo esperado según el propio vehículo
RETROCESO_LEVE_KM = 1000       # un retroceso menor se clasifica como leve
REINICIO_ODOMETRO_KM = 10000   # una lectura menor tras un retroceso sugiere un odómetro nuevo
DESVIO_TIPEO_KM = 500          # desvío mínimo de una lectura aislada para suponer un error de tipeo
FRACCION_INICIAL = 0.25        # primeras cargas del vehículo que definen su comportamiento habitual
FRACCIONAMIENTO_TANQUES = 1.05  # litros del día, en tanques, a partir de los que se sospecha
RENDIMIENTO_MINIMO = 0.4       # km/L del día por debajo de esta fracción de lo habitual
RENDIMIENTO_MINIMO_FRACCIONAMIENTO = 0.75
LITROS_MINIMOS_RENDIMIENTO = 0.3  # solo se evalúan días con al menos esta fracción del tanque
DISTANCIA_MAXIMA_KM = 50       # distancia de la estación a la posición del vehículo
VENTANA_SOLICITUD_DIAS = 3     # días alrededor de la carga en que se busca la solicitud
TOLERANCIA_AUTORIZADO = 0.05   # exceso sobre lo autorizado atribuible a la medición del surtidor
DIFERENCIA_CONCILIACION = 0.01  # diferencia relativa entre consumo del mes y total facturado
DIFERENCIA_ENCABEZADO = 0.005   # diferencia relativa entre el total de la factura y sus líneas
TOLERANCIA_PRECIO = 0.02        # diferencia de precio por litro entre la factura y la carga


def _alertas(df, tipo, regla, detalle):
    """Arma la tabla de alertas (con COLUMNAS_ALERTA) a partir de las filas que marcó una regla.

    Recibe: `df`, las filas marcadas (deben tener una columna `id`); `tipo`, el tipo de
    anomalía; `regla`, el nombre de la regla; y `detalle`, un texto fijo o una función
    que arma un texto distinto para cada fila. Devuelve una tabla con una alerta por
    fila, o una tabla vacía con las columnas correctas si no se marcó nada.
    Todas las reglas la usan para que sus alertas tengan siempre el mismo formato.
    """
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    return pd.DataFrame({
        "id_registro": df["id"].values,
        "tipo_anomalia": tipo,
        "regla": regla,
        "detalle": detalle(df).values if callable(detalle) else detalle,
    })


def detectar_duplicados(consumo):
    """Transacciones idénticas a otra anterior en todos los campos salvo el id.

    Un duplicado suele ser un error de carga de datos (la misma transacción registrada
    dos veces). Se alerta la copia y no la primera aparición. Recibe la tabla de
    consumo y devuelve alertas de tipo DUPLICADO.
    """
    columnas = [c for c in consumo.columns if c != "id"]
    ordenado = consumo.sort_values("id")
    duplicadas = ordenado[ordenado.duplicated(subset=columnas, keep="first")]
    return _alertas(duplicadas, "DUPLICADO", "duplicado_exacto",
                    "idéntica a una transacción anterior")


def detectar_nulos(consumo):
    """Una alerta por cada campo obligatorio vacío.

    Revisa los campos de CAMPOS_OBLIGATORIOS; cada campo genera su propia regla
    (`nulo_estacion`, `nulo_conductor`, `nulo_odometro`). Devuelve alertas de tipo VALOR_NULO.
    """
    partes = []
    for campo in CAMPOS_OBLIGATORIOS:
        vacios = consumo[consumo[campo].isna()]
        partes.append(_alertas(vacios, "VALOR_NULO", f"nulo_{campo}", f"{campo} vacío"))
    return pd.concat(partes, ignore_index=True)


def detectar_dominio_invalido(consumo, flota):
    """H1: el dominio de la transacción no corresponde a ningún vehículo de la flota.

    El "dominio" es la patente del vehículo. Si no existe en la flota, la carga no
    se puede vincular con ningún vehículo y ningún otro control puede aplicarse.
    Recibe las cargas y la flota; devuelve alertas de tipo DOMINIO_INVALIDO.
    """
    sin_vinculo = consumo[~consumo["dominio"].isin(flota["Dominio"])]
    return _alertas(sin_vinculo, "DOMINIO_INVALIDO", "dominio_sin_vinculo",
                    lambda d: "dominio " + d["dominio"].astype(str) + " no existe en la flota")


def detectar_exceso_volumetrico(consumo, flota):
    """H3a: se cargaron más litros que la capacidad del tanque del vehículo.

    Es la versión ingenua: compara cada carga con la capacidad registrada, sin mirar
    el historial (ver `detectar_exceso_sin_antecedente`). Devuelve alertas de tipo
    EXCESO_VOLUMETRICO.
    """
    # Tabla auxiliar "matrícula -> capacidad" para buscar la capacidad de cada carga
    capacidad = flota.set_index("Matricula")["CapacidadTanque"]
    datos = consumo.assign(capacidad=consumo["vehiculo_id"].map(capacidad))
    exceso = datos[datos["litros"] > datos["capacidad"]]
    return _alertas(exceso, "EXCESO_VOLUMETRICO", "litros_mayor_a_tanque",
                    lambda d: d["litros"].round(2).astype(str) + " L con tanque de "
                    + d["capacidad"].round(2).astype(str) + " L")


def secuencia_odometro(consumo, excluir_ids=()):
    """Cambio de odómetro de cada transacción respecto de la lectura válida anterior.

    Se descartan las lecturas vacías y las transacciones en `excluir_ids` (por ejemplo,
    duplicados ya detectados), para comparar cada carga con la anterior real.
    Agrega: km (cambio), dias (días transcurridos) y km_esperados (según la mediana
    de km por día del propio vehículo).

    No es una regla en sí: prepara los datos que usan todas las reglas de odómetro.
    Devuelve la tabla de cargas ordenada por vehículo y fecha, con esas columnas nuevas.
    Un `km` negativo significa que el odómetro retrocedió.
    """
    datos = consumo[consumo["odometro"].notna() & ~consumo["id"].isin(set(excluir_ids))].copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    # groupby separa las cargas por vehículo; diff() resta a cada lectura la anterior del
    # mismo vehículo (la primera carga de cada uno queda vacía porque no tiene anterior)
    grupo = datos.groupby("vehiculo_id")
    datos["km"] = grupo["odometro"].diff()
    datos["dias"] = grupo["fecha"].diff().dt.days

    # Ritmo habitual del vehículo: mediana de km por día entre cargas (robusta a los
    # propios saltos y retrocesos)
    ritmo = (datos["km"] / datos["dias"].where(datos["dias"] > 0)).clip(lower=0)
    datos["km_por_dia_habitual"] = ritmo.groupby(datos["vehiculo_id"]).transform("median")
    datos["km_esperados"] = datos["km_por_dia_habitual"] * datos["dias"]
    return datos.dropna(subset=["km"])


def _tipo_de_retroceso(km):
    """Un retroceso de menos de RETROCESO_LEVE_KM se clasifica como leve."""
    return km.gt(-RETROCESO_LEVE_KM).map({True: "ODOMETRO_REGRESIVO_LEVE", False: "ODOMETRO_REGRESIVO"})


def _alertas_de_retroceso(regresion, regla):
    """Como `_alertas`, pero para retrocesos de odómetro: el tipo (leve o no) depende de cada fila.

    Recibe las filas de la secuencia de odómetro con retroceso y el nombre de la regla.
    """
    if regresion.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    return pd.DataFrame({
        "id_registro": regresion["id"].values,
        "tipo_anomalia": _tipo_de_retroceso(regresion["km"]).values,
        "regla": regla,
        "detalle": ("retrocede " + (-regresion["km"]).astype(int).astype(str) + " km").values,
    })


def detectar_odometro_regresivo(secuencia):
    """H2: el odómetro marca menos que en la carga anterior.

    Versión ingenua: alerta cualquier retroceso, aunque se explique por un odómetro
    nuevo o un error de tipeo (ver `detectar_retroceso_con_contexto`). Un odómetro
    que retrocede puede indicar que se adulteró la lectura para ocultar kilómetros.
    Recibe la tabla de `secuencia_odometro`.
    """
    return _alertas_de_retroceso(secuencia[secuencia["km"] < 0], "odometro_disminuye")


def detectar_odometro_salto_umbral_fijo(secuencia):
    """H2 (umbral general): más de SALTO_FIJO_KM en SALTO_FIJO_DIAS días o menos.

    Usa el mismo límite para todos los vehículos, lo que genera falsas alarmas en los
    que habitualmente recorren mucho (y deja pasar saltos en los que recorren poco).
    """
    salto = secuencia[(secuencia["km"] > SALTO_FIJO_KM) & (secuencia["dias"] <= SALTO_FIJO_DIAS)]
    return _alertas(salto, "ODOMETRO_SALTO", "salto_umbral_fijo",
                    lambda d: d["km"].astype(int).astype(str) + " km en "
                    + d["dias"].astype(int).astype(str) + " días")


def detectar_odometro_salto_historial(secuencia):
    """H2 (historial individual): recorrió SALTO_HISTORIAL_EXCESO_KM más de lo que
    ese vehículo suele recorrer en la misma cantidad de días.

    A diferencia del umbral fijo, compara cada vehículo consigo mismo: lo "normal" es
    distinto para un vehículo de ruta que para uno que casi no sale.
    """
    exceso = secuencia["km"] - secuencia["km_esperados"]
    salto = secuencia[exceso > SALTO_HISTORIAL_EXCESO_KM].assign(exceso=exceso)
    return _alertas(salto, "ODOMETRO_SALTO", "salto_historial_vehiculo",
                    lambda d: d["exceso"].round().astype(int).astype(str)
                    + " km más de lo habitual para el vehículo")


# ============================================================================
# Reglas con contexto (escenario realista)
#
# Usan el historial del vehículo, el estado de la flota, las coordenadas de las
# estaciones y el GPS diario. Cada una tiene su contraparte ingenua para medir
# cuánto aporta el contexto.
# ============================================================================

def _vecinos_de_odometro(secuencia):
    """Agrega, por vehículo, las dos lecturas válidas anteriores y la siguiente.

    Mirar las lecturas vecinas permite saber si una lectura rara es un caso aislado
    (probablemente un error de tipeo) o un cambio que se mantiene.
    """
    s = secuencia.copy()
    # shift(1) trae el valor de la fila anterior del mismo vehículo; shift(-1), el de la siguiente
    s["anterior"] = s["odometro"] - s["km"]
    grupo = s.groupby("vehiculo_id")
    s["anterior2"] = grupo["anterior"].shift(1)
    s["siguiente"] = grupo["odometro"].shift(-1)
    return s


def _es_error_de_tipeo(s):
    """Transacciones cuyo cambio de odómetro se explica por una sola lectura mal cargada.

    - Hueco: esta lectura queda muy por debajo de la anterior y la siguiente vuelve a la
      secuencia (siguiente >= anterior).
    - Rebote tras un pico: la lectura anterior fue la mal cargada (quedó por encima) y esta
      vuelve a la secuencia de antes (anterior2 <= esta).
    - Pico: esta lectura queda muy por encima y la siguiente vuelve a bajar.
    - Rebote tras un hueco: la lectura anterior fue la mal cargada (quedó por debajo de la
      previa) y esta vuelve a subir.

    Devuelve una serie verdadero/falso (una por fila): verdadero si el cambio se
    explica por un error de tipeo y, por lo tanto, no debería alertarse.
    """
    # Cada condición es una columna de verdadero/falso; "&" es "y", "|" es "o", "~" es "no"
    desvio = (s["anterior"] - s["odometro"]).abs() > DESVIO_TIPEO_KM
    hueco = (s["km"] < 0) & (s["siguiente"] >= s["anterior"]) & desvio
    rebote_tras_pico = (s["km"] < 0) & (s["anterior2"] <= s["odometro"]) & desvio
    pico = (s["km"] > 0) & (s["siguiente"] < s["odometro"])
    rebote_tras_hueco = (s["km"] > 0) & (s["anterior"] < s["anterior2"])
    return hueco | rebote_tras_pico | pico | rebote_tras_hueco


def detectar_retroceso_con_contexto(secuencia):
    """H2b: retroceso que no se explica por un odómetro nuevo ni por un error de tipeo.

    - Odómetro nuevo: la lectura queda por debajo de REINICIO_ODOMETRO_KM.
    - Error de tipeo: ver `_es_error_de_tipeo`.

    Es la versión con contexto de `detectar_odometro_regresivo`: usa el historial de
    lecturas para descartar falsas alarmas.
    """
    s = _vecinos_de_odometro(secuencia)
    reinicio = s["odometro"] < REINICIO_ODOMETRO_KM
    return _alertas_de_retroceso(s[(s["km"] < 0) & ~reinicio & ~_es_error_de_tipeo(s)],
                                 "retroceso_con_contexto")


def detectar_salto_con_contexto(secuencia, gps_por_intervalo=None):
    """H2c: salto sobre el ritmo habitual que no es un error de tipeo ni lo confirma el GPS.

    - Error de tipeo: la lectura siguiente vuelve a bajar (el salto fue una sola lectura).
    - GPS: si el dispositivo reportó todos los días del intervalo, el salto debe superar
      en SALTO_HISTORIAL_EXCESO_KM a los km que midió el GPS.

    Recibe la secuencia de odómetro y, opcionalmente, los km del GPS por intervalo
    (de `gps_por_intervalo`). El GPS es una fuente independiente: si confirma que el
    vehículo recorrió esos km, el salto era real y no se alerta.
    """
    s = _vecinos_de_odometro(secuencia)
    exceso = s["km"] - s["km_esperados"]
    candidato = (exceso > SALTO_HISTORIAL_EXCESO_KM) & ~_es_error_de_tipeo(s)
    if gps_por_intervalo is not None:
        gps = s["id"].map(gps_por_intervalo["km_gps"])
        completo = s["id"].map(gps_por_intervalo["completo"]).fillna(False).astype(bool)
        confirmado_por_gps = completo & ((s["km"] - gps) <= SALTO_HISTORIAL_EXCESO_KM)
        candidato &= ~confirmado_por_gps
    salto = s[candidato].assign(exceso=exceso)
    return _alertas(salto, "ODOMETRO_SALTO", "salto_con_contexto",
                    lambda d: d["exceso"].round().astype(int).astype(str)
                    + " km más de lo habitual, sin respaldo del GPS")


def detectar_exceso_sin_antecedente(consumo, flota):
    """H3b: exceso volumétrico en un vehículo que al principio no superaba su tanque.

    Un vehículo que supera el tanque desde sus primeras cargas probablemente tiene más
    capacidad que la registrada (tanque auxiliar); uno que empieza a superarlo después
    cambió de comportamiento.

    "Al principio" = el primer 25% de sus cargas (FRACCION_INICIAL), y al menos una.
    """
    capacidad = flota.set_index("Matricula")["CapacidadTanque"]
    datos = consumo.assign(capacidad=consumo["vehiculo_id"].map(capacidad),
                           fecha=pd.to_datetime(consumo["fecha"]))
    datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    datos["exceso"] = datos["litros"] > datos["capacidad"]
    # cumcount numera las cargas de cada vehículo (0, 1, 2...) en orden de fecha
    posicion = datos.groupby("vehiculo_id").cumcount()
    total = datos.groupby("vehiculo_id")["id"].transform("count")
    iniciales = datos[posicion < (total * FRACCION_INICIAL).clip(lower=1)]
    con_antecedente = set(iniciales.loc[iniciales["exceso"], "vehiculo_id"])
    exceso = datos[datos["exceso"] & ~datos["vehiculo_id"].isin(con_antecedente)]
    return _alertas(exceso, "EXCESO_VOLUMETRICO", "exceso_sin_antecedente",
                    lambda d: d["litros"].round(2).astype(str) + " L con tanque de "
                    + d["capacidad"].round(1).astype(str) + " L; antes no lo superaba")


def detectar_carga_vehiculo_inactivo(consumo, flota):
    """H6: carga con fecha igual o posterior a la baja o salida de servicio del vehículo.

    La cantidad de litros puede ser totalmente normal: lo sospechoso es que el
    vehículo ya no debería estar funcionando. Solo se detecta cruzando la carga con
    el estado de la flota (columnas Estado y FechaEstado).
    """
    inactivos = flota[(flota["Estado"] != "EN SERVICIO") & flota["FechaEstado"].notna()]
    desde = pd.to_datetime(inactivos.set_index("Matricula")["FechaEstado"])
    estado = inactivos.set_index("Matricula")["Estado"]
    datos = consumo.assign(fecha=pd.to_datetime(consumo["fecha"]), desde=consumo["vehiculo_id"].map(desde))
    posteriores = datos[datos["desde"].notna() & (datos["fecha"] >= datos["desde"])]
    return _alertas(posteriores, "CARGA_VEHICULO_INACTIVO", "carga_vehiculo_inactivo",
                    lambda d: "vehículo " + d["vehiculo_id"].map(estado).str.lower()
                    + " desde " + d["desde"].dt.strftime("%Y-%m-%d"))


def cargas_por_dia(consumo, flota, excluir_ids=(), gps_diario=None):
    """Resumen por vehículo y día con carga: litros, cantidad de cargas y rendimiento.

    El rendimiento del día es km recorridos desde el día de carga anterior / litros
    cargados en el día. Se calcula con el odómetro y, si hay GPS completo en el
    intervalo, también con los km del GPS. Cada rendimiento se compara con la mediana
    del propio vehículo.

    El rendimiento (km/L) indica cuántos km se hicieron por cada litro. Si se cargó
    mucho combustible y casi no se recorrió, el rendimiento resulta muy bajo: el
    combustible pudo no ir al vehículo. Un valor "relativo" de 1 significa igual a lo
    habitual; 0,4 significa 40% de lo habitual.

    Recibe: cargas, flota, ids a ignorar (duplicados) y, si hay, el GPS diario.
    Devuelve: una tabla con una fila por vehículo y día con carga. La columna `ids`
    guarda la lista de cargas de ese día. La usan las reglas de fraccionamiento y
    rendimiento, y `modelo.py` para sus variables.
    """
    capacidad = flota.set_index("Matricula")["CapacidadTanque"]
    datos = consumo[~consumo["id"].isin(set(excluir_ids))].copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    dias = (datos.groupby(["vehiculo_id", "fecha"])
            .agg(litros=("litros", "sum"), cargas=("id", "count"), odometro=("odometro", "max"),
                 ids=("id", list))
            .reset_index().sort_values(["vehiculo_id", "fecha"]))
    dias["capacidad"] = dias["vehiculo_id"].map(capacidad)
    grupo = dias.groupby("vehiculo_id")
    dias["dia_anterior"] = grupo["fecha"].shift(1)
    # Última lectura de odómetro conocida antes de este día: ffill rellena los días sin
    # lectura con la última disponible y shift(1) toma la del día anterior
    lectura_valida = grupo["odometro"].transform(lambda x: x.ffill().shift(1))
    dias["km_odometro"] = dias["odometro"] - lectura_valida
    dias["rendimiento_odometro"] = (dias["km_odometro"] / dias["litros"]).where(dias["km_odometro"] >= 0)

    if gps_diario is not None:
        placa = dias["vehiculo_id"].map(flota.set_index("Matricula")["Dominio"])
        km_gps, completo = _km_gps_entre_fechas(placa, dias["dia_anterior"], dias["fecha"], gps_diario)
        dias["km_gps"] = km_gps
        dias["completo"] = completo
        dias["rendimiento_gps"] = (dias["km_gps"] / dias["litros"]).where(dias["completo"])
    else:
        dias["km_gps"] = float("nan")
        dias["completo"] = False
        dias["rendimiento_gps"] = float("nan")

    for columna in ["rendimiento_odometro", "rendimiento_gps"]:
        habitual = dias.groupby("vehiculo_id")[columna].transform("median")
        dias[columna + "_relativo"] = dias[columna] / habitual
    return dias


def _km_gps_entre_fechas(placa, desde, hasta, gps_diario):
    """km del GPS entre `desde` (excluido) y `hasta` (incluido), y si reportó todos esos días.

    Usa sumas acumuladas por placa sobre el calendario completo del GPS.

    Truco de las sumas acumuladas: si se sabe cuántos km llevaba sumados el GPS hasta
    cada fecha, los km entre dos fechas son una simple resta (acumulado al final menos
    acumulado al inicio), sin tener que sumar día por día para cada carga. Lo mismo se
    hace con la cantidad de días con datos, para saber si faltó algún reporte.

    Recibe: la placa de cada fila, las fechas de inicio y fin, y el GPS diario.
    Devuelve: dos series alineadas con `placa`: los km del GPS y si la cobertura fue completa.
    """
    gps = gps_diario.assign(fecha=pd.to_datetime(gps_diario["fecha"]))
    calendario = pd.date_range(gps["fecha"].min() - pd.Timedelta(days=1), gps["fecha"].max())
    indice = pd.MultiIndex.from_product([gps["Placa"].unique(), calendario], names=["Placa", "fecha"])
    diario = gps.set_index(["Placa", "fecha"])["km_gps"].reindex(indice)
    acumulado = pd.DataFrame({
        "km": diario.fillna(0).groupby(level=0).cumsum(),
        "dias": diario.notna().astype(int).groupby(level=0).cumsum(),
    })

    def en(fechas):
        """Valores acumulados (km y días con datos) de cada placa en cada una de `fechas`."""
        claves = pd.MultiIndex.from_arrays([placa, fechas.clip(lower=calendario[0])])
        return acumulado.reindex(claves).to_numpy()

    fin, inicio = en(hasta), en(desde)
    km = fin[:, 0] - inicio[:, 0]
    dias_con_datos = fin[:, 1] - inicio[:, 1]
    completo = (dias_con_datos == (hasta - desde).dt.days.to_numpy()) & ~np.isnan(km)
    return pd.Series(km, index=placa.index), pd.Series(completo, index=placa.index)


def _explotar_dias(dias, tipo, regla, detalle):
    """Convierte días marcados en alertas sobre cada transacción de ese día.

    Algunas reglas evalúan el día completo de un vehículo; pero la evaluación se hace
    por carga, así que cada carga de un día marcado recibe su propia alerta.
    """
    if dias.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    filas = dias.assign(detalle=detalle(dias)).explode("ids")
    return pd.DataFrame({"id_registro": filas["ids"].values, "tipo_anomalia": tipo,
                         "regla": regla, "detalle": filas["detalle"].values})


def detectar_fraccionamiento(dias, con_rendimiento=False):
    """H4: varias cargas el mismo día que entre todas superan el tanque.

    La versión con rendimiento descarta los días en que el recorrido justifica el
    combustible (por ejemplo, un viaje largo con dos cargas en ruta).

    "Fraccionar" es repartir una carga que sería excesiva en varias más chicas, para
    que ninguna supere por sí sola el control por transacción. Recibe la tabla de
    `cargas_por_dia`; devuelve alertas de tipo FRACCIONAMIENTO.
    """
    candidato = (dias["cargas"] >= 2) & (dias["litros"] > FRACCIONAMIENTO_TANQUES * dias["capacidad"])
    regla = "fraccionamiento_diario"
    if con_rendimiento:
        relativo = dias["rendimiento_gps_relativo"].fillna(dias["rendimiento_odometro_relativo"])
        # Se escribe "no (>= mínimo)" en lugar de "< mínimo" para que los días sin
        # rendimiento conocido (NaN) sigan marcados: sin dato no hay justificación
        candidato &= ~(relativo >= RENDIMIENTO_MINIMO_FRACCIONAMIENTO)
        regla = "fraccionamiento_sin_recorrido"
    marcados = dias[candidato]
    return _explotar_dias(marcados, "FRACCIONAMIENTO", regla,
                          lambda d: d["cargas"].astype(str) + " cargas, "
                          + (d["litros"] / d["capacidad"]).round(2).astype(str) + " tanques en el día")


def detectar_rendimiento_bajo(dias, fuente):
    """H5: se cargó mucho combustible para lo poco que se recorrió desde la carga anterior.

    `fuente` = "odometro" (lo que declara la carga) o "gps" (lo que midió el dispositivo;
    cuando no hay GPS completo en el intervalo se usa el odómetro).

    La versión con odómetro es la ingenua: si el odómetro fue adulterado, el
    rendimiento calculado también lo está. El GPS es una medición independiente.
    Solo se evalúan días con una carga relevante (al menos 30% del tanque) para no
    alertar cargas chicas, donde el rendimiento del día es muy variable.
    """
    relativo = dias["rendimiento_odometro_relativo"]
    if fuente == "gps":
        relativo = dias["rendimiento_gps_relativo"].fillna(relativo)
    candidato = ((dias["litros"] >= LITROS_MINIMOS_RENDIMIENTO * dias["capacidad"])
                 & (relativo < RENDIMIENTO_MINIMO))
    marcados = dias[candidato].assign(relativo=relativo[candidato])
    return _explotar_dias(marcados, "RENDIMIENTO_IMPOSIBLE", f"rendimiento_bajo_{fuente}",
                          lambda d: "rendimiento " + d["relativo"].round(2).astype(str)
                          + "× el habitual según " + fuente)


def _xy_km(lat, lon):
    """Proyección plana local (suficiente para distancias de decenas de km).

    Convierte latitud y longitud (grados) a coordenadas x, y en km sobre un plano,
    para poder medir distancias con geometría simple. Un grado de latitud mide unos
    110,57 km; uno de longitud mide menos cuanto más lejos del ecuador, por eso se
    multiplica por el coseno de una latitud de referencia fija de la zona simulada.
    """
    return lon * 111.32 * np.cos(np.radians(-34.65)), lat * 110.57


def _distancia_a_segmento_km(lat, lon, lat1, lon1, lat2, lon2):
    """Distancia en km desde un punto (lat, lon) hasta el segmento que une (lat1, lon1) con (lat2, lon2).

    Se usa para medir qué tan lejos quedó la estación del recorrido del día (el GPS da
    un punto de inicio y uno de fin). Si ambos extremos son el mismo punto, es la
    distancia entre dos puntos. Trabaja con columnas enteras a la vez.
    """
    px, py = _xy_km(lat, lon)
    ax, ay = _xy_km(lat1, lon1)
    bx, by = _xy_km(lat2, lon2)
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    # t indica el punto del segmento más cercano (0 = inicio, 1 = fin); se recorta a
    # [0, 1] para no salirse del segmento. El np.where evita dividir por cero cuando
    # el segmento tiene largo 0.
    t = np.where(largo2 > 0, ((px - ax) * dx + (py - ay) * dy) / np.where(largo2 > 0, largo2, 1), 0)
    t = np.clip(t, 0, 1)
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distancia_a_zona_habitual(consumo, estaciones):
    """Por transacción: km entre la estación y la zona donde suele cargar el vehículo.

    La zona habitual es la mediana de las coordenadas de sus estaciones. NaN si la
    estación falta o no está en el catálogo.
    """
    coords = estaciones.set_index("codigo")[["latitud", "longitud"]]
    datos = consumo.join(coords, on="estacion")
    base = datos.groupby("vehiculo_id")[["latitud", "longitud"]].transform("median")
    # Se pasa el mismo punto como inicio y fin: la distancia a un "segmento" de largo 0
    # es la distancia al punto
    distancia = _distancia_a_segmento_km(datos["latitud"], datos["longitud"], base["latitud"],
                                         base["longitud"], base["latitud"], base["longitud"])
    return pd.Series(distancia, index=consumo.index)


def distancia_al_recorrido_gps(consumo, flota, estaciones, gps_diario):
    """Por transacción: km entre la estación y el recorrido que registró el GPS ese día.

    NaN si el vehículo no tiene GPS, el dispositivo no reportó ese día o falta la estación.
    """
    coords = estaciones.set_index("codigo")[["latitud", "longitud"]]
    gps = gps_diario.assign(fecha=pd.to_datetime(gps_diario["fecha"]))
    datos = consumo.assign(fecha=pd.to_datetime(consumo["fecha"]),
                           Placa=consumo["vehiculo_id"].map(flota.set_index("Matricula")["Dominio"]))
    datos = datos.join(coords, on="estacion").merge(gps, on=["Placa", "fecha"], how="left")
    distancia = _distancia_a_segmento_km(datos["latitud"], datos["longitud"], datos["lat_inicio"],
                                         datos["lon_inicio"], datos["lat_fin"], datos["lon_fin"])
    return pd.Series(np.asarray(distancia), index=consumo.index)


def detectar_carga_lejos_de_base(consumo, estaciones):
    """H7 (ingenua): la estación queda lejos de la zona donde suele cargar el vehículo.

    Genera falsas alarmas con los viajes reales: un vehículo que viajó lejos carga
    lejos de su zona sin que haya nada irregular.
    """
    datos = consumo.assign(distancia=distancia_a_zona_habitual(consumo, estaciones))
    lejos = datos[datos["distancia"] > DISTANCIA_MAXIMA_KM]
    return _alertas(lejos, "CARGA_FUERA_DE_ZONA", "carga_lejos_de_base",
                    lambda d: d["distancia"].round().astype(int).astype(str) + " km de su zona habitual")


def detectar_carga_lejos_del_gps(consumo, flota, estaciones, gps_diario):
    """H7 (con GPS): la estación queda lejos del recorrido que el GPS registró ese día.

    Si el vehículo estaba lejos de la estación cuando se hizo la carga, la tarjeta
    de combustible pudo usarse en otro lado. Un viaje real no se alerta, porque el
    GPS muestra que el vehículo pasó por ahí.
    """
    datos = consumo.assign(distancia=distancia_al_recorrido_gps(consumo, flota, estaciones, gps_diario))
    lejos = datos[datos["distancia"] > DISTANCIA_MAXIMA_KM]
    return _alertas(lejos, "CARGA_FUERA_DE_ZONA", "carga_lejos_del_gps",
                    lambda d: d["distancia"].round().astype(int).astype(str) + " km del recorrido del GPS")


# ============================================================================
# Circuito solicitud -> carga -> factura (escenario realista)
#
# En la flota simulada, antes de cargar se pide una autorización (solicitud) con
# los litros permitidos; después se hace la carga, y cada mes el proveedor emite
# una factura con una línea por carga. Estas reglas verifican que los tres pasos
# coincidan entre sí.
# ============================================================================

COSTO_SIN_SOLICITUD = 20.0     # costo de dejar una carga sin solicitud en el emparejamiento


def emparejar_solicitudes(consumo, solicitudes, excluir_ids=(), dias_antes=VENTANA_SOLICITUD_DIAS,
                          dias_despues=0):
    """Asigna a cada carga, como mucho, una solicitud aprobada del mismo vehículo.

    Las solicitudes no traen el número de carga, así que se emparejan por vehículo con
    una asignación óptima (método húngaro) que minimiza, en conjunto, la distancia en
    días (penalizando levemente las posteriores) y la diferencia entre litros cargados
    y autorizados. Solo se consideran solicitudes entre `dias_antes` días antes y
    `dias_despues` días después de la carga; cada una se usa una vez. Una carga queda
    sin solicitud si emparejarla cuesta más que COSTO_SIN_SOLICITUD.

    Devuelve, por id de carga, el id y los litros autorizados de su solicitud (NaN si no tiene).

    Qué es el método húngaro: es un algoritmo clásico para el "problema de
    asignación": dadas varias cargas y varias solicitudes, y un "costo" de emparejar
    cada carga con cada solicitud, encuentra la combinación que hace mínimo el costo
    total, usando cada solicitud como mucho una vez. Es mejor que emparejar cada carga
    con su solicitud más cercana por separado, porque evita que dos cargas "se
    peleen" por la misma solicitud y una quede mal asignada.
    """
    # linear_sum_assignment es la implementación del método húngaro de la biblioteca scipy
    from scipy.optimize import linear_sum_assignment

    cargas = consumo[~consumo["id"].isin(set(excluir_ids))][["id", "vehiculo_id", "fecha", "litros"]].copy()
    cargas["fecha"] = pd.to_datetime(cargas["fecha"])
    aprobadas = solicitudes[solicitudes["estado"] == "APROBADA"][
        ["id", "vehiculo_id", "fecha_solicitud", "litros_autorizados"]].rename(columns={"id": "solicitud_id"})
    aprobadas["fecha_solicitud"] = pd.to_datetime(aprobadas["fecha_solicitud"])
    por_vehiculo = dict(tuple(aprobadas.groupby("vehiculo_id")))

    filas = []
    # El emparejamiento se hace vehículo por vehículo: una carga solo puede usar
    # solicitudes de su mismo vehículo
    for vehiculo, propias in cargas.groupby("vehiculo_id"):
        candidatas = por_vehiculo.get(vehiculo)
        if candidatas is None:
            continue
        # Matriz de costos: una fila por carga y una columna por solicitud.
        # dias = días de la solicitud respecto de la carga (negativo = antes).
        # El costo suma: los días de diferencia, +0,5 si la solicitud es posterior, y 3
        # veces la diferencia (en escala logarítmica) entre litros autorizados y cargados.
        # Las combinaciones fuera de la ventana permitida reciben costo infinito (prohibidas).
        dias = ((candidatas["fecha_solicitud"].to_numpy()[None, :] - propias["fecha"].to_numpy()[:, None])
                / np.timedelta64(1, "D"))
        proporcion = candidatas["litros_autorizados"].to_numpy()[None, :] / propias["litros"].to_numpy()[:, None]
        costo = np.abs(dias) + 0.5 * (dias > 0) + 3 * np.abs(np.log(np.clip(proporcion, 1e-6, None)))
        costo[(dias < -dias_antes) | (dias > dias_despues)] = np.inf
        # Columnas ficticias: dejar la carga sin solicitud cuesta COSTO_SIN_SOLICITUD
        completo = np.hstack([np.where(np.isfinite(costo), costo, 1e9),
                              np.full((len(propias), len(propias)), COSTO_SIN_SOLICITUD)])
        filas_opt, columnas_opt = linear_sum_assignment(completo)
        # Solo se guardan los pares con una solicitud real (no una columna ficticia)
        # y permitidos por la ventana de días
        for i, j in zip(filas_opt, columnas_opt):
            if j < len(candidatas) and np.isfinite(costo[i, j]):
                solicitud = candidatas.iloc[j]
                filas.append((propias["id"].iloc[i], solicitud["solicitud_id"], solicitud["litros_autorizados"],
                              dias[i, j]))
    resultado = pd.DataFrame(filas, columns=["id", "solicitud_id", "litros_autorizados", "desfase_dias"])
    return cargas[["id"]].merge(resultado, on="id", how="left").set_index("id")


def _tipo_sin_autorizacion(consumo, solicitudes, sin_solicitud, dias_antes, dias_despues):
    """CARGA_CON_SOLICITUD_RECHAZADA si hubo una solicitud rechazada en la ventana; si no, SIN_SOLICITUD.

    Recibe las cargas que quedaron sin solicitud aprobada (`sin_solicitud`, un conjunto
    de ids) y devuelve esas cargas con una columna `tipo` que distingue los dos casos:
    no es lo mismo cargar sin pedir permiso que cargar después de que lo negaron.
    """
    rechazadas = solicitudes[solicitudes["estado"] == "RECHAZADA"][["vehiculo_id", "fecha_solicitud"]].copy()
    rechazadas["fecha_solicitud"] = pd.to_datetime(rechazadas["fecha_solicitud"])
    cargas = consumo[consumo["id"].isin(sin_solicitud)][["id", "vehiculo_id", "fecha"]].copy()
    cargas["fecha"] = pd.to_datetime(cargas["fecha"])
    pares = cargas.merge(rechazadas, on="vehiculo_id")
    desfase = (pares["fecha_solicitud"] - pares["fecha"]).dt.days
    con_rechazo = set(pares.loc[desfase.between(-dias_antes, dias_despues), "id"])
    return cargas.assign(tipo=cargas["id"].isin(con_rechazo).map(
        {True: "CARGA_CON_SOLICITUD_RECHAZADA", False: "CARGA_SIN_SOLICITUD"}))


def detectar_carga_sin_autorizacion(consumo, solicitudes, excluir_ids=(), aceptar_posterior=False):
    """H8: carga sin una solicitud aprobada del vehículo en los días previos.

    La versión con contexto (`aceptar_posterior`) también acepta una solicitud aprobada en
    los días siguientes: una urgencia que se regularizó después.

    Recibe las cargas, las solicitudes y los ids a ignorar (duplicados). Devuelve
    alertas de tipo CARGA_SIN_SOLICITUD o CARGA_CON_SOLICITUD_RECHAZADA.
    """
    despues = VENTANA_SOLICITUD_DIAS if aceptar_posterior else 0
    pares = emparejar_solicitudes(consumo, solicitudes, excluir_ids, dias_despues=despues)
    sin_solicitud = set(pares.index[pares["solicitud_id"].isna()])
    datos = _tipo_sin_autorizacion(consumo, solicitudes, sin_solicitud, VENTANA_SOLICITUD_DIAS, despues)
    regla = "carga_sin_autorizacion" if aceptar_posterior else "carga_sin_solicitud_previa"
    if datos.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    return pd.DataFrame({"id_registro": datos["id"].values, "tipo_anomalia": datos["tipo"].values,
                         "regla": regla, "detalle": np.where(
                             datos["tipo"] == "CARGA_SIN_SOLICITUD", "sin solicitud aprobada",
                             "la solicitud cercana fue rechazada")})


def detectar_supera_autorizado(consumo, solicitudes, excluir_ids=(), tolerancia=0.0):
    """H8: la carga supera los litros autorizados en su solicitud (con una tolerancia opcional).

    Sin tolerancia es la versión ingenua: cualquier exceso, por mínimo que sea, alerta.
    Con tolerancia (por ejemplo 0.05 = 5%) se aceptan las pequeñas diferencias propias
    de la medición del surtidor, que no son irregularidades.
    """
    pares = emparejar_solicitudes(consumo, solicitudes, excluir_ids, dias_despues=VENTANA_SOLICITUD_DIAS)
    datos = consumo.set_index("id").join(pares[["litros_autorizados"]], how="inner").reset_index()
    exceso = datos[datos["litros"] > datos["litros_autorizados"] * (1 + tolerancia)]
    regla = "supera_autorizado_con_tolerancia" if tolerancia else "litros_superan_autorizado"
    return _alertas(exceso, "CARGA_SUPERA_AUTORIZADO", regla,
                    lambda d: d["litros"].round(2).astype(str) + " L con "
                    + d["litros_autorizados"].round(2).astype(str) + " L autorizados")


def detectar_conciliacion_mensual(consumo, estaciones, facturacion, excluir_ids=()):
    """H9 (ingenua): el consumo del mes de cada proveedor no coincide con el total facturado.

    "Conciliar" es comparar dos registros que deberían coincidir (lo que se cargó y lo
    que se facturó). Comparar solo totales mensuales genera falsas alarmas por
    diferencias de fecha de corte o ajustes, y no ve irregularidades chicas que se
    diluyen en el total. El proveedor de cada carga se obtiene de la marca de la estación.
    """
    marca = estaciones.set_index("codigo")["marca"]
    datos = consumo[~consumo["id"].isin(set(excluir_ids))].assign(
        proveedor=lambda d: d["estacion"].map(marca),
        periodo=lambda d: pd.to_datetime(d["fecha"]).dt.to_period("M").astype(str))
    registrado = datos.groupby(["proveedor", "periodo"])["importe_total"].sum()
    facturas = facturacion.set_index(["proveedor", "periodo"])
    comparacion = facturas.join(registrado.rename("registrado"), how="left").fillna({"registrado": 0})
    # Diferencia relativa (proporción, no pesos): clip(lower=1) evita dividir por cero
    # cuando no hubo consumo registrado
    diferencia = (comparacion["total_monto"] - comparacion["registrado"]) / comparacion["registrado"].clip(lower=1)
    marcadas = comparacion[diferencia.abs() > DIFERENCIA_CONCILIACION].reset_index()
    marcadas = marcadas.assign(id=marcadas["numero_factura"], diferencia=diferencia[diferencia.abs()
                                                                                   > DIFERENCIA_CONCILIACION].values)
    return _alertas(marcadas, "TOTAL_INFLADO", "conciliacion_mensual",
                    lambda d: "facturado " + (d["diferencia"] * 100).round(1).astype(str)
                    + "% distinto del consumo registrado del mes")


def detectar_factura_no_concilia(facturacion, facturacion_detalle):
    """H9: el total de la factura no coincide con la suma de sus líneas.

    Un total inflado respecto de su propio detalle indica que se cobró más de lo que
    se detalla. Las alertas se emiten por número de factura.
    """
    lineas = facturacion_detalle.groupby("numero_factura")["importe"].sum()
    datos = facturacion.assign(lineas=facturacion["numero_factura"].map(lineas).fillna(0))
    diferencia = (datos["total_monto"] - datos["lineas"]) / datos["lineas"].abs().clip(lower=1)
    marcadas = datos[diferencia.abs() > DIFERENCIA_ENCABEZADO].assign(
        id=lambda d: d["numero_factura"], diferencia=diferencia[diferencia.abs() > DIFERENCIA_ENCABEZADO])
    return _alertas(marcadas, "TOTAL_INFLADO", "factura_no_concilia",
                    lambda d: "total " + (d["diferencia"] * 100).round(1).astype(str) + "% distinto de sus líneas")


def detectar_irregularidades_de_linea(consumo, facturacion_detalle):
    """H9: líneas de combustible sin carga registrada, duplicadas o con sobreprecio.

    Concilia cada línea de factura con la carga a la que dice corresponder
    (`referencia_consumo`). Tres irregularidades posibles:
    - línea sin consumo: factura una carga que no existe en el registro;
    - línea duplicada: factura dos veces la misma carga;
    - sobreprecio: el precio por litro facturado supera en más de TOLERANCIA_PRECIO
      al que figura en la carga.
    Las alertas se emiten por número de línea.
    """
    lineas = facturacion_detalle[facturacion_detalle["concepto"] == "COMBUSTIBLE"].rename(
        columns={"numero_linea": "id"}).sort_values("id")
    sin_consumo = lineas[~lineas["referencia_consumo"].isin(consumo["id"])]
    duplicadas = lineas[lineas.duplicated("referencia_consumo", keep="first")
                        & lineas["referencia_consumo"].isin(consumo["id"])]
    precio = consumo.set_index("id")["precio_unitario"]
    con_precio = lineas.assign(precio_carga=lineas["referencia_consumo"].map(precio)).dropna(subset=["precio_carga"])
    sobreprecio = con_precio[con_precio["precio_unitario"] > con_precio["precio_carga"] * (1 + TOLERANCIA_PRECIO)]
    return pd.concat([
        _alertas(sin_consumo, "LINEA_SIN_CONSUMO", "linea_sin_consumo",
                 lambda d: d["referencia_consumo"].astype(str) + " no existe en el registro de cargas"),
        _alertas(duplicadas, "LINEA_DUPLICADA", "linea_duplicada",
                 lambda d: d["referencia_consumo"].astype(str) + " ya fue facturada"),
        _alertas(sobreprecio, "SOBREPRECIO", "sobreprecio",
                 lambda d: d["precio_unitario"].astype(str) + " por litro; en la carga, "
                 + d["precio_carga"].astype(str)),
    ], ignore_index=True)


def gps_por_intervalo(dias):
    """Por transacción: km del GPS desde el día de carga anterior y si la cobertura fue completa.

    Recibe la tabla de `cargas_por_dia` (que está por día) y la pasa a una fila por
    carga, que es lo que necesita `detectar_salto_con_contexto`.
    """
    filas = dias.explode("ids")[["ids", "km_gps", "completo"]].rename(columns={"ids": "id"})
    return filas.drop_duplicates("id").set_index("id")


def ejecutar_reglas(flota, consumo, estaciones=None, telemetria_diaria=None, solicitudes=None,
                    facturacion=None, facturacion_detalle=None):
    """Aplica todas las reglas disponibles y devuelve las alertas concatenadas.

    Las reglas con contexto se agregan cuando existen las fuentes que necesitan: fecha
    de estado en la flota, estaciones con coordenadas, GPS diario, solicitudes y el
    detalle de facturación. Las de solicitudes y facturación solo se aplican al
    escenario realista, donde esas fuentes son coherentes con el consumo.

    Es la función que usan `__main__.py`, `modelo.py`, `priorizacion.py` y la
    aplicación. Recibe todas las tablas del dataset (las opcionales pueden ser None) y
    devuelve una sola tabla con todas las alertas de todas las reglas.
    """
    # Los duplicados se detectan primero y se excluyen de las demás reglas, para que
    # una carga repetida no genere alertas falsas de odómetro, fraccionamiento, etc.
    duplicados = detectar_duplicados(consumo)
    secuencia = secuencia_odometro(consumo, excluir_ids=duplicados["id_registro"])
    partes = [
        duplicados,
        detectar_nulos(consumo),
        detectar_dominio_invalido(consumo, flota),
        detectar_exceso_volumetrico(consumo, flota),
        detectar_odometro_regresivo(secuencia),
        detectar_odometro_salto_umbral_fijo(secuencia),
        detectar_odometro_salto_historial(secuencia),
    ]

    # La columna FechaEstado solo existe en el escenario realista: es la señal de que
    # hay contexto disponible para las reglas más elaboradas
    if "FechaEstado" in flota.columns:
        dias = cargas_por_dia(consumo, flota, excluir_ids=duplicados["id_registro"],
                              gps_diario=telemetria_diaria)
        intervalos = gps_por_intervalo(dias) if telemetria_diaria is not None else None
        partes += [
            detectar_retroceso_con_contexto(secuencia),
            detectar_salto_con_contexto(secuencia, intervalos),
            detectar_exceso_sin_antecedente(consumo, flota),
            detectar_carga_vehiculo_inactivo(consumo, flota),
            detectar_fraccionamiento(dias),
            detectar_fraccionamiento(dias, con_rendimiento=True),
            detectar_rendimiento_bajo(dias, "odometro"),
        ]
        if telemetria_diaria is not None:
            partes.append(detectar_rendimiento_bajo(dias, "gps"))
        if estaciones is not None:
            partes.append(detectar_carga_lejos_de_base(consumo, estaciones))
            if telemetria_diaria is not None:
                partes.append(detectar_carga_lejos_del_gps(consumo, flota, estaciones, telemetria_diaria))
        excluir = duplicados["id_registro"]
        if solicitudes is not None:
            partes += [
                detectar_carga_sin_autorizacion(consumo, solicitudes, excluir),
                detectar_carga_sin_autorizacion(consumo, solicitudes, excluir, aceptar_posterior=True),
                detectar_supera_autorizado(consumo, solicitudes, excluir),
                detectar_supera_autorizado(consumo, solicitudes, excluir, tolerancia=TOLERANCIA_AUTORIZADO),
            ]
        if facturacion is not None and facturacion_detalle is not None:
            partes += [
                detectar_factura_no_concilia(facturacion, facturacion_detalle),
                detectar_irregularidades_de_linea(consumo, facturacion_detalle),
            ]
            if estaciones is not None:
                partes.append(detectar_conciliacion_mensual(consumo, estaciones, facturacion, excluir))

    # Se unen todas las tablas de alertas en una sola (omitiendo las vacías)
    return pd.concat([p for p in partes if not p.empty], ignore_index=True)[COLUMNAS_ALERTA]
