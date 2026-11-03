# Análisis completo del proyecto SIS234-AWS-IoT

> Informe generado mediante inspección directa del workspace real. La estructura real es `firmware/` + `mcp-server/`; no existen `src/` ni `mcp/smart-object/`.

## 1. Alcance

Se analizaron **42 archivos visibles**: 17 de firmware, 10 de MCP, 7 de documentación, 6 de configuración y 2 de raíz. Se excluyeron `.git`, `.pio`, `.venv`, `__pycache__` y generados. Se incluyen abajo completos los 26 archivos de código/configuración solicitados. No se encontraron secretos reales; se mantienen solo plantillas. La prueba ejecutada fue `python -m unittest discover -s tests -v` desde `mcp-server`: **25 pruebas OK**. No se compiló PlatformIO ni se probó AWS/hardware/Claude/app reales.

## 2. Árbol completo

```text
SIS234-AWS-IoT/
├── .gitignore
├── README.md
├── ANALISIS_COMPLETO_PROYECTO.md (este documento)
├── config/
│   ├── README.md
│   ├── claude_desktop_config.example.json
│   └── policies/
│       ├── ESP32_extra_rejected_opcional.json
│       ├── PoliticaAppMovil.json
│       ├── PoliticaESP32SIS234_referencia.json
│       └── PoliticaServidorMCP.json
├── docs/
│   ├── APP_MOVIL.md
│   ├── AWS_CONFIGURACION.md
│   ├── CIRCUITO.md
│   ├── DEVICE_SHADOW.md
│   ├── GUIA_IMPLEMENTACION.md
│   ├── MQTT_TOPICOS.md
│   └── PRUEBAS.md
├── firmware/
│   ├── .gitignore
│   ├── platformio.ini
│   ├── include/ (aws_certificates.example.h, config.example.h)
│   └── src/ (13 archivos .cpp/.h: ActuatorController, MqttManager,
│       ShadowManager, TimeSync, UltrasonicSensor, WifiManager y main)
└── mcp-server/
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── aws_iot_bridge.py
    ├── smart-object.py
    ├── pyproject.toml
    ├── certs/ (.gitkeep, README.md)
    └── tests/ (__init__.py, test_bridge.py)
```

## 3. Arquitectura y comunicación

`firmware/` es un proyecto PlatformIO/C++ que corre en ESP32; `mcp-server/` es Python administrado por `uv` que corre en el PC. Son componentes distintos comunicados por AWS IoT Core, no dos copias del mismo módulo. La app móvil está documentada, pero no hay código de app en el repositorio.

Configuración AWS objetivo: región `us-east-2`, endpoint `ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com`, puerto TLS `8883`, Thing/Client ID ESP32 `esp32-sis234`, política existente `PoliticaESP32SIS234`, Shadow clásico.

| Tópico | Publica | Suscribe | Mensaje/uso |
|---|---|---|---|
| `sis234/esp32/distancia` | ESP32 | MCP, app | `{"cm":42.7}`, cada 400 ms configurados |
| `sis234/esp32/comandos` | MCP, app | ESP32 | `{"led":"rojo","estado":"on"}` |
| `$aws/things/esp32-sis234/shadow/update` | ESP32 | AWS | estado reported y desired para comando directo |
| `.../shadow/update/delta` | AWS | ESP32 | diferencia desired/reported |
| `.../shadow/get` | ESP32, MCP | AWS | solicitud del Shadow |
| `.../accepted` | AWS | ESP32/MCP | confirmación o respuesta de estado |

La ESP32 mide HC-SR04, publica distancia, recibe comandos y controla tres LEDs. MCP publica comandos y escucha distancia/Shadow. Claude Desktop usa MCP/stdio y no accede al broker directamente. La app publica comandos y recibe distancia con su propia identidad.

## 4. TLS, autenticación y reconexión

ESP32 usa `WiFiClientSecure` con CA de Amazon, certificado de cliente y clave privada en el header local ignorado. `PubSubClient` conecta a 8883; `TimeSync` obtiene NTP antes del handshake porque TLS valida fechas. `WifiManager` reintenta cada 5 s. `MqttManager` reintenta sin bloquear, re-suscribe cada tópico después de cada conexión y notifica a ShadowManager.

MCP usa Paho MQTT callback API v2, `tls_set(ca_certs, certfile, keyfile)`, `connect_async`, `loop_start` y backoff 1–30 s. Su Client ID/certificado/política (`mcp-sis234`) son independientes de ESP32; no deben reutilizarse.

## 5. Device Shadow

El documento usa `state.desired.leds` y `state.reported.leds`; AWS calcula `delta`. Al conectar, ESP32 pide `shadow/get`, aplica `desired` de `get/accepted` y publica `reported`. Si no hay respuesta en 5 s, reporta el estado actual. Un `update/delta` aplica LEDs y reporta sin reescribir desired. Un comando directo publica reported y desired juntos para evitar un delta que revierta el cambio. Los publishes se difieren fuera de callbacks porque PubSubClient reutiliza su buffer. MCP consulta el Shadow con `get_shadow_state` y confirma cambios mediante `update/accepted` posterior al envío.

## 6. Políticas AWS

Los JSON en `config/policies` son referencias con `<ACCOUNT_ID>`: no prueban que estén aplicados. La referencia ESP32 coincide con `main.cpp`/`ShadowManager`: Connect al cliente ESP32, Publish distancia/update/get, Subscribe+Receive comandos/delta/accepted. La referencia MCP coincide con `aws_iot_bridge.py`: Publish comandos/get y Subscribe+Receive distancia/update accepted/get accepted. La app solo publica comandos y recibe distancia. El JSON `ESP32_extra_rejected_opcional.json` añade diagnósticos rejected; activar solo tras aplicar esos permisos. Verificar siempre las políticas reales en AWS.

## 7. Análisis de módulos

- `main.cpp`: inicialización, callback MQTT, ciclo Wi-Fi/NTP/MQTT/Shadow, publicación de distancia y estado.
- `WifiManager`: modo estación, auto-reconexión y retry no bloqueante.
- `TimeSync`: NTP UTC y epoch válido.
- `UltrasonicSensor`: TRIG/ECHO, timeout 30 ms, rango 2–400 cm y mediana de 3 muestras.
- `ActuatorController`: JSON validado, colores rojo/verde/amarillo, estados on/off y active-low.
- `MqttManager`: TLS, PubSubClient, callbacks, publicaciones y suscripciones persistentes.
- `ShadowManager`: topics, filtros ArduinoJson, desired/reported/delta, timeout y anti-ciclos.
- `aws_iot_bridge.py`: `.env`, TLS Paho, estado sincronizado, parseo, normalización, confirmación y Shadow.
- `smart-object.py`: herramientas `get_distance`, `get_system_status`, `set_led`, `only_led`, `all_leds_on`, `all_leds_off`, `get_shadow_state`; logs por stderr para preservar stdio.
- `test_bridge.py`: 25 pruebas simuladas de helpers, conexión, publicación, reconexión, confirmación y Shadow.

## 8. Ejecución exacta

### Firmware
```powershell
cd firmware
Copy-Item include/config.example.h include/config.h
Copy-Item include/aws_certificates.example.h include/aws_certificates.h
# completar localmente Wi-Fi y certificados
pio run
pio run -t upload
pio device monitor
```

### MCP/uv
```powershell
cd mcp-server
Copy-Item .env.example .env
# copiar CA, certificado y clave del servidor a certs\
uv sync
uv run python -m unittest discover -s tests -v
uv run smart-object.py
```

### Claude Desktop
Copiar `config/claude_desktop_config.example.json` a `%APPDATA%\Claude\claude_desktop_config.json`, sustituir la ruta `C:/RUTA/ABSOLUTA/...` por la ruta real y reiniciar Claude. Si `uv` no está en PATH, usar la ruta de `where uv`.

## 9. Implementado / documentado / pendiente

| Estado | Elementos |
|---|---|
| Implementado | Firmware modular, MQTT/TLS, NTP, reconexión, sensor, LEDs, Shadow, puente Paho, herramientas MCP y pruebas unitarias simuladas. |
| Documentado pero no implementado aquí | App móvil, panel gráfico, recursos AWS, despliegue Claude Desktop y circuito físico. |
| Pendiente de prueba | `pio run`, carga ESP32, TLS/AWS real, permisos reales, sensor, reconexión física, MCP contra AWS y app. |

## 10. Problemas encontrados

| Prioridad | Archivo/área | Causa | Solución recomendada |
|---|---|---|---|
| CRÍTICO | `firmware/` | Faltan `config.h` y `aws_certificates.h` por diseño; sin ellos no compila. | Crear copias locales, completar y ejecutar PlatformIO; no versionar. |
| CRÍTICO | AWS/policies | JSON de referencia con `<ACCOUNT_ID>`; no se sabe si están aplicados. | Verificar y adjuntar políticas/certificados reales por identidad. |
| CRÍTICO | `mcp-server/.env`, `certs/` | Faltan configuración e identidad TLS operativa. | Crear `.env` y copiar CA/cert/key propios del MCP. |
| IMPORTANTE | Config Claude | Ruta placeholder no ejecutable. | Sustituir por ruta absoluta real y reiniciar. |
| IMPORTANTE | `platformio.ini` | Placa fijada a `esp32doit-devkit-v1`. | Confirmar placa física antes de cargar. |
| IMPORTANTE | Hardware | GPIO12 es strapping y ECHO del HC-SR04 es 5 V. | Revisar divisor, resistencias, GND y arranque. |
| IMPORTANTE | App móvil | No hay implementación ni prueba de TLS/certificado/JSON. | Validar app compatible o implementar alternativa segura. |
| MEJORA | `aws_iot_bridge.py` | Valores `.env` mal formados pueden producir excepciones directas. | Añadir validación de tipos y mensajes claros. |
| MEJORA | Costos | 2,5 mensajes/s por cada suscriptor consume cuota. | Medir y ajustar intervalo sin incumplir requisitos. |

No se afirma error de compilación porque PlatformIO aún no se ejecutó.

## 11. Plan paso a paso

1. Verificar región, endpoint, Thing y política ESP32 real.
2. Crear/activar identidades y políticas separadas MCP/app.
3. Montar divisor ECHO, resistencias, GND y revisar GPIO12.
4. Provisionar headers privados, compilar y cargar firmware.
5. Confirmar NTP, TLS, suscripciones y distancia.
6. Probar comandos válidos/inválidos y los tres LEDs.
7. Probar Shadow get, desired/delta, reported, timeout y reinicio.
8. Probar reconexión Wi-Fi/MQTT sin reinicio.
9. Crear `.env`/certs MCP, ejecutar `uv sync`, las 25 pruebas y AWS real.
10. Registrar Claude Desktop y probar herramientas, confirmación y Shadow.
11. Configurar app con identidad propia, distancia gráfica y comandos.
12. Medir estabilidad, exactitud, latencia, frecuencia y reconexión.

