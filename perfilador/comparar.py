"""Brechas entre el perfil de una fuente real y el de los datos sintéticos.

Ambos perfiles se arman con el mismo perfilador, así que se comparan las mismas medidas.
Cada brecha trae una sugerencia concreta para el generador o el análisis.

Para qué sirve este archivo
---------------------------
El proyecto fabrica datos sintéticos (inventados) de una flota. Para saber si se parecen a
los de una fuente real, se compara el perfil agregado de esa fuente (hecho con `perfil.py`)
con el perfil de los datos sintéticos. Cada diferencia importante es una "brecha": algo que
la fuente real tiene y el generador no reproduce (una columna, un formato, una tasa de
vacíos, un defecto de calidad...). La salida es una tabla de brechas, cada una con su
severidad (alta, media o baja) y una sugerencia de qué cambiar.

Cómo encaja con los demás
-------------------------
- Usa `perfil.py` para perfilar los CSV sintéticos (`perfil_de_directorio`).
- `__main__.py` (subcomando `comparar`) y la página "Perfil de fuentes" de la app llaman a
  `sugerir_emparejamiento`, `comparar` e `informe_markdown`.

Recorrido: primero se "empareja" cada tabla real con la sintética que le corresponde, y
dentro de cada par, cada columna real con su columna sintética; después se compara cada par.
"""
import difflib
from pathlib import Path

import pandas as pd

from perfilador.perfil import OTRA, leer_tablas, perfilar

# Orden de las severidades para ordenar la tabla (primero las altas)
SEVERIDAD = {"alta": 0, "media": 1, "baja": 2}
COLUMNAS_BRECHA = ["severidad", "tabla_real", "tabla_sintetica", "columna", "aspecto", "real", "sintetico",
                   "sugerencia"]
# Umbrales: diferencias más chicas que estas no se consideran brechas. "PP" significa puntos
# porcentuales: pasar de 3% a 5% de vacíos es una diferencia de 2 puntos porcentuales.
UMBRAL_FALTANTES_PP = 2.0
UMBRAL_DUPLICADOS_PP = 0.5
UMBRAL_FORMATO_PCT = 5.0
UMBRAL_CALIDAD_PCT = 1.0
UMBRAL_VINCULACION_PP = 2.0

# Defectos de calidad que mide el perfilador, con una descripción legible para el informe
DEFECTOS_DE_CALIDAD = {
    "espacios_extra_pct": "espacios al inicio, al final o dobles",
    "vacios_textuales_pct": "vacíos escritos como texto (\"-\", \"S/D\", \"N/A\")",
    "mayusculas_mixtas_pct": "mayúsculas y minúsculas mezcladas",
    "numeros_como_texto_pct": "números guardados como texto",
}


def perfil_de_directorio(directorio, origen="sintético"):
    """Perfil de todos los CSV de una carpeta (por ejemplo, un escenario generado).

    Recibe la carpeta y un texto que describe el origen. Lee cada CSV con `leer_tablas` y
    devuelve el perfil completo que arma `perfilar`, igual al que se haría de una fuente real.
    """
    tablas = {}
    for archivo in sorted(Path(directorio).glob("*.csv")):
        tablas.update(leer_tablas(archivo, archivo.name))
    return perfilar(tablas, origen=origen)


def _nombres(tabla):
    """Devuelve el conjunto de nombres normalizados de las columnas de una tabla perfilada."""
    return {c["nombre_normalizado"] for c in tabla["perfil_columnas"]}


def sugerir_emparejamiento(perfil_real, perfil_sintetico, minimo=0.2):
    """Para cada tabla real, la tabla sintética con más nombres de columna en común (Jaccard).

    "Emparejar" es decidir qué tabla sintética corresponde a cada tabla real (por ejemplo,
    que la hoja "cargas" de la fuente real equivale a "consumo.csv"). Recibe los dos perfiles
    y un parecido mínimo; devuelve {tabla real: tabla sintética, o None si ninguna se parece
    lo suficiente}. Es una sugerencia: en la app la persona puede corregirla.
    """
    sugerencias = {}
    for nombre_real, tabla_real in perfil_real["tablas"].items():
        mejor, puntaje = None, 0.0
        for nombre_sint, tabla_sint in perfil_sintetico["tablas"].items():
            a, b = _nombres(tabla_real), _nombres(tabla_sint)
            # Índice de Jaccard: columnas en común dividido columnas en total (entre 0 y 1).
            # & es la intersección (lo común) y | la unión (todo junto) de los conjuntos.
            similitud = len(a & b) / len(a | b) if a | b else 0
            if similitud > puntaje:
                mejor, puntaje = nombre_sint, similitud
        sugerencias[nombre_real] = mejor if puntaje >= minimo else None
    return sugerencias


