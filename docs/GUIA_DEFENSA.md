# Guía para entender y defender el proyecto MQTT + MCP

Esta guía explica el proyecto que está implementado en este repositorio y propone
respuestas para defenderlo. La idea principal es poder contar qué hace cada parte,
cómo se comunica con las demás y qué se ha probado realmente.

## 1. Explicación corta del proyecto

El proyecto convierte una ESP32 en un objeto inteligente: mide distancia con un
sensor ultrasónico HC-SR04, publica las mediciones en AWS IoT Core y controla
tres LEDs mediante comandos MQTT. Un servidor MCP permite que Claude Desktop
consulte la medición y solicite cambios en los LEDs usando herramientas descritas
por el servidor.

La ESP32, el servidor MCP y cualquier aplicación MQTT son clientes distintos.
No se conectan directamente entre sí: AWS IoT Core recibe y distribuye sus
mensajes según los tópicos MQTT.

```text
HC-SR04 y LEDs
      ↕
    ESP32 ───── MQTT/TLS ───── AWS IoT Core
                                  ↕      ↕
                       servidor MCP    app MQTT
                            ↕
                     Claude Desktop
                         (MCP/stdio)
```

La aplicación móvil aparece en los documentos del proyecto como una interfaz
posible, pero no está incluida ni validada en este repositorio. No afirmes que
está integrada hasta probarla.

## 2. Cómo funciona el recorrido de los datos

### Cuando se mide una distancia

1. `main.cpp` inicializa el sensor, los LEDs, Wi-Fi y los clientes MQTT.
2. La ESP32 envía un pulso por TRIG. El HC-SR04 devuelve un pulso por ECHO cuya
   duración depende del tiempo que tardó el sonido en ir al objeto y volver.
3. `UltrasonicSensor` calcula la distancia, descarta lecturas inválidas y usa la
   mediana de las lecturas válidas para reducir el efecto de valores atípicos.
4. Si hay conexión MQTT, la ESP32 publica un JSON como
   `{"cm":42.7}` en `sis234/esp32/distancia`.
5. El servidor MCP recibe ese tópico y conserva la última lectura válida y su
   antigüedad. Cuando Claude solicita `get_distance`, la herramienta devuelve
   la medida, o advierte si no hay una lectura o si está antigua.

La fórmula usada es:

```text
distancia en cm = duración del eco en microsegundos × 0,0343 / 2
```

Se divide entre dos porque el sonido recorre la distancia de ida y la de vuelta.
El código usa tres muestras como valor configurado de ejemplo y programa la
publicación cada 400 ms (aproximadamente 2,5 publicaciones por segundo). Eso
no demuestra por sí solo la exactitud ni la frecuencia medidas en el montaje real.

### Cuando se solicita cambiar un LED

1. Claude interpreta la solicitud y puede elegir una herramienta MCP, por ejemplo
   `set_led` u `only_led`.
2. El servidor valida el color y el estado. Luego publica un JSON como
   `{"led":"rojo","estado":"on"}` en `sis234/esp32/comandos`.
3. La ESP32 recibe el mensaje, valida el JSON y solo entonces cambia el GPIO
   correspondiente.
4. El firmware actualiza el Device Shadow de AWS con el estado del LED.
5. El servidor MCP espera el estado reportado para distinguir entre un comando
   enviado y un cambio confirmado por el dispositivo.

Que AWS acepte un mensaje no prueba que el LED haya cambiado físicamente. Por
eso el servidor informa **“enviado, sin confirmar”** si no recibe el estado
reportado dentro del tiempo configurado.

## 3. MQTT que debes poder explicar

MQTT es un protocolo de mensajería ligero basado en publicación/suscripción.
Un cliente publica mensajes en tópicos; otros clientes se suscriben a los
tópicos que les interesan. El broker recibe y distribuye los mensajes. En este
proyecto, AWS IoT Core cumple el rol de broker MQTT.

Un tópico es una ruta de texto que clasifica el mensaje, no una dirección IP ni
una conexión directa entre dos dispositivos. Los nombres usados por el código
son:

