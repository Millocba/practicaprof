"""Perfil agregado de una fuente de datos: estructura y calidad, nunca filas ni valores sueltos.

Sigue las reglas de docs/REAL_DATA_BOUNDARY.md:
- Conteos en bandas o redondeados, porcentajes con un decimal, cuantiles con dos cifras
  significativas; nunca mínimos ni máximos.
- Ningún grupo con menos de MINIMO_GRUPO observaciones: las categorías y formatos
  infrecuentes se agrupan como OTRA_CATEGORIA_SINTETIZABLE.
- Las columnas sensibles (identificadores, personas, vehículos, ubicaciones, organizaciones,
  texto libre) se describen solo por su formato: sin valores, cuantiles ni categorías. Los
  formatos largos se resumen por su largo.
- Fechas agregadas por mes.
- Los errores se registran por tipo, sin el mensaje (podría incluir un valor).

El archivo se procesa en memoria y no se escribe nada salvo el perfil que se decida guardar.

Para qué sirve este archivo
---------------------------
Es el corazón del perfilador. Recibe tablas (hojas de Excel o archivos CSV ya leídos) y
devuelve un "perfil agregado": un diccionario con el resumen de cada tabla y de cada
columna. "Agregado" quiere decir que describe al conjunto (porcentajes, rangos, formatos
frecuentes) y nunca a un registro en particular. Así el perfil de una fuente real puede
salir del lugar donde están los datos sin exponer a ninguna persona, vehículo o lugar.

Por qué nunca se guardan mínimos ni máximos: el valor más chico o más grande de una
columna suele corresponder a un único caso (el vehículo que más cargó, la fecha más
antigua...), y publicarlo equivale a publicar un dato de ese caso.

Cómo encaja con los demás
-------------------------
- `__main__.py` (línea de comandos) y la página "Perfil de fuentes" de la app llaman a
  `leer_tablas()` para leer los archivos y a `perfilar()` para armar el perfil.
- `aprobar_archivo()` registra la revisión manual del perfil.
- `comparar.py` usa `perfilar()` también sobre los datos sintéticos, para que ambos perfiles
  se midan exactamente igual y puedan compararse.

Orden de lectura sugerido: `perfilar()` (al final) -> `perfilar_tabla()` ->
`perfilar_columna()` -> las funciones auxiliares que esta usa.
"""
import json
import math
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Parámetros de las reglas de privacidad. Están juntos acá para poder ajustarlos en un solo lugar.
VERSION = "1.1"
# Tamaño mínimo de grupo: ningún dato se publica si describe a menos de 20 casos, porque un
# grupo tan chico podría permitir reconocer a quienes lo forman.
MINIMO_GRUPO = 20
# Una columna con hasta 50 valores distintos se trata como "categórica" (por ejemplo, tipo de
# combustible) y se informan sus categorías; con más, se considera demasiado variada.
MAX_CATEGORIAS = 50
LARGO_TEXTO_LIBRE = 30          # formatos más largos se consideran texto libre
MAX_FORMATOS_DISTINTOS = 40     # más formatos distintos que esto también indica texto libre
LARGO_FORMATO_SENSIBLE = 20     # en columnas sensibles, formatos más largos se resumen por largo
# Etiqueta con la que se agrupan todos los casos infrecuentes (menos de MINIMO_GRUPO)
OTRA = "OTRA_CATEGORIA_SINTETIZABLE"

# Pistas en el nombre de la columna -> tipo de dato sensible
# (Una columna "sensible" es la que puede identificar a alguien o algo concreto. Si el nombre
# de la columna contiene alguna de estas palabras, se la trata con más cuidado: solo se
# informa la forma de sus valores, nunca los valores.)
PISTAS_SENSIBLES = {
    "identificador": ["id", "codigo", "cod", "numero", "nro", "num", "imei", "matricula", "chasis", "motor",
                      "tarjeta", "msisdn", "ticket", "serie", "cuenta", "cbu", "legajo", "extracto", "remito"],
    "persona": ["nombre", "nombres", "apellido", "apellidos", "conductor", "chofer", "responsable", "dni",
                "cuit", "cuil", "email", "mail", "correo", "telefono", "celular", "usuario", "firma",
                "solicitante", "cargador", "retira"],
    "vehiculo": ["dominio", "patente", "placa"],
    "ubicacion": ["lat", "lon", "lng", "latitud", "longitud", "direccion", "domicilio", "calle", "coordenada",
                  "coordenadas", "ubicacion", "geo", "localidad", "provincia"],
    # Nombres de unidades internas, contratos o comercios permiten reconocer a la organización
    "organizacion": ["depend", "contrato", "establecimiento"],
    "texto libre": ["observacion", "observaciones", "comentario", "comentarios", "descripcion", "detalle",
                    "nota", "notas", "motivo", "glosa", "leyenda"],
}
# Formatos de patentes argentinas (histórico, Mercosur y motos Mercosur)
# (Están escritos como "máscaras de formato": A = una letra, 9 = un dígito. Ver `formato()`.)
FORMATOS_PATENTE = {"AAA999", "AAA 999", "AA999AA", "AA 999 AA", "A999AAA"}
# Formas habituales de escribir "no hay dato" como texto; cuentan como un defecto de calidad
VACIOS_TEXTUALES = {"", "-", "--", "S/D", "SD", "N/A", "NA", "NULL", "NONE", "SIN DATO", "SIN DATOS", "."}


