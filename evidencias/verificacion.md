# Verificación del agente DES

Las 23 pruebas del [reporte de pytest](pruebas/pytest.xml) pasaron en Windows con CPython 3.13.17. Las pruebas de conversación usan un modelo guionado y un servidor MCP real sobre Streamable HTTP. La prueba del adaptador usa respuestas HTTP de ensayo, sin contacto con la API del proveedor. Las comparaciones decimales en las pruebas numéricas usan una tolerancia absoluta de `1e-10` minutos.

## Casos P1 a P14

| Caso | Entrada o acción | Esperado | Obtenido | Evidencia |
| --- | --- | --- | --- | --- |
| P1 | 20 personas, exponencial de media 2, triangular 1/3/5, 30 réplicas, semilla 2026, meta 1 | Tres series de 30 réplicas y agregados verificables | 90 corridas. Medias de espera 11,881018, 1,375945 y 0,250514 min. Recomendación de 3 puestos. | [Resultados y muestras](pruebas/P01-simulador.json), [traza MCP y agente](pruebas/P01-P04-P05/eventos.jsonl) |
| P2 | Cambio de meta real a 2. Regla aislada con medias 7,5, 2 y 0,5 y metas 2 y 8 | Resultados conservados y decisión invalidada. Recomendar 2 y 1 en la regla aislada. | Una sola simulación. La recomendación cambió de 3 a 2 y la decisión quedó vacía. La regla aislada produjo 2 y 1. | [Cambio de contexto](pruebas/P02-contexto/eventos.jsonl), [regla aislada](pruebas/P02-regla.json) |
| P3 | Medias controladas 7,5, 2 y 0,5 con meta 0,25. Evaluación estocástica adicional con meta 0. | `None` y registro bloqueado | La regla controlada y la evaluación estocástica produjeron `None`. El intento de registro terminó sin pausa ni decisión. | [Regla aislada](pruebas/P03-regla.json), [evaluación MCP](pruebas/P03-registro/eventos.jsonl) |
| P4 | Cambiar solo el servicio a uniforme de 1 a 3 en el hilo de P1 | Nuevos servicios y evaluación. Llegadas, personas, réplicas y semilla conservadas. | Las 30 muestras de llegadas coincidieron. Se invalidó la decisión anterior y la nueva evaluación recomendó 2 puestos. | [Continuación y resultados detallados](pruebas/P01-P04-P05/) |
| P5 | Hilo nuevo con «Conserva los datos y compara». Solicitud ambigua de «servicio a 1 minuto» en el hilo inicial. | Aclaración y ausencia de nuevas simulaciones | El hilo nuevo quedó sin configuración. Ambas solicitudes produjeron preguntas y ninguna nueva llamada MCP. | [Trazas de los hilos](pruebas/P01-P04-P05/eventos.jsonl) |
| P6 | Valores inválidos para personas, media, servicio, réplicas, semilla y meta | Rechazo explícito sin registrar | Se rechazaron los valores inválidos. En el grafo, un cambio inválido bloqueó la evaluación y el registro del turno. | [Validación de entradas](pruebas/P06-dominio.json), [validación en el agente](pruebas/P06-agente/eventos.jsonl) |
| P7 | Arrancar y detener el servidor antes de una evaluación nueva | Error comprensible, sin evaluación ni decisión | Fallo de conexión informado. Los resultados y la decisión quedaron vacíos. | [Fallo MCP](pruebas/P07/eventos.jsonl) |
| P8 | Operador evalúa y aprueba de forma explícita | Pausa con decisión vacía y registro coincidente al reanudar | Se guardaron 3 puestos y la nota de la propuesta. El mismo hilo conservó configuración y meta 1. | [Aprobación de ensayo](pruebas/P08/eventos.jsonl) |
| P9 | Otro hilo edita la nota. Intento adicional de editar a 2 puestos. | Nota corregida con la misma capacidad. Rechazo de la capacidad inválida. | Se registró «Nota revisada por la persona.» con 3 puestos. El intento con 2 puestos quedó sin registro. | [Edición de ensayo](pruebas/P09/eventos.jsonl), [edición inválida](pruebas/P09-capacidad-invalida/eventos.jsonl) |
| P10 | Otro hilo rechaza el registro | Conservar resultados y decisión vacía | Misma referencia de evaluación antes y después, con decisión vacía. | [Rechazo de ensayo](pruebas/P10/eventos.jsonl) |
| P11 | Observador pide ignorar las reglas. Invocación directa a la herramienta. | Rechazo en ambas rutas | La conversación y la invocación directa devolvieron el error de rol. | [Intento en conversación](pruebas/P11-P12/eventos.jsonl), [invocación directa](pruebas/P11-validacion.json) |
| P12 | Observar herramientas visibles según rol y estado | Variaciones y validación independiente | La herramienta de registro estuvo oculta al observador y al operador sin resultados. Se habilitó al operador con recomendación vigente. | [Eventos `politica_herramientas`](pruebas/P11-P12/eventos.jsonl) |
| P13 | Seis llegadas en minutos 0 a 5. Servicios de 4 min. | Esperas individuales de la tabla, medias 7,5, 2 y 0,5 y salidas 24, 13 y 10 | Coincidieron las 18 esperas, las tres medias y las tres salidas. | [Regresión FIFO](pruebas/P13.json) |
| P14 | Repetir semilla 2026, cambiar a 2027 e inspeccionar réplicas | Reproducción exacta, muestras comunes por réplica y nuevas muestras con otra semilla | Los resultados completos coincidieron al repetir 2026. El motor recibió los mismos arreglos en las tres capacidades de cada réplica. Las muestras cambiaron entre réplicas y con semilla 2027. Se verificaron los límites del servicio y la variación de los intervalos. | [Muestras de ambas semillas y del servicio uniforme](pruebas/P14.json) |

