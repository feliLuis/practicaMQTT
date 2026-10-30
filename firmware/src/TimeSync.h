/**
 * @file TimeSync.h
 * @brief Sincronización de hora por NTP (no bloqueante).
 *
 * TLS valida las fechas de vigencia de los certificados. Sin hora correcta
 * (la ESP32 arranca en 1970) el handshake con AWS IoT falla, por lo que MQTT
 * no debe intentar conectarse hasta que synced() sea true.
 */
#pragma once
#include <Arduino.h>

class TimeSync {
 public:
  TimeSync(const char *server1, const char *server2);

  /** Llamar en cada loop(). Inicia NTP al haber WiFi y detecta cuándo hay hora válida. */
  void update(bool wifiUp);

  /** true cuando la hora del sistema es válida. */
  bool synced() const { return synced_; }

 private:
  const char *server1_;
  const char *server2_;
  bool started_ = false;
  bool synced_ = false;
};
