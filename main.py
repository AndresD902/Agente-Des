"""Terminal del agente de simulación DES."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from agente_des.configuracion import MCP_URL, Contexto, comprobar_url_mcp
from agente_des.herramientas import error_validacion
from agente_des.sesion import Salida, Sesion
from agente_des.trazas import Trazas

AYUDA = """Escribe una solicitud o usa uno de estos comandos.
  /nuevo [observador|operador]  Abre otro hilo
  /hilos                      Lista los hilos de esta sesión
  /usar ID                    Continúa un hilo existente
  /estado                     Consulta el escenario y los resultados
  /meta MINUTOS               Actualiza la meta del hilo
  /aprobar                    Aprueba la revisión pendiente
  /editar NOTA                Cambia la nota y aprueba la revisión
  /rechazar                   Rechaza la revisión pendiente
  /ayuda                      Muestra estos comandos
  /salir                      Cierra la sesión"""


def mostrar_estado(resumen: dict) -> None:
    escenario = resumen["escenario"]
    if escenario is None:
        print("Aún falta configurar el escenario.")
        return
    servicio = escenario["servicio"]
    parametros = ", ".join(f"{k}={v:g}" for k, v in servicio.items() if k != "tipo")
    print(f"{escenario['personas']} personas. Llegadas exponenciales con media "
          f"{escenario['llegadas']['media']:g} min. Servicio {servicio['tipo']} ({parametros}).")
    print(f"{escenario['replicas']} réplicas por capacidad, semilla {escenario['semilla_base']}, "
          f"meta {resumen['meta']:g} min.")
    if resumen["error_evaluacion"]:
        print(resumen["error_evaluacion"])
        return
    if not resumen["capacidades"]:
        print("La evaluación del escenario está pendiente.")
        return
    print("Puestos | Espera media (min) | Última salida media (min) | Desv. muestral de las esperas (min)")
    for fila in resumen["capacidades"]:
        print(f"{fila['capacidad']:>7} | {fila['espera_promedio']:>17.6f} | "
              f"{fila['ultima_salida_promedio']:>25.6f} | {fila['desviacion_esperas']:>36.6f}")
    recomendacion = resumen["recomendacion"]
    if recomendacion is None:
        print("Las capacidades evaluadas son insuficientes para la meta.")
    else:
        puesto = "puesto" if recomendacion == 1 else "puestos"
        print(f"Se recomienda usar {recomendacion} {puesto}, la menor capacidad que cumple la meta.")
    print("Las desviaciones describen la variación de las esperas medias entre réplicas.")
    print("La meta se aplica al promedio de las réplicas. Las esperas varían por persona y por réplica.")
    decision = resumen["decision"]
    if decision:
        print(f"Decisión registrada con {decision['capacidad']} puestos. Nota registrada. {decision['nota']}")
    print(f"Detalle en {resumen['archivo_resultados']} dentro de la carpeta de evidencia.")


def mostrar_revision(salida: Salida) -> None:
    if not salida.interrupciones:
        return
    propuesta = salida.interrupciones[0].value
    print("Revisión pendiente. El registro requiere una respuesta explícita.")
    print(json.dumps({"accion": propuesta["name"], **propuesta["args"],
                      "meta": salida.resumen["meta"], "escenario": salida.resumen["escenario"]},
                     ensure_ascii=False, indent=2))
    print("Usa /aprobar, /editar NOTA o /rechazar.")


def mostrar_turno(salida: Salida) -> None:
    herramientas = [m for m in salida.mensajes if isinstance(m, ToolMessage)]
    errores = [m.text for m in herramientas if m.status == "error"]
    fallo_proveedor = next((m.text for m in salida.mensajes
                            if isinstance(m, AIMessage) and m.additional_kwargs.get("error_proveedor")), "")
    if errores:
        for error in errores:
            print(error)
    elif salida.interrupciones or any(m.name in {"evaluar_escenario", "consultar_evaluacion",
                                                  "registrar_decision"} for m in herramientas):
        mostrar_estado(salida.resumen)
    else:
        texto = next((m.text for m in reversed(salida.mensajes) if isinstance(m, AIMessage) and m.text), "")
        print(texto or "El turno terminó. Usa /estado para consultar los datos guardados.")
        fallo_proveedor = ""
    if fallo_proveedor:
        print(fallo_proveedor)
    mostrar_revision(salida)


async def interactuar(sesion: Sesion, contexto: Contexto) -> None:
    hilo = sesion.nuevo(contexto)
    print(f"Evidencia de la sesión en {sesion.trazas.carpeta}")
    print(AYUDA)
    while True:
        try:
            rol = sesion.contextos[hilo].rol
            entrada = input(f"[{hilo} {rol}] > ").strip()
        except EOFError:
            return
        if not entrada:
            continue
        comando, _, argumento = entrada.partition(" ")
        argumento = argumento.strip()
        try:
            match comando.lower():
                case "/salir":
                    return
                case "/ayuda":
                    print(AYUDA)
                case "/nuevo":
                    hilo = sesion.nuevo(Contexto(rol=argumento or contexto.rol, meta=contexto.meta,
                                                 limite_personas=contexto.limite_personas))
                case "/hilos":
                    for clave, datos in sesion.contextos.items():
                        pendiente = " (revisión pendiente)" if clave in sesion.turnos_pendientes else ""
                        print(f"{clave}  {datos.rol}  meta {datos.meta:g} min{pendiente}")
                case "/usar":
                    estado = await sesion.consultar(argumento)
                    hilo = argumento
                    mostrar_revision(estado)
                case "/estado":
                    salida = await sesion.consultar(hilo)
                    mostrar_estado(salida.resumen)
                    mostrar_revision(salida)
                case "/meta":
                    try:
                        meta = float(argumento)
                    except ValueError:
                        raise ValueError("Escribe /meta seguido de los minutos, con punto decimal.") from None
                    mostrar_estado((await sesion.meta(hilo, meta)).resumen)
                case "/aprobar" | "/editar" | "/rechazar":
                    accion = {"/aprobar": "approve", "/editar": "edit", "/rechazar": "reject"}[comando.lower()]
                    salida = await sesion.reanudar(hilo, accion, argumento if accion == "edit" else None)
                    if accion == "reject":
                        print("Registro rechazado. La evaluación sigue disponible.")
                    else:
                        mostrar_turno(salida)
                case _:
                    if entrada.startswith("/"):
                        print("Comando desconocido. Usa /ayuda.")
                    else:
                        mostrar_turno(await sesion.enviar(hilo, entrada))
        except ValidationError as error:
            print(error_validacion(error))
        except ValueError as error:
            print(str(error))


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rol", choices=("observador", "operador"), default=os.getenv("DES_ROL", "observador"))
    parser.add_argument("--meta", type=float, default=os.getenv("DES_META", "1"))
    parser.add_argument("--mcp-url", default=os.getenv("DES_MCP_URL", MCP_URL))
    parser.add_argument("--evidencias", type=Path, default=os.getenv("DES_EVIDENCIAS", "evidencias/local"))
    args = parser.parse_args()
    clave, nombre = os.getenv("OPENAI_API_KEY", "").strip(), os.getenv("OPENAI_MODEL", "").strip()
    if not clave or not nombre:
        parser.error("Configura OPENAI_API_KEY y OPENAI_MODEL en .env para usar el modo real.")
    try:
        contexto = Contexto(rol=args.rol, meta=args.meta)
        url = comprobar_url_mcp(args.mcp_url)
    except ValidationError as error:
        parser.error(error_validacion(error))
    except ValueError as error:
        parser.error(str(error))
    modelo = ChatOpenAI(model=nombre, api_key=clave,
                        base_url=os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1",
                        use_responses_api=False, timeout=45, max_retries=0)
    carpeta = args.evidencias / uuid4().hex
    trazas = Trazas(carpeta, "modelo_real", nombre, secretos=(clave, os.getenv("LANGSMITH_API_KEY", "")))
    sesion = Sesion(modelo, url, trazas)
    try:
        asyncio.run(interactuar(sesion, contexto))
    except KeyboardInterrupt:
        print("\nSesión cerrada.")


if __name__ == "__main__":
    main()
