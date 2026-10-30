# Servidor MCP — AWS IoT Core

Puente entre Claude Desktop y el ESP32 mediante MQTT/TLS.

| Archivo | Rol |
|---|---|
| `smart-object.py` | Punto de entrada: declara las herramientas MCP |
| `aws_iot_bridge.py` | Cliente MQTT/TLS, estado, confirmación de comandos y Shadow (lógica comprobable) |
| `tests/test_bridge.py` | 25 pruebas sin red ni hardware |
| `.env.example` | Plantilla de configuración |
| `certs/` | Identidad TLS **propia del servidor** (no se sube a Git) |

## Herramientas

| Herramienta | Parámetros | Propósito |
|---|---|---|
| `get_distance` | — | Última distancia válida (cm) y su antigüedad |
| `get_system_status` | — | Conexión con AWS, antigüedad de la lectura y LEDs reportados |
| `set_led` | `color`, `state` | Un LED on/off; espera confirmación del ESP32 |
| `only_led` | `color` | Enciende ese LED y apaga los demás |
| `all_leds_on` / `all_leds_off` | — | Todos los LEDs |
| `get_shadow_state` | — | `reported`/`desired`/`delta` desde AWS (requiere permisos de Shadow) |

Las herramientas de LED responden **CONFIRMADO** solo si el ESP32 reportó el cambio después del envío; si no, **enviado, SIN confirmar**.

## Puesta en marcha

```bash
uv sync
cp .env.example .env            # ajusta si cambiaste algo
# copia a certs/: AmazonRootCA1.pem, mcp-certificate.pem.crt, mcp-private.pem.key
uv run python -m unittest discover -s tests     # pruebas
uv run smart-object.py                           # prueba manual (Ctrl+C para salir)
```
Luego registra el servidor en Claude Desktop con `../config/claude_desktop_config.example.json` y reinicia la app.
Logs de Claude Desktop (Windows): `%APPDATA%\Claude\logs\mcp-server-smart-object.log`.

Requiere Python ≥ 3.10 y el SDK `mcp` ≥ 2.0 (`MCPServer`; el código acepta también `FastMCP`).
No uses `print()`: stdout es el canal MCP.
