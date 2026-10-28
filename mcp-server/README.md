# Servidor MCP — Objeto inteligente (SIS-234)

Puente entre Claude Desktop (u otra herramienta de IA) y el ESP32 mediante MQTT.

## Herramientas MCP

| Herramienta | Parámetros | Propósito |
|---|---|---|
| `get_distance` | — | Última distancia (cm) medida por el sensor ultrasónico y su antigüedad |
| `set_led` | `color`, `state` (`on`/`off`) | Enciende o apaga un LED sin tocar los demás |
| `only_led` | `color` | Enciende solo ese LED y apaga los demás |
| `all_leds_on` / `all_leds_off` | — | Enciende / apaga todos los LEDs |
| `move_servo` | `angle` (0–180) | Mueve el servo (solo si `SERVO_ENABLED=true`) |
| `get_system_status` | — | Estado del broker y de la última lectura |

## Tópicos y mensajes

| Tópico | Publica | Mensaje |
|---|---|---|
| `<TOPIC_PREFIX>/distancia` | ESP32 | `{"cm": 42.7}` |
| `<TOPIC_PREFIX>/actuadores/cmd` | App móvil, servidor MCP | `{"led":"rojo","estado":"on"}` · `{"servo":90}` |

## Ejecución

```powershell
uv sync
copy .env.example .env      # y editar TOPIC_PREFIX
uv run python simulate_esp32.py --prefix sis234/grupoN   # opcional: probar sin hardware
```

Luego registrar el servidor en Claude Desktop con `../config/claude_desktop_config.example.json`
y reiniciar la aplicación.
