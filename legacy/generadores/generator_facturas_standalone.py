#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Facturas STANDALONE - Para D:\Integrador
===================================================

Genera facturas PDF + Excel de deuda, coherentes con consumo,
con anomalías de facturación inyectadas.

Uso:
    python generator_facturas_standalone.py [--periodo 202609]
"""
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

# Configuración de facturas
ICL_POR_LITRO = 257.90
IDC_POR_LITRO = 24.55
PUNTO_VENTA = "1420"
NUMERO_DESDE = 99001

PROVEEDOR = "COMBUSTIBLES DEMO S.A."
PROVEEDOR_CUIT = "30-00000000-0"
CLIENTE_CUIT = "30-00000000-0"
LEYENDA = "DOCUMENTO DE PRUEBA - DATOS SINTETICOS - SIN VALOR FISCAL"

# Desvíos intencionales por factura
DESVIOS = {
    1: ("SOBREFACTURACION", +847_320.0),
    3: ("SUBFACTURACION", -212_450.0),
}
IDX_NO_COMBUSTIBLE = 2

CODIGO_PRODUCTO = {
    "DIESEL": ("405200", "INFINIA DIESEL", "301202"),
    "NAFTA": ("409900", "NAFTA INFINIA", "333475"),
    "NOCOMB": ("701500", "LUBRICANTE 15W40", "000000")
}


def _mi(v: float, dec: int = 2) -> str:
    """Formato argentino: 1234567.89 -> '1.234.567,89'"""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "@").replace(".", ",").replace("@", ".")


def agregar_consumo(periodo: str) -> dict[int, dict]:
    """Agrupa consumo por contrato."""
    archivo = Path("data") / "consumo" / f"ReporteConsumos_{periodo}.xlsx"
    if not archivo.exists():
        raise FileNotFoundError(
            f"No existe {archivo}. "
            f"Ejecuta primero: python generator_consumo_diario_standalone.py"
        )

    df = pd.read_excel(archivo)

    # Para standalone: usar índice como contrato_id
    out: dict[int, dict] = {}

    # Agrupar por DOMINIO como proxy de contrato
    for (dominio,), g in df.groupby(["DOMINIO"]):
        cid = hash(dominio) % 100  # Pseudo-contrato basado en dominio
        if pd.isna(dominio):
            continue

        d = out.setdefault(cid, {"items": [], "litros": 0.0, "neto": 0.0, "filas": []})

        litros = float(g["LITROS UNIDADES"].sum())
        neto = float(g["IMP TOT YER"].sum())

        diesel_pct = ("DIESEL" in str(g["PRODUCTO"]).str.upper().values).sum() / len(g)
        fam = "DIESEL" if diesel_pct > 0.5 else "NAFTA"

        d["items"].append({
            "fam": fam,
            "litros": litros,
            "neto": neto,
            "unitario": neto / litros if litros else 0.0
        })
        d["litros"] += litros
        d["neto"] += neto
        d["filas"].append(g)

    for d in out.values():
        d["items"].sort(key=lambda x: -x["neto"])
        d["filas"] = pd.concat(d["filas"], ignore_index=True) if d["filas"] else pd.DataFrame()
        d["total"] = d["neto"]
        d["icl"] = d["litros"] * ICL_POR_LITRO
        d["idc"] = d["litros"] * IDC_POR_LITRO
        d["impuestos"] = d["icl"] + d["idc"]

    return out


def construir_deuda(ruta: Path, filas: list[dict], vence: date) -> None:
    """Crea Excel de deuda."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Deuda"
    ws.append(["Tipo", "Nro. Legal", "Referencia", "Clase", "Texto/SGC",
               "F. Doc.", "F. Contab.", "F. Venc.", "Moneda",
               "Original ARS", "Pendiente ARS"])

    for f in filas:
        ws.append([
            "Factura", f["nro_legal"], f["numero"], "RV", f"{f['contrato']:010d}CQ",
            f["fecha"].strftime("%d/%m/%Y"), f["fecha"].strftime("%d/%m/%Y"),
            vence.strftime("%d/%m/%Y"), "ARS", f["total"], f["total"]
        ])

    for col, ancho in zip("ABCDEFGHIJK", (10, 16, 16, 6, 15, 12, 12, 12, 8, 16, 18)):
        ws.column_dimensions[col].width = ancho

    wb.save(ruta)


