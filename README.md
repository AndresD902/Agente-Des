# Agente DES para una oficina de atención estudiantil

El agente compara **1, 2 y 3 puestos** con una única fila FIFO. Evalúa un lote finito que empieza vacío, con la primera llegada en el minuto cero. Todas las personas son atendidas. La simulación termina con la última salida. Los tiempos se expresan en minutos.

El escenario inicial usa 20 personas, intervalos entre llegadas exponenciales con media de 2 minutos, servicio triangular con mínimo 1, moda 3 y máximo 5, 30 réplicas y semilla base 2026. La meta inicial de espera en fila es de 1 minuto. La media exponencial parametriza intervalos aleatorios y la moda triangular es el tiempo de servicio más probable. También se admite el servicio uniforme continuo, determinado por un mínimo y un máximo. Las medias y los límites deben ser positivos y finitos, con `mínimo < moda < máximo` para la triangular y `mínimo < máximo` para la uniforme.

Python selecciona la menor capacidad cuya espera media de todas las réplicas sea **menor o igual** a la meta. Devuelve `None` cuando las tres capacidades son insuficientes. La espera en fila excluye el tiempo de servicio. Cada comparación informa la última salida media y la desviación estándar muestral de las esperas medias entre réplicas.

La ampliación presentada es **C, política dinámica**. Un middleware filtra `registrar_decision` según el rol, la disponibilidad de una recomendación vigente y el estado del registro. Consultar y evaluar están disponibles para ambos roles. La herramienta conserva su propia validación de permisos y resultados.

## Integrantes

| Integrante | Nombre | Contribución concreta |
| --- | --- | --- |
| 1 | Por completar por la pareja | Por completar con el trabajo realizado |
| 2 | Por completar por la pareja | Por completar con el trabajo realizado |

## Instalación en Windows

Se usó **CPython 3.13.17 de 64 bits**. Desde la carpeta raíz, en la terminal PowerShell de VS Code, ejecuta los siguientes comandos. El archivo de requisitos fija tanto las dependencias directas como las transitivas.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
Copy-Item .env.example .env
```

Edita `.env` localmente. Usa un modelo con soporte de llamadas a herramientas por Chat Completions y disponible para tu cuenta. Conserva `.env` fuera de la entrega.

| Variable | Uso |
| --- | --- |
| `OPENAI_API_KEY` | Clave del proveedor para el modo real. |
| `OPENAI_MODEL` | Identificador exacto del modelo contratado. |
| `OPENAI_BASE_URL` | Opcional. URL de un proveedor compatible. Vacío usa OpenAI. |
| `DES_MCP_PORT` | Puerto en el que escucha el proceso local de MCP. Valor de ejemplo `8765`. |
| `DES_MCP_URL` | URL del cliente MCP. Valor de ejemplo `http://127.0.0.1:8765/mcp`. |
| `DES_ROL` | Rol inicial `observador` u `operador`. |
| `DES_META` | Meta inicial en minutos. Usar punto decimal. |
| `DES_EVIDENCIAS` | Carpeta base de las trazas de la CLI. Usa `evidencias/local` por defecto. |

El arranque del servidor, la instalación y las pruebas no llaman a la API del modelo. En la CLI real, los turnos en lenguaje natural y el cierre conversacional tras aprobar o editar pueden consumir cuota. `/estado` y `/meta` operan localmente sobre el estado. El agente admite hasta 6 llamadas al modelo por invocación del grafo. Configura 45 segundos de espera por solicitud del SDK, sin reintentos automáticos, y 15 segundos para una evaluación MCP. Ante un fallo del proveedor, muestra un mensaje y permite un nuevo turno.

## Inicio y uso

En la primera terminal inicia MCP. El servidor escucha en la interfaz local.

```powershell
.\.venv\Scripts\python.exe servidor_mcp.py
```

En la segunda terminal inicia el agente. `--rol` y `--meta` prevalecen sobre `.env`.

```powershell
.\.venv\Scripts\python.exe main.py --rol operador --meta 1
```

Dentro del agente, puedes evaluar, continuar y pedir un registro. Escribe cada línea por separado y espera la respuesta de cada turno.

