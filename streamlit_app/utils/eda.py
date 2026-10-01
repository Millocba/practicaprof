"""Cálculos reproducibles para el análisis exploratorio del Sprint 3.

Las funciones de este módulo no dibujan ni dependen de Streamlit: reciben tablas y
devuelven tablas listas para presentar. La interfaz conserva así una única versión
de cada cálculo y puede probarse con datos pequeños.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from deteccion.reglas import (
    cargas_fuera_del_reporte,
    cargas_por_dia,
    cruzar_registro,
    normalizar_dominio,
    secuencia_odometro,
)


def _conteo(df: pd.DataFrame, columna: str, etiqueta: str) -> pd.DataFrame:
    """Cuenta una categoría y agrega su participación porcentual."""
    if df.empty or columna not in df:
        return pd.DataFrame(columns=[etiqueta, "cantidad", "porcentaje"])
    valores = df[columna].fillna("Sin dato").astype(str)
    salida = valores.value_counts(dropna=False).rename_axis(etiqueta).reset_index(name="cantidad")
    salida["porcentaje"] = (100 * salida["cantidad"] / len(df)).round(1)
    return salida


def resumen_flota(flota: pd.DataFrame, telemetria: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Distribuciones básicas de la flota y cobertura de dispositivos por estado."""
    cobertura = flota[["Dominio", "Estado"]].copy() if {"Dominio", "Estado"} <= set(flota) else pd.DataFrame()
    if not cobertura.empty:
        placas = (set(normalizar_dominio(telemetria["Placa"]).dropna())
                  if not telemetria.empty and "Placa" in telemetria else set())
        cobertura["telemetria"] = np.where(normalizar_dominio(cobertura["Dominio"]).isin(placas), "Con", "Sin")
        cobertura = (cobertura.groupby(["Estado", "telemetria"], dropna=False).size()
                     .reset_index(name="cantidad"))
    return {
        "estados": _conteo(flota, "Estado", "estado"),
        "tipos": _conteo(flota, "TipoVehiculo", "tipo_vehiculo"),
        "combustibles": _conteo(flota, "TipoCombustible", "combustible"),
        "telemetria_estado": cobertura,
    }


