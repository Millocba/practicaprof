"""Brechas entre el perfil de una fuente real y el de los datos sintéticos.

Ambos perfiles se arman con el mismo perfilador, así que se comparan las mismas medidas.
Cada brecha trae una sugerencia concreta para el generador o el análisis.
"""
import difflib
from pathlib import Path

import pandas as pd

from perfilador.perfil import OTRA, leer_tablas, perfilar

SEVERIDAD = {"alta": 0, "media": 1, "baja": 2}
COLUMNAS_BRECHA = ["severidad", "tabla_real", "tabla_sintetica", "columna", "aspecto", "real", "sintetico",
                   "sugerencia"]
UMBRAL_FALTANTES_PP = 2.0
UMBRAL_DUPLICADOS_PP = 0.5
UMBRAL_FORMATO_PCT = 5.0
UMBRAL_CALIDAD_PCT = 1.0
UMBRAL_VINCULACION_PP = 2.0

DEFECTOS_DE_CALIDAD = {
    "espacios_extra_pct": "espacios al inicio, al final o dobles",
    "vacios_textuales_pct": "vacíos escritos como texto (\"-\", \"S/D\", \"N/A\")",
    "mayusculas_mixtas_pct": "mayúsculas y minúsculas mezcladas",
    "numeros_como_texto_pct": "números guardados como texto",
}


def perfil_de_directorio(directorio, origen="sintético"):
    """Perfil de todos los CSV de una carpeta (por ejemplo, un escenario generado)."""
    tablas = {}
    for archivo in sorted(Path(directorio).glob("*.csv")):
        tablas.update(leer_tablas(archivo, archivo.name))
    return perfilar(tablas, origen=origen)


def _nombres(tabla):
    return {c["nombre_normalizado"] for c in tabla["perfil_columnas"]}


def sugerir_emparejamiento(perfil_real, perfil_sintetico, minimo=0.2):
    """Para cada tabla real, la tabla sintética con más nombres de columna en común (Jaccard)."""
    sugerencias = {}
    for nombre_real, tabla_real in perfil_real["tablas"].items():
        mejor, puntaje = None, 0.0
        for nombre_sint, tabla_sint in perfil_sintetico["tablas"].items():
            a, b = _nombres(tabla_real), _nombres(tabla_sint)
            similitud = len(a & b) / len(a | b) if a | b else 0
            if similitud > puntaje:
                mejor, puntaje = nombre_sint, similitud
        sugerencias[nombre_real] = mejor if puntaje >= minimo else None
    return sugerencias


def emparejar_columnas(columnas_real, columnas_sint):
    """Columna real -> columna sintética: mismo nombre normalizado o uno muy parecido."""
    por_nombre = {c["nombre_normalizado"]: c for c in columnas_sint}
    pares = {}
    for columna in columnas_real:
        nombre = columna["nombre_normalizado"]
        if nombre in por_nombre:
            pares[columna["nombre"]] = por_nombre[nombre]
            continue
        parecido = difflib.get_close_matches(nombre, list(por_nombre), n=1, cutoff=0.8)
        if parecido:
            pares[columna["nombre"]] = por_nombre[parecido[0]]
    return pares


def _brecha(filas, severidad, tabla_real, tabla_sint, columna, aspecto, real, sintetico, sugerencia):
    filas.append({"severidad": severidad, "tabla_real": tabla_real, "tabla_sintetica": tabla_sint or "—",
                  "columna": columna or "—", "aspecto": aspecto, "real": real, "sintetico": sintetico,
                  "sugerencia": sugerencia})


def _formatos_relevantes(columna):
    return {f["formato"]: f["pct"] for f in columna.get("formatos", [])
            if f["formato"] != OTRA and f["pct"] >= UMBRAL_FORMATO_PCT}


