"""Perfil agregado de una fuente de datos: estructura y calidad, nunca filas ni valores sueltos.

Sigue las reglas de docs/REAL_DATA_BOUNDARY.md:
- Conteos en bandas o redondeados, porcentajes con un decimal, cuantiles con dos cifras
  significativas; nunca mínimos ni máximos.
- Ningún grupo con menos de MINIMO_GRUPO observaciones: las categorías y formatos
  infrecuentes se agrupan como OTRA_CATEGORIA_SINTETIZABLE.
- Las columnas sensibles (identificadores, personas, vehículos, ubicaciones, texto libre)
  se describen solo por su formato: sin valores, cuantiles ni categorías.
- Fechas agregadas por mes.
- Los errores se registran por tipo, sin el mensaje (podría incluir un valor).

El archivo se procesa en memoria y no se escribe nada salvo el perfil que se decida guardar.
"""
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "1.0"
MINIMO_GRUPO = 20
MAX_CATEGORIAS = 50
LARGO_TEXTO_LIBRE = 30          # formatos más largos se consideran texto libre
MAX_FORMATOS_DISTINTOS = 40     # más formatos distintos que esto también indica texto libre
OTRA = "OTRA_CATEGORIA_SINTETIZABLE"

# Pistas en el nombre de la columna -> tipo de dato sensible
PISTAS_SENSIBLES = {
    "identificador": ["id", "codigo", "cod", "numero", "nro", "num", "imei", "matricula", "chasis", "motor",
                      "tarjeta", "msisdn", "ticket", "serie", "cuenta", "cbu", "legajo"],
    "persona": ["nombre", "nombres", "apellido", "apellidos", "conductor", "chofer", "responsable", "dni",
                "cuit", "cuil", "email", "mail", "correo", "telefono", "celular", "usuario", "firma"],
    "vehiculo": ["dominio", "patente", "placa"],
    "ubicacion": ["lat", "lon", "lng", "latitud", "longitud", "direccion", "domicilio", "calle", "coordenada",
                  "coordenadas", "ubicacion", "geo"],
    "texto libre": ["observacion", "observaciones", "comentario", "comentarios", "descripcion", "detalle",
                    "nota", "notas", "motivo", "glosa", "leyenda"],
}
# Formatos de patentes argentinas (histórico y Mercosur)
FORMATOS_PATENTE = {"AAA999", "AAA 999", "AA999AA", "AA 999 AA"}
VACIOS_TEXTUALES = {"", "-", "--", "S/D", "SD", "N/A", "NA", "NULL", "NONE", "SIN DATO", "SIN DATOS", "."}


# ============================================================================
# Utilidades de redondeo y bandas
# ============================================================================

def pct(parte, total):
    return round(100 * parte / total, 1) if total else None


def dos_cifras(valor):
    """Redondea a dos cifras significativas (123456 -> 120000; 0.0347 -> 0.035)."""
    if valor is None or not np.isfinite(valor) or valor == 0:
        return 0 if valor == 0 else None
    return float(round(valor, -int(math.floor(math.log10(abs(valor)))) + 1))


def banda(n):
    if n < MINIMO_GRUPO:
        return f"<{MINIMO_GRUPO}"
    for limite in [100, 1_000, 10_000, 100_000, 1_000_000]:
        if n < limite:
            inferior = MINIMO_GRUPO if limite == 100 else limite // 10
            return f"{inferior:,}–{limite - 1:,}".replace(",", ".")
    return "≥1.000.000"


def banda_cardinalidad(n):
    for limite, etiqueta in [(1, "1"), (10, "2–10"), (100, "11–100"), (1_000, "101–1.000"), (10_000, "1.001–10.000")]:
        if n <= limite:
            return etiqueta
    return ">10.000"


# ============================================================================
# Nombres, formatos y sensibilidad
# ============================================================================

def normalizar_nombre(nombre):
    """"Fecha_Carga" y "fechaCarga" -> "fecha carga": minúsculas, sin acentos, palabras separadas."""
    texto = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(nombre))
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(re.split(r"[^a-z0-9]+", texto.lower())).strip()


def formato(valor):
    """Forma de un valor sin su contenido: letras -> A, dígitos -> 9, el resto se conserva."""
    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]", "A", texto))


def sensibilidad_por_nombre(nombre):
    palabras = normalizar_nombre(nombre).split()
    for tipo, pistas in PISTAS_SENSIBLES.items():
        for palabra in palabras:
            if palabra in pistas or any(len(p) > 3 and palabra.startswith(p) for p in pistas):
                return tipo
    return None


