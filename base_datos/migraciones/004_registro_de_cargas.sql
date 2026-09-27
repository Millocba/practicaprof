-- 004 · Registro de cada carga de datos: cuándo, desde qué directorio, hasta qué fecha y cuántas
-- filas por tabla. Da trazabilidad a las cargas incrementales.
--
-- Compatibilidad: tabla nueva; no modifica las demás.
-- Bloqueo esperado: ninguno.
-- Vuelta atrás: DROP TABLE carga_de_datos.
-- Verificación: después de una carga, la última fila tiene las filas por tabla.

CREATE TABLE carga_de_datos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instante        TEXT NOT NULL,
    origen          TEXT NOT NULL,
    hasta           TEXT,                 -- NULL: todo el período
    semilla         INTEGER,
    filas_por_tabla TEXT NOT NULL         -- JSON {tabla: filas en la base después de la carga}
);
