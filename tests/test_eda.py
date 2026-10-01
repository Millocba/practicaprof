"""Pruebas unitarias del EDA con tablas pequeñas construidas a mano."""
import pandas as pd

from streamlit_app.utils.eda import (
    comparacion_auditoria,
    preparar_cargas,
    resumen_calidad,
    resumen_cruces,
    resumen_flota,
    resumen_temporal,
)


def tablas_minimas():
    flota = pd.DataFrame({
        "Matricula": [1, 2], "Dominio": ["AA123BB", "ABC123"], "Estado": ["EN SERVICIO", "BAJA"],
        "TipoVehiculo": ["AUTO", "CAMIONETA"], "TipoCombustible": ["NAFTA", "DIESEL"],
        "CapacidadTanque": [50.0, 80.0], "NumeroTarjeta": ["T1", "T2"],
    })
    consumo = pd.DataFrame({
        "id": ["C1", "C2", "C3"], "vehiculo_id": [1, 1, 2],
        "dominio": ["aa-123-bb", "AA123BB", "ABC123"],
        "fecha": ["2026-01-01", "2026-01-03", "2026-01-02"],
        "hora": ["08:00:00", "09:00:00", "10:00:00"],
        "litros": [20.0, 25.0, 40.0], "odometro": [1000.0, 1200.0, 3000.0],
        "numero_tarjeta": ["T1", "T1", "T2"], "conductor": ["A", "A", "B"],
        "tipo_identificacion": ["PATENTE"] * 3,
    })
    telemetria = pd.DataFrame({"Placa": ["AA123BB"], "Estado": ["ACTIVO"]})
    return flota, consumo, telemetria


def test_flota_y_cargas_producen_resumenes_reproducibles():
    flota, consumo, telemetria = tablas_minimas()
    resumen = resumen_flota(flota, telemetria)
    assert resumen["estados"]["cantidad"].sum() == 2
    assert set(resumen["telemetria_estado"]["telemetria"]) == {"Con", "Sin"}

    cargas = preparar_cargas(consumo, flota)
    assert cargas.loc[cargas["id"] == "C2", "km"].iloc[0] == 200
    assert cargas["proporcion_tanque"].round(2).tolist() == [.4, .5, .5]
    assert resumen_temporal(cargas)["mes"]["cargas"].sum() == 3


def test_calidad_mide_la_mejora_de_h1_sin_usar_etiquetas():
    flota, consumo, _ = tablas_minimas()
    calidad = resumen_calidad({"flota": flota, "consumo": consumo}, flota, consumo)
    tasas = calidad["vinculacion"].set_index("criterio")["vinculadas"]
    assert tasas["Formato original"] == 2
    assert tasas["Dominio normalizado (H1)"] == 3
    assert not calidad["columnas"].empty


def test_cruces_describen_cobertura_sin_emitir_veredicto():
    flota, consumo, _ = tablas_minimas()
    solicitudes = pd.DataFrame({
        "id": ["S1", "S2", "S3"], "vehiculo_id": [1, 1, 2], "dominio": ["AA123BB", "AA123BB", "ABC123"],
        "fecha": consumo["fecha"], "hora": ["07:30:00", "08:30:00", "09:30:00"],
        "solicitante": ["A", "A", "B"], "tarjeta_personal": [False] * 3,
        "litros_autorizados": [20.0, 25.0, 40.0], "litros_cargados": [20.0, 25.0, 40.0],
        "rendido": ["SI"] * 3, "anulado": ["NO"] * 3, "estacion_servicio": ["RED"] * 3,
        "odometro": [1000.0, 1200.0, 3000.0],
    })
    detalle = pd.DataFrame({"referencia_consumo": ["C1", "C3"]})
    cruces = resumen_cruces(consumo, flota, solicitudes, None, detalle)
    assert set(cruces["tramo"]) == {"Pedido → carga", "Carga → línea facturada"}
    assert cruces.loc[cruces["tramo"] == "Carga → línea facturada", "cubiertas"].iloc[0] == 2


def test_comparacion_usa_solo_percentiles_aprobados():
    auditoria = {"modelos": {"variables": {"km": {
        "real": {"p05": 1, "p50": 2, "p95": 3},
        "sintetico": {"p05": 1.5, "p50": 2, "p95": 4},
    }}}}
    tabla = comparacion_auditoria(auditoria)
    assert tabla["percentil"].tolist() == ["p05", "p50", "p95"]
    assert "min" not in set(tabla["percentil"])