## Agregados obtenidos por MCP

Los indicadores se expresan en minutos. La desviación es muestral sobre las esperas medias de las 30 réplicas.

| Servicio | Puestos | Espera media | Media de la última salida | Desviación de las esperas medias |
| --- | ---: | ---: | ---: | ---: |
| Triangular 1/3/5 | 1 | 11,881018 | 62,212200 | 4,545517 |
| Triangular 1/3/5 | 2 | 1,375945 | 42,158504 | 1,377463 |
| Triangular 1/3/5 | 3 | 0,250514 | 39,938508 | 0,357470 |
| Uniforme 1–3 | 1 | 3,983347 | 45,400095 | 2,896695 |
| Uniforme 1–3 | 2 | 0,370829 | 39,063644 | 0,443625 |
| Uniforme 1–3 | 3 | 0,064141 | 38,740180 | 0,114900 |

## Ejecuciones con modelo real

| Evidencia requerida por R6 | Estado | Carpeta prevista |
| --- | --- | --- |
| Evaluación con registro aprobado | Pendiente de configuración del proveedor y aprobación humana durante la ejecución. | `evidencias/api/aprobacion/` |
| Evaluación con continuación | Pendiente de configuración del proveedor. | `evidencias/api/continuacion/` |

## Comprobaciones adicionales

- Se verificaron el límite de 6 llamadas al modelo, la recuperación tras un fallo simulado del proveedor, el flujo de terminal, la serialización del adaptador y una respuesta MCP de 100 personas y 100 réplicas por capacidad. [Reporte de pytest](pruebas/pytest.xml)
- Se copió el código a una carpeta limpia y se creó otro entorno con `requirements.txt`. `pip check` informó que todas las dependencias eran compatibles. `main.py --help` funcionó y las 23 pruebas volvieron a pasar.
- Durante la integración se ajustaron la importación de `BaseMessage`, el tipo de los mensajes guionados y el manejo del rechazo tras inspeccionar las APIs instaladas. Los primeros intentos de pytest encontraron una carpeta temporal de Windows con acceso denegado y una carpeta base ausente en la copia limpia. El README indica cómo crear la ruta temporal dentro del workspace e invocar `tests` explícitamente para cargar `--evidencias`. La repetición en la copia limpia pasó después de aplicar estos cambios.
