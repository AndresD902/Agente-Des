"""Tiempos en minutos, con un generador local por flujo y réplica."""

from itertools import accumulate
from math import isfinite
from random import Random

from .modelos import Contrato, Escenario, NoNegativo, Positivo, Semilla, Triangular


class Muestras(Contrato):
    replica: int
    semilla_llegadas: Semilla
    semilla_servicios: Semilla
    intervalos: list[NoNegativo]
    llegadas: list[NoNegativo]
    servicios: list[Positivo]


def exponencial(rng: Random, media: float) -> float:
    tasa = 1.0 / media
    if isfinite(tasa):
        return rng.expovariate(tasa)
    # Una media subnormal puede desbordar al invertirla.
    return rng.expovariate(1.0) * media


def triangular(rng: Random, minimo: float, moda: float, maximo: float) -> float:
    return rng.triangular(minimo, maximo, moda)


def uniforme(rng: Random, minimo: float, maximo: float) -> float:
    return rng.uniform(minimo, maximo)


def generar_muestras(escenario: Escenario, replica: int) -> Muestras:
    semilla_llegadas = escenario.semilla_base + 2 * replica
    semilla_servicios = semilla_llegadas + 1
    rng_llegadas = Random(semilla_llegadas)
    rng_servicios = Random(semilla_servicios)
    intervalos = [exponencial(rng_llegadas, escenario.llegadas.media)
                  for _ in range(escenario.personas - 1)]
    servicio = escenario.servicio
    if isinstance(servicio, Triangular):
        servicios = [triangular(rng_servicios, servicio.minimo, servicio.moda, servicio.maximo)
                     for _ in range(escenario.personas)]
    else:
        servicios = [uniforme(rng_servicios, servicio.minimo, servicio.maximo)
                     for _ in range(escenario.personas)]
    return Muestras(replica=replica, semilla_llegadas=semilla_llegadas,
                    semilla_servicios=semilla_servicios, intervalos=intervalos,
                    llegadas=list(accumulate(intervalos, initial=0.0)), servicios=servicios)
