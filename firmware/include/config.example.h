/**
 * @file config.example.h
 * @brief Plantilla de configuración. Copiar como "config.h" y completar.
 *
 * "config.h" está en .gitignore: nunca subas tu contraseña de WiFi.
 * Los certificados van aparte, en "aws_certificates.h".
 */
#pragma once

// ---------------- WiFi ----------------
#define WIFI_SSID "NOMBRE_DE_LA_RED"
#define WIFI_PASSWORD "CONTRASENA"
#define WIFI_RETRY_INTERVAL_MS 5000UL

// ---------------- AWS IoT Core (región us-east-2) ----------------
// Estos valores están vinculados a la política "PoliticaESP32SIS234": no los cambies.
#define AWS_IOT_ENDPOINT "ab4xz3zsegut6-ats.iot.us-east-2.amazonaws.com"
#define AWS_IOT_PORT 8883
#define AWS_THING_NAME "esp32-sis234"
#define AWS_CLIENT_ID AWS_THING_NAME  // la política autoriza client/esp32-sis234

#define MQTT_KEEPALIVE_S 60
#define MQTT_RETRY_INTERVAL_MS 5000UL
#define MQTT_BUFFER_SIZE 2048  // el documento Shadow puede superar los 256 B por defecto

// ---------------- Tópicos (autorizados en la política) ----------------
#define TOPIC_DISTANCE "sis234/esp32/distancia"
#define TOPIC_COMMAND "sis234/esp32/comandos"

// 1 = suscribirse también a shadow/update/rejected y shadow/get/rejected.
// Requiere añadir esos tópicos a la política (ver docs/AWS_CONFIGURACION.md).
// Si no están autorizados, AWS puede cerrar la conexión: déjalo en 0 hasta añadirlos.
#define SHADOW_SUBSCRIBE_REJECTED 0
#define SHADOW_GET_TIMEOUT_MS 5000UL  // si get/accepted no llega, se reporta igualmente

// ---------------- Hora (NTP): obligatoria para validar certificados TLS ----------------
#define NTP_SERVER_1 "pool.ntp.org"
#define NTP_SERVER_2 "time.nist.gov"

// ---------------- Sensor ultrasónico HC-SR04 ----------------
// Pines según el montaje real del grupo (el diseño original usaba 5/18/25/26/27).
#define PIN_TRIG 27
#define PIN_ECHO 26          // ¡con divisor de voltaje 1k/2k! (el ECHO entrega 5 V)
#define SENSOR_MIN_CM 2.0f
#define SENSOR_MAX_CM 400.0f // rango físico; declara tu rango de trabajo en la documentación
#define SENSOR_SAMPLES 3     // mediana de N lecturas

// ---------------- LEDs ----------------
#define PIN_LED_RED 14
#define PIN_LED_GREEN 13
#define PIN_LED_YELLOW 12    // GPIO12 es un pin de arranque: ver docs/CIRCUITO.md
#define LED_ACTIVE_LOW 0     // 0 = LED a GND con resistencia (HIGH enciende)

// ---------------- Publicación y consola ----------------
// 400 ms = 2,5 lecturas/s (cumple >= 2/s). Cada lectura cuenta como mensaje publicado
// y como mensaje entregado a cada suscriptor: la capa gratuita de AWS es limitada.
#define PUBLISH_INTERVAL_MS 400UL
#define STATUS_INTERVAL_MS 10000UL
#define SERIAL_BAUD 115200
