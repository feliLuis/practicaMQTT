/**
 * @file MqttManager.h
 * @brief Cliente MQTT seguro (TLS con certificado de cliente) para AWS IoT Core.
 *
 * - Autenticación mutua: CA raíz de Amazon + certificado y clave del dispositivo.
 * - Reconexión automática no bloqueante.
 * - Re-suscripción a todos los tópicos registrados tras CADA reconexión.
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

  /** Carga los certificados TLS (cadenas PEM con vida útil estática). */
  void setCertificates(const char *caCert, const char *clientCert, const char *privateKey);

  /** Registra un tópico al que suscribirse en cada (re)conexión. Llamar antes de begin(). */
  void addSubscription(const String &topic, uint8_t qos);

  /** Configura el cliente y los callbacks. Llamar una vez en setup(). */
  void begin(MessageHandler onMessage, ConnectHandler onConnect);

  /** Llamar en cada loop() con WiFi y hora válidas: reconecta y procesa mensajes. */
  void update();

  /** Permite reintentar la conexión de inmediato (p. ej. al recuperar el WiFi). */
  void resetRetry() { lastAttempt_ = 0; }

  bool connected() { return client_.connected(); }

  /** Publica un mensaje. @return true si se envió. */
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
