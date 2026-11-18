"""Respuesta estructurada de MCP y comprobaciones de integridad."""

from itertools import accumulate
from math import isclose
from statistics import mean

from .estadisticas import ResultadoCapacidad, resumir
from .modelos import CAPACIDADES, Contrato, Escenario
from .muestreo import Muestras


class Resultado(Contrato):
    escenario: Escenario
    muestras: list[Muestras]
    capacidades: list[ResultadoCapacidad]

    def comprobar(self, esperado: Escenario) -> None:
        if self.escenario != esperado or len(self.muestras) != esperado.replicas:
            raise ValueError("El resultado no corresponde al escenario o faltan muestras.")
        if tuple(item.resumen.capacidad for item in self.capacidades) != CAPACIDADES:
            raise ValueError("Se requieren resultados para 1, 2 y 3 puestos.")
        for r, muestra in enumerate(self.muestras):
            semilla = esperado.semilla_base + 2 * r
            if (muestra.replica != r or muestra.semilla_llegadas != semilla
                    or muestra.semilla_servicios != semilla + 1
                    or len(muestra.intervalos) != esperado.personas - 1
                    or len(muestra.servicios) != esperado.personas
                    or muestra.llegadas != list(accumulate(muestra.intervalos, initial=0.0))
                    or any(not esperado.servicio.minimo <= t <= esperado.servicio.maximo
                           for t in muestra.servicios)):
                raise ValueError(f"Las muestras de la réplica {r} están incompletas o son inválidas.")
        for item in self.capacidades:
            if len(item.replicas) != esperado.replicas:
                raise ValueError("El resultado tiene una cantidad incorrecta de réplicas.")
            for r, corrida in enumerate(item.replicas):
                if (corrida.replica != r or len(corrida.esperas) != esperado.personas
                        or not isclose(corrida.espera_promedio, mean(corrida.esperas),
                                       rel_tol=1e-12, abs_tol=1e-12)):
                    raise ValueError(f"Los indicadores de la réplica {r} son inválidos.")
            if item.resumen != resumir(item.resumen.capacidad, item.replicas):
                raise ValueError("Los agregados no coinciden con las réplicas.")

    def promedios(self) -> dict[int, float]:
        return {item.resumen.capacidad: item.resumen.espera_promedio for item in self.capacidades}
