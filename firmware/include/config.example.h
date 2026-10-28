/**
 * @file config.example.h
 * @brief Plantilla de configuración del objeto inteligente.
 *
 * Copia este archivo como "config.h" y completa tus valores.
 * "config.h" está en .gitignore: NUNCA subas credenciales reales.
 */
#pragma once

// ---------------- Wi-Fi ----------------
#define WIFI_SSID "NOMBRE_DE_LA_RED"
#define WIFI_PASSWORD "CONTRASENA"
#define WIFI_RETRY_INTERVAL_MS 5000UL

// ---------------- Broker MQTT ----------------
#define MQTT_SERVER "broker.hivemq.com"
#define MQTT_PORT 1883
#define MQTT_USER ""        // vacío = sin autenticación (HiveMQ público)
#define MQTT_PASSWORD ""
#define MQTT_RETRY_INTERVAL_MS 3000UL
#define MQTT_CLIENT_PREFIX "esp32-"

// ---------------- Tópicos (prefijo ÚNICO de tu grupo) ----------------
#define TOPIC_PREFIX "sis234/grupoN"
#define TOPIC_DISTANCE TOPIC_PREFIX "/distancia"
#define TOPIC_COMMAND TOPIC_PREFIX "/actuadores/cmd"

// ---------------- Sensor ultrasónico HC-SR04 ----------------
#define PIN_TRIG 5
#define PIN_ECHO 18          // ¡con divisor de voltaje 1k/2k! (el ECHO entrega 5 V)
#define SENSOR_MIN_CM 2.0f
#define SENSOR_MAX_CM 400.0f // rango máximo físico; declara tu rango de trabajo en el README
#define SENSOR_SAMPLES 3     // mediana de N lecturas (mejora la exactitud)

// ---------------- Actuadores ----------------
#define PIN_LED_RED 25
#define PIN_LED_GREEN 26
#define PIN_LED_YELLOW 27
#define LED_ACTIVE_LOW 0     // 0 = LED externo normal (HIGH enciende)

#define ENABLE_SERVO 0       // 1 = usar servomotor (requiere la librería ESP32Servo)
#define PIN_SERVO 13

// ---------------- Publicación y consola ----------------
#define PUBLISH_INTERVAL_MS 250UL   // ~4 lecturas por segundo
#define SERIAL_BAUD 115200