## 12. Código completo de archivos relevantes
### `firmware/platformio.ini`
```ini
; Firmware del objeto inteligente SIS-234 -> AWS IoT Core (MQTT TLS + Device Shadow)
[env:esp32dev]
platform = espressif32@^6.9.0
board = esp32doit-devkit-v1   ; cambia a "esp32dev" si tu placa no es DOIT DevKit V1
framework = arduino
monitor_speed = 115200
monitor_filters = esp32_exception_decoder
lib_deps =
    knolleary/PubSubClient@^2.8
    bblanchon/ArduinoJson@^7.0.0

### `firmware/include/config.example.h`
```cpp
/**
 * @file config.example.h
 * @brief Plantilla de configuraciÃ³n. Copiar como "config.h" y completar.
 *
 * "config.h" estÃ¡ en .gitignore: nunca subas tu contraseÃ±a de WiFi.
 * Los certificados van aparte, en "aws_certificates.h".
 */
#pragma once

// ---------------- WiFi ----------------
#define WIFI_SSID "NOMBRE_DE_LA_RED"
#define WIFI_PASSWORD "[REDACTADO]"
#define WIFI_RETRY_INTERVAL_MS 5000UL

// ---------------- AWS IoT Core (regiÃ³n us-east-2) ----------------
// Estos valores estÃ¡n vinculados a la polÃ­tica "PoliticaESP32SIS234": no los cambies.
#define AWS_IOT_ENDPOINT "ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com"
#define AWS_IOT_PORT 8883
#define AWS_THING_NAME "esp32-sis234"
#define AWS_CLIENT_ID AWS_THING_NAME  // la polÃ­tica autoriza client/esp32-sis234

#define MQTT_KEEPALIVE_S 60
#define MQTT_RETRY_INTERVAL_MS 5000UL
#define MQTT_BUFFER_SIZE 2048  // el documento Shadow puede superar los 256 B por defecto

// ---------------- TÃ³picos (autorizados en la polÃ­tica) ----------------
#define TOPIC_DISTANCE "sis234/esp32/distancia"
#define TOPIC_COMMAND "sis234/esp32/comandos"

// 1 = suscribirse tambiÃ©n a shadow/update/rejected y shadow/get/rejected.
// Requiere aÃ±adir esos tÃ³picos a la polÃ­tica (ver docs/AWS_CONFIGURACION.md).
// Si no estÃ¡n autorizados, AWS puede cerrar la conexiÃ³n: dÃ©jalo en 0 hasta aÃ±adirlos.
#define SHADOW_SUBSCRIBE_REJECTED 0
#define SHADOW_GET_TIMEOUT_MS 5000UL  // si get/accepted no llega, se reporta igualmente

// ---------------- Hora (NTP): obligatoria para validar certificados TLS ----------------
#define NTP_SERVER_1 "pool.ntp.org"
#define NTP_SERVER_2 "time.nist.gov"

// ---------------- Sensor ultrasÃ³nico HC-SR04 ----------------
// Pines segÃºn el montaje real del grupo (el diseÃ±o original usaba 5/18/25/26/27).
#define PIN_TRIG 27
#define PIN_ECHO 26          // Â¡con divisor de voltaje 1k/2k! (el ECHO entrega 5 V)
#define SENSOR_MIN_CM 2.0f
#define SENSOR_MAX_CM 400.0f // rango fÃ­sico; declara tu rango de trabajo en la documentaciÃ³n
#define SENSOR_SAMPLES 3     // mediana de N lecturas

// ---------------- LEDs ----------------
#define PIN_LED_RED 14
#define PIN_LED_GREEN 13
#define PIN_LED_YELLOW 12    // GPIO12 es un pin de arranque: ver docs/CIRCUITO.md
#define LED_ACTIVE_LOW 0     // 0 = LED a GND con resistencia (HIGH enciende)

// ---------------- PublicaciÃ³n y consola ----------------
// 400 ms = 2,5 lecturas/s (cumple >= 2/s). Cada lectura cuenta como mensaje publicado
// y como mensaje entregado a cada suscriptor: la capa gratuita de AWS es limitada.
#define PUBLISH_INTERVAL_MS 400UL
#define STATUS_INTERVAL_MS 10000UL
#define SERIAL_BAUD 115200

### `firmware/include/aws_certificates.example.h`
```cpp
/**
 * @file aws_certificates.example.h
 * @brief Plantilla de certificados. Copiar como "aws_certificates.h".
 *
 * "aws_certificates.h" estÃ¡ en .gitignore. Contiene la CLAVE PRIVADA de la ESP32:
 * no la subas a Git, no la compartas y no la pegues en chats.
 *
 * Pega el contenido COMPLETO de cada archivo (incluidas las lÃ­neas BEGIN/END)
 * entre R"EOF( y )EOF". No dejes espacios antes de las lÃ­neas -----BEGIN.
 */
#pragma once

// AmazonRootCA1.pem
static const char AWS_CERT_CA[] = R"EOF(
-----BEGIN CERTIFICATE-----
PEGA_AQUI_AmazonRootCA1.pem
-----END CERTIFICATE-----
)EOF";

// certificate.pem (certificado del dispositivo; en AWS termina en -certificate.pem.crt)
static const char AWS_CERT_CRT[] = R"EOF(
-----BEGIN CERTIFICATE-----
PEGA_AQUI_certificate.pem
-----END CERTIFICATE-----
)EOF";

// private.pem.key (clave privada del dispositivo)
static const char AWS_CERT_PRIVATE_KEY[] = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
PEGA_AQUI_private.pem.key
-----END RSA PRIVATE KEY-----
)EOF";

### `firmware/src/main.cpp`
```cpp
/**
 * @file main.cpp
 * @brief Objeto inteligente SIS-234 sobre AWS IoT Core.
 *
 * - Mide distancia (HC-SR04) y la publica en  sis234/esp32/distancia  {"cm":42.7}
 * - Recibe comandos en  sis234/esp32/comandos  {"led":"rojo","estado":"on"}
 * - Sincroniza el estado de los LEDs con el Device Shadow clÃ¡sico del Thing.
 * - ReconexiÃ³n automÃ¡tica de WiFi y MQTT (con re-suscripciÃ³n y consulta del Shadow).
 */
#include <Arduino.h>
#include <WiFi.h>

#include "ActuatorController.h"
#include "MqttManager.h"
#include "ShadowManager.h"
#include "TimeSync.h"
#include "UltrasonicSensor.h"
#include "WifiManager.h"
#include "aws_certificates.h"
#include "config.h"

WifiManager wifi(WIFI_SSID, WIFI_PASSWORD, WIFI_RETRY_INTERVAL_MS);
TimeSync timeSync(NTP_SERVER_1, NTP_SERVER_2);
MqttManager mqtt(AWS_IOT_ENDPOINT, AWS_IOT_PORT, AWS_CLIENT_ID, MQTT_KEEPALIVE_S,
                 MQTT_BUFFER_SIZE, MQTT_RETRY_INTERVAL_MS);
UltrasonicSensor sensor(PIN_TRIG, PIN_ECHO, SENSOR_MIN_CM, SENSOR_MAX_CM, SENSOR_SAMPLES);
ActuatorController actuators;
ShadowManager shadow(mqtt, actuators, AWS_THING_NAME);

unsigned long lastPublish = 0;
unsigned long lastStatus = 0;
bool wifiWasUp = false;

/** Enruta cada mensaje MQTT recibido: comandos directos o Device Shadow. */
void onMqttMessage(const char *topic, const uint8_t *payload, unsigned int length) {
  if (strcmp(topic, TOPIC_COMMAND) == 0) {
    String color;
    bool on = false;
    if (actuators.applyCommand(reinterpret_cast<const char *>(payload), length, color, on)) {
      // Mantener el Shadow coherente: desired = reported, asÃ­ no aparece un delta que revierta.
      shadow.requestReport(true);
    }
    return;
  }
  if (!shadow.handleMessage(topic, payload, length)) {
    Serial.printf("[MQTT] Tema no esperado: %s\n", topic);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println("\n[BOOT] Objeto inteligente SIS-234 (AWS IoT Core)");

  sensor.begin();
  actuators.begin();
  wifi.begin();

  mqtt.setCertificates(AWS_CERT_CA, AWS_CERT_CRT, AWS_CERT_PRIVATE_KEY);
  mqtt.addSubscription(TOPIC_COMMAND, 1);
  shadow.registerSubscriptions(SHADOW_SUBSCRIBE_REJECTED != 0);
  mqtt.begin(onMqttMessage, []() { shadow.onConnected(); });
}

void loop() {
  bool wifiUp = wifi.update();
  timeSync.update(wifiUp);
  if (wifiUp && !wifiWasUp) {
    mqtt.resetRetry();  // reconectar MQTT sin esperar al recuperar el WiFi
  }
  wifiWasUp = wifiUp;

  // TLS necesita WiFi y hora vÃ¡lida (validaciÃ³n de certificados).
  if (wifiUp && timeSync.synced()) {
    mqtt.update();
    shadow.update();
  }

  unsigned long now = millis();

  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = now;
    if (mqtt.connected()) {
      float cm;
      if (sensor.measure(cm)) {
        char payload[32];
        snprintf(payload, sizeof(payload), "{\"cm\":%.1f}", cm);
        mqtt.publish(TOPIC_DISTANCE, payload);
      } else {
        Serial.println("[SENSOR] Lectura invalida (sin eco o fuera de rango)");
      }
    }
  }

  if (now - lastStatus >= STATUS_INTERVAL_MS) {
    lastStatus = now;
    Serial.printf("[STATUS] wifi=%d rssi=%d hora=%d mqtt=%d heap=%u\n", wifiUp,
                  wifiUp ? WiFi.RSSI() : 0, timeSync.synced(), mqtt.connected(),
                  ESP.getFreeHeap());
  }
}

