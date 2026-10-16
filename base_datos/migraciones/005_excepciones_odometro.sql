-- 005 · Excepciones de odómetro (H12): hechos con vigencia, no atributos del vehículo. Mientras rige
-- una excepción, la lectura del odómetro puede repetirse; una excepción puede durar un solo día.
--
-- Compatibilidad: requiere 001 y 002; agrega una tabla y dos vistas, no modifica las existentes.
-- Bloqueo esperado: ninguno (tabla y vistas nuevas, dentro de una transacción).
-- Vuelta atrás: DROP VIEW odometro_sin_avance_sin_excepcion; DROP VIEW excepcion_vigente;
--               DROP TABLE excepcion_odometro; DELETE FROM migracion WHERE version = '005'.
-- Verificación: PRAGMA foreign_key_check sin filas, las vistas se pueden consultar y
--               `python -m base_datos verificar` sin problemas.

-- Historial de excepciones. La clave natural es el vehículo y la vigencia: `hasta` no admite NULL
-- para que la clave no deje pasar duplicados (en SQLite, dos NULL no chocan en un UNIQUE)
CREATE TABLE excepcion_odometro (
    id         TEXT PRIMARY KEY,                                     -- EXC-NNNN, el de la fuente
    matricula  TEXT NOT NULL REFERENCES vehiculo (matricula),        -- resuelta por el dominio
    motivo     TEXT NOT NULL,
    activo     TEXT NOT NULL CHECK (activo IN ('SI', 'NO')),
    desde      TEXT NOT NULL,                                        -- AAAA-MM-DD
    hasta      TEXT NOT NULL,                                        -- último día en que rige
    UNIQUE (matricula, desde, hasta),
    CHECK (desde <= hasta)
);

-- Estado de hoy, como lo muestra el padrón (ExcepcionOdometro = SI y FechaHastaExcepcionOdometro)
CREATE VIEW excepcion_vigente AS
SELECT matricula, id, motivo, desde, hasta
FROM excepcion_odometro
WHERE activo = 'SI';

-- Cargas cuya lectura del odómetro es igual a la de la carga anterior del vehículo, en otro día, sin una
-- excepción vigente ese día (regla sin_avance_sin_excepcion de H12). La secuencia de cada vehículo
-- intercala las cargas en estaciones de otra red que anota el registro interno (pedidos rendidos y no
-- anulados): sirven de lectura anterior pero no se marcan.
CREATE VIEW odometro_sin_avance_sin_excepcion AS
WITH lecturas AS (
    SELECT id, matricula, fecha, COALESCE(hora, '00:00:00') AS hora, odometro, 0 AS de_otra_red
    FROM carga
    WHERE odometro IS NOT NULL AND matricula IS NOT NULL
    UNION ALL
    SELECT 'FUERA-' || id, matricula, fecha, COALESCE(hora, '00:00:00'), odometro, 1
    FROM pedido
    WHERE estacion_servicio = 'ESTACION AJENA' AND UPPER(rendido) = 'SI' AND COALESCE(UPPER(anulado), '') <> 'SI'
      AND odometro IS NOT NULL AND COALESCE(litros_cargados, litros_autorizados) IS NOT NULL
),
secuencia AS (
    SELECT id, matricula, fecha, odometro, de_otra_red,
           LAG(odometro) OVER vehiculo AS odometro_anterior,
           LAG(fecha) OVER vehiculo AS fecha_anterior
    FROM lecturas
    WINDOW vehiculo AS (PARTITION BY matricula ORDER BY fecha, hora, id)
)
SELECT s.id, s.matricula, s.fecha, s.odometro, s.fecha_anterior
FROM secuencia s
WHERE s.de_otra_red = 0
  AND s.odometro = s.odometro_anterior
  AND s.fecha > s.fecha_anterior
  AND NOT EXISTS (SELECT 1 FROM excepcion_odometro e
                  WHERE e.matricula = s.matricula AND s.fecha BETWEEN e.desde AND e.hasta);
