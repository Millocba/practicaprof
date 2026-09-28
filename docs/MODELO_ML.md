# Modelo de ML: qué revisar primero

El componente de ML no es un modelo único: es un **sistema de priorización** que combina las reglas con dos modelos para decidir en qué orden revisar las cargas. Está en `deteccion/priorizacion.py` y `deteccion/modelo.py`, y se ve en la página **Modelo de ML** de la aplicación.

## El problema

Nadie revisa todas las cargas. Con unas 3.200 cargas en nueve meses, un auditor puede mirar 50 o 100. La pregunta útil no es "¿esta carga es anómala?" sino **"¿en qué orden revisarlas para encontrar la mayor cantidad de irregularidades con el tiempo disponible?"**. Por eso los métodos se comparan con una **curva de esfuerzo**: cuántas anomalías encuentra cada uno revisando la misma cantidad de casos.

## Los métodos

| Método | Qué hace |
|---|---|
| Reglas ingenuas | Marcan o no marcan (litros > tanque, cualquier retroceso, suma del día > tanque, cruce voraz con el registro…); se revisa primero lo marcado |
| Reglas con contexto | Las reglas de las hipótesis, con el historial del vehículo, el estado de la flota, el GPS y el registro interno |
| Isolation Forest | No supervisado: mide qué tan rara es cada carga frente a las demás, sin saber cuáles son anomalías |
| Modelo supervisado | Random Forest que aprende de casos ya etiquetados qué combinación de señales tiene una carga irregular |
| **Combinado** | Primero lo que marcan las reglas con contexto, ordenado por la probabilidad del modelo; después el resto, por esa misma probabilidad |

Cada carga de la cola viene con sus **motivos** ("cargó 140% de lo autorizado", "sin pedido en el registro interno"…), para que el auditor sepa qué buscar.

## Resultados

Escenario realista, semilla 42: 3.191 cargas, 79 anomalías de comportamiento.

| Método | Revisando 50: encontradas | Precisión | Casos legítimos revisados | Revisando 100: encontradas |
|---|---|---|---|---|
| Reglas ingenuas | 15 (19%) | 30% | 28 | 28 (35%) |
| Isolation Forest | 17 (22%) | 34% | 12 | 30 (38%) |
| Reglas con contexto | 46 (58%) | 92% | 1 | 73 (92%) |
| Modelo supervisado | 47 (59%) | 94% | 1 | 63 (80%) |
| **Combinado** | **49 (62%)** | **98%** | **0** | **73 (92%)** |

- El **Isolation Forest** rinde casi como las reglas ingenuas: las anomalías del escenario realista son sutiles, y los casos legítimos que se les parecen (tanques auxiliares, viajes largos) también son raros. Ser raro no alcanza para ser sospechoso.
- El **combinado** encuentra lo mismo que las reglas con contexto o algo más, con menos casos legítimos revisados: las reglas aportan lo que sabemos explicar y el modelo, el orden.

## Por qué estos modelos

**Isolation Forest.** Es lo que se puede usar desde el primer día con datos reales, que no traen etiquetas. Es rápido, no necesita escalar las variables y funciona con pocas.

**Random Forest.**

- Trabaja bien con datos tabulares chicos y variables mezcladas (proporciones, km, indicadores de sí o no).
- Maneja el desbalance: solo el 2,6% de las cargas son anomalías (`class_weight="balanced_subsample"`).
- Da una probabilidad para ordenar y la importancia de cada variable para explicar.
- No necesita un ajuste fino.

Descartados:

- **Redes neuronales:** con este volumen y la necesidad de explicar cada caso no se justifican.
- **Gradient boosting:** podría rendir un poco más, pero es menos estable sin ajuste.

Variables que más pesan en el modelo supervisado:

| Variable | Importancia |
|---|---|
| Cambio de odómetro desde la carga anterior | 16% |
| Litros cargados / litros autorizados | 15% |
| Rendimiento km/L frente al habitual del vehículo | 14% |
| Tanques cargados en el día | 12% |

Tienen sentido para un auditor, y eso permite confiar en el orden que propone.

## Cómo se entrena

- **Datos de entrenamiento:** tres datasets realistas generados con **otras semillas** (1001, 1002 y 1003), como si fueran auditorías anteriores ya resueltas. Son 8.349 cargas, 213 anómalas.
- **Variables:** 14 por carga, calculadas de las tablas y nunca de la verdad de referencia:
  - litros frente al tanque y a lo habitual del vehículo;
  - km y retrocesos del odómetro;
  - rendimiento relativo;
  - cargas y tanques del día;
  - distancia de la estación a la zona habitual y al recorrido GPS;
  - vehículo inactivo;
  - sin pedido en el registro interno;
  - litros frente a lo autorizado.
- **Etiqueta:** la carga tiene una anomalía de comportamiento. Las de calidad de datos y facturación quedan fuera: las cubren las reglas.
- **Modelo:** Random Forest con 300 árboles; tarda unos 13 segundos. Se aplica al dataset actual, cuyas etiquetas **nunca ve**.
- **Isolation Forest:** se ajusta sobre el mismo dataset que puntúa, porque no usa etiquetas.
- **Frecuencia:** hoy se entrena una vez por sesión de la aplicación y queda en caché.

## Cómo se implementaría con datos reales

La dificultad principal es que **las fuentes reales no traen etiquetas**: nadie registró qué cargas eran irregulares. Por eso, en etapas:

1. **Sin etiquetas.**
   - Las reglas con contexto y el Isolation Forest arman la cola diaria.
   - El auditor **registra el resultado de cada revisión**: confirmada, legítima o dato erróneo. Así se generan las etiquetas que faltan.
2. **Con las primeras etiquetas** (algunos cientos de casos revisados).
   - Se entrena el Random Forest con casos reales y se valida con los meses más recientes, que el modelo no vio.
   - Se compara con la línea base (las reglas con contexto) y se adopta solo si encuentra más con el mismo esfuerzo.
3. **En operación.**
   - **Cada día:** después de la carga diaria en la base (`python -m base_datos cargar --hasta <día>`), se calculan las variables, se puntúan las cargas nuevas y se publica la cola con sus motivos.
   - **Cada mes**, o cuando se acumulen suficientes revisiones: se reentrena, se guarda cada versión del modelo con sus datos, parámetros y métricas, y se vuelve a comparar con la línea base.
   - **Monitoreo:**
     - la proporción de la cola que resulta confirmada;
     - los cambios en el perfil de las cargas (vehículos nuevos, precios);
     - que la cola no se concentre sin justificación en ciertas dependencias o tipos de vehículo.

Antes de la etapa 1, la **auditoría agregada** corre las reglas y los modelos sobre las fuentes reales, junto a los datos, y devuelve solo agregados: cuánto marca cada regla y si las variables reales se parecen a las sintéticas. Ver [perfiles/README.md](../perfiles/README.md).

## Limitaciones

- El modelo aprende las anomalías tal como las inyecta el generador. Con datos reales los patrones serán otros: estos resultados son un **techo de referencia**, no una promesa de desempeño.
- Frente a las reglas con contexto la mejora es chica (49 contra 46 revisando 50). Su valor está en ordenar dentro de lo marcado y en rescatar casos que las reglas no ven.
- Hay pocas anomalías para aprender: unas 80 por dataset. Con datos reales, la etapa 2 depende de cuántas revisiones se registren.
