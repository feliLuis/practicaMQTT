/**
 * @file ActuatorController.h
 * @brief Control de los actuadores (3 LEDs y, opcionalmente, un servomotor).
 *
 * Comandos JSON aceptados:
 *   {"led":"rojo","estado":"on"}   (colores: rojo, verde, amarillo; estado: on/off)
 *   {"servo":90}                   (0..180, requiere ENABLE_SERVO 1)
 */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

#include "config.h"
#if ENABLE_SERVO
#include <ESP32Servo.h>
#endif

class ActuatorController {
 public:
  /** Configura los pines y apaga todo. Llamar una vez en setup(). */
  void begin();

  /** Enciende/apaga el LED de un color. @return false si el color no existe. */
  bool setLed(const String &color, bool on);

  /** Mueve el servo a un ángulo 0..180. @return false si no aplica o es inválido. */
  bool setServo(int angle);

  /**
   * Interpreta un comando JSON recibido por MQTT y lo ejecuta.
   * @return true si el comando fue válido y se aplicó.
   */
  bool applyCommand(const char *payload, unsigned int length);

 private:
  enum { kLedCount = 3 };
  struct Led {
    const char *name;
    uint8_t pin;
  };
  Led leds_[kLedCount] = {
      {"rojo", PIN_LED_RED}, {"verde", PIN_LED_GREEN}, {"amarillo", PIN_LED_YELLOW}};
#if ENABLE_SERVO
  Servo servo_;
#endif
};