### `firmware/src/ActuatorController.h`
```cpp
/**
 * @file ActuatorController.h
 * @brief Control de los tres LEDs (rojo, verde, amarillo) con validaciÃ³n de comandos.
 *
 * Comando JSON aceptado:  {"led":"rojo","estado":"on"}
 *   led    : rojo | verde | amarillo
 *   estado : on | off
 * NingÃºn GPIO se modifica hasta que el comando completo ha sido validado.
 */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

#include "config.h"

class ActuatorController {
 public:
  /** Configura los pines y apaga todo. Llamar una vez en setup(). */
  void begin();

  /** Enciende/apaga un LED por nombre. @return false si el color no existe. */
  bool setLed(const String &color, bool on);

  /**
   * Valida un comando JSON SIN ejecutarlo.
   * @param[out] color  Color normalizado (minÃºsculas).
   * @param[out] on     Estado pedido.
   * @return true si el comando es vÃ¡lido.
   */
  bool parseCommand(const char *payload, unsigned int length, String &color, bool &on) const;

  /** Valida y ejecuta un comando. @return true si se aplicÃ³. */
  bool applyCommand(const char *payload, unsigned int length, String &color, bool &on);

  /** Escribe el estado actual en un objeto JSON: {"rojo":"on", ...}. */
  void fillState(JsonObject leds) const;

 private:
  enum { kLedCount = 3 };
  struct Led {
    const char *name;
    uint8_t pin;
    bool on;
  };

  int indexOf(const String &lowerCaseColor) const;

  Led leds_[kLedCount] = {{"rojo", PIN_LED_RED, false},
                          {"verde", PIN_LED_GREEN, false},
                          {"amarillo", PIN_LED_YELLOW, false}};
};

### `firmware/src/ActuatorController.cpp`
```cpp
#include "ActuatorController.h"

void ActuatorController::begin() {
  for (uint8_t i = 0; i < kLedCount; i++) {
    pinMode(leds_[i].pin, OUTPUT);
    digitalWrite(leds_[i].pin, LED_ACTIVE_LOW ? HIGH : LOW);
    leds_[i].on = false;
  }
}

int ActuatorController::indexOf(const String &lowerCaseColor) const {
  for (uint8_t i = 0; i < kLedCount; i++) {
    if (lowerCaseColor == leds_[i].name) {
      return i;
    }
  }
  return -1;
}

bool ActuatorController::setLed(const String &color, bool on) {
  String name = color;
  name.toLowerCase();
  int i = indexOf(name);
  if (i < 0) {
    Serial.printf("[ACT] Color desconocido: %s\n", color.c_str());
    return false;
  }
  bool level = LED_ACTIVE_LOW ? !on : on;
  digitalWrite(leds_[i].pin, level ? HIGH : LOW);
  leds_[i].on = on;
  Serial.printf("[ACT] LED %s -> %s\n", leds_[i].name, on ? "ON" : "OFF");
  return true;
}

bool ActuatorController::parseCommand(const char *payload, unsigned int length, String &color,
                                      bool &on) const {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("[ACT] JSON invalido: %s\n", err.c_str());
    return false;
  }
  const char *led = doc["led"].as<const char *>();
  const char *estado = doc["estado"].as<const char *>();
  if (led == nullptr || estado == nullptr) {
    Serial.println("[ACT] Comando incompleto: se requieren 'led' y 'estado'");
    return false;
  }
  String state = estado;
  state.toLowerCase();
  if (state != "on" && state != "off") {
    Serial.printf("[ACT] Estado invalido: %s\n", estado);
    return false;
  }
  String name = led;
  name.toLowerCase();
  if (indexOf(name) < 0) {
    Serial.printf("[ACT] Color desconocido: %s\n", led);
    return false;
  }
  color = name;
  on = (state == "on");
  return true;
}

bool ActuatorController::applyCommand(const char *payload, unsigned int length, String &color,
                                      bool &on) {
  if (!parseCommand(payload, length, color, on)) {
    return false;  // comando invÃ¡lido: ningÃºn GPIO fue modificado
  }
  return setLed(color, on);
}

void ActuatorController::fillState(JsonObject leds) const {
  for (uint8_t i = 0; i < kLedCount; i++) {
    leds[leds_[i].name] = leds_[i].on ? "on" : "off";
  }
}

### `firmware/src/MqttManager.h`
```cpp
/**
 * @file MqttManager.h
 * @brief Cliente MQTT seguro (TLS con certificado de cliente) para AWS IoT Core.
 *
 * - AutenticaciÃ³n mutua: CA raÃ­z de Amazon + certificado y clave del dispositivo.
 * - ReconexiÃ³n automÃ¡tica no bloqueante.
 * - Re-suscripciÃ³n a todos los tÃ³picos registrados tras CADA reconexiÃ³n.
 *
 * Limitaciones de PubSubClient + AWS IoT: solo se publica con QoS 0 y se puede
 * suscribir con QoS 0 o 1 (AWS IoT Core no admite QoS 2).
 */
#pragma once
#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>

#include <functional>

class MqttManager {
 public:
  using MessageHandler =
      std::function<void(const char *topic, const uint8_t *payload, unsigned int length)>;
  using ConnectHandler = std::function<void()>;

  MqttManager(const char *endpoint, uint16_t port, const char *clientId,
              uint16_t keepAliveS, uint16_t bufferSize, unsigned long retryMs);

  /** Carga los certificados TLS (cadenas PEM con vida Ãºtil estÃ¡tica). */
  void setCertificates(const char *caCert, const char *clientCert, const char *privateKey);

  /** Registra un tÃ³pico al que suscribirse en cada (re)conexiÃ³n. Llamar antes de begin(). */
  void addSubscription(const String &topic, uint8_t qos);

  /** Configura el cliente y los callbacks. Llamar una vez en setup(). */
  void begin(MessageHandler onMessage, ConnectHandler onConnect);

  /** Llamar en cada loop() con WiFi y hora vÃ¡lidas: reconecta y procesa mensajes. */
  void update();

  /** Permite reintentar la conexiÃ³n de inmediato (p. ej. al recuperar el WiFi). */
  void resetRetry() { lastAttempt_ = 0; }

  bool connected() { return client_.connected(); }

  /** Publica un mensaje. @return true si se enviÃ³. */
  bool publish(const char *topic, const char *payload);

 private:
  enum { kMaxSubscriptions = 8 };
  struct Subscription {
    String topic;
    uint8_t qos = 0;
  };

  bool connect();

  WiFiClientSecure net_;  // debe declararse antes que client_
  PubSubClient client_;
  const char *endpoint_;
  uint16_t port_;
  const char *clientId_;
  uint16_t keepAliveS_;
  uint16_t bufferSize_;
  unsigned long retryMs_;
  unsigned long lastAttempt_ = 0;
  Subscription subs_[kMaxSubscriptions];
  uint8_t subCount_ = 0;
  MessageHandler onMessage_;
  ConnectHandler onConnect_;
};

### `firmware/src/MqttManager.cpp`
```cpp
#include "MqttManager.h"

MqttManager::MqttManager(const char *endpoint, uint16_t port, const char *clientId,
                         uint16_t keepAliveS, uint16_t bufferSize, unsigned long retryMs)
    : client_(net_),
      endpoint_(endpoint),
      port_(port),
      clientId_(clientId),
      keepAliveS_(keepAliveS),
      bufferSize_(bufferSize),
      retryMs_(retryMs) {}

void MqttManager::setCertificates(const char *caCert, const char *clientCert,
                                  const char *privateKey) {
  net_.setCACert(caCert);
  net_.setCertificate(clientCert);
  net_.setPrivateKey(privateKey);
}

void MqttManager::addSubscription(const String &topic, uint8_t qos) {
  if (subCount_ >= kMaxSubscriptions) {
    Serial.println("[MQTT] Demasiadas suscripciones registradas");
    return;
  }
  subs_[subCount_].topic = topic;
  subs_[subCount_].qos = qos;
  subCount_++;
}

void MqttManager::begin(MessageHandler onMessage, ConnectHandler onConnect) {
  onMessage_ = onMessage;
  onConnect_ = onConnect;
  client_.setServer(endpoint_, port_);
  client_.setKeepAlive(keepAliveS_);
  client_.setSocketTimeout(10);
  if (!client_.setBufferSize(bufferSize_)) {
    Serial.println("[MQTT] No se pudo reservar el buffer MQTT");
  }
  client_.setCallback([this](char *topic, uint8_t *payload, unsigned int length) {
    if (onMessage_) {
      onMessage_(topic, payload, length);
    }
  });
}

bool MqttManager::connect() {
  unsigned long now = millis();
  if (lastAttempt_ != 0 && now - lastAttempt_ < retryMs_) {
    return false;  // aÃºn no toca reintentar
  }
  lastAttempt_ = now;

  Serial.printf("[MQTT] Conectando a %s:%u como '%s'...\n", endpoint_, port_, clientId_);
  if (!client_.connect(clientId_)) {
    char tlsError[100] = {0};
    net_.lastError(tlsError, sizeof(tlsError));
    // estado PubSubClient: -2 sin red/TLS, 4 credenciales, 5 no autorizado (polÃ­tica)
    Serial.printf("[MQTT] Fallo: estado=%d, TLS='%s'\n", client_.state(), tlsError);
    return false;
  }

  Serial.println("[MQTT] Conectado a AWS IoT Core");
  for (uint8_t i = 0; i < subCount_; i++) {
    bool ok = client_.subscribe(subs_[i].topic.c_str(), subs_[i].qos);
    Serial.printf("[MQTT] Suscripcion %s: %s\n", subs_[i].topic.c_str(), ok ? "ok" : "FALLO");
  }
  if (onConnect_) {
    onConnect_();
  }
  return true;
}

void MqttManager::update() {
  if (!client_.connected() && !connect()) {
    return;
  }
  client_.loop();
}

bool MqttManager::publish(const char *topic, const char *payload) {
  return client_.publish(topic, payload);
}

