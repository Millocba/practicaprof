"""Tarjetas explicativas con marco rosa, en palabras simples, para quien llega sin saber nada.

Cada página muestra debajo de su título una tarjeta breve con tres respuestas: qué se hace
en esa página, para qué sirve y en qué parte del camino de la información estamos (una fila
de "estaciones" con la actual pintada de rosa). La portada muestra el camino completo.

Las tarjetas resumen la página entera; los "?" de cada sección explican el detalle. Los
textos están todos acá, en TARJETAS, para corregirlos sin tocar las páginas: cada página
solo llama a `explicar("<clave>")`.

Idea y primera versión de la rama de Meli (issue #18).
"""
import streamlit as st

ROSA = "#e75480"
ROSA_CLARO = "#fff0f6"
TEXTO = "#31333f"   # fijo: el fondo rosa claro no cambia con el tema oscuro

# Las "estaciones" del camino, en el orden de las páginas: (clave, emoji, nombre corto)
RECORRIDO = [
    ("generador", "⚙️", "Inventar"),
    ("datasets", "📋", "Mirar"),
    ("diccionario", "📖", "Entender"),
    ("perfil", "🔬", "Comparar con lo real"),
    ("analisis", "🔍", "Buscar pistas"),
    ("deteccion", "🎯", "Detectives"),
    ("hipotesis", "🧪", "Probar ideas"),
    ("modelo", "🤖", "La compu aprende"),
    ("documentacion", "📚", "Cuaderno"),
]

TARJETAS = {
    "generador": {
        "titulo": "1. La fábrica de datos",
        "que": "Se inventan los vehículos, sus cargas de combustible, sus pedidos y sus facturas, con algunas "
               "<b>trampas</b> escondidas y algunos casos que parecen trampas pero no lo son.",
        "para": "Sin datos no hay nada que investigar. Dónde quedó cada trampa se anota aparte, en una "
                "<b>hoja de respuestas</b> que las reglas nunca miran.",
        "flujo": "Es el primer paso: todas las demás páginas usan lo que se fabrica acá.",
    },
    "datasets": {
        "titulo": "2. Mirar los datos",
        "que": "Se ven las tablas inventadas, como planillas, con filtros y gráficos.",
        "para": "Para conocer los datos antes de investigar, como mirar el mapa antes de salir.",
        "flujo": "Viene después de la fábrica. Acá solo se mira, no se cambia nada.",
    },
    "diccionario": {
        "titulo": "3. El diccionario",
        "que": "Explica qué significa cada columna y cómo se conectan las tablas entre sí.",
        "para": "Para entender lo que estamos mirando y no confundir una cosa con otra.",
        "flujo": "Ayuda a leer lo que viste en la página 2.",
    },
    "perfil": {
        "titulo": "4. Comparar con la vida real",
        "que": "Se describe cómo es un archivo real <b>sin copiar lo que dice</b>: por ejemplo, "
               "\"las patentes tienen 2 letras, 3 números y 2 letras\".",
        "para": "Para que los datos inventados se parezcan más a los reales, sin traer datos de nadie.",
        "flujo": "Una persona revisa la descripción antes de guardarla. Lo que se aprende vuelve a la fábrica.",
    },
    "analisis": {
        "titulo": "5. Buscar pistas",
        "que": "Se aplican las reglas a los datos y se ve qué cargas marca cada una, idea por idea "
               "(cada idea es una <b>hipótesis</b>).",
        "para": "Para ver lo mismo que vería un auditor: acá todavía no se mira la hoja de respuestas.",
        "flujo": "Las páginas 6 y 7 revisan cuántas de esas pistas eran trampas de verdad.",
    },
    "deteccion": {
        "titulo": "6. Los detectives",
        "que": "Lo que marcan las reglas se compara con la hoja de respuestas.",
        "para": "Para ponerle nota a cada regla: cuántas trampas encontró y cuántas veces acusó a un inocente.",
        "flujo": "Es la nota de las reglas. La página 7 compara reglas simples con reglas que piensan más.",
    },
    "hipotesis": {
        "titulo": "7. ¿Ayuda pensar un poco más?",
        "que": "Se compara una regla apurada con otra que mira el <b>contexto</b>: la historia del vehículo, "
               "su estado, el GPS o el pedido de la carga.",
        "para": "Para ver si mirar el contexto evita acusar a inocentes que solo parecen tramposos.",
        "flujo": "Dice qué ideas se confirman con los datos.",
    },
    "modelo": {
        "titulo": "8. La computadora aprende",
        "que": "En vez de escribir reglas, la computadora <b>aprende</b> de casos ya revisados a reconocer "
               "lo sospechoso.",
        "para": "Para decidir qué revisar primero cuando no hay tiempo de revisar todo.",
        "flujo": "Se compara con las reglas de las páginas 6 y 7. Ojo: raro no siempre es trampa.",
    },
    "documentacion": {
        "titulo": "9. El cuaderno del proyecto",
        "que": "Está anotado qué se hizo, qué se decidió y cómo salieron los resultados.",
        "para": "Para que cualquiera pueda entender y repetir el trabajo.",
        "flujo": "Es la última página: resume todas las demás.",
    },
}


