# Brechas entre la fuente real y el generador

- Perfil real: origen **fuentes reales**, generado 2026-09-26, revisado: sí.
- Perfil sintético: **sintético (realista)**.
- Brechas: 94 altas, 185 medias, 162 bajas.

| Severidad | Tabla real | Columna | Aspecto | Real | Sintético | Sugerencia |
|---|---|---|---|---|---|---|
| alta | actas | — | tabla no modelada | 12 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | actas_vehiculos | — | tabla no modelada | 7 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_alertas | — | tabla no modelada | 5 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_contratos | — | tabla no modelada | 3 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_contratos_credito | — | tabla no modelada | 6 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_facturas | — | tabla no modelada | 16 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_incidencia_transacciones | incidencia_id | columna no modelada | entero · 99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencia_transacciones | tarjeta | columna no modelada | número como texto · 99999999999999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencia_transacciones | establecimiento | columna no modelada | texto · 99999 - AAAA A AAAAAAA A AAA AAA, 99999 - AAAAAAAA AAAAAAAA AAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencia_transacciones | importe_yer | columna no modelada | decimal · 99999.9, 99999.99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencia_transacciones | es_combustible | columna no modelada | entero · 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencia_transacciones | remito | columna no modelada | texto · 99999-99999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencia_transacciones | es_contingencia | columna no modelada | entero · 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_incidencias | — | tabla no modelada | 6 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_pdf_items | — | tabla no modelada | 8 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_periodos | — | tabla no modelada | 6 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | fact_transacciones | factura_id | columna no modelada | entero · 999, 99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_transacciones | tarjeta | columna no modelada | número como texto · 99999999999999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_transacciones | establecimiento | columna no modelada | texto · 99999 - AAAA A AAAAAAA A AAA AAA, 99999 - AAAAAAAA AAAAAAAA AAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_transacciones | importe_yer | columna no modelada | decimal · 99999.9, 99999.999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_transacciones | remito | columna no modelada | texto · 9999-99999999, 99999-99999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_transacciones | es_combustible | columna no modelada | entero · 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | fact_transacciones | es_contingencia | columna no modelada | entero · 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | Matricula | columna no modelada | texto · 99999, 9999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | OdometroRegistrado | columna no modelada | entero · 999999, 99999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | CapacidadTanque | columna no modelada | texto · AAAAAA AAAAA, 9/9 AAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | TarjetaDni | columna no modelada | booleano | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | Dependencia | columna no modelada | texto · A.A.A. 99 - AAAA AAAAAAAA AAAAAAAA 99, A.A.A. 9 - AAAA AAAAAAAA AAAAAAAA 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | DependeciaMovil | columna no modelada | texto · A.A.A. 9 - AAAA AAAAAAAA AAAAAAAA 9, A.A.A. 99 - AAAA AAAAAAAA AAAAAAAA 99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | Cargador | columna no modelada | texto · AAAA AAAAAAA AAAAAAA AAAAAAA AAAAAAA (AAA: 99999999), AAAA AAAAAAA AAAAAA AAAAAA AAAAAA (AAA: 99999999) | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | registro_de_combustible | DireccionGral | columna no modelada | texto · AAAAAAAAA AAAA. AAAAAAAAA AAAAAAA, AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | consumo_proveedor_1 | — | tabla no modelada | 31 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | dispositivos_telemetria | Secuencia | columna no modelada | entero · 9999, 999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Tipo Dispositivo | columna no modelada | texto · AAAAAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Modelo equipo | columna no modelada | texto · AAAAAAAA AAA AAAAAA, AAAAAAAA AAA AAAAAA - AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Hora de última transmisión | columna no modelada | texto · AAAAAAA, 99 AA AAAAAAAAAA AA 9999 99:99:99, AAAAAA, 99 AA AAAAAAAAAA AA 9999 99:99:99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Hora de última posición válida | columna no modelada | texto · AAAAAAA, 99 AA AAAAAAAAAA AA 9999 99:99:99, AAAAAA, 99 AA AAAAAAAAAA AA 9999 99:99:99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Estado candado | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Estado de transmisión | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Estado de ignición | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Estado de movimiento | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | % Batería Externa | columna no modelada | entero · 999, 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Valor Batería Externa | columna no modelada | entero · 99999, 9999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | dispositivos_telemetria | Horómetro (hrs) | columna no modelada | decimal · 999.99, 9999.99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | Color | columna no modelada | texto · AAAAAAAAAAAAA, AAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | Procedencia | columna no modelada | texto · AAAAAAAAAA, AAAAAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | RelacionConsumo | columna no modelada | texto · A | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | ExcepcionOdometro | columna no modelada | texto · AA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | FechaHastaExcepcionOdometro | columna no modelada | fecha como texto · 99/99/9999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | RetiraDni | columna no modelada | entero · 99999999, 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | padron_flota | RetiraNombre | columna no modelada | texto · AAAAAAAAA AAAAAAAAA AAAAA AAAAAAAAA AAAAAAAA AAAAAA (AAA: 99…, AAAAAAAAA AAAAAA AAAAA AAAAAAAAA (AAA: 99999999) | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | Color | columna no modelada | texto · AAAAAAAAAAAAA, AAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | Procedencia | columna no modelada | texto · AAAAAAAAAA, AAAAAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | RelacionConsumo | columna no modelada | texto · A | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | ExcepcionOdometro | columna no modelada | texto · AA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | FechaHastaExcepcionOdometro | columna no modelada | fecha como texto · 99/99/9999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | RetiraDni | columna no modelada | entero · 99999999, 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | RetiraNombre | columna no modelada | texto · AAAAAAAAA AAAAAAAAA AAAAA AAAAAAAAA AAAAAAAA AAAAAA (AAA: 99…, AAAAAAAAA AAAAAA AAAAA AAAAAAAAA (AAA: 99999999) | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | dominio_norm | columna no modelada | texto · AA999AA, AAA999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | dominio_invalido | columna no modelada | texto · AAAAA, AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | motor_digits | columna no modelada | número como texto · 99999999999, 99999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | motor_lastN | columna no modelada | número como texto · 9999999, 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | estado_norm | columna no modelada | texto · AA AAAAAAAA, AAAAAAA AA AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | es_baja | columna no modelada | texto · AAAAA, AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | es_fuera_servicio | columna no modelada | texto · AAAAA, AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | es_en_servicio | columna no modelada | texto · AAAA, AAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | grupo_baja | columna no modelada | texto · AA_AAAA, AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | grupo_servicio | columna no modelada | texto · AA_AAAAAAAA, AAAAA_AAAAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | cant_dispositivos | columna no modelada | entero · 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | ultima_tx | columna no modelada | fecha como texto · 9999-99-99 99:99:99 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | imeis | columna no modelada | entero · 999999999999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | msisdns | columna no modelada | decimal · 99.9999999999999, 99.999999999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | placas | columna no modelada | texto · AA999AA, A999AAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | alias | columna no modelada | texto · 99999, 9999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | latitud | columna no modelada | decimal · -99.99999999999999, -99.999999999999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | longitud | columna no modelada | decimal · -99.99999999999999, -99.9999999999999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | fuente_match | columna no modelada | texto · AAAAAAAAA( AAAAA ) | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | tiene_telemetria | columna no modelada | texto · AAAAA, AAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | flota_telemetria_enriquecida | alerta_2_dispositivos | columna no modelada | texto · AAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | actas_tarjetas_dni | — | tabla no modelada | 8 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | tarjetas_dni_items | — | tabla no modelada | 7 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.bandera_blanca_reportes | — | tabla no modelada | 12 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.consumo_reportes | — | tabla no modelada | 13 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.flota_cargas | — | tabla no modelada | 7 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.moviles_exceptuados | — | tabla no modelada | 7 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.reclamos_combustible | — | tabla no modelada | 17 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.reporte_proveedor_1_facturacion | factura | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | base.reporte_proveedor_1_facturacion | extracto | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | base.reporte_proveedor_1_facturacion | dominio | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | base.reporte_proveedor_1_facturacion | litros_unidades | columna no modelada | desconocido | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | base.registro_de_combustible_auth | — | tabla no modelada | 5 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.solicitudes_registro_de_combustible | — | tabla no modelada | 10 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.solicitudes_solapa_c | — | tabla no modelada | 7 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| alta | base.users | — | tabla no modelada | 9 columnas | — | Agregar la tabla al generador o documentar por qué queda fuera del análisis. |
| media | fact_incidencia_transacciones | id | tipo | entero | texto | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | fact_incidencia_transacciones | id | formato | 99999 (100.0%) | no se genera | Agregar el formato 99999 a id (aparece en el 100.0% de la fuente real). |
| media | fact_incidencia_transacciones | fecha | formato | 99/99/9999 (100.0%) | no se genera | Agregar el formato 99/99/9999 a fecha (aparece en el 100.0% de la fuente real). |
| media | fact_incidencia_transacciones | conductor | calidad | espacios al inicio, al final o dobles: 2.5% | 0% | Inyectar espacios al inicio, al final o dobles en conductor (~2.5%) y registrarlo en el ground truth. |
| media | fact_transacciones | id | tipo | entero | texto | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | fact_transacciones | id | formato | 99999 (79.6%) | no se genera | Agregar el formato 99999 a id (aparece en el 79.6% de la fuente real). |
| media | fact_transacciones | id | formato | 999999 (15.0%) | no se genera | Agregar el formato 999999 a id (aparece en el 15.0% de la fuente real). |
| media | fact_transacciones | id | formato | 9999 (5.5%) | no se genera | Agregar el formato 9999 a id (aparece en el 5.5% de la fuente real). |
| media | fact_transacciones | fecha | formato | 99/99/9999 99:99:99 (65.8%) | no se genera | Agregar el formato 99/99/9999 99:99:99 a fecha (aparece en el 65.8% de la fuente real). |
| media | fact_transacciones | fecha | formato | 99/99/9999 9:99:99 (27.9%) | no se genera | Agregar el formato 99/99/9999 9:99:99 a fecha (aparece en el 27.9% de la fuente real). |
| media | fact_transacciones | fecha | formato | 99/99/9999 (6.3%) | no se genera | Agregar el formato 99/99/9999 a fecha (aparece en el 6.3% de la fuente real). |
| media | fact_transacciones | identificacion | faltantes | 6.3% | 0% | Ajustar la tasa de vacíos de identificacion a cerca de 6.3%. |
| media | fact_transacciones | identificacion | formato | AA999AA (77.8%) | no se genera | Agregar el formato AA999AA a identificacion (aparece en el 77.8% de la fuente real). |
| media | fact_transacciones | identificacion | formato | A999AAA (16.0%) | no se genera | Agregar el formato A999AAA a identificacion (aparece en el 16.0% de la fuente real). |
| media | fact_transacciones | identificacion | calidad | números guardados como texto: 1.1% | 0% | Inyectar números guardados como texto en identificacion (~1.1%) y registrarlo en el ground truth. |
| media | registro_de_combustible | Id | tipo | entero | texto | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | registro_de_combustible | Id | formato | 9999999 (100.0%) | no se genera | Agregar el formato 9999999 a Id (aparece en el 100.0% de la fuente real). |
| media | registro_de_combustible | Dominio | calidad | espacios al inicio, al final o dobles: 1.2% | 0% | Inyectar espacios al inicio, al final o dobles en Dominio (~1.2%) y registrarlo en el ground truth. |
| media | registro_de_combustible | Solicitante | calidad | espacios al inicio, al final o dobles: 4.2% | 0% | Inyectar espacios al inicio, al final o dobles en Solicitante (~4.2%) y registrarlo en el ground truth. |
| media | registro_de_combustible | NumeroTicket | tipo | número como texto | entero | En la fuente real es número como texto; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | registro_de_combustible | NumeroTicket | formato | 9 (5.5%) | no se genera | Agregar el formato 9 a NumeroTicket (aparece en el 5.5% de la fuente real). |
| media | registro_de_combustible | EstacionServicio | formato | AAA (92.7%) | no se genera | Agregar el formato AAA a EstacionServicio (aparece en el 92.7% de la fuente real). |
| media | registro_de_combustible | EstacionServicio | formato | AAAAAAAAAAAAAA (6.9%) | no se genera | Agregar el formato AAAAAAAAAAAAAA a EstacionServicio (aparece en el 6.9% de la fuente real). |
| media | dispositivos_telemetria | Grupo | formato | AAAAAAAAAAAAA (8.1%) | no se genera | Agregar el formato AAAAAAAAAAAAA a Grupo (aparece en el 8.1% de la fuente real). |
| media | dispositivos_telemetria | Grupo | formato | AAAAAAAAAA - AAA. AAAAAAAAAAAA (6.7%) | no se genera | Agregar el formato AAAAAAAAAA - AAA. AAAAAAAAAAAA a Grupo (aparece en el 6.7% de la fuente real). |
| media | dispositivos_telemetria | Grupo | formato | AAAAAAAAAAA (6.5%) | no se genera | Agregar el formato AAAAAAAAAAA a Grupo (aparece en el 6.5% de la fuente real). |
| media | dispositivos_telemetria | Grupo | formato | AAA 99 (6.2%) | no se genera | Agregar el formato AAA 99 a Grupo (aparece en el 6.2% de la fuente real). |
| media | dispositivos_telemetria | Grupo | formato | AAAAAAAAAA - AAAAAAAAA (6.1%) | no se genera | Agregar el formato AAAAAAAAAA - AAAAAAAAA a Grupo (aparece en el 6.1% de la fuente real). |
| media | dispositivos_telemetria | Grupo | formato | AAA 9 (5.5%) | no se genera | Agregar el formato AAA 9 a Grupo (aparece en el 5.5% de la fuente real). |
| media | dispositivos_telemetria | Grupo | calidad | mayúsculas y minúsculas mezcladas: 40.1% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Grupo (~40.1%) y registrarlo en el ground truth. |
| media | dispositivos_telemetria | MSISDN | tipo | decimal | entero | En la fuente real es decimal; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | dispositivos_telemetria | MSISDN | formato | 99.9999999999999 (90.2%) | no se genera | Agregar el formato 99.9999999999999 a MSISDN (aparece en el 90.2% de la fuente real). |
| media | dispositivos_telemetria | MSISDN | formato | 99.999999999999 (8.9%) | no se genera | Agregar el formato 99.999999999999 a MSISDN (aparece en el 8.9% de la fuente real). |
| media | dispositivos_telemetria | Alias | formato | 99999 (39.2%) | no se genera | Agregar el formato 99999 a Alias (aparece en el 39.2% de la fuente real). |
| media | dispositivos_telemetria | Alias | formato | 9999 (34.6%) | no se genera | Agregar el formato 9999 a Alias (aparece en el 34.6% de la fuente real). |
| media | dispositivos_telemetria | Alias | formato | A-9999 (22.7%) | no se genera | Agregar el formato A-9999 a Alias (aparece en el 22.7% de la fuente real). |
| media | dispositivos_telemetria | Alias | calidad | espacios al inicio, al final o dobles: 3.0% | 0% | Inyectar espacios al inicio, al final o dobles en Alias (~3.0%) y registrarlo en el ground truth. |
| media | dispositivos_telemetria | Alias | calidad | números guardados como texto: 73.8% | 0% | Inyectar números guardados como texto en Alias (~73.8%) y registrarlo en el ground truth. |
| media | dispositivos_telemetria | Latitud | formato | -99.999999999999999 (59.4%) | no se genera | Agregar el formato -99.999999999999999 a Latitud (aparece en el 59.4% de la fuente real). |
| media | dispositivos_telemetria | Latitud | formato | -99.99999999999999 (35.2%) | no se genera | Agregar el formato -99.99999999999999 a Latitud (aparece en el 35.2% de la fuente real). |
| media | dispositivos_telemetria | Longitud | formato | -99.99999999999999 (76.1%) | no se genera | Agregar el formato -99.99999999999999 a Longitud (aparece en el 76.1% de la fuente real). |
| media | dispositivos_telemetria | Longitud | formato | -99.9999999999999 (14.9%) | no se genera | Agregar el formato -99.9999999999999 a Longitud (aparece en el 14.9% de la fuente real). |
| media | dispositivos_telemetria | Longitud | formato | -99.999999999999999 (5.9%) | no se genera | Agregar el formato -99.999999999999999 a Longitud (aparece en el 5.9% de la fuente real). |
| media | dispositivos_telemetria | % Batería | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | dispositivos_telemetria | % Batería | formato | 99 (69.2%) | no se genera | Agregar el formato 99 a % Batería (aparece en el 69.2% de la fuente real). |
| media | dispositivos_telemetria | % Batería | formato | 9 (29.8%) | no se genera | Agregar el formato 9 a % Batería (aparece en el 29.8% de la fuente real). |
| media | dispositivos_telemetria | Odómetro (Km) | tipo | decimal | entero | En la fuente real es decimal; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | dispositivos_telemetria | Odómetro (Km) | formato | 999999.99 (47.7%) | no se genera | Agregar el formato 999999.99 a Odómetro (Km) (aparece en el 47.7% de la fuente real). |
| media | dispositivos_telemetria | Odómetro (Km) | formato | 99999.99 (26.1%) | no se genera | Agregar el formato 99999.99 a Odómetro (Km) (aparece en el 26.1% de la fuente real). |
| media | dispositivos_telemetria | Odómetro (Km) | formato | 9999.99 (11.7%) | no se genera | Agregar el formato 9999.99 a Odómetro (Km) (aparece en el 11.7% de la fuente real). |
| media | padron_flota | Matricula | formato | 9999 (50.7%) | no se genera | Agregar el formato 9999 a Matricula (aparece en el 50.7% de la fuente real). |
| media | padron_flota | Matricula | formato | A-9999 (23.6%) | no se genera | Agregar el formato A-9999 a Matricula (aparece en el 23.6% de la fuente real). |
| media | padron_flota | Matricula | formato | 99999 (22.9%) | no se genera | Agregar el formato 99999 a Matricula (aparece en el 22.9% de la fuente real). |
| media | padron_flota | Matricula | calidad | números guardados como texto: 73.8% | 0% | Inyectar números guardados como texto en Matricula (~73.8%) y registrarlo en el ground truth. |
| media | padron_flota | Dominio | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.2% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en Dominio (~1.2%) y registrarlo en el ground truth. |
| media | padron_flota | Dependencia | calidad | espacios al inicio, al final o dobles: 2.0% | 0% | Inyectar espacios al inicio, al final o dobles en Dependencia (~2.0%) y registrarlo en el ground truth. |
| media | padron_flota | Marca | formato | AAAAA (10.4%) | no se genera | Agregar el formato AAAAA a Marca (aparece en el 10.4% de la fuente real). |
| media | padron_flota | Marca | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.7% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en Marca (~1.7%) y registrarlo en el ground truth. |
| media | padron_flota | Modelo | formato | AAAAAAAA (17.0%) | no se genera | Agregar el formato AAAAAAAA a Modelo (aparece en el 17.0% de la fuente real). |
| media | padron_flota | Modelo | formato | AAAAAA (15.9%) | no se genera | Agregar el formato AAAAAA a Modelo (aparece en el 15.9% de la fuente real). |
| media | padron_flota | Modelo | formato | AAAAA (14.1%) | no se genera | Agregar el formato AAAAA a Modelo (aparece en el 14.1% de la fuente real). |
| media | padron_flota | Modelo | formato | AAA999 (11.2%) | no se genera | Agregar el formato AAA999 a Modelo (aparece en el 11.2% de la fuente real). |
| media | padron_flota | Modelo | formato | A99 (9.1%) | no se genera | Agregar el formato A99 a Modelo (aparece en el 9.1% de la fuente real). |
| media | padron_flota | Modelo | formato | AA (8.3%) | no se genera | Agregar el formato AA a Modelo (aparece en el 8.3% de la fuente real). |
| media | padron_flota | Modelo | formato | AAAA (6.7%) | no se genera | Agregar el formato AAAA a Modelo (aparece en el 6.7% de la fuente real). |
| media | padron_flota | Modelo | calidad | mayúsculas y minúsculas mezcladas: 3.8% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Modelo (~3.8%) y registrarlo en el ground truth. |
| media | padron_flota | Modelo | calidad | números guardados como texto: 1.6% | 0% | Inyectar números guardados como texto en Modelo (~1.6%) y registrarlo en el ground truth. |
| media | padron_flota | NumeroChasis | faltantes | 37.8% | 0% | Ajustar la tasa de vacíos de NumeroChasis a cerca de 37.8%. |
| media | padron_flota | NumeroChasis | formato | 9AAAA99A9AA999999 (25.2%) | no se genera | Agregar el formato 9AAAA99A9AA999999 a NumeroChasis (aparece en el 25.2% de la fuente real). |
| media | padron_flota | NumeroChasis | formato | 9AAAAAA99AAA99999 (15.8%) | no se genera | Agregar el formato 9AAAAAA99AAA99999 a NumeroChasis (aparece en el 15.8% de la fuente real). |
| media | padron_flota | NumeroChasis | formato | 9AA999AA9AA999999 (10.8%) | no se genera | Agregar el formato 9AA999AA9AA999999 a NumeroChasis (aparece en el 10.8% de la fuente real). |
| media | padron_flota | NumeroChasis | formato | 9 (7.9%) | no se genera | Agregar el formato 9 a NumeroChasis (aparece en el 7.9% de la fuente real). |
| media | padron_flota | NumeroChasis | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.5% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en NumeroChasis (~1.5%) y registrarlo en el ground truth. |
| media | padron_flota | NumeroChasis | calidad | mayúsculas y minúsculas mezcladas: 5.4% | 0% | Inyectar mayúsculas y minúsculas mezcladas en NumeroChasis (~5.4%) y registrarlo en el ground truth. |
| media | padron_flota | NumeroChasis | calidad | números guardados como texto: 10.2% | 0% | Inyectar números guardados como texto en NumeroChasis (~10.2%) y registrarlo en el ground truth. |
| media | padron_flota | NumeroMotor | faltantes | 37.9% | 0% | Ajustar la tasa de vacíos de NumeroMotor a cerca de 37.9%. |
| media | padron_flota | NumeroMotor | formato | AA99A999A999999 (30.0%) | no se genera | Agregar el formato AA99A999A999999 a NumeroMotor (aparece en el 30.0% de la fuente real). |
| media | padron_flota | NumeroMotor | formato | AA999AAA99999 (17.5%) | no se genera | Agregar el formato AA999AAA99999 a NumeroMotor (aparece en el 17.5% de la fuente real). |
| media | padron_flota | NumeroMotor | formato | 999999999999999 (13.6%) | no se genera | Agregar el formato 999999999999999 a NumeroMotor (aparece en el 13.6% de la fuente real). |
| media | padron_flota | NumeroMotor | formato | 9 (8.0%) | no se genera | Agregar el formato 9 a NumeroMotor (aparece en el 8.0% de la fuente real). |
| media | padron_flota | NumeroMotor | calidad | espacios al inicio, al final o dobles: 3.3% | 0% | Inyectar espacios al inicio, al final o dobles en NumeroMotor (~3.3%) y registrarlo en el ground truth. |
| media | padron_flota | NumeroMotor | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.7% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en NumeroMotor (~1.7%) y registrarlo en el ground truth. |
| media | padron_flota | NumeroMotor | calidad | números guardados como texto: 24.3% | 0% | Inyectar números guardados como texto en NumeroMotor (~24.3%) y registrarlo en el ground truth. |
| media | padron_flota | Año | formato | 9 (7.6%) | no se genera | Agregar el formato 9 a Año (aparece en el 7.6% de la fuente real). |
| media | padron_flota | CapacidadTanque | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | padron_flota | CapacidadTanque | formato | 99 (92.6%) | no se genera | Agregar el formato 99 a CapacidadTanque (aparece en el 92.6% de la fuente real). |
| media | padron_flota | CapacidadTanque | formato | 9 (6.5%) | no se genera | Agregar el formato 9 a CapacidadTanque (aparece en el 6.5% de la fuente real). |
| media | padron_flota | NumeroTarjeta | tipo | número como texto | texto | En la fuente real es número como texto; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | padron_flota | NumeroTarjeta | faltantes | 4.4% | 0% | Ajustar la tasa de vacíos de NumeroTarjeta a cerca de 4.4%. |
| media | padron_flota | NumeroTarjeta | formato | 99999999999999999 (98.5%) | no se genera | Agregar el formato 99999999999999999 a NumeroTarjeta (aparece en el 98.5% de la fuente real). |
| media | padron_flota | LimiteSaldo | tipo | decimal | entero | En la fuente real es decimal; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | padron_flota | LimiteSaldo | formato | 9999999.9 (39.8%) | no se genera | Agregar el formato 9999999.9 a LimiteSaldo (aparece en el 39.8% de la fuente real). |
| media | padron_flota | LimiteSaldo | formato | 99999.9 (35.4%) | no se genera | Agregar el formato 99999.9 a LimiteSaldo (aparece en el 35.4% de la fuente real). |
| media | padron_flota | LimiteSaldo | formato | 999999.99 (9.1%) | no se genera | Agregar el formato 999999.99 a LimiteSaldo (aparece en el 9.1% de la fuente real). |
| media | padron_flota | LimiteSaldo | formato | 99999.99 (5.0%) | no se genera | Agregar el formato 99999.99 a LimiteSaldo (aparece en el 5.0% de la fuente real). |
| media | padron_flota | LimiteSaldo | escala (mediana) | 1000000.0 | 3900.0 | La mediana real es 256.4 veces la sintética: revisar el rango que se genera. |
| media | padron_flota | Cupo | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | padron_flota | Cupo | formato | 99 (90.1%) | no se genera | Agregar el formato 99 a Cupo (aparece en el 90.1% de la fuente real). |
| media | padron_flota | Cupo | formato | 9 (9.1%) | no se genera | Agregar el formato 9 a Cupo (aparece en el 9.1% de la fuente real). |
| media | padron_flota | Estado | calidad | mayúsculas y minúsculas mezcladas: 100.0% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Estado (~100.0%) y registrarlo en el ground truth. |
| media | padron_flota | SubEstado | faltantes | 51.5% | 54.5% | Ajustar la tasa de vacíos de SubEstado a cerca de 51.5%. |
| media | padron_flota | SubEstado | formato | AAAAAAAA AA AAAAA (7.9%) | no se genera | Agregar el formato AAAAAAAA AA AAAAA a SubEstado (aparece en el 7.9% de la fuente real). |
| media | padron_flota | SubEstado | formato | AAAAA AAAAAAAAA AAAAAAAAA (5.6%) | no se genera | Agregar el formato AAAAA AAAAAAAAA AAAAAAAAA a SubEstado (aparece en el 5.6% de la fuente real). |
| media | padron_flota | SubEstado | calidad | mayúsculas y minúsculas mezcladas: 100.0% | 0% | Inyectar mayúsculas y minúsculas mezcladas en SubEstado (~100.0%) y registrarlo en el ground truth. |
| media | padron_flota | DireccionGral | formato | AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAA (23.1%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAA a DireccionGral (aparece en el 23.1% de la fuente real). |
| media | padron_flota | DireccionGral | formato | AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAA (20.8%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAA a DireccionGral (aparece en el 20.8% de la fuente real). |
| media | padron_flota | DireccionGral | formato | AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAAAAAAA (7.6%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAAAAAAA a DireccionGral (aparece en el 7.6% de la fuente real). |
| media | padron_flota | DireccionGral | formato | AAAAAAAAA AAAA. AA AAAAAAA AAAAAAAA (5.2%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AA AAAAAAA AAAAAAAA a DireccionGral (aparece en el 5.2% de la fuente real). |
| media | flota_telemetria_enriquecida | Matricula | formato | 9999 (50.7%) | no se genera | Agregar el formato 9999 a Matricula (aparece en el 50.7% de la fuente real). |
| media | flota_telemetria_enriquecida | Matricula | formato | A-9999 (23.6%) | no se genera | Agregar el formato A-9999 a Matricula (aparece en el 23.6% de la fuente real). |
| media | flota_telemetria_enriquecida | Matricula | formato | 99999 (22.9%) | no se genera | Agregar el formato 99999 a Matricula (aparece en el 22.9% de la fuente real). |
| media | flota_telemetria_enriquecida | Matricula | calidad | números guardados como texto: 73.8% | 0% | Inyectar números guardados como texto en Matricula (~73.8%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | Dominio | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.2% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en Dominio (~1.2%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | Dependencia | calidad | espacios al inicio, al final o dobles: 2.0% | 0% | Inyectar espacios al inicio, al final o dobles en Dependencia (~2.0%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | Marca | formato | AAAAA (10.4%) | no se genera | Agregar el formato AAAAA a Marca (aparece en el 10.4% de la fuente real). |
| media | flota_telemetria_enriquecida | Marca | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.7% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en Marca (~1.7%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | Modelo | formato | AAAAAAAA (17.0%) | no se genera | Agregar el formato AAAAAAAA a Modelo (aparece en el 17.0% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | formato | AAAAAA (15.9%) | no se genera | Agregar el formato AAAAAA a Modelo (aparece en el 15.9% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | formato | AAAAA (14.1%) | no se genera | Agregar el formato AAAAA a Modelo (aparece en el 14.1% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | formato | AAA999 (11.2%) | no se genera | Agregar el formato AAA999 a Modelo (aparece en el 11.2% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | formato | A99 (9.1%) | no se genera | Agregar el formato A99 a Modelo (aparece en el 9.1% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | formato | AA (8.3%) | no se genera | Agregar el formato AA a Modelo (aparece en el 8.3% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | formato | AAAA (6.7%) | no se genera | Agregar el formato AAAA a Modelo (aparece en el 6.7% de la fuente real). |
| media | flota_telemetria_enriquecida | Modelo | calidad | mayúsculas y minúsculas mezcladas: 3.8% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Modelo (~3.8%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | Modelo | calidad | números guardados como texto: 1.6% | 0% | Inyectar números guardados como texto en Modelo (~1.6%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | NumeroChasis | faltantes | 37.8% | 0% | Ajustar la tasa de vacíos de NumeroChasis a cerca de 37.8%. |
| media | flota_telemetria_enriquecida | NumeroChasis | formato | 9AAAA99A9AA999999 (25.2%) | no se genera | Agregar el formato 9AAAA99A9AA999999 a NumeroChasis (aparece en el 25.2% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroChasis | formato | 9AAAAAA99AAA99999 (15.8%) | no se genera | Agregar el formato 9AAAAAA99AAA99999 a NumeroChasis (aparece en el 15.8% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroChasis | formato | 9AA999AA9AA999999 (10.8%) | no se genera | Agregar el formato 9AA999AA9AA999999 a NumeroChasis (aparece en el 10.8% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroChasis | formato | 9 (7.9%) | no se genera | Agregar el formato 9 a NumeroChasis (aparece en el 7.9% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroChasis | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.5% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en NumeroChasis (~1.5%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | NumeroChasis | calidad | mayúsculas y minúsculas mezcladas: 5.4% | 0% | Inyectar mayúsculas y minúsculas mezcladas en NumeroChasis (~5.4%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | NumeroChasis | calidad | números guardados como texto: 10.2% | 0% | Inyectar números guardados como texto en NumeroChasis (~10.2%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | NumeroMotor | faltantes | 37.9% | 0% | Ajustar la tasa de vacíos de NumeroMotor a cerca de 37.9%. |
| media | flota_telemetria_enriquecida | NumeroMotor | formato | AA99A999A999999 (30.0%) | no se genera | Agregar el formato AA99A999A999999 a NumeroMotor (aparece en el 30.0% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroMotor | formato | AA999AAA99999 (17.5%) | no se genera | Agregar el formato AA999AAA99999 a NumeroMotor (aparece en el 17.5% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroMotor | formato | 999999999999999 (13.6%) | no se genera | Agregar el formato 999999999999999 a NumeroMotor (aparece en el 13.6% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroMotor | formato | 9 (8.0%) | no se genera | Agregar el formato 9 a NumeroMotor (aparece en el 8.0% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroMotor | calidad | espacios al inicio, al final o dobles: 3.3% | 0% | Inyectar espacios al inicio, al final o dobles en NumeroMotor (~3.3%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | NumeroMotor | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.7% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en NumeroMotor (~1.7%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | NumeroMotor | calidad | números guardados como texto: 24.3% | 0% | Inyectar números guardados como texto en NumeroMotor (~24.3%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | Año | formato | 9 (7.6%) | no se genera | Agregar el formato 9 a Año (aparece en el 7.6% de la fuente real). |
| media | flota_telemetria_enriquecida | CapacidadTanque | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | flota_telemetria_enriquecida | CapacidadTanque | formato | 99 (92.6%) | no se genera | Agregar el formato 99 a CapacidadTanque (aparece en el 92.6% de la fuente real). |
| media | flota_telemetria_enriquecida | CapacidadTanque | formato | 9 (6.5%) | no se genera | Agregar el formato 9 a CapacidadTanque (aparece en el 6.5% de la fuente real). |
| media | flota_telemetria_enriquecida | NumeroTarjeta | tipo | entero | texto | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | flota_telemetria_enriquecida | NumeroTarjeta | faltantes | 5.1% | 0% | Ajustar la tasa de vacíos de NumeroTarjeta a cerca de 5.1%. |
| media | flota_telemetria_enriquecida | NumeroTarjeta | formato | 99999999999999999 (99.1%) | no se genera | Agregar el formato 99999999999999999 a NumeroTarjeta (aparece en el 99.1% de la fuente real). |
| media | flota_telemetria_enriquecida | LimiteSaldo | tipo | decimal | entero | En la fuente real es decimal; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | flota_telemetria_enriquecida | LimiteSaldo | formato | 9999999.9 (39.8%) | no se genera | Agregar el formato 9999999.9 a LimiteSaldo (aparece en el 39.8% de la fuente real). |
| media | flota_telemetria_enriquecida | LimiteSaldo | formato | 99999.9 (35.4%) | no se genera | Agregar el formato 99999.9 a LimiteSaldo (aparece en el 35.4% de la fuente real). |
| media | flota_telemetria_enriquecida | LimiteSaldo | formato | 999999.99 (9.1%) | no se genera | Agregar el formato 999999.99 a LimiteSaldo (aparece en el 9.1% de la fuente real). |
| media | flota_telemetria_enriquecida | LimiteSaldo | formato | 99999.99 (5.0%) | no se genera | Agregar el formato 99999.99 a LimiteSaldo (aparece en el 5.0% de la fuente real). |
| media | flota_telemetria_enriquecida | LimiteSaldo | escala (mediana) | 1000000.0 | 3900.0 | La mediana real es 256.4 veces la sintética: revisar el rango que se genera. |
| media | flota_telemetria_enriquecida | Cupo | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | flota_telemetria_enriquecida | Cupo | formato | 99 (90.1%) | no se genera | Agregar el formato 99 a Cupo (aparece en el 90.1% de la fuente real). |
| media | flota_telemetria_enriquecida | Cupo | formato | 9 (9.1%) | no se genera | Agregar el formato 9 a Cupo (aparece en el 9.1% de la fuente real). |
| media | flota_telemetria_enriquecida | Estado | calidad | mayúsculas y minúsculas mezcladas: 100.0% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Estado (~100.0%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | SubEstado | faltantes | 51.5% | 54.5% | Ajustar la tasa de vacíos de SubEstado a cerca de 51.5%. |
| media | flota_telemetria_enriquecida | SubEstado | formato | AAAAAAAA AA AAAAA (7.9%) | no se genera | Agregar el formato AAAAAAAA AA AAAAA a SubEstado (aparece en el 7.9% de la fuente real). |
| media | flota_telemetria_enriquecida | SubEstado | formato | AAAAA AAAAAAAAA AAAAAAAAA (5.6%) | no se genera | Agregar el formato AAAAA AAAAAAAAA AAAAAAAAA a SubEstado (aparece en el 5.6% de la fuente real). |
| media | flota_telemetria_enriquecida | SubEstado | calidad | mayúsculas y minúsculas mezcladas: 100.0% | 0% | Inyectar mayúsculas y minúsculas mezcladas en SubEstado (~100.0%) y registrarlo en el ground truth. |
| media | flota_telemetria_enriquecida | DireccionGral | formato | AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAA (23.1%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAA a DireccionGral (aparece en el 23.1% de la fuente real). |
| media | flota_telemetria_enriquecida | DireccionGral | formato | AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAA (20.8%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAA a DireccionGral (aparece en el 20.8% de la fuente real). |
| media | flota_telemetria_enriquecida | DireccionGral | formato | AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAAAAAAA (7.6%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AAAAAAAAAAAAAAA AAAAAAAAAA a DireccionGral (aparece en el 7.6% de la fuente real). |
| media | flota_telemetria_enriquecida | DireccionGral | formato | AAAAAAAAA AAAA. AA AAAAAAA AAAAAAAA (5.2%) | no se genera | Agregar el formato AAAAAAAAA AAAA. AA AAAAAAA AAAAAAAA a DireccionGral (aparece en el 5.2% de la fuente real). |
| media | flota_telemetria_enriquecida | matricula_num | tipo | número como texto | texto | En la fuente real es número como texto; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | flota_telemetria_enriquecida | matricula_num | formato | 9999 (74.3%) | no se genera | Agregar el formato 9999 a matricula_num (aparece en el 74.3% de la fuente real). |
| media | flota_telemetria_enriquecida | matricula_num | formato | 99999 (22.9%) | no se genera | Agregar el formato 99999 a matricula_num (aparece en el 22.9% de la fuente real). |
| media | padron_flota | padron_flota.Matricula → flota_telemetria_enriquecida.Matricula | relación no modelada | 100.0% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | padron_flota | padron_flota.Dominio → flota_telemetria_enriquecida.Dominio | relación no modelada | 100.0% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | flota_telemetria_enriquecida | flota_telemetria_enriquecida.Matricula → padron_flota.Matricula | relación no modelada | 100.0% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | flota_telemetria_enriquecida | flota_telemetria_enriquecida.Dominio → padron_flota.Dominio | relación no modelada | 100.0% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | dispositivos_telemetria | dispositivos_telemetria.Alias → padron_flota.Matricula | relación no modelada | 97.5% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | dispositivos_telemetria | dispositivos_telemetria.Alias → flota_telemetria_enriquecida.Matricula | relación no modelada | 97.5% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | fact_transacciones | fact_transacciones.identificacion → padron_flota.Dominio | relación no modelada | 96.5% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | fact_transacciones | fact_transacciones.identificacion → flota_telemetria_enriquecida.Dominio | relación no modelada | 96.5% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | registro_de_combustible | registro_de_combustible.Dominio → dispositivos_telemetria.Placa | cobertura de la relación | 82.7% | 68.8% | Ajustar la tasa de claves sin vínculo para acercarla al 82.7%. |
| media | fact_transacciones | fact_transacciones.identificacion → dispositivos_telemetria.Placa | relación no modelada | 82.3% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | flota_telemetria_enriquecida | flota_telemetria_enriquecida.matricula_num → padron_flota.Matricula | relación no modelada | 73.9% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | padron_flota | padron_flota.Matricula → flota_telemetria_enriquecida.matricula_num | relación no modelada | 73.8% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | dispositivos_telemetria | dispositivos_telemetria.Alias → flota_telemetria_enriquecida.matricula_num | relación no modelada | 73.7% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | flota_telemetria_enriquecida | flota_telemetria_enriquecida.matricula_num → fact_transacciones.id | relación no modelada | 54.0% | — | La fuente real vincula estas columnas y el generador no: agregar la relación. |
| media | padron_flota | padron_flota.Dominio → dispositivos_telemetria.Placa | cobertura de la relación | 50.3% | 52.5% | Ajustar la tasa de claves sin vínculo para acercarla al 50.3%. |
| media | flota_telemetria_enriquecida | flota_telemetria_enriquecida.Dominio → dispositivos_telemetria.Placa | cobertura de la relación | 50.3% | 52.5% | Ajustar la tasa de claves sin vínculo para acercarla al 50.3%. |
| baja | fact_incidencia_transacciones | fecha | cardinalidad | 11–100 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | fact_incidencia_transacciones | conductor | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | fact_incidencia_transacciones | producto | categoría | ORGANISMO (0.3%) | no se genera | Agregar la categoría ORGANISMO al catálogo de producto. |
| baja | fact_incidencia_transacciones | vehiculo_id | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | dominio | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | estacion | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | precio_unitario | columna solo sintética | — | decimal | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | importe_total | columna solo sintética | — | decimal | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | numero_tarjeta | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | odometro | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | hora | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | tipo_identificacion | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_incidencia_transacciones | contrato | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | id | cardinalidad | >10.000 | 1.001–10.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | fact_transacciones | fecha | cardinalidad | >10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | fact_transacciones | identificacion | cardinalidad | 1.001–10.000 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | fact_transacciones | conductor | cardinalidad | >10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | fact_transacciones | producto | categoría | NAFTA SUPER (0.3%) | no se genera | Agregar la categoría NAFTA SUPER al catálogo de producto. |
| baja | fact_transacciones | producto | categoría | D.DIESEL 500 (0.1%) | no se genera | Agregar la categoría D.DIESEL 500 al catálogo de producto. |
| baja | fact_transacciones | producto | categoría | ORGANISMO (0.0%) | no se genera | Agregar la categoría ORGANISMO al catálogo de producto. |
| baja | fact_transacciones | vehiculo_id | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | dominio | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | estacion | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | precio_unitario | columna solo sintética | — | decimal | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | importe_total | columna solo sintética | — | decimal | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | numero_tarjeta | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | odometro | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | hora | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | fact_transacciones | contrato | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | registro_de_combustible | Id | cardinalidad | >10.000 | 1.001–10.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | Hora | cardinalidad | >10.000 | 1.001–10.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | Dominio | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | Solicitante | cardinalidad | >10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | HoraRendicion | cardinalidad | >10.000 | 1.001–10.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | NumeroTicket | cardinalidad | >10.000 | 1.001–10.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | BanderaRendicion | categoría | Rojo (0.1%) | no se genera | Agregar la categoría Rojo al catálogo de BanderaRendicion. |
| baja | registro_de_combustible | RelacionConsumo | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | RelacionConsumo | categoría | P (2.3%) | no se genera | Agregar la categoría P al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | H (1.8%) | no se genera | Agregar la categoría H al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | C (1.4%) | no se genera | Agregar la categoría C al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | L (0.8%) | no se genera | Agregar la categoría L al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | R (0.4%) | no se genera | Agregar la categoría R al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | O (0.2%) | no se genera | Agregar la categoría O al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | G (0.1%) | no se genera | Agregar la categoría G al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | RelacionConsumo | categoría | ORGANISMO (0.0%) | no se genera | Agregar la categoría ORGANISMO al catálogo de RelacionConsumo. |
| baja | registro_de_combustible | FechaAnulado | cardinalidad | 101–1.000 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | EstacionServicio | cardinalidad | 2–10 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | registro_de_combustible | vehiculo_id | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | registro_de_combustible | odometro | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | registro_de_combustible | tarjeta_personal | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | registro_de_combustible | nivel_tanque | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | dispositivos_telemetria | Placa | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | MSISDN | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | Alias | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | IMEI | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | Latitud | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | Longitud | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | Odómetro (Km) | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | dispositivos_telemetria | Modelo | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | dispositivos_telemetria | Tipo | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | dispositivos_telemetria | Estado | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | dispositivos_telemetria | UltimaConexion | columna solo sintética | — | texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | padron_flota | Matricula | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | Dominio | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | Dependencia | cardinalidad | 1.001–10.000 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | TipoVehiculo | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | TipoVehiculo | categoría | PICK-UP 4X4 (1.8%) | no se genera | Agregar la categoría PICK-UP 4X4 al catálogo de TipoVehiculo. |
| baja | padron_flota | TipoVehiculo | categoría | CAMION (0.5%) | no se genera | Agregar la categoría CAMION al catálogo de TipoVehiculo. |
| baja | padron_flota | TipoVehiculo | categoría | FURGON (0.4%) | no se genera | Agregar la categoría FURGON al catálogo de TipoVehiculo. |
| baja | padron_flota | TipoVehiculo | categoría | ORGANISMO (0.8%) | no se genera | Agregar la categoría ORGANISMO al catálogo de TipoVehiculo. |
| baja | padron_flota | Marca | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | Marca | categoría | HONDA (9.9%) | no se genera | Agregar la categoría HONDA al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | VOLKSWAGEN (4.6%) | no se genera | Agregar la categoría VOLKSWAGEN al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | TOYOTA (2.4%) | no se genera | Agregar la categoría TOYOTA al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | S/D (1.7%) | no se genera | Agregar la categoría S/D al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | FORD (1.7%) | no se genera | Agregar la categoría FORD al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | PEUGEOT (1.2%) | no se genera | Agregar la categoría PEUGEOT al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | MONDIAL (0.7%) | no se genera | Agregar la categoría MONDIAL al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | YAMAHA (0.4%) | no se genera | Agregar la categoría YAMAHA al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | ZANELLA (0.4%) | no se genera | Agregar la categoría ZANELLA al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | KELLER (0.4%) | no se genera | Agregar la categoría KELLER al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | IVECO (0.3%) | no se genera | Agregar la categoría IVECO al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | CITROEN (0.3%) | no se genera | Agregar la categoría CITROEN al catálogo de Marca. |
| baja | padron_flota | Marca | categoría | ORGANISMO (1.4%) | no se genera | Agregar la categoría ORGANISMO al catálogo de Marca. |
| baja | padron_flota | Modelo | cardinalidad | 101–1.000 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | NumeroChasis | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | NumeroMotor | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | CapacidadTanque | cardinalidad | 11–100 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | NumeroTarjeta | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | Cupo | cardinalidad | 11–100 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | Estado | categoría | En Servicio (51.5%) | no se genera | Agregar la categoría En Servicio al catálogo de Estado. |
| baja | padron_flota | Estado | categoría | Tramite en Baja (35.8%) | no se genera | Agregar la categoría Tramite en Baja al catálogo de Estado. |
| baja | padron_flota | Estado | categoría | Fuera de Servicio (12.7%) | no se genera | Agregar la categoría Fuera de Servicio al catálogo de Estado. |
| baja | padron_flota | SubEstado | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | SubEstado | categoría | Tramite no iniciado en el Dpto. Transporte (37.3%) | no se genera | Agregar la categoría Tramite no iniciado en el Dpto. Transporte al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Tramite iniciado en el Dpto. Transporte (36.6%) | no se genera | Agregar la categoría Tramite iniciado en el Dpto. Transporte al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema de motor (7.0%) | no se genera | Agregar la categoría Problema de motor al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Otros problemas mecanicos (5.6%) | no se genera | Agregar la categoría Otros problemas mecanicos al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema de bateria (3.9%) | no se genera | Agregar la categoría Problema de bateria al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Siniestro (1.9%) | no se genera | Agregar la categoría Siniestro al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema electricos (1.3%) | no se genera | Agregar la categoría Problema electricos al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema de embrague (1.0%) | no se genera | Agregar la categoría Problema de embrague al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema de tren delantero (1.0%) | no se genera | Agregar la categoría Problema de tren delantero al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema de bomba (0.9%) | no se genera | Agregar la categoría Problema de bomba al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problemas de neumaticos (0.7%) | no se genera | Agregar la categoría Problemas de neumaticos al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | Problema de frenos (0.7%) | no se genera | Agregar la categoría Problema de frenos al catálogo de SubEstado. |
| baja | padron_flota | SubEstado | categoría | ORGANISMO (2.2%) | no se genera | Agregar la categoría ORGANISMO al catálogo de SubEstado. |
| baja | padron_flota | DireccionGral | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | padron_flota | FechaEstado | columna solo sintética | — | fecha como texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | flota_telemetria_enriquecida | Matricula | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | Dominio | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | Dependencia | cardinalidad | 1.001–10.000 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | TipoVehiculo | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | TipoVehiculo | categoría | PICK-UP 4X4 (1.8%) | no se genera | Agregar la categoría PICK-UP 4X4 al catálogo de TipoVehiculo. |
| baja | flota_telemetria_enriquecida | TipoVehiculo | categoría | CAMION (0.5%) | no se genera | Agregar la categoría CAMION al catálogo de TipoVehiculo. |
| baja | flota_telemetria_enriquecida | TipoVehiculo | categoría | FURGON (0.4%) | no se genera | Agregar la categoría FURGON al catálogo de TipoVehiculo. |
| baja | flota_telemetria_enriquecida | TipoVehiculo | categoría | ORGANISMO (0.8%) | no se genera | Agregar la categoría ORGANISMO al catálogo de TipoVehiculo. |
| baja | flota_telemetria_enriquecida | Marca | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | Marca | categoría | HONDA (9.9%) | no se genera | Agregar la categoría HONDA al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | VOLKSWAGEN (4.6%) | no se genera | Agregar la categoría VOLKSWAGEN al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | TOYOTA (2.4%) | no se genera | Agregar la categoría TOYOTA al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | S/D (1.7%) | no se genera | Agregar la categoría S/D al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | FORD (1.7%) | no se genera | Agregar la categoría FORD al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | PEUGEOT (1.2%) | no se genera | Agregar la categoría PEUGEOT al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | MONDIAL (0.7%) | no se genera | Agregar la categoría MONDIAL al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | YAMAHA (0.4%) | no se genera | Agregar la categoría YAMAHA al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | ZANELLA (0.4%) | no se genera | Agregar la categoría ZANELLA al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | KELLER (0.4%) | no se genera | Agregar la categoría KELLER al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | IVECO (0.3%) | no se genera | Agregar la categoría IVECO al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | CITROEN (0.3%) | no se genera | Agregar la categoría CITROEN al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Marca | categoría | ORGANISMO (1.4%) | no se genera | Agregar la categoría ORGANISMO al catálogo de Marca. |
| baja | flota_telemetria_enriquecida | Modelo | cardinalidad | 101–1.000 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | NumeroChasis | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | NumeroMotor | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | CapacidadTanque | cardinalidad | 11–100 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | NumeroTarjeta | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | Cupo | cardinalidad | 11–100 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | Estado | categoría | En Servicio (51.5%) | no se genera | Agregar la categoría En Servicio al catálogo de Estado. |
| baja | flota_telemetria_enriquecida | Estado | categoría | Tramite en Baja (35.8%) | no se genera | Agregar la categoría Tramite en Baja al catálogo de Estado. |
| baja | flota_telemetria_enriquecida | Estado | categoría | Fuera de Servicio (12.7%) | no se genera | Agregar la categoría Fuera de Servicio al catálogo de Estado. |
| baja | flota_telemetria_enriquecida | SubEstado | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Tramite no iniciado en el Dpto. Transporte (37.3%) | no se genera | Agregar la categoría Tramite no iniciado en el Dpto. Transporte al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Tramite iniciado en el Dpto. Transporte (36.6%) | no se genera | Agregar la categoría Tramite iniciado en el Dpto. Transporte al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema de motor (7.0%) | no se genera | Agregar la categoría Problema de motor al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Otros problemas mecanicos (5.6%) | no se genera | Agregar la categoría Otros problemas mecanicos al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema de bateria (3.9%) | no se genera | Agregar la categoría Problema de bateria al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Siniestro (1.9%) | no se genera | Agregar la categoría Siniestro al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema electricos (1.3%) | no se genera | Agregar la categoría Problema electricos al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema de embrague (1.0%) | no se genera | Agregar la categoría Problema de embrague al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema de tren delantero (1.0%) | no se genera | Agregar la categoría Problema de tren delantero al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema de bomba (0.9%) | no se genera | Agregar la categoría Problema de bomba al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problemas de neumaticos (0.7%) | no se genera | Agregar la categoría Problemas de neumaticos al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | Problema de frenos (0.7%) | no se genera | Agregar la categoría Problema de frenos al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | SubEstado | categoría | ORGANISMO (2.2%) | no se genera | Agregar la categoría ORGANISMO al catálogo de SubEstado. |
| baja | flota_telemetria_enriquecida | DireccionGral | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | matricula_num | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | flota_telemetria_enriquecida | FechaEstado | columna solo sintética | — | fecha como texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | base.reporte_proveedor_1_facturacion | id | cardinalidad | 0 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | base.reporte_proveedor_1_facturacion | fecha | cardinalidad | 0 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | base.reporte_proveedor_1_facturacion | contrato_origen | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | base.reporte_proveedor_1_facturacion | contrato_destino | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
| baja | base.reporte_proveedor_1_facturacion | monto | columna solo sintética | — | entero | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
