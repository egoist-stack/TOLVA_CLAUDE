import os
import streamlit.components.v1 as components

_RUTA_FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anotador_fotos_frontend")

_componente = components.declare_component(
    "anotador_fotos",
    path=_RUTA_FRONTEND
)


def anotador_fotos(imagen_base64, ancho=600, alto=350, key=None):
    """
    Lienzo de anotacion sobre una foto (circulo, rectangulo, flecha, dibujo libre).
    Construido desde cero para evitar el bug de streamlit-drawable-canvas en
    Streamlit Cloud (la imagen se incrusta directo en el HTML, no se pide
    como recurso aparte) y para soportar dibujo con el dedo en celular.

    imagen_base64: string tipo "data:image/png;base64,...."
    Devuelve: la imagen anotada (mismo formato de string) cuando el usuario
    presiona "Guardar anotacion". Devuelve None mientras no se haya guardado.
    """
    return _componente(
        imagen_base64=imagen_base64,
        ancho=ancho,
        alto=alto,
        key=key,
        default=None
    )
