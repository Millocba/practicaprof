"""Tarjetas explicativas con marco rosa, escritas para que las entienda un chico de 10 años.

Cada página de la app muestra arriba una tarjeta que cuenta, en palabras simples:
- qué se hace en esa página,
- para qué sirve,
- y en qué paso del recorrido de la información estamos (una fila de "estaciones"
  con la actual pintada de rosa).

La página de inicio además muestra el recorrido completo, de punta a punta.

Los textos están todos acá, en TARJETAS, para poder corregirlos sin tocar las páginas.
Cada página solo llama a `tarjeta("<clave>")`.
"""
import streamlit as st

ROSA = "#e75480"
ROSA_CLARO = "#fff0f6"

# Las "estaciones" del recorrido, en el orden en que viaja la información.
# (clave de la página, emoji, nombre corto)
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
    "inicio": {
        "titulo": "¿De qué se trata todo esto?",
        "que": "Imaginá una flota de autos, camionetas y camiones <b>de juguete</b>: no existen, "
               "los inventa la computadora. Cada vehículo carga combustible, anda por la calle y alguien "
               "paga la factura. Nosotros escondemos <b>trampas a propósito</b> (como alguien que carga "
               "más nafta de la que entra en el tanque) y anotamos en un <b>sobre secreto</b> dónde las "
               "escondimos.",
        "para": "Para practicar ser <b>detectives</b>: probamos distintas formas de encontrar las trampas "
                "y después abrimos el sobre secreto para ver cuántas encontramos y cuántas veces nos "
                "equivocamos. Como todo es inventado, nadie real sale perjudicado.",
        "flujo": "Esta es la <b>portada</b>: desde acá ves un resumen de todo. Seguí las estaciones de "
                 "abajo, de izquierda a derecha, para hacer el recorrido completo.",
    },
    "generador": {
        "titulo": "Estación 1: la fábrica de datos",
        "que": "Acá la computadora <b>inventa</b> la flota: los vehículos, sus cargas de combustible, "
               "los viajes del GPS, los pedidos de nafta y las facturas. También esconde las trampas y "
               "llena el <b>sobre secreto</b> (se llama <i>ground truth</i>, \"la verdad\").",
        "para": "Sin datos no hay nada que investigar. Usamos una <b>semilla</b>, que es como el número "
                "de una receta: con la misma semilla sale siempre la misma flota, así cualquiera puede "
                "repetir el experimento y obtener lo mismo.",
        "flujo": "Es el <b>primer paso</b>: todo lo que ves en las otras páginas sale de acá. Lo que se "
                 "fabrica se guarda en archivos que usan las estaciones siguientes.",
    },
    "datasets": {
        "titulo": "Estación 2: mirar lo que fabricamos",
        "que": "Acá ves las <b>tablas</b> que inventó la fábrica, como si fueran planillas: una fila por "
               "vehículo, por carga o por factura. Podés filtrar, ordenar y ver gráficos.",
        "para": "Antes de buscar trampas hay que <b>conocer los datos</b>: cuántos vehículos hay, cuánto "
                "cargan, si falta algún dato. Es como mirar el mapa antes de salir de excursión.",
        "flujo": "Viene <b>después de la fábrica</b>. Solo miramos: acá no se cambia nada.",
    },
    "diccionario": {
        "titulo": "Estación 3: el diccionario",
        "que": "Acá dice <b>qué significa cada columna</b> de cada tabla (por ejemplo, \"dominio\" es la "
               "patente) y cómo se conectan las tablas entre sí: qué carga es de qué vehículo, qué "
               "factura paga qué cargas.",
        "para": "Para no confundirnos. Si no sabés qué quiere decir una palabra, no podés entender la "
                "historia. También muestra la lista de trampas que puede esconder la fábrica.",
        "flujo": "Sirve para <b>entender</b> lo que viste en la estación 2 antes de ponerte a investigar.",
    },
    "perfil": {
        "titulo": "Estación 4: comparar con la vida real (sin copiar)",
        "que": "Acá se le puede dar a la computadora un archivo <b>de verdad</b> y ella anota solo "
               "<b>cómo es</b>, nunca lo que dice: por ejemplo \"las patentes tienen dos letras, tres "
               "números y dos letras\" en vez de copiar las patentes. Esa anotación se llama "
               "<b>perfil</b>.",
        "para": "Para que nuestros datos inventados se <b>parezcan más a los reales</b>, sin traer ningún "
                "dato real al proyecto. Después se compara el perfil con lo inventado y sale una lista "
                "de diferencias (<b>brechas</b>) para mejorar la fábrica.",
        "flujo": "Los pasos son tres: <b>perfilar</b> (anotar cómo es), <b>aprobar</b> (una persona "
                 "revisa que no se escape nada privado y firma) y <b>comparar</b> (ver qué le falta a "
                 "la fábrica). Lo que se aprende vuelve a la estación 1.",
    },
    "analisis": {
        "titulo": "Estación 5: buscar pistas",
        "que": "Acá se miran los datos pensando en cada <b>hipótesis</b>, que es una idea que queremos "
               "comprobar, como \"si el odómetro retrocede, alguien lo tocó\". Hay gráficos que muestran "
               "dónde aparecen cosas raras.",
        "para": "Para <b>ver con los ojos</b> las pistas antes de armar las reglas que las buscan "
                "solas. Es como un detective mirando huellas con la lupa.",
        "flujo": "Usa los datos de la fábrica. Lo que se descubre acá ayuda a armar a los detectives "
                 "de la estación 6.",
    },
    "deteccion": {
        "titulo": "Estación 6: los detectives",
        "que": "Acá trabajan las <b>reglas</b>: son instrucciones fijas, como \"si cargó más litros de "
               "los que entran en el tanque, es sospechoso\". Cada regla marca cargas sospechosas y "
               "después abrimos el <b>sobre secreto</b> para ver cuántas acertó.",
        "para": "Para ponerle <b>nota</b> a cada detective. Se miran dos cosas: cuántas trampas "
                "encontró (si se le escaparon, es malo) y cuántas veces acusó a alguien inocente "
                "(una <b>falsa alarma</b>, también es malo).",
        "flujo": "Las reglas son la <b>línea de base</b>: la forma más simple de detectar. Las "
                 "estaciones 7 y 8 intentan hacerlo mejor.",
    },
    "hipotesis": {
        "titulo": "Estación 7: ¿ayuda pensar un poco más?",
        "que": "Acá se enfrentan dos detectives por cada idea: uno <b>apurado</b> (regla simple) y uno "
               "<b>que mira el contexto</b> (por ejemplo, que se fija si el camión suele andar mucho "
               "antes de acusarlo). Se comparan sus notas.",
        "para": "Para comprobar si mirar el contexto <b>evita acusar inocentes</b>: hay casos que "
                "parecen trampas pero no lo son, como un tanque nuevo que nadie anotó.",
        "flujo": "Toma las reglas de la estación 6 y las mejora. Si el detective con contexto sube "
                 "bastante su nota, decimos que la hipótesis <b>se sostiene</b>.",
    },
    "modelo": {
        "titulo": "Estación 8: la computadora aprende sola",
        "que": "Acá, en vez de escribir reglas, dejamos que la <b>computadora aprenda</b>. Un modelo "
               "busca lo que es <b>raro</b> sin ayuda; otro aprende mirando casos que ya fueron "
               "revisados antes, como un alumno que estudia con ejercicios resueltos.",
        "para": "Para saber <b>qué revisar primero</b> cuando no hay tiempo de revisar todo: la "
                "computadora arma una fila de cargas ordenadas de más a menos sospechosa, y cada una "
                "dice por qué está ahí.",
        "flujo": "Se compara con los detectives de las estaciones 6 y 7. Ojo: <b>raro no siempre es "
                 "trampa</b> (un viaje largo es raro y es legítimo).",
    },
    "documentacion": {
        "titulo": "Estación 9: el cuaderno del proyecto",
        "que": "Acá está todo <b>anotado</b>: qué se hizo, qué se decidió, qué salió bien y qué no, y "
               "los números actualizados de los resultados.",
        "para": "Para que cualquiera pueda <b>entender y repetir</b> el trabajo, y para no olvidarnos "
                "de por qué hicimos cada cosa. Es como la carpeta de la escuela, pero del proyecto.",
        "flujo": "Es la <b>última estación</b>: junta lo que pasó en todas las demás.",
    },
}


