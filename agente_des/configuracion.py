"""Configuración confiable suministrada por la aplicación."""

from typing import Literal
from urllib.parse import urlsplit

from .modelos import Contrato, NoNegativo, Personas

Rol = Literal["observador", "operador"]
MCP_URL = "http://127.0.0.1:8765/mcp"
MCP_HERRAMIENTA = "simular_escenario"
MCP_RECURSO = "des://escenario/supuestos"
LIMITE_MODELO = 6


class Contexto(Contrato):
    rol: Rol = "observador"
    meta: NoNegativo = 1.0
    limite_personas: Personas = 100


def comprobar_url_mcp(url: str) -> str:
    destino = urlsplit(url)
    if (destino.scheme != "http" or destino.hostname not in {"localhost", "127.0.0.1", "::1"}
            or destino.username is not None or destino.query or destino.fragment):
        raise ValueError("La URL de MCP debe ser HTTP local y no incluir credenciales.")
    if destino.port == 0:
        raise ValueError("El puerto de MCP debe ser distinto de cero.")
    return url
