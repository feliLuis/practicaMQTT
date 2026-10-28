# Guía de implementación — Práctica MQTT + MCP (SIS-234)

**Entrega: jueves 29/10/2026, 17:45 — enlace del repositorio GitHub por el LMS-UCB.**

---

## 0. El contrato (todos los componentes deben respetarlo)

Prefijo único del grupo: `sis234/grupoN` (cámbienlo por el suyo, p. ej. `sis234/grupo3`).

| Tópico | Publica | Se suscribe | Mensaje |
|---|---|---|---|
| `sis234/grupoN/distancia` | ESP32 | App, servidor MCP | `{"cm": 42.7}` |
| `sis234/grupoN/actuadores/cmd` | App, servidor MCP | ESP32 | `{"led":"rojo","estado":"on"}` o `{"servo":90}` |

Reglas del firmware para los comandos: `led` ∈ {`rojo`,`verde`,`amarillo`}, `estado` ∈ {`on`,`off`}; `servo` es un entero 0–180. Cada mensaje cambia **un** actuador (el servidor MCP envía varios mensajes seguidos para "enciende el rojo y apaga los demás").

---

## 1. Servidor MCP (ya está hecho)

Carpeta `mcp-server/`. Pasos:

1. Instalar `uv` (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` y reiniciar la terminal.
2. En `mcp-server/`: `uv sync`
3. Copiar `.env.example` a `.env` y poner su `TOPIC_PREFIX`. Si usan servo: `SERVO_ENABLED=true`.
4. **Probar sin hardware**: en una terminal `uv run python simulate_esp32.py --prefix sis234/grupoN`. Publica distancias falsas y muestra los comandos que llegan.
5. Registrar en Claude Desktop: abrir `%APPDATA%\Claude\claude_desktop_config.json` y copiar el contenido de `config/claude_desktop_config.example.json`, con la **ruta absoluta** de `mcp-server` (usar `/` o `\\`). Si falla, poner la ruta completa de `uv` (`where uv`) en `command`. Reiniciar Claude Desktop.
6. Verificar en el menú "+" → Conectores que aparece `smart-object`, y preguntar: *"¿A qué distancia está el objeto?"* (debe responder con los datos del simulador) y *"Enciende el LED rojo y apaga los demás"* (el simulador muestra 3 comandos).
7. Si algo falla, los logs están en `%APPDATA%\Claude\logs\mcp-server-smart-object.log`.

---

## 2. Circuito del objeto inteligente

| Componente | Conexión al ESP32 |
|---|---|
| HC-SR04 VCC / GND | 5V (pin VIN) / GND |
| HC-SR04 TRIG | GPIO 5 |
| HC-SR04 ECHO | **divisor de voltaje** → GPIO 18 |
| LED rojo, verde, amarillo | GPIO 25, 26, 27, cada uno con resistencia de 220 Ω a GND |
| (Servo opcional) señal | GPIO 13; alimentar a 5V |

**Divisor para ECHO:** ECHO → resistencia 1 kΩ → nodo (a GPIO 18) → resistencia 2 kΩ → GND. El ECHO entrega 5 V y el ESP32 tolera 3,3 V: sin divisor puede dañarse el pin. Evitar GPIO 6–11.

---

## 3. Firmware del ESP32 (carpeta `firmware/`, ya incluido)

| Archivo | Clase / rol |
|---|---|
| `src/main.cpp` | Solo orquesta: `setup()` y `loop()` |
| `src/UltrasonicSensor` | Mide con HC-SR04; mediana de 3 lecturas; descarta lecturas inválidas |
| `src/ActuatorController` | LEDs por color (+ servo opcional); interpreta los comandos JSON |
| `src/WifiManager` | Reconexión Wi-Fi no bloqueante |
| `src/MqttManager` | Conexión/reconexión MQTT, suscripción a comandos (QoS 1), publicación |
| `include/config.example.h` | Plantilla de configuración (copiar como `config.h`, que está en `.gitignore`) |

Pasos:
1. Instalar PlatformIO (extensión de VS Code) y abrir la carpeta `firmware/`.
2. Copiar `include/config.example.h` a `include/config.h` y completar Wi-Fi, `TOPIC_PREFIX` y pines.
3. `pio run` (compilar). Si hay errores, corregirlos: este código **no fue compilado** al entregarlo.
4. `pio run --target upload` y `pio device monitor` para ver los logs.
5. Distancia: `cm = duración_µs × 0,0343 / 2` con timeout; publicación cada 250 ms (~4 lecturas/s).
6. Si usan servo: `ENABLE_SERVO 1` en `config.h` y descomentar `ESP32Servo` en `platformio.ini`.

---

## 4. App móvil (IoT MQTT Panel)

1. Crear conexión: broker `broker.hivemq.com`, puerto `1883`, sin usuario.
2. Panel con:
   - **Gauge** o **Line graph** suscrito a `sis234/grupoN/distancia` (rango 0–200 cm). Si su versión permite leer JSON (opción tipo "Payload is JSON" con la clave `cm`), úsenla; si no, hagan que el firmware publique además el número solo en `sis234/grupoN/distancia/valor`.
   - **Un switch por LED** (rojo, verde, amarillo) que publique en `sis234/grupoN/actuadores/cmd` con payload ON `{"led":"rojo","estado":"on"}` y OFF `{"led":"rojo","estado":"off"}`.
   - (Servo: un slider que publique `{"servo":90}` — según permita la app).
3. Exportar la configuración del panel y guardarla en `config/` del repo.

---

## 5. Pruebas y requerimientos no funcionales

Midan y anoten valores reales; van en el README y se verifican en la Demo.

| Atributo | Referencia | Cómo medirlo | Valor obtenido |
|---|---|---|---|
| Estabilidad | ≥ 10 min | Dejar corriendo, sin reinicios (ver monitor serie) | |
| Exactitud | ≤ ±3 cm | Cinta métrica a 10, 20, 50, 100 cm; anotar error en cada punto | |
| Tiempo de respuesta | ≤ 1 s | Video del teléfono: pulsar switch → LED cambia | |
| Frecuencia | ≥ 2 lect./s | Contar mensajes en 10 s desde la app o el log | |
| Reconexión | automática | Apagar y encender el hotspot Wi-Fi; verificar que vuelve a publicar solo | |

Declaren también el **rango de trabajo** (p. ej. 5–150 cm).

---

## 6. Repositorio GitHub

```
repo/
├── firmware/            # código del ESP32 + include/config.example.h
├── mcp-server/          # servidor MCP (smart-object.py, pyproject.toml, .env.example, simulador)
├── config/              # claude_desktop_config.example.json + export del panel de la app
├── README.md            # integrantes, tópicos, herramientas MCP, valores NF, cómo ejecutar
└── .gitignore           # .env, config.h, .venv/, .pio/, __pycache__/
```

- **Cada integrante hace commits con su propia cuenta de GitHub**, desde hoy y con mensajes claros (p. ej. `feat: medición ultrasónica con mediana`). La defensa individual (50 % de la nota) usa ese historial.
- Antes de subir: buscar contraseñas Wi-Fi o credenciales en los archivos (`git grep -i password`).
- Compartir el repositorio con el docente o ponerlo público y **verificar que el enlace abre sin iniciar sesión**.

---

## 7. Plan sugerido hasta la entrega

1. Hoy: crear el repo, subir el servidor MCP, probarlo con el simulador y Claude Desktop (1 h).
2. Hoy: armar el circuito y hacer el firmware de medición + publicación; verificar en la app (2–3 h).
3. Hoy/mañana temprano: comandos de LEDs en el firmware, panel de la app, pruebas con Claude Desktop con el hardware real.
4. Mañana (antes del mediodía): medir los requerimientos no funcionales, redactar el README, revisar commits de ambos.
5. Mañana: enviar el enlace por el LMS **con margen antes de las 17:45** y ensayar la demo completa.

## 8. Preparación de la defensa (ambos deben poder responder)

- ¿Qué es QoS y cuál usaron en cada caso? (suscripción de distancia QoS 0, comandos QoS 1 en el servidor MCP)
- ¿Por qué el ECHO necesita divisor de voltaje?
- ¿Cómo se calcula la distancia a partir del tiempo del eco?
- ¿Qué pasa si se cae el Wi-Fi? ¿Cómo se reconecta el ESP32 y el servidor MCP?
- ¿Qué es MCP, qué hace una "herramienta" y cómo decide Claude cuál usar?
- ¿Por qué no se usa `print()` en el servidor MCP? (stdio transporta el protocolo)
- ¿Por qué ningún componente habla directo con el ESP32? (modelo pub/sub desacoplado vía broker)
