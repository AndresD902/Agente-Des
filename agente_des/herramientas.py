"""Operaciones tipadas. Las simulaciones del agente salen por ClienteMCP."""

import json

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from pydantic import ValidationError

from .cliente_mcp import ClienteMCP, ErrorMCP
from .configuracion import Contexto
from .decision import recomendar
from .estado import Estado, escenario_actual, resumen_estado, sin_evaluacion
from .modelos import ESCENARIO_INICIAL, CambioEscenario
from .revision import Propuesta, validar_registro
from .trazas import Trazas, correlacion


def mensaje_error(llamada: str, texto: str) -> ToolMessage:
    return ToolMessage(content=texto, tool_call_id=llamada, status="error")


def error_validacion(error: ValidationError) -> str:
    detalles = [f"{'.'.join(map(str, problema['loc']))} ({problema['msg']})"
                for problema in error.errors(include_input=False, include_url=False)]
    return "Revisa los datos del escenario o de la propuesta. " + ", ".join(detalles)


def actualizar(runtime: ToolRuntime, contenido: str, cambios: dict, error: bool = False) -> Command:
    mensaje = ToolMessage(content=contenido, tool_call_id=runtime.tool_call_id,
                          status="error" if error else "success")
    return Command(update={**cambios, "messages": [mensaje]})


@tool
async def registrar_decision(capacidad: int, nota: str, runtime: ToolRuntime[Contexto, Estado]) -> Command | ToolMessage:
    """Registra la capacidad recomendada y una nota breve tras la revisión humana."""
    try:
        propuesta = Propuesta(capacidad=capacidad, nota=nota)
        decision = validar_registro(runtime.state, runtime.context, propuesta)
    except ValidationError as error:
        return mensaje_error(runtime.tool_call_id, error_validacion(error))
    except ValueError as error:
        return mensaje_error(runtime.tool_call_id, str(error))
    return actualizar(runtime, f"Decisión registrada por revisión humana. {capacidad} puestos. Nota: {decision['nota']}",
                      {"decision": decision})


def crear_herramientas(cliente: ClienteMCP, trazas: Trazas):
    @tool
    async def configurar_escenario(runtime: ToolRuntime[Contexto, Estado],
                                   cambios: CambioEscenario | None = None,
                                   usar_escenario_inicial: bool = False) -> Command | ToolMessage:
        """Prepara un escenario. Usa el inicial solo si se pidió. Envía únicamente los cambios solicitados."""
        anterior = escenario_actual(runtime.state)
        base = ESCENARIO_INICIAL if usar_escenario_inicial else anterior
        try:
            escenario = (cambios or CambioEscenario()).aplicar(base)
        except ValidationError as error:
            return mensaje_error(runtime.tool_call_id, error_validacion(error))
        if escenario.personas > runtime.context.limite_personas:
            return mensaje_error(runtime.tool_call_id, f"El límite de este hilo es {runtime.context.limite_personas} personas.")
        if escenario == anterior:
            return ToolMessage(content="El escenario ya está configurado.", tool_call_id=runtime.tool_call_id)
        trazas.evento("escenario_configurado", **correlacion(runtime.config), llamada=runtime.tool_call_id,
                      escenario=escenario.model_dump(),
                      resultado_invalidado=runtime.state.get("resultados") is not None,
                      decision_invalidada=runtime.state.get("decision") is not None)
        return actualizar(runtime, "Escenario configurado. Usa evaluar_escenario para obtener resultados vigentes.",
                          {**sin_evaluacion(), "escenario": escenario.model_dump()})

    @tool
    async def evaluar_escenario(runtime: ToolRuntime[Contexto, Estado]) -> Command | ToolMessage:
        """Ejecuta por MCP las tres capacidades del escenario configurado y aplica la meta del contexto."""
        escenario = escenario_actual(runtime.state)
        if escenario is None:
            return mensaje_error(runtime.tool_call_id, "Indica el escenario inicial o proporciona los parámetros faltantes.")
        if escenario.personas > runtime.context.limite_personas:
            return mensaje_error(runtime.tool_call_id, "La cantidad de personas supera el límite de este hilo.")
        contexto = runtime.context
        ids = {**correlacion(runtime.config), "llamada": runtime.tool_call_id}
        try:
            resultado = await cliente.evaluar(escenario, **ids)
            archivo = trazas.guardar_resultado(resultado)
        except (ErrorMCP, OSError) as error:
            texto = str(error) if isinstance(error, ErrorMCP) else "No se pudo guardar la evidencia de la evaluación."
            return actualizar(runtime, texto, {**sin_evaluacion(), "error_evaluacion": texto}, error=True)
        nuevas = {
            "resultados": resultado.model_dump(),
            "archivo_resultados": archivo,
            "recomendacion": recomendar(resultado.promedios(), contexto.meta),
            "meta_aplicada": contexto.meta,
            "decision": None,
            "error_evaluacion": None,
        }
        resumen = resumen_estado({**runtime.state, **nuevas}, contexto)
        trazas.evento("mcp_resultado", **ids, **resumen)
        return actualizar(runtime, json.dumps(resumen, ensure_ascii=False), nuevas)

    @tool
    async def consultar_evaluacion(runtime: ToolRuntime[Contexto, Estado]) -> ToolMessage:
        """Consulta la configuración, los agregados vigentes y si hay una decisión registrada."""
        resumen = resumen_estado(runtime.state, runtime.context)
        return ToolMessage(content=json.dumps(resumen, ensure_ascii=False), tool_call_id=runtime.tool_call_id)

    return [configurar_escenario, evaluar_escenario, consultar_evaluacion, registrar_decision]
