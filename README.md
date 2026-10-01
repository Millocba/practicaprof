# Proyecto de análisis y auditoría de datos de flotas

Proyecto académico colaborativo centrado en el ciclo completo de los datos: generación, calidad, limpieza, integración, análisis exploratorio, visualización y detección de anomalías.

## Declaración sobre los datos

Este proyecto utiliza exclusivamente **datos sintéticos generados desde cero** con fines educativos. No contiene información real de personas, instituciones, vehículos, contratos, tarjetas, dispositivos o ubicaciones. No es un conjunto de datos anonimizado ni una reproducción exacta de una organización existente. Cualquier semejanza con entidades reales es accidental.

Los futuros generadores serán reproducibles mediante semillas configurables. Las anomalías se inyectarán deliberadamente y sus etiquetas de evaluación se mantendrán separadas de los datos disponibles para los modelos.

## Motivación

El proyecto nace de una pregunta pequeña: **¿qué podemos aprender al observar con curiosidad la calidad y el comportamiento de datos operativos de una flota?**

Esa exploración conduce a preguntas más amplias: cómo corregir inconsistencias, vincular fuentes heterogéneas, producir indicadores confiables, explicar comportamientos y detectar eventos que merecen revisión. El resultado esperado no es solo una aplicación, sino un proceso analítico trazable y defendible.

## Objetivo general

Diseñar y evaluar un sistema reproducible de apoyo al análisis y la auditoría de una flota ficticia mediante datos sintéticos, integración de fuentes y detección explicable de anomalías.

## Objetivos específicos

- Diseñar un modelo coherente de datos sintéticos relacionados.
- Medir y mejorar calidad, completitud, consistencia y unicidad.
- Integrar flota, telemetría, recorridos, consumo y contratos ficticios.
- Desarrollar análisis exploratorios e indicadores reproducibles.
- Comparar reglas de negocio, métodos estadísticos y modelos de aprendizaje automático.
- Evaluar resultados con una verdad de referencia sintética.
- Comunicar hallazgos, supuestos, errores y limitaciones.

## Alcance previsto

1. Generación reproducible de entidades y eventos sintéticos.
2. Validación, perfilado y limpieza.
3. Transformación e integración entre fuentes.
4. Análisis descriptivo y exploratorio.
5. KPIs y visualizaciones.
6. Reglas de control como línea base.
7. Detección estadística y aprendizaje automático.
8. Evaluación, interpretabilidad y análisis de errores.
9. Capas técnicas de soporte para consultar y presentar resultados.

## Hipótesis iniciales

- Las inconsistencias de los datos afectan la confiabilidad de los indicadores.
- Integrar fuentes permite detectar situaciones invisibles en análisis aislados.
- El consumo puede explicarse parcialmente mediante características, actividad e historial del vehículo.
- Las reglas de control identifican una parte relevante de los eventos irregulares.

## Hipótesis emergentes

- Algunos aparentes problemas de consumo provienen de errores de vinculación.
- La ausencia de telemetría también puede constituir una señal.
- Los umbrales adecuados varían según el tipo de vehículo y su contexto.
- El historial individual puede resultar más informativo que un umbral general.
- Combinar reglas, estadística robusta y ML puede reducir falsas alertas.
- En auditoría, la trazabilidad puede ser tan importante como la precisión.

Estas hipótesis deberán contrastarse; no representan conclusiones anticipadas.

## ML propuesto

La detección de anomalías comparará una línea base de reglas con métodos estadísticos robustos y modelos no supervisados. Si la generación proporciona etiquetas suficientes, también podrá evaluarse un enfoque supervisado. La selección definitiva dependerá de los experimentos, no de preferencias previas.

## Estado actual

- **Generador oficial**: [`generator_pipeline_maestro.py`](generator_pipeline_maestro.py) produce cinco entidades relacionadas (flota, telemetría, consumo, solicitudes y facturación) y un `ground_truth.csv` con cada anomalía inyectada. La misma semilla produce los mismos datos. Tiene dos escenarios:
  - **Didáctico**: anomalías inconfundibles, para explicar el método.
  - **Realista**: cada vehículo se simula día por día (consumo según su rendimiento, cargas cuando baja el tanque, GPS diario) y el circuito **solicitud → carga → factura** es coherente: cada carga tiene su solicitud y cada proveedor factura por mes con detalle línea por línea. Incluye anomalías sutiles, cruces entre fuentes y **casos legítimos que se parecen a anomalías** (`casos_legitimos.csv`), con una prevalencia cercana al 1%.
