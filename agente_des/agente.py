"""Construcción de LangChain, política C y manejo de fallos del modelo."""

import json

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, HumanInTheLoopMiddleware, ModelCallLimitMiddleware
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_config
from langgraph.types import Command
from openai import APIError
from pydantic import ValidationError

from .cliente_mcp import ClienteMCP
from .configuracion import LIMITE_MODELO, Contexto
from .estado import Estado
from .herramientas import crear_herramientas, error_validacion, mensaje_error
from .revision import REGISTRAR, Propuesta, registro_visible, validar_registro
from .trazas import Trazas, correlacion

INSTRUCCIONES = """Eres el agente DES de una oficina de atención estudiantil. Habla en español.
Compara 1, 2 y 3 puestos con fila FIFO, primera llegada al minuto cero y minutos como unidad.
La simulación se obtiene únicamente con evaluar_escenario. Python calcula la menor capacidad
con espera media menor o igual a la meta y devuelve null si las tres son insuficientes.
Presenta los agregados reales y explica el resultado según la meta, las réplicas y la variabilidad
de las esperas medias. La estimación no garantiza el cumplimiento individual ni por réplica.

Usa configurar_escenario con usar_escenario_inicial=true solo si el usuario pide el escenario
inicial documentado. Para un escenario propio nuevo necesitas personas, media de la exponencial,
servicio triangular (mínimo, moda, máximo) o uniforme (mínimo, máximo), réplicas y semilla.
Si faltan datos, pregunta antes de ejecutar. Si ya hay escenario, envía solo los cambios pedidos.
El cambio de tipo de servicio requiere sus parámetros. Ante «cambia el servicio a 1 minuto»,
pregunta si se refiere a un tiempo fijo o a un parámetro de alguna distribución admitida.
Los tiempos fijos solo se usan en la regresión. Usa una herramienta por paso. Si falla una
validación o MCP, explica el error y espera una nueva solicitud. No inventes valores ni resultados.

Consulta el estado para responder sobre resultados vigentes. Rol, meta y límite provienen de la
aplicación. Para cambiar la meta indica el comando /meta de la terminal. Usa registrar_decision
solo si el operador pide registrar y hay capacidad recomendada. Propón una nota breve cuando
no se indique. La decisión requiere la pausa humana. Si se rechaza, informa y finaliza ese turno.
"""


def fallo_de_evaluacion(estado: Estado) -> bool:
    respuestas_con_error = set()
    for mensaje in reversed(estado.get("messages", [])):
        if isinstance(mensaje, HumanMessage):
            break
        if isinstance(mensaje, ToolMessage) and mensaje.status == "error":
            respuestas_con_error.add(mensaje.tool_call_id)
        if isinstance(mensaje, AIMessage) and any(
            llamada["id"] in respuestas_con_error
            and llamada["name"] in {"configurar_escenario", "evaluar_escenario"}
            for llamada in mensaje.tool_calls
        ):
            return True
    return False


class Politica(AgentMiddleware):
    def __init__(self, trazas: Trazas):
        self.trazas = trazas

    async def awrap_model_call(self, solicitud, ejecutar):
        contexto: Contexto = solicitud.runtime.context
        estado: Estado = solicitud.state
        config = get_config()
        ids = correlacion(config)
        if config.get("metadata", {}).get("registro_rechazado"):
            return AIMessage(content="Registro rechazado. La evaluación sigue disponible.")
        visible = registro_visible(estado, contexto) and not fallo_de_evaluacion(estado)
        herramientas = [herramienta for herramienta in solicitud.tools
                        if herramienta.name != REGISTRAR or visible]
        self.trazas.evento("politica_herramientas", **ids, rol=contexto.rol,
                           tiene_resultados=estado.get("resultados") is not None,
                           recomendacion=estado.get("recomendacion"),
                           herramientas=[herramienta.name for herramienta in herramientas])
        datos = {**contexto.model_dump(), "escenario_vigente": estado.get("escenario"),
                 "recomendacion_vigente": estado.get("recomendacion"),
                 "hay_resultados": estado.get("resultados") is not None,
                 "hay_decision": estado.get("decision") is not None}
        sistema = SystemMessage(content=INSTRUCCIONES + "\nDatos de la aplicación\n"
                                + json.dumps(datos, ensure_ascii=False))
        try:
            respuesta = await ejecutar(solicitud.override(
                tools=herramientas, system_message=sistema,
                model_settings={**solicitud.model_settings, "parallel_tool_calls": False},
            ))
        except APIError as error:
            self.trazas.evento("modelo_error", **ids, clase=type(error).__name__,
                               codigo_http=getattr(error, "status_code", None))
            return AIMessage(content="El proveedor del modelo no respondió correctamente. "
                                     "Revisa la configuración de la API y vuelve a intentarlo.",
                             additional_kwargs={"error_proveedor": True})
        for mensaje in respuesta.result:
            if not isinstance(mensaje, AIMessage):
                continue
            self.trazas.evento("modelo_respuesta", **ids, contenido=mensaje.content,
                               llamadas=mensaje.tool_calls, modelo_servido=mensaje.response_metadata.get("model_name"))
            if len(mensaje.tool_calls) > 1:
                self.trazas.evento("herramientas_bloqueadas", **ids, motivo="llamadas simultáneas")
                return AIMessage(content="La solicitud requiere acciones secuenciales. "
                                         "Vuelve a pedir una acción a la vez.")
        return respuesta

    async def awrap_tool_call(self, solicitud, ejecutar):
        llamada = solicitud.tool_call
        nombre, id_llamada = llamada["name"], llamada["id"]
        estado: Estado = solicitud.state
        contexto: Contexto = solicitud.runtime.context
        config = solicitud.runtime.config
        ids = {**correlacion(config), "llamada": id_llamada, "herramienta": nombre}
        try:
            if nombre in {REGISTRAR, "evaluar_escenario"} and fallo_de_evaluacion(estado):
                raise ValueError("Corrige el error de la evaluación en una nueva solicitud.")
            if nombre == REGISTRAR:
                validar_registro(estado, contexto, Propuesta.model_validate(llamada["args"]))
        except (ValidationError, ValueError) as error:
            texto = error_validacion(error) if isinstance(error, ValidationError) else str(error)
            self.trazas.evento("herramienta_bloqueada", **ids, motivo=texto)
            return mensaje_error(id_llamada, texto)

        respuesta = await ejecutar(solicitud)
        mensajes = respuesta.update.get("messages", []) if isinstance(respuesta, Command) else [respuesta]
        for mensaje in mensajes:
            self.trazas.evento("herramienta_respuesta", **ids, estado=mensaje.status, contenido=mensaje.content)
        return respuesta


def construir_agente(modelo, cliente: ClienteMCP, trazas: Trazas):
    return create_agent(
        model=modelo, tools=crear_herramientas(cliente, trazas),
        state_schema=Estado, context_schema=Contexto, checkpointer=InMemorySaver(),
        middleware=[
            ModelCallLimitMiddleware(run_limit=LIMITE_MODELO, exit_behavior="end"),
            Politica(trazas),
            HumanInTheLoopMiddleware(interrupt_mode="per_call", interrupt_on={
                REGISTRAR: {"allowed_decisions": ["approve", "edit", "reject"],
                            "description": "Revisa la propuesta de registro de la capacidad."},
            }),
        ],
    )
