#include <unity.h>
#include <ArduinoJson.h>
#include <string>

// Espejo de la migración agregada en configFile.cpp::loadConfig() para
// backfillear hash/incubator_name/min_temperature/max_temperature/min_hum/
// max_hum en config.json viejos que no los tienen (config.json creado por
// una versión de firmware anterior a estos campos). Usa std::string en vez
// de la String de Arduino para poder correr en el entorno nativo (native_test).
static bool migrateMissingFields(JsonDocument& doc, const std::string& mac) {
    bool configModified = false;

    const char* hash = doc["hash"].is<const char*>() ? doc["hash"].as<const char*>() : "";
    if (hash[0] == '\0') {
        doc["hash"] = mac;
        const char* name = doc["incubator_name"].is<const char*>()
                                ? doc["incubator_name"].as<const char*>()
                                : "";
        if (name[0] == '\0') {
            doc["incubator_name"] = "moni-" + mac;
        }
        configModified = true;
    }

    if (!doc["min_temperature"].is<float>() || !doc["max_temperature"].is<float>() ||
        !doc["min_hum"].is<float>() || !doc["max_hum"].is<float>()) {
        doc["min_temperature"] = doc["min_temperature"] | 37.3;
        doc["max_temperature"] = doc["max_temperature"] | 37.7;
        doc["min_hum"] = doc["min_hum"] | 55;
        doc["max_hum"] = doc["max_hum"] | 65;
        configModified = true;
    }

    return configModified;
}

// Reproduce el /config real reportado por el hub en producción: le faltan
// hash, incubator_name y los 4 campos de rango — exactamente el caso que
// rompe validateHubConfig() en la app LibreAgro.
void testMigration_BackfillsHashAndRanges_OnLegacyConfig() {
    JsonDocument doc;
    JsonArray relays = doc["relays"].to<JsonArray>();
    (void)relays;
    JsonObject rs485 = doc["rs485"].to<JsonObject>();
    rs485["enabled"] = true;

    bool modified = migrateMissingFields(doc, "AABBCCDDEEFF");

    TEST_ASSERT_TRUE(modified);
    TEST_ASSERT_EQUAL_STRING("AABBCCDDEEFF", doc["hash"].as<const char*>());
    TEST_ASSERT_EQUAL_STRING("moni-AABBCCDDEEFF", doc["incubator_name"].as<const char*>());
    TEST_ASSERT_EQUAL_FLOAT(37.3, doc["min_temperature"].as<float>());
    TEST_ASSERT_EQUAL_FLOAT(37.7, doc["max_temperature"].as<float>());
    TEST_ASSERT_EQUAL_FLOAT(55, doc["min_hum"].as<float>());
    TEST_ASSERT_EQUAL_FLOAT(65, doc["max_hum"].as<float>());
}

// No debe pisar valores ya configurados (por ejemplo, rangos que el usuario
// ya ajustó desde /config, o un incubator_name personalizado).
void testMigration_PreservesExistingValues() {
    JsonDocument doc;
    doc["hash"] = "112233445566";
    doc["incubator_name"] = "Plantinera Norte";
    doc["min_temperature"] = 18.5;
    doc["max_temperature"] = 24.0;
    doc["min_hum"] = 40;
    doc["max_hum"] = 70;

    bool modified = migrateMissingFields(doc, "112233445566");

    TEST_ASSERT_FALSE(modified);
    TEST_ASSERT_EQUAL_STRING("Plantinera Norte", doc["incubator_name"].as<const char*>());
    TEST_ASSERT_EQUAL_FLOAT(18.5, doc["min_temperature"].as<float>());
    TEST_ASSERT_EQUAL_FLOAT(24.0, doc["max_temperature"].as<float>());
}

// Config ya completo salvo por el hash vacío (string vacío en vez de ausente):
// también debe backfillearse.
void testMigration_BackfillsEmptyHash() {
    JsonDocument doc;
    doc["hash"] = "";
    doc["incubator_name"] = "";

    bool modified = migrateMissingFields(doc, "665544332211");

    TEST_ASSERT_TRUE(modified);
    TEST_ASSERT_EQUAL_STRING("665544332211", doc["hash"].as<const char*>());
    TEST_ASSERT_EQUAL_STRING("moni-665544332211", doc["incubator_name"].as<const char*>());
}
