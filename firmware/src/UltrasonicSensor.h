/**
 * @file UltrasonicSensor.h
 * @brief Medición de distancia con un sensor HC-SR04.
 */
#pragma once
#include <Arduino.h>

class UltrasonicSensor {
 public:
  /**
   * @param trigPin  Pin TRIG del sensor.
   * @param echoPin  Pin ECHO (con divisor de voltaje).
   * @param minCm    Distancia mínima válida.
   * @param maxCm    Distancia máxima válida.
   * @param samples  Lecturas por medición; se devuelve la mediana.
   */
  UltrasonicSensor(uint8_t trigPin, uint8_t echoPin, float minCm, float maxCm,
                   uint8_t samples);

  /** Configura los pines. Llamar una vez en setup(). */
  void begin();

  /**
   * Mide la distancia (mediana de varias lecturas).
   * @param[out] cm Distancia en centímetros.
   * @return true si la medición es válida.
   */
  bool measure(float &cm);

 private:
  enum { kMaxSamples = 9 };
  static const unsigned long kTimeoutUs = 30000UL;  // ~5 m de ida y vuelta

  float readOnce();

  uint8_t trigPin_;
  uint8_t echoPin_;
  float minCm_;
  float maxCm_;
  uint8_t samples_;
};