- **Detección**: reglas ingenuas y reglas con contexto, un Isolation Forest y un modelo supervisado, evaluados contra el ground truth (paquete [`deteccion/`](deteccion/)).
- **Aplicación**: Streamlit con generación, exploración, análisis, detección, contraste de hipótesis y priorización de la revisión ([`streamlit_app/`](streamlit_app/README.md)).
- **Tests**: `python -m pytest` cubre generador, reglas, modelo y páginas, y se ejecuta en cada push.
- Las versiones anteriores del generador se conservan en [`legacy/`](legacy/EVOLUCION.md).

### Resultados preliminares

Promedio de 5 semillas, 200 vehículos cada una.

**Escenario didáctico**

| Método | Precision | Recall | F1 |
|---|---|---|---|
| Reglas (línea base) | 1,00 | 1,00 | 1,00 |
| Isolation Forest | 0,73 | 0,82 | 0,77 |

- Las reglas son perfectas porque se diseñaron conociendo cómo se inyectan las anomalías sintéticas: funcionan como techo de referencia, no como desempeño esperable con datos reales.
- En los saltos de odómetro (H2), comparar con el historial del propio vehículo detecta el 100% de los casos, contra el 25% de un umbral fijo.
- Isolation Forest encuentra todas las anomalías de odómetro, pero solo el 76% de los excesos volumétricos: los vehículos con exceso forman un grupo denso que deja de parecer atípico.

**Escenario realista: hipótesis.** La flota está calibrada con el perfil agregado de las fuentes reales: 52% en servicio, 13% fuera de servicio y 36% en trámite de baja; telemetría en el 80% de los vehículos en servicio y casi ninguno de baja; sedanes, pick-ups y motos. Con la auditoría agregada se calibró además la forma de cargar: los vehículos cargan seguido y completan el tanque (unas 8 cargas por mes por vehículo en servicio, contra 7 en la fuente; mediana de 32 L por carga, contra 35 L), el 7% de las cargas cae en días con dos cargas por un segundo turno y el 7% de los pedidos es de otra red. Cada hipótesis compara una regla ingenua con una regla con contexto; se sostiene si el F1 mejora al menos 0,10. Las 14 (H1 a H13, con H2b, H2c y H3b) se sostienen en las 5 semillas.

