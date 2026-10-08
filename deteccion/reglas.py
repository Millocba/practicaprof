"""Línea base de detección por reglas.

Cada regla recibe las fuentes que necesita (flota y consumo siempre; según la hipótesis,
también estaciones, GPS diario, registro interno, facturación, contratos, transferencias,
telemetría o excepciones de odómetro) y devuelve alertas. `ejecutar_reglas` aplica las
que tienen sus fuentes disponibles. Ninguna regla lee el ground truth: la evaluación
contra la verdad de referencia se hace aparte, en `deteccion.evaluacion`.

Una alerta es una fila con:
- id_registro: identificador de la entidad alertada. Su unidad depende de la regla: una
  carga de consumo, un pedido del registro interno (rendida_sin_carga), una factura, una
  línea de factura, un contrato-mes (CTO-N|AAAA-MM) o un dispositivo (Alias)
- tipo_anomalia: tipo que la regla atribuye (mismo vocabulario que el ground truth)
- regla: nombre de la regla que la produjo
- detalle: explicación legible del motivo
"""
import numpy as np
import pandas as pd

COLUMNAS_ALERTA = ["id_registro", "tipo_anomalia", "regla", "detalle"]

# Campos que toda transacción debería traer completos
CAMPOS_OBLIGATORIOS = ["estacion", "conductor", "odometro"]

# Umbrales
SALTO_FIJO_KM = 500            # km entre dos cargas...
SALTO_FIJO_DIAS = 7            # ...en esta cantidad de días o menos
SALTO_HISTORIAL_EXCESO_KM = 1000  # km por encima de lo esperado según el propio vehículo
RETROCESO_LEVE_KM = 1000       # un retroceso menor se clasifica como leve
REINICIO_ODOMETRO_KM = 10000   # una lectura menor tras un retroceso sugiere un odómetro nuevo
DESVIO_TIPEO_KM = 500          # desvío mínimo de una lectura que queda por debajo (hueco, o rebote tras un pico)
                               # para suponer un error de tipeo; un pico no lo necesita: la siguiente vuelve a bajar
FRACCION_INICIAL = 0.25        # primeras cargas del vehículo que definen su comportamiento habitual
FRACCIONAMIENTO_TANQUES = 1.05  # litros del día, en tanques, a partir de los que se sospecha
HORAS_CARGAS_MULTIPLES = 6     # criterio de la fuente (H4): más de una carga del mismo vehículo en menos de 6 h
KM_SIN_AVANCE_FUENTE = 5       # criterio de la fuente (H12): el odómetro avanza menos de 5 km
RENDIMIENTO_MINIMO = 0.4       # km/L del día por debajo de esta fracción de lo habitual
RENDIMIENTO_MINIMO_FRACCIONAMIENTO = 0.75
LITROS_MINIMOS_RENDIMIENTO = 0.3  # solo se evalúan días con al menos esta fracción del tanque
DISTANCIA_MAXIMA_KM = 50       # distancia de la estación a la posición del vehículo
TOLERANCIA_AUTORIZADO = 0.05   # exceso sobre lo autorizado atribuible a la medición del surtidor
DIFERENCIA_CONCILIACION = 0.01  # diferencia relativa entre consumo del mes y total facturado
DIFERENCIA_ENCABEZADO = 0.005   # diferencia relativa entre el total de la factura y sus líneas
TOLERANCIA_PRECIO = 0.02        # diferencia de precio por litro entre la factura y la carga
MARGEN_PRECIO_SURTIDOR = 0.005  # a menos de esto del precio del surtidor, la línea no tiene el descuento de empresa
DIFERENCIA_PDF = 0.001          # diferencia relativa entre el total del PDF y la deuda
MARGEN_PROYECCION = 1.05        # una transferencia se justifica si la proyección supera el saldo con este margen
HOLGURA_TRANSFERENCIA = 0.9     # es injustificada si la proyección con margen no llega a este tanto de lo disponible
DIAS_PESO_HISTORICO = 7         # la proyección combina el mes con 7 días del promedio histórico del contrato
ORIGEN_CONTINGENCIA = "CONTINGENCIA"  # origen de la transacción cargada por la vía alternativa
HORAS_DOBLE_COBRO = 12          # una contingencia es un doble cobro si hay una carga habitual a menos de estas horas...
TOLERANCIA_LITROS_DOBLE_COBRO = 0.02  # ...con una diferencia de litros de hasta este porcentaje


def _alertas(df, tipo, regla, detalle):
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    return pd.DataFrame({
        "id_registro": df["id"].values,
        "tipo_anomalia": tipo,
        "regla": regla,
        "detalle": detalle(df).values if callable(detalle) else detalle,
    })


def detectar_duplicados(consumo):
    """Transacciones idénticas a otra anterior en todos los campos salvo el id."""
    columnas = [c for c in consumo.columns if c != "id"]
    ordenado = consumo.sort_values("id")
    duplicadas = ordenado[ordenado.duplicated(subset=columnas, keep="first")]
    return _alertas(duplicadas, "DUPLICADO", "duplicado_exacto",
                    "idéntica a una transacción anterior")


def detectar_nulos(consumo):
    """Una alerta por cada campo obligatorio vacío."""
    partes = []
    for campo in CAMPOS_OBLIGATORIOS:
        vacios = consumo[consumo[campo].isna()]
        partes.append(_alertas(vacios, "VALOR_NULO", f"nulo_{campo}", f"{campo} vacío"))
    return pd.concat(partes, ignore_index=True)


def normalizar_dominio(serie):
    """Dominio en mayúsculas y sin espacios, guiones ni puntos: `ab-0001 cd` -> `AB0001CD`."""
    return serie.astype("string").str.upper().str.replace(r"[\s\-_.]", "", regex=True)