### `firmware/src/ShadowManager.h`
```cpp
/**
 * @file ShadowManager.h
 * @brief Device Shadow clÃ¡sico de AWS IoT: estados desired / reported / delta.
 *
 * Modelo del documento:
 *   {"state":{"desired":{"leds":{"rojo":"on",...}},"reported":{"leds":{"rojo":"on",...}}}}
 *
 * Reglas:
 *  - delta (desired != reported): se aplica al LED y se reporta. Nunca se toca "desired".
 *  - get/accepted tras (re)conectar: se aplica "desired" y se reporta el estado real.
 *  - comando directo (tÃ³pico de comandos): se aplica y se publica desired = reported
 *    para que no aparezca un delta que revierta el cambio.
 *  - update/accepted solo se registra: no genera nuevas publicaciones (sin ciclos).
 *
 * Las publicaciones se difieren a update() (fuera del callback MQTT) porque
 * PubSubClient reutiliza el mismo buffer para recibir y publicar.
 */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

#include "ActuatorController.h"
#include "MqttManager.h"

class ShadowManager {
 public:
  ShadowManager(MqttManager &mqtt, ActuatorController &actuators, const char *thingName);

  /** Registra los tÃ³picos del Shadow en MqttManager. Llamar antes de mqtt.begin(). */
  void registerSubscriptions(bool includeRejected);

  /** Llamar cuando MQTT se (re)conecta: pedirÃ¡ el Shadow para recuperar "desired". */
  void onConnected();

  /** Pide reportar el estado y, si syncDesired, igualar tambiÃ©n "desired". */
  void requestReport(bool syncDesired);

  /** Procesa un mensaje. @return true si el tÃ³pico pertenece al Shadow. */
  bool handleMessage(const char *topic, const uint8_t *payload, unsigned int length);

  /** Llamar en cada loop(): envÃ­a las publicaciones pendientes. */
  void update();

 private:
  enum ReportMode { kNone = 0, kReportOnly = 1, kReportAndDesired = 2 };

  /** Aplica {"rojo":"on",...} a los LEDs. @return cantidad de LEDs modificados. */
  int applyLeds(JsonObjectConst leds);
  bool publishState(bool includeDesired);

  MqttManager &mqtt_;
  ActuatorController &actuators_;
  String topicUpdate_, topicGet_;
  String topicDelta_, topicUpdateAccepted_, topicGetAccepted_;
  String topicUpdateRejected_, topicGetRejected_;
  bool getPending_ = false;
  bool waitingGet_ = false;
  unsigned long getSentAt_ = 0;
  ReportMode report_ = kNone;
};

### `firmware/src/ShadowManager.cpp`
```cpp
#include "ShadowManager.h"

ShadowManager::ShadowManager(MqttManager &mqtt, ActuatorController &actuators,
                             const char *thingName)
    : mqtt_(mqtt), actuators_(actuators) {
  String base = String("$aws/things/") + thingName + "/shadow";
  topicUpdate_ = base + "/update";
  topicGet_ = base + "/get";
  topicDelta_ = base + "/update/delta";
  topicUpdateAccepted_ = base + "/update/accepted";
  topicGetAccepted_ = base + "/get/accepted";
  topicUpdateRejected_ = base + "/update/rejected";
  topicGetRejected_ = base + "/get/rejected";
}

void ShadowManager::registerSubscriptions(bool includeRejected) {
  mqtt_.addSubscription(topicDelta_, 0);
  mqtt_.addSubscription(topicUpdateAccepted_, 0);
  mqtt_.addSubscription(topicGetAccepted_, 0);
  if (includeRejected) {
    mqtt_.addSubscription(topicUpdateRejected_, 0);
    mqtt_.addSubscription(topicGetRejected_, 0);
  }
}

void ShadowManager::onConnected() {
  getPending_ = true;  // se publica en update(), fuera del callback de conexiÃ³n
  waitingGet_ = false;
}

void ShadowManager::requestReport(bool syncDesired) {
  if (syncDesired) {
    report_ = kReportAndDesired;
  } else if (report_ == kNone) {
    report_ = kReportOnly;
  }
}

int ShadowManager::applyLeds(JsonObjectConst leds) {
  int changed = 0;
  for (JsonPairConst kv : leds) {
    const char *value = kv.value().as<const char *>();
    if (value == nullptr) {
      continue;
    }
    String state = value;
    state.toLowerCase();
    if (state != "on" && state != "off") {
      Serial.printf("[SHADOW] Estado invalido para %s: %s\n", kv.key().c_str(), value);
      continue;
    }
    if (actuators_.setLed(String(kv.key().c_str()), state == "on")) {
      changed++;
    }
  }
  return changed;
}

bool ShadowManager::handleMessage(const char *topic, const uint8_t *payload,
                                  unsigned int length) {
  const char *data = reinterpret_cast<const char *>(payload);
  String t = topic;

  if (t == topicDelta_) {
    // Cambio deseado distinto del reportado: aplicar y reportar (no se toca desired).
    JsonDocument filter;
    filter["state"]["leds"] = true;
    JsonDocument doc;
    DeserializationError err =
        deserializeJson(doc, data, length, DeserializationOption::Filter(filter));
    if (err) {
      Serial.printf("[SHADOW] delta invalido: %s\n", err.c_str());
      return true;
    }
    int n = applyLeds(doc["state"]["leds"].as<JsonObjectConst>());
    Serial.printf("[SHADOW] delta aplicado (%d LED)\n", n);
    requestReport(false);  // reportar iguala reported con desired y elimina el delta
    return true;
  }

  if (t == topicGetAccepted_) {
    // Respuesta a get: recuperar el estado deseado tras un reinicio o reconexiÃ³n.
    JsonDocument filter;
    filter["state"]["desired"]["leds"] = true;
    JsonDocument doc;
    DeserializationError err =
        deserializeJson(doc, data, length, DeserializationOption::Filter(filter));
    waitingGet_ = false;
    if (err) {
      Serial.printf("[SHADOW] get/accepted invalido: %s\n", err.c_str());
    } else {
      JsonObjectConst desired = doc["state"]["desired"]["leds"].as<JsonObjectConst>();
      if (!desired.isNull()) {
        Serial.printf("[SHADOW] desired recuperado (%d LED)\n", applyLeds(desired));
      } else {
        Serial.println("[SHADOW] Sin 'desired' guardado; se reporta el estado actual");
      }
    }
    requestReport(false);
    return true;
  }

  if (t == topicUpdateAccepted_) {
    // ConfirmaciÃ³n de AWS. Solo se registra: responder aquÃ­ crearÃ­a un ciclo.
    Serial.println("[SHADOW] update aceptado por AWS");
    return true;
  }

  if (t == topicUpdateRejected_ || t == topicGetRejected_) {
    Serial.printf("[SHADOW] RECHAZADO en %s: %.*s\n", topic, (int)length, data);
    if (t == topicGetRejected_) {
      waitingGet_ = false;  // el Shadow aÃºn no existe (404): crearlo reportando
      requestReport(false);
    }
    return true;
  }
  return false;
}

bool ShadowManager::publishState(bool includeDesired) {
  JsonDocument doc;
  actuators_.fillState(doc["state"]["reported"]["leds"].to<JsonObject>());
  if (includeDesired) {
    actuators_.fillState(doc["state"]["desired"]["leds"].to<JsonObject>());
  }
  char buffer[256];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  if (n == 0 || n >= sizeof(buffer)) {
    Serial.println("[SHADOW] Documento demasiado grande");
    return true;  // no reintentar indefinidamente
  }
  return mqtt_.publish(topicUpdate_.c_str(), buffer);
}

void ShadowManager::update() {
  if (!mqtt_.connected()) {
    return;
  }
  unsigned long now = millis();

  if (getPending_ && mqtt_.publish(topicGet_.c_str(), "")) {
    getPending_ = false;
    waitingGet_ = true;
    getSentAt_ = now;
    Serial.println("[SHADOW] get solicitado");
  }
  // Si el Shadow no existe o get/accepted no llega, igualmente se reporta el estado.
  if (waitingGet_ && now - getSentAt_ >= SHADOW_GET_TIMEOUT_MS) {
    waitingGet_ = false;
    Serial.println("[SHADOW] get sin respuesta; se reporta el estado actual");
    requestReport(false);
  }
  if (report_ != kNone && publishState(report_ == kReportAndDesired)) {
    report_ = kNone;
  }
}

### `firmware/src/TimeSync.h`
```cpp
/**
 * @file TimeSync.h
 * @brief SincronizaciÃ³n de hora por NTP (no bloqueante).
 *
 * TLS valida las fechas de vigencia de los certificados. Sin hora correcta
 * (la ESP32 arranca en 1970) el handshake con AWS IoT falla, por lo que MQTT
 * no debe intentar conectarse hasta que synced() sea true.
 */
#pragma once
#include <Arduino.h>

class TimeSync {
 public:
  TimeSync(const char *server1, const char *server2);

  /** Llamar en cada loop(). Inicia NTP al haber WiFi y detecta cuÃ¡ndo hay hora vÃ¡lida. */
  void update(bool wifiUp);

  /** true cuando la hora del sistema es vÃ¡lida. */
  bool synced() const { return synced_; }

 private:
  const char *server1_;
  const char *server2_;
  bool started_ = false;
  bool synced_ = false;
};

### `firmware/src/TimeSync.cpp`
```cpp
#include "TimeSync.h"

#include <time.h>

// Cualquier valor posterior a nov-2023 indica que NTP ya fijÃ³ la hora.
static const time_t kMinValidEpoch = 1700000000;

TimeSync::TimeSync(const char *server1, const char *server2)
    : server1_(server1), server2_(server2) {}

void TimeSync::update(bool wifiUp) {
  if (wifiUp && !started_) {
    configTime(0, 0, server1_, server2_);  // UTC; solo importa para validar certificados
    started_ = true;
    Serial.println("[NTP] Sincronizando hora...");
  }
  if (started_ && !synced_ && time(nullptr) > kMinValidEpoch) {
    synced_ = true;
    Serial.printf("[NTP] Hora valida (epoch %ld)\n", (long)time(nullptr));
  }
}

### `firmware/src/UltrasonicSensor.h`
```cpp
/**
 * @file UltrasonicSensor.h
 * @brief MediciÃ³n de distancia con un sensor HC-SR04.
 */
#pragma once
#include <Arduino.h>

class UltrasonicSensor {
 public:
  /**
   * @param trigPin  Pin TRIG del sensor.
   * @param echoPin  Pin ECHO (con divisor de voltaje).
   * @param minCm    Distancia mÃ­nima vÃ¡lida.
   * @param maxCm    Distancia mÃ¡xima vÃ¡lida.
   * @param samples  Lecturas por mediciÃ³n; se devuelve la mediana.
   */
  UltrasonicSensor(uint8_t trigPin, uint8_t echoPin, float minCm, float maxCm,
                   uint8_t samples);

  /** Configura los pines. Llamar una vez en setup(). */
  void begin();

  /**
   * Mide la distancia (mediana de varias lecturas).
   * @param[out] cm Distancia en centÃ­metros.
   * @return true si la mediciÃ³n es vÃ¡lida.
   */
  bool measure(float &cm);

 private:
  enum { kMaxSamples = 9 };
  static const unsigned long kTimeoutUs = 30000UL;  // ~5 m de ida y vuelta

  float readOnce();

  uint8_t trigPin_;
  uint8_t echoPin_;
  float minCm_;
  float maxCm_;
  uint8_t samples_;
};

### `firmware/src/UltrasonicSensor.cpp`
```cpp
#include "UltrasonicSensor.h"