# ============================================================================
# Utilidades de redondeo y bandas
# ============================================================================
# Estas funciones "borronean" los números antes de publicarlos: en vez de decir que una tabla
# tiene 4.873 filas, se dice que tiene entre 1.000 y 9.999. Un número exacto puede servir para
# reconocer una fuente o cruzarla con otra; una banda (un rango) no.

def pct(parte, total):
    """Porcentaje de `parte` sobre `total`, redondeado a un decimal.

    Recibe dos números (por ejemplo, 3 vacíos sobre 40 filas) y devuelve 7.5.
    Si el total es cero devuelve None (no hay porcentaje posible) en lugar de fallar.
    Se usa en todo el archivo para informar proporciones en vez de conteos exactos.
    """
    return round(100 * parte / total, 1) if total else None


def dos_cifras(valor):
    """Redondea a dos cifras significativas (123456 -> 120000; 0.0347 -> 0.035).

    Recibe un número y devuelve el número redondeado (o None si no es un número válido,
    como un infinito o un vacío; y 0 si es cero). Sirve para publicar tamaños y cuantiles
    con una precisión suficiente para comparar, pero no tanta como para revelar el valor exacto.
    """
    if valor is None or not np.isfinite(valor) or valor == 0:
        return 0 if valor == 0 else None
    # log10 da la cantidad de dígitos del número (su "orden de magnitud"); con eso se calcula
    # cuántas posiciones redondear para quedarse solo con las dos primeras cifras
    return float(round(valor, -int(math.floor(math.log10(abs(valor)))) + 1))


def banda(n):
    """Convierte una cantidad de filas en una banda (rango) de texto.

    Recibe un número entero (por ejemplo, 4873) y devuelve un texto como "1.000–9.999".
    Por debajo de MINIMO_GRUPO devuelve "<20", sin más detalle. Se usa para informar el
    tamaño de cada tabla sin dar la cifra exacta.
    """
    if n < MINIMO_GRUPO:
        return f"<{MINIMO_GRUPO}"
    # Las bandas crecen de a potencias de 10: 20–99, 100–999, 1.000–9.999, etc.
    for limite in [100, 1_000, 10_000, 100_000, 1_000_000]:
        if n < limite:
            inferior = MINIMO_GRUPO if limite == 100 else limite // 10
            # Se usa el punto como separador de miles, como se escribe en español
            return f"{inferior:,}–{limite - 1:,}".replace(",", ".")
    return "≥1.000.000"


def banda_cardinalidad(n):
    """Convierte una cantidad de valores distintos en una banda de texto.

    La "cardinalidad" de una columna es cuántos valores distintos tiene: una columna
    "tipo de combustible" puede tener 3, y una de "número de ticket", miles. Recibe ese
    número y devuelve un rango como "11–100". Sirve para saber si la columna es una
    categoría, un código o un identificador, sin dar el número exacto.
    """
    for limite, etiqueta in [(1, "1"), (10, "2–10"), (100, "11–100"), (1_000, "101–1.000"), (10_000, "1.001–10.000")]:
        if n <= limite:
            return etiqueta
    return ">10.000"


# ============================================================================
# Nombres, formatos y sensibilidad
# ============================================================================

