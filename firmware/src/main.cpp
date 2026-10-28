/**
 * @file main.cpp
 * @brief Objeto inteligente: mide distancia (HC-SR04), la publica por MQTT y
 *        activa LEDs/servo según los comandos recibidos.
 *
 * Tópicos (ver config.h):
 *   publica   <prefijo>/distancia         {"cm": 42.7}
 *   se suscribe <prefijo>/actuadores/cmd  {"led":"rojo","estado":"on"} | {"servo":90}
 */
#include <Arduino.h>
#include <WiFi.h>

#include "ActuatorController.h"
#include "MqttManager.h"
#include "UltrasonicSensor.h"
#include "WifiManager.h"
#include "config.h"

WiFiClient netClient;
WifiManager wifi(WIFI_SSID, WIFI_PASSWORD, WIFI_RETRY_INTERVAL_MS);
MqttManager mqtt(netClient, MQTT_SERVER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
                 MQTT_CLIENT_PREFIX, MQTT_RETRY_INTERVAL_MS);
UltrasonicSensor sensor(PIN_TRIG, PIN_ECHO, SENSOR_MIN_CM, SENSOR_MAX_CM, SENSOR_SAMPLES);
ActuatorController actuators;

unsigned long lastPublish = 0;
bool wifiWasUp = false;

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println("\n[BOOT] Objeto inteligente iniciando");

  sensor.begin();
  actuators.begin();
  wifi.begin();
  mqtt.begin(TOPIC_COMMAND, [](const char *payload, unsigned int length) {
    actuators.applyCommand(payload, length);
  });
}

void loop() {
  bool wifiUp = wifi.update();
  if (wifiUp && !wifiWasUp) {
    mqtt.resetRetry();  // reconectar MQTT sin esperar al recuperar el Wi-Fi
  }
  wifiWasUp = wifiUp;

  if (wifiUp) {
    mqtt.update();
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
}
