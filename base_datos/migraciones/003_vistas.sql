-- 003 · Vistas de control: los controles de auditoría escritos en SQL estándar (ventanas y CTE),
-- portables a otros motores.
--
-- Compatibilidad: requiere 001 y 002; no modifica datos.
-- Bloqueo esperado: ninguno (solo vistas).
-- Vuelta atrás: DROP VIEW de las vistas de este archivo.
-- Verificación: cada vista se puede consultar (SELECT ... LIMIT 1).

-- Saldo de cada contrato por día: tope del mes, transferencias (se acreditan antes de las cargas
-- del día) y consumo a precio del surtidor, que es como se sigue la ejecución del cupo (H10)
CREATE VIEW saldo_diario_contrato AS
WITH RECURSIVE dias (dia) AS (
    SELECT date(MIN(fecha), 'start of month') FROM carga
    UNION ALL
    SELECT date(dia, '+1 day') FROM dias WHERE dia < (SELECT MAX(fecha) FROM carga)
),
consumos AS (
    SELECT contrato, fecha AS dia, SUM(importe) AS consumo FROM carga GROUP BY contrato, fecha
),
netas AS (
    SELECT contrato, dia, SUM(monto) AS transferido FROM (
        SELECT contrato_destino AS contrato, fecha AS dia, monto FROM transferencia
        UNION ALL
        SELECT contrato_origen, fecha, -monto FROM transferencia
    ) GROUP BY contrato, dia
),
diario AS (
    SELECT c.indice AS contrato, d.dia, strftime('%Y-%m', d.dia) AS mes, c.limite_mensual AS tope,
           COALESCE(n.transferido, 0) AS transferido, COALESCE(k.consumo, 0) AS consumo
    FROM contrato c CROSS JOIN dias d
    LEFT JOIN netas n ON n.contrato = c.indice AND n.dia = d.dia
    LEFT JOIN consumos k ON k.contrato = c.indice AND k.dia = d.dia
)
SELECT contrato, dia, mes, tope, transferido, consumo,
       tope + SUM(transferido) OVER mes_en_curso - (SUM(consumo) OVER mes_en_curso - consumo) AS saldo_para_cargar,
       tope + SUM(transferido) OVER mes_en_curso - SUM(consumo) OVER mes_en_curso AS saldo_al_cierre
FROM diario
WINDOW mes_en_curso AS (PARTITION BY contrato, mes ORDER BY dia ROWS UNBOUNDED PRECEDING);

-- Contratos-mes con días que empiezan sin saldo y tienen cargas: el corte debió impedirlas (H10)
CREATE VIEW cargas_con_saldo_agotado AS
SELECT contrato, mes, COUNT(*) AS dias, ROUND(SUM(consumo), 2) AS consumo_sin_saldo
FROM saldo_diario_contrato
WHERE saldo_para_cargar <= 0 AND consumo > 0
GROUP BY contrato, mes;

-- Conciliación triple de cada factura: deuda contra líneas, PDF contra deuda y renglones que no
-- son combustible (H9)
CREATE VIEW conciliacion_factura AS
SELECT f.numero, f.contrato, f.periodo, f.producto,
       f.total_monto AS deuda, f.total_pdf,
       ROUND(SUM(l.importe), 2) AS suma_lineas,
       ROUND(f.total_monto - SUM(l.importe), 2) AS diferencia_deuda_lineas,
       CASE WHEN f.total_pdf IS NULL THEN NULL ELSE ROUND(f.total_pdf - f.total_monto, 2) END AS diferencia_pdf_deuda,
       SUM(CASE WHEN l.concepto NOT IN ('COMBUSTIBLE', 'AJUSTE') THEN 1 ELSE 0 END) AS renglones_no_combustible,
       CASE WHEN ABS(f.total_monto - SUM(l.importe)) > 0.005 * ABS(SUM(l.importe))
                 OR (f.total_pdf IS NOT NULL AND ABS(f.total_pdf - f.total_monto) > 0.001 * ABS(f.total_monto))
                 OR SUM(CASE WHEN l.concepto NOT IN ('COMBUSTIBLE', 'AJUSTE') THEN 1 ELSE 0 END) > 0
            THEN 1 ELSE 0 END AS observada
FROM factura f
JOIN factura_linea l ON l.factura = f.numero
GROUP BY f.numero;

-- Líneas de combustible que facturan una carga que no está en el reporte (H9)
CREATE VIEW linea_sin_carga AS
SELECT l.*
FROM factura_linea l
LEFT JOIN carga c ON c.id = l.referencia_carga
WHERE l.concepto = 'COMBUSTIBLE' AND c.id IS NULL;

-- Móviles de baja con el dispositivo fuera del grupo de depósito y con transmisión en la última
-- semana: irían a desguace con el aparato funcionando (H11)
CREATE VIEW baja_con_dispositivo_activo AS
SELECT v.matricula, v.dominio, e.estado, d.alias AS dispositivo, d.grupo, d.ultima_conexion
FROM vehiculo v
JOIN estado_vehiculo e ON e.matricula = v.matricula AND e.hasta IS NULL
JOIN asignacion_dispositivo a ON a.matricula = v.matricula AND a.hasta IS NULL
JOIN dispositivo d ON d.alias = a.dispositivo
WHERE e.estado LIKE '%BAJA%'
  AND d.grupo <> 'BAJA / REEMPLAZOS'
  AND julianday((SELECT MAX(ultima_conexion) FROM dispositivo)) - julianday(d.ultima_conexion) <= 7;
