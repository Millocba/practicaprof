"""Análisis por hipótesis: qué encuentran las reglas en los datos.

Usa el mismo catálogo de hipótesis y las mismas reglas que las páginas de Detección e
Hipótesis. No usa el ground truth: muestra lo que vería un auditor. La validación
contra las anomalías inyectadas está en la página Hipótesis.

Qué muestra esta página
-----------------------
- Un resumen con cuántos registros marca cada hipótesis, primero con la regla "ingenua" (la más
  simple que se le ocurriría a cualquiera) y después con la regla "con contexto" (que suma
  información de otras fuentes: historial del vehículo, GPS, solicitudes, facturación...).
- Los problemas de calidad de datos: cargas duplicadas, campos obligatorios vacíos y patentes
  (dominios) que no aparecen en la flota.
- El detalle de una hipótesis elegida: indicadores, el "antes y después" entre reglas y la lista de
  casos concretos que quedaron marcados.

Para qué la usa quien audita
----------------------------
Es la vista "de trabajo": lo que vería una persona auditora con datos reales, donde NO se sabe de
antemano qué es una anomalía y qué no. Sirve para decidir qué casos mirar y para entender cuánto
ruido saca el contexto. Por eso acá no se usa el ground truth (la lista de anomalías que el
generador inyectó a propósito en los datos sintéticos).

Cómo encaja en la app
---------------------
Es una de las páginas del menú lateral de Streamlit (cada archivo de la carpeta `pages/` es una
página). Lee los datos que creó la página Generador, según el escenario elegido en la barra lateral
(realista o didáctico). La página Detección y la página Hipótesis usan las mismas reglas, pero
además las comparan con el ground truth para medir cuánto aciertan.

Nota sobre Streamlit: cada vez que la persona toca algo en la pantalla (un botón, un selector),
Streamlit vuelve a ejecutar este archivo entero de arriba a abajo. Por eso el código se lee como un
guion que "dibuja" la página en orden, y los cálculos pesados se guardan en caché para no repetirlos.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Se agregan a la ruta de búsqueda de Python la carpeta `utils` de la app y la raíz del repositorio,
# para poder importar `data_loader` (carga de datos) y el paquete `deteccion` (reglas e hipótesis).
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

from data_loader import (  # noqa: E402
    NOMBRES_ESCENARIO,
    asegurar_datos_maestro,
    load_dataset_deteccion,
    load_solicitudes,
    load_telemetria,
    selector_escenario,
)
from deteccion.hipotesis import describir_regla, hipotesis_del_escenario, reglas_de  # noqa: E402
from deteccion.reglas import CAMPOS_OBLIGATORIOS, ejecutar_reglas  # noqa: E402

# Configuración de la pestaña del navegador (título e ícono) y diseño a todo el ancho de la pantalla.
st.set_page_config(page_title="Análisis por hipótesis", page_icon="🔍", layout="wide")

st.markdown("# 🔍 Análisis por hipótesis")
st.markdown(
    "Qué encuentran las reglas en los datos, hipótesis por hipótesis. Para cada una se muestra cuánto "
    "marca la **regla ingenua** y cuánto queda con la **regla con contexto**, con los casos concretos. "
    "Esta página **no usa el ground truth**: muestra lo que vería un auditor. Cuántas de esas alertas son "
    "anomalías reales se valida en la página **Hipótesis**."
)

# Carga de datos. `selector_escenario` dibuja en la barra lateral la elección de escenario (realista o
# didáctico) y devuelve la opción elegida; `asegurar_datos_maestro` genera los datos si todavía no
# existen en disco; después se leen todas las tablas que usan las reglas.
escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
flota, consumo = datos["flota"], datos["consumo"]
telemetria = load_telemetria(escenario)
solicitudes = load_solicitudes(escenario)
detalle_factura = datos["facturacion_detalle"]
facturas = datos["facturacion"]

# Sin flota o sin cargas de combustible no hay nada que analizar: se muestra un error y `st.stop()`
# corta la ejecución del resto del archivo (la página queda solo con el mensaje).
if flota.empty or consumo.empty:
    st.error("❌ Datos insuficientes. Ejecutá primero el Generador.")
    st.stop()
st.caption(f"Escenario: **{NOMBRES_ESCENARIO[escenario]}** (se cambia en la barra lateral).")


# `@st.cache_data` guarda en memoria el resultado de la función. Como Streamlit re-ejecuta el archivo
# en cada interacción, sin caché las reglas se volverían a correr cada vez que se toca un selector.
# Con caché, si los datos de entrada son los mismos, se devuelve el resultado guardado al instante.
@st.cache_data
def calcular_alertas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion, facturacion_detalle):
    """Corre todas las reglas de detección sobre los datos y devuelve la tabla de alertas.

    Cada fila de la tabla de alertas dice qué regla marcó qué registro (`regla` e `id_registro`).
    Recibe las tablas del dataset: flota, cargas de combustible, estaciones, telemetría (GPS),
    solicitudes y facturación (cabecera y detalle por línea).
    """
    return ejecutar_reglas(flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
                           facturacion_detalle)


alertas = calcular_alertas(flota, consumo, datos["estaciones"], datos["telemetria_diaria"], datos["solicitudes"],
                           facturas, detalle_factura)
# El catálogo es la lista de hipótesis del escenario. Una hipótesis es una sospecha a comprobar (por
# ejemplo "hay cargas con más litros que el tanque") junto con las reglas que la ponen a prueba, de la
# más ingenua a la que usa más contexto.
catalogo = hipotesis_del_escenario(escenario)


# Algunas reglas marcan líneas de factura; este diccionario permite saber a qué factura pertenece cada
# línea, para poder contar "facturas con problemas" en lugar de líneas sueltas.
factura_de_linea = (dict(zip(detalle_factura["numero_linea"], detalle_factura["numero_factura"]))
                    if detalle_factura is not None else {})


def ids_de(reglas, por_factura=False):
    """Registros marcados por las reglas; `por_factura` cuenta cada línea como su factura.

    Recibe una lista de nombres de reglas y devuelve el conjunto (sin repetidos) de identificadores de
    registros que alguna de esas reglas marcó. Si `por_factura` es verdadero, cada línea de factura
    se reemplaza por el número de su factura, así una factura con tres líneas raras cuenta una vez.
    """
    ids = set(alertas.loc[alertas["regla"].isin(reglas), "id_registro"])
    return {factura_de_linea.get(i, i) for i in ids} if por_factura else ids


def tabla_de_hallazgos(ids_alertas):
    """Alertas con los datos del registro alertado (carga, línea de factura o factura).

    Una alerta sola solo dice "la regla X marcó el registro Y". Para que quien audita pueda mirar el
    caso, esta función le pega al lado los datos del registro: fecha, patente, litros, importe, etc.
    Junta en una sola tabla las cargas, las líneas de factura y las facturas (todas identificadas por
    una columna `id`), la cruza con las alertas y quita las columnas que quedaron vacías.
    """
    columnas_carga = ["id", "vehiculo_id", "dominio", "fecha", "estacion", "litros", "odometro"]
    tablas = [consumo[columnas_carga]]
    if detalle_factura is not None:
        tablas.append(detalle_factura.rename(columns={"numero_linea": "id"})[
            ["id", "numero_factura", "referencia_consumo", "fecha", "dominio", "litros", "precio_unitario", "importe"]])
    if facturas is not None:
        tablas.append(facturas.rename(columns={"numero_factura": "id"})[["id", "proveedor", "periodo", "total_monto"]])
    registros = pd.concat(tablas, ignore_index=True).drop_duplicates("id")
    return (ids_alertas.merge(registros, left_on="id_registro", right_on="id", how="left")
            .drop(columns="id").dropna(axis=1, how="all"))


# Tablas de búsqueda rápida: dado el id de una carga, a qué vehículo corresponde y en qué fecha fue.
vehiculo_de_carga = consumo.set_index("id")["vehiculo_id"]
fecha_de_carga = pd.to_datetime(consumo.set_index("id")["fecha"])

# ============================================================================
# Vistas
# ============================================================================

# Cada vista es una función que dibuja una parte de la página. Solo se llama a la que la persona
# eligió en el selector de más abajo (sección "Navegación").

def mostrar_resumen():
    """Dibuja la vista Resumen: una fila por hipótesis y un gráfico de barras.

    Para cada hipótesis cuenta cuántos registros marca la regla ingenua (la primera de su lista) y
    cuántos la regla con contexto (la última). Si la hipótesis tiene una sola regla, no hay
    comparación y se muestra "—".
    """
    st.markdown("## Resumen")
    filas = []
    for h in catalogo:
        ingenua, contexto = h["reglas"][0][0], h["reglas"][-1][0]
        por_factura = h.get("nivel") == "factura"
        n_ingenua = len(ids_de(reglas_de(ingenua), por_factura))
        n_contexto = len(ids_de(reglas_de(contexto), por_factura))
        filas.append({
            "Hipótesis": h["codigo"], "Tema": h["titulo"],
            "Regla ingenua": describir_regla(ingenua) if len(h["reglas"]) > 1 else "—",
            "Marcadas (ingenua)": f"{n_ingenua:,}" if len(h["reglas"]) > 1 else "—",
            "Regla con contexto": describir_regla(contexto), "Marcadas (con contexto)": n_contexto,
            "Unidad": "facturas" if h.get("nivel") == "factura" else "registros",
        })
    resumen = pd.DataFrame(filas)
    st.dataframe(resumen, use_container_width=True, hide_index=True)

    # Para el gráfico se usan solo las hipótesis que tienen las dos reglas. La columna "Marcadas
    # (ingenua)" se había guardado como texto con separador de miles ("1,234"); acá se la vuelve a
    # convertir en número. `melt` pasa la tabla de formato "ancho" (una columna por regla) a "largo"
    # (una fila por hipótesis y regla), que es lo que necesita el gráfico de barras agrupadas.
    comparables = resumen[resumen["Regla ingenua"] != "—"].assign(
        **{"Marcadas (ingenua)": lambda d: d["Marcadas (ingenua)"].str.replace(",", "").astype(int)})
    grafico = comparables.melt(
        id_vars="Hipótesis", value_vars=["Marcadas (ingenua)", "Marcadas (con contexto)"],
        var_name="Regla", value_name="Registros marcados")
    if not grafico.empty:
        # Escala logarítmica en el eje vertical: las cantidades van de unas pocas a miles, y en escala
        # común las barras chicas no se verían.
        fig = px.bar(grafico, x="Hipótesis", y="Registros marcados", color="Regla", barmode="group",
                     log_y=True, text_auto=True, height=380)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Escala logarítmica. Que la regla con contexto marque menos no garantiza que acierte más: "
                   "eso se valida en la página Hipótesis.")



def mostrar_calidad():
    """Dibuja la vista Calidad de datos: duplicados, campos vacíos y patentes sin vínculo.

    Son errores del registro, no conductas sospechosas: conviene verlos primero porque pueden
    generar alertas falsas en las demás reglas.
    """
    st.markdown("## Calidad de datos")
    st.markdown("Defectos del registro que conviene resolver antes de analizar el comportamiento.")
    # `st.columns(3)` divide el ancho en tres columnas lado a lado; cada `colN.metric(...)` muestra un
    # indicador grande (número con su título) dentro de su columna.
    col1, col2, col3 = st.columns(3)
    col1.metric("Cargas duplicadas", len(ids_de(["duplicado_exacto"])))
    col2.metric("Campos obligatorios vacíos", len(alertas[alertas["regla"].str.startswith("nulo_")]))
    col3.metric("Dominios sin vínculo", len(ids_de(["dominio_sin_vinculo"])))

    # Una fila por campo obligatorio: hay una regla `nulo_<campo>` por cada uno.
    nulos = pd.DataFrame([{"Campo": campo, "Vacíos": len(ids_de([f"nulo_{campo}"])),
                           "% de las cargas": len(ids_de([f"nulo_{campo}"])) / len(consumo)}
                          for campo in CAMPOS_OBLIGATORIOS])
    st.markdown("### Campos obligatorios vacíos")
    st.dataframe(nulos.style.format({"% de las cargas": "{:.2%}"}), use_container_width=True, hide_index=True)

    st.markdown("### Cargas duplicadas (ejemplos)")
    duplicadas = alertas[alertas["regla"] == "duplicado_exacto"]
    if duplicadas.empty:
        st.success("✅ No hay cargas duplicadas.")
    else:
        st.dataframe(tabla_de_hallazgos(duplicadas).head(20), use_container_width=True, hide_index=True)



def mostrar_hipotesis(h):
    """Dibuja el detalle de una hipótesis `h` (un diccionario del catálogo).

    Muestra el enunciado, indicadores, el "antes y después" entre la regla ingenua y la regla con
    contexto, y los casos concretos que marca la regla con contexto. Las hipótesis de nivel
    "factura" se cuentan en facturas e importes; las demás, en cargas de combustible y vehículos.
    """
    st.markdown(f"## {h['codigo']} — {h['titulo']}")
    st.markdown(f"**Hipótesis.** {h['enunciado']}")
    st.caption(f"Contexto que usa: {h['contexto']}.")
    por_factura = h.get("nivel") == "factura"
    # `h["reglas"]` es una lista de pasos (regla, descripción) ordenada de la más ingenua a la de más
    # contexto; `[-1]` toma el último paso, que es la regla con contexto.
    reglas_contexto = reglas_de(h["reglas"][-1][0])
    hallazgos = alertas[alertas["regla"].isin(reglas_contexto)]
    ids = set(hallazgos["id_registro"])

    # Indicadores
    col1, col2, col3 = st.columns(3)
    if por_factura:
        factura_de = dict(zip(detalle_factura["numero_linea"], detalle_factura["numero_factura"]))
        facturas_marcadas = {factura_de.get(i, i) for i in ids}
        importe = detalle_factura.set_index("numero_linea")["importe"]
        col1.metric("Facturas con hallazgos", f"{len(facturas_marcadas)} de {len(facturas)}")
        col2.metric("Líneas irregulares", len(ids & set(importe.index)))
        col3.metric("Importe de esas líneas", f"${importe.reindex(list(ids & set(importe.index))).sum():,.0f}")
    else:
        vehiculos = {vehiculo_de_carga.get(i) for i in ids} - {None}
        col1.metric("Cargas marcadas", f"{len(ids):,}")
        col2.metric("% de las cargas", f"{len(ids) / len(consumo):.2%}")
        col3.metric("Vehículos involucrados", len(vehiculos))

    # Antes y después: de la regla ingenua a la regla con contexto
    if len(h["reglas"]) > 1:
        st.markdown("### Antes y después")
        pasos = pd.DataFrame([{"Regla": describir_regla(regla), "Criterio": descripcion,
                               "Marcadas": len(ids_de(reglas_de(regla), por_factura))}
                              for regla, descripcion in h["reglas"]])
        if por_factura:
            st.caption("Contado en facturas: una línea irregular cuenta como su factura.")
        st.dataframe(pasos, use_container_width=True, hide_index=True)
        antes, despues = pasos["Marcadas"].iloc[0], pasos["Marcadas"].iloc[-1]
        unidad = "facturas" if por_factura else "registros"
        if antes > despues:
            st.markdown(f"Con contexto se descartan **{antes - despues:,}** de las **{antes:,}** {unidad} que "
                        f"marcaría la regla ingenua ({(antes - despues) / antes:.0%}).")
        elif antes < despues:
            st.markdown(f"La regla ingenua marca **{antes:,}** {unidad} y la regla con contexto **{despues:,}**: "
                        "el contexto permite ver casos que la ingenua no alcanza.")

    # H1: vinculación de cada fuente con la flota
    if h["codigo"] == "H1":
        st.markdown("### Vinculación de cada fuente con la flota")
        dominios = set(flota["Dominio"])
        fuentes = [("⛽ Consumo → flota", consumo["dominio"]),
                   ("📡 Telemetría → flota", telemetria["Placa"] if not telemetria.empty else pd.Series(dtype=str)),
                   ("📋 Solicitudes → flota", solicitudes["dominio"] if not solicitudes.empty else pd.Series(dtype=str))]
        vinculos = pd.DataFrame([{"Fuente": nombre, "Registros": len(serie),
                                  "Vinculados": int(serie.isin(dominios).sum()),
                                  "% vinculado": serie.isin(dominios).mean() if len(serie) else float("nan")}
                                 for nombre, serie in fuentes])
        st.dataframe(vinculos.style.format({"% vinculado": "{:.1%}"}, na_rep="—"),
                     use_container_width=True, hide_index=True)

    # Hallazgos
    st.markdown("### Hallazgos")
    if hallazgos.empty:
        st.success("✅ Las reglas no encontraron casos en estos datos.")
        return
    # Gráfico: para facturas, cuántos hallazgos hay por regla; para cargas, cómo se reparten por mes
    # (sirve para ver si los casos se concentran en algún período).
    if por_factura:
        por_regla = hallazgos.groupby("regla")["id_registro"].nunique().reset_index(name="Hallazgos")
        fig = px.bar(por_regla, x="regla", y="Hallazgos", text_auto=True, height=320, labels={"regla": ""})
    else:
        en_el_tiempo = hallazgos.assign(mes=hallazgos["id_registro"].map(fecha_de_carga).dt.to_period("M")
                                        .astype(str)).dropna(subset=["mes"])
        por_mes = en_el_tiempo.groupby(["mes", "regla"])["id_registro"].nunique().reset_index(name="Cargas")
        fig = px.bar(por_mes, x="mes", y="Cargas", color="regla", height=320, labels={"mes": ""})
    st.plotly_chart(fig, use_container_width=True)
    # Se muestran como máximo 100 casos para que la tabla no se vuelva lenta ni ilegible.
    st.dataframe(tabla_de_hallazgos(hallazgos.drop_duplicates("id_registro")).head(100),
                 use_container_width=True, hide_index=True)
    if len(ids) > 100:
        st.caption(f"Se muestran 100 de {len(ids):,} registros.")


# ============================================================================
# Navegación: una vista a la vez (las pestañas no entraban en la pantalla)
# ============================================================================

# `st.radio` muestra botones de opción y devuelve la elegida. El parámetro `key` le da un nombre fijo
# al widget: Streamlit guarda su valor en `st.session_state` (la memoria de la sesión del navegador)
# con ese nombre, así la elección se conserva entre re-ejecuciones y no choca con otros widgets.
VISTAS = ["📋 Resumen", "🧹 Calidad de datos", "🔍 Por hipótesis"]
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista_analisis", label_visibility="collapsed")
st.markdown("---")

if vista == VISTAS[0]:
    mostrar_resumen()
    st.info("💡 Para ver los hallazgos de una hipótesis, elegí **🔍 Por hipótesis** arriba.")
elif vista == VISTAS[1]:
    mostrar_calidad()
else:
    # Selector de hipótesis: la lista muestra "código · título" (`format_func`), pero lo que devuelve
    # es solo el código, que se usa para buscar la hipótesis en el catálogo.
    por_codigo = {h["codigo"]: h for h in catalogo}
    codigo = st.selectbox("Hipótesis", list(por_codigo), key="hipotesis_analisis",
                          format_func=lambda c: f"{c} · {por_codigo[c]['titulo']}")
    mostrar_hipotesis(por_codigo[codigo])
