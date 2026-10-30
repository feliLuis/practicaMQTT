/**
 * @file ActuatorController.h
 * @brief Control de los tres LEDs (rojo, verde, amarillo) con validación de comandos.
 *
 * Comando JSON aceptado:  {"led":"rojo","estado":"on"}
 *   led    : rojo | verde | amarillo
 *   estado : on | off
 * Ningún GPIO se modifica hasta que el comando completo ha sido validado.
 */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

#include "config.h"

class ActuatorController {
 public:
  /** Configura los pines y apaga todo. Llamar una vez en setup(). */
  void begin();

  /** Enciende/apaga un LED por nombre. @return false si el color no existe. */
  bool setLed(const String &color, bool on);

  /**
   * Valida un comando JSON SIN ejecutarlo.
   * @param[out] color  Color normalizado (minúsculas).
   * @param[out] on     Estado pedido.
   * @return true si el comando es válido.
   */
  bool parseCommand(const char *payload, unsigned int length, String &color, bool &on) const;

  /** Valida y ejecuta un comando. @return true si se aplicó. */
  bool applyCommand(const char *payload, unsigned int length, String &color, bool &on);

  /** Escribe el estado actual en un objeto JSON: {"rojo":"on", ...}. */
  void fillState(JsonObject leds) const;

 private:
  enum { kLedCount = 3 };
  struct Led {
    const char *name;
    uint8_t pin;
    bool on;
  };

  int indexOf(const String &lowerCaseColor) const;

  Led leds_[kLedCount] = {{"rojo", PIN_LED_RED, false},
                          {"verde", PIN_LED_GREEN, false},
                          {"amarillo", PIN_LED_YELLOW, false}};
};