def normalizar_nombre(nombre):
    """"Fecha_Carga" y "fechaCarga" -> "fecha carga": minúsculas, sin acentos, palabras separadas.

    Recibe el nombre de una columna y devuelve una versión "limpia" del nombre. Sirve para
    buscar palabras clave en el nombre (ver `sensibilidad_por_nombre`) y para reconocer que
    dos columnas de fuentes distintas son la misma aunque estén escritas diferente.
    """
    # Las "expresiones regulares" (módulo re) son patrones para buscar y reemplazar texto.
    # Esta separa con un espacio una minúscula seguida de una mayúscula: "fechaCarga" -> "fecha Carga"
    texto = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(nombre))
    # Quita los acentos: separa cada letra de su tilde (NFKD) y descarta lo que no es ASCII
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    # Corta en todo lo que no sea letra o número (guiones bajos, espacios, puntos...) y une con espacios
    return " ".join(re.split(r"[^a-z0-9]+", texto.lower())).strip()


def formato(valor):
    """Forma de un valor sin su contenido: letras -> A, dígitos -> 9, el resto se conserva.

    Esta es la "máscara de formato": por ejemplo, la patente "AB123CD" se convierte en
    "AA999AA" y la fecha "15/03/2024" en "99/99/9999". Así se puede describir cómo están
    escritos los valores de una columna (y detectar formatos mezclados o erróneos) sin
    mostrar ningún valor real. Recibe un valor cualquiera y devuelve su máscara como texto.
    """
    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    # Primero se reemplazan las letras por A y después los dígitos por 9
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]", "A", texto))


def sensibilidad_por_nombre(nombre):
    """Adivina, por el nombre de la columna, si guarda un dato sensible y de qué tipo.

    Recibe el nombre de la columna y devuelve el tipo de dato sensible ("persona",
    "identificador", "ubicacion"...) o None si el nombre no da ninguna pista. Es la primera
    barrera de protección; `perfilar_columna` agrega otras basadas en los valores.
    """
    palabras = normalizar_nombre(nombre).split()
    for tipo, pistas in PISTAS_SENSIBLES.items():
        for palabra in palabras:
            # Coincide si la palabra es exactamente una pista, o si empieza con una pista de más de
            # 3 letras ("dependencia" empieza con "depend"). Las pistas cortas como "id" o "lat"
            # exigen coincidencia exacta, para no marcar por error palabras como "idioma" o "lateral".
            if palabra in pistas or any(len(p) > 3 and palabra.startswith(p) for p in pistas):
                return tipo
    return None


def _es_codigo(formato_valor):
    """Formatos como 9999-99999999: mayormente dígitos y largos, típicos de remitos o extractos.

    Recibe una máscara de formato y devuelve True si tiene 6 caracteres o más y al menos el
    60% son dígitos. Un texto así probablemente es un número de comprobante, es decir, un
    identificador, y se protege como tal.
    """
    return len(formato_valor) >= 6 and formato_valor.count("9") / len(formato_valor) >= 0.6


def resumir_formatos_largos(formatos):
    """Los formatos largos de una columna sensible dejan ver su estructura (cómo se nombra una
    unidad o una persona): se reemplazan por su banda de largo.

    Por ejemplo, la máscara de un nombre completo ("AAAAA AAAAAAA") deja ver cuántas letras
    tiene cada palabra, y eso podría ayudar a adivinarlo. Recibe la lista de formatos de la
    columna (cada uno con su porcentaje) y devuelve otra lista donde los formatos de más de
    20 caracteres se reemplazan por "TEXTO_21-40" o "TEXTO_MAS_DE_40", sumando sus porcentajes.
    """
    resumidos = {}
    for f in formatos:
        clave = f["formato"]
        if clave != OTRA and len(clave) > LARGO_FORMATO_SENSIBLE:
            clave = "TEXTO_21-40" if len(clave) <= 40 else "TEXTO_MAS_DE_40"
        resumidos[clave] = round(resumidos.get(clave, 0) + (f["pct"] or 0), 1)
    # Se ordena de mayor a menor porcentaje
    return [{"formato": k, "pct": v} for k, v in sorted(resumidos.items(), key=lambda kv: -kv[1])]


def _es_fecha(formato_valor):
    """Indica si una máscara de formato tiene forma de fecha (con o sin hora).

    Recibe una máscara como "99/99/9999" o "9999-99-99 99:99:99" y devuelve True o False.
    Sirve para reconocer columnas de texto que en realidad guardan fechas.
    """
    # Expresión regular: 1 a 4 dígitos, un separador (- / o .), 1 a 2 dígitos, otro separador,
    # 1 a 4 dígitos; y opcionalmente una hora (hh:mm, con segundos y fracciones opcionales).
    # fullmatch exige que la máscara completa tenga esa forma, no solo una parte.
    return bool(re.fullmatch(r"9{1,4}[-/.]9{1,2}[-/.]9{1,4}([ T]9{1,2}:9{2}(:9{2})?(\.9+)?)?", formato_valor))


