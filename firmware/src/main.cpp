/**
 * @file main.cpp
 * @brief Objeto inteligente SIS-234 sobre AWS IoT Core.
 *
 * - Mide distancia (HC-SR04) y la publica en  sis234/esp32/distancia  {"cm":42.7}
 * - Recibe comandos en  sis234/esp32/comandos  {"led":"rojo","estado":"on"}
 * - Sincroniza el estado de los LEDs con el Device Shadow clásico del Thing.
 * - Reconexión automática de WiFi y MQTT (con re-suscripción y consulta del Shadow).
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
      // Mantener el Shadow coherente: desired = reported, así no aparece un delta que revierta.
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

  // TLS necesita WiFi y hora válida (validación de certificados).
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
