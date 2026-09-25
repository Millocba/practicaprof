"""Modelo de ML: qué revisar primero (escenario realista) o Isolation Forest vs. reglas (didáctico)."""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(APP_DIR.parent))

from ayudas import seccion  # noqa: E402
from data_loader import (  # noqa: E402
    asegurar_datos_maestro,
    load_dataset_deteccion,
    load_maestro_metadata,
    selector_escenario,
)
from deteccion.modelo import (  # noqa: E402
    TIPOS_COMPORTAMIENTO,
    VARIABLES,
    comparar_con_reglas,
    ids_con_anomalia_de_comportamiento,
)
from deteccion import priorizacion  # noqa: E402

st.set_page_config(page_title="Modelo de ML", page_icon="🤖", layout="wide")

escenario = selector_escenario()
asegurar_datos_maestro(escenario)
datos = load_dataset_deteccion(escenario)
flota, consumo, ground_truth = datos["flota"], datos["consumo"], datos["ground_truth"]
seed = int(load_maestro_metadata(escenario).get("seed", 42))

if flota.empty or consumo.empty or ground_truth.empty:
    st.error("❌ No hay datos con ground truth. Ejecutá el Generador y volvé a esta página.")
    st.stop()


# ============================================================================
# Escenario didáctico: Isolation Forest vs. reglas
# ============================================================================

def pagina_didactica():
    seccion(
        "🤖 Isolation Forest vs. reglas", nivel=1,
        ayuda="Compara un método de **aprendizaje no supervisado** contra la línea base de "
              "reglas, en el escenario didáctico. El modelo no ve ninguna etiqueta: aprende qué "
              "es habitual y marca lo que se aparta. Sirve para responder una pregunta concreta: "
              "¿alcanza con un método que no conoce el problema, o hace falta escribir las "
              "reglas?")
    st.markdown(
        "Modelo **no supervisado**: aprende qué es habitual sin ver ninguna etiqueta y marca "
        "las transacciones que se apartan. Se compara con la línea base de reglas sobre las "
        "anomalías de comportamiento: exceso volumétrico (H3a) y odómetro (H2)."
    )
    st.info("ℹ️ La vista práctica (cola de revisión, curva de esfuerzo, modelo supervisado) está en el "
            "escenario **Realista**; elegilo en la barra lateral.")

    @st.cache_data
    def calcular(flota, consumo, ground_truth, seed):
        return comparar_con_reglas(flota, consumo, ground_truth, seed=seed)

    comparacion, por_tipo, resultados = calcular(flota, consumo, ground_truth, seed)

    with st.expander("Variables del modelo y criterio de corte", expanded=False):
        st.markdown("\n".join(f"- **{k}**: {v}" for k, v in VARIABLES.items()))
        st.markdown(
            "- El umbral es el de `contamination='auto'`: no se ajusta con la cantidad real de "
            "anomalías, porque eso usaría el ground truth.\n"
            "- La **precisión promedio** resume el ranking de puntajes sin depender de ningún umbral."
        )

    seccion(
        "Comparación",
        ayuda="Los dos métodos medidos con la misma vara: cuántos aciertos, cuántos falsos "
              "positivos y cuántos se les pasaron. **Precisión promedio** es la única columna "
              "comparable aunque los métodos usen umbrales distintos: mide si las alertas quedan "
              "arriba en el ranking, sin cortar en ningún punto.")
    formato = {"precision": "{:.1%}", "recall": "{:.1%}", "f1": "{:.3f}", "precision_promedio": "{:.3f}"}
    st.dataframe(
        comparacion[["metodo", "tp", "fp", "fn", "precision", "recall", "f1", "precision_promedio"]]
        .style.format(formato, na_rep="—"),
        use_container_width=True, hide_index=True,
    )

    seccion(
        "Recall por tipo de anomalía",
        ayuda="El mismo total desglosado por tipo. Es donde se ve el problema real del modelo no "
              "supervisado: puede tener un número global razonable y aun así fallar por completo "
              "en una categoría, porque ahí lo anómalo es un grupo denso y deja de parecer raro.")
    fig = px.bar(por_tipo, x="tipo_anomalia", y="recall", color="metodo", barmode="group",
                 range_y=[0, 1.05], text_auto=".0%",
                 labels={"tipo_anomalia": "", "recall": "Recall", "metodo": "Método"})
    fig.update_layout(yaxis_tickformat=".0%", height=380)
    st.plotly_chart(fig, use_container_width=True)

    seccion(
        "Distribución del puntaje de anomalía",
        ayuda="Cada transacción en el eje horizontal según su puntaje: más a la derecha, más rara. "
              "Lo útil es ver **si los dos grupos se separan**. Si se mezclan, el modelo no puede "
              "distinguir por sí solo; si hay un punto de corte razonable, el método funciona "
              "como clasificador aunque no haya escrito ninguna regla.")
    st.caption("La etiqueta real se usa solo para colorear el gráfico; el modelo no la ve.")
    reales = ids_con_anomalia_de_comportamiento(ground_truth)
    resultados["Etiqueta real"] = resultados["id"].isin(reales).map(
        {True: "Anomalía de comportamiento", False: "Normal"})
    fig = px.histogram(resultados, x="puntaje_if", color="Etiqueta real", nbins=60, barmode="overlay",
                       opacity=0.7, labels={"puntaje_if": "Puntaje (más alto = más anómalo)"})
    fig.update_layout(height=380, yaxis_title="Transacciones")
    st.plotly_chart(fig, use_container_width=True)

    ratio_exceso = por_tipo.set_index(["tipo_anomalia", "metodo"]).loc[
        ("EXCESO_VOLUMETRICO", "Isolation Forest"), "recall"]
    seccion(
        "Lectura",
        ayuda="La conclusión en dos puntos, y el límite que hay que tener presente: las reglas "
              "sacan 100% porque se escribieron sabiendo cómo el generador inyecta cada "
              "anomalía, así que ese número es un techo de referencia, no un resultado esperable "
              "con datos reales. Lo mismo aplica al Isolation Forest: está midiéndose contra el "
              "mismo generador.")
    st.markdown(
        "- Las **reglas** conocen cómo se inyectan las anomalías sintéticas, por eso son perfectas: "
        "sirven como techo de referencia, no como resultado esperable con datos reales.\n"
        f"- **Isolation Forest** encuentra las anomalías de odómetro, que son casos aislados, pero "
        f"solo el {ratio_exceso:.0%} de los excesos volumétricos: cada vehículo con exceso carga de "
        "más en todas sus transacciones y forma un grupo denso que deja de verse raro "
        "(*efecto de enmascaramiento*)."
    )
    st.caption(f"Semilla del modelo: {seed}. Tipos evaluados: {', '.join(TIPOS_COMPORTAMIENTO)}.")


