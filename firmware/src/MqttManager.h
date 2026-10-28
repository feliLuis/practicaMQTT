/**
 * @file MqttManager.h
 * @brief Cliente MQTT con reconexión automática, suscripción a comandos y publicación.
 */
#pragma once
#include <Arduino.h>
#include <PubSubClient.h>

#include <functional>

class MqttManager {
 public:
  /** Función invocada al llegar un mensaje en el tópico de comandos. */
  using CommandHandler = std::function<void(const char *payload, unsigned int length)>;

  MqttManager(Client &net, const char *server, uint16_t port, const char *user,
              const char *password, const char *clientPrefix, unsigned long retryMs);

  /** Configura servidor, tópico de comandos y callback. Llamar en setup(). */
  void begin(const char *commandTopic, CommandHandler handler);

  /** Llamar en cada loop() (solo con Wi-Fi activo): reconecta y procesa mensajes. */
  void update();

  /** Fuerza un reintento inmediato (p. ej. al recuperar el Wi-Fi). */
  void resetRetry() { lastAttempt_ = 0; }

  bool connected() { return client_.connected(); }

  /** Publica un mensaje. @return true si se envió. */
  bool publish(const char *topic, const char *payload);

 private:
  bool connect();

  PubSubClient client_;
  const char *server_;
  uint16_t port_;
  const char *user_;
  const char *password_;
  const char *clientPrefix_;
  unsigned long retryMs_;
  unsigned long lastAttempt_ = 0;
  const char *commandTopic_ = nullptr;
  CommandHandler handler_;
  String clientId_;
};
