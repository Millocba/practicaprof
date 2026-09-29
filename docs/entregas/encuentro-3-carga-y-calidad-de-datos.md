# Encuentro 3 — Carga y calidad de los datos

*¿Los datos que tenemos alcanzan y son confiables?*

**Proyecto:** SIFAD — Sistema Inteligente de Flota y Auditoría de Datos.<br>
**Repositorio:** github.com/Millocba/practicaprof

## 1. Contexto y objetivo del encuentro

En el Encuentro 1 se definió la decisión que SIFAD busca apoyar y se estimó el nivel de preparación inicial de las fuentes. En el Encuentro 2 se confirmó ese nivel (Banda B) y se confrontó el mapa de hipótesis con el diccionario de datos.

Este encuentro se concentra en trabajar directamente sobre los registros: cargarlos de forma reproducible, medir su calidad, normalizar sus identificadores, integrarlos y comenzar a contrastar las hipótesis con controles ejecutables en vez de con criterios conceptuales.

A diferencia de lo documentado en encuentros anteriores, el equipo avanzó durante este período más de lo previsto en el plan original: en lugar de perfilar únicamente los cuatro archivos iniciales, se construyó un generador único y oficial que reemplaza los intentos previos, una base de datos con integridad verificable, un módulo de detección con reglas y modelos, y una aplicación para explorar los resultados. Este documento describe ese estado real, no una proyección.

## 2. Negocio y Datos

### 2.1 Criterios de calidad aplicados

La calidad de los datos se evalúa desde la perspectiva de la decisión que se busca apoyar, no solo con criterios técnicos. Una operación de combustible debe permitir reconocer el vehículo involucrado, el momento de la carga, el volumen registrado y su relación con las características conocidas de la unidad.

Se aplicaron los siguientes criterios: completitud, unicidad, validez, consistencia, capacidad de vinculación entre fuentes y trazabilidad del origen de cada dato y de las transformaciones aplicadas. Un registro que no se vincula con la flota no se considera automáticamente una anomalía: primero se comprueba si la falta de correspondencia responde a un problema de representación (espacios, formato, valores faltantes).

### 2.2 Evolución del mapa de hipótesis

El mapa inicial de tres hipótesis (H1, H2 y H3) se amplió considerablemente a partir de lo que reveló la calibración del generador contra el perfil agregado de fuentes reales. El backlog analítico actual contiene trece formulaciones, organizadas en pares ingenua/con contexto para poder medir cuánto aporta cada tratamiento:

| Hipótesis | Qué evalúa | Resultado (F1: ingenua → con contexto) |
| :--- | :--- | :--- |
| H1 | Normalizar el dominio antes de vincular con la flota; identificar tarjetas personales por la persona | 0,29 → 1,00 |
| H2b | Distinguir un odómetro nuevo o un error de tipeo de una adulteración real | 0,67 → 0,88 |
| H2c | Confirmar un salto de odómetro descartando errores de tipeo y cruzando con GPS | 0,00–0,41 → 1,00 |
| H3b | Distinguir un exceso volumétrico que aparece después (posible problema) de uno que existe desde el inicio (tanque no registrado) | 0,40 → 0,97 |
| H4 | Detectar fraccionamiento de cargas sumando por día y separando por recorrido | 0,00–0,35 → 0,77 |
| H5 | Detectar una carga sin recorrido que la justifique mediante el rendimiento km/L | 0,00 → 0,48 |
| H6 | Detectar cargas a vehículos de baja o fuera de servicio cruzando con su estado | 0,00 → 1,00 |
| H7 | Distinguir una tarjeta usada en otro lugar de un viaje real mediante el recorrido GPS | 0,62 → 0,90 |
| H8 | Conciliar el circuito solicitud → carga con tolerancias y asignación óptima, en vez de un cruce voraz por dominio y día | 0,11 → 0,98 |
| H9 | Conciliar la facturación línea por línea contra la carga, en vez de comparar solo totales mensuales | 0,35 → 1,00 |
| H10 | Detectar cargas con el saldo del contrato agotado mediante la proyección a fin de mes | 0,17 → 0,88 |
| H11 | Distinguir un dispositivo en depósito (por baja del móvil) de uno que debería estar activo | 0,57 → 1,00 |
| H12 | Distinguir una excepción de odómetro vigente de una lectura repetida sin justificación | 0,18 → 0,81 |

Una hipótesis se considera sostenida cuando la regla con contexto mejora el F1 de la regla ingenua en al menos 0,10. **Las trece hipótesis se sostienen**, promediadas sobre cinco semillas de 200 vehículos cada una. Esto no significa que estén "demostradas" en un sentido absoluto: se evalúan contra los datos que produce el propio generador que las define, por lo que miden cuánto aporta cada tratamiento bajo los supuestos del escenario, no el desempeño esperable frente a datos reales.

Ninguna hipótesis del mapa original quedó descartada. H1, H2 y H3 evolucionaron hacia formulaciones más específicas (H2b, H2c, H3b) a medida que se identificaron matices que una regla única no podía resolver, y se incorporaron nuevas hipótesis (H4 a H12) a partir de lo que el circuito solicitud → carga → factura y la telemetría permitieron observar.

## 3. Modelado / IA

### 3.1 Generador oficial y escenarios

Se consolidó un único generador (`generator_pipeline_maestro.py`), que reemplaza las versiones anteriores conservadas en `legacy/`. Produce cinco entidades relacionadas (flota, telemetría, consumo, solicitudes y facturación) junto con un `ground_truth.csv` que registra cada anomalía inyectada. La misma semilla reproduce siempre los mismos datos.

