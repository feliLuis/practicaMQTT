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
    return false;  // comando inválido: ningún GPIO fue modificado
  }
  return setLed(color, on);
}

void ActuatorController::fillState(JsonObject leds) const {
  for (uint8_t i = 0; i < kLedCount; i++) {
    leds[leds_[i].name] = leds_[i].on ? "on" : "off";
  }
}