def emparejar_columnas(columnas_real, columnas_sint):
    """Columna real -> columna sintética: mismo nombre normalizado o uno muy parecido.

    Recibe las listas de perfiles de columna de una tabla real y de su tabla sintética.
    Devuelve {nombre de la columna real: perfil de la columna sintética}. Las columnas reales
    que no encuentran pareja no aparecen (se informan como "columna no modelada").
    """
    por_nombre = {c["nombre_normalizado"]: c for c in columnas_sint}
    pares = {}
    for columna in columnas_real:
        nombre = columna["nombre_normalizado"]
        if nombre in por_nombre:
            pares[columna["nombre"]] = por_nombre[nombre]
            continue
        # difflib busca el nombre más parecido; cutoff=0.8 exige un 80% de parecido
        # (acepta "fecha carga" contra "fecha cargas", pero no nombres muy distintos)
        parecido = difflib.get_close_matches(nombre, list(por_nombre), n=1, cutoff=0.8)
        if parecido:
            pares[columna["nombre"]] = por_nombre[parecido[0]]
    return pares


def _brecha(filas, severidad, tabla_real, tabla_sint, columna, aspecto, real, sintetico, sugerencia):
    """Agrega una brecha (un renglón) a la lista `filas`.

    Recibe la lista donde se acumulan las brechas y los datos del renglón: severidad, tablas,
    columna, qué aspecto difiere, el valor real, el sintético y la sugerencia. Los datos que
    faltan se muestran como "—". No devuelve nada: modifica la lista recibida.
    """
    filas.append({"severidad": severidad, "tabla_real": tabla_real, "tabla_sintetica": tabla_sint or "—",
                  "columna": columna or "—", "aspecto": aspecto, "real": real, "sintetico": sintetico,
                  "sugerencia": sugerencia})


def _formatos_relevantes(columna):
    """Formatos de una columna que pesan lo suficiente como para exigir que el generador los tenga.

    Recibe el perfil de una columna y devuelve {formato: porcentaje} solo con los formatos que
    aparecen en al menos UMBRAL_FORMATO_PCT (5%) de los valores, sin contar el grupo "otra".
    """
    return {f["formato"]: f["pct"] for f in columna.get("formatos", [])
            if f["formato"] != OTRA and f["pct"] >= UMBRAL_FORMATO_PCT}


