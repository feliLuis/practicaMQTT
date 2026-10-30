/**
 * @file ShadowManager.h
 * @brief Device Shadow clásico de AWS IoT: estados desired / reported / delta.
 *
 * Modelo del documento:
 *   {"state":{"desired":{"leds":{"rojo":"on",...}},"reported":{"leds":{"rojo":"on",...}}}}
 *
 * Reglas:
 *  - delta (desired != reported): se aplica al LED y se reporta. Nunca se toca "desired".
 *  - get/accepted tras (re)conectar: se aplica "desired" y se reporta el estado real.
 *  - comando directo (tópico de comandos): se aplica y se publica desired = reported
 *    para que no aparezca un delta que revierta el cambio.
 *  - update/accepted solo se registra: no genera nuevas publicaciones (sin ciclos).
 *
 * Las publicaciones se difieren a update() (fuera del callback MQTT) porque
 * PubSubClient reutiliza el mismo buffer para recibir y publicar.
 */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

#include "ActuatorController.h"
#include "MqttManager.h"

class ShadowManager {
 public:
  ShadowManager(MqttManager &mqtt, ActuatorController &actuators, const char *thingName);

  /** Registra los tópicos del Shadow en MqttManager. Llamar antes de mqtt.begin(). */
  void registerSubscriptions(bool includeRejected);

  /** Llamar cuando MQTT se (re)conecta: pedirá el Shadow para recuperar "desired". */
  void onConnected();

  /** Pide reportar el estado y, si syncDesired, igualar también "desired". */
  void requestReport(bool syncDesired);

  /** Procesa un mensaje. @return true si el tópico pertenece al Shadow. */
  bool handleMessage(const char *topic, const uint8_t *payload, unsigned int length);

  /** Llamar en cada loop(): envía las publicaciones pendientes. */
  void update();

 private:
  enum ReportMode { kNone = 0, kReportOnly = 1, kReportAndDesired = 2 };

  /** Aplica {"rojo":"on",...} a los LEDs. @return cantidad de LEDs modificados. */
  int applyLeds(JsonObjectConst leds);
  bool publishState(bool includeDesired);

  MqttManager &mqtt_;
  ActuatorController &actuators_;
  String topicUpdate_, topicGet_;
  String topicDelta_, topicUpdateAccepted_, topicGetAccepted_;
  String topicUpdateRejected_, topicGetRejected_;
  bool getPending_ = false;
  bool waitingGet_ = false;
  unsigned long getSentAt_ = 0;
  ReportMode report_ = kNone;
};