def preparar_cargas(
    consumo: pd.DataFrame,
    flota: pd.DataFrame,
    solicitudes: pd.DataFrame | None = None,
    gps_diario: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Enriquece cada carga con vehículo, tiempo, tanque y tramo de odómetro."""
    if consumo.empty:
        return consumo.copy()
    datos = consumo.copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce")
    datos["litros"] = pd.to_numeric(datos["litros"], errors="coerce")
    columnas_flota = [c for c in ["Matricula", "TipoVehiculo", "CapacidadTanque", "TipoCombustible"] if c in flota]
    if "Matricula" in columnas_flota:
        datos = datos.merge(flota[columnas_flota].drop_duplicates("Matricula"), how="left",
                            left_on="vehiculo_id", right_on="Matricula")
    datos["proporcion_tanque"] = datos["litros"] / pd.to_numeric(
        datos.get("CapacidadTanque"), errors="coerce")
    datos["mes"] = datos["fecha"].dt.to_period("M").astype("string")
    datos["dia_semana"] = datos["fecha"].dt.day_name().map({
        "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
        "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo",
    })
    if "hora" in datos:
        datos["hora_del_dia"] = pd.to_numeric(datos["hora"].astype("string").str.slice(0, 2), errors="coerce")
    else:
        datos["hora_del_dia"] = np.nan

    fuera = cargas_fuera_del_reporte(solicitudes) if solicitudes is not None else None
    if {"id", "vehiculo_id", "odometro", "fecha"} <= set(consumo):
        secuencia = secuencia_odometro(consumo, fuera=fuera)
        datos = datos.merge(secuencia[["id", "km"]].drop_duplicates("id"), on="id", how="left")
        datos["rendimiento_km_l"] = datos["km"].where(datos["km"] >= 0) / datos["litros"]
    else:
        datos["km"] = np.nan
        datos["rendimiento_km_l"] = np.nan

    # Reutiliza el resumen diario del motor de reglas; se conserva aparte del km/L por carga.
    if {"id", "vehiculo_id", "odometro", "fecha", "litros"} <= set(consumo) and "Matricula" in flota:
        diario = cargas_por_dia(consumo, flota, gps_diario=gps_diario, fuera=fuera)
        por_id = diario.explode("ids")[["ids", "rendimiento_odometro", "rendimiento_gps"]]
        por_id = por_id.rename(columns={"ids": "id"}).drop_duplicates("id")
        datos = datos.merge(por_id, on="id", how="left")
    return datos


def resumen_cargas(cargas: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Distribuciones operativas de volumen, tanque, distancia y rendimiento."""
    tipo = "TipoVehiculo" if "TipoVehiculo" in cargas else None
    if tipo:
        litros = (cargas.groupby(tipo, dropna=False)["litros"].agg(cargas="size", litros_mediana="median",
                                                                   litros_total="sum").reset_index())
    else:
        litros = pd.DataFrame(columns=["TipoVehiculo", "cargas", "litros_mediana", "litros_total"])
    variables = [c for c in ["proporcion_tanque", "km", "rendimiento_km_l"] if c in cargas]
    percentiles = (cargas[variables].quantile([.05, .25, .5, .75, .95]).rename_axis("percentil").reset_index()
                   if variables else pd.DataFrame())
    return {"por_tipo": litros, "percentiles": percentiles}


def resumen_temporal(cargas: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Cantidad de cargas y litros por mes, día de semana y hora."""
    resultado = {}
    for columna in ["mes", "dia_semana", "hora_del_dia"]:
        if columna not in cargas or cargas[columna].dropna().empty:
            resultado[columna] = pd.DataFrame(columns=[columna, "cargas", "litros"])
        else:
            resultado[columna] = (cargas.dropna(subset=[columna]).groupby(columna, observed=True)
                                  .agg(cargas=("id", "size"), litros=("litros", "sum")).reset_index())
    orden = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    if not resultado["dia_semana"].empty:
        resultado["dia_semana"]["dia_semana"] = pd.Categorical(
            resultado["dia_semana"]["dia_semana"], categories=orden, ordered=True)
        resultado["dia_semana"] = resultado["dia_semana"].sort_values("dia_semana")
    return resultado


def resumen_calidad(fuentes: dict[str, pd.DataFrame], flota: pd.DataFrame, consumo: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Completitud, unicidad y capacidad de vinculación de las fuentes observadas."""
    filas = []
    for fuente, df in fuentes.items():
        if df is None or df.empty:
            continue
        for columna in df.columns:
            filas.append({
                "fuente": fuente, "columna": columna, "filas": len(df),
                "completitud_pct": round(100 * df[columna].notna().mean(), 1),
                "valores_unicos": int(df[columna].nunique(dropna=True)),
                "unicidad_pct": round(100 * df[columna].nunique(dropna=True) / len(df), 1),
            })
    calidad = pd.DataFrame(filas)

    vinculacion = pd.DataFrame(columns=["criterio", "vinculadas", "total", "porcentaje"])
    formatos = pd.DataFrame(columns=["formato", "cantidad", "porcentaje"])
    if not consumo.empty and "dominio" in consumo and "Dominio" in flota:
        personales = consumo.get("tipo_identificacion", pd.Series("PATENTE", index=consumo.index)).eq("DNI")
        evaluar = consumo.loc[~personales, "dominio"]
        flota_raw = set(flota["Dominio"].dropna().astype(str))
        flota_norm = set(normalizar_dominio(flota["Dominio"]).dropna())
        raw = evaluar.astype(str).isin(flota_raw)
        norm = normalizar_dominio(evaluar).isin(flota_norm)
        vinculacion = pd.DataFrame([
            {"criterio": "Formato original", "vinculadas": int(raw.sum()), "total": len(evaluar),
             "porcentaje": round(100 * raw.mean(), 1) if len(evaluar) else np.nan},
            {"criterio": "Dominio normalizado (H1)", "vinculadas": int(norm.sum()), "total": len(evaluar),
             "porcentaje": round(100 * norm.mean(), 1) if len(evaluar) else np.nan},
        ])
        texto = evaluar.fillna("").astype(str)
        clase = np.select([
            texto.str.fullmatch(r"[A-Z]{3}\d{3}"), texto.str.fullmatch(r"[A-Z]{2}\d{3}[A-Z]{2}"),
            texto.str.fullmatch(r"[A-Za-z0-9 ._-]+")],
            ["Patente antigua", "Patente Mercosur", "Variante normalizable"], default="Otro/inválido")
        formatos = pd.Series(clase).value_counts().rename_axis("formato").reset_index(name="cantidad")
        formatos["porcentaje"] = (100 * formatos["cantidad"] / len(evaluar)).round(1)
    return {"columnas": calidad, "vinculacion": vinculacion, "formatos_dominio": formatos}


def resumen_cruces(
    consumo: pd.DataFrame,
    flota: pd.DataFrame,
    solicitudes: pd.DataFrame | None,
    gps_diario: pd.DataFrame | None,
    facturacion_detalle: pd.DataFrame | None,
) -> pd.DataFrame:
    """Coberturas descriptivas del circuito pedido → carga → recorrido → factura."""
    filas = []
    total = len(consumo)
    if solicitudes is not None and not solicitudes.empty and "hora" in solicitudes:
        cruce, _ = cruzar_registro(consumo, solicitudes, flota=flota)
        cubiertas = int(cruce["registro_id"].notna().sum())
        filas.append({"tramo": "Pedido → carga", "cubiertas": cubiertas, "total": total,
                      "cobertura_pct": round(100 * cubiertas / total, 1) if total else np.nan})
    if gps_diario is not None and not gps_diario.empty and "Placa" in gps_diario:
        dias = set(zip(normalizar_dominio(gps_diario["Placa"]), pd.to_datetime(gps_diario["fecha"]).dt.normalize()))
        placas = consumo["vehiculo_id"].map(flota.set_index("Matricula")["Dominio"])
        fechas = pd.to_datetime(consumo["fecha"]).dt.normalize()
        cubiertas = sum((p, f) in dias for p, f in zip(normalizar_dominio(placas), fechas))
        filas.append({"tramo": "Carga → GPS diario", "cubiertas": int(cubiertas), "total": total,
                      "cobertura_pct": round(100 * cubiertas / total, 1) if total else np.nan})
    if facturacion_detalle is not None and not facturacion_detalle.empty and "referencia_consumo" in facturacion_detalle:
        refs = set(facturacion_detalle["referencia_consumo"].dropna().astype(str))
        cubiertas = int(consumo["id"].astype(str).isin(refs).sum())
        filas.append({"tramo": "Carga → línea facturada", "cubiertas": cubiertas, "total": total,
                      "cobertura_pct": round(100 * cubiertas / total, 1) if total else np.nan})
    return pd.DataFrame(filas, columns=["tramo", "cubiertas", "total", "cobertura_pct"])


def comparacion_auditoria(auditoria: dict | str | Path) -> pd.DataFrame:
    """Convierte los percentiles aprobados de real vs. sintético a formato largo."""
    if isinstance(auditoria, (str, Path)):
        with open(auditoria, encoding="utf-8") as archivo:
            auditoria = json.load(archivo)
    variables = auditoria.get("modelos", {}).get("variables", {})
    filas = []
    for variable, valores in variables.items():
        for percentil in ["p05", "p50", "p95"]:
            real = valores.get("real", {}).get(percentil)
            sintetico = valores.get("sintetico", {}).get(percentil)
            if real is not None and sintetico is not None:
                filas.append({"variable": variable, "percentil": percentil, "real": real,
                              "sintetico": sintetico, "diferencia": sintetico - real})
    return pd.DataFrame(filas)
