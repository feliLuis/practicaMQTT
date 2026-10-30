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
    return false;  // aún no toca reintentar
  }
  lastAttempt_ = now;

  Serial.printf("[MQTT] Conectando a %s:%u como '%s'...\n", endpoint_, port_, clientId_);
  if (!client_.connect(clientId_)) {
    char tlsError[100] = {0};
    net_.lastError(tlsError, sizeof(tlsError));
    // estado PubSubClient: -2 sin red/TLS, 4 credenciales, 5 no autorizado (política)
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
