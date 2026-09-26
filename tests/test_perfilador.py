"""Tests del perfilador: el perfil describe estructura y calidad sin filtrar valores.

Todos los datos se generan en el test (sintéticos).
"""
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

from perfilador.comparar import comparar, sugerir_emparejamiento  # noqa: E402
from perfilador.perfil import (  # noqa: E402
    MINIMO_GRUPO,
    OTRA,
    dos_cifras,
    formato,
    leer_tablas,
    perfilar,
    perfilar_columna,
)


@pytest.fixture(scope="module")
def tablas():
    rng = np.random.default_rng(7)
    n = 400
    dominios = [f"ZZ{i:03d}QQ" for i in range(n)]
    vehiculos = pd.DataFrame({
        "Dominio": dominios,
        "Marca": rng.choice(["MARCA_A", "MARCA_B", "MARCA_C"], n).tolist(),
        "Modelo": ["MODELO_RARO_UNICO" if i < 5 else "MODELO_COMUN" for i in range(n)],  # grupo de 5
        "Chofer": [f"PERSONA_SINTETICA_{i}" for i in range(n)],
        "Latitud": rng.uniform(-35, -30, n).round(6),
        "Odometro": rng.integers(10_000, 300_000, n),
    })
    m = 1200
    cargas = pd.DataFrame({
        "id_carga": np.arange(1, m + 1),
        # la mitad escrita con espacio y en minúsculas: solo coincide después de normalizar
        "dominio": [d if i % 2 else d.lower()[:2] + " " + d.lower()[2:] for i, d in
                    enumerate(rng.choice(dominios, m))],
        "Fecha": pd.date_range("2025-01-01", periods=m, freq="6h").strftime("%d/%m/%Y"),
        "Litros": rng.uniform(10, 80, m).round(2),
        "Observaciones": [f"texto libre sintético número {i} con detalle largo" for i in range(m)],
    })
    return {"vehiculos": vehiculos, "cargas": cargas}


@pytest.fixture(scope="module")
def perfil(tablas):
    return perfilar(tablas, origen="prueba")


def columna(perfil, tabla, nombre):
    return next(c for c in perfil["tablas"][tabla]["perfil_columnas"] if c["nombre"] == nombre)


def test_no_filtra_valores_sensibles(perfil, tablas):
    texto = json.dumps(perfil, ensure_ascii=False)
    for valor in ["ZZ000QQ", "zz 001qq", "PERSONA_SINTETICA_0", "texto libre sintético", "MODELO_RARO_UNICO"]:
        assert valor not in texto
    lat = f"{tablas['vehiculos']['Latitud'].iloc[0]:.6f}"
    assert lat not in texto


def test_detecta_columnas_sensibles(perfil):
    assert columna(perfil, "vehiculos", "Dominio")["sensible"] == "vehiculo"
    assert columna(perfil, "vehiculos", "Chofer")["sensible"] == "persona"
    assert columna(perfil, "vehiculos", "Latitud")["sensible"] == "ubicacion"
    assert columna(perfil, "cargas", "Observaciones")["sensible"] == "texto libre"
    for nombre in ["Dominio", "Chofer", "Latitud"]:
        c = columna(perfil, "vehiculos", nombre)
        assert "categorias" not in c and "numerico" not in c


def test_formatos_y_tipos(perfil):
    assert columna(perfil, "vehiculos", "Dominio")["formatos"][0]["formato"] == "AA999AA"
    assert columna(perfil, "cargas", "Fecha")["tipo"] == "fecha como texto"
    odometro = columna(perfil, "vehiculos", "Odometro")
    assert odometro["tipo"] == "entero" and odometro["sensible"] is None
    assert "min" not in odometro["numerico"] and "max" not in odometro["numerico"]
    assert columna(perfil, "cargas", "Litros")["tipo"] == "decimal"
    assert formato("AB 123 cd") == "AA 999 AA"


def test_grupos_chicos_se_suprimen(perfil):
    categorias = columna(perfil, "vehiculos", "Modelo")["categorias"]
    assert all(c["valor"] in {"MODELO_COMUN", OTRA} for c in categorias)
    marcas = {c["valor"] for c in columna(perfil, "vehiculos", "Marca")["categorias"]}
    assert marcas == {"MARCA_A", "MARCA_B", "MARCA_C"}


def test_cuantiles_redondeados():
    assert dos_cifras(123456) == 120000
    assert dos_cifras(0.0347) == 0.035
    c = perfilar_columna("Importe", pd.Series(np.arange(1000, 1100)))
    assert all(v == dos_cifras(v) for v in c["numerico"].values() if isinstance(v, float) and v > 100)


def test_tabla_chica_sin_estadisticas():
    c = perfilar_columna("Importe", pd.Series(range(MINIMO_GRUPO - 1)))
    assert c["tipo"] == "desconocido" and "numerico" not in c
    p = perfilar({"chica": pd.DataFrame({"a": range(5)})})
    assert p["tablas"]["chica"]["filas_aprox"] is None


