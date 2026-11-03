# Configuración en AWS IoT Core

> Este proyecto **no crea recursos en AWS**. Aquí se documenta qué verificar y qué crear a mano.
> Los nombres de menús de la consola pueden variar ligeramente; busca "Security → Policies / Certificates".

## 1. Recursos que ya tienes (no se tocan)

| Recurso | Valor |
|---|---|
| Región | `us-east-2` (Ohio) |
| Thing / Client ID de la ESP32 | `esp32-sis234` |
| Endpoint | `ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com` (puerto TLS `8883`) |
| Política de la ESP32 | `PoliticaESP32SIS234` |
| Shadow | clásico (sin nombre) |
| Archivos de la ESP32 | `certificate.pem`, `private.pem.key`, `public.pem.key`, `AmazonRootCA1.pem` |

El endpoint no es secreto, pero los certificados y claves **sí**. No los subas a Git ni los pegues en chats.

## 2. Verifica `PoliticaESP32SIS234` (sin modificarla)

El firmware usa exactamente estas operaciones. Compara con tu política (referencia en `config/policies/PoliticaESP32SIS234_referencia.json`):

| Acción | Recursos que debe permitir |
|---|---|
| `iot:Connect` | `client/esp32-sis234` |
| `iot:Publish` | `sis234/esp32/distancia`, `$aws/things/esp32-sis234/shadow/update`, `.../shadow/get` |
| `iot:Subscribe` | **topicfilter** de `sis234/esp32/comandos`, `.../shadow/update/delta`, `.../update/accepted`, `.../get/accepted` |
| `iot:Receive` | **topic** de esos mismos cuatro tópicos |

Detalles que suelen fallar:
- `Subscribe` usa el recurso `topicfilter/...` y `Receive` usa `topic/...`. Con solo uno de los dos no llegan mensajes.
- El Client ID del firmware (`AWS_CLIENT_ID`) debe coincidir con `client/esp32-sis234`.
- Si una acción no está permitida, AWS puede **cerrar la conexión** en lugar de ignorar la operación; en el monitor serie se verá un ciclo de conexión/desconexión.

### Permisos opcionales (solo si quieres ver los rechazos del Shadow)
El firmware puede suscribirse a `shadow/update/rejected` y `shadow/get/rejected` (útil para diagnosticar). **No están en tu política actual**, así que vienen desactivados (`SHADOW_SUBSCRIBE_REJECTED 0`). Para activarlos:
1. Añade las sentencias de `config/policies/ESP32_extra_rejected_opcional.json` a `PoliticaESP32SIS234` (crea una nueva versión de la política).
2. Pon `SHADOW_SUBSCRIBE_REJECTED 1` en `config.h` y vuelve a cargar el firmware.

Sin ellos todo funciona: si `get/accepted` no llega en 5 s, la ESP32 reporta igualmente su estado (esto también crea el Shadow la primera vez).

## 3. Identidad independiente para el servidor MCP

El servidor **no reutiliza** la clave de la ESP32. Crea otra identidad con permisos mínimos:

1. **Política:** Security → Policies → Create policy → modo JSON. Nombre sugerido `PoliticaServidorMCP`. Pega `config/policies/PoliticaServidorMCP.json` y reemplaza `<ACCOUNT_ID>` por tu ID de cuenta de 12 dígitos.
2. **Certificado:** Security → Certificates → Add certificate → *Create certificate* (generado por AWS). Descarga: certificado del dispositivo (`...-certificate.pem.crt`), clave privada (`...-private.pem.key`) y la CA raíz Amazon Root CA 1. **La clave privada solo se puede descargar en este momento.**
3. **Activa** el certificado y **adjunta** `PoliticaServidorMCP`.
4. (Opcional) Asócialo a un Thing nuevo, por ejemplo `mcp-sis234`. No es necesario: la política autoriza por Client ID, no por Thing.
5. Copia los archivos a `mcp-server/certs/` con los nombres:
   - `AmazonRootCA1.pem`, `mcp-certificate.pem.crt`, `mcp-private.pem.key`

| Acción de la política del servidor | Para qué |
|---|---|
| `Connect` a `client/mcp-sis234` | Conectarse (el Client ID es fijo: dos instancias iguales se expulsan entre sí) |
| `Publish` a `sis234/esp32/comandos` | Enviar comandos de LED |
| `Publish` a `shadow/get` | Herramienta `get_shadow_state` |
| `Subscribe`+`Receive` a `sis234/esp32/distancia` | `get_distance` |
| `Subscribe`+`Receive` a `shadow/update/accepted` | Confirmar que el ESP32 aplicó un cambio |
| `Subscribe`+`Receive` a `shadow/get/accepted` | `get_shadow_state` |

Si no quieres dar permisos de Shadow al servidor: pon `SHADOW_ENABLED=false` en `.env` y quita esas sentencias. Entonces los comandos quedarán como "enviados, sin confirmar".

## 4. Identidad para la app móvil

Mismo procedimiento, con otro certificado, el Client ID `app-sis234` y la política `config/policies/PoliticaAppMovil.json` (publica comandos y recibe distancias). Ver `APP_MOVIL.md`. Un certificado por cliente permite **revocar solo el del teléfono** si se pierde.

## 5. Probar desde la consola de AWS (sin código)

Test → **MQTT test client** (usa tu sesión de la consola, no las políticas de arriba):
- Suscríbete a `sis234/esp32/#` y a `$aws/things/esp32-sis234/shadow/#`.
- Publica en `sis234/esp32/comandos`: `{"led":"rojo","estado":"on"}`.

## 6. Costos (capa gratuita)

Según la página de precios de AWS IoT Core, la capa gratuita de 12 meses desde la creación de la cuenta incluye, por mes, 2.250.000 minutos de conexión, 500.000 mensajes y 225.000 operaciones de Registry/Shadow. **Cada mensaje cuenta al publicarse y otra vez por cada entrega a un suscriptor.**

Con 2,5 lecturas/s, un suscriptor (servidor MCP) y otro (app): ≈ 7,5 mensajes/s ≈ 27.000/hora. **500.000 se agotan tras ~18 horas de ejecución continua.** Apaga la ESP32 cuando no pruebes y revisa Billing en AWS. Para ahorrar puedes subir `PUBLISH_INTERVAL_MS` (mínimo exigido: ≥ 2 lecturas/s → ≤ 500 ms).

## 7. Antes de ejecutar (checklist)
- [ ] Política de la ESP32 revisada
- [ ] Certificado + política del servidor MCP creados y archivos en `mcp-server/certs/`
- [ ] Certificado + política de la app creados
- [ ] Hora correcta en tu PC (TLS valida fechas)