# ============================================================================
# Perfil de una columna
# ============================================================================

def _formatos(serie_texto, total):
    """Cuenta qué máscaras de formato aparecen en una columna y con qué frecuencia.

    Recibe la columna como texto (una "serie" de pandas, es decir, una columna de datos) y la
    cantidad total de valores. Devuelve dos cosas:
    - la lista publicable: hasta 10 formatos frecuentes con su porcentaje, más un renglón
      OTRA_CATEGORIA_SINTETIZABLE que junta todos los formatos infrecuentes o que no entraron;
    - el conteo completo de formatos, que se usa solo internamente para decidir el tipo de la
      columna y nunca se guarda en el perfil.
    """
    conteo = serie_texto.map(formato).value_counts()
    # Solo se muestran los formatos que aparecen al menos MINIMO_GRUPO veces; los demás van al grupo "otra"
    visibles = conteo[conteo >= MINIMO_GRUPO]
    resto = int(conteo[conteo < MINIMO_GRUPO].sum())
    formatos = [{"formato": f, "pct": pct(int(n), total)} for f, n in visibles.head(10).items()]
    resto += int(visibles.iloc[10:].sum())
    if resto:
        formatos.append({"formato": OTRA, "pct": pct(resto, total)})
    return formatos, conteo


# Cuantiles que se informan de las columnas numéricas. Un cuantil es el valor que deja por
# debajo cierto porcentaje de los datos: p50 (la mediana) deja la mitad de los valores por
# debajo; p05, el 5%; p95, el 95%. Juntos describen cómo se reparten los valores sin mostrar
# ninguno en particular, y a diferencia del mínimo y el máximo no dependen de un único caso.
CUANTILES = {"p05": 0.05, "p25": 0.25, "p50": 0.5, "p75": 0.75, "p95": 0.95}


def cuantil_publicable(q, n):
    """Un cuantil se publica solo si deja al menos MINIMO_GRUPO observaciones de cada lado.

    Con pocos datos, p05 o p95 quedan pegados al mínimo o al máximo real y lo revelan.

    Recibe el cuantil `q` (por ejemplo 0.05) y la cantidad de valores `n`; devuelve True si
    se puede publicar. Ejemplo: con 100 valores, p05 deja solo 5 por debajo -> no se publica.
    """
    return min(q, 1 - q) * n >= MINIMO_GRUPO


def _numerico(serie):
    """Resumen de una columna numérica no sensible.

    Recibe la columna y devuelve un diccionario con los cuantiles (redondeados a dos cifras,
    o None si no son publicables) y el porcentaje de ceros, de negativos y de números enteros.
    Estos porcentajes ayudan a detectar, por ejemplo, montos cargados en cero por error.
    """
    valores = serie.astype(float)
    cuantiles = valores.quantile(list(CUANTILES.values()))
    return {
        # Los ** "despliegan" este diccionario dentro del que se está armando
        **{clave: dos_cifras(cuantiles[q]) if cuantil_publicable(q, len(valores)) else None
           for clave, q in CUANTILES.items()},
        "ceros_pct": pct(int((valores == 0).sum()), len(valores)),
        "negativos_pct": pct(int((valores < 0).sum()), len(valores)),
        "enteros_pct": pct(int((valores == valores.round()).sum()), len(valores)),
    }


def _fechas(serie_fecha):
    """Resumen de una columna de fechas, agregado por mes y por día de la semana.

    Recibe la columna ya convertida a fechas. Devuelve cuántos meses tienen datos, la
    cantidad de registros por mes (redondeada a decenas, y solo para meses con al menos
    MINIMO_GRUPO registros), cuántos meses se ocultaron por tener pocos, y el porcentaje
    por día de la semana. Agregar por mes evita que una fecha exacta señale un hecho puntual.
    """
    # to_period("M") convierte cada fecha en su mes ("2024-03"), y se cuenta cuántas hay de cada mes
    meses = serie_fecha.dt.to_period("M").astype(str).value_counts().sort_index()
    # round(n, -1) redondea a la decena más cercana (47 -> 50)
    visibles = {mes: int(round(n, -1)) for mes, n in meses.items() if n >= MINIMO_GRUPO}
    return {
        "meses_con_datos": int(len(meses)),
        "por_mes": visibles,
        "meses_suprimidos": int((meses < MINIMO_GRUPO).sum()),
        "dia_semana_pct": {d: pct(int(n), len(serie_fecha)) for d, n in
                           serie_fecha.dt.day_name().value_counts().items() if n >= MINIMO_GRUPO},
    }


