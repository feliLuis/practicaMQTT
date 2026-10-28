/**
 * @file WifiManager.h
 * @brief Conexión Wi-Fi con reconexión automática y NO bloqueante.
 */
#pragma once
#include <Arduino.h>
#include <WiFi.h>

class WifiManager {
 public:
  WifiManager(const char *ssid, const char *password, unsigned long retryMs);

  /** Configura el modo estación. Llamar una vez en setup(). */
  void begin();

  /**
   * Debe llamarse en cada loop(). Reintenta la conexión cada retryMs si se cayó.
   * @return true si hay conexión Wi-Fi.
   */
  bool update();

 private:
  const char *ssid_;
  const char *password_;
  unsigned long retryMs_;
  unsigned long lastAttempt_ = 0;
  bool wasConnected_ = false;
};