def test_relacion_exacta_y_normalizada(perfil):
    rel = next(r for r in perfil["relaciones"] if r["origen"] == "cargas.dominio")
    assert rel["destino"] == "vehiculos.Dominio"
    assert rel["cobertura_normalizada_pct"] == 100.0
    assert 40 <= rel["cobertura_exacta_pct"] <= 60


def test_lee_csv_con_punto_y_coma_y_ceros_a_la_izquierda():
    csv = "codigo;litros\n" + "\n".join(f"{i:05d};{i * 1.5}" for i in range(30))
    df = leer_tablas(io.BytesIO(csv.encode()), "cargas.csv")["cargas"]
    assert list(df.columns) == ["codigo", "litros"]
    assert df["codigo"].dtype == object and pd.api.types.is_numeric_dtype(df["litros"])


def test_comparador_detecta_brechas(perfil, tablas):
    sintetico = dict(tablas)
    sintetico["cargas"] = tablas["cargas"].drop(columns=["Observaciones"]).assign(
        dominio=tablas["cargas"]["dominio"].str.upper().str.replace(" ", ""))
    perfil_sint = perfilar(sintetico, origen="sintético")
    emparejamiento = sugerir_emparejamiento(perfil, perfil_sint)
    assert emparejamiento == {"vehiculos": "vehiculos", "cargas": "cargas"}
    brechas = comparar(perfil, perfil_sint, emparejamiento)
    assert ((brechas["columna"] == "Observaciones") & (brechas["aspecto"].str.contains("no modelada"))).any()
    assert brechas["tabla_real"].eq("cargas").any()
    assert (brechas["aspecto"].str.contains("relaci", case=False)).any()


def test_cli_escribe_solo_el_perfil(tmp_path, tablas):
    fuente = tmp_path / "vehiculos.csv"
    tablas["vehiculos"].to_csv(fuente, index=False)
    salida = tmp_path / "perfil.json"
    antes = set(tmp_path.iterdir())
    subprocess.run([sys.executable, "-m", "perfilador", "perfilar", str(fuente), "--salida", str(salida)],
                   cwd=RAIZ, check=True, capture_output=True)
    assert set(tmp_path.iterdir()) - antes == {salida}
    assert "ZZ000QQ" not in salida.read_text(encoding="utf-8")


