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
  getPending_ = true;  // se publica en update(), fuera del callback de conexión
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
    // Respuesta a get: recuperar el estado deseado tras un reinicio o reconexión.
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
    // Confirmación de AWS. Solo se registra: responder aquí crearía un ciclo.
    Serial.println("[SHADOW] update aceptado por AWS");
    return true;
  }

  if (t == topicUpdateRejected_ || t == topicGetRejected_) {
    Serial.printf("[SHADOW] RECHAZADO en %s: %.*s\n", topic, (int)length, data);
    if (t == topicGetRejected_) {
      waitingGet_ = false;  // el Shadow aún no existe (404): crearlo reportando
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
