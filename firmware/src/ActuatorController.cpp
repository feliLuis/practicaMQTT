#include "ActuatorController.h"

void ActuatorController::begin() {
  for (uint8_t i = 0; i < kLedCount; i++) {
    pinMode(leds_[i].pin, OUTPUT);
    setLed(leds_[i].name, false);
  }
#if ENABLE_SERVO
  servo_.attach(PIN_SERVO);
#endif
}

bool ActuatorController::setLed(const String &color, bool on) {
  String name = color;
  name.toLowerCase();
  for (uint8_t i = 0; i < kLedCount; i++) {
    if (name == leds_[i].name) {
      bool level = LED_ACTIVE_LOW ? !on : on;
      digitalWrite(leds_[i].pin, level ? HIGH : LOW);
      Serial.printf("[ACT] LED %s -> %s\n", leds_[i].name, on ? "ON" : "OFF");
      return true;
    }
  }
  Serial.printf("[ACT] Color desconocido: %s\n", color.c_str());
  return false;
}

bool ActuatorController::setServo(int angle) {
#if ENABLE_SERVO
  if (angle < 0 || angle > 180) {
    Serial.printf("[ACT] Angulo fuera de rango: %d\n", angle);
    return false;
  }
  servo_.write(angle);
  Serial.printf("[ACT] Servo -> %d grados\n", angle);
  return true;
#else
  (void)angle;
  Serial.println("[ACT] Servo deshabilitado (ENABLE_SERVO 0)");
  return false;
#endif
}

bool ActuatorController::applyCommand(const char *payload, unsigned int length) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("[ACT] JSON invalido: %s\n", err.c_str());
    return false;
  }

  if (doc["led"].is<const char *>() && doc["estado"].is<const char *>()) {
    String state = doc["estado"].as<String>();
    state.toLowerCase();
    if (state != "on" && state != "off") {
      Serial.printf("[ACT] Estado invalido: %s\n", state.c_str());
      return false;
    }
    return setLed(doc["led"].as<String>(), state == "on");
  }

  if (doc["servo"].is<int>()) {
    return setServo(doc["servo"].as<int>());
  }

  Serial.println("[ACT] Comando no reconocido");
  return false;
}
