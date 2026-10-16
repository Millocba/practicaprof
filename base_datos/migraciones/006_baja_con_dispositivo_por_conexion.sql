-- 006 · Móviles de baja con el dispositivo transmitiendo (H11): la vista decide por la última conexión.
-- El grupo del dispositivo (por ejemplo `BAJA / REEMPLAZOS`, donde deberían estar los retirados) a veces
-- queda con el valor anterior aunque el aparato ya no esté instalado, así que lo que dice si dejó de
-- trabajar es la última conexión. Da el mismo conjunto que la regla `detectar_dispositivo_activo_en_baja`
-- de `deteccion/reglas.py`, y un test lo comprueba.
--
-- Compatibilidad: requiere 003; reemplaza la vista `baja_con_dispositivo_activo` con las mismas columnas,
--                 así que lo que la consulta sigue funcionando. Una base ya migrada la recibe al aplicarse.
-- Bloqueo esperado: ninguno (solo una vista, dentro de una transacción).
-- Vuelta atrás: DROP VIEW baja_con_dispositivo_activo; volver a crearla con el filtro
--               `d.grupo <> 'BAJA / REEMPLAZOS'` de la migración 003; DELETE FROM migracion WHERE version = '006'.
-- Verificación: la vista se puede consultar y `python -m base_datos verificar` no informa problemas.

DROP VIEW baja_con_dispositivo_activo;

CREATE VIEW baja_con_dispositivo_activo AS
SELECT v.matricula, v.dominio, e.estado, d.alias AS dispositivo, d.grupo, d.ultima_conexion
FROM vehiculo v
JOIN estado_vehiculo e ON e.matricula = v.matricula AND e.hasta IS NULL
JOIN asignacion_dispositivo a ON a.matricula = v.matricula AND a.hasta IS NULL
JOIN dispositivo d ON d.alias = a.dispositivo
WHERE e.estado LIKE '%BAJA%'
  AND julianday((SELECT MAX(ultima_conexion) FROM dispositivo)) - julianday(d.ultima_conexion) <= 7;