def _categorias(serie):
    """Lista de categorías de una columna categórica no sensible, con su porcentaje.

    Recibe la columna (por ejemplo "tipo de combustible") y devuelve una lista como
    [{"valor": "NAFTA", "pct": 62.0}, ...]. Las categorías con menos de MINIMO_GRUPO casos
    no se nombran: se suman en un único renglón OTRA_CATEGORIA_SINTETIZABLE, porque una
    categoría rara puede identificar a quien la tiene.
    """
    conteo = serie.astype(str).str.strip().value_counts()
    total = int(conteo.sum())
    visibles = conteo[conteo >= MINIMO_GRUPO]
    categorias = [{"valor": v, "pct": pct(int(n), total)} for v, n in visibles.items()]
    resto = int(conteo[conteo < MINIMO_GRUPO].sum())
    if resto:
        categorias.append({"valor": OTRA, "pct": pct(resto, total)})
    return categorias


def _calidad_texto(serie_texto):
    """Mide defectos de calidad típicos de una columna de texto.

    Recibe la columna como texto y devuelve el porcentaje de valores con:
    - espacios de más (al principio, al final, o dos seguidos);
    - "vacíos escritos como texto" ("-", "S/D", "N/A"...);
    - mayúsculas y minúsculas mezcladas;
    - números guardados como texto.
    Estos defectos dificultan cruzar tablas, y el proyecto los reproduce en los datos
    sintéticos para poder medir cuánto ayuda limpiarlos.
    """
    total = len(serie_texto)
    return {
        # Dos casos: el valor cambia al quitarle espacios de los bordes (strip), o contiene dos o
        # más espacios seguidos (en expresiones regulares, \s es "espacio" y {2,} es "dos o más")
        "espacios_extra_pct": pct(int((serie_texto != serie_texto.str.strip()).sum()
                                      + serie_texto.str.contains(r"\s{2,}", regex=True).sum()), total),
        "vacios_textuales_pct": pct(int(serie_texto.str.strip().str.upper().isin(VACIOS_TEXTUALES).sum()), total),
        # Tiene al menos una minúscula ([a-z]) y al menos una mayúscula ([A-Z])
        "mayusculas_mixtas_pct": pct(int((serie_texto.str.contains(r"[a-z]", regex=True)
                                          & serie_texto.str.contains(r"[A-Z]", regex=True)).sum()), total),
        # Se intenta convertir a número (aceptando coma decimal); errors="coerce" deja vacío lo que no se puede
        "numeros_como_texto_pct": pct(int(pd.to_numeric(serie_texto.str.replace(",", ".", regex=False),
                                                        errors="coerce").notna().sum()), total),
    }


