"""Perfil de fuentes: estructura y calidad de fuentes externas sin guardar sus datos.

- Generar un perfil a partir de archivos (solo con la app corriendo en la máquina local:
  en un despliegue en la nube los archivos viajarían a un servidor externo).
- Comparar un perfil con los datos sintéticos y listar las brechas.
- Perfiles guardados: los aprobados se versionan en perfiles/aprobados/.

Los archivos se procesan en memoria y nunca se escriben. Solo se guarda el perfil agregado.

Explicación para quien recién empieza:

- Qué muestra: tres vistas que se eligen arriba de todo.
  1. Generar un perfil: se suben archivos CSV o Excel de una fuente y la página
     muestra un "perfil": un resumen de su estructura y calidad (tablas,
     columnas, tipos de dato, formatos, porcentaje de faltantes, relaciones)
     hecho solo con cifras agregadas, nunca con filas ni valores individuales.
  2. Comparar con el generador: pone un perfil al lado del perfil de los datos
     sintéticos y lista las "brechas", es decir, lo que la fuente tiene y el
     generador todavía no imita (una tabla, una columna, un formato, etc.).
  3. Perfiles guardados: lista los perfiles aprobados y permite revisar y
     aprobar los pendientes.
- Para qué la usa quien audita: para saber qué tan parecidos son los datos
  sintéticos a los de una fuente de datos operativos sin copiar esos datos, y
  así decidir qué mejorar en el generador. La revisión y aprobación deja
  registro de quién verificó que el perfil no contiene información sensible.
- Cómo encaja en la app: usa el paquete perfilador/ (fuera de la app) para
  calcular perfiles y brechas; perfila los datos sintéticos del escenario
  elegido con el mismo método, para que la comparación sea justa.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

# Se agregan utils/ y la raíz del repositorio a los lugares donde Python busca
# módulos, para poder importar data_loader y el paquete perfilador.
APP_DIR = Path(__file__).parent.parent
RAIZ = APP_DIR.parent
sys.path.insert(0, str(APP_DIR / "utils"))
sys.path.insert(0, str(RAIZ))

from data_loader import NOMBRES_ESCENARIO, asegurar_datos_maestro, directorio, selector_escenario  # noqa: E402
from perfilador.comparar import (  # noqa: E402
    comparar,
    informe_markdown,
    perfil_de_directorio,
    sugerir_emparejamiento,
)
from perfilador.perfil import MINIMO_GRUPO, OTRA, aprobar_archivo, leer_tablas, perfilar  # noqa: E402

# Carpetas del circuito de revisión: un perfil nuevo se guarda primero en
# "pendientes" (no se sube al repositorio) y, cuando una persona lo revisa y
# aprueba, pasa a "aprobados" (sí se versiona con git).
# NO_MODELADA es la opción para indicar que una tabla de la fuente no tiene
# equivalente en los datos sintéticos.
PENDIENTES = RAIZ / "perfiles" / "pendientes"
APROBADOS = RAIZ / "perfiles" / "aprobados"
NO_MODELADA = "— no modelada —"

st.set_page_config(page_title="Perfil de fuentes", page_icon="🔬", layout="wide")

st.markdown("# 🔬 Perfil de fuentes")
st.markdown(
    "Describe la **estructura y la calidad** de una fuente de datos (tablas, columnas, tipos, formatos, faltantes, "
    "relaciones) **sin guardar sus datos**, y la compara con lo que produce el generador para saber qué le falta. "
    f"Sigue `docs/REAL_DATA_BOUNDARY.md`: sin filas, sin valores sueltos, sin grupos de menos de {MINIMO_GRUPO} casos, "
    "y las columnas sensibles (identificadores, personas, patentes, ubicaciones, organizaciones, texto libre) solo por su formato."
)
# Escenario elegido en la barra lateral; se recuerda en st.session_state, la
# "memoria" que Streamlit conserva mientras el script se re-ejecuta en cada clic.
escenario = selector_escenario()


def es_local():
    """True si la app corre en esta máquina: solo así se permite subir archivos para perfilar.

    Mira la dirección con la que se abrió la página: si es localhost o
    127.0.0.1, la app corre en la misma computadora y los archivos no salen de
    ella. La variable de entorno PERFILADOR_PERMITIR_ARCHIVOS=1 fuerza el permiso
    (por ejemplo, para las pruebas automáticas). Si no se puede leer la
    dirección, por precaución se considera que no es local.
    """
    if os.environ.get("PERFILADOR_PERMITIR_ARCHIVOS") == "1":
        return True
    try:
        host = st.context.headers.get("Host", "")
    except Exception:  # noqa: BLE001
        host = ""
    return host.split(":")[0] in {"localhost", "127.0.0.1"}


def tabla_de_columnas(tabla):
    """Arma una tabla para mostrar en pantalla, con una fila por columna de la tabla perfilada.

    Recibe el perfil de una tabla y resume cada columna: tipo, si es sensible,
    porcentaje de faltantes, cantidad de valores distintos, los formatos más
    frecuentes (hasta 3), las categorías más frecuentes (hasta 4) y la mediana
    si es numérica. Todo son porcentajes o cifras agregadas, no valores sueltos.
    """
    filas = []
    for c in tabla["perfil_columnas"]:
        formatos = ", ".join(f"{f['formato']} ({f['pct']}%)" for f in c.get("formatos", [])[:3] if f["formato"] != OTRA)
        categorias = ", ".join(f"{k['valor']} ({k['pct']}%)" for k in c.get("categorias", [])[:4])
        filas.append({"Columna": c["nombre"], "Tipo": c.get("tipo", c.get("error", "?")), "Sensible": c.get("sensible") or "",
                      "Faltantes %": c.get("faltantes_pct"), "Distintos": c.get("cardinalidad"),
                      "Formatos": formatos, "Categorías": categorias,
                      "Mediana": (c.get("numerico") or {}).get("p50")})
    return pd.DataFrame(filas)


def resumen_seguro(perfil):
    """Faltantes promedio y cantidad de columnas por tipo: solo agregados del perfil, nunca valores.

    Devuelve dos cosas: el porcentaje promedio de faltantes entre todas las
    columnas de todas las tablas (o None si no hay dato) y un conteo de cuántas
    columnas hay de cada tipo (texto, número, fecha, etc.).
    """
    columnas = [c for t in perfil["tablas"].values() for c in t["perfil_columnas"]]
    faltantes = [c["faltantes_pct"] for c in columnas if c.get("faltantes_pct") is not None]
    tipos = pd.Series([c.get("tipo", "error") for c in columnas]).value_counts()
    return (round(sum(faltantes) / len(faltantes), 1) if faltantes else None), tipos


def mostrar_resumen_seguro(perfil):
    """Muestra en pantalla el resumen de resumen_seguro(): faltantes promedio y tipos detectados."""
    faltantes, tipos = resumen_seguro(perfil)
    col1, col2 = st.columns([1, 3])
    col1.metric("Faltantes promedio por columna", f"{faltantes}%" if faltantes is not None else "—")
    col2.markdown("**Tipos detectados:** " + " · ".join(f"{tipo} ({n})" for tipo, n in tipos.items()))


def mostrar_perfil(perfil):
    """Muestra un perfil completo en pantalla.

    Arriba, cuatro cifras (tablas, columnas, columnas sensibles y relaciones).
    Después, una sección plegable por tabla con sus columnas y las columnas que
    podrían servir como clave. Al final, si las hay, las relaciones detectadas
    entre tablas con su porcentaje de coincidencia.
    """
    tablas = perfil["tablas"]
    sensibles = sum(1 for t in tablas.values() for c in t["perfil_columnas"] if c.get("sensible"))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tablas", len(tablas))
    col2.metric("Columnas", sum(t["columnas"] for t in tablas.values()))
    col3.metric("Columnas sensibles (solo formato)", sensibles)
    col4.metric("Relaciones detectadas", len(perfil["relaciones"]))
    for nombre, tabla in tablas.items():
        # st.expander: sección plegable, cerrada por defecto, para no llenar la
        # pantalla cuando la fuente tiene muchas tablas.
        with st.expander(f"📄 {nombre} — {tabla['filas']} filas, {tabla['columnas']} columnas, "
                         f"{tabla.get('filas_duplicadas_pct') or 0}% filas duplicadas"):
            if tabla["columnas_candidatas_a_clave"]:
                st.caption("Candidatas a clave: " + ", ".join(f"`{c}`" for c in tabla["columnas_candidatas_a_clave"]))
            st.dataframe(tabla_de_columnas(tabla), use_container_width=True, hide_index=True)
    if perfil["relaciones"]:
        st.markdown("**Relaciones entre tablas** (porcentaje de valores distintos del origen que existen en el destino)")
        st.dataframe(pd.DataFrame(perfil["relaciones"]).rename(columns={
            "origen": "Origen", "destino": "Destino", "cobertura_exacta_pct": "Coincidencia exacta %",
            "cobertura_normalizada_pct": "Coincidencia normalizada %"}), use_container_width=True, hide_index=True)


def perfiles_en(carpeta):
    """Lista los perfiles (.json) de una carpeta, del más nuevo al más viejo por nombre.

    Si la carpeta no existe todavía, devuelve una lista vacía.
    """
    return sorted(carpeta.glob("*.json"), reverse=True) if carpeta.exists() else []


# @st.cache_data guarda el resultado de la función: la primera vez la ejecuta
# (mostrando el mensaje de espera) y las siguientes, con los mismos argumentos,
# devuelve lo guardado sin recalcular. Perfilar los datos sintéticos tarda, y sin
# caché se repetiría en cada clic, porque el script se re-ejecuta entero.
@st.cache_data(show_spinner="Perfilando los datos sintéticos con el mismo perfilador...")
def perfil_sintetico(escenario, _marca):
    """Perfila los datos sintéticos del escenario con el mismo perfilador que la fuente.

    Así los dos perfiles se calculan igual y la comparación es justa. `_marca` es
    la fecha de modificación de metadata.json. Ojo: Streamlit no tiene en cuenta
    los parámetros que empiezan con guion bajo para decidir si reutiliza la
    caché, así que `_marca` no fuerza un recálculo por sí sola; el perfil se
    renueva cuando se vacía la caché (por ejemplo, al generar desde el Generador).
    """
    return perfil_de_directorio(directorio(escenario), origen=f"sintético ({NOMBRES_ESCENARIO[escenario].lower()})")


# Selector de vista: según la opción elegida se ejecuta solo uno de los tres
# bloques de abajo (if / elif / else). label_visibility="collapsed" oculta el título.
VISTAS = ["1️⃣ Generar un perfil", "2️⃣ Comparar con el generador", "📁 Perfiles guardados"]
vista = st.radio("Vista", VISTAS, horizontal=True, key="vista_perfil", label_visibility="collapsed")
st.markdown("---")

# ---------------------------------------------------------------- Generar
if vista == VISTAS[0]:
    # Por seguridad, en la app publicada en internet no se pueden subir archivos:
    # se explica cómo generar el perfil en la propia computadora.
    if not es_local():
        st.warning(
            "🔒 **Subir archivos está deshabilitado en la app publicada.** En un despliegue en la nube los archivos "
            "viajarían a un servidor externo. Generá el perfil en tu máquina, junto a los datos:"
        )
        st.code('python -m perfilador perfilar archivo1.xlsx archivo2.csv --origen "fuentes reales"', language="bash")
        st.markdown("O abrí esta página con la app corriendo en tu máquina (`streamlit run streamlit_app/app.py`). "
                    "Después podés cargar el perfil (el `.json`) en **2️⃣ Comparar con el generador**.")
    else:
        st.info("🔐 Los archivos se leen **en memoria** y no se guardan. Solo se conserva el perfil agregado, "
                "que tenés que revisar antes de aprobarlo.")
        origen = st.text_input("Nombre de la fuente (para identificar el perfil)", value="fuentes reales",
                               key="origen_fuente")
        # st.file_uploader muestra una zona para arrastrar o elegir archivos y
        # devuelve una lista de archivos en memoria (vacía si no se subió nada).
        # No se guardan en disco.
        archivos = st.file_uploader("Archivos de la fuente (CSV o Excel)", type=["csv", "xlsx", "xls", "xlsm"],
                                    accept_multiple_files=True, key="archivos_fuente")
        # Como el script se re-ejecuta en cada clic, sin cuidado se volvería a
        # perfilar todo cada vez. La "firma" (nombre de la fuente + nombre y tamaño
        # de cada archivo) se guarda en st.session_state: solo se perfila de nuevo
        # si la firma cambió, y el perfil ya calculado queda guardado ahí también.
        firma = (origen, tuple((a.name, a.size) for a in archivos)) if archivos else None
        if firma and firma != st.session_state.get("firma_perfilada"):
            tablas = {}
            for archivo in archivos:
                tablas.update(leer_tablas(archivo, archivo.name))
            with st.spinner("Perfilando..."):
                st.session_state["perfil_generado"] = perfilar(tablas, origen=origen)
            st.session_state["firma_perfilada"] = firma
            del tablas  # los datos no se conservan: solo el perfil
        perfil = st.session_state.get("perfil_generado")
        if perfil:
            mostrar_resumen_seguro(perfil)
            mostrar_perfil(perfil)
            texto = json.dumps(perfil, indent=2, ensure_ascii=False)
            nombre_archivo = f"perfil_{date.today().isoformat()}.json"
            # Dos formas de conservar el perfil: descargarlo o guardarlo en
            # perfiles/pendientes/ para revisarlo después.
            col1, col2 = st.columns(2)
            col1.download_button("⬇️ Descargar el perfil (JSON)", texto, file_name=nombre_archivo,
                                 mime="application/json", use_container_width=True, key="descargar_perfil")
            if col2.button("💾 Guardar en perfiles/pendientes/", use_container_width=True, key="guardar_pendiente"):
                PENDIENTES.mkdir(parents=True, exist_ok=True)
                (PENDIENTES / nombre_archivo).write_text(texto, encoding="utf-8")
                st.success(f"Guardado en `perfiles/pendientes/{nombre_archivo}` (no se versiona hasta aprobarlo).")
            with st.expander("Ver el JSON completo antes de guardarlo o compartirlo"):
                st.json(perfil)

            st.markdown("**Aprobar** después de revisar que no contenga nombres, identificadores ni valores sensibles:")
            col1, col2 = st.columns(2)
            revisor = col1.text_input("Nombre del revisor", key="revisor_generado")
            notas = col2.text_input("Notas (opcional)", key="notas_generado")
            # El botón queda deshabilitado hasta que se escribe quién revisa: la
            # aprobación siempre tiene un responsable. Si el perfil no estaba
            # guardado como pendiente, se guarda primero y después se aprueba.
            if st.button("✅ Aprobar y mover a perfiles/aprobados/", disabled=not revisor, key="aprobar_generado"):
                pendiente = PENDIENTES / nombre_archivo
                if not pendiente.exists():
                    PENDIENTES.mkdir(parents=True, exist_ok=True)
                    pendiente.write_text(texto, encoding="utf-8")
                destino = aprobar_archivo(pendiente, APROBADOS, revisor, notas)
                st.success(f"Aprobado: `perfiles/aprobados/{destino.name}`. Commitealo para que quede versionado.")

# ---------------------------------------------------------------- Comparar
elif vista == VISTAS[1]:
    asegurar_datos_maestro(escenario)
    # Perfiles disponibles para comparar: los aprobados siempre; los pendientes
    # solo en la máquina local; el recién generado si está en st.session_state;
    # y, como última opción, subir un .json.
    opciones = {f"Aprobado · {p.name}": p for p in perfiles_en(APROBADOS)}
    if es_local():
        opciones.update({f"Pendiente · {p.name}": p for p in perfiles_en(PENDIENTES)})
    if st.session_state.get("perfil_generado"):
        opciones["Recién generado (sin guardar)"] = None
    col1, col2 = st.columns([2, 2])
    with col1:
        eleccion = st.selectbox("Perfil de la fuente", list(opciones) + ["Subir un perfil (.json)"], key="perfil_elegido")
    perfil_real = None
    if eleccion == "Subir un perfil (.json)":
        with col2:
            subido = st.file_uploader("Perfil generado con el perfilador", type=["json"], key="perfil_subido")
        if subido:
            perfil_real = json.loads(subido.getvalue().decode("utf-8"))
    elif eleccion == "Recién generado (sin guardar)":
        perfil_real = st.session_state["perfil_generado"]
    elif eleccion:
        perfil_real = json.loads(opciones[eleccion].read_text(encoding="utf-8"))

    # Si todavía no hay perfil, o el archivo subido no tiene la forma de un perfil,
    # se avisa y st.stop() corta la página hasta que se elija uno válido.
    if not perfil_real:
        st.info("Elegí o subí un perfil para compararlo con los datos sintéticos del escenario "
                f"**{NOMBRES_ESCENARIO[escenario]}**.")
        st.stop()
    if "tablas" not in perfil_real or "perfilador_version" not in perfil_real:
        st.error("❌ El archivo no es un perfil generado por el perfilador.")
        st.stop()
    revision = perfil_real.get("revision", {})
    if not revision.get("revisado"):
        st.warning("⚠️ Este perfil todavía no fue revisado ni aprobado.")
    else:
        st.caption(f"Aprobado por {revision.get('responsable')} el {revision.get('fecha')}.")

    # Fecha de modificación de metadata.json (0 si no existe), usada como marca
    # de la versión de los datos sintéticos; ver el docstring de perfil_sintetico.
    marca = (directorio(escenario) / "metadata.json").stat().st_mtime if (directorio(escenario) / "metadata.json").exists() else 0
    sintetico = perfil_sintetico(escenario, marca)
    # Emparejamiento: qué tabla sintética equivale a cada tabla de la fuente. Se
    # propone uno automático y se muestra un selector por tabla (en tres columnas)
    # para corregirlo. La key de cada selector lleva el nombre de la tabla para
    # que cada uno recuerde su propia elección.
    sugerido = sugerir_emparejamiento(perfil_real, sintetico)
    st.markdown("### Qué tabla sintética corresponde a cada tabla de la fuente")
    st.caption("Sugerido por los nombres de columna en común; se puede corregir.")
    opciones_sint = [NO_MODELADA] + list(sintetico["tablas"])
    emparejamiento = {}
    columnas = st.columns(3)
    for i, tabla_real in enumerate(perfil_real["tablas"]):
        with columnas[i % 3]:
            valor = sugerido.get(tabla_real) or NO_MODELADA
            elegido = st.selectbox(tabla_real, opciones_sint, index=opciones_sint.index(valor), key=f"par_{tabla_real}")
            emparejamiento[tabla_real] = None if elegido == NO_MODELADA else elegido

    # Brechas: diferencias entre la fuente y los datos sintéticos, clasificadas por
    # severidad (alta, media, baja). Por defecto se ocultan las bajas. Se pueden
    # descargar como informe legible (.md) o como tabla (.csv).
    brechas = comparar(perfil_real, sintetico, emparejamiento)
    st.markdown("### Brechas")
    conteo = brechas["severidad"].value_counts()
    col1, col2, col3 = st.columns(3)
    col1.metric("Altas", int(conteo.get("alta", 0)))
    col2.metric("Medias", int(conteo.get("media", 0)))
    col3.metric("Bajas", int(conteo.get("baja", 0)))
    niveles = st.multiselect("Severidad", ["alta", "media", "baja"], default=["alta", "media"], key="niveles_brecha")
    st.dataframe(brechas[brechas["severidad"].isin(niveles)], use_container_width=True, hide_index=True)
    informe = informe_markdown(brechas, perfil_real, sintetico)
    col1, col2 = st.columns(2)
    col1.download_button("⬇️ Informe de brechas (.md)", informe, file_name="brechas.md", mime="text/markdown",
                         use_container_width=True, key="descargar_informe")
    col2.download_button("⬇️ Brechas (.csv)", brechas.to_csv(index=False), file_name="brechas.csv", mime="text/csv",
                         use_container_width=True, key="descargar_brechas")
    # Solo en la máquina local y si el perfil vino de una carpeta: el informe se
    # guarda al lado, con el mismo nombre terminado en _brechas.md.
    if es_local() and eleccion.startswith(("Aprobado", "Pendiente")):
        destino = opciones[eleccion].with_name(opciones[eleccion].stem + "_brechas.md")
        if st.button(f"💾 Guardar el informe junto al perfil ({destino.name})", key="guardar_informe"):
            destino.write_text(informe, encoding="utf-8")
            st.success(f"Guardado en `{destino.relative_to(RAIZ)}`.")

    if st.toggle("Ver el perfil de la fuente", key="ver_perfil_fuente"):
        mostrar_perfil(perfil_real)

# ---------------------------------------------------------------- Guardados
# Registro de perfiles: los aprobados (quién y cuándo los aprobó) y, en la máquina
# local, los pendientes con la opción de revisarlos y aprobarlos.
else:
    st.markdown("### Aprobados (se versionan en `perfiles/aprobados/`)")
    aprobados = perfiles_en(APROBADOS)
    if not aprobados:
        st.info("Todavía no hay perfiles aprobados.")
    else:
        filas = []
        for ruta in aprobados:
            p = json.loads(ruta.read_text(encoding="utf-8"))
            filas.append({"Archivo": ruta.name, "Origen": p.get("origen"), "Generado": p.get("generado"),
                          "Aprobó": p.get("revision", {}).get("responsable"), "Fecha": p.get("revision", {}).get("fecha"),
                          "Tablas": len(p.get("tablas", {})), "Notas": p.get("revision", {}).get("notas")})
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    if es_local():
        st.markdown("### Pendientes de revisión (`perfiles/pendientes/`, no se versionan)")
        pendientes = perfiles_en(PENDIENTES)
        if not pendientes:
            st.info("No hay perfiles pendientes.")
        else:
            ruta = st.selectbox("Perfil", pendientes, format_func=lambda p: p.name, key="pendiente_elegido")
            perfil = json.loads(ruta.read_text(encoding="utf-8"))
            mostrar_perfil(perfil)
            with st.expander("Ver el JSON completo"):
                st.json(perfil)
            st.markdown("**Aprobar** después de revisar que no contenga nombres, identificadores ni valores sensibles:")
            col1, col2 = st.columns(2)
            responsable = col1.text_input("Responsable de la revisión", key="responsable")
            notas = col2.text_input("Notas (opcional)", key="notas_revision")
            if st.button("✅ Aprobar y mover a perfiles/aprobados/", disabled=not responsable, key="aprobar"):
                aprobar_archivo(ruta, APROBADOS, responsable, notas)
                st.success(f"Aprobado: `perfiles/aprobados/{ruta.name}`. Commitealo para que quede versionado.")
    else:
        st.caption("Los perfiles pendientes solo se ven con la app corriendo en la máquina local.")
