"""Servidor de integración en otro proceso y evidencia opcional."""

from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import sys
from time import monotonic, sleep

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption("--evidencias", type=Path, help="Directorio de evidencias de los casos.")


@pytest.fixture
def evidencias(request, tmp_path):
    ruta = request.config.getoption("--evidencias") or tmp_path
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


@pytest.fixture
def guardar_caso(evidencias):
    def guardar(caso, **datos):
        (evidencias / f"{caso}.json").write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return guardar


@contextmanager
def servidor_de_prueba():
    with socket.socket() as reserva:
        reserva.bind(("127.0.0.1", 0))
        puerto = reserva.getsockname()[1]
    proceso = subprocess.Popen(
        [sys.executable, "servidor_mcp.py", "--port", str(puerto)], cwd=RAIZ,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        vencimiento = monotonic() + 12
        while monotonic() < vencimiento:
            if proceso.poll() is not None:
                pytest.fail(f"El servidor MCP terminó al arrancar. {proceso.stderr.read()}")
            try:
                with socket.create_connection(("127.0.0.1", puerto), timeout=0.2):
                    break
            except OSError:
                sleep(0.05)
        else:
            pytest.fail("El servidor MCP no quedó listo para la prueba.")
        yield f"http://127.0.0.1:{puerto}/mcp"
    finally:
        if proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=5)
        proceso.stderr.close()


@pytest.fixture(scope="session")
def mcp_url():
    with servidor_de_prueba() as url:
        yield url


@pytest.fixture
def mcp_detenido():
    with servidor_de_prueba() as url:
        pass
    return url