def construir_reporte_factura(ruta: Path, filas: pd.DataFrame, numero: str) -> float:
    """Reporte de consumo por factura."""
    df = filas.copy()
    df["FACTURA"] = numero
    df.to_excel(ruta, index=False, sheet_name="ReporteConsumos")
    return float(df["IMP TOT YER"].sum())


def generar(periodo: str = "202609") -> list[dict]:
    """Genera facturas e invoice matching."""
    anio, mes = int(periodo[:4]), int(periodo[4:])
    ultimo = (date(anio + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1))
    vence = ultimo + timedelta(days=15)

    print("\n" + "="*80)
    print("GENERADOR FACTURAS STANDALONE")
    print("="*80)

    agregados = agregar_consumo(periodo)
    print(f"\n✓ Consumo cargado: {len(agregados)} contratos")

    destino = Path("data") / "facturacion" / periodo
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*"):
        viejo.unlink()

    filas_deuda = []

    for i, cid in enumerate(sorted(agregados, key=lambda k: -agregados[k]["neto"])):
        d = agregados[cid]
        seq = NUMERO_DESDE + i
        numero = f"F{PUNTO_VENTA}B{seq:08d}"
        detalle = d["filas"]

        # Inyectar producto no combustible
        no_comb = 0.0
        if i == IDX_NO_COMBUSTIBLE and len(detalle) > 0:
            extra = detalle.tail(3).copy()
            extra["PRODUCTO"] = "LUBRICANTE 15W40"
            extra["LITROS UNIDADES"] = [4.0, 8.0, 4.0]
            extra["IMP TOT YER"] = [58_400.0, 116_800.0, 58_400.0]
            extra["IMP TOT PVP ESTABLECIMIENTO"] = extra["IMP TOT YER"] / 0.98
            detalle = pd.concat([detalle, extra], ignore_index=True)
            no_comb = float(extra["IMP TOT YER"].sum())

        reporte = destino / f"Reporte_{numero}.xlsx"
        consumido = construir_reporte_factura(reporte, detalle, numero)

        # Aplicar desvíos
        tipo_desvio, delta = DESVIOS.get(i, (None, 0.0))
        monto = consumido + delta
        d["total"] = monto
        d["neto"] = d["neto"] + no_comb

        if no_comb:
            d["items"].append({
                "fam": "NOCOMB",
                "litros": 16.0,
                "neto": no_comb,
                "unitario": no_comb / 16.0
            })

        filas_deuda.append({
            "numero": numero,
            "nro_legal": f"B{PUNTO_VENTA}{seq:08d}",
            "contrato": cid,
            "dependencia": f"DEP_{cid}",
            "litros": d["litros"],
            "consumido": consumido,
            "total": monto,
            "fecha": ultimo,
            "desvio": tipo_desvio,
            "delta": delta,
            "no_combustible": bool(no_comb),
        })

        print(f"  {numero:16s} consumo={consumido:>12,.0f} factura={monto:>12,.0f}", end="")
        if tipo_desvio:
            print(f" ⚠️ {tipo_desvio}", end="")
        if no_comb:
            print(f" ⚠️ NO_COMBUSTIBLE", end="")
        print()

    construir_deuda(destino / f"Deuda_{periodo}.xlsx", filas_deuda, vence)

    print("\n" + "="*80)
    print("✅ FACTURAS GENERADAS")
    print(f"   Total: {len(filas_deuda)} facturas")
    print(f"   Importe total: ${sum(f['total'] for f in filas_deuda):,.0f}")
    print(f"   Anomalías inyectadas: {sum(1 for f in filas_deuda if f['desvio'])}")
    print("="*80)

    return filas_deuda


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", default="202609", help="AAAAMMM")
    a = ap.parse_args()

    filas = generar(a.periodo)
    print("\nDETALLE:")
    for f in filas:
        al = []
        if f["desvio"]:
            al.append(f"{f['desvio']} ({f['delta']:+.0f})")
        if f["no_combustible"]:
            al.append("NO_COMBUSTIBLE")
        print(f"{f['numero']:16s} "
              f"consumido={f['consumido']:>12,.0f} "
              f"facturado={f['total']:>12,.0f} "
              f"{' + '.join(al) if al else '-'}")