def _recorrido_html(actual):
    """Fila de estaciones del recorrido; la estación `actual` se pinta de rosa."""
    pasos = []
    for i, (clave, emoji, nombre) in enumerate(RECORRIDO, start=1):
        if clave == actual:
            estilo = f"background:{ROSA};color:white;font-weight:bold;"
        else:
            estilo = f"background:white;color:{ROSA};border:1px solid {ROSA};"
        pasos.append(f'<span style="{estilo}border-radius:999px;padding:2px 10px;margin:2px;'
                     f'display:inline-block;font-size:0.85em;">{i}. {emoji} {nombre}</span>')
    return '<span style="color:#e75480;margin:0 2px;">➜</span>'.join(pasos)


def tarjeta(clave):
    """Dibuja la tarjeta de marco rosa de una página. `clave` es una de las de TARJETAS."""
    datos = TARJETAS[clave]
    st.markdown(f"""
<div style="border:3px solid {ROSA};border-radius:16px;background:{ROSA_CLARO};padding:16px 20px;
            margin:8px 0 20px 0;color:#31333f;line-height:1.5;">
  <div style="font-size:1.2em;font-weight:bold;color:{ROSA};margin-bottom:8px;">🧸 {datos['titulo']}</div>
  <p style="margin:6px 0;"><b>🛠️ ¿Qué se hace acá?</b> {datos['que']}</p>
  <p style="margin:6px 0;"><b>🎯 ¿Para qué sirve?</b> {datos['para']}</p>
  <p style="margin:6px 0;"><b>🗺️ ¿Dónde estamos en el camino?</b> {datos['flujo']}</p>
  <div style="margin-top:10px;">{_recorrido_html(clave)}</div>
</div>
""", unsafe_allow_html=True)