def _comparar_columna(filas, tabla_real, tabla_sint, real, sint):
    """Compara una columna real con su pareja sintética y anota las brechas encontradas.

    Recibe la lista donde acumular brechas, los nombres de ambas tablas y los perfiles de las
    dos columnas. Revisa, en orden: tipo, porcentaje de faltantes, formatos, defectos de
    calidad, cardinalidad, escala de los números (mediana) y categorías. No devuelve nada.
    """
    nombre = real["nombre"]
    # Tipo distinto (salvo que alguno sea "desconocido" por tener pocos datos)
    if real.get("tipo") and sint.get("tipo") and real["tipo"] != sint["tipo"] and "desconocido" not in (
            real["tipo"], sint["tipo"]):
        _brecha(filas, "media", tabla_real, tabla_sint, nombre, "tipo", real["tipo"], sint["tipo"],
                f"En la fuente real es {real['tipo']}; generar la columna con ese tipo o normalizarla en la limpieza.")
    # `or 0` reemplaza un dato ausente por cero para poder restar
    faltantes_r, faltantes_s = real.get("faltantes_pct") or 0, sint.get("faltantes_pct") or 0
    if abs(faltantes_r - faltantes_s) >= UMBRAL_FALTANTES_PP:
        _brecha(filas, "media", tabla_real, tabla_sint, nombre, "faltantes", f"{faltantes_r}%", f"{faltantes_s}%",
                f"Ajustar la tasa de vacíos de {nombre} a cerca de {faltantes_r}%.")
    # Formatos frecuentes en la fuente real que el generador nunca produce
    formatos_r, formatos_s = _formatos_relevantes(real), {f["formato"] for f in sint.get("formatos", [])}
    for forma, porcentaje in formatos_r.items():
        if forma not in formatos_s:
            _brecha(filas, "media", tabla_real, tabla_sint, nombre, "formato", f"{forma} ({porcentaje}%)", "no se genera",
                    f"Agregar el formato {forma} a {nombre} (aparece en el {porcentaje}% de la fuente real).")
    # Defectos de calidad: brecha si en la fuente real son apreciables y el sintético tiene menos de la mitad
    for clave, descripcion in DEFECTOS_DE_CALIDAD.items():
        valor_r = (real.get("calidad") or {}).get(clave) or 0
        valor_s = (sint.get("calidad") or {}).get(clave) or 0
        if clave == "numeros_como_texto_pct" and real.get("tipo") == "número como texto":
            continue  # ya informado como diferencia de tipo
        if valor_r >= UMBRAL_CALIDAD_PCT and valor_s < valor_r / 2:
            _brecha(filas, "media", tabla_real, tabla_sint, nombre, "calidad", f"{descripcion}: {valor_r}%",
                    f"{valor_s}%", f"Inyectar {descripcion} en {nombre} (~{valor_r}%) y registrarlo en el ground truth.")
    # La cardinalidad se compara por banda: solo hay brecha si caen en bandas distintas
    if real.get("cardinalidad") != sint.get("cardinalidad"):
        _brecha(filas, "baja", tabla_real, tabla_sint, nombre, "cardinalidad", real.get("cardinalidad"),
                sint.get("cardinalidad"), "Revisar la cantidad de valores distintos que produce el generador.")
    # Escala: si una mediana es más del doble o menos de la mitad de la otra, los números están en otro rango
    num_r, num_s = real.get("numerico"), sint.get("numerico")
    if num_r and num_s and num_r.get("p50") and num_s.get("p50"):
        proporcion = num_r["p50"] / num_s["p50"]
        if not 0.5 <= proporcion <= 2:
            _brecha(filas, "media", tabla_real, tabla_sint, nombre, "escala (mediana)", num_r["p50"], num_s["p50"],
                    f"La mediana real es {proporcion:.1f} veces la sintética: revisar el rango que se genera.")
    # Categorías de la fuente real (con al menos 20 casos) que el generador no incluye
    if real.get("categorias") and sint.get("categorias"):
        sinteticas = {c["valor"] for c in sint["categorias"]}
        for categoria in real["categorias"]:
            if categoria["valor"] != OTRA and categoria["valor"] not in sinteticas:
                _brecha(filas, "baja", tabla_real, tabla_sint, nombre, "categoría",
                        f"{categoria['valor']} ({categoria['pct']}%)", "no se genera",
                        f"Agregar la categoría {categoria['valor']} al catálogo de {nombre}.")


def comparar(perfil_real, perfil_sintetico, emparejamiento):
    """Tabla de brechas, de mayor a menor severidad. `emparejamiento`: {tabla real: tabla sintética o None}.

    Es la función principal del archivo. Recibe los dos perfiles y el emparejamiento de tablas
    (normalmente el que devuelve `sugerir_emparejamiento`). Devuelve un DataFrame (una tabla de
    pandas) con una fila por brecha y las columnas de COLUMNAS_BRECHA. Revisa, por cada tabla:
    si tiene pareja, los duplicados, cada columna real (con o sin pareja), las columnas que
    solo existen en el sintético y, al final, las relaciones entre tablas.
    """
    filas = []
    for tabla_real, datos_real in perfil_real["tablas"].items():
        tabla_sint = emparejamiento.get(tabla_real)
        # Tabla real sin equivalente sintético: brecha alta, porque falta modelar una fuente entera
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
                # Para describir la columna faltante se usan su tipo y sus dos formatos principales
                descripcion = columna.get("tipo", "?")
                formatos = ", ".join(f["formato"] for f in columna.get("formatos", [])[:2] if f["formato"] != OTRA)
                _brecha(filas, "alta", tabla_real, tabla_sint, columna["nombre"], "columna no modelada",
                        f"{descripcion}{' · ' + formatos if formatos else ''}", "—",
                        "Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa.")
            else:
                _comparar_columna(filas, tabla_real, tabla_sint, columna, pares[columna["nombre"]])
        # Columnas sintéticas que ninguna columna real usó como pareja
        usadas = {c["nombre"] for c in pares.values()}
        for columna in datos_sint["perfil_columnas"]:
            if columna["nombre"] not in usadas:
                _brecha(filas, "baja", tabla_real, tabla_sint, columna["nombre"], "columna solo sintética", "—",
                        columna.get("tipo", "?"), "La fuente real no la tiene con ese nombre: revisar si se llama distinto.")
    filas += _comparar_relaciones(perfil_real, perfil_sintetico, emparejamiento)
    brechas = pd.DataFrame(filas, columns=COLUMNAS_BRECHA)
    # Se ordena por severidad (alta, media, baja); kind="stable" mantiene el orden original dentro de cada severidad
    return brechas.sort_values("severidad", key=lambda s: s.map(SEVERIDAD), kind="stable").reset_index(drop=True)