def _es_fecha(formato_valor):
    return bool(re.fullmatch(r"9{1,4}[-/.]9{1,2}[-/.]9{1,4}([ T]9{1,2}:9{2}(:9{2})?(\.9+)?)?", formato_valor))


# ============================================================================
# Perfil de una columna
# ============================================================================

def _formatos(serie_texto, total):
    conteo = serie_texto.map(formato).value_counts()
    visibles = conteo[conteo >= MINIMO_GRUPO]
    resto = int(conteo[conteo < MINIMO_GRUPO].sum())
    formatos = [{"formato": f, "pct": pct(int(n), total)} for f, n in visibles.head(10).items()]
    resto += int(visibles.iloc[10:].sum())
    if resto:
        formatos.append({"formato": OTRA, "pct": pct(resto, total)})
    return formatos, conteo


def _numerico(serie):
    valores = serie.astype(float)
    cuantiles = valores.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "p05": dos_cifras(cuantiles[0.05]), "p25": dos_cifras(cuantiles[0.25]), "p50": dos_cifras(cuantiles[0.5]),
        "p75": dos_cifras(cuantiles[0.75]), "p95": dos_cifras(cuantiles[0.95]),
        "ceros_pct": pct(int((valores == 0).sum()), len(valores)),
        "negativos_pct": pct(int((valores < 0).sum()), len(valores)),
        "enteros_pct": pct(int((valores == valores.round()).sum()), len(valores)),
    }


def _fechas(serie_fecha):
    meses = serie_fecha.dt.to_period("M").astype(str).value_counts().sort_index()
    visibles = {mes: int(round(n, -1)) for mes, n in meses.items() if n >= MINIMO_GRUPO}
    return {
        "meses_con_datos": int(len(meses)),
        "por_mes": visibles,
        "meses_suprimidos": int((meses < MINIMO_GRUPO).sum()),
        "dia_semana_pct": {d: pct(int(n), len(serie_fecha)) for d, n in
                           serie_fecha.dt.day_name().value_counts().items() if n >= MINIMO_GRUPO},
    }


def _categorias(serie):
    conteo = serie.astype(str).str.strip().value_counts()
    total = int(conteo.sum())
    visibles = conteo[conteo >= MINIMO_GRUPO]
    categorias = [{"valor": v, "pct": pct(int(n), total)} for v, n in visibles.items()]
    resto = int(conteo[conteo < MINIMO_GRUPO].sum())
    if resto:
        categorias.append({"valor": OTRA, "pct": pct(resto, total)})
    return categorias


def _calidad_texto(serie_texto):
    total = len(serie_texto)
    return {
        "espacios_extra_pct": pct(int((serie_texto != serie_texto.str.strip()).sum()
                                      + serie_texto.str.contains(r"\s{2,}", regex=True).sum()), total),
        "vacios_textuales_pct": pct(int(serie_texto.str.strip().str.upper().isin(VACIOS_TEXTUALES).sum()), total),
        "mayusculas_mixtas_pct": pct(int((serie_texto.str.contains(r"[a-z]", regex=True)
                                          & serie_texto.str.contains(r"[A-Z]", regex=True)).sum()), total),
        "numeros_como_texto_pct": pct(int(pd.to_numeric(serie_texto.str.replace(",", ".", regex=False),
                                                        errors="coerce").notna().sum()), total),
    }