| | Hipótesis | F1 ingenua → con contexto | Falsas alarmas por casos legítimos |
|---|---|---|---|
| H1 | Normalizar el dominio (mayúsculas, sin espacios ni guiones) antes de vincular con la flota deja solo los dominios que no corresponden a ningún vehículo; las tarjetas personales se identifican por la persona | 0,29 → 1,00 | 555 → 0 |
| H2b | Distinguir un odómetro nuevo o un error de tipeo elimina las falsas alarmas de retroceso, sin perder adulteraciones leves | 0,67 → 0,88 | 25 → 0 |
| H2c | Un salto sobre el ritmo habitual se confirma descartando errores de tipeo y cruzando con el GPS | 0,00 (umbral fijo) · 0,41 (historial) → 1,00 | 767 · 14 → 0 |
| H3b | Solo el exceso volumétrico que aparece después indica un problema; el que existe desde el inicio es un tanque no registrado | 0,40 → 0,97 | 286 → 13 |
| H4 | El fraccionamiento evade el control por transacción; lo revela la suma del día y el recorrido separa los viajes largos | 0,00 (por carga) · 0,07 (fuente: <6 h) · 0,35 (por día) → 0,77 | 248 · 74 → 9 |
| H5 | Una carga sin recorrido que la justifique solo se ve con el rendimiento km/L frente al habitual, y sin repetir las cargas que ya explicó otra regla | 0,00 · 0,25 (fuente: mediana del tipo, −30%) → 0,83 | 286 · 0 → 0 |
| H6 | Las cargas a vehículos de baja o fuera de servicio solo se detectan cruzando con el estado de la flota | 0,00 → 1,00 | — |
| H7 | El recorrido del GPS distingue una tarjeta usada en otro lado de un viaje real | 0,62 → 0,90 | 39 → 6 |
| H8 | El cruce diario por dominio de un sistema operativo, voraz y sin tolerancias, confunde las tarjetas personales y las rendiciones pendientes con cargas sin respaldo y no ve los registros anulados, los desacuerdos de litros ni los excesos; cruzar por dominio (el del vehículo de la tarjeta) o persona y horario, con asignación óptima y tolerancias, los separa | 0,11 → 0,98 | 567 → 0 |
| H9 | Comparar lo facturado a cada contrato con su consumo a precio del surtidor confunde el descuento de empresa, los desfases de corte y los ajustes con diferencias; la conciliación triple (deuda, PDF y consumo) y cada línea contra su carga detectan cargas inexistentes, duplicadas, sobreprecios, cobros al precio del surtidor, renglones que no son combustible, deudas infladas y PDF que no coinciden (evaluada por factura) | 0,33 → 1,00 | 127 → 0 |
| H10 | Comparar el consumo del mes con el tope confunde las transferencias de saldo legítimas con problemas y no ve las innecesarias; el saldo diario con la proyección a fin de mes separa unas de otras y encuentra las cargas con el saldo agotado (evaluada por contrato y mes) | 0,17 → 0,91 | 41 → 3 |
| H11 | Marcar todo móvil de baja con dispositivo confunde los aparatos retirados al depósito con los que siguen funcionando; el grupo del dispositivo y su última transmisión dejan solo los móviles que irían a desguace con el aparato activo (pocos casos: 2 anomalías y unos 3 dispositivos en depósito por dataset) | 0,57 → 1,00 | 15 → 0 |
| H12 | Marcar toda carga cuyo odómetro no avanza confunde los vehículos con una excepción de odómetro vigente con los que no informan la lectura; la excepción del día de cada carga (puede durar un solo día) deja solo las lecturas repetidas sin justificación | 0,18 · 0,51 (fuente: <5 km, excepción de hoy) → 0,81 | 533 · 41 → 0 |
| H13 | Marcar toda transacción de contingencia confunde las contingencias legítimas con los cobros duplicados; buscar una carga del mismo vehículo por el medio habitual a menos de 12 horas y con hasta 2% de diferencia de litros deja solo los posibles dobles cobros | 0,17 → 1,00 | 381 → 0 |

- En H5 el GPS no mejora al odómetro, porque en esos vehículos el odómetro no está adulterado. La mayoría de sus falsos positivos eran otras anomalías que también cargan sin recorrido: H5 ya no evalúa el rendimiento de los días que H3b, H4, H6 o H7 explican por su cuenta, porque ahí el bajo rendimiento es consecuencia y no el hecho. El descarte es por día y no por carga, ya que el rendimiento es una propiedad del día. Con el umbral en 0,3 baja de 48 a 34 alertas y de 15 a 1 el falso positivo, sin perder ningún acierto; con el de 0,4 baja de 91 a 43 y de 57 a 9. Ojo con la circularidad: H4 también usa el rendimiento para separar los viajes largos, así que un día que H4 ya marcó tampoco se evalúa acá.
- **H5: curva del umbral con el descarte.** Medido con las 5 semillas del README y 200 vehículos, 45 anomalías reales en total. "F1 medio" es el promedio de las 5 semillas y "F1 peor" la peor de las 5:

  | Umbral | Alertas | Aciertos | Falsos positivos | Recall | F1 medio | F1 peor |
  |---|---|---|---|---|---|---|
  | 0,40 (el anterior) | 43 | 34 | 9 | 0,756 | 0,781 | 0,667 |
  | 0,35 | 39 | 34 | 5 | 0,756 | 0,816 | 0,667 |
  | 0,32 | 37 | 34 | 3 | 0,756 | 0,835 | 0,667 |
  | 0,30 | 34 | 33 | 1 | 0,733 | 0,841 | 0,667 |

  Entre 0,32 y 0,40 no se pierde recall, y 0,32 es el mejor de esa ventana: +0,054 de F1 medio sobre el 0,40 con el mismo peor caso y seis alertas menos. Bajarlo a 0,30 suma solo 0,006 más y cuesta un acierto de 45. Elegir entre 0,32 y 0,30 es del dueño del código; el issue pide no perder recall, así que 0,32 cumple y 0,30 no.
