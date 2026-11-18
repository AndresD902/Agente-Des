"""Indicadores de una corrida y agregación entre réplicas."""

from statistics import mean, stdev

from .modelos import Capacidad, Contrato, NoNegativo


class IndicadoresReplica(Contrato):
    replica: int
    esperas: list[NoNegativo]
    espera_promedio: NoNegativo
    ultima_salida: NoNegativo


class Resumen(Contrato):
    capacidad: Capacidad
    espera_promedio: NoNegativo
    ultima_salida_promedio: NoNegativo
    desviacion_esperas: NoNegativo


class ResultadoCapacidad(Contrato):
    resumen: Resumen
    replicas: list[IndicadoresReplica]


def resumir(capacidad: Capacidad, replicas: list[IndicadoresReplica]) -> Resumen:
    esperas = [replica.espera_promedio for replica in replicas]
    return Resumen(
        capacidad=capacidad,
        espera_promedio=mean(esperas),
        ultima_salida_promedio=mean(replica.ultima_salida for replica in replicas),
        desviacion_esperas=stdev(esperas),
    )