def perfilar_columna(nombre, serie):
    """Perfil agregado de una columna. Nunca incluye valores de columnas sensibles."""
    total = len(serie)
    presentes = serie.dropna()
    if pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie):
        texto_limpio = presentes.astype(str)
        presentes = presentes[~texto_limpio.str.strip().str.upper().isin({"", "NAN"})]
    n = len(presentes)
    perfil = {
        "nombre": str(nombre),
        "nombre_normalizado": normalizar_nombre(nombre),
        "faltantes_pct": pct(total - n, total),
        "cardinalidad": banda_cardinalidad(int(presentes.nunique())) if n else "0",
        "unicos_pct": pct(int(presentes.nunique()), n) if n else None,
        "sensible": sensibilidad_por_nombre(nombre),
    }
    if n < MINIMO_GRUPO:
        perfil["tipo"] = "desconocido"
        perfil["nota"] = f"menos de {MINIMO_GRUPO} valores: sin estadísticas"
        return perfil

    if pd.api.types.is_bool_dtype(serie):
        perfil["tipo"] = "booleano"
        perfil["verdaderos_pct"] = pct(int(presentes.astype(bool).sum()), n)
        return perfil

    if pd.api.types.is_datetime64_any_dtype(serie):
        perfil["tipo"] = "fecha"
        perfil["fechas"] = _fechas(pd.to_datetime(presentes))
        perfil["con_hora_pct"] = pct(int((pd.to_datetime(presentes).dt.time.astype(str) != "00:00:00").sum()), n)
        return perfil

    if pd.api.types.is_numeric_dtype(serie):
        valores = presentes.astype(float)
        perfil["tipo"] = "entero" if (valores == valores.round()).all() else "decimal"
        como_texto = valores.astype("int64").astype(str) if perfil["tipo"] == "entero" else presentes.astype(str)
        perfil["formatos"], _ = _formatos(como_texto, n)
        if not perfil["sensible"] and perfil["tipo"] == "decimal" and valores.between(-90, 90).all() \
                and presentes.astype(str).str.split(".").str[-1].str.len().median() >= 4:
            perfil["sensible"] = "ubicacion"
        # Enteros largos (IMEI, líneas, cuentas) son identificadores aunque el nombre no lo diga
        if not perfil["sensible"] and perfil["tipo"] == "entero" and como_texto.str.len().median() >= 11:
            perfil["sensible"] = "identificador"
        if not perfil["sensible"]:
            perfil["numerico"] = _numerico(presentes)
        return perfil

    # Texto (o mezcla): tipo según sus formatos
    texto = presentes.astype(str)
    perfil["formatos"], conteo = _formatos(texto, n)
    principal = conteo.index[0]
    perfil["largo"] = {k: int(v) for k, v in texto.str.len().quantile([0.1, 0.5, 0.9]).round()
                       .rename({0.1: "p10", 0.5: "p50", 0.9: "p90"}).items()}
    perfil["calidad"] = _calidad_texto(texto)
    fecha_pct = conteo[[f for f in conteo.index if _es_fecha(f)]].sum() / n
    if fecha_pct >= 0.9:
        perfil["tipo"] = "fecha como texto"
        fechas = pd.to_datetime(texto, errors="coerce", dayfirst=not principal.startswith("9999"))
        perfil["fechas_invalidas_pct"] = pct(int(fechas.isna().sum()), n)
        perfil["fechas"] = _fechas(fechas.dropna()) if fechas.notna().sum() >= MINIMO_GRUPO else None
        return perfil
    if perfil["calidad"]["numeros_como_texto_pct"] >= 90:
        perfil["tipo"] = "número como texto"
    else:
        perfil["tipo"] = "texto"

    libre = len(principal) > LARGO_TEXTO_LIBRE or len(conteo) > MAX_FORMATOS_DISTINTOS
    if not perfil["sensible"] and conteo.index.isin(FORMATOS_PATENTE)[:3].any():
        perfil["sensible"] = "vehiculo"
    if not perfil["sensible"] and libre and (perfil["unicos_pct"] or 0) > 50:
        perfil["sensible"] = "texto libre"
    if not perfil["sensible"] and (perfil["unicos_pct"] or 0) > 95 and presentes.nunique() > MAX_CATEGORIAS:
        perfil["sensible"] = "identificador"
    if not perfil["sensible"] and presentes.nunique() <= MAX_CATEGORIAS:
        perfil["categorias"] = _categorias(presentes)
    return perfil


# ============================================================================
# Perfil de tablas, relaciones y fuentes
# ============================================================================

def _normalizar_valor(valor):
    return re.sub(r"[\s\-_.]", "", str(valor).strip().upper())


def perfilar_tabla(nombre, df):
    columnas = []
    for columna in df.columns:
        try:
            columnas.append(perfilar_columna(columna, df[columna]))
        except Exception as error:  # noqa: BLE001 - no se registra el mensaje: podría incluir un valor
            columnas.append({"nombre": str(columna), "nombre_normalizado": normalizar_nombre(columna),
                             "error": type(error).__name__})
    filas = len(df)
    claves = [str(c) for c in df.columns if filas >= MINIMO_GRUPO and df[c].notna().all() and df[c].is_unique]
    return {
        "nombre": nombre,
        "filas": banda(filas),
        "filas_aprox": dos_cifras(filas) if filas >= MINIMO_GRUPO else None,
        "columnas": len(df.columns),
        "filas_duplicadas_pct": pct(int(df.duplicated().sum()), filas) if filas >= MINIMO_GRUPO else None,
        "columnas_candidatas_a_clave": claves,
        "perfil_columnas": columnas,
    }