def _comparar_relaciones(perfil_real, perfil_sintetico, emparejamiento):
    """Vinculación entre tablas: cobertura real vs. sintética y mejora al normalizar.

    Recibe los dos perfiles y el emparejamiento de tablas. Devuelve una lista de brechas
    (renglones) sobre las relaciones entre tablas:
    - si en la fuente real limpiar la clave mejora mucho el cruce (lo que estudia la
      hipótesis H1 del proyecto), para que el generador reproduzca esos defectos;
    - si una relación real no existe en el sintético;
    - si existe pero con una cobertura muy distinta.
    """
    filas = []
    # Relaciones sintéticas indexadas por (origen, destino) para buscarlas rápido
    sinteticas = {(r["origen"], r["destino"]): r for r in perfil_sintetico.get("relaciones", [])}
    # Traducción de "tabla_real.columna" a "tabla_sintetica.columna", usando los emparejamientos
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
        # Si normalizar sube la cobertura, la fuente real tiene claves "sucias" que el generador debe imitar
        if normalizada - exacta >= UMBRAL_VINCULACION_PP:
            _brecha(filas, "alta", tabla_real, emparejamiento.get(tabla_real), f"{origen} → {destino}",
                    "vinculación (H1)", f"{exacta}% exacta, {normalizada}% normalizada", "—",
                    f"Normalizar la clave sube la vinculación {normalizada - exacta:.1f} puntos: inyectar esos defectos "
                    "de formato (espacios, guiones, minúsculas) y medir la mejora en H1.")
        # Si alguna de las dos columnas no tiene pareja sintética, no hay con qué comparar la relación
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
    """Informe de brechas en markdown, para descargar o versionar junto al perfil.

    Markdown es un formato de texto simple que se ve como documento con títulos y tablas
    (GitHub y la app lo muestran así). Recibe la tabla de brechas que devuelve `comparar` y
    los dos perfiles (para el encabezado). Devuelve el informe como un único texto: un resumen
    con el origen, la fecha, si fue revisado y cuántas brechas hay, y la tabla de brechas.
    """
    conteo = brechas["severidad"].value_counts()
    lineas = [
        "# Brechas entre la fuente real y el generador", "",
        f"- Perfil real: origen **{perfil_real.get('origen')}**, generado {perfil_real.get('generado')}, "
        f"revisado: {'sí' if perfil_real.get('revision', {}).get('revisado') else 'no'}.",
        f"- Perfil sintético: **{perfil_sintetico.get('origen')}**.",
        f"- Brechas: {conteo.get('alta', 0)} altas, {conteo.get('media', 0)} medias, {conteo.get('baja', 0)} bajas.",
        "", "| Severidad | Tabla real | Columna | Aspecto | Real | Sintético | Sugerencia |", "|---|---|---|---|---|---|---|",
    ]
    # Una línea de tabla markdown por brecha
    for b in brechas.itertuples():
        lineas.append(f"| {b.severidad} | {b.tabla_real} | {b.columna} | {b.aspecto} | {b.real} | {b.sintetico} | "
                      f"{b.sugerencia} |")
    return "\n".join(lineas) + "\n"
