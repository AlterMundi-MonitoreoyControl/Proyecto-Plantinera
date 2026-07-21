#include "createGrafanaMessage.h"
#include <WiFi.h>
#include <constants.h>
#include "configFile.h"

/**
 * Helper function to build the device name from deviceId
 * If deviceId is a mesh sensor (starts with "mesh_"), use it directly
 * Otherwise, use the gateway MAC address
 */
static void buildDeviceName(char* device_name, size_t size, const char* deviceId) {
  if (deviceId && strncmp(deviceId, "moni-", 5) == 0) {
    snprintf(device_name, size, "%s", deviceId);
    return;
  }

  // Sensores locales: el tag `device` debe coincidir con lo que la app LibreAgro
  // consulta = `moni-<hash>` donde hash = config.json["hash"]. Antes se usaba la
  // MAC en vivo (WiFi.macAddress()), que en este device NO coincide con el hash
  // del config → la app no encontraba la telemetría. Cacheamos el nombre una vez.
  static char cached[64] = {0};
  if (cached[0] == '\0') {
    JsonDocument cfg = loadConfig();
    const char* hash = cfg["hash"] | "";
    if (hash[0] != '\0' && strncmp(hash, "moni-", 5) == 0) {
      snprintf(cached, sizeof(cached), "%s", hash);
    } else if (hash[0] != '\0') {
      snprintf(cached, sizeof(cached), "moni-%s", hash);
    } else {
      String mac = WiFi.macAddress();
      mac.replace(":", "");
      snprintf(cached, sizeof(cached), "moni-%s", mac.c_str());
    }
  }
  snprintf(device_name, size, "%s", cached);
}

/**
 * Helper function to build the InfluxDB line protocol message
 * Returns: "medicionesCO2,device=<device>,sensor=<sensor> <fields> <timestamp>"
 */
static String buildInfluxMessage(const char* device_name, const char* sensorId, const char* fields, unsigned long long timestamp) {
  return "medicionesCO2,device=" + String(device_name) + 
         ",sensor=" + String(sensorId) + 
         " " + String(fields) + 
         " " + String(timestamp);
}

String create_grafana_message(float temperature, float humidity, float co2, const char* sensorId, const char* deviceId)
{
  unsigned long long timestamp = time(nullptr) * 1000000000ULL;
  char device_name[64] = {0};
  buildDeviceName(device_name, sizeof(device_name), deviceId);

  // Build fields string: "temp=X,hum=Y,co2=Z"
  String fields = "temp=" + String(temperature, 2) +
                  ",hum=" + String(humidity, 2) +
                  ",co2=" + String(co2);

  return buildInfluxMessage(device_name, sensorId, fields.c_str(), timestamp);
}

/**
 * Overload that accepts a pre-formatted fields string
 * The message parameter should already be formatted as: field1=value1,field2=value2
 */
String create_grafana_message(const char* message, const char* sensorId, const char* deviceId)
{
  unsigned long long timestamp = time(nullptr) * 1000000000ULL;
  char device_name[64] = {0};
  buildDeviceName(device_name, sizeof(device_name), deviceId);

  return buildInfluxMessage(device_name, sensorId, message, timestamp);
}