def perfilar_columna(nombre, serie):
    """Perfil agregado de una columna. Nunca incluye valores de columnas sensibles.

    Recibe el nombre de la columna y sus datos (una serie de pandas). Devuelve un diccionario
    con lo que se sabe de ella: tipo, porcentaje de faltantes, cardinalidad, si es sensible y,
    según el tipo, formatos, cuantiles, fechas por mes, categorías o defectos de calidad.

    El recorrido es: primero datos comunes a todas las columnas; después se prueba, en orden,
    si es booleana, fecha, numérica o texto, y cada caso agrega lo suyo. En numéricas y texto
    se hacen además controles extra para detectar columnas sensibles que el nombre no delató.
    """
    total = len(serie)
    presentes = serie.dropna()
    # En columnas de texto, los valores vacíos o escritos "nan" también cuentan como faltantes
    if pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie):
        texto_limpio = presentes.astype(str)
        presentes = presentes[~texto_limpio.str.strip().str.upper().isin({"", "NAN"})]
    n = len(presentes)
    perfil = {
        "nombre": str(nombre),
        "nombre_normalizado": normalizar_nombre(nombre),
        "faltantes_pct": pct(total - n, total),
        # nunique() cuenta los valores distintos (la cardinalidad), que se publica solo como banda
        "cardinalidad": banda_cardinalidad(int(presentes.nunique())) if n else "0",
        "unicos_pct": pct(int(presentes.nunique()), n) if n else None,
        "sensible": sensibilidad_por_nombre(nombre),
    }
    # Con tan pocos valores cualquier estadística describiría casos individuales: se corta acá
    if n < MINIMO_GRUPO:
        perfil["tipo"] = "desconocido"
        perfil["nota"] = f"menos de {MINIMO_GRUPO} valores: sin estadísticas"
        return perfil

    # Columnas de verdadero/falso: solo el porcentaje de verdaderos
    if pd.api.types.is_bool_dtype(serie):
        perfil["tipo"] = "booleano"
        perfil["verdaderos_pct"] = pct(int(presentes.astype(bool).sum()), n)
        return perfil

    # Columnas que ya vienen como fechas (típico de Excel)
    if pd.api.types.is_datetime64_any_dtype(serie):
        perfil["tipo"] = "fecha"
        perfil["fechas"] = _fechas(pd.to_datetime(presentes))
        # Porcentaje de fechas que traen hora (las que no la traen quedan en 00:00:00)
        perfil["con_hora_pct"] = pct(int((pd.to_datetime(presentes).dt.time.astype(str) != "00:00:00").sum()), n)
        return perfil

    if pd.api.types.is_numeric_dtype(serie):
        # "Precio del establecimiento" es un monto, no el nombre de una organización
        if perfil["sensible"] == "organizacion":
            perfil["sensible"] = None
        valores = presentes.astype(float)
        perfil["tipo"] = "entero" if (valores == valores.round()).all() else "decimal"
        como_texto = valores.astype("int64").astype(str) if perfil["tipo"] == "entero" else presentes.astype(str)
        perfil["formatos"], _ = _formatos(como_texto, n)
        # Decimales entre -90 y 90 con 4 o más decimales tienen toda la pinta de coordenadas
        # (latitud o longitud): se marcan como ubicación aunque la columna no se llame así
        if not perfil["sensible"] and perfil["tipo"] == "decimal" and valores.between(-90, 90).all() \
                and presentes.astype(str).str.split(".").str[-1].str.len().median() >= 4:
            perfil["sensible"] = "ubicacion"
        # Enteros largos (IMEI, líneas, cuentas) son identificadores aunque el nombre no lo diga
        if not perfil["sensible"] and perfil["tipo"] == "entero" and como_texto.str.len().median() >= 11:
            perfil["sensible"] = "identificador"
        # Los cuantiles solo se calculan si la columna no es sensible
        if not perfil["sensible"]:
            perfil["numerico"] = _numerico(presentes)
        return perfil

    # Texto (o mezcla): tipo según sus formatos
    texto = presentes.astype(str)
    perfil["formatos"], conteo = _formatos(texto, n)
    # El formato más frecuente de la columna (value_counts ordena de mayor a menor)
    principal = conteo.index[0]
    # Largo de los textos en tres puntos (p10, mediana y p90), redondeado a enteros
    perfil["largo"] = {k: int(v) for k, v in texto.str.len().quantile([0.1, 0.5, 0.9]).round()
                       .rename({0.1: "p10", 0.5: "p50", 0.9: "p90"}).items()}
    perfil["calidad"] = _calidad_texto(texto)
    # Si al menos el 90% de los valores tiene forma de fecha, es una fecha guardada como texto
    fecha_pct = conteo[[f for f in conteo.index if _es_fecha(f)]].sum() / n
    if fecha_pct >= 0.9:
        perfil["tipo"] = "fecha como texto"
        # Si el formato empieza con el año (9999-...) se lee año-mes-día; si no, día/mes/año
        fechas = pd.to_datetime(texto, errors="coerce", dayfirst=not principal.startswith("9999"))
        perfil["fechas_invalidas_pct"] = pct(int(fechas.isna().sum()), n)
        perfil["fechas"] = _fechas(fechas.dropna()) if fechas.notna().sum() >= MINIMO_GRUPO else None
        return perfil
    if perfil["calidad"]["numeros_como_texto_pct"] >= 90:
        perfil["tipo"] = "número como texto"
    else:
        perfil["tipo"] = "texto"

    # Controles extra de sensibilidad basados en los valores (no en el nombre), del más específico
    # al más general. El primero que se cumple decide el tipo sensible.
    # "Texto libre": formato principal muy largo o demasiados formatos distintos (lo escrito a mano)
    libre = len(principal) > LARGO_TEXTO_LIBRE or len(conteo) > MAX_FORMATOS_DISTINTOS
    # Alguno de los tres formatos más frecuentes es de patente
    if not perfil["sensible"] and conteo.index.isin(FORMATOS_PATENTE)[:3].any():
        perfil["sensible"] = "vehiculo"
    if not perfil["sensible"] and libre and (perfil["unicos_pct"] or 0) > 50:
        perfil["sensible"] = "texto libre"
    # Casi todos los valores distintos entre sí: se comporta como un identificador
    if not perfil["sensible"] and (perfil["unicos_pct"] or 0) > 95 and presentes.nunique() > MAX_CATEGORIAS:
        perfil["sensible"] = "identificador"
    # La mitad o más de los valores parecen números de comprobante
    if not perfil["sensible"] and conteo[[f for f in conteo.index if _es_codigo(f)]].sum() / n >= 0.5:
        perfil["sensible"] = "identificador"
    # Sensible: solo formatos (resumidos). No sensible y con pocas variantes: se listan las categorías.
    if perfil["sensible"]:
        perfil["formatos"] = resumir_formatos_largos(perfil["formatos"])
    elif presentes.nunique() <= MAX_CATEGORIAS:
        perfil["categorias"] = _categorias(presentes)
    return perfil


