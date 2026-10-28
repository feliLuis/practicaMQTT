#include "WifiManager.h"

WifiManager::WifiManager(const char *ssid, const char *password, unsigned long retryMs)
    : ssid_(ssid), password_(password), retryMs_(retryMs) {}

void WifiManager::begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
}

bool WifiManager::update() {
  bool connected = (WiFi.status() == WL_CONNECTED);

  if (connected != wasConnected_) {
    wasConnected_ = connected;
    if (connected) {
      Serial.printf("[WIFI] Conectado, IP %s\n", WiFi.localIP().toString().c_str());
    } else {
      Serial.println("[WIFI] Conexion perdida");
    }
  }
  if (connected) {
    return true;
  }

  unsigned long now = millis();
  if (lastAttempt_ == 0 || now - lastAttempt_ >= retryMs_) {
    lastAttempt_ = now;
    Serial.printf("[WIFI] Conectando a %s...\n", ssid_);
    WiFi.disconnect();
    WiFi.begin(ssid_, password_);
  }
  return false;
}
