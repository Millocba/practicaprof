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
from deteccion.reglas import (ESTACION_AJENA, cargas_exceptuadas, cargas_fuera_del_reporte, cruzar_registro,
                              leer_fecha, reglas_del_dataset)
from perfilador.adaptador import adaptar
from perfilador.controles import acotar
from perfilador.perfil import MINIMO_GRUPO, VERSION, dos_cifras

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


def _cuantiles(serie):
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    if len(serie) < MINIMO_GRUPO:
        return None
    return {f"p{int(q * 100):02d}": dos_cifras(float(serie.quantile(q))) for q in (0.05, 0.5, 0.95)}


def _variables(datos):
    """Variables del modelo con las mismas fuentes que tiene la fuente real (sin estaciones ni GPS diario)."""
    return construir_variables(datos["flota"], datos["consumo"], None, None, datos.get("solicitudes"),
                               datos.get("excepciones_odometro"))


def _modelo_sintetico(semillas, n_flota):
    """Random Forest entrenado con datasets sintéticos, con las mismas fuentes disponibles que la real."""
    from generator_pipeline_maestro import GeneradorMaestro

    partes_x, partes_y, referencia = [], [], None
    for semilla in semillas:
        with tempfile.TemporaryDirectory() as carpeta:
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
    diagnostico["cobertura"] = _cobertura(datos, alertas, registro_del_periodo if registro is not None else None)
    por_regla = {}
    for regla, grupo in alertas.groupby("regla"):
        ids = set(grupo["id_registro"])
        tabla, total = _unidad(ids, datos)
        por_regla[regla] = {"alertas": acotar(len(ids)), "pct": _pct(len(ids), total), "sobre": tabla}

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
        minutos = ((instante_carga.set_axis(consumo["id"]).reindex(pares.index).values
                    - instante_pedido.set_axis(registro["id"]).reindex(pares.values).values) / np.timedelta64(1, "m"))
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
        "supervisado_probabilidad": _cuantiles(probabilidad) | {"p99": dos_cifras(float(probabilidad.quantile(0.99)))},
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
