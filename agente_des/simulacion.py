"""Motor FIFO de lote finito. Solo el servidor MCP y las pruebas lo invocan."""

from collections.abc import Sequence
from math import isfinite
from statistics import mean

import simpy

from .estadisticas import IndicadoresReplica, ResultadoCapacidad, resumir
from .modelos import CAPACIDADES, Capacidad, Escenario
from .muestreo import generar_muestras
from .resultado import Resultado


def simular_corrida(llegadas: Sequence[float], servicios: Sequence[float],
                    capacidad: Capacidad, replica: int = 0) -> IndicadoresReplica:
    if type(capacidad) is not int or capacidad not in CAPACIDADES:
        raise ValueError("La capacidad debe ser 1, 2 o 3.")
    if not llegadas or len(llegadas) != len(servicios) or llegadas[0] != 0:
        raise ValueError("Se requiere una llegada en cero y un servicio por persona.")
    if (any(not isfinite(t) or t < 0 for t in llegadas)
            or any(a > b for a, b in zip(llegadas, llegadas[1:]))
            or any(not isfinite(t) or t <= 0 for t in servicios)):
        raise ValueError("Las llegadas deben ser finitas y ordenadas y los servicios positivos y finitos.")

    entorno = simpy.Environment()
    puestos = simpy.Resource(entorno, capacity=capacidad)
    esperas = [0.0] * len(llegadas)

    def atender(indice: int, llegada: float, servicio: float):
        yield entorno.timeout(llegada)
        with puestos.request() as turno:
            yield turno
            esperas[indice] = entorno.now - llegada
            if not isfinite(entorno.now + servicio):
                raise ValueError("El reloj de simulación excede el rango de precisión disponible.")
            yield entorno.timeout(servicio)

    for i, (llegada, servicio) in enumerate(zip(llegadas, servicios, strict=True)):
        entorno.process(atender(i, llegada, servicio))
    entorno.run()
    return IndicadoresReplica(replica=replica, esperas=esperas,
                             espera_promedio=mean(esperas), ultima_salida=entorno.now)


def simular(escenario: Escenario) -> Resultado:
    muestras = []
    corridas = {capacidad: [] for capacidad in CAPACIDADES}
    for r in range(escenario.replicas):
        muestra = generar_muestras(escenario, r)
        muestras.append(muestra)
        for capacidad in CAPACIDADES:
            corridas[capacidad].append(simular_corrida(muestra.llegadas, muestra.servicios,
                                                       capacidad, replica=r))
    return Resultado(escenario=escenario, muestras=muestras, capacidades=[
        ResultadoCapacidad(resumen=resumir(capacidad, replicas), replicas=replicas)
        for capacidad, replicas in corridas.items()
    ])