def _recorrido_html(actual):
    """Fila de estaciones del camino; la estación `actual` se pinta de rosa."""
    pasos = []
    for i, (clave, emoji, nombre) in enumerate(RECORRIDO, start=1):
        if clave == actual:
            estilo = f"background:{ROSA};color:white;font-weight:bold;"
        else:
            estilo = f"background:white;color:{ROSA};border:1px solid {ROSA};"
        pasos.append(f'<span style="{estilo}border-radius:999px;padding:2px 10px;margin:2px;'
                     f'display:inline-block;font-size:0.85em;">{i}. {emoji} {nombre}</span>')
    return f'<span style="color:{ROSA};margin:0 2px;">➜</span>'.join(pasos)


def _caja(titulo, cuerpo):
    """Caja de marco rosa con un título y un cuerpo en HTML."""
    st.markdown(f"""
<div style="border:3px solid {ROSA};border-radius:16px;background:{ROSA_CLARO};padding:14px 20px;
            margin:8px 0 20px 0;color:{TEXTO};line-height:1.5;">
  <div style="font-size:1.15em;font-weight:bold;color:{ROSA};margin-bottom:6px;">🧸 {titulo}</div>
  {cuerpo}
</div>
""", unsafe_allow_html=True)


def explicar(clave):
    """Dibuja la tarjeta de una página. `clave` es una de las de TARJETAS."""
    datos = TARJETAS[clave]
    _caja(datos["titulo"], f"""
  <p style="margin:4px 0;"><b>🛠️ Qué se hace:</b> {datos['que']}</p>
  <p style="margin:4px 0;"><b>🎯 Para qué:</b> {datos['para']}</p>
  <p style="margin:4px 0;"><b>🗺️ En el camino:</b> {datos['flujo']}</p>
  <div style="margin-top:8px;">{_recorrido_html(clave)}</div>""")


def camino_completo():
    """Tarjeta de la portada con el camino completo de la información."""
    _caja("El camino de la información", f"""
  <p style="margin:4px 0;">La computadora inventa una flota de vehículos y esconde algunas <b>trampas</b>, como
     cargar más combustible del que entra en el tanque. Después buscamos las trampas como detectives y revisamos
     cuántas encontramos de verdad. Los datos pasan por estas estaciones, en orden:</p>
  <div style="margin:8px 0;">{_recorrido_html(None)}</div>
  <p style="margin:4px 0;">🔁 Lo que se aprende en la estación 4 vuelve a la 1, para inventar datos más realistas.</p>
  <p style="margin:4px 0;">🔒 <b>Regla de oro:</b> los datos reales nunca entran al proyecto. Solo se anota
     <i>cómo son</i>, nunca <i>qué dicen</i>.</p>""")