def leer_fecha(serie):
    """Fechas escritas como AAAA-MM-DD o DD/MM/AAAA, cada formato interpretado por separado.

    Con un solo formato inferido, `05/03/2024` podría leerse como 3 de mayo: se leen las ISO
    con su formato y las demás como día/mes/año.
    """
    texto = serie.astype("string").str.strip()
    iso = pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")
    return iso.fillna(pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce"))


def detectar_dominio_invalido(consumo, flota, normalizado=False):
    """H1: el dominio de la transacción no corresponde a ningún vehículo de la flota.

    Con `normalizado`, se compara después de quitar espacios, guiones y minúsculas (un dominio
    escrito de otra forma sigue siendo el del vehículo) y no se cuentan las tarjetas personales,
    que traen la persona en lugar del dominio.
    """
    if normalizado:
        # Las cargas con tarjeta personal no traen dominio: se identifican por la persona
        personal = consumo.get("tipo_identificacion", pd.Series("PATENTE", index=consumo.index)).eq("DNI")
        vinculado = normalizar_dominio(consumo["dominio"]).isin(set(normalizar_dominio(flota["Dominio"])))
        sin_vinculo = consumo[~vinculado & ~personal]
        return _alertas(sin_vinculo, "DOMINIO_INVALIDO", "dominio_sin_vinculo_normalizado",
                        lambda d: "dominio " + d["dominio"].astype(str) + " no existe en la flota ni normalizado")
    sin_vinculo = consumo[~consumo["dominio"].isin(flota["Dominio"])]
    return _alertas(sin_vinculo, "DOMINIO_INVALIDO", "dominio_sin_vinculo",
                    lambda d: "dominio " + d["dominio"].astype(str) + " no existe en la flota")


def detectar_exceso_volumetrico(consumo, flota):
    """H3a: se cargaron más litros que la capacidad del tanque del vehículo."""
    capacidad = flota.set_index("Matricula")["CapacidadTanque"]
    datos = consumo.assign(capacidad=consumo["vehiculo_id"].map(capacidad))
    exceso = datos[datos["litros"] > datos["capacidad"]]
    return _alertas(exceso, "EXCESO_VOLUMETRICO", "litros_mayor_a_tanque",
                    lambda d: d["litros"].round(2).astype(str) + " L con tanque de "
                    + d["capacidad"].round(2).astype(str) + " L")


def cargas_fuera_del_reporte(solicitudes):
    """Cargas en estaciones de otra red, según el registro interno: pedidos rendidos y no anulados.

    El reporte es de un solo proveedor, pero el registro interno anota las cargas de todas las
    redes con su odómetro y sus litros. Sirven para cerrar los tramos de cada vehículo: sin ellas,
    los km entre dos cargas del reporte incluyen lo recorrido con combustible de otra red.
    """
    if solicitudes is None or "estacion_servicio" not in solicitudes.columns:
        return None
    fuera = solicitudes[(solicitudes["estacion_servicio"] == ESTACION_AJENA)
                        & (solicitudes["rendido"].astype(str).str.upper() == "SI")
                        & (solicitudes["anulado"].astype(str).str.upper() != "SI")
                        & solicitudes["vehiculo_id"].notna()]
    litros = pd.to_numeric(fuera["litros_cargados"], errors="coerce").fillna(
        pd.to_numeric(fuera["litros_autorizados"], errors="coerce"))
    return pd.DataFrame({
        "id": "FUERA-" + fuera["id"].astype(str), "vehiculo_id": fuera["vehiculo_id"],
        "fecha": leer_fecha(fuera["fecha"]).dt.normalize(), "hora": fuera["hora"].astype("string").fillna("00:00:00"),
        "odometro": pd.to_numeric(fuera["odometro"], errors="coerce"), "litros": litros,
    }).dropna(subset=["fecha", "litros"])


def _con_cargas_fuera(consumo, fuera):
    """El consumo con las cargas de otra red intercaladas, marcadas en la columna `fuera`."""
    datos = consumo.assign(fuera=False)
    if fuera is None or fuera.empty:
        return datos
    return pd.concat([datos, fuera.assign(fuera=True)], ignore_index=True)


def secuencia_odometro(consumo, excluir_ids=(), fuera=None, sin_repetidas=False):
    """Cambio de odómetro de cada transacción respecto de la lectura válida anterior.

    Se descartan las lecturas vacías y las transacciones en `excluir_ids` (por ejemplo,
    duplicados ya detectados), para comparar cada carga con la anterior real.
    Agrega: km (cambio), dias (días transcurridos) y km_esperados (según la mediana
    de km por día del propio vehículo).

    Con `fuera` (ver `cargas_fuera_del_reporte`) se intercalan las cargas de otra red, ordenadas
    por fecha y hora: cierran los tramos y quedan en la secuencia con `fuera=True`, para que las
    reglas las usen como vecinas pero no las marquen.

    Con `sin_repetidas`, una lectura igual a la anterior no cuenta como lectura (odómetro exceptuado o
    sin avance, H12): la carga siguiente se compara con la última lectura que avanzó.
    """
    datos = consumo[consumo["odometro"].notna() & ~consumo["id"].isin(set(excluir_ids))].copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    if fuera is None:
        datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    else:
        datos = _con_cargas_fuera(datos, fuera[fuera["odometro"].notna()])
        horas = datos["hora"].astype("string").fillna("00:00:00") if "hora" in datos.columns else "00:00:00"
        datos["_instante"] = datos["fecha"] + pd.to_timedelta(horas)
        datos = datos.sort_values(["vehiculo_id", "_instante", "id"]).drop(columns="_instante")
    if sin_repetidas:
        repetida = datos["odometro"].eq(datos.groupby("vehiculo_id")["odometro"].shift(1))
        datos = datos[~repetida]
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
    if regresion.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    return pd.DataFrame({
        "id_registro": regresion["id"].values,
        "tipo_anomalia": _tipo_de_retroceso(regresion["km"]).values,
        "regla": regla,
        "detalle": ("retrocede " + (-regresion["km"]).astype(int).astype(str) + " km").values,
    })


def detectar_odometro_regresivo(secuencia):
    """H2: el odómetro marca menos que en la carga anterior."""
    return _alertas_de_retroceso(secuencia[secuencia["km"] < 0], "odometro_disminuye")


def detectar_odometro_salto_umbral_fijo(secuencia):
    """H2 (umbral general): más de SALTO_FIJO_KM en SALTO_FIJO_DIAS días o menos."""
    salto = secuencia[(secuencia["km"] > SALTO_FIJO_KM) & (secuencia["dias"] <= SALTO_FIJO_DIAS)]
    return _alertas(salto, "ODOMETRO_SALTO", "salto_umbral_fijo",
                    lambda d: d["km"].astype(int).astype(str) + " km en "
                    + d["dias"].astype(int).astype(str) + " días")


def detectar_odometro_salto_historial(secuencia):
    """H2 (historial individual): recorrió SALTO_HISTORIAL_EXCESO_KM más de lo que
    ese vehículo suele recorrer en la misma cantidad de días."""
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
    """Agrega, por vehículo, las dos lecturas válidas anteriores y la siguiente."""
    s = secuencia.copy()
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
    """
    desvio = (s["anterior"] - s["odometro"]).abs() > DESVIO_TIPEO_KM
    hueco = (s["km"] < 0) & (s["siguiente"] >= s["anterior"]) & desvio
    rebote_tras_pico = (s["km"] < 0) & (s["anterior2"] <= s["odometro"]) & desvio
    pico = (s["km"] > 0) & (s["siguiente"] < s["odometro"])
    rebote_tras_hueco = (s["km"] > 0) & (s["anterior"] < s["anterior2"])
    return hueco | rebote_tras_pico | pico | rebote_tras_hueco


def cargas_exceptuadas(consumo, flota, excepciones=None):
    """Ids de las cargas hechas con una excepción de odómetro vigente ese día.

    Con el historial de excepciones (desde y hasta, por dominio) se mira la fecha de cada carga;
    una excepción puede durar un solo día. Sin historial, el padrón da el estado de hoy:
    ExcepcionOdometro = SI y la carga no es posterior a FechaHastaExcepcionOdometro.
    """
    fecha = pd.to_datetime(consumo["fecha"]).dt.normalize()
    if excepciones is not None and len(excepciones):
        matricula_de = dict(zip(normalizar_dominio(flota["Dominio"]), flota["Matricula"]))
        tramos = pd.DataFrame({"vehiculo_id": normalizar_dominio(excepciones["patente"]).map(matricula_de),
                               "desde": leer_fecha(excepciones["fecha_creacion"]).dt.normalize(),
                               "hasta": leer_fecha(excepciones["fecha_hasta"]).dt.normalize()}).dropna()
        cruce = consumo[["id", "vehiculo_id"]].assign(fecha=fecha).merge(tramos, on="vehiculo_id")
        return set(cruce.loc[cruce["fecha"].between(cruce["desde"], cruce["hasta"]), "id"])
    if "ExcepcionOdometro" in flota.columns:
        si = flota["ExcepcionOdometro"].astype(str).str.strip().str.upper().eq("SI")
        hasta = leer_fecha(flota["FechaHastaExcepcionOdometro"].astype("string")).where(si)
        limite = pd.Series(hasta.to_numpy(), index=flota["Matricula"]).reindex(consumo["vehiculo_id"]).to_numpy()
        return set(consumo.loc[pd.notna(limite) & (fecha.to_numpy() <= limite), "id"])
    return set()


def detectar_odometro_sin_avance(secuencia):
    """H12 (ingenua): la lectura del odómetro es igual a la de la carga anterior."""
    s = secuencia[(secuencia["km"] == 0) & ~_es_de_otra_red(secuencia)]
    return _alertas(s, "ODOMETRO_SIN_AVANCE", "odometro_sin_avance", "el odómetro no avanzó desde la carga anterior")


def detectar_avance_menor_fuente(secuencia, exceptuadas_hoy):
    """H12 (criterio de la fuente): el odómetro avanza menos de KM_SIN_AVANCE_FUENTE desde la carga
    anterior, aunque sea del mismo día, salvo que el vehículo tenga hoy una excepción vigente.

    Los retrocesos (avance negativo) quedan fuera: los ve H2b. La fuente mira la excepción con la
    vigencia de hoy (`exceptuadas_hoy`, del padrón), no con la del día de cada carga.
    """
    s = secuencia[secuencia["km"].between(0, KM_SIN_AVANCE_FUENTE, inclusive="left")
                  & ~secuencia["id"].isin(set(exceptuadas_hoy)) & ~_es_de_otra_red(secuencia)]
    return _alertas(s, "ODOMETRO_SIN_AVANCE", "avance_menor_a_5_km",
                    lambda d: "avanzó " + d["km"].astype(int).astype(str) + " km desde la carga anterior")


def detectar_sin_avance_sin_excepcion(secuencia, exceptuadas):
    """H12: el odómetro no avanza y el vehículo no está exceptuado ese día.

    Si la carga anterior es del mismo día, no se vuelve a leer el tablero: no es una alerta.
    """
    s = secuencia[(secuencia["km"] == 0) & (secuencia["dias"] > 0) & ~secuencia["id"].isin(set(exceptuadas))
                  & ~_es_de_otra_red(secuencia)]
    return _alertas(s, "ODOMETRO_SIN_AVANCE", "sin_avance_sin_excepcion",
                    "el odómetro no avanzó desde la carga anterior y no hay excepción vigente")


def detectar_contingencia(consumo):
    """H13 (ingenua): toda transacción cuyo origen es una contingencia."""
    if "origen_transaccion" not in consumo.columns:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    contingencias = consumo[consumo["origen_transaccion"].astype("string").str.upper() == ORIGEN_CONTINGENCIA]
    return _alertas(contingencias, "DOBLE_COBRO", "contingencia", "transacción de contingencia")


def detectar_doble_cobro(consumo):
    """H13: una contingencia con una carga del mismo vehículo por el medio habitual cercana y con los mismos litros.

    La misma carga cobrada por las dos vías: a menos de HORAS_DOBLE_COBRO horas y con hasta
    TOLERANCIA_LITROS_DOBLE_COBRO de diferencia de litros (respecto de la carga habitual).
    """
    if not {"origen_transaccion", "hora"} <= set(consumo.columns):
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    c = consumo.assign(instante=_instantes(consumo["fecha"], consumo["hora"]),
                       contingencia=consumo["origen_transaccion"].astype("string").str.upper() == ORIGEN_CONTINGENCIA)
    c = c.dropna(subset=["vehiculo_id", "instante", "litros"])
    habituales = c.loc[~c["contingencia"], ["vehiculo_id", "instante", "litros"]]
    pares = c.loc[c["contingencia"], ["id", "vehiculo_id", "instante", "litros"]].merge(
        habituales, on="vehiculo_id", suffixes=("", "_habitual"))
    horas = (pares["instante"] - pares["instante_habitual"]).abs() / pd.Timedelta(hours=1)
    diferencia = (pares["litros"] - pares["litros_habitual"]).abs().round(6)
    cerca = diferencia <= (TOLERANCIA_LITROS_DOBLE_COBRO * pares["litros_habitual"]).round(6)
    dobles = pares[(horas < HORAS_DOBLE_COBRO) & cerca].drop_duplicates("id")
    return _alertas(dobles, "DOBLE_COBRO", "doble_cobro",
                    "contingencia con una carga del mismo vehículo por el medio habitual cercana y con los mismos litros")


def _exceptuadas_y_siguientes(s, exceptuadas):
    """Cargas con excepción de odómetro y la primera después de cada una (la lectura vuelve al valor real)."""
    excepto = s["id"].isin(set(exceptuadas))
    siguiente = excepto.groupby(s["vehiculo_id"]).shift(1).eq(True)
    return excepto, excepto | siguiente


def _es_de_otra_red(s):
    return s["fuera"].fillna(False).astype(bool) if "fuera" in s.columns else pd.Series(False, index=s.index)


def detectar_retroceso_con_contexto(secuencia, exceptuadas=()):
    """H2b: retroceso que no se explica por un odómetro nuevo ni por un error de tipeo.

    - Odómetro nuevo: la lectura queda por debajo de REINICIO_ODOMETRO_KM.
    - Error de tipeo: ver `_es_error_de_tipeo`.
    """
    s = _vecinos_de_odometro(secuencia)
    reinicio = s["odometro"] < REINICIO_ODOMETRO_KM
    exceptuada, _ = _exceptuadas_y_siguientes(s, exceptuadas)
    return _alertas_de_retroceso(s[(s["km"] < 0) & ~reinicio & ~_es_error_de_tipeo(s) & ~_es_de_otra_red(s)
                                   & ~exceptuada],
                                 "retroceso_con_contexto")


def detectar_salto_con_contexto(secuencia, gps_por_intervalo=None, exceptuadas=()):
    """H2c: salto sobre el ritmo habitual que no es un error de tipeo ni lo confirma el GPS.

    - Error de tipeo: la lectura siguiente vuelve a bajar (el salto fue una sola lectura).
    - GPS: si el dispositivo reportó todos los días del intervalo, el salto debe superar
      en SALTO_HISTORIAL_EXCESO_KM a los km que midió el GPS.
    """
    s = _vecinos_de_odometro(secuencia)
    exceso = s["km"] - s["km_esperados"]
    _, con_excepcion = _exceptuadas_y_siguientes(s, exceptuadas)
    candidato = (exceso > SALTO_HISTORIAL_EXCESO_KM) & ~_es_error_de_tipeo(s) & ~_es_de_otra_red(s) & ~con_excepcion
    if gps_por_intervalo is not None:
        gps = s["id"].map(gps_por_intervalo["km_gps"])
        completo = s["id"].map(gps_por_intervalo["completo"]).eq(True)
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
    """
    capacidad = flota.set_index("Matricula")["CapacidadTanque"]
    datos = consumo.assign(capacidad=consumo["vehiculo_id"].map(capacidad),
                           fecha=pd.to_datetime(consumo["fecha"]))
    datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    datos["exceso"] = datos["litros"] > datos["capacidad"]
    posicion = datos.groupby("vehiculo_id").cumcount()
    total = datos.groupby("vehiculo_id")["id"].transform("count")
    iniciales = datos[posicion < (total * FRACCION_INICIAL).clip(lower=1)]
    con_antecedente = set(iniciales.loc[iniciales["exceso"], "vehiculo_id"])
    exceso = datos[datos["exceso"] & ~datos["vehiculo_id"].isin(con_antecedente)]
    return _alertas(exceso, "EXCESO_VOLUMETRICO", "exceso_sin_antecedente",
                    lambda d: d["litros"].round(2).astype(str) + " L con tanque de "
                    + d["capacidad"].round(1).astype(str) + " L; antes no lo superaba")


def detectar_carga_vehiculo_inactivo(consumo, flota):
    """H6: carga con fecha igual o posterior a la baja o salida de servicio del vehículo."""
    inactivos = flota[(flota["Estado"] != "EN SERVICIO") & flota["FechaEstado"].notna()]
    desde = pd.to_datetime(inactivos.set_index("Matricula")["FechaEstado"])
    estado = inactivos.set_index("Matricula")["Estado"]
    # reindex y no map: con pandas 3, map falla si no hay ningún vehículo inactivo con fecha
    datos = consumo.assign(fecha=pd.to_datetime(consumo["fecha"]),
                           desde=desde.reindex(consumo["vehiculo_id"]).to_numpy())
    posteriores = datos[datos["desde"].notna() & (datos["fecha"] >= datos["desde"])]
    return _alertas(posteriores, "CARGA_VEHICULO_INACTIVO", "carga_vehiculo_inactivo",
                    lambda d: "vehículo " + d["vehiculo_id"].map(estado).str.lower()
                    + " desde " + d["desde"].dt.strftime("%Y-%m-%d"))


def cargas_por_dia(consumo, flota, excluir_ids=(), gps_diario=None, fuera=None):
    """Resumen por vehículo y día con carga: litros, cantidad de cargas y rendimiento.

    El rendimiento del día es km recorridos desde el día de carga anterior / litros
    cargados en el día. Se calcula con el odómetro y, si hay GPS completo en el
    intervalo, también con los km del GPS. Cada rendimiento se compara con la mediana
    del propio vehículo.

    Con `fuera` (ver `cargas_fuera_del_reporte`) se suman las cargas de otra red: sus litros
    cuentan en el día y sus lecturas cierran los tramos, pero `ids` lista solo las del reporte y
    los días sin cargas del reporte no se devuelven.
    """
    capacidad = flota.set_index("Matricula")["CapacidadTanque"]
    datos = consumo[~consumo["id"].isin(set(excluir_ids))].copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    datos = _con_cargas_fuera(datos, fuera)
    datos["id_del_reporte"] = datos["id"].where(~datos["fuera"].astype(bool))
    dias = (datos.groupby(["vehiculo_id", "fecha"])
            .agg(litros=("litros", "sum"), cargas=("id", "count"), odometro=("odometro", "max"),
                 ids=("id_del_reporte", lambda x: list(x.dropna())))
            .reset_index().sort_values(["vehiculo_id", "fecha"]))
    dias["capacidad"] = dias["vehiculo_id"].map(capacidad)
    grupo = dias.groupby("vehiculo_id")
    dias["dia_anterior"] = grupo["fecha"].shift(1)
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
    return dias[dias["ids"].str.len() > 0].reset_index(drop=True)


def _km_gps_entre_fechas(placa, desde, hasta, gps_diario):
    """km del GPS entre `desde` (excluido) y `hasta` (incluido), y si reportó todos esos días.

    Usa sumas acumuladas por placa sobre el calendario completo del GPS.
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
        claves = pd.MultiIndex.from_arrays([placa, fechas.clip(lower=calendario[0])])
        return acumulado.reindex(claves).to_numpy()

    fin, inicio = en(hasta), en(desde)
    km = fin[:, 0] - inicio[:, 0]
    dias_con_datos = fin[:, 1] - inicio[:, 1]
    completo = (dias_con_datos == (hasta - desde).dt.days.to_numpy()) & ~np.isnan(km)
    return pd.Series(km, index=placa.index), pd.Series(completo, index=placa.index)


def _explotar_dias(dias, tipo, regla, detalle):
    """Convierte días marcados en alertas sobre cada transacción de ese día."""
    if dias.empty:
        return pd.DataFrame(columns=COLUMNAS_ALERTA)
    filas = dias.assign(detalle=detalle(dias)).explode("ids")
    return pd.DataFrame({"id_registro": filas["ids"].values, "tipo_anomalia": tipo,
                         "regla": regla, "detalle": filas["detalle"].values})


def detectar_fraccionamiento(dias, con_rendimiento=False):
    """H4: varias cargas el mismo día que entre todas superan el tanque.

    La versión con rendimiento descarta los días en que el recorrido justifica el
    combustible (por ejemplo, un viaje largo con dos cargas en ruta).
    """
    candidato = (dias["cargas"] >= 2) & (dias["litros"] > FRACCIONAMIENTO_TANQUES * dias["capacidad"])
    regla = "fraccionamiento_diario"
    if con_rendimiento:
        relativo = dias["rendimiento_gps_relativo"].fillna(dias["rendimiento_odometro_relativo"])
        candidato &= ~(relativo >= RENDIMIENTO_MINIMO_FRACCIONAMIENTO)
        regla = "fraccionamiento_sin_recorrido"
    marcados = dias[candidato]
    return _explotar_dias(marcados, "FRACCIONAMIENTO", regla,
                          lambda d: d["cargas"].astype(str) + " cargas, "
                          + (d["litros"] / d["capacidad"]).round(2).astype(str) + " tanques en el día")


def detectar_cargas_multiples(consumo, excluir_ids=()):
    """H4 (criterio de la fuente): más de una carga del mismo vehículo en menos de HORAS_CARGAS_MULTIPLES.

    Marca cada carga que tiene otra del mismo vehículo a menos de ese tiempo, antes o después,
    sin mirar los litros ni el recorrido. Solo usa el reporte, como la fuente. Una carga sin hora
    se toma a las 00:00 de su día.
    """
    datos = consumo[~consumo["id"].isin(set(excluir_ids))]
    instante = pd.to_datetime(datos["fecha"]) + pd.to_timedelta(datos["hora"].astype("string").fillna("00:00:00"))
    datos = datos.assign(_instante=instante).sort_values(["vehiculo_id", "_instante"])
    grupo = datos.groupby("vehiculo_id")["_instante"]
    limite = pd.Timedelta(hours=HORAS_CARGAS_MULTIPLES)
    cerca = ((datos["_instante"] - grupo.shift(1)) < limite) | ((grupo.shift(-1) - datos["_instante"]) < limite)
    return _alertas(datos[cerca], "FRACCIONAMIENTO", "cargas_menos_de_6_horas",
                    f"otra carga del mismo vehículo a menos de {HORAS_CARGAS_MULTIPLES} horas")


def detectar_rendimiento_bajo(dias, fuente, sin_odometro=()):
    """H5: se cargó mucho combustible para lo poco que se recorrió desde la carga anterior.

    `fuente` = "odometro" (lo que declara la carga) o "gps" (lo que midió el dispositivo;
    cuando no hay GPS completo en el intervalo se usa el odómetro).
    """
    relativo = dias["rendimiento_odometro_relativo"]
    if fuente == "gps":
        relativo = dias["rendimiento_gps_relativo"].fillna(relativo)
    candidato = ((dias["litros"] >= LITROS_MINIMOS_RENDIMIENTO * dias["capacidad"])
                 & (relativo < RENDIMIENTO_MINIMO))
    if sin_odometro:
        # Con el odómetro exceptuado o sin avance (H12), los km del día no son un dato: lo ve H12
        sin_dato = set(sin_odometro)
        candidato &= ~dias["ids"].apply(lambda ids: bool(sin_dato.intersection(ids)))
    marcados = dias[candidato].assign(relativo=relativo[candidato])
    return _explotar_dias(marcados, "RENDIMIENTO_IMPOSIBLE", f"rendimiento_bajo_{fuente}",
                          lambda d: "rendimiento " + d["relativo"].round(2).astype(str)
                          + "× el habitual según " + fuente)


def _xy_km(lat, lon):
    """Proyección plana local (suficiente para distancias de decenas de km)."""
    return lon * 111.32 * np.cos(np.radians(-34.65)), lat * 110.57


def _distancia_a_segmento_km(lat, lon, lat1, lon1, lat2, lon2):
    px, py = _xy_km(lat, lon)
    ax, ay = _xy_km(lat1, lon1)
    bx, by = _xy_km(lat2, lon2)
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
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
    """H7 (ingenua): la estación queda lejos de la zona donde suele cargar el vehículo."""
    datos = consumo.assign(distancia=distancia_a_zona_habitual(consumo, estaciones))
    lejos = datos[datos["distancia"] > DISTANCIA_MAXIMA_KM]
    return _alertas(lejos, "CARGA_FUERA_DE_ZONA", "carga_lejos_de_base",
                    lambda d: d["distancia"].round().astype(int).astype(str) + " km de su zona habitual")


def detectar_carga_lejos_del_gps(consumo, flota, estaciones, gps_diario):
    """H7 (con GPS): la estación queda lejos del recorrido que el GPS registró ese día."""
    datos = consumo.assign(distancia=distancia_al_recorrido_gps(consumo, flota, estaciones, gps_diario))
    lejos = datos[datos["distancia"] > DISTANCIA_MAXIMA_KM]
    return _alertas(lejos, "CARGA_FUERA_DE_ZONA", "carga_lejos_del_gps",
                    lambda d: d["distancia"].round().astype(int).astype(str) + " km del recorrido del GPS")


# ============================================================================
# Circuito registro interno -> carga -> factura (escenario realista)
# ============================================================================


ESTACION_AJENA = "ESTACION AJENA"
MINUTOS_ANTES_REGISTRO = 180    # el pedido puede hacerse hasta 3 horas antes de la carga...
MINUTOS_DESPUES_REGISTRO = 30   # ...o, por demoras en el registro, hasta media hora después
TOLERANCIA_REGISTRO_LITROS = 0.5  # diferencia de litros entre el registro y la carga que no es desacuerdo


def _instantes(fechas, horas):
    return leer_fecha(fechas) + pd.to_timedelta(horas.astype("string").fillna("00:00:00"))


def cruzar_registro(consumo, registro, excluir_ids=(), voraz=False, flota=None):
    """Cruza cada carga del reporte con, como mucho, un pedido del registro interno.

    No comparten identificador. `voraz` reproduce el cruce de un sistema operativo: por dominio y
    día, cada pedido rendido toma la carga más cercana en horario, sin tolerancias; las tarjetas
    personales (sin dominio en el reporte) no cruzan. La versión con contexto usa también los
    anulados y los pendientes, cruza las tarjetas personales por persona, exige que el pedido
    esté entre 3 horas antes y media hora después de la carga y resuelve con una asignación
    óptima (método húngaro) que prefiere pedidos no anulados y con los mismos litros. Si se pasa
    `flota`, toma el dominio del vehículo dueño de la tarjeta: la tarjeta lo identifica aunque el
    dominio del reporte venga mal.

    Devuelve las cargas con su pedido (NaN si no tiene) y el conjunto de pedidos sin carga.
    Los pedidos en estaciones de otra red no se cruzan: no están en el reporte.
    """
    from scipy.optimize import linear_sum_assignment

    cargas = consumo[~consumo["id"].isin(set(excluir_ids))].copy()
    cargas["instante"] = pd.to_datetime(cargas["fecha"]) + pd.to_timedelta(cargas["hora"].astype(str))
    personal_c = cargas.get("tipo_identificacion", pd.Series("PATENTE", index=cargas.index)).eq("DNI")
    pedidos = registro[registro["estacion_servicio"] != ESTACION_AJENA].copy()
    pedidos["instante"] = _instantes(pedidos["fecha"], pedidos["hora"])
    if voraz:
        pedidos = pedidos[(pedidos["rendido"] == "SI") & (pedidos["anulado"] != "SI")]
        cargas["clave"] = normalizar_dominio(cargas["dominio"]).where(~personal_c)
        pedidos["clave"] = normalizar_dominio(pedidos["dominio"])
    else:
        personal_p = pedidos["tarjeta_personal"].astype(str).str.upper().eq("TRUE")
        dominio = cargas["dominio"]
        if flota is not None:
            # Una tarjeta puede figurar en más de un vehículo del padrón: se toma el primero
            dominio_de = flota.dropna(subset=["NumeroTarjeta"]).drop_duplicates("NumeroTarjeta").set_index(
                "NumeroTarjeta")["Dominio"]
            dominio = cargas["numero_tarjeta"].map(dominio_de).fillna(dominio)
        cargas["clave"] = np.where(personal_c, "P:" + cargas["conductor"].astype(str),
                                   "D:" + normalizar_dominio(dominio).astype(str))
        pedidos["clave"] = np.where(personal_p, "P:" + pedidos["solicitante"].astype(str),
                                    "D:" + normalizar_dominio(pedidos["dominio"]).astype(str))

    pares = []
    if voraz:
        cargas["dia"] = cargas["instante"].dt.normalize()
        pedidos["dia"] = pedidos["instante"].dt.normalize()
        disponibles = {k: list(g.index) for k, g in cargas.dropna(subset=["clave"]).groupby(["clave", "dia"])}
        for j, pedido in pedidos.iterrows():
            candidatas = disponibles.get((pedido["clave"], pedido["dia"]), [])
            if candidatas:
                i = min(candidatas, key=lambda k: abs(cargas.at[k, "instante"] - pedido["instante"]))
                candidatas.remove(i)
                pares.append((i, j))
    else:
        por_clave = dict(tuple(pedidos.groupby("clave")))
        for clave, propias in cargas.groupby("clave"):
            candidatos = por_clave.get(clave)
            if candidatos is None:
                continue
            minutos = ((propias["instante"].to_numpy()[:, None] - candidatos["instante"].to_numpy()[None, :])
                       / np.timedelta64(1, "m"))
            litros = np.abs(propias["litros"].to_numpy()[:, None] - candidatos["litros_cargados"].to_numpy()[None, :])
            costo = (np.abs(minutos - 45) / 60 + 2 * litros / np.maximum(propias["litros"].to_numpy()[:, None], 1)
                     + 2 * (candidatos["anulado"].to_numpy()[None, :] == "SI"))
            costo[(minutos > MINUTOS_ANTES_REGISTRO) | (minutos < -MINUTOS_DESPUES_REGISTRO)] = np.inf
            completo = np.hstack([np.where(np.isfinite(costo), costo, 1e9), np.full((len(propias), len(propias)), 5.0)])
            filas, columnas = linear_sum_assignment(completo)
            pares += [(propias.index[i], candidatos.index[j]) for i, j in zip(filas, columnas)
                      if j < len(candidatos) and np.isfinite(costo[i, j])]

    unidos = pd.DataFrame(pares, columns=["carga", "pedido"])
    resultado = cargas[["id", "litros"]].assign(registro_id=pd.Series(None, index=cargas.index, dtype=object),
                                                anulado=None, rendido=None, litros_registro=np.nan,
                                                litros_autorizados=np.nan)
    if not unidos.empty:
        elegidos = pedidos.loc[unidos["pedido"]]
        resultado.loc[unidos["carga"], "registro_id"] = elegidos["id"].values
        resultado.loc[unidos["carga"], "anulado"] = elegidos["anulado"].values
        resultado.loc[unidos["carga"], "rendido"] = elegidos["rendido"].values
        resultado.loc[unidos["carga"], "litros_registro"] = elegidos["litros_cargados"].values
        resultado.loc[unidos["carga"], "litros_autorizados"] = elegidos["litros_autorizados"].values
    rendidos = pedidos[(pedidos["rendido"] == "SI") & (pedidos["anulado"] != "SI")]
    sin_carga = rendidos[~rendidos.index.isin(unidos["pedido"])]
    return resultado.set_index("id"), sin_carga


def detectar_cruce_ingenuo(consumo, registro, excluir_ids=()):
    """H8 (ingenua): el cruce diario por dominio de un sistema operativo, voraz y sin tolerancias."""
    pares, sin_carga = cruzar_registro(consumo, registro, excluir_ids, voraz=True)
    sin_registro = pares[pares["registro_id"].isna()].reset_index()
    return pd.concat([
        _alertas(sin_registro, "CARGA_SIN_REGISTRO", "cruce_por_dominio_y_dia",
                 "sin pedido rendido del dominio en el día"),
        _alertas(sin_carga, "RENDIDA_SIN_CARGA", "cruce_por_dominio_y_dia", "pedido rendido sin carga del dominio"),
    ], ignore_index=True)


def detectar_cruce_con_contexto(consumo, registro, excluir_ids=(), flota=None, tolerancia=TOLERANCIA_AUTORIZADO):
    """H8: cruce por dominio (el del vehículo de la tarjeta) o persona y horario, con asignación óptima y tolerancias."""
    pares, sin_carga = cruzar_registro(consumo, registro, excluir_ids, flota=flota)
    pares = pares.reset_index()
    unidas = pares[pares["registro_id"].notna()]
    desacuerdo = unidas[(unidas["litros_registro"] - unidas["litros"]).abs() > TOLERANCIA_REGISTRO_LITROS]
    exceso = unidas[unidas["litros"] > unidas["litros_autorizados"] * (1 + tolerancia)]
    return pd.concat([
        _alertas(pares[pares["registro_id"].isna()], "CARGA_SIN_REGISTRO", "carga_sin_registro",
                 "sin pedido del dominio o de la persona en las 3 horas previas"),
        _alertas(unidas[unidas["anulado"] == "SI"], "ANULADA_CON_CARGA", "carga_de_registro_anulado",
                 lambda d: "su pedido " + d["registro_id"].astype(str) + " está anulado"),
        _alertas(desacuerdo, "DESACUERDO_DE_LITROS", "desacuerdo_de_litros",
                 lambda d: "el registro declara " + d["litros_registro"].round(2).astype(str) + " L y se cargaron "
                 + d["litros"].round(2).astype(str) + " L"),
        _alertas(exceso, "CARGA_SUPERA_AUTORIZADO", "supera_autorizado_con_tolerancia",
                 lambda d: d["litros"].round(2).astype(str) + " L con " + d["litros_autorizados"].round(2).astype(str)
                 + " L autorizados"),
        _alertas(sin_carga, "RENDIDA_SIN_CARGA", "rendida_sin_carga", "pedido rendido sin carga en las 3 horas siguientes"),
    ], ignore_index=True)


# ============================================================================
# Causa probable de las alertas (#24)
#
# La mayoría de las alertas del registro son errores de carga que después se corrigen. La alerta
# se mantiene; la causa probable acompaña la citación de quien hizo el pedido.
# ============================================================================

SIN_EXPLICACION = "sin_explicacion"
REGLAS_CON_CAUSA = [
    "cruce_por_dominio_y_dia", "carga_sin_registro", "carga_de_registro_anulado", "rendida_sin_carga",   # H8
    "desacuerdo_de_litros", "supera_autorizado_con_tolerancia",
    "odometro_disminuye", "retroceso_con_contexto", "salto_umbral_fijo", "salto_historial_vehiculo",    # H2
    "salto_con_contexto",
    "rendimiento_bajo_odometro", "rendimiento_bajo_gps",                                                # H5
    "odometro_sin_avance", "sin_avance_sin_excepcion",                                                  # H12
    # H4: el pedido registrado como de otra red suma sus litros a los del día
    "fraccionamiento_diario", "fraccionamiento_sin_recorrido",
    # H3: con la tarjeta de otro vehículo, la carga se compara con el tanque del dueño de la tarjeta
    "litros_mayor_a_tanque", "exceso_sin_antecedente",
]


def _encaja(lecturas, vehiculo, instante, odometro):
    """Si la lectura queda entre la anterior y la siguiente del vehículo en el reporte."""
    propias = lecturas[lecturas["vehiculo_id"] == vehiculo]
    antes = propias.loc[propias["instante"] < instante, "odometro"]
    despues = propias.loc[propias["instante"] > instante, "odometro"]
    return (antes.empty or antes.iloc[-1] <= odometro) and (despues.empty or odometro <= despues.iloc[0])


def causas_probables(consumo, registro, flota=None):
    """{id de carga o de pedido: causa} para las cargas sin pedido que tienen la firma de un error de carga.

    - proveedor_equivocado: hay un pedido de otra red del mismo vehículo, en el horario del cruce
      (de 3 horas antes a media hora después) y con los mismos litros.
    - tarjeta_equivocada: hay un pedido sin carga de otro vehículo, en ese horario y con los mismos
      litros, y el odómetro de la carga encaja con ese vehículo y no con el de la tarjeta. La carga
      siguiente del vehículo de la tarjeta, que cierra el tramo, lleva la misma causa (en el generador
      no se etiqueta: es una carga normal cuya alerta explica el error anterior).
    - dominio_equivocado: el mismo pedido de otro vehículo, pero el odómetro encaja con el propio.
    El pedido de cada firma lleva la misma causa que su carga.
    """
    pares, sin_carga = cruzar_registro(consumo, registro, flota=flota)
    lecturas = consumo.assign(instante=pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(consumo["hora"].astype(str)))
    lecturas = lecturas.dropna(subset=["odometro"]).sort_values("instante")
    cargas = lecturas[lecturas["id"].isin(pares.index[pares["registro_id"].isna()])].dropna(subset=["vehiculo_id"])
    pedidos = registro.assign(instante=_instantes(registro["fecha"], registro["hora"]))
    ajenos = pedidos[pedidos["estacion_servicio"] == ESTACION_AJENA]
    candidatos = pd.concat([ajenos.assign(ajeno=True), pedidos[pedidos["id"].isin(sin_carga["id"])].assign(ajeno=False)])
    cruce = cargas[["id", "vehiculo_id", "instante", "litros", "odometro"]].merge(
        candidatos[["id", "vehiculo_id", "instante", "litros_cargados", "ajeno"]], how="cross", suffixes=("", "_pedido"))
    minutos = (cruce["instante"] - cruce["instante_pedido"]) / pd.Timedelta(minutes=1)
    cruce = cruce[minutos.between(-MINUTOS_DESPUES_REGISTRO, MINUTOS_ANTES_REGISTRO)
                  & ((cruce["litros"] - cruce["litros_cargados"]).abs() <= TOLERANCIA_REGISTRO_LITROS)
                  & (cruce["ajeno"] == (cruce["vehiculo_id"] == cruce["vehiculo_id_pedido"]))]
    cruce = cruce.assign(distancia=(cruce["instante"] - cruce["instante_pedido"]).abs())
    causas = {}
    for carga, opciones in cruce.sort_values(["ajeno", "distancia"], ascending=[False, True]).groupby("id", sort=False):
        c = opciones.iloc[0]
        otras = lecturas[lecturas["id"] != carga]
        if c["ajeno"]:
            causa = "proveedor_equivocado"
        elif (_encaja(otras, c["vehiculo_id_pedido"], c["instante"], c["odometro"])
              and not _encaja(otras, c["vehiculo_id"], c["instante"], c["odometro"])):
            causa = "tarjeta_equivocada"
            siguiente = otras[(otras["vehiculo_id"] == c["vehiculo_id"]) & (otras["instante"] > c["instante"])]
            if len(siguiente):
                causas[siguiente["id"].iloc[0]] = causa
        else:
            causa = "dominio_equivocado"
        causas[carga] = causas[c["id_pedido"]] = causa
    return causas


def asignar_causa_probable(alertas, causas):
    """Agrega la columna causa_probable: la de la firma, SIN_EXPLICACION o vacía si la regla no tiene causa."""
    con_causa = alertas["regla"].isin(REGLAS_CON_CAUSA)
    causa = alertas["id_registro"].map(causas).where(con_causa)
    causa = causa.where(~con_causa | causa.notna(), SIN_EXPLICACION)
    explicada = causa.notna() & (causa != SIN_EXPLICACION)
    detalle = alertas["detalle"].astype(str).where(~explicada, alertas["detalle"].astype(str) + " · causa probable: "
                                                   + causa.fillna("").str.replace("_", " "))
    return alertas.assign(detalle=detalle, causa_probable=causa)


RESULTADO_PENDIENTE = "pendiente"


def asignar_observacion(alertas, observaciones):
    """Agrega `documentada` y `resultado_observacion`: qué alertas ya se investigaron y con qué resultado (#36).

    Se cruza por `id_registro` y `regla`. Una alerta documentada sigue siendo una alerta: no sale de los
    conteos ni de la cola. El texto de la observación no se trae: es texto libre. `pendiente` equivale a
    no investigada.
    """
    if observaciones is None or observaciones.empty:
        return alertas
    hechas = observaciones[observaciones["resultado"] != RESULTADO_PENDIENTE]
    resultado = hechas.drop_duplicates(["id_registro", "regla"], keep="last").set_index(
        ["id_registro", "regla"])["resultado"]
    claves = pd.MultiIndex.from_frame(alertas[["id_registro", "regla"]])
    encontrado = pd.Series(resultado.reindex(claves).to_numpy(), index=alertas.index)
    return alertas.assign(documentada=encontrado.notna(), resultado_observacion=encontrado)


def detectar_conciliacion_mensual(consumo, facturacion, excluir_ids=()):
    """H9 (ingenua): el consumo del mes de cada contrato, a precio del surtidor (como se sigue la
    ejecución del cupo), no coincide con el total facturado del contrato en el mes."""
    datos = consumo[~consumo["id"].isin(set(excluir_ids))].assign(
        periodo=lambda d: pd.to_datetime(d["fecha"]).dt.to_period("M").astype(str))
    registrado = datos.groupby(["contrato", "periodo"])["importe_total"].sum()
    facturado = facturacion.groupby(["contrato", "periodo"])["total_monto"].sum().rename("facturado")
    comparacion = facturacion.set_index(["contrato", "periodo"]).join(facturado).join(
        registrado.rename("registrado"), how="left").fillna({"registrado": 0})
    comparacion["total_monto"] = comparacion["facturado"]
    diferencia = (comparacion["total_monto"] - comparacion["registrado"]) / comparacion["registrado"].clip(lower=1)
    marcadas = comparacion[diferencia.abs() > DIFERENCIA_CONCILIACION].reset_index()
    marcadas = marcadas.assign(id=marcadas["numero_factura"], diferencia=diferencia[diferencia.abs()
                                                                                   > DIFERENCIA_CONCILIACION].values)
    return _alertas(marcadas, "TOTAL_INFLADO", "conciliacion_mensual",
                    lambda d: "facturado " + (d["diferencia"] * 100).round(1).astype(str)
                    + "% distinto del consumo registrado del mes")


def detectar_factura_no_concilia(facturacion, facturacion_detalle):
    """H9: el total de la factura no coincide con la suma de sus líneas."""
    lineas = facturacion_detalle.groupby("numero_factura")["importe"].sum()
    datos = facturacion.assign(lineas=facturacion["numero_factura"].map(lineas).fillna(0))
    diferencia = (datos["total_monto"] - datos["lineas"]) / datos["lineas"].abs().clip(lower=1)
    marcadas = datos[diferencia.abs() > DIFERENCIA_ENCABEZADO].assign(
        id=lambda d: d["numero_factura"], diferencia=diferencia[diferencia.abs() > DIFERENCIA_ENCABEZADO])
    return _alertas(marcadas, "TOTAL_INFLADO", "factura_no_concilia",
                    lambda d: "total " + (d["diferencia"] * 100).round(1).astype(str) + "% distinto de sus líneas")


def detectar_pdf_no_concilia(facturacion):
    """H9: el total del PDF no coincide con el monto de la deuda (si el PDF está cargado)."""
    con_pdf = facturacion.dropna(subset=["total_pdf"])
    diferencia = (con_pdf["total_pdf"] - con_pdf["total_monto"]) / con_pdf["total_monto"].abs().clip(lower=1)
    marcadas = con_pdf[diferencia.abs() > DIFERENCIA_PDF].assign(id=lambda d: d["numero_factura"])
    return _alertas(marcadas, "DIFERENCIA_DEUDA_PDF", "pdf_no_concilia",
                    lambda d: "PDF por " + d["total_pdf"].round(2).astype(str) + " y deuda por "
                    + d["total_monto"].round(2).astype(str))


def detectar_irregularidades_de_linea(consumo, facturacion_detalle):
    """H9: líneas sin carga registrada, duplicadas, con sobreprecio, al precio del surtidor o que no
    son combustible.

    El proveedor factura a precio de empresa, un 2% menor que el del surtidor que registra la
    carga: una línea al precio del surtidor es un cobro de más; una por encima, sobreprecio.
    """
    lineas = facturacion_detalle[facturacion_detalle["concepto"] == "COMBUSTIBLE"].rename(
        columns={"numero_linea": "id"}).sort_values("id")
    sin_consumo = lineas[~lineas["referencia_consumo"].isin(consumo["id"])]
    duplicadas = lineas[lineas.duplicated("referencia_consumo", keep="first")
                        & lineas["referencia_consumo"].isin(consumo["id"])]
    precio = consumo.set_index("id")["precio_unitario"]
    con_precio = lineas.assign(precio_carga=lineas["referencia_consumo"].map(precio)).dropna(subset=["precio_carga"])
    sobreprecio = con_precio[con_precio["precio_unitario"] > con_precio["precio_carga"] * (1 + TOLERANCIA_PRECIO)]
    al_surtidor = con_precio[(con_precio["precio_unitario"] >= con_precio["precio_carga"] * (1 - MARGEN_PRECIO_SURTIDOR))
                             & ~con_precio["id"].isin(sobreprecio["id"])]
    otros = facturacion_detalle[~facturacion_detalle["concepto"].isin(["COMBUSTIBLE", "AJUSTE"])].rename(
        columns={"numero_linea": "id"})
    return pd.concat([
        _alertas(sin_consumo, "LINEA_SIN_CONSUMO", "linea_sin_consumo",
                 lambda d: d["referencia_consumo"].astype(str) + " no existe en el registro de cargas"),
        _alertas(duplicadas, "LINEA_DUPLICADA", "linea_duplicada",
                 lambda d: d["referencia_consumo"].astype(str) + " ya fue facturada"),
        _alertas(sobreprecio, "SOBREPRECIO", "sobreprecio",
                 lambda d: d["precio_unitario"].astype(str) + " por litro; en la carga, "
                 + d["precio_carga"].astype(str)),
        _alertas(al_surtidor, "FACTURADA_A_PRECIO_DE_SURTIDOR", "precio_de_surtidor",
                 lambda d: d["precio_unitario"].astype(str) + " por litro, el del surtidor: sin descuento de empresa"),
        _alertas(otros, "PRODUCTO_NO_COMBUSTIBLE", "producto_no_combustible",
                 lambda d: d["concepto"].astype(str) + " en una factura de combustible"),
    ], ignore_index=True)


def clave_contrato_mes(contrato, mes):
    return f"CTO-{contrato}|{mes}"


def _saldos_por_contrato_mes(consumo, contratos, transferencias):
    """Por contrato y mes: saldo al empezar cada día, saldo para cargar (con las transferencias del
    día, que se acreditan antes de las cargas), consumo del día y transferencias recibidas. Es lo que se ve en los datos: el tope,
    las transferencias y las cargas de cada contrato."""
    fechas = pd.to_datetime(consumo["fecha"])
    por_dia = consumo.assign(dia=fechas.dt.normalize()).groupby(["contrato", "dia"])["importe_total"].sum()
    por_mes = consumo.assign(mes=fechas.dt.to_period("M")).groupby(["contrato", "mes"])["importe_total"].sum()
    meses = sorted(fechas.dt.to_period("M").unique())
    completos = [m for m in meses if m != meses[-1]] or meses
    tr = transferencias.assign(dia=pd.to_datetime(transferencias["fecha"]).dt.normalize())
    limite = contratos.set_index("indice")["limite_mensual"]
    for c in limite.index:
        medio = sum(float(por_mes.get((c, m), 0.0)) for m in completos) / len(completos)
        for m in meses:
            dias = pd.date_range(m.start_time, m.end_time.normalize(), freq="D")
            saldo, consumido = float(limite[c]), 0.0
            filas = []
            for n_dia, dia in enumerate(dias, 1):
                del_dia = tr[tr["dia"] == dia]
                recibidas = del_dia[del_dia["contrato_destino"] == c]
                cedidas = del_dia[del_dia["contrato_origen"] == c]
                historico = medio / len(dias)
                diario = (consumido + historico * DIAS_PESO_HISTORICO) / (n_dia - 1 + DIAS_PESO_HISTORICO)
                hoy = float(por_dia.get((c, dia), 0.0))
                filas.append({"dia": dia, "saldo_inicio": saldo, "consumo": hoy,
                              "proyeccion": diario * (len(dias) - n_dia + 1), "recibidas": recibidas,
                              "cedido": float(cedidas["monto"].sum()),
                              "saldo_para_cargar": saldo + recibidas["monto"].sum() - cedidas["monto"].sum()})
                saldo += recibidas["monto"].sum() - cedidas["monto"].sum() - hoy
                consumido += hoy
            yield c, m, filas


def detectar_ejecucion_supera_tope(consumo, contratos):
    """H10 (ingenua): el consumo del mes del contrato supera su tope."""
    mes = pd.to_datetime(consumo["fecha"]).dt.to_period("M")
    ejecucion = consumo.assign(mes=mes).groupby(["contrato", "mes"])["importe_total"].sum().reset_index()
    ejecucion["tope"] = ejecucion["contrato"].map(contratos.set_index("indice")["limite_mensual"])
    marcadas = ejecucion[ejecucion["importe_total"] > ejecucion["tope"]].assign(
        id=lambda d: [clave_contrato_mes(c, m) for c, m in zip(d["contrato"], d["mes"])],
        pct=lambda d: (100 * d["importe_total"] / d["tope"]).round(0))
    return _alertas(marcadas, "CARGA_CON_CUPO_AGOTADO", "ejecucion_supera_tope",
                    lambda d: "consumo del mes " + d["pct"].astype(int).astype(str) + "% del tope")


def detectar_irregularidades_de_cupo(consumo, contratos, transferencias):
    """H10: cargas con el saldo agotado y transferencias que la proyección no justifica.

    Sigue el saldo diario de cada contrato: tope del mes, transferencias y cargas. Un día con
    cargas cuyo saldo para cargar (el del inicio del día más las transferencias recibidas y
    menos las cedidas ese día) es cero o menos es una carga que el corte debió impedir.
    Una transferencia recibida es injustificada si la proyección del consumo a fin de mes
    (promedio del mes combinado con el histórico), con el margen de MARGEN_PROYECCION, no llega
    ni a HOLGURA_TRANSFERENCIA (90%) de lo disponible sin ella (saldo del inicio del día menos lo
    cedido) y ese día no se cargó más que eso.
    """
    agotadas, injustificadas = [], []
    for c, m, filas in _saldos_por_contrato_mes(consumo, contratos, transferencias):
        sin_saldo = [f for f in filas if f["saldo_para_cargar"] <= 0 and f["consumo"] > 0]
        if sin_saldo:
            agotadas.append({"id": clave_contrato_mes(c, m), "dias": len(sin_saldo)})
        for f in filas:
            # Se juzga con el saldo que le quedaba después de lo que el propio contrato cedió ese día
            disponible = f["saldo_inicio"] - f["cedido"]
            for _, tr in f["recibidas"].iterrows():
                necesaria = f["proyeccion"] * MARGEN_PROYECCION
                if necesaria < HOLGURA_TRANSFERENCIA * disponible and f["consumo"] <= disponible:
                    injustificadas.append({"id": clave_contrato_mes(c, m), "transferencia": tr["id"]})
    agotadas = pd.DataFrame(agotadas, columns=["id", "dias"])
    injustificadas = pd.DataFrame(injustificadas, columns=["id", "transferencia"]).drop_duplicates("id")
    return pd.concat([
        _alertas(agotadas, "CARGA_CON_CUPO_AGOTADO", "carga_con_saldo_agotado",
                 lambda d: d["dias"].astype(str) + " días con cargas y el saldo agotado"),
        _alertas(injustificadas, "TRANSFERENCIA_SIN_NECESIDAD", "transferencia_no_justificada",
                 lambda d: d["transferencia"] + ": la proyección del mes alcanzaba"),
    ], ignore_index=True)


GRUPO_DEPOSITO = "BAJA / REEMPLAZOS"
DIAS_TRANSMISION_RECIENTE = 7   # transmitió en la última semana


def _dispositivos_de_baja(flota, telemetria):
    """Dispositivos instalados en móviles cuyo estado es de baja (por dominio normalizado)."""
    de_baja = set(normalizar_dominio(flota.loc[flota["Estado"].astype(str).str.contains("BAJA"), "Dominio"]))
    return telemetria[normalizar_dominio(telemetria["Placa"]).isin(de_baja)].rename(columns={"Alias": "id"})


def detectar_baja_con_dispositivo(flota, telemetria):
    """H11 (ingenua): móvil de baja con un dispositivo asociado."""
    return _alertas(_dispositivos_de_baja(flota, telemetria), "DISPOSITIVO_ACTIVO_EN_BAJA", "baja_con_dispositivo",
                    lambda d: "móvil de baja con el dispositivo " + d["id"].astype(str) + " en " + d["Grupo"].astype(str))


def detectar_dispositivo_activo_en_baja(flota, telemetria, dias=DIAS_TRANSMISION_RECIENTE):
    """H11: móvil de baja con el dispositivo fuera del grupo de depósito y transmitiendo.

    Si el dispositivo quedó en el grupo de depósito (baja / reemplazos) y no transmite, está
    recuperado. Un móvil de baja no debe ir a desguace con el aparato funcionando.
    """
    dispositivos = _dispositivos_de_baja(flota, telemetria)
    ultima = pd.to_datetime(telemetria["UltimaConexion"], errors="coerce", format="mixed")
    referencia = ultima.max()
    transmite = (referencia - pd.to_datetime(dispositivos["UltimaConexion"], errors="coerce", format="mixed")
                 ) <= pd.Timedelta(days=dias)
    activos = dispositivos[(dispositivos["Grupo"] != GRUPO_DEPOSITO) & transmite]
    return _alertas(activos, "DISPOSITIVO_ACTIVO_EN_BAJA", "dispositivo_activo_en_baja",
                    lambda d: "móvil de baja con " + d["id"].astype(str) + " en " + d["Grupo"].astype(str)
                    + ", transmitiendo")


def gps_por_intervalo(dias):
    """Por transacción: km del GPS desde el día de carga anterior y si la cobertura fue completa."""
    filas = dias.explode("ids")[["ids", "km_gps", "completo"]].rename(columns={"ids": "id"})
    return filas.drop_duplicates("id").set_index("id")


def reglas_del_dataset(datos):
    """Aplica `ejecutar_reglas` a un dataset {tabla: DataFrame o None} como el de `cargar_dataset`."""
    return ejecutar_reglas(datos["flota"], datos["consumo"], datos.get("estaciones"), datos.get("telemetria_diaria"),
                           datos.get("solicitudes"), datos.get("facturacion"), datos.get("facturacion_detalle"),
                           contratos=datos.get("contratos"), transferencias=datos.get("transferencias"),
                           telemetria=datos.get("telemetria"), excepciones=datos.get("excepciones_odometro"),
                           observaciones=datos.get("observaciones_alertas"))


def ejecutar_reglas(flota, consumo, estaciones=None, telemetria_diaria=None, solicitudes=None,
                    facturacion=None, facturacion_detalle=None, contratos=None, transferencias=None,
                    telemetria=None, excepciones=None, observaciones=None):
    """Aplica todas las reglas disponibles y devuelve las alertas concatenadas.

    Las reglas con contexto se agregan cuando existen las fuentes que necesitan: fecha
    de estado en la flota, estaciones con coordenadas, GPS diario, solicitudes y el
    detalle de facturación. Las de solicitudes y facturación solo se aplican al
    escenario realista, donde esas fuentes son coherentes con el consumo.
    """
    duplicados = detectar_duplicados(consumo)
    # Un doble cobro no es una carga más del vehículo: las reglas de odómetro, de cargas del día y del
    # cruce con el registro no la cuentan (como los duplicados de nuestro registro)
    dobles = detectar_doble_cobro(consumo)
    excluidas = pd.concat([duplicados["id_registro"], dobles["id_registro"]], ignore_index=True)
    secuencia = secuencia_odometro(consumo, excluir_ids=excluidas)
    partes = [
        duplicados,
        detectar_nulos(consumo),
        detectar_dominio_invalido(consumo, flota),
        detectar_exceso_volumetrico(consumo, flota),
        detectar_odometro_regresivo(secuencia),
        detectar_odometro_salto_umbral_fijo(secuencia),
        detectar_odometro_salto_historial(secuencia),
        detectar_contingencia(consumo),
        dobles,
    ]

    if "FechaEstado" in flota.columns:
        # Las reglas con contexto ven también las cargas de otra red que anota el registro interno
        fuera = cargas_fuera_del_reporte(solicitudes)
        completa = secuencia_odometro(consumo, excluir_ids=excluidas, fuera=fuera, sin_repetidas=True)
        con_repetidas = secuencia_odometro(consumo, excluir_ids=excluidas, fuera=fuera)
        dias_del_reporte = cargas_por_dia(consumo, flota, excluir_ids=excluidas, gps_diario=telemetria_diaria)
        dias = cargas_por_dia(consumo, flota, excluir_ids=excluidas, gps_diario=telemetria_diaria, fuera=fuera)
        intervalos = gps_por_intervalo(dias) if telemetria_diaria is not None else None
        exceptuadas = cargas_exceptuadas(consumo, flota, excepciones)
        sin_avance = detectar_sin_avance_sin_excepcion(con_repetidas, exceptuadas)
        partes += [
            detectar_dominio_invalido(consumo, flota, normalizado=True),
            detectar_retroceso_con_contexto(completa, exceptuadas),
            detectar_salto_con_contexto(completa, intervalos, exceptuadas),
            detectar_exceso_sin_antecedente(consumo, flota),
            detectar_carga_vehiculo_inactivo(consumo, flota),
            detectar_fraccionamiento(dias_del_reporte),
            detectar_fraccionamiento(dias, con_rendimiento=True),
            detectar_rendimiento_bajo(dias, "odometro", exceptuadas | set(sin_avance["id_registro"])),
            detectar_odometro_sin_avance(secuencia),
            detectar_avance_menor_fuente(secuencia, cargas_exceptuadas(consumo, flota)),
            sin_avance,
        ]
        if "hora" in consumo.columns:
            partes.append(detectar_cargas_multiples(consumo, excluir_ids=duplicados["id_registro"]))
        if telemetria_diaria is not None:
            partes.append(detectar_rendimiento_bajo(dias, "gps", exceptuadas | set(sin_avance["id_registro"])))
        if estaciones is not None:
            partes.append(detectar_carga_lejos_de_base(consumo, estaciones))
            if telemetria_diaria is not None:
                partes.append(detectar_carga_lejos_del_gps(consumo, flota, estaciones, telemetria_diaria))
        excluir = excluidas
        if solicitudes is not None and "hora" in consumo.columns and "rendido" in solicitudes.columns:
            partes += [
                detectar_cruce_ingenuo(consumo, solicitudes, excluir),
                detectar_cruce_con_contexto(consumo, solicitudes, excluir, flota),
            ]
        if facturacion is not None and facturacion_detalle is not None:
            partes += [
                detectar_factura_no_concilia(facturacion, facturacion_detalle),
                detectar_irregularidades_de_linea(consumo, facturacion_detalle),
            ]
            if "contrato" in facturacion.columns and "contrato" in consumo.columns:
                # Un doble cobro se factura: la conciliación del mes la cuenta
                partes += [detectar_conciliacion_mensual(consumo, facturacion, duplicados["id_registro"]),
                           detectar_pdf_no_concilia(facturacion)]
        if telemetria is not None and "Grupo" in telemetria.columns:
            partes += [detectar_baja_con_dispositivo(flota, telemetria),
                       detectar_dispositivo_activo_en_baja(flota, telemetria)]
        if contratos is not None and transferencias is not None and "contrato" in consumo.columns:
            partes += [
                detectar_ejecucion_supera_tope(consumo, contratos),
                detectar_irregularidades_de_cupo(consumo, contratos, transferencias),
            ]

    alertas = pd.concat([p for p in partes if not p.empty], ignore_index=True)[COLUMNAS_ALERTA]
    if "FechaEstado" in flota.columns and solicitudes is not None and "hora" in consumo.columns \
            and "rendido" in solicitudes.columns:
        alertas = asignar_causa_probable(alertas, causas_probables(consumo, solicitudes, flota))
    return asignar_observacion(alertas, observaciones)
