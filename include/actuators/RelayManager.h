#ifndef RELAY_MANAGER_H
#define RELAY_MANAGER_H

#include <vector>
#include <ArduinoJson.h>
#include "RelayModule2CH.h"
#include "RelayModule4CH.h"
#include "core/GpioActuator.h"
#include "../debug.h"

struct GpioRelayConfig {
    GpioActuator* actuator;
    uint8_t pin;
    String alias;
};

class RelayManager {
private:
    std::vector<RelayModule2CH*> relays;
    std::vector<RelayModule4CH*> relays4ch;
    std::vector<GpioRelayConfig> gpioRelays;

public:
    ~RelayManager() {
        for (auto r : relays)    delete r;
        relays.clear();
        for (auto r : relays4ch) delete r;
        relays4ch.clear();
        for (auto g : gpioRelays) delete g.actuator;
        gpioRelays.clear();
    }

    void loadFromConfig(JsonDocument& doc) {
        // Clear existing
        for (auto r : relays)    delete r;
        relays.clear();
        for (auto r : relays4ch) delete r;
        relays4ch.clear();
        for (auto g : gpioRelays) delete g.actuator;
        gpioRelays.clear();

        if (!doc["relays"].is<JsonArray>()) {
            DBG_INFO("[RelayMgr] No relays in config\n");
            return;
        }

        JsonArrayConst relayArray = doc["relays"].as<JsonArrayConst>();
        DBG_INFO("[RelayMgr] Found %d relays\n", relayArray.size());

        for (JsonObjectConst r : relayArray) {
            bool enabled = r["enabled"].as<bool>();
            if (enabled) {
                String type = r["type"] | "relay_2ch";
                if (type == "gpio") {
                    uint8_t pin = r["config"]["pin"] | 2;
                    bool activeLow = r["config"]["active_low"] | false;
                    String defaultAlias = "GPIO " + String(pin);
                    String alias = r["config"]["alias"] | defaultAlias;
                    
                    uint8_t gpioId = pin + 200; // Desplazamiento para evitar colisión con Modbus
                    auto* act = new GpioActuator(gpioId, pin, alias, !activeLow);
                    act->configure(r["config"]["max_on_ms"] | 0, r["config"]["min_off_ms"] | 0);
                    gpioRelays.push_back({act, pin, alias});
                    DBG_INFO("[RelayMgr] Added GPIO: Pin=%d '%s' (ID=%d)\n", pin, alias.c_str(), gpioId);
                } else if (type == "relay_4ch") {
                    uint8_t addr = r["config"]["address"] | 255;
                    if (addr >= 12 && addr < 200) {
                        DBG_ERROR("[RelayMgr] WARN: Modbus Dir %d (ID %d) puede colisionar con GPIOs!\n", addr, addr << 4);
                    }
                    String alias = r["config"]["alias"] | "";

                    auto* relay4 = new RelayModule4CH(addr, alias);
                    const char* chKeys[4] = {"ch0","ch1","ch2","ch3"};
                    for (uint8_t ch = 0; ch < 4; ch++) {
                        JsonObjectConst chCfg = r["config"][chKeys[ch]];
                        relay4->configureChannel(ch,
                            chCfg["max_on_ms"] | 0,
                            chCfg["min_off_ms"] | 0,
                            chCfg["inverted"]   | false);
                    }
                    relays4ch.push_back(relay4);
                    DBG_INFO("[RelayMgr] Added 4CH Modbus: Addr=%d '%s'\n", addr, alias.c_str());
                } else {
                    uint8_t addr = r["config"]["address"] | 1;
                    if (addr >= 12) {
                        DBG_ERROR("[RelayMgr] WARN: Modbus Dir %d (ID %d) puede colisionar con GPIOs!\n", addr, addr << 4);
                    }
                    String alias = r["config"]["alias"] | "";
                    
                    auto* modbusRelay = new RelayModule2CH(addr, alias);
                    JsonObjectConst ch0 = r["config"]["ch0"];
                    JsonObjectConst ch1 = r["config"]["ch1"];
                    
                    modbusRelay->configureChannel(0, ch0["max_on_ms"] | 0, ch0["min_off_ms"] | 0, ch0["inverted"] | false);
                    modbusRelay->configureChannel(1, ch1["max_on_ms"] | 0, ch1["min_off_ms"] | 0, ch1["inverted"] | false);

                    relays.push_back(modbusRelay);
                    DBG_INFO("[RelayMgr] Added Modbus 2CH: Addr=%d '%s'\n", addr, alias.c_str());
                }
            } else {
                DBG_VERBOSE("[RelayMgr] Relay disabled\n");
            }
        }
    }

    std::vector<RelayModule2CH*>& getRelays() {
        return relays;
    }

    std::vector<RelayModule4CH*>& getRelays4ch() {
        return relays4ch;
    }

    std::vector<GpioRelayConfig>& getGpioRelays() {
        return gpioRelays;
    }
    
    RelayModule2CH* getRelay(int index) {
        if(index >= 0 && index < (int)relays.size()) return relays[index];
        return nullptr;
    }

    RelayModule4CH* getRelay4ch(int index) {
        if(index >= 0 && index < (int)relays4ch.size()) return relays4ch[index];
        return nullptr;
    }
};

#endif // RELAY_MANAGER_H