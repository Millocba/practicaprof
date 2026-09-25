#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Combustible STANDALONE - Para D:\Integrador
=========================================================

Genera transacciones de combustible sincronizadas (YPF + RIGCOM)
con anomalías de cruce auditables.

Uso:
    python generator_combustible_standalone.py [--periodos 4] [--seed 20260906]
"""
import random
import unicodedata
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

TOL_LITROS_OK = 0.5
RIG_FILTRO_YPF = "YPF"


def periodos_por_defecto(n: int = 4) -> tuple:
    """Últimos N meses (relativo a HOY)."""
    hoy = datetime.now()
    out = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        out.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return tuple(reversed(out))


@dataclass
class ConfigCombustible:
    periodos: tuple = field(default_factory=periodos_por_defecto)
    filas_ypf_por_mes: int = 730
    seed: int = 20260906
    tasa_solo_ypf: float = 0.035
    tasa_solo_rig: float = 0.030
    tasa_desacuerdo: float = 0.045
    tasa_estacion_no_ypf: float = 0.08


# ---- Catálogos ----
APELLIDOS = [
    "GOMEZ", "RODRIGUEZ", "FERNANDEZ", "LOPEZ", "MARTINEZ", "PEREZ", "GARCIA",
    "SANCHEZ", "ROMERO", "SOSA", "TORRES", "ALVAREZ", "RUIZ", "DIAZ", "MORENO",
]
NOMBRES = [
    "JUAN CARLOS", "MARIA LAURA", "CRISTIAN ALEJANDRO", "FACUNDO LEONEL",
    "SERGIO DANIEL", "ANALIA BEATRIZ", "PABLO MARTIN", "LUCAS EZEQUIEL",
]
LOCALIDADES = [
    "CORDOBA", "RIO CUARTO", "VILLA MARIA", "SAN FRANCISCO", "ALTA GRACIA",
    "VILLA CARLOS PAZ", "JESUS MARIA", "BELL VILLE", "MARCOS JUAREZ",
]
RAZONES = [
    "ROBERTO S SANCHEZ E HIJOS", "ESTACION DEL CENTRO SRL", "COMBUSTIBLES DEL SUR SA",
    "SERVICENTRO LA ESQUINA", "PETROSUR SRL", "AUTOSERVICIO RUTA 9 SA",
]
CONTRATOS = [
    ("CRE POLICIA CORDOBA OP 1", 362),
    ("CRE POLICIA CORDOBA 3", 162),
    ("CRE POLICIA CORDOBA OP", 81),
]
PRODUCTOS_DIESEL = [("INFINIA DIESEL", 388), ("D.DIESEL 500", 2)]
PRODUCTOS_NAFTA = [("INFINIA", 339), ("NAFTA SUPER", 3)]
JERARQUIAS = [
    "AGENTE", "CABO", "SARGENTO", "SUBOFICIAL", "OFICIAL",
]

anomalias: list = []


def _reg(tabla, ref, columna, tipo, severidad, desc, original=None, inyectado=None):
    anomalias.append({
        "tabla": tabla, "referencia": ref, "columna": columna, "tipo": tipo,
        "severidad": severidad, "descripcion": desc,
        "valor_original": original, "valor_inyectado": inyectado,
    })


def _pick(pares):
    vals = [v for v, _ in pares]
    pesos = [w for _, w in pares]
    return random.choices(vals, weights=pesos)[0]


def _digits(n):
    return "".join(random.choices("0123456789", k=n))


def _persona():
    dni = str(random.randint(20000000, 46999999))
    nombre = f"{random.choice(APELLIDOS)} {random.choice(NOMBRES)}"
    return nombre, dni


def _dias_del_mes(anio, mes):
    d = datetime(anio, mes, 1)
    fin = datetime(anio + (mes == 12), (mes % 12) + 1, 1)
    hoy = datetime.now()
    if (anio, mes) == (hoy.year, hoy.month):
        fin = min(fin, datetime(anio, mes, hoy.day) + timedelta(days=1))
    out = []
    while d < fin:
        out.append(d)
        d += timedelta(days=1)
    return out


def cargar_flota(ruta_flota: Path | None = None) -> pd.DataFrame:
    """Carga flota desde CSV generado por v7.5."""
    if ruta_flota is None:
        candidatos = sorted(Path("data/synthetic").glob("vehiculos_*.csv"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidatos:
            raise FileNotFoundError(
                "No hay CSV de flota en data/synthetic/. "
                "Ejecuta primero: python setup_integrador.py"
            )
        ruta_flota = candidatos[0]

    f = pd.read_csv(ruta_flota, dtype=str)
    dom = f["Dominio"].fillna("").str.strip().str.upper()
    invalido = dom.eq("") | dom.str.contains(r"S\s*/?\s*D|SIN\s*DOMINIO", regex=True, na=False)
    estado = f.get("Estado", pd.Series()).fillna("").str.strip().str.upper()
    elegible = (~invalido) & ((~estado.eq("BAJA")) | (estado.eq("")))
    return f[elegible].copy().reset_index(drop=True)


def construir_eventos(flota: pd.DataFrame, anio: int, mes: int, cfg: ConfigCombustible):
    """Genera eventos de carga con anomalías."""
    dias = _dias_del_mes(anio, mes)
    dias_completos = monthrange(anio, mes)[1]
    objetivo = max(40, round(cfg.filas_ypf_por_mes * len(dias) / dias_completos))
    eventos = []

    conductores = {}
    for _, v in flota.iterrows():
        conductores[v["Dominio"]] = _persona()

    if not hasattr(construir_eventos, "_odo"):
        construir_eventos._odo = {}
    odo = construir_eventos._odo

    i = 0
    while len(eventos) < objetivo:
        v = flota.iloc[i % len(flota)]
        i += 1
        dominio = v["Dominio"]
        if dominio not in odo:
            odo[dominio] = random.randint(20000, 480000)

        combustible = str(v.get("TipoCombustible", "Diesel"))
        capacidad = pd.to_numeric(v.get("CapacidadTanque"), errors="coerce")
        capacidad = float(capacidad) if pd.notna(capacidad) else 70.0

        litros = round(min(capacidad, max(5.0, random.gauss(0.55 * capacidad, 0.18 * capacidad))), 2)
        odo[dominio] += random.randint(200, 1400)
        fecha = random.choice(dias) + timedelta(
            hours=random.randint(0, 23), minutes=random.randint(0, 59)
        )
        nombre, dni = conductores[dominio]

        eventos.append({
            "dominio": dominio,
            "matricula": v.get("Matricula", ""),
            "dependencia": v.get("Dependencia", ""),
            "direccion_gral": v.get("DireccionGral", ""),
            "combustible": combustible,
            "capacidad": capacidad,
            "litros_ypf": litros,
            "litros_rig": litros,
            "odometro": odo[dominio],
            "fecha": fecha,
            "conductor": nombre,
            "jerarquia": random.choice(JERARQUIAS),
            "dni": dni,
            "en_ypf": True,
            "en_rig": True,
            "estacion": "YPF",
            "anulado": "NO",
            "rendido": "SI",
        })

    # ---- Inyección de anomalías ----
    por_dominio = {}
    for j, e in enumerate(eventos):
        por_dominio.setdefault(e["dominio"], []).append(j)
    dominios = list(por_dominio)
    random.shuffle(dominios)
    cd = 0

    def tomar_dominios(frac):
        nonlocal cd
        k = max(1, int(len(dominios) * frac))
        s_ = dominios[cd:cd + k]
        cd += k
        return s_

    # SOLO_YPF
    for dom in tomar_dominios(cfg.tasa_solo_ypf):
        for j in por_dominio[dom]:
            eventos[j].update(en_ypf=True, en_rig=False, estacion="YPF")
        litros = round(sum(eventos[j]["litros_ypf"] for j in por_dominio[dom]), 2)
        _reg("cruce", dom, "LITROS", "SOLO_YPF", "alta",
             f"{len(por_dominio[dom])} carga(s) por {litros}L sin solicitud RIGCOM",
             None, litros)

    # SOLO_RIG
    for dom in tomar_dominios(cfg.tasa_solo_rig):
        for j in por_dominio[dom]:
            eventos[j].update(en_ypf=False, en_rig=True, estacion="YPF", rendido="SI", anulado="NO")
        litros = round(sum(eventos[j]["litros_rig"] for j in por_dominio[dom]), 2)
        _reg("cruce", dom, "LITROS", "SOLO_RIG", "alta",
             f"{len(por_dominio[dom])} solicitud(es) por {litros}L sin carga en YPF",
             litros, None)

    # DESACUERDO
    for dom in tomar_dominios(cfg.tasa_desacuerdo):
        js = por_dominio[dom]
        for j in js:
            eventos[j].update(en_ypf=True, en_rig=True, estacion="YPF", rendido="SI", anulado="NO")
        j = random.choice(js)
        delta = round(random.uniform(2.0, 18.0), 2) * random.choice([1, -1])
        orig = eventos[j]["litros_rig"]
        eventos[j]["litros_rig"] = max(0.0, round(orig - delta, 2))
        _reg("cruce", dom, "LITROS", "DESACUERDO", "alta",
             f"Diferencia {abs(delta):.2f}L (tolerancia {TOL_LITROS_OK}L)",
             orig, eventos[j]["litros_rig"])

    # Cargas fuera de red YPF
    libres = [j for j, e in enumerate(eventos) if e["en_ypf"] and e["en_rig"]]
    random.shuffle(libres)
    cur = 0

    def tomar(k):
        nonlocal cur
        s_ = libres[cur:cur + k]
        cur += k
        return s_

    for j in tomar(int(len(eventos) * cfg.tasa_estacion_no_ypf)):
        eventos[j].update(estacion=random.choice(["BIOCOMBUSTIBLE", "COMBUSTIBLES CENTRO"]),
                         en_ypf=False)

    return eventos


def fila_ypf(e, seq):
    diesel = "DIESEL" in str(e["combustible"]).upper()
    producto = _pick(PRODUCTOS_DIESEL if diesel else PRODUCTOS_NAFTA)
    precio = round(random.uniform(2300, 2600), 2)
    importe = round(precio * e["litros_ypf"], 2)
    yer = round(precio * 0.98, 2)
    imp_yer = round(yer * e["litros_ypf"], 2)

    tipo_id, ident = "PATENTE", e["dominio"]

    return {
        "FECHA": e["fecha"].strftime("%d/%m/%Y %H:%M:%S"),
        "CONTRATO": _pick(CONTRATOS),
        "ESTABLECIMIENTO": f"{random.randint(1000, 9999)} - {random.choice(RAZONES)}",
        "LOCALIDAD": random.choice(LOCALIDADES),
        "CONDUCTOR": e["conductor"],
        "TIPO IDENTIFICACION TARJETA": tipo_id,
        "IDENTIFICACION TARJETA": ident,
        "ODOMETRO": e["odometro"],
        "PRODUCTO": producto,
        "LITROS UNIDADES": e["litros_ypf"],
        "PRECIO PVP": precio,
        "IMPORTE": importe,
        "PRECIO YER": yer,
        "IMP YER": imp_yer,
    }


def fila_rigcom(e, seq):
    rend = e["rendido"] == "SI" and e["anulado"] == "NO"
    f_rend = e["fecha"] + timedelta(minutes=random.randint(5, 90))
    autorizados = int(round(e["litros_rig"] + random.uniform(0, 10)))

    return {
        "Id": seq,
        "Fecha": e["fecha"].strftime("%d/%m/%Y"),
        "Hora": e["fecha"].strftime("%H:%M:%S"),
        "Matricula": e["matricula"],
        "Dominio": e["dominio"],
        "OdometroRegistrado": e["odometro"],
        "Solicitante": f"{e['jerarquia']} {e['conductor']}",
        "Rendido": "SI" if rend else "NO",
        "LitrosAutorizados": autorizados,
        "LitrosCargados": e["litros_rig"],
        "CapacidadTanque": f"{int(e['capacidad'])}/L",
        "FechaRendicion": f_rend.strftime("%d/%m/%Y") if rend else None,
        "Dependencia": e["dependencia"],
        "DireccionGral": e["direccion_gral"],
    }


def generar(cfg: ConfigCombustible = ConfigCombustible(), base: Path = Path(".")):
    global anomalias
    anomalias = []
    random.seed(cfg.seed)

    print("\n" + "="*80)
    print("GENERADOR COMBUSTIBLE STANDALONE")
    print("="*80)

    flota = cargar_flota()
    print(f"\n✓ Flota cargada: {len(flota)} vehículos")

    resumen = []
    seq_rig = 1_800_000

    for anio, mes in cfg.periodos:
        print(f"\n⏳ Procesando {anio}-{mes:02d}...", end=" ")
        eventos = construir_eventos(flota, anio, mes, cfg)
        ypf_rows, rig_rows = [], []

        for e in eventos:
            if e["en_ypf"]:
                ypf_rows.append(fila_ypf(e, len(ypf_rows) + 1))
            if e["en_rig"]:
                rig_rows.append(fila_rigcom(e, seq_rig))
                seq_rig += 1

        ypf = pd.DataFrame(ypf_rows).sort_values("FECHA").reset_index(drop=True)
        rig = pd.DataFrame(rig_rows).sort_values(["Fecha", "Hora"]).reset_index(drop=True)

        d_ypf = base / "data" / "combustible" / str(anio) / f"{mes:02d}"
        d_rig = base / "data" / "rigcom" / str(anio) / f"{mes:02d}"
        d_ypf.mkdir(parents=True, exist_ok=True)
        d_rig.mkdir(parents=True, exist_ok=True)

        for viejo in list(d_ypf.glob("*.xlsx")) + list(d_rig.glob("*.xlsx")):
            viejo.unlink(missing_ok=True)

        p_ypf = d_ypf / f"ReporteConsumos_{anio}{mes:02d}.xlsx"
        p_rig = d_rig / f"SolicitudesRigcom_{anio}{mes:02d}.xlsx"
        ypf.to_excel(p_ypf, index=False, sheet_name="ReporteConsumos")
        rig.to_excel(p_rig, index=False, sheet_name="Sheet1")

        resumen.append({"periodo": f"{anio}-{mes:02d}", "ypf": len(ypf), "rigcom": len(rig)})
        print(f"YPF={len(ypf):4d}  RIGCOM={len(rig):4d}  ✓")

    ano_df = pd.DataFrame(anomalias)
    (base / "data").mkdir(exist_ok=True)
    ano_df.to_csv(base / "data" / "anomalias_combustible.csv", index=False, encoding="utf-8")

    print("\n" + "="*80)
    print(f"✅ COMBUSTIBLE GENERADO")
    print(f"   YPF: {sum(r['ypf'] for r in resumen)} transacciones")
    print(f"   RIGCOM: {sum(r['rigcom'] for r in resumen)} solicitudes")
    print(f"   Anomalías: {len(ano_df)} inyectadas")
    print("="*80)

    return pd.DataFrame(resumen), ano_df


if __name__ == "__main__":
    res, ano = generar()
    print("\nRESUMEN:")
    print(res.to_string(index=False))
