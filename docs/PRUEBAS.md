# Pruebas

**Honestidad sobre el estado:** lo marcado ✅ fue ejecutado al preparar el proyecto (en un entorno sin hardware, sin AWS y sin PlatformIO). Lo marcado ⬜ **requiere tu hardware/cuenta** y no ha sido ejecutado. El firmware **no fue compilado**.

## A. Pruebas automáticas (servidor MCP)

```bash
cd mcp-server
python -m unittest discover -s tests -v      # o: uv run python -m unittest discover -s tests -v
```

| Área | Qué verifica | Estado |
|---|---|---|
| Lectura de distancia | JSON, número suelto, valores inválidos | ✅ 25 pruebas OK |
| Reconexión | Tras `disconnect` → `connect` se vuelve a suscribir a todos los tópicos | ✅ |
| Publicación | Formato JSON, tópico, QoS 1, error si no hay conexión, código de error | ✅ |
| Comandos | `enviado` ≠ `confirmado`; el reporte viejo no confirma; estado erróneo no confirma; confirmación individual por LED | ✅ |
| Device Shadow | `get/accepted`, timeout, `rejected`, Shadow deshabilitado | ✅ |
| Herramientas MCP | Validación de color/estado y formato de respuestas, con un servidor MCP simulado | ✅ |
| Con el SDK `mcp` y `paho-mqtt` reales + AWS | ⬜ Pendiente (ver C) |

## B. Compilar el firmware
```bash
cd firmware
cp include/config.example.h include/config.h                       # completa WiFi
cp include/aws_certificates.example.h include/aws_certificates.h   # pega los 3 PEM
pio run                 # ⬜ compilar (pégame los errores si aparecen)
pio run -t upload
pio device monitor
```

## C. Pruebas con hardware y AWS (⬜ todas pendientes)

| ID | Prueba | Pasos | Resultado esperado |
|---|---|---|---|
| T1 | Hora y TLS | Arrancar con WiFi | `[NTP] Hora valida` y luego `[MQTT] Conectado a AWS IoT Core` |
| T2 | Suscripciones | Ver el monitor | 4 líneas `Suscripcion ...: ok` |
| T3 | Publicación de distancia | Consola AWS → MQTT test client → suscribir `sis234/esp32/distancia` | `{"cm":...}` ~2,5 veces/s; cambia al mover un objeto |
| T4 | Comando directo | Publicar `{"led":"rojo","estado":"on"}` en `sis234/esp32/comandos` | LED rojo enciende; en el monitor `[ACT] LED rojo -> ON` |
| T5 | Verde, amarillo y `off` | Repetir | Cada LED responde; `off` apaga |
| T6 | Comando inválido | `{"led":"azul","estado":"on"}`, `{"led":"rojo","estado":"quizas"}`, `basura` | Mensaje de error en el monitor; **ningún LED cambia** |
| T7 | Shadow tras comando | Tras T4 suscribir `$aws/things/esp32-sis234/shadow/#` | Aparece `update` con `reported` y `desired` iguales; **sin** `delta` |
| T8 | Shadow delta | Consola → Shadow → `desired.leds.amarillo = "on"` | `update/delta`; el LED amarillo enciende; `reported` se actualiza; el delta desaparece |
| T9 | Recuperación tras reinicio | Dejar un LED en `on`, pulsar EN/reset | Tras reconectar, el LED vuelve a su estado (`desired recuperado`) |
| T10 | Reconexión WiFi | Apagar el hotspot 20 s y encenderlo | `[WIFI] Conexion perdida` → reconecta sola → `[MQTT] Conectado` → se re-suscribe y vuelve a publicar |
| T11 | Reconexión MQTT | Mantener el WiFi pero quitar internet 30–60 s (hotspot del móvil con datos apagados, o desconectar el cable WAN del router) y restablecerlo | Tras el timeout de keep-alive: `Fallo`/reintentos cada 5 s y, al volver internet, `Conectado` + re-suscripción + `get` del Shadow, sin reiniciar |
| T12 | Servidor MCP arranca | `uv sync`, `uv run smart-object.py` (con certs/.env) | Log `Conectado a AWS IoT Core`; sin errores de política |
| T13 | MCP: distancia | Claude Desktop: "¿A qué distancia está el objeto?" | Valor en cm con antigüedad |
| T14 | MCP: LEDs | "Enciende el LED rojo y apaga los demás" | LED rojo solo; respuesta con `CONFIRMADO por el ESP32` |
| T15 | MCP: no confirmado | Apagar la ESP32 y repetir T14 | `enviado, SIN confirmar` y el aviso; **nunca** "confirmado" |
| T16 | MCP: Shadow | "Muestra el estado del Shadow" | `reported`, `desired` y `delta` |
| T17 | MCP: reconexión | Cortar el WiFi del PC unos segundos | Logs de desconexión y reconexión; las herramientas vuelven a funcionar |
| T18 | App móvil | Gauge se mueve; switches cambian LEDs | Ver `APP_MOVIL.md` |

## D. Requerimientos no funcionales (⬜ medir y declarar)

| Atributo | Referencia | Método | Resultado |
|---|---|---|---|
| Estabilidad | ≥ 10 min | Dejar corriendo; vigilar `[BOOT]` en el monitor (no debe repetirse) y `heap` en `[STATUS]` (no debe decrecer sin parar) | |
| Exactitud | ≤ ±3 cm | Cinta métrica a 10, 20, 50, 100 cm; anotar el error en cada punto | |
| Tiempo de respuesta | ≤ 1 s | Grabar el teléfono: pulsar switch → LED. (Medir con TLS y WiFi reales) | |
| Frecuencia | ≥ 2 lect./s | Contar mensajes de `distancia` en 10 s | |
| Reconexión | Automática | T10/T11 | |

Recuerda que las pruebas largas consumen la capa gratuita de mensajes (ver `AWS_CONFIGURACION.md §6`).

## E. Diagnóstico rápido

| Síntoma (monitor serie) | Causa probable |
|---|---|
| `[NTP]` nunca llega a "Hora valida" | Sin internet o NTP bloqueado; TLS no se intentará |
| `Fallo: estado=-2, TLS='...'` | Certificado/clave/CA mal pegados, hora incorrecta o endpoint equivocado |
| `estado=5` (no autorizado) | Client ID distinto del de la política |
| Conecta y se desconecta en bucle | Suscripción/publicación a un tópico **no autorizado** en la política |
| Conecta pero no llegan comandos | Falta `Receive` o `topicfilter` en la política |
| `Documento demasiado grande` / mensajes ignorados | Buffer `MQTT_BUFFER_SIZE` insuficiente |
| Lecturas inválidas constantes | ECHO sin eco: revisar TRIG/ECHO, divisor y alimentación 5 V |
