"""La elegibilidad se verifica en Python antes y después de la pausa."""

from typing import Annotated

from pydantic import Field, StringConstraints

from .configuracion import Contexto
from .decision import recomendar
from .estado import Estado, escenario_actual
from .modelos import Contrato
from .resultado import Resultado

REGISTRAR = "registrar_decision"


class Propuesta(Contrato):
    capacidad: Annotated[int, Field(ge=1, le=3)]
    nota: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]


def registro_visible(estado: Estado, contexto: Contexto) -> bool:
    return (contexto.rol == "operador" and estado.get("resultados") is not None
            and estado.get("meta_aplicada") == contexto.meta
            and estado.get("recomendacion") is not None and estado.get("decision") is None)


def validar_registro(estado: Estado, contexto: Contexto, propuesta: Propuesta) -> dict:
    if contexto.rol != "operador":
        raise ValueError("El registro requiere rol operador.")
    if estado.get("decision") is not None:
        raise ValueError("Ya hay una decisión registrada para la evaluación vigente.")
    escenario = escenario_actual(estado)
    datos = estado.get("resultados")
    referencia = estado.get("archivo_resultados")
    if not escenario or not datos or not referencia:
        raise ValueError("El registro requiere una evaluación completa del escenario vigente.")
    if escenario.personas > contexto.limite_personas or estado.get("meta_aplicada") != contexto.meta:
        raise ValueError("La evaluación no corresponde al contexto vigente.")
    resultado = Resultado.model_validate(datos)
    resultado.comprobar(escenario)
    vigente = recomendar(resultado.promedios(), contexto.meta)
    if vigente is None:
        raise ValueError("Las capacidades evaluadas son insuficientes para la meta vigente.")
    if propuesta.capacidad != vigente or estado.get("recomendacion") != vigente:
        raise ValueError(f"El registro requiere la capacidad vigente de {vigente} puestos.")
    return {**propuesta.model_dump(), "meta": contexto.meta, "escenario": escenario.model_dump(),
            "archivo_resultados": referencia}
