"""Integración de descubrimiento, recurso y llamada por la red."""

import asyncio
import json

from agente_des.cliente_mcp import ClienteMCP
from agente_des.configuracion import MCP_HERRAMIENTA, MCP_RECURSO
from agente_des.modelos import ESCENARIO_INICIAL, CambioEscenario
from agente_des.trazas import Trazas


def test_mcp_descubre_lee_y_ejecuta(mcp_url, evidencias):
    trazas = Trazas(evidencias / "mcp-integracion", "prueba_mcp", "sin_modelo")
    resultado = asyncio.run(ClienteMCP(mcp_url, trazas).evaluar(ESCENARIO_INICIAL, hilo="integracion"))
    referencia = trazas.guardar_resultado(resultado)
    trazas.evento("mcp_resultado", archivo_resultados=referencia, hilo="integracion")
    eventos = [json.loads(linea) for linea in (trazas.carpeta / "eventos.jsonl").read_text(encoding="utf-8").splitlines()]
    assert eventos[2]["herramientas"] == [MCP_HERRAMIENTA]
    assert eventos[3]["uri"] == MCP_RECURSO
    assert json.loads(eventos[3]["contenido"][0]["text"])["capacidades"] == [1, 2, 3]
    assert resultado.escenario == ESCENARIO_INICIAL
    assert all(len(item.replicas) == 30 for item in resultado.capacidades)


def test_mcp_retorna_maximo_de_personas_y_replicas(mcp_url, tmp_path):
    trazas = Trazas(tmp_path, "prueba_mcp", "sin_modelo")
    escenario = CambioEscenario(personas=100, replicas=100).aplicar(ESCENARIO_INICIAL)
    resultado = asyncio.run(ClienteMCP(mcp_url, trazas).evaluar(escenario, hilo="limites"))
    assert len(resultado.muestras) == 100
    assert len(resultado.muestras[-1].servicios) == 100
    assert all(len(item.replicas) == 100 for item in resultado.capacidades)