UltrasonicSensor::UltrasonicSensor(uint8_t trigPin, uint8_t echoPin, float minCm,
                                   float maxCm, uint8_t samples)
    : trigPin_(trigPin),
      echoPin_(echoPin),
      minCm_(minCm),
      maxCm_(maxCm),
      samples_(samples < 1 ? 1 : (samples > kMaxSamples ? kMaxSamples : samples)) {}

void UltrasonicSensor::begin() {
  pinMode(trigPin_, OUTPUT);
  pinMode(echoPin_, INPUT);
  digitalWrite(trigPin_, LOW);
}

float UltrasonicSensor::readOnce() {
  // Pulso de disparo de 10 us
  digitalWrite(trigPin_, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin_, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin_, LOW);

  unsigned long us = pulseIn(echoPin_, HIGH, kTimeoutUs);
  if (us == 0) {
    return NAN;  // sin eco (fuera de rango o desconectado)
  }
  // Velocidad del sonido ~0.0343 cm/us; el eco recorre ida y vuelta.
  float cm = us * 0.0343f / 2.0f;
  if (cm < minCm_ || cm > maxCm_) {
    return NAN;
  }
  return cm;
}

bool UltrasonicSensor::measure(float &cm) {
  float values[kMaxSamples];
  uint8_t n = 0;
  for (uint8_t i = 0; i < samples_; i++) {
    float v = readOnce();
    if (!isnan(v)) {
      values[n++] = v;
    }
    delay(10);  // evita que un eco se confunda con el siguiente disparo
  }
  if (n < samples_ / 2 + 1) {
    return false;  // demasiadas lecturas invÃ¡lidas
  }
  // Ordenamiento por inserciÃ³n (n es pequeÃ±o) y selecciÃ³n de la mediana
  for (uint8_t i = 1; i < n; i++) {
    float key = values[i];
    int j = i - 1;
    while (j >= 0 && values[j] > key) {
      values[j + 1] = values[j];
      j--;
    }
    values[j + 1] = key;
  }
  cm = values[n / 2];
  return true;
}

### `firmware/src/WifiManager.h`
```cpp
/**
 * @file WifiManager.h
 * @brief ConexiÃ³n Wi-Fi con reconexiÃ³n automÃ¡tica y NO bloqueante.
 */
#pragma once
#include <Arduino.h>
#include <WiFi.h>

class WifiManager {
 public:
  WifiManager(const char *ssid, const char *password, unsigned long retryMs);

  /** Configura el modo estaciÃ³n. Llamar una vez en setup(). */
  void begin();

  /**
   * Debe llamarse en cada loop(). Reintenta la conexiÃ³n cada retryMs si se cayÃ³.
   * @return true si hay conexiÃ³n Wi-Fi.
   */
  bool update();

 private:
  const char *ssid_;
  const char *password_;
  unsigned long retryMs_;
  unsigned long lastAttempt_ = 0;
  bool wasConnected_ = false;
};

### `firmware/src/WifiManager.cpp`
```cpp
#include "WifiManager.h"

WifiManager::WifiManager(const char *ssid, const char *password, unsigned long retryMs)
    : ssid_(ssid), password_(password), retryMs_(retryMs) {}

void WifiManager::begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
}

bool WifiManager::update() {
  bool connected = (WiFi.status() == WL_CONNECTED);

  if (connected != wasConnected_) {
    wasConnected_ = connected;
    if (connected) {
      Serial.printf("[WIFI] Conectado, IP %s\n", WiFi.localIP().toString().c_str());
    } else {
      Serial.println("[WIFI] Conexion perdida");
    }
  }
  if (connected) {
    return true;
  }

  unsigned long now = millis();
  if (lastAttempt_ == 0 || now - lastAttempt_ >= retryMs_) {
    lastAttempt_ = now;
    Serial.printf("[WIFI] Conectando a %s...\n", ssid_);
    WiFi.disconnect();
    WiFi.begin(ssid_, password_);
  }
  return false;
}

### `mcp-server/pyproject.toml`
```toml
[project]
name = "smart-object"
version = "0.2.0"
description = "Servidor MCP que conecta Claude Desktop con un ESP32 vÃ­a AWS IoT Core (MQTT/TLS + Device Shadow)"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=2.0.0",
    "paho-mqtt>=2.1.0",
]

### `mcp-server/.env.example`
```text
# Copia como ".env" (excluido de Git). Las rutas relativas parten de la carpeta mcp-server/.

# --- AWS IoT Core ---
AWS_IOT_ENDPOINT=ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com
AWS_IOT_PORT=8883
AWS_THING_NAME=esp32-sis234

# --- Identidad MQTT PROPIA del servidor (NO la del ESP32) ---
# El Client ID debe estar autorizado en la polÃ­tica del servidor (client/mcp-sis234).
MQTT_CLIENT_ID=mcp-sis234
AWS_CA_PATH=certs/AmazonRootCA1.pem
AWS_CERT_PATH=certs/mcp-certificate.pem.crt
AWS_KEY_PATH=certs/mcp-private.pem.key

# --- TÃ³picos (deben coincidir con las polÃ­ticas AWS) ---
TOPIC_DISTANCE=sis234/esp32/distancia
TOPIC_COMMAND=sis234/esp32/comandos

LED_COLORS=rojo,verde,amarillo
STALE_AFTER_S=5
CONFIRM_TIMEOUT_S=3

# --- Device Shadow ---
# Pon false si la polÃ­tica del servidor NO incluye permisos de Shadow.
SHADOW_ENABLED=true
# Pon true solo tras aÃ±adir update/rejected y get/rejected a la polÃ­tica del servidor.
SHADOW_SUBSCRIBE_REJECTED=false