# ============================================================================
# Escenario realista: priorización práctica
# ============================================================================

@st.cache_resource(show_spinner=False)
def modelo_supervisado(semillas):
    variables, etiqueta = priorizacion.datos_de_entrenamiento(list(semillas))
    return priorizacion.entrenar_supervisado(variables, etiqueta), len(variables), int(etiqueta.sum())


@st.cache_data(show_spinner=False)
def puntuar(_modelo, clave_modelo, flota, consumo, estaciones, telemetria_diaria, solicitudes, facturacion,
            facturacion_detalle, seed):
    dataset = {"flota": flota, "consumo": consumo, "estaciones": estaciones, "telemetria_diaria": telemetria_diaria,
               "solicitudes": solicitudes, "facturacion": facturacion, "facturacion_detalle": facturacion_detalle}
    return priorizacion.puntuar(dataset, _modelo, seed=seed)


def pagina_realista():
    seccion(
        "🤖 ¿Qué revisar primero?", nivel=1,
        ayuda="La pregunta práctica de una auditoría: con un equipo limitado, ¿qué se mira "
              "primero? Un auditor no revisa todas las alertas, revisa las **N más "
              "suspiciosas**. Esta página compara cinco maneras de ordenar esa cola y muestra, "
              "para la mejor, el trabajo concreto que quedaría pendiente con el motivo de cada "
              "caso.")
    st.markdown(
        "Un equipo de auditoría no revisa cientos de alertas: revisa las **N cargas más sospechosas**. "
        "Esta página compara cinco maneras de ordenar esa revisión y muestra, para la mejor, la cola "
        "de trabajo con el **motivo** de cada caso."
    )
    with st.expander("Los cinco métodos", expanded=False):
        st.markdown(
            "- **Reglas ingenuas**: litros > tanque, cualquier retroceso, suma del día > tanque, carga lejos "
            "de la zona habitual… Marcan o no marcan.\n"
            "- **Reglas con contexto**: las de la página *Hipótesis* (historial, estado de la flota, GPS, "
            "solicitudes).\n"
            "- **Isolation Forest**: no supervisado; ordena por rareza sin ver ninguna etiqueta.\n"
            "- **Modelo supervisado** (Random Forest): entrenado con datasets de *otras* semillas, como si "
            "aprendiera de auditorías anteriores ya resueltas y se aplicara al período actual.\n"
            "- **Combinado**: primero lo que marcan las reglas con contexto, ordenado por la probabilidad "
            "del modelo; después el resto."
        )

    semillas = tuple(s for s in priorizacion.SEMILLAS_ENTRENAMIENTO + [1004] if s != seed)[:3]
    with st.spinner("Entrenando el modelo supervisado con auditorías simuladas anteriores (una sola vez)..."):
        modelo, n_entrenamiento, n_anomalas = modelo_supervisado(semillas)
    with st.spinner("Puntuando las cargas..."):
        puntajes, variables, alertas = puntuar(modelo, semillas, flota, consumo, datos["estaciones"],
                                               datos["telemetria_diaria"], datos["solicitudes"],
                                               datos["facturacion"], datos["facturacion_detalle"], seed)

    anomalas = ids_con_anomalia_de_comportamiento(ground_truth)
    legitimos = datos["casos_legitimos"]
    total = len(anomalas)

    seccion(
        "¿Cuántas cargas podés revisar?",
        ayuda="El presupuesto es la restricción real del trabajo: cuántas cargas alcanza a "
              "revisar una persona o un equipo en el período. Mover el deslizador cambia la "
              "tabla, las métricas y la cola. La columna que más importa es **casos legítimos "
              "revisados en vano**: revisar una carga que estaba bien no es solo tiempo "
              "perdido, es confianza que se gasta con el área que la pidió.")
    presupuesto = st.slider("Presupuesto de revisión (cargas)", 10, 300, 50, step=10, key="presupuesto",
                            help="Cuántas cargas alcanza a revisar el equipo en este período. "
                                 "Es la restricción que define si un método sirve o no.")
    curva = priorizacion.curva_de_esfuerzo(puntajes, ground_truth, legitimos, maximo=300)
    en_presupuesto = curva[curva["revisadas"] == presupuesto].set_index("metodo").loc[priorizacion.METODOS]

    mejor = en_presupuesto["encontradas"].idxmax()
    col1, col2, col3 = st.columns(3)
    col1.metric("Cargas en el período", f"{len(consumo):,}")
    col2.metric("Anomalías de comportamiento", f"{total}", help="Lo que habría que encontrar")
    col3.metric(f"Encontradas revisando {presupuesto} ({mejor})",
                f"{int(en_presupuesto.loc[mejor, 'encontradas'])} de {total}",
                f"{en_presupuesto.loc[mejor, 'recall']:.0%}")

    tabla = en_presupuesto.reset_index()[["metodo", "encontradas", "recall", "precision", "legitimos_revisados"]]
    tabla["normales_revisadas"] = presupuesto - tabla["encontradas"] - tabla["legitimos_revisados"]
    st.dataframe(
        tabla.rename(columns={"metodo": "Método", "encontradas": "Anomalías encontradas",
                              "recall": "% del total", "precision": "% de aciertos",
                              "legitimos_revisados": "Casos legítimos revisados en vano",
                              "normales_revisadas": "Cargas normales revisadas"})
        .style.format({"% del total": "{:.0%}", "% de aciertos": "{:.0%}"}),
        use_container_width=True, hide_index=True,
    )

    seccion(
        "Curva de esfuerzo", nivel=3,
        ayuda="Cada curva dice qué fracción de las anomalías se encuentra según cuántas cargas se "
              "revisan. La línea punteada marca el presupuesto actual. Un método que arranca alto "
              "y después se aplana está revisando mejor los casos más graves primero; uno que "
              "arranca bajo no mejora con más tiempo.")
    st.caption("Qué fracción de las anomalías se encuentra según cuántas cargas se revisan, en el orden de cada método.")
    fig = px.line(curva, x="revisadas", y="recall", color="metodo",
                  labels={"revisadas": "Cargas revisadas", "recall": "Anomalías encontradas", "metodo": "Método"})
    fig.add_vline(x=presupuesto, line_dash="dash", line_color="gray")
    fig.update_layout(yaxis_tickformat=".0%", height=400)
    st.plotly_chart(fig, use_container_width=True)

    seccion(
        "Qué encuentra cada método", nivel=3,
        ayuda="El mismo desglose por tipo de anomalía, agora con el presupuesto ya fijado. Sirve "
              "para ver si a un método se le escapa una categoría concreta: puede ganar en total y "
              "no detectar nada de un tipo.")
    por_tipo = priorizacion.recall_por_tipo(puntajes, ground_truth, presupuesto)
    fig = px.bar(por_tipo, x="tipo_anomalia", y="recall", color="metodo", barmode="group", range_y=[0, 1.05],
                 labels={"tipo_anomalia": "", "recall": f"Encontradas revisando {presupuesto}", "metodo": "Método"})
    fig.update_layout(yaxis_tickformat=".0%", height=380)
    st.plotly_chart(fig, use_container_width=True)

    seccion(
        "📋 Cola de revisión",
        ayuda="El resultado accionable: la lista ordenada de cargas a revisar, con la "
              "**prioridad** y el **motivo** por el que se marcaron. El motivo es lo que la "
              "distingue de un número: es lo que permite que otra persona repita el criterio o "
              "lo discuta. Cambiá el método de ordenamiento arriba y la cola se recalcula.")
    col1, col2 = st.columns([2, 1])
    with col1:
        metodo = st.selectbox("Ordenar según", priorizacion.METODOS, index=priorizacion.METODOS.index("Combinado"),
                              key="metodo_cola")
    with col2:
        verificar = st.checkbox("Mostrar el resultado real (ground truth)", value=True, key="verificar",
                                help="Simula el resultado de la revisión. En la práctica no se conoce de antemano.")
    cola = priorizacion.cola_de_revision(puntajes, metodo, consumo, variables, alertas,
                                         cantidad=min(presupuesto, 100))
    if verificar:
        caso = legitimos.drop_duplicates("id_registro").set_index("id_registro")["tipo_caso"]
        tipo = ground_truth[ground_truth["id_registro"].isin(anomalas)].groupby("id_registro")["tipo_anomalia"].first()
        cola["resultado"] = cola["id"].map(tipo).radd("⚠️ ").fillna(
            cola["id"].map(caso).radd("✅ legítimo: ")).fillna("normal")
    columnas = ["prioridad", "id", "vehiculo_id", "fecha", "estacion", "litros", "odometro", "motivos", "reglas"]
    st.dataframe(cola[columnas + (["resultado"] if verificar else [])], use_container_width=True, hide_index=True)
    st.download_button("⬇️ Descargar la cola (CSV)", cola.to_csv(index=False), file_name="cola_de_revision.csv",
                       mime="text/csv")

    seccion(
        "🚗 Vehículos a auditar",
        ayuda="Agrupado por vehículo en vez de por carga. Sirve para el seguimiento: si un mismo "
              "vehículo aparece muchas veces, el problema no es un evento aislado sino un patrón "
              "que conviene tratar a nivel del vehículo, con su conductor o su estado.")
    st.caption(f"Vehículos con más cargas entre las {presupuesto} más sospechosas según {metodo}.")
    vehiculos = priorizacion.vehiculos_prioritarios(puntajes, metodo, consumo, cantidad_cargas=presupuesto)
    info = flota.set_index("Matricula")[["Dominio", "TipoVehiculo", "Estado", "DireccionGral"]]
    st.dataframe(vehiculos.join(info, on="vehiculo_id").head(20), use_container_width=True, hide_index=True)

    seccion(
        "🧾 Facturas a revisar",
        ayuda="La otra mitad de la auditoría: la facturación del proveedor contra las cargas "
              "registradas. Acá el problema no es el comportamiento del vehículo sino que lo "
              "facturado no coincide con lo registrado: líneas que no existen, duplicadas, "
              "precios inflados o totales que no cuadran con sus líneas.")
    st.caption("Conciliación de cada factura contra sus líneas y de cada línea contra la carga que referencia. "
               "Se ordenan por el importe en juego.")
    facturas = priorizacion.facturas_a_revisar(datos["facturacion"], datos["facturacion_detalle"], alertas)
    if facturas.empty:
        st.success("✅ Todas las facturas concilian con sus líneas y con las cargas registradas.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Facturas con hallazgos", f"{len(facturas)} de {len(datos['facturacion'])}")
        col2.metric("Importe en juego", f"${facturas['importe_en_juego'].sum():,.0f}")
        st.dataframe(facturas, use_container_width=True, hide_index=True)

    seccion(
        "🔍 Qué mira el modelo supervisado",
        ayuda="Qué variables usa el modelo y cuánto pesan. Esta es la parte que hay que mirar con "
              "más cuidado: si una sola variable domina, el modelo puede estar aprendiendo un "
              "truco del generador en vez de una relación real. Es un modelo de árbol, así que "
              "la importancia no implica causalidad: dice qué usa para separar, no por qué.")
    st.caption(f"Entrenado con {n_entrenamiento:,} cargas de {len(semillas)} períodos simulados anteriores "
               f"({n_anomalas} anomalías confirmadas).")
    importancia = priorizacion.importancia_de_variables(modelo, variables.columns)
    fig = px.bar(importancia.head(10), x="importancia", y="variable", orientation="h", hover_data=["descripcion"],
                 labels={"importancia": "Importancia", "variable": ""})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=380)
    st.plotly_chart(fig, use_container_width=True)

    reglas_i = en_presupuesto.loc["Reglas ingenuas"]
    combinado = en_presupuesto.loc["Combinado"]
    iforest = en_presupuesto.loc["Isolation Forest"]
    seccion(
        "Lectura",
        ayuda="Síntesis de los cinco métodos y, sobre todo, el **límite** del ejercicio: el modelo "
              "supervisado se entrena y se evalúa con datos del mismo generador, así que mide "
              "cuánto aporta cada fuente bajo los supuestos del escenario simulado, no el "
              "desempeño esperable con datos reales.")
    st.markdown(
        f"- Revisando **{presupuesto} cargas**, las reglas ingenuas encuentran {int(reglas_i['encontradas'])} "
        f"anomalías y gastan {int(reglas_i['legitimos_revisados'])} revisiones en casos legítimos; el método "
        f"combinado encuentra {int(combinado['encontradas'])} con {int(combinado['legitimos_revisados'])}.\n"
        "- El **modelo supervisado** llega a un rendimiento similar al de las reglas con contexto sin que "
        "nadie las haya escrito: aprende los patrones de auditorías anteriores. Sirve cuando los patrones "
        "cambian o combinan muchas variables.\n"
        f"- **Isolation Forest** ({int(iforest['encontradas'])} encontradas) no necesita casos previos, "
        "pero confunde lo raro con lo sospechoso: los viajes largos y los tanques no registrados también "
        "son raros.\n"
        "- Cada fila de la cola trae su **motivo**: la trazabilidad de por qué se revisa un caso es parte "
        "del resultado, no un agregado.\n\n"
        "**Límite.** El modelo supervisado se entrena y evalúa con datos del mismo generador; con datos "
        "reales, los patrones de las auditorías anteriores pueden no repetirse igual."
    )
    st.caption(f"Semilla evaluada: {seed}. Semillas de entrenamiento: {', '.join(map(str, semillas))}.")


if escenario == "realista":
    pagina_realista()
else:
    pagina_didactica()
