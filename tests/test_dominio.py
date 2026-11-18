"""Regla aislada, validación de entradas y autorización interna."""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agente_des.configuracion import Contexto
from agente_des.decision import recomendar
from agente_des.herramientas import registrar_decision
from agente_des.modelos import ESCENARIO_INICIAL, Escenario

CONTROLADAS = {1: 7.5, 2: 2.0, 3: 0.5}


def test_p2_igualdad_y_capacidad_minima(guardar_caso):
    obtenidas = {meta: recomendar(CONTROLADAS, meta) for meta in (2.0, 8.0)}
    assert obtenidas == {2.0: 2, 8.0: 1}
    guardar_caso("P02-regla", promedios_controlados=CONTROLADAS, recomendaciones=obtenidas)


def test_p3_regla_controlada_sin_capacidad(guardar_caso):
    obtenida = recomendar(CONTROLADAS, 0.25)
    assert obtenida is None
    guardar_caso("P03-regla", promedios_controlados=CONTROLADAS, meta=0.25, recomendacion=obtenida)


def test_p6_campos_invalidos(guardar_caso):
    entradas = [
        {"personas": 0}, {"personas": 101}, {"personas": 1.5}, {"personas": True},
        {"llegadas": {"tipo": "exponencial", "media": 0}},
        {"llegadas": {"tipo": "exponencial", "media": float("inf")}},
        {"servicio": {"tipo": "triangular", "minimo": 1, "moda": 6, "maximo": 5}},
        {"servicio": {"tipo": "uniforme", "minimo": 3, "maximo": 1}},
        {"replicas": 29}, {"replicas": 101}, {"semilla_base": -1}, {"semilla_base": 2.5},
    ]
    errores = []
    for cambio in entradas:
        with pytest.raises(ValidationError) as capturado:
            Escenario.model_validate(ESCENARIO_INICIAL.model_dump() | cambio)
        errores.append({"entrada": repr(cambio), "errores": [e["msg"] for e in capturado.value.errors()]})
    for meta in (-1, float("nan"), float("inf"), True):
        with pytest.raises(ValidationError):
            recomendar(CONTROLADAS, meta)
        with pytest.raises(ValidationError) as capturado:
            Contexto(meta=meta)
        errores.append({"meta": repr(meta), "errores": [e["msg"] for e in capturado.value.errors()]})
    for capacidades in ({1: 2, 2: 1}, {1: 2, 2: 1, 4: 0}, {True: 2, 2: 1, 3: 0}):
        with pytest.raises(ValueError):
            recomendar(capacidades, 1)
    guardar_caso("P06-dominio", entradas_rechazadas=errores, conjuntos_de_capacidad_rechazados=3)


def test_p11_invocacion_interna_observador(guardar_caso):
    runtime = SimpleNamespace(context=Contexto(rol="observador"), state={}, tool_call_id="directa-p11")
    respuesta = asyncio.run(registrar_decision.coroutine(capacidad=3, nota="Propuesta", runtime=runtime))
    assert respuesta.status == "error" and respuesta.tool_call_id == "directa-p11"
    assert "requiere rol operador" in respuesta.content
    assert runtime.state == {}
    guardar_caso("P11-validacion", rol="observador", obtenido=respuesta.content, decision=None)
