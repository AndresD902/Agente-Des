"""Estado por hilo. El contexto de aplicación se inyecta en cada invocación."""

from langchain.agents import AgentState

from .configuracion import Contexto
from .decision import recomendar
from .modelos import Capacidad, Escenario
from .resultado import Resultado


class Estado(AgentState, total=False):
    escenario: dict | None
    resultados: dict | None
    archivo_resultados: str | None
    recomendacion: Capacidad | None
    meta_aplicada: float | None
    decision: dict | None
    error_evaluacion: str | None


def sin_evaluacion() -> dict:
    return {"resultados": None, "archivo_resultados": None, "recomendacion": None,
            "meta_aplicada": None, "decision": None, "error_evaluacion": None}


def escenario_actual(estado: Estado) -> Escenario | None:
    datos = estado.get("escenario")
    return Escenario.model_validate(datos) if datos else None


def cambiar_meta(estado: Estado, contexto: Contexto) -> dict:
    datos = estado.get("resultados")
    resultado = Resultado.model_validate(datos) if datos else None
    if not resultado or estado.get("meta_aplicada") == contexto.meta:
        return {}
    return {"meta_aplicada": contexto.meta, "decision": None,
            "recomendacion": recomendar(resultado.promedios(), contexto.meta)}


def resumen_estado(estado: Estado, contexto: Contexto) -> dict:
    datos = estado.get("resultados")
    return {"escenario": estado.get("escenario"), "meta": contexto.meta,
            "recomendacion": estado.get("recomendacion"), "decision": estado.get("decision"),
            "archivo_resultados": estado.get("archivo_resultados"),
            "error_evaluacion": estado.get("error_evaluacion"),
            "capacidades": [item["resumen"] for item in datos["capacidades"]] if datos else []}