# ============================================================================
# Perfil de tablas, relaciones y fuentes
# ============================================================================

def _normalizar_valor(valor):
    """Limpia un valor para compararlo con otro: mayúsculas y sin espacios, guiones, guiones bajos ni puntos.

    Por ejemplo, " ab-123 " y "AB123" quedan iguales. Recibe un valor y devuelve el texto limpio.
    Se usa en `relaciones_entre_tablas` para medir cuánto mejora el cruce de tablas al limpiar.
    """
    return re.sub(r"[\s\-_.]", "", str(valor).strip().upper())


def perfilar_tabla(nombre, df):
    """Perfil agregado de una tabla completa.

    Recibe el nombre de la tabla y sus datos (`df`, un DataFrame de pandas: una tabla con filas
    y columnas). Devuelve un diccionario con la cantidad de filas en banda (y aproximada a dos
    cifras), la cantidad de columnas, el porcentaje de filas duplicadas, las columnas que
    podrían ser clave (sin vacíos y sin repetidos) y el perfil de cada columna.
    """
    columnas = []
    for columna in df.columns:
        # Si una columna falla, se anota solo el tipo de error y se sigue con las demás
        try:
            columnas.append(perfilar_columna(columna, df[columna]))
        except Exception as error:  # noqa: BLE001 - no se registra el mensaje: podría incluir un valor
            columnas.append({"nombre": str(columna), "nombre_normalizado": normalizar_nombre(columna),
                             "error": type(error).__name__})
    filas = len(df)
    # Candidata a clave: columna sin vacíos y con todos los valores distintos (puede identificar cada fila)
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

    Una "relación" es un vínculo entre tablas: por ejemplo, la patente de la tabla de consumos
    que apunta a la patente de la tabla de flota. La "cobertura" es qué parte de los valores
    del origen se encuentra en el destino. Recibe las tablas {nombre: DataFrame} y la cobertura
    mínima para informar una relación (50% por defecto). Devuelve una lista de relaciones
    (origen, destino y ambas coberturas), de la más fuerte a la más débil.
    """
    # Paso 1: elegir columnas candidatas a participar de una relación
    candidatas = []
    for tabla, df in tablas.items():
        for columna in df.columns:
            valores = df[columna].dropna()
            # Se descartan columnas con pocos datos, decimales, con un único valor o de fechas:
            # coincidirían entre tablas por casualidad y no son claves
            if len(valores) < MINIMO_GRUPO or pd.api.types.is_float_dtype(valores) or valores.nunique() < 2 \
                    or pd.api.types.is_datetime64_any_dtype(valores):
                continue
            texto = valores.astype(str).str.strip()
            if _es_fecha(formato(texto.iloc[0])):
                continue
            # Conjuntos (set) de valores distintos, tal cual y normalizados; se guardan solo en memoria
            exactos = set(texto)
            es_clave = len(exactos) / len(valores) >= 0.9
            candidatas.append((tabla, str(columna), exactos, {_normalizar_valor(v) for v in exactos}, es_clave))
    # Paso 2: comparar cada candidata con todas las de otras tablas
    relaciones = []
    for tabla_a, col_a, exactos_a, normal_a, _ in candidatas:
        for tabla_b, col_b, exactos_b, normal_b, destino_es_clave in candidatas:
            # Clave foránea -> clave: el destino debe ser (casi) único; con pocos valores distintos en el
            # origen las coincidencias pueden ser casuales
            if tabla_a == tabla_b or len(exactos_a) < 50 or not destino_es_clave:
                continue
            # & es la intersección de conjuntos: los valores que están en ambas columnas
            exacta = len(exactos_a & exactos_b) / len(exactos_a)
            normalizada = len(normal_a & normal_b) / len(normal_a)
            if normalizada >= cobertura_minima:
                relaciones.append({"origen": f"{tabla_a}.{col_a}", "destino": f"{tabla_b}.{col_b}",
                                   "cobertura_exacta_pct": round(100 * exacta, 1),
                                   "cobertura_normalizada_pct": round(100 * normalizada, 1)})
    return sorted(relaciones, key=lambda r: -r["cobertura_normalizada_pct"])


def leer_tablas(archivo, nombre):
    """Lee un CSV o un Excel (cada hoja es una tabla) desde una ruta o un archivo en memoria.

    Recibe `archivo` (una ruta en disco, o un archivo subido a la app que vive solo en la
    memoria) y su `nombre`, que se usa para saber si es Excel o CSV y para nombrar la tabla.
    Devuelve un diccionario {nombre de tabla: DataFrame}. Un Excel con varias hojas da una
    tabla por hoja ("archivo:hoja"). No escribe nada en disco.
    """
    nombre = str(nombre)
    if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        # sheet_name=None lee todas las hojas del Excel
        hojas = pd.read_excel(archivo, sheet_name=None)
        # Nombre base: sin carpetas ni extensión ("C:/datos/flota.xlsx" -> "flota")
        base = re.sub(r"\.\w+$", "", nombre.split("/")[-1].split("\\")[-1])
        return {base if len(hojas) == 1 else f"{base}:{hoja}": df for hoja, df in hojas.items()}
    base = re.sub(r"\.\w+$", "", nombre.split("/")[-1].split("\\")[-1])
    # Un CSV puede separar sus columnas con coma, punto y coma, tabulación o barra vertical. Se prueba
    # cada separador hasta que la lectura da más de una columna.
    for separador in [",", ";", "\t", "|"]:
        # Un archivo en memoria se "rebobina" al principio antes de cada nuevo intento de lectura
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
        # r"0\d+" es la expresión regular de "un cero seguido de más dígitos" (como "00123")
        if valores.empty or valores.str.fullmatch(r"0\d+").any():
            continue
        numeros = pd.to_numeric(valores, errors="coerce")
        # Se convierte si al menos el 98% son números; el resto (errores de carga) queda vacío
        if numeros.notna().mean() >= 0.98:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
    return {base: df}


def aprobar_archivo(origen, carpeta_aprobados, responsable, notas=None):
    """Registra la revisión manual de un perfil pendiente y lo mueve a la carpeta de aprobados.

    Recibe la ruta del perfil pendiente, la carpeta de aprobados, el nombre de la persona
    responsable y notas opcionales. Completa la sección "revision" del perfil (revisado, quién,
    fecha y notas), lo escribe en la carpeta de aprobados y borra el archivo pendiente.
    Devuelve la ruta del perfil aprobado.
    """
    origen = Path(origen)
    perfil = json.loads(origen.read_text(encoding="utf-8"))
    perfil["revision"] = {"revisado": True, "responsable": responsable, "fecha": date.today().isoformat(),
                          "notas": notas or None}
    destino = Path(carpeta_aprobados) / origen.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(perfil, indent=2, ensure_ascii=False), encoding="utf-8")
    # Se borra el pendiente solo si es otro archivo (si ya estaba en aprobados, se habría borrado el recién escrito)
    if origen.resolve() != destino.resolve():
        origen.unlink()
    return destino


def perfilar(tablas, origen="fuente"):
    """Perfil completo de un conjunto de tablas {nombre: DataFrame}.

    Es la función principal del archivo. Recibe las tablas (como las devuelve `leer_tablas`)
    y un texto que describe su origen ("fuentes reales", "sintético (realista)"...). Devuelve
    el perfil completo: versión del perfilador, fecha, origen, estado de la revisión (al
    principio sin revisar), las reglas usadas, el perfil de cada tabla y las relaciones entre
    tablas. Ese diccionario es lo que se guarda como JSON.
    """
    return {
        "perfilador_version": VERSION,
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "origen": origen,
        "revision": {"revisado": False, "responsable": None, "fecha": None, "notas": None},
        "reglas": {"minimo_grupo": MINIMO_GRUPO, "max_categorias": MAX_CATEGORIAS},
        "tablas": {nombre: perfilar_tabla(nombre, df) for nombre, df in tablas.items()},
        "relaciones": relaciones_entre_tablas(tablas),
    }