### `mcp-server/aws_iot_bridge.py`
```python
"""Puente MQTT/TLS hacia AWS IoT Core para el servidor MCP (SIS-234).

Este mÃ³dulo contiene TODA la lÃ³gica de comunicaciÃ³n y es importable y
comprobable sin hardware ni red (el cliente MQTT se inyecta mediante
``client_factory``).

Conceptos clave
---------------
* **Comando enviado** != **estado confirmado.**  Publicar en MQTT solo prueba que
  AWS aceptÃ³ el mensaje. El ESP32 confirma tras aplicar el comando publicando su
  estado en el Device Shadow (``shadow/update/accepted``). ``send_led_commands``
  distingue ambos casos.
* La identidad MQTT del servidor es INDEPENDIENTE de la del ESP32: su propio
  certificado, clave, Client ID (``mcp-sis234``) y polÃ­tica.
* Nunca se usa ``print()``: el transporte MCP stdio usa stdout; se registra con
  ``logging`` (stderr).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger("smart-object.bridge")


# --------------------------------------------------------------------------- #
# ConfiguraciÃ³n
# --------------------------------------------------------------------------- #
def load_dotenv(path: Path) -> None:
    """Carga CLAVE=valor de un .env sin pisar variables ya definidas."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "si", "sÃ­"}


@dataclass(frozen=True)
class Settings:
    """ParÃ¡metros del servidor. Los tÃ³picos deben coincidir con la polÃ­tica AWS."""

    endpoint: str
    port: int
    thing_name: str
    client_id: str
    ca_path: Path
    cert_path: Path
    key_path: Path
    keepalive: int
    topic_distance: str
    topic_command: str
    leds: tuple[str, ...]
    stale_after_s: float
    confirm_timeout_s: float
    shadow_enabled: bool
    shadow_rejected: bool

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "Settings":
        base = base_dir or Path(__file__).resolve().parent
        load_dotenv(base / ".env")

        def path(name: str, default: str) -> Path:
            p = Path(os.environ.get(name, default)).expanduser()
            return p if p.is_absolute() else base / p

        return cls(
            endpoint=os.environ.get("AWS_IOT_ENDPOINT", "").strip(),
            port=int(os.environ.get("AWS_IOT_PORT", "8883")),
            thing_name=os.environ.get("AWS_THING_NAME", "esp32-sis234"),
            client_id=os.environ.get("MQTT_CLIENT_ID", "mcp-sis234"),
            ca_path=path("AWS_CA_PATH", "certs/AmazonRootCA1.pem"),
            cert_path=path("AWS_CERT_PATH", "certs/mcp-certificate.pem.crt"),
            key_path=path("AWS_KEY_PATH", "certs/mcp-private.pem.key"),
            keepalive=int(os.environ.get("MQTT_KEEPALIVE", "60")),
            topic_distance=os.environ.get("TOPIC_DISTANCE", "sis234/esp32/distancia"),
            topic_command=os.environ.get("TOPIC_COMMAND", "sis234/esp32/comandos"),
            leds=tuple(
                c.strip().lower()
                for c in os.environ.get("LED_COLORS", "rojo,verde,amarillo").split(",")
                if c.strip()
            ),
            stale_after_s=float(os.environ.get("STALE_AFTER_S", "5")),
            confirm_timeout_s=float(os.environ.get("CONFIRM_TIMEOUT_S", "3")),
            shadow_enabled=_env_bool("SHADOW_ENABLED", True),
            shadow_rejected=_env_bool("SHADOW_SUBSCRIBE_REJECTED", False),
        )

    # -- tÃ³picos del Device Shadow clÃ¡sico (sin nombre) ---------------------- #
    @property
    def shadow_base(self) -> str:
        return f"$aws/things/{self.thing_name}/shadow"

    @property
    def topic_shadow_get(self) -> str:
        return f"{self.shadow_base}/get"

    @property
    def topic_shadow_get_accepted(self) -> str:
        return f"{self.shadow_base}/get/accepted"

    @property
    def topic_shadow_get_rejected(self) -> str:
        return f"{self.shadow_base}/get/rejected"

    @property
    def topic_shadow_update_accepted(self) -> str:
        return f"{self.shadow_base}/update/accepted"

    @property
    def topic_shadow_update_rejected(self) -> str:
        return f"{self.shadow_base}/update/rejected"

    def problems(self) -> list[str]:
        """Lista de problemas de configuraciÃ³n (vacÃ­a si todo estÃ¡ bien)."""
        found: list[str] = []
        if not self.endpoint:
            found.append("Falta AWS_IOT_ENDPOINT (endpoint de AWS IoT Core).")
        for label, p in (("CA raÃ­z", self.ca_path), ("certificado", self.cert_path),
                         ("clave privada", self.key_path)):
            if not p.is_file():
                found.append(f"No existe el archivo de {label}: {p}")
        return found


# --------------------------------------------------------------------------- #
# Modelos de datos
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reading:
    cm: float
    received_at: float


@dataclass(frozen=True)
class LedReport:
    """Ãšltimo estado de un LED reportado por el dispositivo (confirmaciÃ³n real)."""

    state: str
    received_at: float


@dataclass(frozen=True)
class ShadowSnapshot:
    reported: dict
    desired: dict
    delta: dict
    version: int | None
    received_at: float


@dataclass(frozen=True)
class LedResult:
    """Resultado de pedir un cambio de LED: enviado y/o confirmado."""

    color: str
    requested: str
    sent: bool
    confirmed: bool
    detail: str = ""


# --------------------------------------------------------------------------- #
# Utilidades de normalizaciÃ³n
# --------------------------------------------------------------------------- #
_COLOR_ALIASES = {"red": "rojo", "green": "verde", "yellow": "amarillo"}
_STATE_ON = {"on", "encender", "enciende", "prender", "prende", "1", "true"}
_STATE_OFF = {"off", "apagar", "apaga", "0", "false"}


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).strip().lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_color(color: str, valid: tuple[str, ...]) -> str | None:
    value = _COLOR_ALIASES.get(_clean(color), _clean(color))
    return value if value in valid else None


def normalize_state(state: str) -> str | None:
    value = _clean(state)
    if value in _STATE_ON:
        return "on"
    if value in _STATE_OFF:
        return "off"
    return None


def parse_distance(payload: bytes) -> float | None:
    """Extrae los cm de ``{"cm": 42.7}``; tambiÃ©n acepta un nÃºmero suelto."""
    try:
        data = json.loads(payload.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return None
    value = data.get("cm") if isinstance(data, dict) else data
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# --------------------------------------------------------------------------- #
# Puente MQTT
# --------------------------------------------------------------------------- #
def default_client_factory(settings: Settings):
    """Crea el cliente Paho con TLS mutuo (importaciÃ³n diferida para poder probar sin Paho)."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.client_id,
    )
    client.tls_set(
        ca_certs=str(settings.ca_path),
        certfile=str(settings.cert_path),
        keyfile=str(settings.key_path),
    )
    return client


class AwsIotBridge:
    """Cliente MQTT/TLS en segundo plano con estado compartido y thread-safe."""

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], object] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._s = settings
        self._clock = clock
        self._cond = threading.Condition()
        self._connected = False
        self._distance: Reading | None = None
        self._led_reports: dict[str, LedReport] = {}
        self._snapshot: ShadowSnapshot | None = None
        self._snapshot_seq = 0
        self._shadow_error: str | None = None

        self._client = client_factory(settings)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_subscribe = self._on_subscribe
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    # -- ciclo de vida ------------------------------------------------------ #
    def start(self) -> None:
        logger.info("Conectando a AWS IoT %s:%d como '%s'", self._s.endpoint, self._s.port,
                    self._s.client_id)
        self._client.connect_async(self._s.endpoint, self._s.port, self._s.keepalive)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # -- suscripciones ------------------------------------------------------ #
    def subscription_topics(self) -> list[str]:
        topics = [self._s.topic_distance]
        if self._s.shadow_enabled:
            topics += [self._s.topic_shadow_update_accepted, self._s.topic_shadow_get_accepted]
            if self._s.shadow_rejected:
                topics += [self._s.topic_shadow_update_rejected,
                           self._s.topic_shadow_get_rejected]
        return topics

    # -- callbacks de Paho (VERSION2) --------------------------------------- #
    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if getattr(reason_code, "is_failure", False):
            logger.error("AWS IoT rechazÃ³ la conexiÃ³n: %s (Â¿polÃ­tica o certificado?)", reason_code)
            return
        logger.info("Conectado a AWS IoT Core")
        with self._cond:
            self._connected = True
            self._cond.notify_all()
        # Suscribir en CADA conexiÃ³n garantiza la re-suscripciÃ³n tras una reconexiÃ³n.
        for topic in self.subscription_topics():
            client.subscribe(topic, qos=0)

    def _on_disconnect(self, client, userdata, *args) -> None:
        with self._cond:
            self._connected = False
            self._cond.notify_all()
        logger.warning("Desconectado de AWS IoT; Paho reintentarÃ¡ automÃ¡ticamente")

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None) -> None:
        for rc in reason_codes or []:
            if getattr(rc, "is_failure", False):
                logger.error("SuscripciÃ³n rechazada (%s). Revisa la polÃ­tica del servidor.", rc)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            self.handle_message(msg.topic, bytes(msg.payload))
        except Exception:  # un mensaje malo no debe tumbar el hilo de red
            logger.exception("Error procesando mensaje en %s", msg.topic)

    # -- procesamiento de mensajes (lÃ³gica pura, probada en tests) ---------- #
    def handle_message(self, topic: str, payload: bytes) -> None:
        s = self._s
        now = self._clock()
        if topic == s.topic_distance:
            cm = parse_distance(payload)
            if cm is None:
                logger.warning("Distancia invÃ¡lida: %r", payload[:60])
                return
            with self._cond:
                self._distance = Reading(cm, now)
            return

        if topic in (s.topic_shadow_update_rejected, s.topic_shadow_get_rejected):
            logger.warning("Shadow rechazado en %s: %r", topic, payload[:200])
            with self._cond:
                self._shadow_error = f"AWS rechazÃ³ la operaciÃ³n Shadow ({topic.rsplit('/', 2)[-2]})"
                self._cond.notify_all()
            return

        if topic not in (s.topic_shadow_update_accepted, s.topic_shadow_get_accepted):
            return
        try:
            doc = json.loads(payload.decode("utf-8", errors="replace"))
            state = doc.get("state", {}) if isinstance(doc, dict) else {}
        except json.JSONDecodeError:
            logger.warning("JSON invÃ¡lido en %s", topic)
            return

        def leds_of(section: str) -> dict:
            leds = (state.get(section) or {}).get("leds") if isinstance(state, dict) else None
            return {k: v for k, v in leds.items() if isinstance(v, str)} if isinstance(leds, dict) else {}

        with self._cond:
            if topic == s.topic_shadow_update_accepted:
                # Lo reportado por el dispositivo = confirmaciÃ³n fÃ­sica del cambio.
                for color, value in leds_of("reported").items():
                    self._led_reports[color] = LedReport(value, now)
            else:
                self._snapshot = ShadowSnapshot(
                    reported=leds_of("reported"),
                    desired=leds_of("desired"),
                    delta=leds_of("delta"),
                    version=doc.get("version") if isinstance(doc, dict) else None,
                    received_at=now,
                )
                self._snapshot_seq += 1
                self._shadow_error = None
            self._cond.notify_all()

    # -- consultas ---------------------------------------------------------- #
    @property
    def connected(self) -> bool:
        with self._cond:
            return self._connected

    def last_distance(self) -> tuple[Reading | None, float | None]:
        with self._cond:
            reading = self._distance
        if reading is None:
            return None, None
        return reading, self._clock() - reading.received_at

    def led_reports(self) -> dict[str, tuple[str, float]]:
        """Ãšltimo estado reportado por el ESP32 por LED: {color: (estado, antigÃ¼edad_s)}."""
        now = self._clock()
        with self._cond:
            return {c: (r.state, now - r.received_at) for c, r in self._led_reports.items()}

    # -- publicaciÃ³n -------------------------------------------------------- #
    def _publish(self, topic: str, payload: str) -> tuple[bool, str]:
        if not self.connected:
            return False, "No hay conexiÃ³n con AWS IoT Core."
        info = self._client.publish(topic, payload, qos=1)
        rc = getattr(info, "rc", 0)
        if rc != 0:
            logger.error("Fallo al publicar en %s (cÃ³digo %s)", topic, rc)
            return False, f"Error al publicar (cÃ³digo MQTT {rc})."
        logger.info("Publicado en %s: %s", topic, payload)
        return True, payload

    def publish_command(self, color: str, state: str) -> tuple[bool, str]:
        """Publica un comando de LED (solo 'enviado', NO confirma nada)."""
        payload = json.dumps({"led": color, "estado": state}, separators=(",", ":"))
        return self._publish(self._s.topic_command, payload)

    def send_led_commands(
        self, changes: list[tuple[str, str]], timeout_s: float | None = None
    ) -> list[LedResult]:
        """EnvÃ­a cambios de LED y espera la confirmaciÃ³n del dispositivo.

        Un cambio queda *confirmado* solo si el ESP32 reporta, DESPUÃ‰S del envÃ­o,
        el estado pedido en el Shadow. Si no llega a tiempo, queda "enviado sin confirmar".
        """
        timeout = self._s.confirm_timeout_s if timeout_s is None else timeout_s
        t0 = self._clock()
        results: dict[str, LedResult] = {}
        for color, state in changes:
            ok, detail = self.publish_command(color, state)
            results[color] = LedResult(color, state, ok, False, "" if ok else detail)

        if not self._s.shadow_enabled:
            return list(results.values())  # sin Shadow no hay forma de confirmar

        deadline = t0 + timeout

        def satisfied(color: str, state: str) -> bool:
            rep = self._led_reports.get(color)
            return rep is not None and rep.state == state and rep.received_at >= t0

        with self._cond:
            pending = {c: r for c, r in results.items() if r.sent}
            while pending:
                for color in [c for c, r in pending.items() if satisfied(c, r.requested)]:
                    results[color] = LedResult(color, pending[color].requested, True, True)
                    del pending[color]
                remaining = deadline - self._clock()
                if not pending or remaining <= 0:
                    break
                self._cond.wait(remaining)
        return [results[c] for c, _ in changes]

    def request_shadow(self, timeout_s: float = 4.0) -> tuple[ShadowSnapshot | None, str]:
        """Consulta el Shadow (publica en shadow/get y espera get/accepted)."""
        if not self._s.shadow_enabled:
            return None, "El Shadow estÃ¡ deshabilitado (SHADOW_ENABLED=false)."
        with self._cond:
            seq0 = self._snapshot_seq
            self._shadow_error = None
        ok, detail = self._publish(self._s.topic_shadow_get, "")
        if not ok:
            return None, detail
        deadline = self._clock() + timeout_s
        with self._cond:
            while self._snapshot_seq == seq0 and self._shadow_error is None:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    return None, "AWS no respondiÃ³ a tiempo (Â¿el Shadow aÃºn no existe o falta permiso?)."
                self._cond.wait(remaining)
            if self._shadow_error:
                return None, self._shadow_error
            return self._snapshot, ""

### `mcp-server/smart-object.py`
```python
#!/usr/bin/env python3
"""Servidor MCP del objeto inteligente (SIS-234) sobre AWS IoT Core.

    Claude Desktop <--MCP/stdio--> este servidor <--MQTT/TLS--> AWS IoT Core <--> ESP32

La lÃ³gica de red vive en ``aws_iot_bridge.py``; aquÃ­ solo se declaran las
herramientas MCP y se da formato a sus respuestas.

IMPORTANTE: el transporte es stdio, por lo que NUNCA se debe usar ``print()``
(corrompe el protocolo). Todo log sale por ``logging`` hacia stderr.
"""

