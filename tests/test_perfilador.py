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
    aprobar_archivo,
    dos_cifras,
    formato,
    leer_tablas,
    perfilar,
    perfilar_columna,
    resumir_formatos_largos,
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


def test_organizacion_geografia_y_codigos_son_sensibles():
    n = 200
    df = pd.DataFrame({
        "Dependencia": [f"U.O.S. {i % 3} - AREA SINTETICA NUMERO {i % 3}" for i in range(n)],
        "DependeciaMovil": [f"UNIDAD {i % 4}" for i in range(n)],
        "CONTRATO": [f"CTR SINTETICO {i % 2}" for i in range(n)],
        "PROVINCIA": ["PROVINCIA_SINTETICA"] * n,
        "LOCALIDAD": [f"LOCALIDAD_{i % 5}" for i in range(n)],
        "Solicitante": [f"PERSONA {i % 5}" for i in range(n)],
        "Lote": [f"{1000000000 + i % 4}-{2000000000 + i % 4}-{i % 4:08d}" for i in range(n)],
    })
    perfil = perfilar({"t": df})
    columnas = {c["nombre"]: c for c in perfil["tablas"]["t"]["perfil_columnas"]}
    assert columnas["Dependencia"]["sensible"] == "organizacion"
    assert columnas["DependeciaMovil"]["sensible"] == "organizacion"
    assert columnas["CONTRATO"]["sensible"] == "organizacion"
    assert columnas["PROVINCIA"]["sensible"] == "ubicacion"
    assert columnas["LOCALIDAD"]["sensible"] == "ubicacion"
    assert columnas["Solicitante"]["sensible"] == "persona"
    assert columnas["Lote"]["sensible"] == "identificador"  # detectado por el formato, no por el nombre
    assert all("categorias" not in c for c in columnas.values())
    texto = json.dumps(perfil, ensure_ascii=False)
    for valor in ["AREA SINTETICA", "CTR SINTETICO", "PROVINCIA_SINTETICA", "LOCALIDAD_0", "1000000000"]:
        assert valor not in texto
    precio = perfilar_columna("PRECIO ESTABLECIMIENTO", pd.Series(np.arange(1000, 1100)))
    assert precio["sensible"] is None and precio["numerico"]["p50"] is not None
    # el formato largo de Dependencia se resume por su largo
    assert [f["formato"] for f in columnas["Dependencia"]["formatos"]] == ["TEXTO_21-40"]


def test_resumir_formatos_largos_suma_por_banda():
    formatos = [{"formato": "A" * 25, "pct": 30.0}, {"formato": "A" * 30, "pct": 20.0},
                {"formato": "A" * 45, "pct": 10.0}, {"formato": "AA999AA", "pct": 35.0}, {"formato": OTRA, "pct": 5.0}]
    assert resumir_formatos_largos(formatos) == [
        {"formato": "TEXTO_21-40", "pct": 50.0}, {"formato": "AA999AA", "pct": 35.0},
        {"formato": "TEXTO_MAS_DE_40", "pct": 10.0}, {"formato": OTRA, "pct": 5.0}]


def test_cuantiles_redondeados():
    assert dos_cifras(123456) == 120000
    assert dos_cifras(0.0347) == 0.035
    c = perfilar_columna("Importe", pd.Series(np.arange(1000, 1100)))
    assert all(v == dos_cifras(v) for v in c["numerico"].values() if isinstance(v, float) and v > 100)


def test_cuantiles_de_las_colas_se_suprimen_con_pocos_datos():
    # 100 valores: p05 y p95 dejarían 5 observaciones afuera y quedarían pegados a los extremos
    chica = perfilar_columna("Importe", pd.Series(np.arange(100)))["numerico"]
    assert chica["p05"] is None and chica["p95"] is None
    assert chica["p25"] is not None and chica["p50"] is not None
    # 400 valores: todas las colas tienen al menos MINIMO_GRUPO observaciones
    grande = perfilar_columna("Importe", pd.Series(np.arange(400)))["numerico"]
    assert all(grande[k] is not None for k in ["p05", "p25", "p50", "p75", "p95"])
    assert grande["p95"] != 399 and grande["p05"] != 0


def test_aprobar_archivo_registra_revisor_y_mueve(tmp_path, perfil):
    pendiente = tmp_path / "pendientes" / "perfil_x.json"
    pendiente.parent.mkdir()
    pendiente.write_text(json.dumps(perfil), encoding="utf-8")
    destino = aprobar_archivo(pendiente, tmp_path / "aprobados", "Revisora", "sin observaciones")
    assert not pendiente.exists() and destino == tmp_path / "aprobados" / "perfil_x.json"
    revision = json.loads(destino.read_text(encoding="utf-8"))["revision"]
    assert revision["revisado"] and revision["responsable"] == "Revisora"
    assert revision["notas"] == "sin observaciones"


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


def test_pagina_muestra_resumen_y_permite_aprobar(monkeypatch, perfil):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PERFILADOR_PERMITIR_ARCHIVOS", "1")
    at = AppTest.from_file(str(RAIZ / "streamlit_app" / "pages" / "04_perfil_de_fuentes.py"), default_timeout=60)
    at.session_state["perfil_generado"] = perfil
    at.run()
    assert not at.exception
    assert any(m.label == "Faltantes promedio por columna" for m in at.metric)
    assert at.button(key="aprobar_generado").disabled
    at.text_input(key="revisor_generado").input("Revisora").run()
    assert not at.button(key="aprobar_generado").disabled


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
