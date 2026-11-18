"""Evidencia local con correlación por hilo, turno y llamada de herramienta."""

from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
import re
from uuid import uuid4

from .resultado import Resultado

PATRON_SECRETO = re.compile(r"\b(?:sk-|lsv2_|ghp_|github_pat_)[A-Za-z0-9_-]{8,}|(?i:\bbearer\s+[^\s,;]+)")


def instante() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def correlacion(config: dict) -> dict:
    return {"hilo": config.get("configurable", {}).get("thread_id"),
            "turno": config.get("metadata", {}).get("turno")}


class Trazas:
    def __init__(self, carpeta: Path, origen: str, modelo: str, secretos: tuple[str, ...] = ()):
        self.carpeta = carpeta
        self.secretos = tuple(valor for valor in secretos if valor)
        carpeta.mkdir(parents=True, exist_ok=True)
        self.evento("sesion", origen=origen, modelo=modelo)

    def depurar(self, valor):
        if isinstance(valor, str):
            for secreto in self.secretos:
                valor = valor.replace(secreto, "[redactado]")
            return PATRON_SECRETO.sub("[redactado]", valor)
        if isinstance(valor, dict):
            return {self.depurar(k): self.depurar(v) for k, v in valor.items()}
        if isinstance(valor, (list, tuple)):
            return [self.depurar(elemento) for elemento in valor]
        if isinstance(valor, float) and not isfinite(valor):
            return str(valor)
        return valor

    def evento(self, evento: str, **datos) -> None:
        linea = self.depurar({"fecha_utc": instante(), "evento": evento, **datos})
        with (self.carpeta / "eventos.jsonl").open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(linea, ensure_ascii=False, allow_nan=False) + "\n")

    def guardar_resultado(self, resultado: Resultado) -> str:
        archivo = Path("resultados") / f"{uuid4().hex}.json"
        ruta = self.carpeta / archivo
        ruta.parent.mkdir(exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")
        temporal.replace(ruta)
        return archivo.as_posix()
