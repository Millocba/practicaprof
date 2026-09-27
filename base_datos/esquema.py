"""Esquema de la base: migraciones SQL numeradas, aplicadas en orden y una sola vez."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRACIONES = Path(__file__).parent / "migraciones"


def conectar(ruta):
    """Conexión con claves foráneas activas. `ruta` puede ser ':memory:'."""
    conexion = sqlite3.connect(ruta)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def migraciones_disponibles():
    return sorted(MIGRACIONES.glob("[0-9][0-9][0-9]_*.sql"))


def aplicadas(conexion):
    conexion.execute("CREATE TABLE IF NOT EXISTS migracion (version TEXT PRIMARY KEY, nombre TEXT NOT NULL, "
                     "aplicada TEXT NOT NULL)")
    return {v for (v,) in conexion.execute("SELECT version FROM migracion")}


def migrar(conexion):
    """Aplica las migraciones pendientes, cada una en su propia transacción. Devuelve las aplicadas."""
    hechas = aplicadas(conexion)
    nuevas = []
    for archivo in migraciones_disponibles():
        version = archivo.name[:3]
        if version in hechas:
            continue
        with conexion:
            conexion.executescript("BEGIN;\n" + archivo.read_text(encoding="utf-8") + "\n"
                                   f"INSERT INTO migracion VALUES ('{version}', '{archivo.stem}', "
                                   f"'{datetime.now(timezone.utc).isoformat(timespec='seconds')}');\nCOMMIT;")
        nuevas.append(archivo.stem)
    return nuevas


def verificar(conexion):
    """Integridad referencial y de la base: devuelve una lista de problemas (vacía si está bien)."""
    problemas = [f"{tabla}: fila {fila} rompe la clave hacia {padre}"
                 for tabla, fila, padre, _ in conexion.execute("PRAGMA foreign_key_check")]
    problemas += [r for (r,) in conexion.execute("PRAGMA integrity_check") if r != "ok"]
    return problemas
