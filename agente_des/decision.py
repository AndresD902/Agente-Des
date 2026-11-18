"""La regla de decisión actúa sobre medias calculadas, sin redondearlas."""

from pydantic import TypeAdapter

from .modelos import CAPACIDADES, Capacidad, NoNegativo

validar_no_negativo = TypeAdapter(NoNegativo)


def recomendar(promedios: dict[int, float], meta: float) -> Capacidad | None:
    meta = validar_no_negativo.validate_python(meta, strict=True)
    if set(promedios) != set(CAPACIDADES) or any(type(c) is not int for c in promedios):
        raise ValueError("Se requieren los promedios de 1, 2 y 3 puestos.")
    medias = {capacidad: validar_no_negativo.validate_python(promedio, strict=True)
              for capacidad, promedio in promedios.items()}
    return next((capacidad for capacidad in CAPACIDADES if medias[capacidad] <= meta), None)