def test_pagina_sin_carga_de_archivos_fuera_de_local(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("PERFILADOR_PERMITIR_ARCHIVOS", raising=False)
    at = AppTest.from_file(str(RAIZ / "streamlit_app" / "pages" / "04_perfil_de_fuentes.py"), default_timeout=60).run()
    assert not at.exception
    assert any("deshabilitado" in w.value for w in at.warning)


def test_pagina_local_habilita_la_carga(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PERFILADOR_PERMITIR_ARCHIVOS", "1")
    at = AppTest.from_file(str(RAIZ / "streamlit_app" / "pages" / "04_perfil_de_fuentes.py"), default_timeout=60).run()
    assert not at.exception
    assert not any("deshabilitado" in w.value for w in at.warning)
    assert any("en memoria" in i.value for i in at.info)


def test_pagina_compara_un_perfil(monkeypatch, perfil):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PERFILADOR_PERMITIR_ARCHIVOS", "1")
    at = AppTest.from_file(str(RAIZ / "streamlit_app" / "pages" / "04_perfil_de_fuentes.py"), default_timeout=180)
    at.session_state["perfil_generado"] = perfil
    at.run()
    at.radio(key="vista_perfil").set_value("2️⃣ Comparar con el generador").run()
    at.selectbox(key="perfil_elegido").set_value("Recién generado (sin guardar)").run()
    assert not at.exception
    assert [m.label for m in at.metric][:3] == ["Altas", "Medias", "Bajas"]


def test_carpeta_agrupa_archivos_del_mismo_tipo_sin_guardar_sus_nombres(tmp_path, tablas):
    volumen = tmp_path / "volumen"
    (volumen / "uploads" / "2025-09").mkdir(parents=True)
    cargas = tablas["cargas"]
    for i, dia in enumerate(["2025-09-01", "2025-09-02", "2025-09-03"]):
        cargas.iloc[i * 400:(i + 1) * 400].to_csv(volumen / "uploads" / "2025-09" / f"consumo_{dia}.csv", index=False)
    tablas["vehiculos"].to_excel(volumen / "flota.xlsx", index=False)
    (volumen / "factura.pdf").write_bytes(b"%PDF-1.4")        # se ignora: no es CSV ni Excel
    (volumen / "roto.xlsx").write_bytes(b"no es un excel")      # se cuenta como no leído
    salida = tmp_path / "perfil.json"
    antes = {p: p.stat().st_mtime for p in volumen.rglob("*")}
    subprocess.run([sys.executable, "-m", "perfilador", "perfilar", str(volumen), "--salida", str(salida)],
                   cwd=RAIZ, check=True, capture_output=True)
    perfil = json.loads(salida.read_text(encoding="utf-8"))
    assert set(perfil["tablas"]) == {"consumo", "flota"}
    assert perfil["lectura"]["archivos_por_tabla"] == {"consumo": 3, "flota": 1}
    assert sum(perfil["lectura"]["no_leidos_por_error"].values()) == 1
    assert perfil["tablas"]["consumo"]["filas_aprox"] == 1200
    assert "2025-09-01" not in salida.read_text(encoding="utf-8")
    assert {p: p.stat().st_mtime for p in volumen.rglob("*")} == antes  # no escribe junto a los archivos


def test_nombres_opacos_se_agrupan_por_columnas_como_lotes_o_versiones(tmp_path, tablas):
    import os
    import uuid

    volumen = tmp_path / "volumen"
    volumen.mkdir()
    cargas, vehiculos = tablas["cargas"], tablas["vehiculos"]
    for i in range(3):  # lotes: cada archivo trae cargas distintas
        cargas.iloc[i * 400:(i + 1) * 400].to_csv(volumen / f"{uuid.uuid4()}.csv", index=False)
    for i, filas in enumerate([380, 390, 400]):  # versiones: el mismo padrón exportado tres veces
        ruta = volumen / f"{uuid.uuid4()}.csv"
        vehiculos.head(filas).to_csv(ruta, index=False)
        os.utime(ruta, (1_700_000_000 + i, 1_700_000_000 + i))
    cargas.head(100).drop(columns=["Observaciones"]).to_csv(volumen / "reporte ORGANIZACION_FICTICIA 01-02.csv",
                                                            index=False)
    salida = tmp_path / "perfil.json"
    subprocess.run([sys.executable, "-m", "perfilador", "perfilar", str(volumen), "--salida", str(salida),
                    "--renombrar", "reporte ORGANIZACION_FICTICIA=reporte_de_cargas"],
                   cwd=RAIZ, check=True, capture_output=True)
    perfil = json.loads(salida.read_text(encoding="utf-8"))
    lectura = perfil["lectura"]
    assert lectura["archivos_por_tabla"] == {"tabla_de_5_columnas": 3, "tabla_de_6_columnas": 3,
                                             "reporte_de_cargas": 1}
    assert lectura["combinacion_por_tabla"]["tabla_de_5_columnas"] == "lotes"
    assert lectura["combinacion_por_tabla"]["tabla_de_6_columnas"] == "versiones"
    assert perfil["tablas"]["tabla_de_5_columnas"]["filas_aprox"] == 1200
    assert perfil["tablas"]["tabla_de_6_columnas"]["filas_aprox"] == 400  # la versión más reciente
    assert "ORGANIZACION_FICTICIA" not in salida.read_text(encoding="utf-8")


def test_lotes_superpuestos_no_se_confunden_con_versiones():
    import pandas as pd
    from perfilador.perfil import combinar_archivos

    def lote(ids):
        return pd.DataFrame({"Id": [f"SOL-{i:06d}" for i in ids], "litros": [float(i % 50) for i in ids]})

    grande = lote(range(600))
    subconjuntos = [lote(range(k * 100, k * 100 + 80)) for k in range(5)]    # contenidos en el grande
    sueltos = [lote(range(1000 + k * 30, 1000 + (k + 1) * 30)) for k in range(4)]  # sin claves en común
    # El más reciente es un lote chico: no puede ganar como "versión"
    partes = [(1, grande)] + [(2 + i, s) for i, s in enumerate(subconjuntos)] + [(10 + i, s) for i, s in enumerate(sueltos)]
    tabla, modo, descartadas = combinar_archivos(partes)
    assert modo == "lotes"
    assert len(tabla) == 600 + 4 * 30 and tabla["Id"].is_unique
    assert descartadas == round(100 * 5 * 80 / (600 + 5 * 80 + 4 * 30), 1)


def test_copias_del_mismo_reporte_se_unen_y_los_nombres_se_neutralizan(tmp_path, tablas):
    volumen = tmp_path / "volumen"
    volumen.mkdir()
    cargas = tablas["cargas"].assign(Proveedor="PROVEEDOR_REAL_FICTICIO")
    nombres = ["ReporteConsumos.csv", "ReporteConsumos (1).csv", "ReporteConsumos (12) (3).csv",
               "ReporteConsumos - 2025-09-01T101530.123.csv"]
    for i, nombre in enumerate(nombres):
        cargas.iloc[i * 300:(i + 1) * 300].to_csv(volumen / nombre, index=False)
    salida = tmp_path / "perfil.json"
    subprocess.run([sys.executable, "-m", "perfilador", "perfilar", str(volumen), "--salida", str(salida),
                    "--reemplazar", "proveedor_real_ficticio=PROVEEDOR_1"],
                   cwd=RAIZ, check=True, capture_output=True)
    texto = salida.read_text(encoding="utf-8")
    perfil = json.loads(texto)
    assert perfil["lectura"]["archivos_por_tabla"] == {"ReporteConsumos": 4}
    assert perfil["tablas"]["ReporteConsumos"]["filas_aprox"] == 1200
    assert "PROVEEDOR_REAL_FICTICIO" not in texto.upper()
    proveedor = columna(perfil, "ReporteConsumos", "Proveedor")
    assert proveedor["categorias"][0]["valor"] == "PROVEEDOR_1" and proveedor["categorias"][0]["pct"] == 100.0
