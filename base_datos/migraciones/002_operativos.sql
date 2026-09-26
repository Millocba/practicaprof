-- 002 · Datos operativos: crecen todos los días y se cargan de forma repetible (por clave).
--
-- Compatibilidad: requiere 001; no modifica tablas existentes.
-- Bloqueo esperado: ninguno (tablas nuevas, dentro de una transacción).
-- Vuelta atrás: DROP TABLE de las tablas de este archivo, en orden inverso.
-- Verificación: PRAGMA foreign_key_check sin filas.

-- Reporte del proveedor: una fila por carga
CREATE TABLE carga (
    id                   TEXT PRIMARY KEY,
    fecha                TEXT NOT NULL,          -- AAAA-MM-DD
    hora                 TEXT,                   -- HH:MM:SS
    tarjeta              TEXT NOT NULL REFERENCES tarjeta (numero),
    matricula            TEXT REFERENCES vehiculo (matricula),
    tipo_identificacion  TEXT CHECK (tipo_identificacion IN ('PATENTE', 'DNI')),
    dominio_informado    TEXT,                   -- tal como llega: puede no coincidir con el vehículo
    conductor            TEXT,
    estacion             TEXT REFERENCES estacion (codigo),
    producto             TEXT NOT NULL,
    litros               REAL NOT NULL CHECK (litros > 0),
    precio_unitario      REAL NOT NULL,          -- del surtidor
    importe              REAL NOT NULL,
    odometro             INTEGER,
    contrato             INTEGER NOT NULL REFERENCES contrato (indice)
);
CREATE INDEX carga_contrato_fecha ON carga (contrato, fecha);
CREATE INDEX carga_matricula_fecha ON carga (matricula, fecha);

-- Registro interno: pedido y rendición. No comparte clave con el reporte: se cruza por dominio y horario
CREATE TABLE pedido (
    id                  TEXT PRIMARY KEY,
    matricula           TEXT NOT NULL REFERENCES vehiculo (matricula),
    dominio             TEXT,
    fecha               TEXT NOT NULL,           -- AAAA-MM-DD (la fuente la trae como DD/MM/AAAA)
    hora                TEXT,
    odometro            INTEGER,
    solicitante         TEXT,
    tarjeta_personal    INTEGER NOT NULL CHECK (tarjeta_personal IN (0, 1)),
    litros_autorizados  REAL,
    litros_cargados     REAL,
    nivel_tanque        TEXT,
    rendido             TEXT CHECK (rendido IN ('SI', 'NO')),
    fecha_rendicion     TEXT,
    hora_rendicion      TEXT,
    numero_ticket       TEXT,
    anulado             TEXT CHECK (anulado IN ('SI', 'NO')),
    fecha_anulado       TEXT,
    estacion_servicio   TEXT,                    -- código de estación o ESTACION AJENA
    bandera_rendicion   TEXT,
    relacion_consumo    TEXT
);
CREATE INDEX pedido_dominio_fecha ON pedido (dominio, fecha);

CREATE TABLE transferencia (
    id                TEXT PRIMARY KEY,
    fecha             TEXT NOT NULL,
    contrato_origen   INTEGER NOT NULL REFERENCES contrato (indice),
    contrato_destino  INTEGER NOT NULL REFERENCES contrato (indice),
    monto             REAL NOT NULL CHECK (monto > 0),
    CHECK (contrato_origen <> contrato_destino)
);

CREATE TABLE factura (
    numero       TEXT PRIMARY KEY,
    contrato     INTEGER NOT NULL REFERENCES contrato (indice),
    proveedor    TEXT,
    producto     TEXT CHECK (producto IN ('DIESEL', 'NAFTA')),
    periodo      TEXT NOT NULL,                  -- AAAA-MM
    fecha        TEXT NOT NULL,
    vencimiento  TEXT,
    total_monto  REAL NOT NULL,                  -- deuda, a precio de empresa
    total_pdf    REAL,                           -- NULL si el PDF no se cargó
    total_litros REAL,
    estado       TEXT
);

-- La referencia a la carga no es clave foránea a propósito: una línea que factura una carga
-- inexistente es justamente lo que se audita (vista linea_sin_carga)
CREATE TABLE factura_linea (
    numero_linea     TEXT PRIMARY KEY,
    factura          TEXT NOT NULL REFERENCES factura (numero),
    referencia_carga TEXT,
    concepto         TEXT NOT NULL,              -- COMBUSTIBLE, AJUSTE o LUBRICANTE
    fecha            TEXT,
    litros           REAL,
    precio_unitario  REAL,                       -- de empresa
    importe          REAL NOT NULL,
    descripcion      TEXT
);
CREATE INDEX factura_linea_referencia ON factura_linea (referencia_carga);

CREATE TABLE posicion_diaria (
    matricula  TEXT NOT NULL REFERENCES vehiculo (matricula),
    fecha      TEXT NOT NULL,
    km_gps     REAL,
    lat_inicio REAL, lon_inicio REAL, lat_fin REAL, lon_fin REAL,
    PRIMARY KEY (matricula, fecha)
);