| Tópico | Publica | Se suscribe | Ejemplo |
|---|---|---|---|
| `sis234/esp32/distancia` | ESP32 | Servidor MCP | `{"cm":42.7}` |
| `sis234/esp32/comandos` | Servidor MCP (y un cliente MQTT autorizado) | ESP32 | `{"led":"rojo","estado":"on"}` |
| `$aws/things/esp32-sis234/shadow/...` | ESP32, AWS y clientes autorizados | ESP32 y servidor MCP, según operación | Estado del Device Shadow |

Los tópicos concretos se configuran en
[`config.example.h`](../firmware/include/config.example.h) y
[`.env.example`](../mcp-server/.env.example). Los nombres deben coincidir con
los autorizados por las políticas de AWS IoT.

### Niveles QoS en este proyecto

QoS describe la garantía de entrega MQTT entre clientes y broker; no certifica
que un actuador haya cambiado físicamente.

| Uso | QoS configurado | Qué significa aquí |
|---|---:|---|
| ESP32 publica distancia | 0 | Entrega “como máximo una vez”; es ligero y una medida siguiente pronto estará disponible. |
| ESP32 se suscribe a comandos | 1 | AWS intenta entregar el mensaje al menos una vez; el consumidor debe tolerar que pueda repetirse. |
| Servidor MCP se suscribe a distancia y respuestas Shadow | 0 | Recibir la lectura más reciente es más importante que retransmitir cada muestra. |
| Servidor MCP publica comandos y solicitudes Shadow | 1 | El cliente solicita entrega al menos una vez hacia AWS; no equivale a confirmación de ejecución. |
| ESP32 publica actualizaciones Shadow | 0 | Es la publicación que permite reportar el estado; el código usa PubSubClient. |

En teoría MQTT define QoS 2, pero este proyecto no lo usa: la combinación de
AWS IoT Core y PubSubClient utilizada por el firmware trabaja con QoS 0/1 en
estos flujos.

## 4. Device Shadow: estado que AWS conserva

El Device Shadow es un documento JSON asociado al dispositivo. Permite conservar
un estado aunque la ESP32 se desconecte temporalmente.

- **desired**: estado que se quiere que tenga el dispositivo.
- **reported**: estado que el dispositivo informa que tiene.
- **delta**: diferencias entre `desired` y `reported`.

Ejemplo simplificado:

```json
{
  "state": {
    "desired":  { "leds": { "rojo": "on" } },
    "reported": { "leds": { "rojo": "off" } }
  }
}
```

En ese ejemplo existe un delta porque se desea el LED rojo encendido, pero el
dispositivo reporta que está apagado. El firmware se suscribe a los tópicos de
actualización del Shadow, aplica los cambios deseados y publica el estado
reportado. Al reconectarse, consulta el Shadow para recuperar el estado deseado.
Cuando recibe un comando MQTT directo, sincroniza el estado desired y reported
para que un estado anterior no revierta el comando.

El Shadow no es el sensor ni un actuador: es una representación del estado en
AWS. La confirmación del servidor depende de recibir el estado reportado por la
ESP32 después de la solicitud.

## 5. Qué es MCP y qué hace la IA

MCP (Model Context Protocol) es un protocolo para que una aplicación con IA
descubra y use herramientas ofrecidas por un servidor. En este proyecto:

- **Claude Desktop** es el cliente que conversa con el usuario y decide si una
  herramienta disponible ayuda a responder.
- **El servidor MCP** describe las herramientas y traduce sus llamadas a
  operaciones del proyecto.
- **AWS IoT Core** sigue siendo el broker de los mensajes entre MCP y la ESP32.
- **La ESP32** ejecuta las acciones físicas; no ejecuta el modelo de IA.

Entre las herramientas implementadas están `get_distance`,
`get_system_status`, `set_led`, `only_led`, `all_leds_on`,
`all_leds_off` y, si Shadow está habilitado, `get_shadow_state`.
Por ejemplo, Claude puede usar `get_distance` ante “¿A qué distancia está el
objeto?” o `only_led` ante “Enciende el LED rojo y apaga los demás”.

Claude Desktop se comunica con el servidor mediante MCP sobre `stdio`. Por eso
el servidor no debe escribir mensajes normales con `print()` en stdout: esos
bytes son el canal del protocolo. Los registros de diagnóstico se envían a
stderr con `logging`.

MCP no reemplaza MQTT: MCP conecta la aplicación de IA con las herramientas del
servidor, mientras MQTT conecta los clientes IoT a AWS IoT Core.