```text
Evalúa el escenario inicial de la evaluación y compara las capacidades.
Ahora usa un servicio uniforme entre 1 y 3 minutos; conserva los demás datos.
Registra la capacidad recomendada con la nota «Propuesta para la oficina estudiantil».
```

En la pausa, la terminal muestra la acción, la capacidad, la nota, la meta y el escenario. Usa **uno** de `/aprobar`, `/editar Propuesta revisada para la oficina` o `/rechazar`. La edición aplica la nota revisada a la propuesta validada. El rechazo conserva la evaluación. Usa `/estado` para confirmar el resultado. Para un escenario sin capacidad factible, el registro queda bloqueado.

`/nuevo observador` abre un hilo aislado desde la aplicación. `/hilos` lista los identificadores y las pausas. `/usar ID` retoma el hilo indicado dentro del mismo proceso. `/meta 2` ajusta la meta del hilo y recalcula la recomendación con las réplicas vigentes. Para cerrar la CLI usa `/salir` o `Ctrl+C`. Para detener MCP pulsa `Ctrl+C` en la primera terminal.

Puedes definir un escenario desde cero con una solicitud como «Evalúa 40 personas, llegadas exponenciales con media 2,5 minutos, servicio triangular con mínimo 1, moda 2 y máximo 4 minutos, 60 réplicas y semilla 123». Se admiten entre 1 y 100 personas, entre 30 y 100 réplicas y semillas enteras no negativas. En un hilo existente puedes indicar un cambio puntual como «Conserva el escenario y usa 50 réplicas y la semilla 30». Si faltan datos en un hilo nuevo o la petición es ambigua, el agente solicita aclaración.

## Pruebas y conversaciones

Ejecuta las pruebas sin clave. Estas arrancan su propio servidor MCP en un puerto local libre. `--basetemp` dirige los temporales a una subcarpeta de pruebas del workspace.

```powershell
New-Item -ItemType Directory -Force .pytest_cache | Out-Null
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest_cache/temporales
```

Para reproducir los archivos de verificación en una carpeta local, ejecuta lo siguiente.

```powershell
New-Item -ItemType Directory -Force .pytest_cache | Out-Null
$desEvidenciaPruebas = "evidencias/local/pruebas-$([guid]::NewGuid().ToString('N'))"
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest_cache/temporales --evidencias $desEvidenciaPruebas --junitxml "$desEvidenciaPruebas/pytest.xml"
```

Las pruebas de simulación y reglas ejecutan Python directamente. El modelo de ensayo emite llamadas guionadas para probar el grafo, el middleware, el control de roles, la CLI y la revisión humana. El servidor MCP que recibe esas llamadas es real. Una prueba adicional usa un transporte HTTP de ensayo para comprobar que el adaptador serializa los esquemas y los identificadores de llamadas. La interpretación libre de solicitudes se verifica con las conversaciones del modelo real.

Con el proveedor configurado y MCP iniciado, reproduce las dos conversaciones en sesiones separadas. Usa solo datos sintéticos y conserva la carpeta que imprime la CLI.

| Conversación | Inicio | Turnos y evidencia esperada |
| --- | --- | --- |
| Evaluación y registro | `main.py --rol operador --meta 1 --evidencias evidencias/api/aprobacion` | Solicita evaluar el escenario inicial. En el segundo turno pide registrar la capacidad recomendada. Revisa la propuesta y escribe `/aprobar`. La traza debe enlazar el resultado MCP, la pausa, la aprobación y la decisión del mismo hilo. |
| Continuación | `main.py --rol observador --meta 1 --evidencias evidencias/api/continuacion` | Solicita evaluar el escenario inicial. En el mismo hilo escribe «Ahora usa un servicio uniforme entre 1 y 3 minutos; conserva los demás datos». La traza debe mostrar dos llamadas MCP y las mismas muestras de llegadas. |

En PowerShell, antepone `.\.venv\Scripts\python.exe` al inicio indicado. Los resultados esperados y obtenidos de P1–P14, las rutas y el estado de las conversaciones reales se encuentran en [la tabla de verificación](evidencias/verificacion.md).

## Evidencia y limitaciones

