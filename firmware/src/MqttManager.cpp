#include "MqttManager.h"

#include <WiFi.h>

MqttManager::MqttManager(Client &net, const char *server, uint16_t port, const char *user,
                         const char *password, const char *clientPrefix, unsigned long retryMs)
    : client_(net),
      server_(server),
      port_(port),
      user_(user),
      password_(password),
      clientPrefix_(clientPrefix),
      retryMs_(retryMs) {}

void MqttManager::begin(const char *commandTopic, CommandHandler handler) {
  commandTopic_ = commandTopic;
  handler_ = handler;
  client_.setServer(server_, port_);
  client_.setKeepAlive(15);
  client_.setSocketTimeout(3);
  client_.setCallback([this](char *topic, byte *payload, unsigned int length) {
    Serial.printf("[MQTT] Mensaje en %s (%u bytes)\n", topic, length);
    if (handler_) {
      handler_(reinterpret_cast<const char *>(payload), length);
    }
  });
}

bool MqttManager::connect() {
  unsigned long now = millis();
  if (lastAttempt_ != 0 && now - lastAttempt_ < retryMs_) {
    return false;  // aún no toca reintentar
  }
  lastAttempt_ = now;

  if (clientId_.length() == 0) {
    clientId_ = String(clientPrefix_) + WiFi.macAddress();
    clientId_.replace(":", "");
  }

  Serial.printf("[MQTT] Conectando a %s:%u...\n", server_, port_);
  bool ok = (user_[0] != '\0') ? client_.connect(clientId_.c_str(), user_, password_)
                               : client_.connect(clientId_.c_str());
  if (!ok) {
    Serial.printf("[MQTT] Fallo, estado=%d\n", client_.state());
    return false;
  }
  client_.subscribe(commandTopic_, 1);  // se repite en cada reconexión
  Serial.printf("[MQTT] Conectado. Suscrito a %s\n", commandTopic_);
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