- **H5: criterio de la fuente.** La fuente compara el rendimiento con la mediana del tipo de vehículo (no con la del propio), avisa si está más de un 30% por debajo y descarta los tramos de más de 2.000 km por error de tipeo. Medido como lo hace la fuente (excluyendo solo las cargas con excepción vigente): encuentra las 45 anomalías, recall 1,00, pero su F1 queda en 0,25 porque marca 323 cargas de las que 278 no son ni anomalías ni casos legítimos. Queda como nivel intermedio y no se adopta: acerca el recall y aleja el F1. Con el descarte de lo que ya explican otras reglas, su F1 sube a 0,50 y marca 135.
- H5 no evalúa las cargas con el odómetro exceptuado ni las que no avanzan sin excepción: esas las ve H12. Es el techo del recall de H5 y es una decisión de diseño: sin ese descarte el recall sería 0,978 en lugar de 0,733, pero las alertas subirían de 34 a 103 y el F1 caería de 0,835 a 0,595.
- El reporte de consumo es de un solo proveedor, pero el registro interno anota las cargas de todas las redes con su odómetro y sus litros. Las reglas con contexto de H2b, H2c, H4 y H5 intercalan esas cargas en la secuencia de cada vehículo: sin ellas, el tramo entre dos cargas del reporte incluye lo recorrido con combustible de otra red y parece un salto o un rendimiento imposible. Las reglas ingenuas usan solo el reporte.
- En H12, el padrón indica si cada vehículo tiene hoy una excepción de odómetro (`ExcepcionOdometro`, 1,5% de la flota, como en la fuente) y hasta cuándo; `excepciones_odometro.csv` guarda el historial, porque la vigencia se mira el día de cada carga. Mientras rige, la carga repite la última lectura; al terminar, la lectura vuelve al valor real, y las reglas de saltos comparan con la última lectura que avanzó. Dos cargas del mismo día con la misma lectura no son una alerta: no se vuelve a leer el tablero. Los falsos positivos que quedan son otras anomalías (cargas que no llegaron al vehículo, que tampoco avanzan el odómetro).
- En H13, el reporte trae el origen de cada transacción (`origen_transaccion`: `POSNET` o `CONTINGENCIA`, 1,2% de contingencias como en la fuente). Un doble cobro es la misma carga cobrada por las dos vías; se factura con su propia línea, que H9 no cuenta como `LINEA_DUPLICADA` (son dos transacciones distintas), y no cuenta como una carga más en las reglas de odómetro, de cargas del día y del cruce con el registro. Cuántas contingencias son doble cobro no se conoce: la proporción del generador es un supuesto.
- **Criterios de la fuente (#22).** **H4:** la fuente alerta más de una carga del mismo vehículo en menos de 6 horas. Encuentra el 88% del fraccionamiento, pero marca unas 350 cargas por dataset (F1 0,07), casi todas normales, como los días con un segundo turno, y las contingencias legítimas que tienen otra carga cercana (H13); lo que separa los viajes largos sigue siendo el recorrido (0,35 por día → 0,77). Queda como nivel intermedio y no se adopta. **H12:** la fuente alerta un avance de menos de 5 km, también entre dos cargas del mismo día, y mira la excepción con la vigencia de hoy (F1 0,51 contra 0,81). Mirar la excepción del día de cada carga descarta las excepciones ya vencidas (8 falsas alarmas por dataset), y no alertar dos cargas del mismo día descarta unas 10 más, que son otras anomalías que tampoco avanzan el odómetro. En el generador la lectura repetida es siempre exacta y no hay avances de 1 a 4 km entre días, así que el umbral de 5 km no distinguiría nada en la regla con contexto. Para eso haría falta saber si en la fuente esas lecturas casi iguales son errores o vehículos que casi no se movieron (pregunta para el referente); hasta entonces el generador no las inyecta y se mantiene la regla actual. En las dos reglas, una carga sin hora se toma a las 00:00 de su día. Durante el análisis se probaron además, y se descartaron sin llevarlas al código, dos variantes: exigir en H4 que las cargas de menos de 6 horas superen juntas el tanque (queda igual que la suma por día) y agregar el umbral de 5 km o las cargas del mismo día a la regla con contexto de H12 (no mejora o empeora).
- El umbral fijo de saltos es inutilizable con uso realista: genera casi 1.000 falsas alarmas por dataset, porque un camión recorre 500 km en pocos días.
- En H1, el 0,5% de las cargas trae el dominio escrito de otra forma, la ganancia que muestra la fuente real al normalizar (`za123bc`, `ZA 123 BC`, `ZA-123-BC`): la vinculación exacta las confunde con dominios inválidos. El registro interno trae la fecha en `DD/MM/AAAA` y el reporte en `AAAA-MM-DD`, como en la fuente: cada formato se interpreta por separado.
- En H10, cada tarjeta pertenece a uno de seis contratos con tope mensual. Dos veces por semana se proyecta el consumo a fin de mes y, si no alcanza, se transfiere saldo desde el contrato al que más le sobra (unas 5 transferencias por mes). La fuente real no registra las transferencias; su frecuencia y su margen son supuestos del diseño.
- El registro interno (pedido y rendición de cada carga, como en la fuente) no comparte ningún identificador con el reporte del proveedor. La regla ingenua de H8 reproduce el cruce de un sistema operativo: por dominio y día, cada pedido toma la carga más cercana, sin tolerancias. La regla con contexto usa el dominio del vehículo dueño de la tarjeta (o la persona, si la tarjeta es personal), una ventana de 3 horas antes a media hora después y una asignación óptima (método húngaro) que prefiere pedidos no anulados y con los mismos litros.
- La comparación de totales mensuales (H9) solo detecta 68% de las facturas con irregularidades: un sobreprecio o una línea de más cambian menos del 1% del total, mientras que los desfases de corte y los ajustes documentados sí superan ese umbral.

**Escenario realista: priorización de la revisión.** Qué encuentra cada método según cuántas cargas se revisan, de unas 103 anomalías de comportamiento en las cargas por dataset (prevalencia 1,5%), en promedio de 5 semillas. Con 50 revisiones, el máximo posible es 49%.

| Método | Revisando 50 | Revisando 100 | Legítimos revisados en vano (de 100) |
|---|---|---|---|
| Reglas ingenuas | 12% | 23% | 61 |
| Isolation Forest | 11% | 17% | 25 |
| Reglas con contexto | 44% | 85% | 4 |
| Modelo supervisado (entrenado con otras semillas) | 48% | 80% | 7 |
| Combinado (reglas con contexto + modelo) | 48% | 88% | 3 |

Con 50 revisiones, el combinado no revisa ningún caso legítimo.

**Escenario realista: facturas a revisar.** La conciliación línea por línea marca unas 24 de 100 facturas por dataset y encuentra todas las irregularidades de facturación (31 por dataset), con un importe en juego de 3.100 a 5.100 por dataset.

- El modelo supervisado queda cerca de las reglas con contexto, y las supera revisando 50, sin que nadie las haya escrito: aprende de auditorías anteriores.
- Isolation Forest confunde lo raro con lo sospechoso, porque los viajes largos y los tanques no registrados también son raros.
- La combinación de reglas con contexto y modelo es la que mejor ordena la revisión. Cada caso de la cola trae su motivo.
- **Límite:** las reglas con contexto y el modelo se evalúan con datos del mismo generador que los define. Miden cuánto aporta cada fuente bajo los supuestos del escenario, no el desempeño esperable con datos reales.

## Cómo usarlo

```bash
pip install -r requirements.txt                 # Python 3.12

python generator_pipeline_maestro.py                       # escenario didáctico: datasets/synthetics_maestro/
python generator_pipeline_maestro.py --escenario realista  # escenario realista: datasets/synthetics_realista/
python -m deteccion                                        # evalúa las reglas contra el ground truth
python -m deteccion --escenario realista --ml              # además, hipótesis y priorización
python -m pytest                                # corre todos los tests
streamlit run streamlit_app/app.py              # abre la aplicación
```

- El generador acepta `--escenario`, `--n_flota`, `--seed` y `--output`.
- La aplicación genera los datos por su cuenta si no existen.
- `datasets/` está excluido de Git: se versionan el generador, las pruebas y la configuración, y los datos se recrean con la semilla.

Para mejorar el generador a partir de fuentes externas sin traer sus datos al proyecto, el [perfilador](perfiles/README.md) describe su estructura y calidad (tipos, formatos, faltantes, relaciones) de forma agregada y la compara con los datos sintéticos: `python -m perfilador perfilar archivo.xlsx`.

Cada corrida del generador escribe también un `diccionario.json` con el grano, las columnas y las relaciones de las tablas generadas. El detalle de cada archivo, las relaciones entre tablas (con diagrama) y los tipos de anomalía están en el [diccionario de datos](docs/DICCIONARIO_DATOS.md).

## Estructura

```text
generator_pipeline_maestro.py   generador oficial
deteccion/                      reglas, hipótesis, modelos de ML, priorización y evaluación
base_datos/                     base SQLite del escenario realista: migraciones, carga y vistas de control
perfilador/                     perfil agregado de fuentes y comparación con los datos sintéticos
perfiles/                       perfiles aprobados e informes de brechas
streamlit_app/                  aplicación (páginas y carga de datos)
tests/                          tests del generador, la detección y la app
docs/                           gobierno, arquitectura, diccionario, sprints y análisis
results/                        reportes de los encuentros
legacy/                         generadores, notebooks y etapa inicial anteriores
```

## Gobierno y colaboración

- [Reglas para agentes de IA](AGENTS.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Playbook de IA](docs/AI_PLAYBOOK.md)
- [Gobierno de datos y persistencia](docs/DATA_GOVERNANCE.md)
- [Arquitectura conceptual](docs/ARCHITECTURE.md)
- [Entorno de desarrollo](docs/DEVELOPMENT.md)
- [Diccionario de datos del pipeline maestro](docs/DICCIONARIO_DATOS.md)
- [Límite de metadatos reales](docs/REAL_DATA_BOUNDARY.md)
- [Base de datos](docs/BASE_DE_DATOS.md)
- [Modelo de ML: qué revisar primero](docs/MODELO_ML.md)
- [Evolución de los generadores](legacy/EVOLUCION.md)
- [Registro del Sprint 1](docs/sprints/sprint-1/README.md)
- [Estado actual](docs/ESTADO_ACTUAL.md) (con valores vivos en la página Documentación de la aplicación)
- [Bitácora](docs/BITACORA.md)

Las personas integrantes conservan la autoridad final sobre las decisiones y sobre `main`. Las IA colaboran mediante ramas y pull requests sujetos a revisión humana.

## Hoja de ruta

- [x] Fundación documental y reglas de trabajo.
- [x] Especificación del modelo de datos sintéticos.
- [x] Generador reproducible con verdad de referencia.
- [x] Análisis exploratorio inicial.
- [x] Líneas base de detección por reglas.
- [x] Primer experimento de ML (Isolation Forest) y evaluación.
- [x] Presentación interactiva de resultados (aplicación Streamlit).
- [ ] Pipeline de integración y limpieza sobre fuentes con defectos de formato.
- [x] Escenario realista con anomalías sutiles, cruces entre fuentes y casos legítimos.
- [x] Contraste de hipótesis: reglas ingenuas vs. reglas con contexto.
- [x] Modelo supervisado y priorización de la revisión.
- [x] Circuito solicitud → carga → factura: emparejamiento de solicitudes y conciliación de facturas.
- [ ] Métodos estadísticos robustos y comparación de más modelos.
- [ ] Validaciones de privacidad automatizadas antes de versionar datos.

## Limitaciones iniciales

Los datos sintéticos permiten experimentar sin exponer información sensible, pero sus patrones dependen de los supuestos del generador. Los resultados no podrán generalizarse automáticamente a flotas reales y deberán interpretarse dentro del escenario simulado.

Con las fuentes reales disponibles, el reporte de consumo, la facturación y los contratos son de un solo proveedor, mientras que las cargas se hacen en tres redes. La auditoría agregada ve el consumo total solo a través del registro interno: puede auditar lo que factura ese proveedor y completar los tramos de odómetro, pero no conciliar el consumo ni la facturación de las otras redes.