Cada sesión guarda `eventos.jsonl` con el origen de la ejecución, los identificadores de hilo, turno y herramienta, el recurso MCP consultado, los parámetros, el resultado de cada herramienta, las interrupciones y el resumen del estado. Cada `resultados/*.json` incluye muestras, semillas, esperas individuales, indicadores por réplica y agregados. Los resultados de un turno se vinculan mediante `archivo_resultados`, relativo a la carpeta de la sesión. `.gitignore` excluye `.env`, entornos, cachés y `evidencias/local`. La entrega debe contener únicamente trazas sintéticas revisadas.

La memoria y las pausas se pierden al cerrar el agente. Los archivos de trazas permanecen y sirven para auditoría. El rol es una configuración de esta aplicación local y no una identidad autenticada. Los tiempos se calculan en doble precisión. Configuraciones extremas cuyo reloj desborde el rango representable se rechazan con un error de evaluación.

## Explicación técnica

`modelos.py` valida los parámetros y `muestreo.py` construye los flujos aleatorios. `simulacion.py` ejecuta SimPy y `estadisticas.py` agrega las corridas. `servidor_mcp.py` devuelve el resultado estructurado. `cliente_mcp.py` descubre la herramienta, lee `des://escenario/supuestos` y solicita la simulación por Streamable HTTP. La aplicación entrega al modelo los agregados y la ruta local al detalle. `decision.py` aplica la regla sobre los promedios sin redondear. La CLI formatea los valores calculados por Python.

El **estado** contiene el escenario, el resultado, su referencia, la recomendación y la decisión. El **contexto** contiene el rol, la meta y el límite de personas suministrados por la aplicación. El **historial** contiene los mensajes del usuario, el modelo y las herramientas. `Command` actualiza el estado y adjunta un `ToolMessage` con el identificador de la llamada. El checkpointer en memoria usa `thread_id` para restaurar el estado y el historial de cada hilo durante la sesión. Un sistema con usuarios debe derivar el rol de una identidad autenticada y controlar la propiedad de los hilos.

El modelo interpreta intenciones, solicita datos y decide qué herramienta llamar. Python valida tipos y rangos, verifica el resultado MCP, elige la capacidad y controla el registro. Una configuración nueva invalida resultados y decisiones antes de volver a simular. Si cambia solo la meta, se conservan las réplicas, se recalcula la recomendación y se invalida la decisión anterior. `HumanInTheLoopMiddleware` pausa la acción antes del registro y `Command(resume=...)` aplica una elección explícita al hilo de la pausa. Antes de registrar se verifica que la propuesta siga coincidiendo con el escenario, los resultados, el rol y la meta.

En la réplica `r` las semillas son `semilla_base + 2*r` para llegadas y `semilla_base + 2*r + 1` para servicios. Cada flujo usa su propio `random.Random`. El generador exponencial recibe la tasa `1 / media` cuando es representable. Las tres capacidades consumen las mismas muestras pregeneradas, en el mismo orden de llegada. Una sola corrida no permite estimar la variación entre réplicas. La desviación estándar usa `R - 1`. El estudio representa un lote finito y no requiere periodo de calentamiento. Una espera media compatible con la meta es una estimación y las esperas individuales o de otras corridas pueden superarla.

## Fuentes y procedencia

- Se implementaron módulos propios. Los notebooks del curso no estaban presentes en el workspace y no se reutilizaron archivos del curso.
- Se consultó la documentación oficial de las bibliotecas. [SimPy](https://simpy.readthedocs.io/en/latest/topical_guides/resources.html), [SDK de MCP](https://py.sdk.modelcontextprotocol.io/), [LangChain](https://docs.langchain.com/oss/python/langchain/agents), [LangGraph](https://docs.langchain.com/oss/python/langgraph/interrupts)
- Se utilizó Codex para analizar el enunciado, implementar el proyecto y ejecutar las verificaciones documentadas. Cada integrante debe revisar la implementación antes de la sustentación.
- Para una entrega por GitHub, acompaña el enlace con la rama y el identificador del commit evaluable. Si la entrega es privada, habilita acceso al docente. Para ZIP, usa `evaluacion_agente_apellido1_apellido2.zip` con una carpeta raíz del proyecto.
