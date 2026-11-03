# Aplicación móvil

La práctica exige: ver la distancia **gráficamente** (RF4) y **enviar comandos** a los LEDs (RF5).

## Requisito de AWS que condiciona la elección
AWS IoT Core con MQTT en el puerto 8883 exige **TLS con certificado de cliente** (autenticación mutua). Por tanto la app debe permitir:
1. Habilitar TLS/SSL con la **CA raíz de Amazon** (`AmazonRootCA1.pem`)
2. Usar un **certificado de cliente + clave privada** (muchas apps los piden empaquetados en un `.p12`/PKCS#12)
3. Fijar un Client ID propio (`app-sis234`)

> **Estado de verificación:** no pude confirmar que IoT MQTT Panel ofrezca estas opciones; no encontré documentación oficial que lo garantice. Comprueba en tu teléfono antes de invertir tiempo (paso 1). No asumas que funciona.

## Paso 1 — Comprobar la app (5 minutos)
En IoT MQTT Panel: crear conexión → habilitar SSL/TLS → mira qué campos aparecen.

| Lo que ves | Conclusión |
|---|---|
| Campos para **CA** y **certificado/clave de cliente** (o `.p12`) | Compatible: sigue con el paso 2 |
| Solo "usuario/contraseña" o "certificado firmado por CA" sin certificado de cliente | **No sirve** con certificados AWS: usa la alternativa B |

## Paso 2 — Identidad propia de la app
1. Crea un certificado nuevo en AWS y adjunta la política `PoliticaAppMovil` (ver `AWS_CONFIGURACION.md §4`). No reutilices el de la ESP32 ni el del servidor.
2. En tu PC, empaquétalo (OpenSSL; en Windows se incluye con Git Bash):
   ```bash
   openssl pkcs12 -export -in app-certificate.pem.crt -inkey app-private.pem.key \
       -certfile AmazonRootCA1.pem -out app-sis234.p12
   ```
   Te pedirá una contraseña para el `.p12`. Algunas versiones nuevas de OpenSSL cifran de una forma que ciertas apps Android antiguas no leen; si falla, repite con `-legacy` (OpenSSL 3).
3. Pasa `app-sis234.p12` y `AmazonRootCA1.pem` al teléfono por un medio privado (cable USB; evita correo o chats públicos). **Bórralos de la carpeta de descargas** después de importarlos.

## Paso 3 — Conexión
| Campo | Valor |
|---|---|
| Servidor | `ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com` |
| Puerto | `8883` |
| TLS/SSL | activado, con CA + certificado de cliente |
| Client ID | `app-sis234` (debe coincidir con la política) |
| Usuario/contraseña | vacío |

## Paso 4 — Panel
| Widget | Configuración |
|---|---|
| **Gauge** (o *Line graph*) | Tópico `sis234/esp32/distancia`, mín 0, máx 200 cm. Debe extraer el campo `cm` del JSON (busca una opción tipo "JSON key" / "payload is JSON") |
| **Switch Rojo** | Publica en `sis234/esp32/comandos`: ON → `{"led":"rojo","estado":"on"}`, OFF → `{"led":"rojo","estado":"off"}` |
| **Switch Verde / Amarillo** | Igual, con `verde` / `amarillo` |

Si la app **no** puede leer el campo `cm` de un JSON, el gauge no mostrará valores. Solución: que el firmware publique el número solo en un tópico adicional (p. ej. `sis234/esp32/distancia_valor`), lo cual exige **añadir ese tópico a las políticas** de la ESP32 y de la app. No se implementó para respetar los tópicos autorizados; puede añadirse si hace falta.

Exporta la configuración del panel y guárdala en `config/` (sin credenciales dentro del archivo exportado: revísalo antes de subirlo).

## Alternativas si la app no admite certificados de cliente

| Alternativa | Comentario |
|---|---|
| **B. Otra app MQTT móvil con soporte de certificados de cliente (.p12/PEM)** | Busca una que lo declare en su ficha y aplica los pasos 2–4. No recomiendo ninguna sin haberla probado. |
| **C. Consola de AWS → MQTT test client desde el navegador del teléfono** | Segura (usa tu sesión de AWS, sin claves en el teléfono) y sirve para ver mensajes y publicar comandos, pero **no ofrece gráfico**: no cumple RF4 por sí sola. |
| **D. Panel web propio** que se conecte por MQTT sobre WebSocket con credenciales temporales (Amazon Cognito) | Cumple RF4 y RF5 sin guardar claves privadas en el teléfono, pero exige **crear recursos nuevos en AWS** (identity pool + política). No se implementó por tu restricción de no crear recursos; puede prepararse como siguiente paso. |

No uses un broker público adicional (p. ej. HiveMQ público) como atajo: dividiría el sistema en dos brokers y expondría los datos.

## Seguridad
- Un certificado por cliente: si pierdes el teléfono, **desactiva solo el certificado de la app** en AWS.
- La política de la app es mínima: no puede leer ni modificar el Shadow, ni conectarse como la ESP32.
