# Bitácora del proyecto

Registro de los cambios importantes y del **por qué** de cada uno. El detalle técnico está en el historial de git; acá queda lo que conviene recordar al retomar el trabajo o al presentar avances.

**Cómo agregar una entrada:** una fila nueva arriba de todo en la tabla, con la fecha, qué cambió, por qué y quién lo decidió. La página **Documentación** de la aplicación muestra además los últimos commits.

| Fecha | Cambio | Por qué | Decidió |
|---|---|---|---|
| 2026-09-29 | Forma de cargar del escenario realista calibrada con la auditoría agregada: cargas más frecuentes que completan el tanque, nivel de carga por vehículo (las motos, casi vacías), km por tipo, segundo turno, tarjetas personales y cargas en otra red como proporción de las cargas (versión 2.2) | La auditoría mostró unas 7 cargas por mes por vehículo en servicio (el generador tenía 3,4), 35 L por carga en la mediana, rendimiento estable y días con dos cargas; el modelo entrenado con datos sintéticos no se parecía a lo real | Equipo |
| 2026-09-29 | La auditoría concilia la facturación solo en los meses completos del reporte y cruza el registro solo en los días que trae el reporte | El sistema de origen es nuevo y le faltan quincenas o meses; sin este límite, los pedidos y las líneas de esos días quedaban como irregularidades | Equipo |
| 2026-09-28 | Las reglas con contexto y el modelo intercalan las cargas de otra red del registro interno; la auditoría informa el alcance y la cobertura de cada fuente; en el generador, las cargas del mismo día siguen en horario el orden del odómetro (versión 2.1) | Las fuentes reales de consumo y facturación son de un solo proveedor y las cargas se hacen en tres redes: sin las otras, los tramos entre cargas parecen saltos o rendimientos imposibles | Equipo |
| 2026-09-27 | Auditoría agregada: adaptador de las fuentes reales al esquema del generador y corrida de reglas y modelos con salida solo agregada | Medir, sin traer datos reales, cuánto marcan las reglas en la realidad y si el modelo entrenado con datos sintéticos generaliza | Equipo |
| 2026-09-27 | Documento del modelo de ML: métodos, por qué se eligieron, entrenamiento y plan de implementación con datos reales | Explicar el componente de priorización para la presentación y dejar escrito cómo llevarlo a operación | Equipo |
| 2026-09-26 | Base de datos SQLite del escenario realista: migraciones versionadas, maestros con vigencia, carga repetible e incremental y vistas de control | Hacer verificable la integridad, dejar los controles en SQL portable y documentar una propuesta de mejora para la fuente real | Equipo |
| 2026-09-26 | Grupo de cada dispositivo, dispositivos en depósito de los móviles de baja e H11 | Regla de la fuente: los móviles de baja no llevan telemetría y, si la tuvieron, el dispositivo debe quedar en depósito; uno activo en un móvil de baja es una alerta | Equipo |
| 2026-09-26 | Facturación por contrato, mes y familia a precio de empresa, con deuda, PDF y conciliación triple; H9 ampliada | En la fuente el proveedor factura cada contrato a precio de empresa y la deuda, el PDF y el consumo deben coincidir | Equipo |
| 2026-09-26 | Registro interno en lugar de las solicitudes del realista, tarjetas personales e H8 reformulada (cruce voraz del sistema operativo frente a cruce con contexto) | Las solicitudes con litros autorizados no reflejaban el circuito real: pedido, rendición con ticket, anulaciones, estaciones de otra red y tarjetas personales | Equipo |
| 2026-09-26 | Contratos con cupo mensual, transferencias preventivas según la proyección a fin de mes e H10 | En la realidad cada tarjeta descuenta de un contrato con tope y el saldo se reparte entre contratos antes de que se corte el suministro | Equipo |
| 2026-09-26 | Flota del escenario realista calibrada con el perfil de las fuentes: estados, telemetría por estado, tipos, combustibles, productos y formatos de dominio; dominios con otro formato bajan a 0,5% | El generador suponía 88% de telemetría pareja y casi toda la flota en servicio; la fuente muestra 48% fuera de servicio o en baja | Equipo |
| 2026-09-25 | Formatos de origen en el escenario realista: dominios con otro formato y fechas de solicitud en dos formatos; H1 pasa a contrastarse (exacto vs. normalizado) | Los datos salían perfectamente limpios; la propuesta de defectos de calidad del PR #6 mostró que faltaba ejercitar la normalización | Equipo |
| 2026-09-25 | Perfilador de fuentes y página Perfil de fuentes | Saber qué le falta al generador frente a fuentes externas sin traer sus datos: solo estructura y calidad agregadas, con revisión manual antes de versionar | Equipo |
| 2026-09-25 | Página de documentación con variables vivas y esta bitácora | Tener el contexto vigente de la documentación dentro de la aplicación y poder descargarlo | Equipo |
| 2026-09-24 | Diccionario de datos generado por el generador (`diccionario.json`) y página Diccionario de datos | Que la descripción de tablas y relaciones no se desactualice: un test la compara con lo que se genera | Equipo |
| 2026-09-24 | Página de análisis unificada con el catálogo de hipótesis (H1 a H9) | Las páginas de análisis e hipótesis usaban reglas distintas y se contradecían | Equipo |
| 2026-09-24 | Circuito solicitud → carga → factura (H8 y H9) | Verificar la coherencia entre lo solicitado, lo cargado y lo facturado | Equipo |
| 2026-09-24 | Escenario realista con casos legítimos y reglas con contexto (H2b a H7) | Con anomalías inconfundibles las reglas daban 100% y la comparación con ML no decía nada | Equipo |
| 2026-09-24 | Modelo supervisado y priorización de la revisión | Que el ML responda qué revisar primero con un presupuesto de revisión, con el motivo de cada caso | Equipo |
| 2026-09-24 | Ground truth en el generador, detección por reglas e Isolation Forest | Poder evaluar la detección contra una verdad de referencia | Equipo |
| 2026-09-24 | Generador oficial único; versiones anteriores a `legacy/` y datos regenerables fuera de git | Había ocho generadores con flujos contradictorios | Equipo |
| 2026-09-23 | Arreglo de la página principal de la aplicación | Leía una fuente de datos que no existe en el despliegue | Equipo |
| 2026-09-22 | Aplicación Streamlit y consolidación del Sprint 1 | Presentar los resultados de forma interactiva | Equipo |
| 2026-09-10 | Pipeline v7.5 y generadores de consumo, combustible y facturas | Capas 3 y 4 del Sprint 1 | Equipo |
| 2026-09-03 | Notebooks y análisis del Encuentro 1 | Primer análisis exploratorio | Equipo |
| 2026-08-19 | Propuesta del encuentro inicial y roles del equipo | Definir alcance y responsabilidades | Equipo |
| 2026-08-16 | Fundación: gobierno, alcance, modelo de datos y primer generador | Base documental y reglas de trabajo del proyecto | Equipo |
