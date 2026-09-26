-- 001 · Datos maestros: cambian poco y se versionan con vigencia.
--
-- Compatibilidad: base nueva; no modifica tablas existentes.
-- Bloqueo esperado: ninguno (se crea en una base vacía, dentro de una transacción).
-- Vuelta atrás: DROP TABLE de las tablas de este archivo, en orden inverso.
-- Verificación: PRAGMA foreign_key_check sin filas y las tablas presentes en sqlite_master.

CREATE TABLE contrato (
    indice          INTEGER PRIMARY KEY,
    numero          TEXT NOT NULL UNIQUE,
    etiqueta        TEXT NOT NULL,
    limite_mensual  REAL NOT NULL CHECK (limite_mensual > 0)
);

CREATE TABLE dependencia (
    codigo             TEXT PRIMARY KEY,
    direccion_general  TEXT NOT NULL
);

CREATE TABLE vehiculo (
    matricula         TEXT PRIMARY KEY,
    dominio           TEXT NOT NULL UNIQUE,
    tipo              TEXT NOT NULL,
    marca             TEXT,
    modelo            TEXT,
    anio              INTEGER,
    combustible       TEXT NOT NULL,
    capacidad_tanque  REAL NOT NULL CHECK (capacidad_tanque > 0),
    identificable     TEXT CHECK (identificable IN ('SI', 'NO')),
    dependencia       TEXT REFERENCES dependencia (codigo)
);

-- Historia de estados: EN SERVICIO hasta la fecha del último cambio, y desde ahí el estado actual
CREATE TABLE estado_vehiculo (
    matricula  TEXT NOT NULL REFERENCES vehiculo (matricula),
    estado     TEXT NOT NULL,
    subestado  TEXT,
    desde      TEXT NOT NULL DEFAULT '1900-01-01',   -- 1900-01-01: desde antes del período
    hasta      TEXT,                                  -- NULL: vigente
    PRIMARY KEY (matricula, estado, desde)
);

-- Tarjetas de combustible: de un vehículo o personales, siempre de un contrato
CREATE TABLE tarjeta (
    numero         TEXT PRIMARY KEY,
    tipo           TEXT NOT NULL CHECK (tipo IN ('VEHICULO', 'PERSONAL')),
    contrato       INTEGER NOT NULL REFERENCES contrato (indice),
    cupo_litros    REAL,      -- litros por carga
    limite_litros  REAL,      -- mensual, fijado al registrar la tarjeta
    limite_saldo   REAL       -- mensual, fijado al registrar la tarjeta
);

CREATE TABLE asignacion_tarjeta (
    tarjeta    TEXT NOT NULL REFERENCES tarjeta (numero),
    matricula  TEXT REFERENCES vehiculo (matricula),   -- tarjeta de vehículo
    persona    TEXT,                                   -- tarjeta personal
    desde      TEXT NOT NULL DEFAULT '1900-01-01',
    hasta      TEXT,
    PRIMARY KEY (tarjeta, desde),
    CHECK ((matricula IS NULL) <> (persona IS NULL))
);

CREATE TABLE estacion (
    codigo     TEXT PRIMARY KEY,
    marca      TEXT,
    ubicacion  TEXT CHECK (ubicacion IN ('LOCAL', 'RUTA')),
    latitud    REAL,
    longitud   REAL
);

CREATE TABLE dispositivo (
    alias            TEXT PRIMARY KEY,
    imei             TEXT NOT NULL UNIQUE,
    msisdn           TEXT,
    modelo           TEXT,
    grupo            TEXT,
    estado           TEXT CHECK (estado IN ('ONLINE', 'OFFLINE')),
    ultima_conexion  TEXT,
    bateria          REAL
);

CREATE TABLE asignacion_dispositivo (
    dispositivo  TEXT NOT NULL REFERENCES dispositivo (alias),
    matricula    TEXT NOT NULL REFERENCES vehiculo (matricula),
    desde        TEXT NOT NULL DEFAULT '1900-01-01',
    hasta        TEXT,
    PRIMARY KEY (dispositivo, desde)
);