def recorrido_completo():
    """Tarjeta de la portada con el viaje completo de la información, de punta a punta."""
    pasos = "".join(
        f'<li style="margin:4px 0;"><b>{emoji} {nombre}</b>: {TARJETAS[clave]["titulo"].split(": ", 1)[-1]}</li>'
        for clave, emoji, nombre in RECORRIDO)
    st.markdown(f"""
<div style="border:3px solid {ROSA};border-radius:16px;background:{ROSA_CLARO};padding:16px 20px;
            margin:8px 0 20px 0;color:#31333f;line-height:1.5;">
  <div style="font-size:1.2em;font-weight:bold;color:{ROSA};margin-bottom:8px;">🚂 El viaje de la información</div>
  <p style="margin:6px 0;">La información viaja como un tren que para en estaciones. En cada una le pasa algo:</p>
  <ol style="margin:6px 0 6px 18px;">{pasos}</ol>
  <p style="margin:6px 0;">🔁 Lo que aprendemos en la estación 4, comparando con la vida real, vuelve a la
     estación 1 para que la fábrica invente datos cada vez más parecidos a los de verdad.</p>
  <p style="margin:6px 0;">🔒 <b>Regla de oro:</b> los datos de personas o vehículos reales nunca entran al
     proyecto. Solo se anota <i>cómo son</i>, nunca <i>qué dicen</i>.</p>
</div>
""", unsafe_allow_html=True)
