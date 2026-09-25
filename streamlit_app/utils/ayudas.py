"""Ayudas contextuales de la aplicación.

El parámetro `help=` de Streamlit solo funciona sobre widgets: botones, deslizadores,
selectores y métricas. Los títulos de sección se escriben con `st.markdown`, así que no
tienen dónde colgar una explicación. `seccion` los dibuja con un botón "?" al lado que
despliega el texto, para que quien entra por primera vez entienda qué está mirando y cómo
leerlo sin ensuciar la página.
"""
import streamlit as st

ICONO_AYUDA = "?"

# Proporción de la fila: el título toma el ancho y la ayuda queda a la derecha.
_ANCHO_TITULO = 20
_ANCHO_AYUDA = 1


def seccion(titulo, ayuda=None, nivel=2):
    """Escribe un título de sección y, si se pasa `ayuda`, un "?" que la despliega.

    Sin `ayuda` se comporta exactamente como el `st.markdown` de siempre. El título se
    sigue escribiendo con `st.markdown`, así que las páginas que dependen de inspeccionar
    los markdown siguen funcionando.
    """
    encabezado = "#" * nivel + " " + titulo
    if not ayuda:
        st.markdown(encabezado)
        return

    columna_titulo, columna_ayuda = st.columns([_ANCHO_TITULO, _ANCHO_AYUDA],
                                               vertical_alignment="center")
    with columna_titulo:
        st.markdown(encabezado)
    with columna_ayuda:
        with st.popover(ICONO_AYUDA, help="¿Qué estoy mirando?"):
            st.markdown(ayuda)


def subtitulo(titulo, ayuda=None, nivel=3):
    """Igual que `seccion`, para los títulos internos de una sección."""
    seccion(titulo, ayuda, nivel=nivel)
