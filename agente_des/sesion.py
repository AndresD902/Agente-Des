"""Entrada de aplicación para conversar, consultar y responder a revisiones."""

from dataclasses import dataclass
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command, Interrupt
from langsmith import tracing_context

from .agente import construir_agente
from .cliente_mcp import ClienteMCP
from .configuracion import Contexto
from .estado import cambiar_meta, resumen_estado
from .revision import REGISTRAR, Propuesta
from .trazas import Trazas


@dataclass
class Salida:
    mensajes: list[BaseMessage]
    resumen: dict
    interrupciones: tuple[Interrupt, ...]


class Sesion:
    def __init__(self, modelo, url_mcp: str, trazas: Trazas):
        self.trazas = trazas
        self.contextos: dict[str, Contexto] = {}
        self.turnos_pendientes: dict[str, str] = {}
        self.agente = construir_agente(modelo, ClienteMCP(url_mcp, trazas), trazas)

    def nuevo(self, contexto: Contexto) -> str:
        hilo = uuid4().hex[:12]
        self.contextos[hilo] = contexto
        self.trazas.evento("hilo_nuevo", hilo=hilo, contexto=contexto.model_dump())
        return hilo

    def _config(self, hilo: str, **metadata) -> dict:
        if hilo not in self.contextos:
            raise ValueError("Ese hilo no existe en este proceso.")
        return {"configurable": {"thread_id": hilo}, "metadata": metadata, "recursion_limit": 40}

    async def estado(self, hilo: str):
        return await self.agente.aget_state(self._config(hilo))

    async def consultar(self, hilo: str) -> Salida:
        estado = await self.estado(hilo)
        resumen = resumen_estado(estado.values, self.contextos[hilo])
        self.trazas.evento("estado_consultado", hilo=hilo, **resumen)
        return Salida([], resumen, estado.interrupts)

    async def meta(self, hilo: str, nueva_meta: float) -> Salida:
        estado = await self.estado(hilo)
        if estado.interrupts:
            raise ValueError("Resuelve la revisión pendiente antes de cambiar la meta.")
        anterior = self.contextos[hilo]
        contexto = Contexto(rol=anterior.rol, meta=nueva_meta, limite_personas=anterior.limite_personas)
        cambios = cambiar_meta(estado.values, contexto)
        if cambios:
            await self.agente.aupdate_state(self._config(hilo), cambios)
        self.contextos[hilo] = contexto
        self.trazas.evento("meta_modificada", hilo=hilo, anterior=anterior.meta, nueva=nueva_meta,
                           reutilizo_resultados=bool(estado.values.get("resultados")),
                           decision_invalidada=bool(cambios and estado.values.get("decision")))
        return await self.consultar(hilo)

    async def enviar(self, hilo: str, texto: str) -> Salida:
        estado = await self.estado(hilo)
        if estado.interrupts:
            raise ValueError("Responde a la revisión pendiente con /aprobar, /editar o /rechazar.")
        turno = uuid4().hex
        self.trazas.evento("usuario", hilo=hilo, turno=turno, mensaje=texto)
        return await self._ejecutar(hilo, turno, {"messages": [HumanMessage(content=texto)]},
                                    len(estado.values.get("messages", [])))

    async def reanudar(self, hilo: str, accion: str, nota: str | None = None) -> Salida:
        estado = await self.estado(hilo)
        if len(estado.interrupts) != 1 or hilo not in self.turnos_pendientes:
            raise ValueError("Selecciona un hilo con una revisión pendiente.")
        pausa = estado.interrupts[0]
        datos = pausa.value
        if datos["name"] != REGISTRAR or self.contextos[hilo].rol != "operador":
            raise ValueError("La revisión no corresponde a un registro de este operador.")
        if accion not in {"approve", "edit", "reject"}:
            raise ValueError("Elige aprobar, editar o rechazar.")
        respuesta: dict = {"type": accion}
        if accion == "edit":
            propuesta = Propuesta(capacidad=datos["args"]["capacidad"], nota=nota)
            respuesta["edited_action"] = {"name": REGISTRAR, "args": propuesta.model_dump()}
        turno = self.turnos_pendientes[hilo]
        self.trazas.evento("revision_humana", hilo=hilo, turno=turno, interrupcion=pausa.id, respuesta=respuesta)
        metadatos = {"registro_rechazado": True} if accion == "reject" else {}
        return await self._ejecutar(hilo, turno, Command(resume={pausa.id: respuesta}),
                                    len(estado.values.get("messages", [])), **metadatos)

    async def _ejecutar(self, hilo: str, turno: str, entrada, inicio: int, **metadata) -> Salida:
        contexto = self.contextos[hilo]
        with tracing_context(enabled=False):
            salida = await self.agente.ainvoke(entrada, self._config(hilo, turno=turno, **metadata),
                                               context=contexto, version="v2")
        resumen = resumen_estado(salida.value, contexto)
        for pausa in salida.interrupts:
            self.turnos_pendientes[hilo] = turno
            self.trazas.evento("interrupcion", hilo=hilo, turno=turno, interrupcion=pausa.id,
                               propuesta=pausa.value, evaluacion=resumen)
        if not salida.interrupts:
            self.turnos_pendientes.pop(hilo, None)
        self.trazas.evento("estado_final", hilo=hilo, turno=turno,
                           pendiente=bool(salida.interrupts), **resumen)
        return Salida(salida.value.get("messages", [])[inicio:], resumen, salida.interrupts)
