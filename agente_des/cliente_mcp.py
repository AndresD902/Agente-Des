"""Cliente de red. Cada evaluación descubre, lee y llama al servidor real."""

from anyio import fail_after
from mcp import Client
from pydantic import ValidationError

from .configuracion import MCP_HERRAMIENTA, MCP_RECURSO, comprobar_url_mcp
from .modelos import Escenario
from .resultado import Resultado
from .trazas import Trazas


class ErrorMCP(Exception):
    """Fallo de MCP que se puede mostrar en la interfaz."""


class ClienteMCP:
    def __init__(self, url: str, trazas: Trazas, timeout: float = 15.0):
        self.url = comprobar_url_mcp(url)
        self.trazas = trazas
        self.timeout = timeout

    async def evaluar(self, escenario: Escenario, **correlacion) -> Resultado:
        argumentos = {"escenario": escenario.model_dump(mode="json")}
        fase = "conexión"
        self.trazas.evento("mcp_conectar", url=self.url, **correlacion)
        try:
            with fail_after(self.timeout):
                async with Client(self.url, read_timeout_seconds=self.timeout) as cliente:
                    fase = "descubrimiento de herramientas"
                    herramientas = [t.name for t in (await cliente.list_tools()).tools]
                    self.trazas.evento("mcp_descubrir", herramientas=herramientas,
                                       protocolo=cliente.protocol_version, **correlacion)
                    if MCP_HERRAMIENTA not in herramientas:
                        raise ErrorMCP("El servidor MCP no ofrece la herramienta de simulación.")
                    fase = "lectura de recurso"
                    recurso = await cliente.read_resource(MCP_RECURSO)
                    if not recurso.contents:
                        raise ErrorMCP("El recurso MCP de supuestos está vacío.")
                    self.trazas.evento("mcp_leer_recurso", uri=MCP_RECURSO,
                                       contenido=[c.model_dump(mode="json") for c in recurso.contents],
                                       **correlacion)
                    fase = "simulación"
                    self.trazas.evento("mcp_llamar", herramienta=MCP_HERRAMIENTA,
                                       argumentos=argumentos, **correlacion)
                    respuesta = await cliente.call_tool(MCP_HERRAMIENTA, arguments=argumentos)
                    if respuesta.is_error or respuesta.structured_content is None:
                        raise ErrorMCP("MCP no pudo completar la simulación. Revisa la configuración y el servidor.")
        except Exception as error:
            self.trazas.evento("mcp_error", fase=fase, clase=type(error).__name__, **correlacion)
            if isinstance(error, ErrorMCP):
                raise
            raise ErrorMCP(f"MCP no está disponible o no completó la etapa de {fase}. "
                           "Comprueba que el servidor esté iniciado.") from error
        try:
            resultado = Resultado.model_validate(respuesta.structured_content)
            resultado.comprobar(escenario)
        except (ValidationError, ValueError) as error:
            self.trazas.evento("mcp_error", fase="validación", clase=type(error).__name__, **correlacion)
            raise ErrorMCP("MCP devolvió resultados incompletos o incompatibles con el escenario.") from error
        return resultado
