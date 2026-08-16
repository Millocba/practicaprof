# Playbook de colaboración con IA

Las personas integrantes dirigen el producto y el análisis. Los agentes de IA funcionan como equipo técnico asistente: pueden proponer, diseñar, implementar y revisar, pero no poseen autoridad final.

## Secuencia de trabajo

1. Explorar el contexto y el estado de Git.
2. Aclarar objetivo, restricciones y criterios de aceptación.
3. Comparar alternativas y explicitar supuestos.
4. Presentar un diseño para aprobación humana.
5. Escribir un plan verificable.
6. Implementar en una rama acotada.
7. Ejecutar pruebas y revisar el diff.
8. Abrir un PR con evidencia y limitaciones.

## Agentes y subagentes

- Delegar solo subtareas independientes y acotadas.
- Definir entradas, salidas y criterios de aceptación.
- Evitar ediciones simultáneas sobre los mismos archivos.
- No aceptar informes de éxito sin revisar diff y verificaciones.
- La persona responsable y su agente orquestador integran los resultados.

## Orden de revisión

1. Riesgo de privacidad o referencias reales.
2. Corrección conceptual de los datos.
3. Efectos sobre persistencia.
4. Reproducibilidad y pruebas.
5. Interpretación estadística.
6. Mantenibilidad y presentación.

## Pausas obligatorias

El agente debe detenerse antes de ampliar el alcance, usar datos posiblemente reales, instalar dependencias, conectar servicios, cambiar configuración compartida, alterar una persistencia no demostrada como local y efímera, publicar, desplegar o fusionar.

## Capacidades recomendadas

- Integración con GitHub para issues, ramas, PRs y revisiones.
- Flujos tipo Superpowers para ideación, planificación, pruebas y verificación.
- Servidores MCP o conectores cuando aporten una capacidad aprobada.
- Herramientas para notebooks, Python, SQL, visualización y pruebas de datos.

Estas capacidades pueden proveerse mediante plugins, CLI o integraciones equivalentes. No se exige una marca concreta. La instalación requiere aprobación humana y debe seguir la documentación oficial.

## Entrega

Cada entrega distingue hechos observados, inferencias, decisiones, alternativas descartadas, verificaciones, riesgos y trabajo pendiente. Nunca presenta una hipótesis como conclusión ni una ejecución parcial como validación completa.
