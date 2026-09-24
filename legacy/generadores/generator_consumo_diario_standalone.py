#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Consumo Diario STANDALONE - Para D:\Integrador
==========================================================

Genera reportes diarios de consumo en formato YPF
con anomalías de odometro inyectadas.

Uso:
    python generator_consumo_diario_standalone.py [--meses 2]
"""
import random
import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd


TX_POR_DIA = 33
SEED = 20260906

# Reutilizar catalogos del generador combustible
RAZONES = [
    "ROBERTO S SANCHEZ E HIJOS", "ESTACION DEL CENTRO SRL", "COMBUSTIBLES DEL SUR SA",
    "SERVICENTRO LA ESQUINA", "PETROSUR SRL", "AUTOSERVICIO RUTA 9 SA",
]
LOCALIDADES = [
    "CORDOBA", "RIO CUARTO", "VILLA MARIA", "SAN FRANCISCO", "ALTA GRACIA",
]
PRODUCTOS_DIESEL = [("INFINIA DIESEL", 388), ("D.DIESEL 500", 2)]
PRODUCTOS_NAFTA = [("INFINIA", 339), ("NAFTA SUPER", 3)]


def _pick(pares):
    vals = [v for v, _ in pares]
    pesos = [w for _, w in pares]
    return random.choices(vals, weights=pesos)[0]


def _digits(n):
    return "".join(random.choices("0123456789", k=n))


def _clave_odometro(dominio: str) -> str:
    """Normaliza el dominio para tracking de odometro."""
    return re.sub(r"[^A-Z0-9]", "", str(dominio).strip().upper())


def _persona():
    dni = str(random.randint(20000000, 46999999))
    apellidos = ["GOMEZ", "RODRIGUEZ", "FERNANDEZ", "LOPEZ", "MARTINEZ"]
    nombres = ["JUAN", "MARIA", "CARLOS", "LAURA", "SERGIO"]
    nombre = f"{random.choice(apellidos)} {random.choice(nombres)}"
    return nombre, dni


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


def construir_dia(dia: date, flota: pd.DataFrame, odometros: dict[str, int]) -> pd.DataFrame:
    """Genera transacciones de un día."""
    sorteo = sorted(
        (datetime(dia.year, dia.month, dia.day, random.randint(0, 23),
                  random.randint(0, 59), random.randint(0, 59)),
         random.randrange(len(flota)))
        for _ in range(TX_POR_DIA)
    )

    filas = []
    for momento, idx_v in sorteo:
        v = flota.iloc[idx_v]
        dominio = v["Dominio"]

        capacidad = pd.to_numeric(v.get("CapacidadTanque"), errors="coerce")
        capacidad = float(capacidad) if pd.notna(capacidad) else 70.0
        litros = round(min(capacidad, max(5.0, random.gauss(0.55 * capacidad, 0.18 * capacidad))), 2)

        clave = _clave_odometro(dominio)
        odometros[clave] = odometros.get(clave, random.randint(20000, 480000)) + random.randint(150, 900)

        nombre, dni = _persona()
        diesel = "DIESEL" in str(v.get("TipoCombustible", "")).upper()
        producto = _pick(PRODUCTOS_DIESEL if diesel else PRODUCTOS_NAFTA)
        precio = round(random.uniform(2300, 2600), 2)
        importe = round(precio * litros, 2)
        yer = round(precio * 0.98, 2)

        filas.append({
            "FECHA": momento.strftime("%d/%m/%Y %H:%M:%S"),
            "ESTABLECIMIENTO": f"{random.randint(1000, 9999)} - {random.choice(RAZONES)}",
            "DOMICILIO": f"AV. {random.choice(['COLON', 'SAN MARTIN', 'BELGRANO'])} {random.randint(100, 3500)}",
            "LOCALIDAD": random.choice(LOCALIDADES),
            "DOMINIO": dominio,
            "CONDUCTOR": f"{nombre.split()[0]}, {' '.join(nombre.split()[1:])},",
            "IDENTIFICACION TARJETA": dominio,
            "ODOMETRO": odometros[clave],
            "PRODUCTO": producto,
            "LITROS UNIDADES": litros,
            "PRECIO PVP ESTABLECIMIENTO": precio,
            "IMP TOT PVP ESTABLECIMIENTO": importe,
            "PRECIO YER": yer,
            "IMP TOT YER": round(yer * litros, 2),
        })

    return pd.DataFrame(filas)


def inyectar_odometro(df: pd.DataFrame, retrocesos: int = 5, saltos: int = 4) -> list[dict]:
    """Inyecta anomalías de odometro."""
    reg = []
    ultima_por_movil = (df.assign(_k=df["IDENTIFICACION TARJETA"].map(_clave_odometro))
                          .groupby("_k").tail(1).index.tolist())
    random.shuffle(ultima_por_movil)

    for i in ultima_por_movil[:retrocesos]:
        orig = int(df.at[i, "ODOMETRO"])
        df.at[i, "ODOMETRO"] = max(0, orig - random.randint(3000, 40000))
        reg.append({
            "tipo": "ODOMETRO_REGRESIVO",
            "patente": df.at[i, "IDENTIFICACION TARJETA"],
            "fecha": df.at[i, "FECHA"],
            "original": orig,
            "inyectado": int(df.at[i, "ODOMETRO"])
        })

    for i in ultima_por_movil[retrocesos:retrocesos + saltos]:
        orig = int(df.at[i, "ODOMETRO"])
        df.at[i, "ODOMETRO"] = orig + random.randint(1500, 9000)
        reg.append({
            "tipo": "ODOMETRO_SALTO",
            "patente": df.at[i, "IDENTIFICACION TARJETA"],
            "fecha": df.at[i, "FECHA"],
            "original": orig,
            "inyectado": int(df.at[i, "ODOMETRO"])
        })

    return reg


def _meses_hacia_atras(hoy: date, n: int) -> list[tuple[int, int]]:
    out, anio, mes = [], hoy.year, hoy.month
    for _ in range(n):
        out.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(out))


def generar(meses: int = 2, hasta: date | None = None) -> list[dict]:
    """Genera reportes diarios de consumo."""
    random.seed(SEED)
    hoy = hasta or date.today()

    print("\n" + "="*80)
    print("GENERADOR CONSUMO DIARIO STANDALONE")
    print("="*80)

    destino = Path("data") / "consumo"
    destino.mkdir(parents=True, exist_ok=True)

    flota = cargar_flota()
    print(f"\n✓ Flota cargada: {len(flota)} vehículos")

    odometros: dict[str, int] = {}
    resumen = []

    for anio, mes in _meses_hacia_atras(hoy, meses):
        print(f"\n⏳ Procesando {anio}-{mes:02d}...", end=" ")
        ultimo = hoy.day if (anio, mes) == (hoy.year, hoy.month) else monthrange(anio, mes)[1]
        dias = [date(anio, mes, d) for d in range(1, ultimo + 1)]

        partes = [construir_dia(d, flota, odometros) for d in dias]
        df = pd.concat(partes, ignore_index=True)
        anomalias = inyectar_odometro(df)

        archivo = destino / f"ReporteConsumos_{anio}{mes:02d}.xlsx"
        df.to_excel(archivo, index=False, sheet_name="ReporteConsumos")

        importe = float(df["IMP TOT PVP ESTABLECIMIENTO"].sum())
        resumen.append({
            "periodo": f"{anio}-{mes:02d}",
            "archivo": archivo.name,
            "dias": len(dias),
            "dias_mes": monthrange(anio, mes)[1],
            "transacciones": len(df),
            "importe": importe,
            "anomalias_odometro": len(anomalias),
            "parcial": ultimo != monthrange(anio, mes)[1],
        })
        print(f"✓ ({len(df)} tx, {len(anomalias)} anomalías)")

    print("\n" + "="*80)
    print("✅ CONSUMO DIARIO GENERADO")
    print(f"   Total meses: {len(resumen)}")
    print(f"   Total transacciones: {sum(r['transacciones'] for r in resumen)}")
    print(f"   Total anomalías: {sum(r['anomalias_odometro'] for r in resumen)}")
    print("="*80)

    return resumen


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=2)
    a = ap.parse_args()

    resumen = generar(meses=a.meses)
    print("\nRESUMEN:")
    for r in resumen:
        marca = " (parcial)" if r["parcial"] else ""
        print(f"{r['periodo']:9s} {r['archivo']:30s} "
              f"tx={r['transacciones']:>6d} "
              f"anom={r['anomalias_odometro']:>2d}{marca}")