def _comparar_columna(filas, tabla_real, tabla_sint, real, sint):
    nombre = real["nombre"]
    if real.get("tipo") and sint.get("tipo") and real["tipo"] != sint["tipo"] and "desconocido" not in (
            real["tipo"], sint["tipo"]):
        _brecha(filas, "media", tabla_real, tabla_sint, nombre, "tipo", real["tipo"], sint["tipo"],
                f"En la fuente real es {real['tipo']}; generar la columna con ese tipo o normalizarla en la limpieza.")
    faltantes_r, faltantes_s = real.get("faltantes_pct") or 0, sint.get("faltantes_pct") or 0
    if abs(faltantes_r - faltantes_s) >= UMBRAL_FALTANTES_PP:
        _brecha(filas, "media", tabla_real, tabla_sint, nombre, "faltantes", f"{faltantes_r}%", f"{faltantes_s}%",
                f"Ajustar la tasa de vacíos de {nombre} a cerca de {faltantes_r}%.")
    formatos_r, formatos_s = _formatos_relevantes(real), {f["formato"] for f in sint.get("formatos", [])}
    for forma, porcentaje in formatos_r.items():
        if forma not in formatos_s:
            _brecha(filas, "media", tabla_real, tabla_sint, nombre, "formato", f"{forma} ({porcentaje}%)", "no se genera",
                    f"Agregar el formato {forma} a {nombre} (aparece en el {porcentaje}% de la fuente real).")
    for clave, descripcion in DEFECTOS_DE_CALIDAD.items():
        valor_r = (real.get("calidad") or {}).get(clave) or 0
        valor_s = (sint.get("calidad") or {}).get(clave) or 0
        if clave == "numeros_como_texto_pct" and real.get("tipo") == "número como texto":
            continue  # ya informado como diferencia de tipo
        if valor_r >= UMBRAL_CALIDAD_PCT and valor_s < valor_r / 2:
            _brecha(filas, "media", tabla_real, tabla_sint, nombre, "calidad", f"{descripcion}: {valor_r}%",
                    f"{valor_s}%", f"Inyectar {descripcion} en {nombre} (~{valor_r}%) y registrarlo en el ground truth.")
    if real.get("cardinalidad") != sint.get("cardinalidad"):
        _brecha(filas, "baja", tabla_real, tabla_sint, nombre, "cardinalidad", real.get("cardinalidad"),
                sint.get("cardinalidad"), "Revisar la cantidad de valores distintos que produce el generador.")
    num_r, num_s = real.get("numerico"), sint.get("numerico")
    if num_r and num_s and num_r.get("p50") and num_s.get("p50"):
        proporcion = num_r["p50"] / num_s["p50"]
        if not 0.5 <= proporcion <= 2:
            _brecha(filas, "media", tabla_real, tabla_sint, nombre, "escala (mediana)", num_r["p50"], num_s["p50"],
                    f"La mediana real es {proporcion:.1f} veces la sintética: revisar el rango que se genera.")
    if real.get("categorias") and sint.get("categorias"):
        sinteticas = {c["valor"] for c in sint["categorias"]}
        for categoria in real["categorias"]:
            if categoria["valor"] != OTRA and categoria["valor"] not in sinteticas:
                _brecha(filas, "baja", tabla_real, tabla_sint, nombre, "categoría",
                        f"{categoria['valor']} ({categoria['pct']}%)", "no se genera",
                        f"Agregar la categoría {categoria['valor']} al catálogo de {nombre}.")


def comparar(perfil_real, perfil_sintetico, emparejamiento):
    """Tabla de brechas, de mayor a menor severidad. `emparejamiento`: {tabla real: tabla sintética o None}."""
    filas = []
    for tabla_real, datos_real in perfil_real["tablas"].items():
        tabla_sint = emparejamiento.get(tabla_real)
        if not tabla_sint:
            _brecha(filas, "alta", tabla_real, None, None, "tabla no modelada", f"{datos_real['columnas']} columnas", "—",
                    "Agregar la tabla al generador o documentar por qué queda fuera del análisis.")
            continue
        datos_sint = perfil_sintetico["tablas"][tabla_sint]
        dup_r, dup_s = datos_real.get("filas_duplicadas_pct") or 0, datos_sint.get("filas_duplicadas_pct") or 0
        if abs(dup_r - dup_s) >= UMBRAL_DUPLICADOS_PP:
            _brecha(filas, "media", tabla_real, tabla_sint, None, "filas duplicadas", f"{dup_r}%", f"{dup_s}%",
                    f"Ajustar la tasa de duplicados a cerca de {dup_r}%.")
        pares = emparejar_columnas(datos_real["perfil_columnas"], datos_sint["perfil_columnas"])
        for columna in datos_real["perfil_columnas"]:
            if columna["nombre"] not in pares:
                descripcion = columna.get("tipo", "?")
                formatos = ", ".join(f["formato"] for f in columna.get("formatos", [])[:2] if f["formato"] != OTRA)
                _brecha(filas, "alta", tabla_real, tabla_sint, columna["nombre"], "columna no modelada",
                        f"{descripcion}{' · ' + formatos if formatos else ''}", "—",
                        "Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa.")
            else:
                _comparar_columna(filas, tabla_real, tabla_sint, columna, pares[columna["nombre"]])
        usadas = {c["nombre"] for c in pares.values()}
        for columna in datos_sint["perfil_columnas"]:
            if columna["nombre"] not in usadas:
                _brecha(filas, "baja", tabla_real, tabla_sint, columna["nombre"], "columna solo sintética", "—",
                        columna.get("tipo", "?"), "La fuente real no la tiene con ese nombre: revisar si se llama distinto.")
    filas += _comparar_relaciones(perfil_real, perfil_sintetico, emparejamiento)
    brechas = pd.DataFrame(filas, columns=COLUMNAS_BRECHA)
    return brechas.sort_values("severidad", key=lambda s: s.map(SEVERIDAD), kind="stable").reset_index(drop=True)