def relaciones_entre_tablas(tablas, cobertura_minima=0.5):
    """Qué porcentaje de los valores distintos de una columna aparece en otra de otra tabla.

    Se calcula también después de normalizar (mayúsculas, sin espacios ni guiones): la
    diferencia mide cuánto mejora la vinculación con esa limpieza. Solo se guardan porcentajes.
    """
    candidatas = []
    for tabla, df in tablas.items():
        for columna in df.columns:
            valores = df[columna].dropna()
            if len(valores) < MINIMO_GRUPO or pd.api.types.is_float_dtype(valores) or valores.nunique() < 2 \
                    or pd.api.types.is_datetime64_any_dtype(valores):
                continue
            texto = valores.astype(str).str.strip()
            if _es_fecha(formato(texto.iloc[0])):
                continue
            exactos = set(texto)
            es_clave = len(exactos) / len(valores) >= 0.9
            candidatas.append((tabla, str(columna), exactos, {_normalizar_valor(v) for v in exactos}, es_clave))
    relaciones = []
    for tabla_a, col_a, exactos_a, normal_a, _ in candidatas:
        for tabla_b, col_b, exactos_b, normal_b, destino_es_clave in candidatas:
            # Clave foránea -> clave: el destino debe ser (casi) único; con pocos valores distintos en el
            # origen las coincidencias pueden ser casuales
            if tabla_a == tabla_b or len(exactos_a) < 50 or not destino_es_clave:
                continue
            exacta = len(exactos_a & exactos_b) / len(exactos_a)
            normalizada = len(normal_a & normal_b) / len(normal_a)
            if normalizada >= cobertura_minima:
                relaciones.append({"origen": f"{tabla_a}.{col_a}", "destino": f"{tabla_b}.{col_b}",
                                   "cobertura_exacta_pct": round(100 * exacta, 1),
                                   "cobertura_normalizada_pct": round(100 * normalizada, 1)})
    return sorted(relaciones, key=lambda r: -r["cobertura_normalizada_pct"])


def leer_tablas(archivo, nombre):
    """Lee un CSV o un Excel (cada hoja es una tabla) desde una ruta o un archivo en memoria."""
    nombre = str(nombre)
    if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        hojas = pd.read_excel(archivo, sheet_name=None)
        base = re.sub(r"\.\w+$", "", nombre.split("/")[-1].split("\\")[-1])
        return {base if len(hojas) == 1 else f"{base}:{hoja}": df for hoja, df in hojas.items()}
    base = re.sub(r"\.\w+$", "", nombre.split("/")[-1].split("\\")[-1])
    for separador in [",", ";", "\t", "|"]:
        if hasattr(archivo, "seek"):
            archivo.seek(0)
        df = pd.read_csv(archivo, sep=separador, dtype=str, keep_default_na=False, encoding_errors="replace")
        if len(df.columns) > 1:
            break
    # Los CSV se leen como texto para ver sus formatos tal como vienen; después se convierten a
    # número las columnas que lo son (salvo códigos con ceros a la izquierda, que son identificadores)
    df = df.replace({"": np.nan})
    for columna in df.columns:
        valores = df[columna].dropna()
        if valores.empty or valores.str.fullmatch(r"0\d+").any():
            continue
        numeros = pd.to_numeric(valores, errors="coerce")
        if numeros.notna().mean() >= 0.98:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
    return {base: df}


EXTENSIONES = (".csv", ".xlsx", ".xlsm", ".xls")


UUID = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", re.IGNORECASE)
UNION_VERSIONES = 1.1           # unión de claves / archivo más grande hasta la que son versiones


def patron_de_nombre(nombre):
    """Nombre de archivo sin identificadores ni números: `consumo_2025-09-01` -> `consumo_9999-99-99`.

    Un nombre que es solo un identificador (UUID) queda vacío: no dice qué contiene.
    """
    sin_uuid = UUID.sub("", nombre)
    return re.sub(r"\d", "9", sin_uuid).strip(" _-.:()")


def _clave_comun(dfs):
    """Columna presente en todos los archivos y única y completa en la mayoría, o None."""
    comunes = set(dfs[0].columns).intersection(*[set(df.columns) for df in dfs[1:]])
    for columna in dfs[0].columns:
        if columna not in comunes:
            continue
        unica = [len(df) >= MINIMO_GRUPO and df[columna].notna().all() and df[columna].is_unique for df in dfs]
        if sum(unica) > len(dfs) / 2:
            return columna
    return None


