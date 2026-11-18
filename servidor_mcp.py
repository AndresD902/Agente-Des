"""Servidor MCP local. Ejecutar con `python servidor_mcp.py`."""

import argparse
import json
import os

from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from agente_des.configuracion import MCP_HERRAMIENTA, MCP_RECURSO
from agente_des.modelos import CAPACIDADES, ESCENARIO_INICIAL, Escenario
from agente_des.resultado import Resultado
from agente_des.simulacion import simular

mcp = MCPServer("Oficina de atención estudiantil", version="1.0")


@mcp.resource(MCP_RECURSO, mime_type="application/json")
def supuestos() -> str:
    return json.dumps({
        "supuestos": ["Minutos", "Cola única FIFO", "Sistema inicialmente vacío",
                      "Primera llegada al minuto cero", "Sin abandono",
                      "Fin al salir la última persona"],
        "capacidades": list(CAPACIDADES),
        "distribuciones": {
            "exponencial": "Media positiva y finita de los intervalos entre llegadas",
            "triangular": "Parámetros finitos con 0 < mínimo < moda < máximo",
            "uniforme": "Límites finitos con 0 < mínimo < máximo",
        },
        "semillas": {"llegadas": "semilla_base + 2*r", "servicios": "semilla_base + 2*r + 1"},
        "muestras_compartidas": True,
        "escenario_inicial": ESCENARIO_INICIAL.model_dump(mode="json"),
    }, ensure_ascii=False)


@mcp.tool(name=MCP_HERRAMIENTA, structured_output=True)
def simular_escenario(escenario: Escenario) -> Resultado:
    """Compara 1, 2 y 3 puestos FIFO con muestras comunes por réplica."""
    try:
        return simular(escenario)
    except (ValueError, ArithmeticError) as error:
        raise ToolError("La simulación no pudo calcular tiempos finitos para esa configuración.") from error


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=os.getenv("DES_MCP_PORT", "8765"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=args.port, json_response=True)


if __name__ == "__main__":
    main()
