#include "UltrasonicSensor.h"

UltrasonicSensor::UltrasonicSensor(uint8_t trigPin, uint8_t echoPin, float minCm,
                                   float maxCm, uint8_t samples)
    : trigPin_(trigPin),
      echoPin_(echoPin),
      minCm_(minCm),
      maxCm_(maxCm),
      samples_(samples < 1 ? 1 : (samples > kMaxSamples ? kMaxSamples : samples)) {}

void UltrasonicSensor::begin() {
  pinMode(trigPin_, OUTPUT);
  pinMode(echoPin_, INPUT);
  digitalWrite(trigPin_, LOW);
}

float UltrasonicSensor::readOnce() {
  // Pulso de disparo de 10 us
  digitalWrite(trigPin_, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin_, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin_, LOW);

  unsigned long us = pulseIn(echoPin_, HIGH, kTimeoutUs);
  if (us == 0) {
    return NAN;  // sin eco (fuera de rango o desconectado)
  }
  // Velocidad del sonido ~0.0343 cm/us; el eco recorre ida y vuelta.
  float cm = us * 0.0343f / 2.0f;
  if (cm < minCm_ || cm > maxCm_) {
    return NAN;
  }
  return cm;
}

bool UltrasonicSensor::measure(float &cm) {
  float values[kMaxSamples];
  uint8_t n = 0;
  for (uint8_t i = 0; i < samples_; i++) {
    float v = readOnce();
    if (!isnan(v)) {
      values[n++] = v;
    }
    delay(10);  // evita que un eco se confunda con el siguiente disparo
  }
  if (n < samples_ / 2 + 1) {
    return false;  // demasiadas lecturas inválidas
  }
  // Ordenamiento por inserción (n es pequeño) y selección de la mediana
  for (uint8_t i = 1; i < n; i++) {
    float key = values[i];
    int j = i - 1;
    while (j >= 0 && values[j] > key) {
      values[j + 1] = values[j];
      j--;
    }
    values[j + 1] = key;
  }
  cm = values[n / 2];
  return true;
}