def _comparar_relaciones(perfil_real, perfil_sintetico, emparejamiento):
    """Vinculación entre tablas: cobertura real vs. sintética y mejora al normalizar."""
    filas = []
    sinteticas = {(r["origen"], r["destino"]): r for r in perfil_sintetico.get("relaciones", [])}
    columnas = {}
    for tabla_real, tabla_sint in emparejamiento.items():
        if tabla_sint:
            pares = emparejar_columnas(perfil_real["tablas"][tabla_real]["perfil_columnas"],
                                       perfil_sintetico["tablas"][tabla_sint]["perfil_columnas"])
            columnas.update({f"{tabla_real}.{c}": f"{tabla_sint}.{s['nombre']}" for c, s in pares.items()})
    for relacion in perfil_real.get("relaciones", []):
        exacta, normalizada = relacion["cobertura_exacta_pct"], relacion["cobertura_normalizada_pct"]
        origen, destino = relacion["origen"], relacion["destino"]
        tabla_real = origen.split(".")[0]
        if normalizada - exacta >= UMBRAL_VINCULACION_PP:
            _brecha(filas, "alta", tabla_real, emparejamiento.get(tabla_real), f"{origen} → {destino}",
                    "vinculación (H1)", f"{exacta}% exacta, {normalizada}% normalizada", "—",
                    f"Normalizar la clave sube la vinculación {normalizada - exacta:.1f} puntos: inyectar esos defectos "
                    "de formato (espacios, guiones, minúsculas) y medir la mejora en H1.")
        par = (columnas.get(origen), columnas.get(destino))
        if None in par:
            continue
        sintetica = sinteticas.get(par)
        if sintetica is None:
            _brecha(filas, "media", tabla_real, emparejamiento.get(tabla_real), f"{origen} → {destino}",
                    "relación no modelada", f"{normalizada}%", "—",
                    "La fuente real vincula estas columnas y el generador no: agregar la relación.")
        elif abs(sintetica["cobertura_exacta_pct"] - exacta) >= UMBRAL_VINCULACION_PP:
            _brecha(filas, "media", tabla_real, emparejamiento.get(tabla_real), f"{origen} → {destino}",
                    "cobertura de la relación", f"{exacta}%", f"{sintetica['cobertura_exacta_pct']}%",
                    f"Ajustar la tasa de claves sin vínculo para acercarla al {exacta}%.")
    return filas


def informe_markdown(brechas, perfil_real, perfil_sintetico):
    """Informe de brechas en markdown, para descargar o versionar junto al perfil."""
    conteo = brechas["severidad"].value_counts()
    lineas = [
        "# Brechas entre la fuente real y el generador", "",
        f"- Perfil real: origen **{perfil_real.get('origen')}**, generado {perfil_real.get('generado')}, "
        f"revisado: {'sí' if perfil_real.get('revision', {}).get('revisado') else 'no'}.",
        f"- Perfil sintético: **{perfil_sintetico.get('origen')}**.",
        f"- Brechas: {conteo.get('alta', 0)} altas, {conteo.get('media', 0)} medias, {conteo.get('baja', 0)} bajas.",
        "", "| Severidad | Tabla real | Columna | Aspecto | Real | Sintético | Sugerencia |", "|---|---|---|---|---|---|---|",
    ]
    for b in brechas.itertuples():
        lineas.append(f"| {b.severidad} | {b.tabla_real} | {b.columna} | {b.aspecto} | {b.real} | {b.sintetico} | "
                      f"{b.sugerencia} |")
    return "\n".join(lineas) + "\n"
