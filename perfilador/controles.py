"""Controles agregados que cruzan tablas de la fuente, calculados junto a los datos.

El perfil describe cada tabla por separado; algunos controles de auditoría necesitan cruzarlas.
Estos controles se calculan en el mismo lugar que el perfil y devuelven solo conteos por
categoría: ningún identificador sale del entorno y los conteos de 1 a 19 se informan como
"1–19" (docs/REAL_DATA_BOUNDARY.md).
"""
import pandas as pd

from perfilador.perfil import MINIMO_GRUPO, _normalizar_valor, normalizar_nombre

DIAS_TRANSMISION = 7
GRUPO_DEPOSITO = r"BAJA|REEMPLAZ|DEPOSITO|DEPÓSITO"
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                      "septiembre", "octubre", "noviembre", "diciembre"], 1)}
MESES["setiembre"] = 9
CATEGORIAS = ["sin_dispositivo", "deposito_sin_transmitir", "deposito_transmite",
              "otro_grupo_sin_transmitir", "otro_grupo_transmite"]


def acotar(n):
    """Conteo exportable: 0, "1–19" o el número."""
    n = int(n)
    return n if n == 0 or n >= MINIMO_GRUPO else f"1–{MINIMO_GRUPO - 1}"


def _columna(df, *pistas):
    """Primera columna cuyo nombre normalizado contiene todas las palabras de alguna pista."""
    for pista in pistas:
        palabras = pista.split()
        for columna in df.columns:
            nombre = normalizar_nombre(columna)
            if all(p in nombre.split() or p in nombre for p in palabras):
                return columna
    return None


def leer_fecha_texto(serie):
    """Fechas como `viernes, 12 de septiembre de 2025 9:05:03`, o ISO / dd/mm/aaaa."""
    texto = serie.astype("string").str.lower()
    partes = texto.str.extract(r"(\d{1,2}) de ([a-záéíóú]+) de (\d{4})\s+(\d{1,2}):(\d{2})")
    meses = partes[1].map(MESES)
    armadas = pd.to_datetime(
        dict(year=pd.to_numeric(partes[2], errors="coerce"), month=meses, day=pd.to_numeric(partes[0], errors="coerce"),
             hour=pd.to_numeric(partes[3], errors="coerce"), minute=pd.to_numeric(partes[4], errors="coerce")),
        errors="coerce")
    otras = pd.to_datetime(texto, errors="coerce", dayfirst=True, format="mixed")
    return armadas.fillna(otras)


def _tabla_con(tablas, requeridas):
    """La tabla con menos columnas que tenga todas las columnas pedidas (por pistas)."""
    candidatas = []
    for nombre, df in tablas.items():
        columnas = {clave: _columna(df, *pistas) for clave, pistas in requeridas.items()}
        if all(columnas.values()):
            candidatas.append((len(df.columns), nombre, columnas))
    return min(candidatas)[1:] if candidatas else (None, None)


def telemetria_vs_estado(tablas, dias=DIAS_TRANSMISION, grupo_deposito=GRUPO_DEPOSITO):
    """Móviles por estado según su dispositivo: sin dispositivo, en el grupo de depósito
    (baja / reemplazos) o en otro grupo, y si transmitió en los últimos `dias` días.

    Un móvil de baja no debería tener telemetría; si la tuvo, el dispositivo debería estar en el
    grupo de depósito. Uno en baja con el dispositivo en otro grupo y transmitiendo es una alerta.
    Devuelve None si no están las tablas necesarias.
    """
    padron, cp = _tabla_con(tablas, {"estado": ["estado"], "dominio": ["dominio"], "matricula": ["matricula"]})
    disp, cd = _tabla_con(tablas, {"placa": ["placa"], "grupo": ["grupo"],
                                   "transmision": ["ultima transmision", "ultima tx"]})
    if padron is None or disp is None:
        return None
    flota, dispositivos = tablas[padron], tablas[disp]
    alias = _columna(dispositivos, "alias")

    por_dominio = dict(zip(_normalizar_valor_serie(flota[cp["dominio"]]), flota.index))
    por_matricula = dict(zip(_normalizar_valor_serie(flota[cp["matricula"]]), flota.index))
    movil = _normalizar_valor_serie(dispositivos[cd["placa"]]).map(por_dominio)
    if alias:
        movil = movil.fillna(_normalizar_valor_serie(dispositivos[alias]).map(por_matricula))

    fechas = leer_fecha_texto(dispositivos[cd["transmision"]])
    referencia = fechas.max()
    transmite = (referencia - fechas) <= pd.Timedelta(days=dias)
    deposito = dispositivos[cd["grupo"]].astype("string").str.upper().str.contains(grupo_deposito, regex=True,
                                                                                  na=False)
    categoria = pd.Series("otro_grupo_sin_transmitir", index=dispositivos.index)
    categoria[deposito & ~transmite] = "deposito_sin_transmitir"
    categoria[deposito & transmite] = "deposito_transmite"
    categoria[~deposito & transmite] = "otro_grupo_transmite"
    prioridad = {c: i for i, c in enumerate(CATEGORIAS)}
    # Si un móvil tiene varios dispositivos, cuenta el de la categoría más comprometida
    por_movil = (pd.DataFrame({"movil": movil, "categoria": categoria}).dropna(subset=["movil"])
                 .assign(orden=lambda d: d["categoria"].map(prioridad))
                 .sort_values("orden").groupby("movil")["categoria"].last())

    estado = flota[cp["estado"]].astype("string").str.strip().str.upper().fillna("SIN ESTADO")
    estado = estado.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    detalle = pd.DataFrame({"estado": estado, "categoria": flota.index.map(por_movil).fillna("sin_dispositivo")})
    tabla = pd.crosstab(detalle["estado"], detalle["categoria"]).reindex(columns=CATEGORIAS, fill_value=0)
    en_baja = tabla.index.str.contains("BAJA")
    return {
        "descripcion": "móviles por estado según su dispositivo (grupo de depósito o no) y si transmitió "
                       f"en los últimos {dias} días; conteos de 1 a {MINIMO_GRUPO - 1} acotados",
        "mes_de_referencia": referencia.strftime("%Y-%m") if pd.notna(referencia) else None,
        "patron_grupo_deposito": grupo_deposito,
        "por_estado": {e: {"moviles": acotar(fila.sum()), **{c: acotar(fila[c]) for c in CATEGORIAS}}
                       for e, fila in tabla.iterrows()},
        "dispositivos_sin_movil": acotar(movil.isna().sum()),
        "fechas_de_transmision_ilegibles": acotar(fechas.isna().sum()),
        "alerta_baja_con_dispositivo_activo": acotar(tabla.loc[en_baja, "otro_grupo_transmite"].sum()),
    }


def _normalizar_valor_serie(serie):
    return serie.dropna().astype(str).map(_normalizar_valor).reindex(serie.index)


def ejecutar_controles(tablas):
    """Todos los controles que se pueden calcular con las tablas disponibles."""
    controles = {}
    resultado = telemetria_vs_estado(tablas)
    if resultado is not None:
        controles["telemetria_vs_estado"] = resultado
    return controles
