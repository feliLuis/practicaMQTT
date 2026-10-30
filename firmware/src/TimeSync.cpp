#include "TimeSync.h"

#include <time.h>

// Cualquier valor posterior a nov-2023 indica que NTP ya fijó la hora.
static const time_t kMinValidEpoch = 1700000000;

TimeSync::TimeSync(const char *server1, const char *server2)
    : server1_(server1), server2_(server2) {}

void TimeSync::update(bool wifiUp) {
  if (wifiUp && !started_) {
    configTime(0, 0, server1_, server2_);  // UTC; solo importa para validar certificados
    started_ = true;
    Serial.println("[NTP] Sincronizando hora...");
  }
  if (started_ && !synced_ && time(nullptr) > kMinValidEpoch) {
    synced_ = true;
    Serial.printf("[NTP] Hora valida (epoch %ld)\n", (long)time(nullptr));
  }
}