from __future__ import annotations

import logging
import os
import sys

from aws_iot_bridge import (
    AwsIotBridge,
    LedResult,
    Settings,
    normalize_color,
    normalize_state,
)

# MCP SDK 2.x expone MCPServer; versiones anteriores y el paquete "fastmcp" exponen FastMCP.
try:
    from mcp.server import MCPServer as ServerClass
except ImportError:  # pragma: no cover - depende de la versiÃ³n instalada
    try:
        from mcp.server.fastmcp import FastMCP as ServerClass
    except ImportError:
        from fastmcp import FastMCP as ServerClass

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smart-object")


def format_results(results: list[LedResult], timeout_s: float) -> str:
    """Texto que distingue 'enviado' de 'confirmado por el dispositivo'."""
    lines = []
    for r in results:
        if not r.sent:
            lines.append(f"- {r.color} -> {r.requested.upper()}: NO ENVIADO ({r.detail})")
        elif r.confirmed:
            lines.append(f"- {r.color} -> {r.requested.upper()}: CONFIRMADO por el ESP32")
        else:
            lines.append(
                f"- {r.color} -> {r.requested.upper()}: enviado, SIN confirmar "
                f"(el ESP32 no reportÃ³ el cambio en {timeout_s:g} s)"
            )
    if any(r.sent and not r.confirmed for r in results):
        lines.append(
            "Aviso: 'enviado' solo significa que AWS aceptÃ³ el mensaje; no se puede asegurar "
            "que el LED haya cambiado fÃ­sicamente."
        )
    return "\n".join(lines)


def create_server(settings: Settings, bridge: AwsIotBridge) -> ServerClass:
    """Construye el servidor MCP y registra sus herramientas."""
    mcp = ServerClass("smart-object")
    colors_txt = ", ".join(settings.leds)

    @mcp.tool()
    def get_distance() -> str:
        """Devuelve la Ãºltima distancia vÃ¡lida (en cm) medida por el sensor ultrasÃ³nico
        del objeto inteligente, con su antigÃ¼edad. Ãšsala cuando pregunten a quÃ©
        distancia estÃ¡ el objeto."""
        reading, age = bridge.last_distance()
        if reading is None:
            return ("AÃºn no se recibiÃ³ ninguna lectura. Verifica que el ESP32 estÃ© encendido "
                    f"y conectado (conexiÃ³n con AWS IoT: {'sÃ­' if bridge.connected else 'NO'}).")
        text = f"Distancia: {reading.cm:.1f} cm (lectura de hace {age:.1f} s)."
        if age > settings.stale_after_s:
            text += " Aviso: la lectura es antigua; el ESP32 podrÃ­a estar desconectado."
        return text

    @mcp.tool()
    def get_system_status() -> str:
        """Informa la conexiÃ³n con AWS IoT Core, la antigÃ¼edad de la Ãºltima lectura del
        sensor y el Ãºltimo estado de los LEDs reportado por el dispositivo."""
        reading, age = bridge.last_distance()
        if reading is None:
            sensor = "sin lecturas"
        else:
            fresh = "al dÃ­a" if age <= settings.stale_after_s else "ANTIGUA"
            sensor = f"{reading.cm:.1f} cm, hace {age:.1f} s ({fresh})"
        reports = bridge.led_reports()
        leds = ", ".join(f"{c}={s} (hace {a:.0f} s)" for c, (s, a) in sorted(reports.items()))
        return (
            f"AWS IoT Core: {'conectado' if bridge.connected else 'DESCONECTADO'} "
            f"({settings.endpoint}). Sensor: {sensor}. "
            f"LEDs reportados por el dispositivo: {leds or 'ninguno aÃºn'}."
        )

    @mcp.tool()
    def set_led(color: str, state: str) -> str:
        """Enciende o apaga UN LED sin tocar los demÃ¡s y espera la confirmaciÃ³n del ESP32.

        Args:
            color: rojo, verde o amarillo.
            state: "on" para encender, "off" para apagar.
        """
        led = normalize_color(color, settings.leds)
        if led is None:
            return f"Color no vÃ¡lido: '{color}'. Opciones: {colors_txt}."
        value = normalize_state(state)
        if value is None:
            return f"Estado no vÃ¡lido: '{state}'. Usa 'on' u 'off'."
        return format_results(bridge.send_led_commands([(led, value)]), settings.confirm_timeout_s)

    @mcp.tool()
    def only_led(color: str) -> str:
        """Enciende SOLO el LED indicado y apaga los demÃ¡s ("enciende el rojo y apaga los
        demÃ¡s"). Espera la confirmaciÃ³n del ESP32.

        Args:
            color: rojo, verde o amarillo.
        """
        target = normalize_color(color, settings.leds)
        if target is None:
            return f"Color no vÃ¡lido: '{color}'. Opciones: {colors_txt}."
        changes = [(c, "off") for c in settings.leds if c != target] + [(target, "on")]
        return format_results(bridge.send_led_commands(changes), settings.confirm_timeout_s)

    @mcp.tool()
    def all_leds_on() -> str:
        """Enciende todos los LEDs y espera la confirmaciÃ³n del ESP32."""
        changes = [(c, "on") for c in settings.leds]
        return format_results(bridge.send_led_commands(changes), settings.confirm_timeout_s)

    @mcp.tool()
    def all_leds_off() -> str:
        """Apaga todos los LEDs y espera la confirmaciÃ³n del ESP32."""
        changes = [(c, "off") for c in settings.leds]
        return format_results(bridge.send_led_commands(changes), settings.confirm_timeout_s)

    if settings.shadow_enabled:

        @mcp.tool()
        def get_shadow_state() -> str:
            """Consulta en AWS el Device Shadow del objeto: estado de los LEDs reportado
            por el dispositivo (reported), el deseado (desired) y las diferencias (delta).
            Requiere permisos de Shadow en la polÃ­tica del servidor."""
            snap, error = bridge.request_shadow()
            if snap is None:
                return f"No se pudo leer el Shadow: {error}"
            delta = snap.delta or "ninguna (reported = desired)"
            return (f"Shadow (versiÃ³n {snap.version}): reported={snap.reported}, "
                    f"desired={snap.desired}, diferencias pendientes={delta}.")

    return mcp


def main() -> None:
    settings = Settings.from_env()
    problems = settings.problems()
    if problems:
        for p in problems:
            logger.error(p)
        logger.error("Corrige la configuraciÃ³n (ver mcp-server/README.md y docs/AWS_CONFIGURACION.md).")
        sys.exit(1)

    bridge = AwsIotBridge(settings)
    server = create_server(settings, bridge)
    bridge.start()
    try:
        server.run(transport="stdio")  # bloquea: el servidor corre todo el tiempo
    except KeyboardInterrupt:
        logger.info("Interrumpido, cerrando.")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()

### `mcp-server/tests/__init__.py`
```python


### `mcp-server/tests/test_bridge.py`
```python
"""Pruebas de aws_iot_bridge.py sin red ni hardware (cliente MQTT simulado).

Ejecutar desde mcp-server/:   python -m unittest discover -s tests -v
"""

import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aws_iot_bridge import (  # noqa: E402
    AwsIotBridge,
    Settings,
    normalize_color,
    normalize_state,
    parse_distance,
)


class FakeReason:
    def __init__(self, failure=False):
        self.is_failure = failure


class FakeInfo:
    rc = 0


class FakeClient:
    """Sustituye a paho.mqtt.client.Client: registra lo que el puente hace."""

    def __init__(self):
        self.published = []  # (topic, payload, qos)
        self.subscribed = []
        self.on_publish_hook = None
        self.rc = 0

    def reconnect_delay_set(self, **kw):
        pass

    def connect_async(self, *a):
        self.connect_args = a

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        if self.on_publish_hook:
            self.on_publish_hook(topic, payload)
        info = FakeInfo()
        info.rc = self.rc
        return info


def make_settings(**over):
    base = dict(
        endpoint="example-ats.iot.us-east-2.amazonaws.com", port=8883, thing_name="esp32-sis234",
        client_id="mcp-sis234", ca_path=Path("ca"), cert_path=Path("crt"), key_path=Path("key"),
        keepalive=60, topic_distance="sis234/esp32/distancia",
        topic_command="sis234/esp32/comandos", leds=("rojo", "verde", "amarillo"),
        stale_after_s=5.0, confirm_timeout_s=0.3, shadow_enabled=True, shadow_rejected=False,
    )
    base.update(over)
    return Settings(**base)


def make_bridge(**over):
    client = FakeClient()
    s = make_settings(**over)
    bridge = AwsIotBridge(s, client_factory=lambda _s: client)
    return bridge, client, s


def connect(bridge, client):
    bridge._on_connect(client, None, None, FakeReason(False), None)


def accepted(s, leds):
    return json.dumps({"state": {"reported": {"leds": leds}}, "version": 7}).encode()


class TestHelpers(unittest.TestCase):
    def test_parse_distance(self):
        self.assertEqual(parse_distance(b'{"cm":42.7}'), 42.7)
        self.assertEqual(parse_distance(b"15"), 15.0)
        self.assertIsNone(parse_distance(b"hola"))
        self.assertIsNone(parse_distance(b'{"x":1}'))
        self.assertIsNone(parse_distance(b'{"cm":"abc"}'))
        self.assertIsNone(parse_distance(b"true"))

    def test_normalize(self):
        valid = ("rojo", "verde", "amarillo")
        self.assertEqual(normalize_color("Rojo", valid), "rojo")
        self.assertEqual(normalize_color("yellow", valid), "amarillo")
        self.assertIsNone(normalize_color("azul", valid))
        self.assertEqual(normalize_state("Enciende"), "on")
        self.assertEqual(normalize_state("OFF"), "off")
        self.assertIsNone(normalize_state("quizÃ¡s"))


