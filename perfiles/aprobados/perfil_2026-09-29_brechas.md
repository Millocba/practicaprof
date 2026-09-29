# Brechas entre la fuente real y el generador

- Perfil real: origen **flota**, generado 2026-09-29, revisado: sí.
- Perfil sintético: **sintético (realista)**.
- Brechas: 9 altas, 63 medias, 41 bajas.

| Severidad | Tabla real | Columna | Aspecto | Real | Sintético | Sugerencia |
|---|---|---|---|---|---|---|
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | Color | columna no modelada | texto · AAAAAAAAAAAAA, AAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | Procedencia | columna no modelada | texto · AAAAAAAAAA, AAAAAAAAA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | RelacionConsumo | columna no modelada | texto · A | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | ExcepcionOdometro | columna no modelada | texto · AA | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | FechaHastaExcepcionOdometro | columna no modelada | fecha como texto · 99/99/9999 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroContrato | columna no modelada | entero · 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | RetiraDni | columna no modelada | entero · 99999999, 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | RetiraNombre | columna no modelada | texto · TEXTO_MAS_DE_40 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| alta | 5edec563-8acd-4f59-acc3-8c0abf226702 | Cupo | columna no modelada | entero · 99, 9 | — | Agregar la columna al generador (con su tipo y formato) o documentar por qué no se usa. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Matricula | formato | 9999 (50.7%) | no se genera | Agregar el formato 9999 a Matricula (aparece en el 50.7% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Matricula | formato | A-9999 (23.5%) | no se genera | Agregar el formato A-9999 a Matricula (aparece en el 23.5% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Matricula | formato | 99999 (22.9%) | no se genera | Agregar el formato 99999 a Matricula (aparece en el 22.9% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Matricula | calidad | números guardados como texto: 73.8% | 0% | Inyectar números guardados como texto en Matricula (~73.8%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dominio | formato | AA999AA (52.2%) | no se genera | Agregar el formato AA999AA a Dominio (aparece en el 52.2% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dominio | formato | AAA999 (22.1%) | no se genera | Agregar el formato AAA999 a Dominio (aparece en el 22.1% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dominio | formato | A999AAA (20.8%) | no se genera | Agregar el formato A999AAA a Dominio (aparece en el 20.8% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dominio | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.2% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en Dominio (~1.2%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dependencia | formato | TEXTO_21-40 (16.1%) | no se genera | Agregar el formato TEXTO_21-40 a Dependencia (aparece en el 16.1% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dependencia | calidad | espacios al inicio, al final o dobles: 2.0% | 0% | Inyectar espacios al inicio, al final o dobles en Dependencia (~2.0%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | formato | AAAAAAAA (11.3%) | no se genera | Agregar el formato AAAAAAAA a Marca (aparece en el 11.3% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.7% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en Marca (~1.7%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | AAAAAAAA (17.0%) | no se genera | Agregar el formato AAAAAAAA a Modelo (aparece en el 17.0% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | AAAAAA (15.9%) | no se genera | Agregar el formato AAAAAA a Modelo (aparece en el 15.9% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | AAAAA (14.1%) | no se genera | Agregar el formato AAAAA a Modelo (aparece en el 14.1% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | AAA999 (11.2%) | no se genera | Agregar el formato AAA999 a Modelo (aparece en el 11.2% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | A99 (9.1%) | no se genera | Agregar el formato A99 a Modelo (aparece en el 9.1% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | AA (8.3%) | no se genera | Agregar el formato AA a Modelo (aparece en el 8.3% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | formato | AAAA (6.7%) | no se genera | Agregar el formato AAAA a Modelo (aparece en el 6.7% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | calidad | mayúsculas y minúsculas mezcladas: 3.8% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Modelo (~3.8%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | calidad | números guardados como texto: 1.6% | 0% | Inyectar números guardados como texto en Modelo (~1.6%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | faltantes | 37.4% | 0% | Ajustar la tasa de vacíos de NumeroChasis a cerca de 37.4%. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | formato | 9AAAA99A9AA999999 (25.0%) | no se genera | Agregar el formato 9AAAA99A9AA999999 a NumeroChasis (aparece en el 25.0% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | formato | 9AAAAAA99AAA99999 (15.7%) | no se genera | Agregar el formato 9AAAAAA99AAA99999 a NumeroChasis (aparece en el 15.7% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | formato | 9AA999AA9AA999999 (10.7%) | no se genera | Agregar el formato 9AA999AA9AA999999 a NumeroChasis (aparece en el 10.7% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | formato | 9 (7.9%) | no se genera | Agregar el formato 9 a NumeroChasis (aparece en el 7.9% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.5% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en NumeroChasis (~1.5%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | calidad | mayúsculas y minúsculas mezcladas: 5.4% | 0% | Inyectar mayúsculas y minúsculas mezcladas en NumeroChasis (~5.4%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | calidad | números guardados como texto: 10.8% | 0% | Inyectar números guardados como texto en NumeroChasis (~10.8%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | faltantes | 37.5% | 0% | Ajustar la tasa de vacíos de NumeroMotor a cerca de 37.5%. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | formato | AA99A999A999999 (29.8%) | no se genera | Agregar el formato AA99A999A999999 a NumeroMotor (aparece en el 29.8% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | formato | AA999AAA99999 (17.4%) | no se genera | Agregar el formato AA999AAA99999 a NumeroMotor (aparece en el 17.4% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | formato | 999999999999999 (13.5%) | no se genera | Agregar el formato 999999999999999 a NumeroMotor (aparece en el 13.5% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | formato | 9 (7.9%) | no se genera | Agregar el formato 9 a NumeroMotor (aparece en el 7.9% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | calidad | espacios al inicio, al final o dobles: 3.3% | 0% | Inyectar espacios al inicio, al final o dobles en NumeroMotor (~3.3%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | calidad | vacíos escritos como texto ("-", "S/D", "N/A"): 1.6% | 0% | Inyectar vacíos escritos como texto ("-", "S/D", "N/A") en NumeroMotor (~1.6%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | calidad | números guardados como texto: 24.8% | 0% | Inyectar números guardados como texto en NumeroMotor (~24.8%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Año | formato | 9 (7.6%) | no se genera | Agregar el formato 9 a Año (aparece en el 7.6% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | CapacidadTanque | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | CapacidadTanque | formato | 99 (92.6%) | no se genera | Agregar el formato 99 a CapacidadTanque (aparece en el 92.6% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | CapacidadTanque | formato | 9 (6.5%) | no se genera | Agregar el formato 9 a CapacidadTanque (aparece en el 6.5% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroTarjeta | tipo | número como texto | texto | En la fuente real es número como texto; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroTarjeta | faltantes | 4.5% | 0% | Ajustar la tasa de vacíos de NumeroTarjeta a cerca de 4.5%. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroTarjeta | formato | 99999999999999999 (98.5%) | no se genera | Agregar el formato 99999999999999999 a NumeroTarjeta (aparece en el 98.5% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteSaldo | formato | 9999999.9 (39.8%) | no se genera | Agregar el formato 9999999.9 a LimiteSaldo (aparece en el 39.8% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteSaldo | formato | 99999.9 (35.4%) | no se genera | Agregar el formato 99999.9 a LimiteSaldo (aparece en el 35.4% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteSaldo | formato | 999999.99 (9.1%) | no se genera | Agregar el formato 999999.99 a LimiteSaldo (aparece en el 9.1% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteSaldo | formato | 99999.99 (5.0%) | no se genera | Agregar el formato 99999.99 a LimiteSaldo (aparece en el 5.0% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteSaldo | escala (mediana) | 1000000.0 | 5600.0 | La mediana real es 178.6 veces la sintética: revisar el rango que se genera. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteLitros | tipo | entero | decimal | En la fuente real es entero; generar la columna con ese tipo o normalizarla en la limpieza. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteLitros | formato | 9999 (52.4%) | no se genera | Agregar el formato 9999 a LimiteLitros (aparece en el 52.4% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteLitros | formato | 999 (38.3%) | no se genera | Agregar el formato 999 a LimiteLitros (aparece en el 38.3% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | LimiteLitros | escala (mediana) | 1400.0 | 310.0 | La mediana real es 4.5 veces la sintética: revisar el rango que se genera. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Estado | formato | AAAAAAA AA AAAA (35.8%) | no se genera | Agregar el formato AAAAAAA AA AAAA a Estado (aparece en el 35.8% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Estado | formato | AAAAA AA AAAAAAAA (12.6%) | no se genera | Agregar el formato AAAAA AA AAAAAAAA a Estado (aparece en el 12.6% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | Estado | calidad | mayúsculas y minúsculas mezcladas: 100.0% | 0% | Inyectar mayúsculas y minúsculas mezcladas en Estado (~100.0%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | faltantes | 51.6% | 0% | Ajustar la tasa de vacíos de SubEstado a cerca de 51.6%. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | formato | AAAAAAA AA AAAAAAAA AA AA AAAA. AAAAAAAAAA (37.4%) | no se genera | Agregar el formato AAAAAAA AA AAAAAAAA AA AA AAAA. AAAAAAAAAA a SubEstado (aparece en el 37.4% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | formato | AAAAAAA AAAAAAAA AA AA AAAA. AAAAAAAAAA (36.6%) | no se genera | Agregar el formato AAAAAAA AAAAAAAA AA AA AAAA. AAAAAAAAAA a SubEstado (aparece en el 36.6% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | formato | AAAAAAAA AA AAAAA (7.9%) | no se genera | Agregar el formato AAAAAAAA AA AAAAA a SubEstado (aparece en el 7.9% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | formato | AAAAA AAAAAAAAA AAAAAAAAA (5.6%) | no se genera | Agregar el formato AAAAA AAAAAAAAA AAAAAAAAA a SubEstado (aparece en el 5.6% de la fuente real). |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | calidad | mayúsculas y minúsculas mezcladas: 100.0% | 0% | Inyectar mayúsculas y minúsculas mezcladas en SubEstado (~100.0%) y registrarlo en el ground truth. |
| media | 5edec563-8acd-4f59-acc3-8c0abf226702 | DireccionGral | formato | TEXTO_MAS_DE_40 (11.2%) | no se genera | Agregar el formato TEXTO_MAS_DE_40 a DireccionGral (aparece en el 11.2% de la fuente real). |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Matricula | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dominio | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Dependencia | cardinalidad | 1.001–10.000 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Identificable | categoría | NO (20.5%) | no se genera | Agregar la categoría NO al catálogo de Identificable. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | TipoVehiculo | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | TipoVehiculo | categoría | PICK-UP 4X4 (1.8%) | no se genera | Agregar la categoría PICK-UP 4X4 al catálogo de TipoVehiculo. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | TipoVehiculo | categoría | FURGON (0.4%) | no se genera | Agregar la categoría FURGON al catálogo de TipoVehiculo. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | FIAT (24.0%) | no se genera | Agregar la categoría FIAT al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | NISSAN (20.6%) | no se genera | Agregar la categoría NISSAN al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | KAWASAKI (11.2%) | no se genera | Agregar la categoría KAWASAKI al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | S/D (1.7%) | no se genera | Agregar la categoría S/D al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | PEUGEOT (1.2%) | no se genera | Agregar la categoría PEUGEOT al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | MONDIAL (0.7%) | no se genera | Agregar la categoría MONDIAL al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | YAMAHA (0.4%) | no se genera | Agregar la categoría YAMAHA al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | KELLER (0.4%) | no se genera | Agregar la categoría KELLER al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | ZANELLA (0.4%) | no se genera | Agregar la categoría ZANELLA al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Marca | categoría | CITROEN (0.3%) | no se genera | Agregar la categoría CITROEN al catálogo de Marca. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Modelo | cardinalidad | 101–1.000 | 11–100 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroChasis | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroMotor | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | CapacidadTanque | cardinalidad | 11–100 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | NumeroTarjeta | cardinalidad | 1.001–10.000 | 101–1.000 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Estado | categoría | En Servicio (51.6%) | no se genera | Agregar la categoría En Servicio al catálogo de Estado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Estado | categoría | Tramite en Baja (35.8%) | no se genera | Agregar la categoría Tramite en Baja al catálogo de Estado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | Estado | categoría | Fuera de Servicio (12.6%) | no se genera | Agregar la categoría Fuera de Servicio al catálogo de Estado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Tramite no iniciado en el Dpto. Transporte (37.4%) | no se genera | Agregar la categoría Tramite no iniciado en el Dpto. Transporte al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Tramite iniciado en el Dpto. Transporte (36.6%) | no se genera | Agregar la categoría Tramite iniciado en el Dpto. Transporte al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema de motor (7.0%) | no se genera | Agregar la categoría Problema de motor al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Otros problemas mecanicos (5.6%) | no se genera | Agregar la categoría Otros problemas mecanicos al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema de bateria (3.9%) | no se genera | Agregar la categoría Problema de bateria al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Siniestro (1.8%) | no se genera | Agregar la categoría Siniestro al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema electricos (1.3%) | no se genera | Agregar la categoría Problema electricos al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema de embrague (1.0%) | no se genera | Agregar la categoría Problema de embrague al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema de tren delantero (1.0%) | no se genera | Agregar la categoría Problema de tren delantero al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema de bomba (0.9%) | no se genera | Agregar la categoría Problema de bomba al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problemas de neumaticos (0.7%) | no se genera | Agregar la categoría Problemas de neumaticos al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | SubEstado | categoría | Problema de frenos (0.7%) | no se genera | Agregar la categoría Problema de frenos al catálogo de SubEstado. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | DireccionGral | cardinalidad | 11–100 | 2–10 | Revisar la cantidad de valores distintos que produce el generador. |
| baja | 5edec563-8acd-4f59-acc3-8c0abf226702 | FechaEstado | columna solo sintética | — | fecha como texto | La fuente real no la tiene con ese nombre: revisar si se llama distinto. |
