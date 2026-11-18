"""P1, P13 y P14 verifican indicadores, FIFO y muestras reutilizadas."""

from statistics import mean, stdev

import pytest

from agente_des import simulacion
from agente_des.decision import recomendar
from agente_des.modelos import CAPACIDADES, ESCENARIO_INICIAL, CambioEscenario, CambioServicio

TOLERANCIA = 1e-10


def test_p1_escenario_inicial(guardar_caso):
    resultado = simulacion.simular(ESCENARIO_INICIAL)
    resultado.comprobar(ESCENARIO_INICIAL)
    for capacidad in resultado.capacidades:
        corridas = capacidad.replicas
        resumen = capacidad.resumen
        esperas = [corrida.espera_promedio for corrida in corridas]
        assert len(corridas) == 30
        assert resumen.espera_promedio == pytest.approx(mean(esperas), abs=TOLERANCIA)
        assert resumen.desviacion_esperas == pytest.approx(stdev(esperas), abs=TOLERANCIA)
        assert resumen.ultima_salida_promedio == pytest.approx(
            mean(corrida.ultima_salida for corrida in corridas), abs=TOLERANCIA)
    recomendacion = recomendar(resultado.promedios(), 1.0)
    assert recomendacion == 3
    guardar_caso("P01-simulador", resultado=resultado.model_dump(), meta=1.0, recomendacion=recomendacion)


def test_p13_regresion_fifo(guardar_caso):
    esperados = {
        1: ([0, 3, 6, 9, 12, 15], 7.5, 24),
        2: ([0, 0, 2, 2, 4, 4], 2, 13),
        3: ([0, 0, 0, 1, 1, 1], 0.5, 10),
    }
    obtenidos = {}
    for capacidad, (esperas, media, ultima) in esperados.items():
        corrida = simulacion.simular_corrida(list(range(6)), [4] * 6, capacidad)
        assert corrida.esperas == pytest.approx(esperas, abs=TOLERANCIA)
        assert corrida.espera_promedio == pytest.approx(media, abs=TOLERANCIA)
        assert corrida.ultima_salida == pytest.approx(ultima, abs=TOLERANCIA)
        obtenidos[capacidad] = corrida.model_dump()
    guardar_caso("P13", llegadas=list(range(6)), servicios=[4] * 6, obtenidos=obtenidos,
                 tolerancia=TOLERANCIA)


def test_p14_semillas_y_muestras_compartidas(monkeypatch, guardar_caso):
    entradas = {}
    ejecutar = simulacion.simular_corrida

    def capturar(llegadas, servicios, capacidad, replica):
        entradas[replica, capacidad] = llegadas, servicios
        return ejecutar(llegadas, servicios, capacidad, replica)

    with monkeypatch.context() as parche:
        parche.setattr(simulacion, "simular_corrida", capturar)
        inicial = simulacion.simular(ESCENARIO_INICIAL)

    for r, muestra in enumerate(inicial.muestras):
        assert muestra.semilla_llegadas == 2026 + 2 * r
        assert muestra.semilla_servicios == 2027 + 2 * r
        assert len(set(muestra.intervalos)) > 1
        assert all(1 <= t <= 5 for t in muestra.servicios)
        for capacidad in CAPACIDADES:
            llegadas, servicios = entradas[r, capacidad]
            assert llegadas is muestra.llegadas and servicios is muestra.servicios
    assert inicial.muestras[0].llegadas != inicial.muestras[1].llegadas
    assert inicial.muestras[0].servicios != inicial.muestras[1].servicios
    misma = simulacion.simular(ESCENARIO_INICIAL)
    assert inicial == misma
    otra = simulacion.simular(CambioEscenario(semilla_base=2027).aplicar(ESCENARIO_INICIAL))
    assert inicial.muestras[0].llegadas != otra.muestras[0].llegadas
    assert inicial.muestras[0].servicios != otra.muestras[0].servicios
    uniforme = simulacion.simular(CambioEscenario(servicio=CambioServicio(
        tipo="uniforme", minimo=1, maximo=3)).aplicar(ESCENARIO_INICIAL))
    assert all(1 <= t <= 3 for muestra in uniforme.muestras for t in muestra.servicios)
    guardar_caso("P14", misma_semilla_reproduce_resultado=inicial == misma,
                 capacidades_con_identidad_comprobada=list(CAPACIDADES),
                 replicas_comprobadas=len(inicial.muestras),
                 primeras_replicas=[m.model_dump() for m in inicial.muestras[:2]],
                 otras_primeras_replicas=[m.model_dump() for m in otra.muestras[:2]],
                 primeras_uniformes=[m.model_dump() for m in uniforme.muestras[:2]])