class TestConnection(unittest.TestCase):
    def test_subscribes_on_every_connection(self):
        """ReconexiÃ³n: tras caer y volver, debe re-suscribirse a los mismos tÃ³picos."""
        bridge, client, s = make_bridge()
        connect(bridge, client)
        first = list(client.subscribed)
        self.assertIn(s.topic_distance, first)
        self.assertIn(s.topic_shadow_update_accepted, first)
        self.assertIn(s.topic_shadow_get_accepted, first)
        self.assertNotIn(s.topic_shadow_update_rejected, first)  # opcional, desactivado

        bridge._on_disconnect(client, None, None, FakeReason(), None)
        self.assertFalse(bridge.connected)
        connect(bridge, client)
        self.assertTrue(bridge.connected)
        self.assertEqual(client.subscribed, first + first)

    def test_rejected_topics_only_when_enabled(self):
        bridge, client, s = make_bridge(shadow_rejected=True)
        connect(bridge, client)
        self.assertIn(s.topic_shadow_get_rejected, client.subscribed)

    def test_shadow_disabled_does_not_subscribe_to_shadow(self):
        bridge, client, s = make_bridge(shadow_enabled=False)
        connect(bridge, client)
        self.assertEqual(client.subscribed, [s.topic_distance])

    def test_failed_connect_does_not_mark_connected(self):
        bridge, client, _ = make_bridge()
        bridge._on_connect(client, None, None, FakeReason(True), None)
        self.assertFalse(bridge.connected)
        self.assertEqual(client.subscribed, [])


class TestPublishing(unittest.TestCase):
    def test_publish_fails_when_disconnected(self):
        bridge, client, _ = make_bridge()
        ok, detail = bridge.publish_command("rojo", "on")
        self.assertFalse(ok)
        self.assertEqual(client.published, [])
        self.assertIn("conexiÃ³n", detail)

    def test_publish_command_format_topic_and_qos(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)
        ok, _ = bridge.publish_command("rojo", "on")
        self.assertTrue(ok)
        topic, payload, qos = client.published[0]
        self.assertEqual(topic, s.topic_command)
        self.assertEqual(json.loads(payload), {"led": "rojo", "estado": "on"})
        self.assertEqual(qos, 1)  # AWS IoT solo admite QoS 0 y 1

    def test_publish_error_code_is_reported(self):
        bridge, client, _ = make_bridge()
        connect(bridge, client)
        client.rc = 4
        ok, detail = bridge.publish_command("rojo", "on")
        self.assertFalse(ok)
        self.assertIn("4", detail)


class TestIncomingMessages(unittest.TestCase):
    def test_distance_stored(self):
        bridge, client, s = make_bridge()
        self.assertEqual(bridge.last_distance(), (None, None))
        bridge.handle_message(s.topic_distance, b'{"cm":42.7}')
        reading, age = bridge.last_distance()
        self.assertEqual(reading.cm, 42.7)
        self.assertGreaterEqual(age, 0)

    def test_invalid_distance_keeps_previous_value(self):
        bridge, _, s = make_bridge()
        bridge.handle_message(s.topic_distance, b'{"cm":10}')
        bridge.handle_message(s.topic_distance, b"basura")
        self.assertEqual(bridge.last_distance()[0].cm, 10.0)

    def test_update_accepted_records_reported_leds(self):
        bridge, _, s = make_bridge()
        bridge.handle_message(s.topic_shadow_update_accepted, accepted(s, {"rojo": "on"}))
        self.assertEqual(bridge.led_reports()["rojo"][0], "on")

    def test_malformed_shadow_json_is_ignored(self):
        bridge, _, s = make_bridge()
        bridge.handle_message(s.topic_shadow_update_accepted, b"{no es json")
        self.assertEqual(bridge.led_reports(), {})


class TestCommandConfirmation(unittest.TestCase):
    def test_confirmed_when_device_reports(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def device(topic, payload):  # el ESP32 simulado confirma por el Shadow
            if topic == s.topic_command:
                cmd = json.loads(payload)
                threading.Timer(0.05, bridge.handle_message, (
                    s.topic_shadow_update_accepted, accepted(s, {cmd["led"]: cmd["estado"]}))).start()

        client.on_publish_hook = device
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=1.0)
        self.assertTrue(res[0].sent)
        self.assertTrue(res[0].confirmed)

    def test_sent_but_not_confirmed_on_timeout(self):
        bridge, client, _ = make_bridge()
        connect(bridge, client)
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.1)
        self.assertTrue(res[0].sent)
        self.assertFalse(res[0].confirmed)  # MQTT aceptÃ³, pero nadie confirmÃ³

    def test_old_report_does_not_confirm_new_command(self):
        """Un 'on' reportado ANTES de enviar no puede confirmar un comando nuevo."""
        bridge, client, s = make_bridge()
        connect(bridge, client)
        bridge.handle_message(s.topic_shadow_update_accepted, accepted(s, {"rojo": "on"}))
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.1)
        self.assertFalse(res[0].confirmed)

    def test_wrong_state_report_does_not_confirm(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def device(topic, payload):
            if topic == s.topic_command:
                threading.Timer(0.02, bridge.handle_message,
                                (s.topic_shadow_update_accepted, accepted(s, {"rojo": "off"}))).start()

        client.on_publish_hook = device
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.2)
        self.assertFalse(res[0].confirmed)

    def test_not_sent_when_disconnected(self):
        bridge, client, _ = make_bridge()
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.1)
        self.assertFalse(res[0].sent)
        self.assertFalse(res[0].confirmed)

    def test_multiple_leds_confirmed_individually(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def device(topic, payload):
            if topic == s.topic_command:
                cmd = json.loads(payload)
                if cmd["led"] != "verde":  # el verde nunca responde
                    threading.Timer(0.02, bridge.handle_message, (
                        s.topic_shadow_update_accepted, accepted(s, {cmd["led"]: cmd["estado"]}))).start()

        client.on_publish_hook = device
        res = bridge.send_led_commands([("rojo", "on"), ("verde", "off"), ("amarillo", "off")], 0.4)
        by = {r.color: r for r in res}
        self.assertTrue(by["rojo"].confirmed)
        self.assertTrue(by["amarillo"].confirmed)
        self.assertFalse(by["verde"].confirmed)
        self.assertEqual([r.color for r in res], ["rojo", "verde", "amarillo"])  # orden conservado


class TestShadow(unittest.TestCase):
    def get_accepted_payload(self):
        return json.dumps({"state": {"desired": {"leds": {"rojo": "on"}},
                                     "reported": {"leds": {"rojo": "off"}},
                                     "delta": {"leds": {"rojo": "on"}}},
                           "version": 12}).encode()

    def test_request_shadow_success(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def aws(topic, payload):
            if topic == s.topic_shadow_get:
                threading.Timer(0.03, bridge.handle_message,
                                (s.topic_shadow_get_accepted, self.get_accepted_payload())).start()

        client.on_publish_hook = aws
        snap, err = bridge.request_shadow(timeout_s=1.0)
        self.assertEqual(err, "")
        self.assertEqual(snap.version, 12)
        self.assertEqual(snap.desired, {"rojo": "on"})
        self.assertEqual(snap.reported, {"rojo": "off"})
        self.assertEqual(snap.delta, {"rojo": "on"})
        self.assertEqual(client.published[0][0], s.topic_shadow_get)

    def test_request_shadow_timeout(self):
        bridge, client, _ = make_bridge()
        connect(bridge, client)
        snap, err = bridge.request_shadow(timeout_s=0.1)
        self.assertIsNone(snap)
        self.assertIn("no respondiÃ³", err)

    def test_request_shadow_rejected(self):
        bridge, client, s = make_bridge(shadow_rejected=True)
        connect(bridge, client)

        def aws(topic, payload):
            if topic == s.topic_shadow_get:
                threading.Timer(0.02, bridge.handle_message, (
                    s.topic_shadow_get_rejected, b'{"code":404,"message":"No shadow exists"}')).start()

        client.on_publish_hook = aws
        snap, err = bridge.request_shadow(timeout_s=1.0)
        self.assertIsNone(snap)
        self.assertIn("rechazÃ³", err)

    def test_request_shadow_when_disabled(self):
        bridge, _, _ = make_bridge(shadow_enabled=False)
        snap, err = bridge.request_shadow()
        self.assertIsNone(snap)
        self.assertIn("deshabilitado", err)


class TestSettings(unittest.TestCase):
    def test_problems_lists_missing_files_and_endpoint(self):
        s = make_settings(endpoint="")
        problems = s.problems()
        self.assertEqual(len(problems), 4)  # endpoint + 3 archivos inexistentes

    def test_shadow_topics_use_thing_name(self):
        s = make_settings()
        self.assertEqual(s.topic_shadow_get, "$aws/things/esp32-sis234/shadow/get")
        self.assertEqual(s.topic_shadow_update_accepted,
                         "$aws/things/esp32-sis234/shadow/update/accepted")


if __name__ == "__main__":
    unittest.main()

### `config/claude_desktop_config.example.json`
```json
{
  "mcpServers": {
    "smart-object": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/RUTA/ABSOLUTA/A/SIS234-AWS-IoT/mcp-server",
        "run",
        "smart-object.py"
      ]
    }
  }
}

### `config/policies/PoliticaESP32SIS234_referencia.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:client/esp32-sis234"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/sis234/esp32/distancia",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/update",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/get"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/sis234/esp32/comandos",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/update/delta",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/update/accepted",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/get/accepted"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Receive",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/sis234/esp32/comandos",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/update/delta",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/update/accepted",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/get/accepted"
      ]
    }
  ]
}

### `config/policies/PoliticaServidorMCP.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:client/mcp-sis234"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/sis234/esp32/comandos",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/get"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/sis234/esp32/distancia",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/update/accepted",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/get/accepted"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Receive",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/sis234/esp32/distancia",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/update/accepted",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/get/accepted"
      ]
    }
  ]
}

### `config/policies/PoliticaAppMovil.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:client/app-sis234"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/sis234/esp32/comandos"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/sis234/esp32/distancia"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Receive",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/sis234/esp32/distancia"
      ]
    }
  ]
}

### `config/policies/ESP32_extra_rejected_opcional.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/update/rejected",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topicfilter/$aws/things/esp32-sis234/shadow/get/rejected"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Receive",
      "Resource": [
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/update/rejected",
        "arn:aws:iot:us-east-2:<ACCOUNT_ID>:topic/$aws/things/esp32-sis234/shadow/get/rejected"
      ]
    }
  ]
}

## 13. Documentación revisada

Se revisaron `README.md`, `config/README.md`, `mcp-server/README.md` y los siete documentos de `docs/`: AWS, tópicos, Shadow, guía, pruebas, app móvil y circuito. Sus conclusiones están integradas en las secciones anteriores.

## 14. Protección de secretos

No se reproducen certificados, claves privadas, contraseñas ni tokens. Los secretos deben permanecer únicamente en archivos locales excluidos por `.gitignore`.