def combinar_archivos(partes):
    """Une los archivos de un mismo tipo. `partes` es una lista de (fecha de modificación, DataFrame).

    Devuelve la tabla, el modo y el porcentaje de filas descartadas por repetirse entre archivos.

    - Versiones: cada archivo repite casi los mismos registros (el mismo padrón exportado varias
      veces). Se reconocen porque la unión de las claves apenas supera al archivo más grande;
      se perfila solo el más reciente, para no multiplicar las filas.
    - Lotes: los archivos suman registros (un día, un mes, exportaciones que se superponen). Se
      apilan del más reciente al más antiguo y se descartan los registros cuya clave ya vino en
      un archivo más reciente; los repetidos dentro de un mismo archivo se conservan.
    Sin clave común se usa la fila completa como clave.
    """
    if len(partes) == 1:
        return partes[0][1], "unico", 0.0
    partes = sorted(partes, key=lambda p: p[0], reverse=True)
    dfs = [df for _, df in partes]
    clave = _clave_comun(dfs)
    if clave is not None:
        claves = [df[clave].astype(str).where(df[clave].notna()) for df in dfs]
    else:
        claves = [pd.util.hash_pandas_object(df, index=False).astype(str) for df in dfs]
    union = set().union(*(set(c.dropna()) for c in claves))
    mayor = max(c.nunique() for c in claves)
    if mayor and len(union) / mayor <= UNION_VERSIONES:
        return dfs[0], "versiones", 0.0
    vistas, conservadas, total = set(), [], 0
    for df, c in zip(dfs, claves):
        nuevas = c.isna() | ~c.isin(vistas)
        conservadas.append(df[nuevas.to_numpy()])
        vistas.update(c.dropna())
        total += len(df)
    apiladas = pd.concat(conservadas, ignore_index=True)
    return apiladas, "lotes", pct(total - len(apiladas), total)


def tablas_de_rutas(rutas, renombrar=None):
    """Lee archivos o carpetas (recorridas completas) y agrupa los archivos del mismo tipo.

    Son del mismo tipo los archivos cuyo nombre coincide salvo por números e identificadores
    (uno por día, por mes...); si el nombre es solo un identificador, los que tienen las mismas
    columnas. Cada grupo es una tabla con el patrón como nombre, así el perfil no guarda fechas
    ni otros números de los nombres; `renombrar` ({patrón: nombre}) permite reemplazarlo. Los
    grupos se unen como lotes o versiones (ver `combinar_archivos`).

    Solo lee: no escribe nada junto a los archivos. Devuelve las tablas y un resumen con la
    cantidad de archivos por tabla, cómo se unieron, cuántas filas se descartaron por repetirse
    entre archivos y los que no se pudieron leer, por tipo de error.
    """
    renombrar = renombrar or {}
    archivos = []
    for ruta in map(Path, rutas):
        if ruta.is_dir():
            archivos += sorted(a for a in ruta.rglob("*") if a.is_file() and a.suffix.lower() in EXTENSIONES)
        elif ruta.suffix.lower() in EXTENSIONES:
            archivos.append(ruta)
    grupos, errores = {}, {}
    for archivo in archivos:
        try:
            leidas = leer_tablas(archivo, archivo.name)
        except Exception as error:  # noqa: BLE001 - el mensaje podría incluir un valor
            errores[type(error).__name__] = errores.get(type(error).__name__, 0) + 1
            continue
        for nombre, df in leidas.items():
            patron = patron_de_nombre(nombre)
            clave = patron or ("esquema", tuple(sorted(normalizar_nombre(c) for c in df.columns)))
            grupos.setdefault(clave, []).append((archivo.stat().st_mtime, df))

    tablas, conteo, combinacion, descartadas = {}, {}, {}, {}
    for clave, partes in grupos.items():
        nombre = clave if isinstance(clave, str) else f"tabla_de_{len(clave[1])}_columnas"
        nombre = renombrar.get(nombre, nombre)
        base, n = nombre, 2
        while nombre in tablas:
            nombre, n = f"{base}_{n}", n + 1
        tablas[nombre], combinacion[nombre], descartadas[nombre] = combinar_archivos(partes)
        conteo[nombre] = len(partes)
    return tablas, {"archivos_por_tabla": conteo, "combinacion_por_tabla": combinacion,
                    "filas_repetidas_entre_archivos_pct": descartadas, "no_leidos_por_error": errores}


def perfilar(tablas, origen="fuente"):
    """Perfil completo de un conjunto de tablas {nombre: DataFrame}."""
    return {
        "perfilador_version": VERSION,
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "origen": origen,
        "revision": {"revisado": False, "responsable": None, "fecha": None, "notas": None},
        "reglas": {"minimo_grupo": MINIMO_GRUPO, "max_categorias": MAX_CATEGORIAS},
        "tablas": {nombre: perfilar_tabla(nombre, df) for nombre, df in tablas.items()},
        "relaciones": relaciones_entre_tablas(tablas),
    }
