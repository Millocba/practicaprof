# Bitácora del proyecto

Registro de los cambios importantes y del **por qué** de cada uno. El detalle técnico está en el historial de git; acá queda lo que conviene recordar al retomar el trabajo o al presentar avances.

**Cómo agregar una entrada:** una fila nueva arriba de todo en la tabla, con la fecha, qué cambió, por qué y quién lo decidió. La página **Documentación** de la aplicación muestra además los últimos commits.

| Fecha | Cambio | Por qué | Decidió |
|---|---|---|---|
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
