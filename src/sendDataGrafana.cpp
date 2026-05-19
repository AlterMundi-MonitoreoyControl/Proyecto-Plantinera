#include <Arduino.h>
#include <WiFi.h>
#include "constants.h"
#include "globals.h"
#include "sendDataGrafana.h"
#include "createGrafanaMessage.h"
#include "GrafanaLogger.h"
#include "debug.h"

/**
 * sendDataGrafana — guarded Grafana POST via GrafanaLogger.
 *
 * All preflight checks (WiFi, heap, throttle, Grafana reachability back-off)
 * are handled inside GrafanaLogger::safePost(), ported from tools/log.lua.
 */
void sendDataGrafana(float temperature, float humidity, float co2,
                     const char* sensorId, const char* deviceId) {
    String data = create_grafana_message(temperature, humidity, co2, sensorId, deviceId);
    DBG_VERBOSE("Grafana: %s\n", data.c_str());
    GrafanaLogger::getInstance().safePost(data, String(sensorId));
}

void sendDataGrafana(const char* message, const char* sensorId, const char* deviceId) {
    String data = create_grafana_message(message, sensorId, deviceId);
    DBG_VERBOSE("Grafana: %s\n", data.c_str());
    GrafanaLogger::getInstance().safePost(data, String(sensorId));
}