El generador ofrece dos escenarios:

- **Didáctico:** anomalías inconfundibles, pensado para explicar el método antes de complejizarlo.
- **Realista:** cada vehículo se simula día por día (consumo según su rendimiento, cargas cuando baja el tanque, posición GPS diaria). El circuito **solicitud → carga → factura** es coherente de punta a punta, e incluye anomalías sutiles, cruces entre fuentes y **casos legítimos que se parecen a anomalías**, para poder medir también las falsas alarmas.

La flota del escenario realista se calibró con el perfil agregado de fuentes externas (sin incorporar sus datos al proyecto): 52 % de los vehículos en servicio, 13 % fuera de servicio y 36 % en trámite de baja, con telemetría en el 80 % de los vehículos en servicio.

### 3.2 Perfilado sin incorporar datos reales

Se incorporó un módulo de perfilado (`perfilador/`) que permite comparar la estructura y la calidad del generador contra fuentes externas sin traer sus datos al repositorio: solo estructura y estadísticas agregadas (tipos, formatos, faltantes, cardinalidades), con revisión manual antes de aprobar cualquier perfil. Los perfiles aprobados y las auditorías agregadas quedan versionados en `perfiles/aprobados/`.

Esa comparación fue la que permitió detectar, por ejemplo, que el generador original sobrestimaba la proporción de vehículos en servicio y la cobertura pareja de telemetría, y ajustar el escenario realista en consecuencia.

### 3.3 Base de datos e integración

Se construyó una base de datos SQLite (`base_datos/`) para el escenario realista, con migraciones versionadas en SQL, maestros con vigencia temporal, carga idempotente e incremental, y vistas de control para verificar la integridad de la carga. Esto reemplaza la propuesta de "tabla analítica" que se había esbozado como objetivo del Encuentro 3 en la documentación anterior: hoy existe como base de datos versionada, no como notebook.

### 3.4 Detección

El paquete `deteccion/` implementa reglas ingenuas, reglas con contexto, un Isolation Forest y un modelo supervisado, evaluados siempre contra el ground truth del generador. En el escenario didáctico, la línea base de reglas alcanza F1 1,00 (funciona como techo de referencia, porque se diseñó conociendo cómo se inyectan las anomalías) y el Isolation Forest alcanza F1 0,77.

Sobre el escenario realista se agregó además la priorización de revisión: combinando reglas con contexto y el modelo supervisado, revisando 100 casos se encuentra el 100 % de las anomalías de comportamiento en las cargas (frente al 75 % de las reglas ingenuas solas y al 37 % del Isolation Forest).

## 4. Producto y Gestión

### 4.1 Ficha DRL

En el Encuentro 2 se confirmó Banda B: las fuentes eran accesibles y con estructura interpretable, pero todavía requerían perfilado, normalización, conciliación e integración antes de sostener un análisis confiable.

Con el trabajo de este encuentro (base de datos con integridad verificable, perfilado reproducible, conciliación del circuito solicitud-carga-factura), el equipo cuenta con evidencia para evaluar si corresponde mantener la Banda B o avanzar hacia Banda A. Esa decisión queda pendiente de confirmación conjunta, porque todavía restan los puntos señalados en la sección 5.

### 4.2 Backlog de hipótesis y artefactos disponibles

El backlog analítico pasó de tres hipótesis en formulación conceptual a trece hipótesis con resultado medido y reproducible (sección 2.2). Los artefactos que sostienen esos resultados son:

| Artefacto | Contenido | Ubicación |
| :--- | :--- | :--- |
| Generador oficial | Escenarios didáctico y realista, ground truth | `generator_pipeline_maestro.py` |
| Base de datos | Migraciones, carga, vistas de control | `base_datos/` |
| Perfilador | Comparación agregada contra fuentes externas | `perfilador/`, `perfiles/` |
| Detección | Reglas, modelos, evaluación y priorización | `deteccion/` |
| Aplicación | Exploración, análisis por hipótesis y documentación viva | `streamlit_app/` |
| Pruebas automatizadas | Generador, reglas, modelo, base de datos y páginas | `tests/` (ejecutan en cada push) |

### 4.3 Ciclo de CRISP-DM

A diferencia del Encuentro 2, donde el ciclo se detenía en la preparación de los datos, en este encuentro se avanzó también sobre las etapas de modelado y evaluación: hay reglas y modelos implementados, y se evaluaron contra una verdad de referencia. La etapa de implementación permanece fuera de alcance: los resultados siguen en un entorno académico.

## 5. Pendiente para los próximos encuentros

- Definir un pipeline de integración y limpieza sobre fuentes con defectos de formato reales (más allá de la comparación agregada que ya hace el perfilador).
- Incorporar métodos estadísticos robustos adicionales y ampliar la comparación de modelos, más allá de reglas, Isolation Forest y el modelo supervisado actual.
- Automatizar las validaciones de privacidad de `docs/DATA_GOVERNANCE.md` antes de versionar datos nuevos, en vez de aplicarlas manualmente.
- Confirmar en equipo si la evidencia reunida en este encuentro alcanza para actualizar la Ficha DRL de Banda B a Banda A.

## 6. Alcance y limitaciones

Los resultados de este encuentro se obtuvieron evaluando las reglas con contexto y los modelos contra datos generados por el mismo generador que define sus reglas de anomalía. Esto mide cuánto aporta cada fuente y cada tratamiento bajo los supuestos del escenario diseñado, pero no equivale al desempeño esperable frente a una flota real. Cualquier conclusión debe indicar qué parte proviene de la evidencia y qué parte responde al diseño de la simulación.