## 6. Seguridad y reconexión

- La conexión MQTT del dispositivo y del servidor usa TLS en el puerto 8883.
- Cada cliente usa su propia identidad/certificado y clave privada; la identidad
  del servidor MCP no debe reutilizar la de la ESP32.
- La CA permite verificar el certificado del servidor y el certificado de
  cliente identifica al dispositivo ante AWS IoT Core.
- Las políticas de AWS limitan qué cliente puede conectarse, publicar y
  suscribirse. Tener un certificado no debe significar permisos ilimitados.
- El firmware sincroniza la hora por NTP antes de iniciar MQTT/TLS, porque la
  validación de certificados depende de una hora válida.
- Wi-Fi y MQTT reintentan la conexión. Después de reconectar MQTT, el firmware
  vuelve a suscribirse y solicita el estado del Shadow.
- Los archivos locales con credenciales (`config.h`, `aws_certificates.h`,
  `.env` y claves/certificados del servidor) están pensados para excluirse de
  Git. No copies credenciales en este documento, en capturas ni en commits.

El pin ECHO del HC-SR04 puede entregar 5 V, mientras que los GPIO de la ESP32
trabajan a 3,3 V. Se necesita el divisor de voltaje indicado para el montaje;
sin él se puede dañar la placa. Los pines configurados actualmente se consultan
en [`config.example.h`](../firmware/include/config.example.h), no en guías
anteriores que puedan mostrar otra distribución.

## 7. Cómo se organiza el código

| Archivo | Responsabilidad |
|---|---|
| [`main.cpp`](../firmware/src/main.cpp) | Orquesta inicialización y ciclo principal; enruta los mensajes MQTT. |
| [`UltrasonicSensor.cpp`](../firmware/src/UltrasonicSensor.cpp) | Controla el HC-SR04, calcula la distancia y filtra lecturas con mediana. |
| [`ActuatorController.cpp`](../firmware/src/ActuatorController.cpp) | Valida comandos JSON y controla los LEDs. |
| [`WifiManager.cpp`](../firmware/src/WifiManager.cpp) | Mantiene y restablece la conexión Wi-Fi. |
| [`TimeSync.cpp`](../firmware/src/TimeSync.cpp) | Obtiene la hora por NTP para que TLS pueda validar certificados. |
| [`MqttManager.cpp`](../firmware/src/MqttManager.cpp) | Configura MQTT/TLS, publica, procesa mensajes y re-suscribe tras reconexión. |
| [`ShadowManager.cpp`](../firmware/src/ShadowManager.cpp) | Consulta, aplica y reporta desired/reported del Device Shadow. |
| [`smart-object.py`](../mcp-server/smart-object.py) | Declara las herramientas MCP disponibles para Claude Desktop. |
| [`aws_iot_bridge.py`](../mcp-server/aws_iot_bridge.py) | Implementa la conexión MQTT del servidor, procesa datos, envía comandos y espera reportes. |
| [`test_bridge.py`](../mcp-server/tests/test_bridge.py) | Pruebas del puente usando un cliente MQTT simulado. |

La separación permite explicar y probar responsabilidades por partes: el sensor
no decide cómo hablar con AWS y el servidor MCP no acciona directamente los
GPIO.

## 8. Preguntas frecuentes para la defensa

### ¿Cuál es el propósito del proyecto?

Medir distancia y controlar actuadores de un objeto IoT con MQTT sobre AWS IoT
Core, y permitir consultar o solicitar acciones usando herramientas MCP desde
Claude Desktop.

### ¿Por qué MQTT en vez de que cada programa se conecte directamente a la ESP32?

El modelo publicación/suscripción desacopla los clientes. La ESP32 publica o se
suscribe a tópicos y el broker distribuye los mensajes; así el sensor no tiene
que conocer la aplicación ni Claude.

### ¿Qué ocurre si se pierde Internet o Wi-Fi?

La medición no se puede enviar mientras no haya conexión. El firmware intenta
recuperar Wi-Fi y MQTT; después de reconectarse re-suscribe los tópicos y vuelve
a consultar el Shadow. No debo afirmar un tiempo de recuperación específico sin
medirlo.

### ¿QoS 1 garantiza que el LED se encendió?

