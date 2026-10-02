"""Presentación Streamlit del EDA; los cálculos viven en :mod:`eda`."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ayudas import seccion
from data_loader import (
    load_consumo_maestro, load_contratos, load_estaciones, load_excepciones_odometro,
    load_facturacion, load_facturacion_detalle, load_flota, load_solicitudes,
    load_telemetria, load_telemetria_diaria, load_transferencias,
)
from deteccion.modelo import construir_variables
from eda import (
    comparacion_auditoria, preparar_cargas, resumen_calidad, resumen_cargas,
    resumen_cruces, resumen_flota, resumen_temporal,
)

PALETA = ["#4C9FD8", "#41B3A3", "#E5A94D", "#8FCB68", "#9B7ED0"]
LABELS = {
    "estado": "Estado", "tipo_vehiculo": "Tipo de vehículo", "combustible": "Combustible",
    "cantidad": "Cantidad", "telemetria": "Telemetría", "TipoVehiculo": "Tipo de vehículo",
    "litros_mediana": "Mediana de litros (L)", "cargas": "Cantidad de cargas",
    "proporcion_tanque": "Proporción del tanque", "km": "Kilómetros desde la carga anterior",
    "rendimiento_km_l": "Rendimiento (km/L)", "litros": "Litros (L)", "mes": "Mes",
    "dia_semana": "Día de la semana", "hora_del_dia": "Hora del día", "criterio": "Criterio",
    "porcentaje": "Porcentaje (%)", "formato": "Resultado del vínculo",
    "resultado": "Resultado", "tramo": "Tramo del circuito", "cobertura_pct": "Cobertura (%)",
}

NOMBRES_VARIABLES = {
    "ratio_litros_tanque": "Proporción del tanque",
    "proporcion_tanque": "Proporción del tanque",
    "km": "Kilómetros entre cargas",
    "rendimiento_relativo": "Rendimiento relativo",
    "rendimiento_km_l": "Rendimiento (km/L)",
    "cargas_en_el_dia": "Cargas en el día",
    "litros_vs_autorizado": "Litros sobre autorizados",
}
NOMBRES_PERCENTILES = {"p05": "P5", "p50": "Mediana", "p95": "P95",
                       .05: "P5", .25: "P25", .5: "Mediana", .75: "P75", .95: "P95"}


@st.cache_data(show_spinner=False)
def calcular_eda(escenario: str):
    """Calcula el EDA usando solo el escenario como clave de caché."""
    realista = escenario == "realista"
    flota, telemetria = load_flota(escenario), load_telemetria(escenario)
    consumo, solicitudes = load_consumo_maestro(escenario), load_solicitudes(escenario)
    gps = load_telemetria_diaria(escenario) if realista else pd.DataFrame()
    detalle = load_facturacion_detalle(escenario) if realista else pd.DataFrame()
    estaciones = load_estaciones(escenario) if realista else pd.DataFrame()
    excepciones = load_excepciones_odometro(escenario) if realista else pd.DataFrame()
    fuentes = {
        "Flota": flota, "Telemetría": telemetria, "Consumo": consumo,
        "Solicitudes": solicitudes, "Facturación": load_facturacion(escenario),
    }
    if realista:
        fuentes.update({
            "Estaciones": estaciones, "Detalle de facturación": detalle,
            "Telemetría diaria": gps, "Contratos": load_contratos(escenario),
            "Transferencias": load_transferencias(escenario),
            "Excepciones de odómetro": excepciones,
        })
    solicitudes_ok = solicitudes if realista and not solicitudes.empty else None
    gps_ok, detalle_ok = (None if gps.empty else gps), (None if detalle.empty else detalle)
    cargas = preparar_cargas(consumo, flota, solicitudes_ok, gps_ok)
    variables = construir_variables(
        flota, consumo, estaciones=None if estaciones.empty else estaciones,
        telemetria_diaria=gps_ok, solicitudes=solicitudes_ok,
        excepciones=None if excepciones.empty else excepciones,
    )
    return {
        "flota": resumen_flota(flota, telemetria), "cargas": resumen_cargas(cargas),
        "tiempo": resumen_temporal(cargas), "calidad": resumen_calidad(fuentes, flota, consumo),
        "cruces": resumen_cruces(consumo, flota, solicitudes_ok, gps_ok, detalle_ok),
        "variables": variables,
    }


def _barra(df, x, y, titulo, lectura, color=None):
    if df.empty:
        st.info("Esta vista no está disponible para el escenario seleccionado.")
        return
    fig = px.bar(df, x=x, y=y, color=color, title=titulo, labels=LABELS,
                 color_discrete_sequence=PALETA)
    fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(lectura)


def _caja(df, y, titulo, lectura):
    datos = df.dropna(subset=["TipoVehiculo", y]) if {"TipoVehiculo", y} <= set(df) else pd.DataFrame()
    if datos.empty:
        st.info("Esta vista no está disponible para el escenario seleccionado.")
        return
    fig = px.box(datos, x="TipoVehiculo", y=y, color="TipoVehiculo", points=False,
                 title=titulo, labels=LABELS, color_discrete_sequence=PALETA)
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(lectura)


def _dispersion(df):
    datos = df.dropna(subset=["km", "litros"])
    datos = datos[datos["km"] >= 0]
    if datos.empty:
        st.info("Esta vista no está disponible para el escenario seleccionado.")
        return
    if len(datos) > 2500:
        datos = datos.sample(2500, random_state=42)
    fig = px.scatter(datos, x="km", y="litros", color="TipoVehiculo", opacity=.45,
                     title="Relación entre recorrido y litros cargados", labels=LABELS,
                     color_discrete_sequence=PALETA)
    fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Variables: kilómetros desde la carga anterior válida y litros cargados. Unidad: carga; "
               "ejes en kilómetros y litros. Permite reconocer operaciones alejadas del patrón general, "
               "pero una separación visual necesita contexto antes de interpretarse.")


def mostrar_eda(escenario: str, base_dir: Path):
    """Dibuja los seis bloques exploratorios exigidos para el Sprint 3."""
    st.subheader("📊 Análisis exploratorio")
    st.caption("Lectura descriptiva y reproducible. Las diferencias orientan preguntas; no prueban alertas ni causas.")
    datos = calcular_eda(escenario)

    seccion("1. Flota — ¿Cómo está compuesta?", nivel=3,
            ayuda="Describe vehículos y cobertura de dispositivos antes de comparar comportamientos.")
    c1, c2 = st.columns(2)
    with c1:
        _barra(datos["flota"]["estados"], "estado", "cantidad", "Vehículos por estado",
               "Variables: estado y cantidad. Unidad: vehículo. Delimita qué parte de la flota está "
               "operativa y qué estados administrativos deben considerarse en los cruces.")
    with c2:
        _barra(datos["flota"]["tipos"], "tipo_vehiculo", "cantidad", "Vehículos por tipo",
               "Variables: tipo y cantidad. Unidad: vehículo. La mezcla de unidades impide aplicar un "
               "único patrón de capacidad, recorrido o consumo a toda la flota.")
    c1, c2 = st.columns(2)
    with c1:
        _barra(datos["flota"]["combustibles"], "combustible", "cantidad", "Combustible declarado",
               "Variables: combustible declarado y cantidad. Unidad: vehículo. Sirve para controlar la "
               "compatibilidad del producto informado en cada carga.")
    with c2:
        _barra(datos["flota"]["telemetria_estado"], "Estado", "cantidad",
               "Cobertura de telemetría por estado",
               "Variables: estado y presencia de dispositivo. Unidad: vehículo. Muestra en qué estados "
               "la ubicación y la actividad pueden aportar contexto adicional.", "telemetria")

    seccion("2. Cargas — ¿Cómo carga la flota?", nivel=3,
            ayuda="Compara volumen, capacidad, recorrido y rendimiento sin convertirlos en alertas.")
    dist = datos["cargas"]["distribuciones"]
    c1, c2 = st.columns(2)
    with c1:
        _barra(datos["cargas"]["por_tipo"], "TipoVehiculo", "litros_mediana",
               "Mediana de litros por tipo", "Variables: litros y tipo. Unidad: carga; volumen en litros. "
               "La referencia cambia por tipo de vehículo, por lo que una carga alta no se interpreta aislada.")
    with c2:
        _caja(dist, "proporcion_tanque", "Proporción del tanque por tipo",
              "Variables: litros/capacidad y tipo. Unidad: carga; razón sin unidad. Los valores altos "
              "orientan la revisión volumétrica, pero no constituyen por sí solos un exceso.")
    c1, c2 = st.columns(2)
    with c1:
        _caja(dist, "km", "Kilómetros entre cargas por tipo",
              "Variables: diferencia de odómetro y tipo. Unidad: carga; distancia en kilómetros. Solo "
              "incluye cargas con un tramo anterior válido; los casos sin tramo quedan vacíos.")
    with c2:
        _caja(dist, "rendimiento_km_l", "Rendimiento por tipo",
              "Variables: recorrido diario y litros. Unidad mostrada: carga; rendimiento en km/L. El "
              "valor diario se repite en las cargas del mismo vehículo y día, por lo que se usa como contexto.")
    _dispersion(dist)
    tabla_percentiles = datos["cargas"]["percentiles"].rename(columns=NOMBRES_VARIABLES).copy()
    if "percentil" in tabla_percentiles:
        tabla_percentiles["percentil"] = tabla_percentiles["percentil"].map(NOMBRES_PERCENTILES)
        tabla_percentiles = tabla_percentiles.rename(columns={"percentil": "Percentil"})
    st.dataframe(tabla_percentiles, use_container_width=True, hide_index=True)

    seccion("3. Tiempo — ¿Cuándo se realizan las cargas?", nivel=3,
            ayuda="Muestra frecuencia y volumen cargado durante el período.")
    for clave, nombre in [("mes", "mes"), ("dia_semana", "día de la semana"), ("hora_del_dia", "hora")]:
        c1, c2 = st.columns(2)
        with c1:
            _barra(datos["tiempo"][clave], clave, "cargas", f"Cargas por {nombre}",
                   f"Variables: {nombre} y cantidad. Unidad: carga. Permite reconocer cuándo se concentra "
                   "la actividad y qué períodos requieren contexto operativo adicional.")
        with c2:
            _barra(datos["tiempo"][clave], clave, "litros", f"Litros por {nombre}",
                   f"Variables: {nombre} y litros. Unidad: carga; volumen en litros. Distingue períodos "
                   "con muchas operaciones de aquellos con mayor volumen total.")

    seccion("4. Calidad — ¿Qué tan preparados están los datos?", nivel=3,
            ayuda="Mide completitud, unicidad y el efecto de normalizar dominios con la regla oficial H1.")
    c1, c2 = st.columns(2)
    with c1:
        _barra(datos["calidad"]["vinculacion"], "criterio", "porcentaje",
               "Vinculación antes y después de H1",
               "Variables: criterio y resultado. Unidad: carga; resultado en porcentaje. Separar las "
               "tarjetas personales evita confundir una identificación por persona con un dominio inválido.",
               "resultado")
    with c2:
        _barra(datos["calidad"]["formatos_dominio"], "formato", "cantidad",
               "Resultado del vínculo de dominios",
               "Variables: forma de vinculación y cantidad. Unidad: carga. Muestra qué parte coincide de "
               "forma exacta, cuál requiere normalización, cuál usa tarjeta personal y cuál queda sin vínculo.")
    calidad = datos["calidad"]["columnas"]
    if not calidad.empty:
        tabla_calidad = calidad.sort_values(["completitud_pct", "fuente", "columna"]).head(30).rename(columns={
            "fuente": "Fuente", "columna": "Columna", "filas": "Filas",
            "completitud_pct": "Completitud (%)", "valores_unicos": "Valores únicos",
            "unicidad_pct": "Unicidad (%)",
        })
        st.dataframe(tabla_calidad,
                     use_container_width=True, hide_index=True)
        st.caption("Se muestran primero las 30 columnas con menor completitud.")
    st.info("La comparación de reglas simples y con contexto permanece en las páginas de análisis e hipótesis.")

    seccion("5. Cruce entre fuentes — ¿Qué partes del circuito pueden vincularse?", nivel=3,
            ayuda="Describe cobertura sin convertir una ausencia de vínculo en irregularidad.")
    cruces = datos["cruces"]
    _barra(cruces, "tramo", "cobertura_pct", "Cobertura de los cruces disponibles",
           "Variables: tramo y cobertura. Unidad: carga; resultado en porcentaje. Una cobertura menor "
           "delimita el universo analizable con esa fuente y no confirma una irregularidad.")
    if not cruces.empty:
        st.dataframe(cruces, use_container_width=True, hide_index=True)
    if escenario != "realista":
        st.info("El escenario didáctico no incluye el circuito completo ni GPS diario; este bloque es parcial.")

    seccion("6. Sintético frente a real — ¿El escenario conserva la escala observada?", nivel=3,
            ayuda="Compara el escenario actual con agregados reales aprobados, sin exponer filas.")
    if escenario != "realista":
        st.info("Esta comparación se muestra solo en el escenario realista calibrado con los agregados aprobados.")
        return
    auditoria = base_dir / "perfiles" / "aprobados" / "auditoria_2026-09-30.json"
    elegidas = ["ratio_litros_tanque", "km", "rendimiento_relativo", "cargas_en_el_dia", "litros_vs_autorizado"]
    comp = comparacion_auditoria(auditoria, datos["variables"], elegidas) if auditoria.exists() else pd.DataFrame()
    if comp.empty:
        st.info("No se encontró una auditoría agregada aprobada.")
        return
    comp_presentacion = comp.copy()
    comp_presentacion["variable"] = comp_presentacion["variable"].map(NOMBRES_VARIABLES).fillna(
        comp_presentacion["variable"])
    comp_presentacion["percentil"] = comp_presentacion["percentil"].map(NOMBRES_PERCENTILES).fillna(
        comp_presentacion["percentil"])
    grafico = comp_presentacion.melt(id_vars=["variable", "percentil"], value_vars=["real", "sintetico"],
                        var_name="origen", value_name="valor")
    grafico["origen"] = grafico["origen"].map({"real": "Real agregado", "sintetico": "Sintético"})
    fig = px.bar(grafico, x="percentil", y="valor", color="origen", facet_col="variable",
                 barmode="group", color_discrete_sequence=PALETA,
                 title="Fuente real agregada y escenario sintético actual",
                 labels={"percentil": "Percentil", "valor": "Valor", "origen": "Origen"})
    fig.update_yaxes(matches=None)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.update_layout(margin=dict(l=10, r=10, t=70, b=10), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)
    tabla_comp = comp_presentacion.rename(columns={
        "variable": "Variable", "percentil": "Percentil", "real": "Real agregado",
        "sintetico": "Sintético", "diferencia": "Diferencia",
    })
    st.dataframe(tabla_comp, use_container_width=True, hide_index=True)
    st.caption("Variables: volumen relativo, recorrido, rendimiento, frecuencia diaria y autorización. "
               "Unidad: agregado por variable y percentil. Las medianas son cercanas, pero los extremos "
               "de kilómetros y rendimiento son menores en el escenario sintético; la comparación evalúa "
               "escala, no equivalencia estadística.")
