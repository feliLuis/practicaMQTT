# Práctica MQTT — Objeto inteligente con MQTT y MCP (SIS-234)

## Integrantes
- _Nombre 1_ — usuario GitHub: `...`
- _Nombre 2_ — usuario GitHub: `...`
- _Nombre 3 (si aplica)_ — usuario GitHub: `...`

## Descripción
ESP32 con sensor ultrasónico HC-SR04 y 3 LEDs (rojo, verde, amarillo). Todo se comunica a través de un broker MQTT en la nube (HiveMQ):

```
ESP32 <--> broker.hivemq.com <--> App móvil (IoT MQTT Panel)
                  ^
                  +-------------> Servidor MCP <--> Claude Desktop
```

## Tópicos MQTT y mensajes
Prefijo del grupo: `sis234/grupoN` _(reemplazar)_

| Tópico | Publica | Se suscribe | Mensaje |
|---|---|---|---|
| `sis234/grupoN/distancia` | ESP32 | App, servidor MCP | `{"cm": 42.7}` |
| `sis234/grupoN/actuadores/cmd` | App, servidor MCP | ESP32 | `{"led":"rojo","estado":"on"}` |

## Herramientas MCP
| Herramienta | Parámetros | Propósito |
|---|---|---|
| `get_distance` | — | Última distancia (cm) y su antigüedad |
| `set_led` | `color`, `state` | Enciende/apaga un LED |
| `only_led` | `color` | Enciende solo ese LED y apaga los demás |
| `all_leds_on` / `all_leds_off` | — | Todos los LEDs |
| `move_servo` | `angle` | Solo con `SERVO_ENABLED=true` |
| `get_system_status` | — | Estado del broker y del sensor |

## Requerimientos no funcionales (valores medidos)
| Atributo | Valor declarado | Cómo se verificó |
|---|---|---|
| Rango de trabajo | _… cm a … cm_ | |
| Estabilidad | _… minutos sin reinicios_ | |
| Exactitud | _error máx. ± … cm_ | Cinta métrica |
| Tiempo de respuesta | _≤ … s_ | App → broker → ESP32 |
| Frecuencia de publicación | _… lecturas/s_ | |
| Reconexión | Automática (Wi-Fi y MQTT) | Se apagó y encendió el hotspot |

## Cómo ejecutar
1. **Firmware:** en `firmware/`, copiar `include/config.example.h` a `include/config.h`, completar Wi-Fi y `TOPIC_PREFIX`, y ejecutar `pio run --target upload`.
2. **Servidor MCP:** en `mcp-server/`, `uv sync`, copiar `.env.example` a `.env` (poner `TOPIC_PREFIX`).
3. **Claude Desktop:** agregar `config/claude_desktop_config.example.json` a `claude_desktop_config.json` (ruta absoluta) y reiniciar.
4. **App móvil:** importar/crear el panel descrito en `config/`.

Más detalle en `docs/GUIA_IMPLEMENTACION.md`.