No. QoS 1 es una garantía de entrega al menos una vez entre clientes y broker y
puede producir duplicados. Para saber si la ESP32 aplicó el cambio, el servidor
espera el estado reportado en el Shadow. Incluso eso comprueba el estado lógico
informado por el firmware, no una medición eléctrica independiente del LED.

### ¿Por qué hay un divisor de voltaje en ECHO?

Porque el HC-SR04 puede entregar 5 V en ECHO y la ESP32 usa lógica de 3,3 V. El
divisor reduce el voltaje para proteger la entrada GPIO.

### ¿Qué diferencia hay entre MQTT y MCP?

MQTT lleva mensajes IoT entre clientes y el broker AWS. MCP permite que Claude
descubra e invoque herramientas del servidor. En este proyecto se usan ambos:
Claude → MCP server → MQTT/AWS → ESP32.

### ¿Claude controla directamente los pines?

No. Claude solicita una herramienta; el servidor valida los parámetros y
publica el comando; el firmware valida de nuevo el JSON y cambia el GPIO.

### ¿Para qué sirve el Device Shadow?

Para representar en AWS el estado deseado y el que el dispositivo reportó.
Permite recuperar el estado deseado tras una reconexión y detectar diferencias
mediante delta.

### ¿Qué hace que una orden de lenguaje natural termine en una herramienta?

El servidor anuncia a Claude nombres, descripciones y parámetros de sus
herramientas. Claude elige una según la solicitud, y el servidor ejecuta esa
operación. La elección de herramienta no sustituye la validación del servidor
ni del firmware.

## 9. Estado del proyecto y cómo hablar de resultados

El README del repositorio indica que el servidor MCP tiene 25 pruebas automáticas
con un cliente MQTT simulado. Esas pruebas no prueban una conexión real con AWS,
Claude Desktop ni el hardware.

El mismo README señala que el firmware aún no está compilado/probado en hardware
y que la integración real con AWS, la aplicación móvil y Claude Desktop está
pendiente de validación. Comprueba el estado actual antes de la defensa y no
presentes una prueba simulada como una prueba física.

Las mediciones de alcance, exactitud, latencia, estabilidad y reconexión se
deben completar con resultados del montaje real. Si no las has medido, dilo y
explica cómo las medirías; no inventes valores.

### Nota sobre documentación anterior

Algunos apartados de [`GUIA_IMPLEMENTACION.md`](./GUIA_IMPLEMENTACION.md) y
[`FALTA_POR_HACER.md`](./FALTA_POR_HACER.md) conservan instrucciones de una
versión previa, como un broker público, `TOPIC_PREFIX` o pines distintos. Para
describir lo que hace el código actual, toma como referencia los valores de
[`config.example.h`](../firmware/include/config.example.h),
[`.env.example`](../mcp-server/.env.example) y los archivos fuente. Conviene
armonizar esas guías antes de usarlas como instrucciones de instalación.

## 10. Saber ser: cómo demostrar responsabilidad

- Explica el trabajo del equipo y también cómo se integra con las otras partes;
  no presentes como validado algo que hizo otra persona sin comprobarlo.
- Trabaja de forma ordenada: configura, prueba una parte, registra el resultado
  y luego integra el siguiente componente.
- Usa commits claros y propios para que el historial permita entender las
  contribuciones del equipo.
- Protege credenciales y certificados; usa las plantillas de ejemplo para
  compartir configuración sin contraseñas ni claves.
- Al reportar errores, indica qué componente probaste, qué esperabas, qué
  ocurrió y qué evidencia tienes (por ejemplo, logs o una prueba).

## 11. Respuesta de 30 segundos

> “Nuestra ESP32 mide distancia con un HC-SR04 y publica el resultado como JSON
> en AWS IoT Core mediante MQTT/TLS. También se suscribe a un tópico de comandos
> para controlar tres LEDs. Un servidor MCP expone herramientas que Claude
> Desktop puede invocar: el servidor consulta las mediciones o publica comandos
> MQTT. El Device Shadow conserva el estado deseado y el reportado, y permite
> saber si el dispositivo confirmó un cambio. MQTT transporta los mensajes IoT;
> MCP conecta Claude con las herramientas. Estamos separando las pruebas
> simuladas de las que todavía debemos validar con el hardware y AWS reales.”
