"""Línea base de detección por reglas.

Cada regla recibe solo las entidades generadas (flota y consumo) y devuelve alertas.
Ninguna regla lee el ground truth: la evaluación contra la verdad de referencia se
hace aparte, en `deteccion.evaluacion`.

Una alerta es una fila con:
- id_registro: id de la transacción de consumo alertada
- tipo_anomalia: tipo que la regla atribuye (mismo vocabulario que el ground truth)
- regla: nombre de la regla que la produjo
- detalle: explicación legible del motivo
"""
import pandas as pd

COLUMNAS_ALERTA = ["id_registro", "tipo_anomalia", "regla", "detalle"]

# Campos que toda transacción debería traer completos
CAMPOS_OBLIGATORIOS = ["estacion", "conductor", "odometro"]

# Umbrales
SALTO_FIJO_KM = 500            # km entre dos cargas...
SALTO_FIJO_DIAS = 7            # ...en esta cantidad de días o menos
SALTO_HISTORIAL_EXCESO_KM = 1000  # km por encima de lo esperado según el propio vehículo


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


def detectar_dominio_invalido(consumo, flota):
    """H1: el dominio de la transacción no corresponde a ningún vehículo de la flota."""
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


def secuencia_odometro(consumo, excluir_ids=()):
    """Cambio de odómetro de cada transacción respecto de la lectura válida anterior.

    Se descartan las lecturas vacías y las transacciones en `excluir_ids` (por ejemplo,
    duplicados ya detectados), para comparar cada carga con la anterior real.
    Agrega: km (cambio), dias (días transcurridos) y km_esperados (según la mediana
    de km por día del propio vehículo).
    """
    datos = consumo[consumo["odometro"].notna() & ~consumo["id"].isin(set(excluir_ids))].copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    datos = datos.sort_values(["vehiculo_id", "fecha", "id"])
    grupo = datos.groupby("vehiculo_id")
    datos["km"] = grupo["odometro"].diff()
    datos["dias"] = grupo["fecha"].diff().dt.days

    # Ritmo habitual del vehículo: mediana de km por día entre cargas (robusta a los
    # propios saltos y retrocesos)
    ritmo = (datos["km"] / datos["dias"].where(datos["dias"] > 0)).clip(lower=0)
    datos["km_por_dia_habitual"] = ritmo.groupby(datos["vehiculo_id"]).transform("median")
    datos["km_esperados"] = datos["km_por_dia_habitual"] * datos["dias"]
    return datos.dropna(subset=["km"])


def detectar_odometro_regresivo(secuencia):
    """H2: el odómetro marca menos que en la carga anterior."""
    regresion = secuencia[secuencia["km"] < 0]
    return _alertas(regresion, "ODOMETRO_REGRESIVO", "odometro_disminuye",
                    lambda d: "retrocede " + (-d["km"]).astype(int).astype(str) + " km")


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


def ejecutar_reglas(flota, consumo):
    """Aplica todas las reglas y devuelve las alertas concatenadas."""
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
    return pd.concat([p for p in partes if not p.empty], ignore_index=True)[COLUMNAS_ALERTA]
