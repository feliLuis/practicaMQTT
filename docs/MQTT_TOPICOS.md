# Tópicos MQTT

Broker: AWS IoT Core (`ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com:8883`, TLS con certificado de cliente). AWS IoT solo admite QoS 0 y 1.

## Tópicos de aplicación

| Tópico | Publica | Se suscribe | Formato | QoS |
|---|---|---|---|---|
| `sis234/esp32/distancia` | ESP32 | Servidor MCP, App | `{"cm":42.7}` | 0 |
| `sis234/esp32/comandos` | Servidor MCP, App | ESP32 | `{"led":"rojo","estado":"on"}` | 1 |

Valores válidos de comando: `led` ∈ `rojo` \| `verde` \| `amarillo`; `estado` ∈ `on` \| `off`. Un comando inválido se ignora **sin tocar ningún GPIO**.

## Tópicos del Device Shadow clásico (`$aws/things/esp32-sis234/shadow/…`)

| Subtópico | Publica | Se suscribe | Uso |
|---|---|---|---|
| `update` | ESP32 | AWS | Reportar estado (y alinear `desired` tras un comando directo) |
| `update/accepted` | AWS | ESP32 (log), Servidor MCP (confirmación) | El servidor lo usa como **confirmación física** |
| `update/delta` | AWS | ESP32 | Diferencia `desired` ≠ `reported` |
| `get` | ESP32, Servidor MCP | AWS | Pedir el Shadow |
| `get/accepted` | AWS | ESP32, Servidor MCP | Respuesta con el estado |
| `update/rejected`, `get/rejected` | AWS | ESP32 (opcional) | Diagnóstico; requieren permisos extra |

## Quién necesita qué permiso

| Cliente | Client ID | Publish | Subscribe + Receive |
|---|---|---|---|
| ESP32 | `esp32-sis234` | distancia, shadow/update, shadow/get | comandos, shadow/update/delta, update/accepted, get/accepted |
| Servidor MCP | `mcp-sis234` | comandos, shadow/get | distancia, shadow/update/accepted, get/accepted |
| App móvil | `app-sis234` | comandos | distancia |

JSON de cada política en `config/policies/`. Cualquier cambio de tópico exige actualizar la política correspondiente.
