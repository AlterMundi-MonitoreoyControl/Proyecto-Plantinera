#ifndef PUSH_SUBSCRIBER_MANAGER_H
#define PUSH_SUBSCRIBER_MANAGER_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>
#include "debug.h"

#ifndef UNIT_TEST
#include <Preferences.h>
#include <HTTPClient.h>
#include <WiFi.h>
#endif

struct PushSubscriber {
    String endpoint;
    uint32_t added_at;
};

class PushSubscriberManager {
private:
    PushSubscriberManager() {}

#ifdef UNIT_TEST
    static std::vector<PushSubscriber>& getTestSubscribers() {
        static std::vector<PushSubscriber> testSubs;
        return testSubs;
    }
#endif

    std::vector<PushSubscriber> loadFromStorage() const {
#ifdef UNIT_TEST
        return getTestSubscribers();
#else
        std::vector<PushSubscriber> subscribers;
        Preferences prefs;
        if (!prefs.begin("up_subs", true)) {
            return subscribers;
        }
        String jsonStr = prefs.getString("subs", "[]");
        prefs.end();

        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, jsonStr);
        if (!err) {
            JsonArray arr;
            if (doc.is<JsonArray>()) {
                arr = doc.as<JsonArray>();
            } else if (doc["subscribers"].is<JsonArray>()) {
                arr = doc["subscribers"].as<JsonArray>();
            }

            for (JsonObject obj : arr) {
                const char* ep = obj["endpoint"];
                uint32_t ts = obj["added_at"] | 0;
                if (ep && isValidEndpointUrl(String(ep))) {
                    subscribers.push_back({String(ep), ts});
                    if (subscribers.size() >= MAX_SUBSCRIBERS) break;
                }
            }
        }
        return subscribers;
#endif
    }

    void saveToStorage(const std::vector<PushSubscriber>& subscribers) const {
#ifdef UNIT_TEST
        getTestSubscribers() = subscribers;
#else
        Preferences prefs;
        if (!prefs.begin("up_subs", false)) {
            DBG_ERROR("[PushSub] Failed to open Preferences for writing\n");
            return;
        }
        JsonDocument doc;
        JsonArray arr = doc.to<JsonArray>();
        for (const auto& sub : subscribers) {
            JsonObject obj = arr.add<JsonObject>();
            obj["endpoint"] = sub.endpoint;
            obj["added_at"] = sub.added_at;
        }
        std::string jsonStr;
        serializeJson(doc, jsonStr);
        prefs.putString("subs", jsonStr.c_str());
        prefs.end();
#endif
    }

public:
    static const size_t MAX_SUBSCRIBERS = 5;

    static PushSubscriberManager& getInstance() {
        static PushSubscriberManager instance;
        return instance;
    }

    PushSubscriberManager(const PushSubscriberManager&) = delete;
    PushSubscriberManager& operator=(const PushSubscriberManager&) = delete;

    static bool isValidEndpointUrl(const String& url) {
        if (url.length() == 0) return false;
        return url.startsWith("http://") || url.startsWith("https://");
    }

    static String getTopic() {
#ifndef UNIT_TEST
        String mac = WiFi.macAddress();
        mac.replace(":", "");
        mac.toUpperCase();
        return "moni-" + mac;
#else
        return "moni-004B12EE1FF4";
#endif
    }

    bool addOrUpdateSubscriber(const String& endpoint, uint32_t addedAt = 0) {
        if (!isValidEndpointUrl(endpoint)) return false;

        if (addedAt == 0) {
            uint32_t nowSec = (uint32_t)time(nullptr);
            if (nowSec < 1000000000UL) {
                nowSec = 1784730000UL + (millis() / 1000);
            }
            addedAt = nowSec;
        }

        std::vector<PushSubscriber> subscribers = loadFromStorage();

        // Check if subscriber already exists
        for (auto& sub : subscribers) {
            if (sub.endpoint == endpoint) {
                sub.added_at = addedAt;
                saveToStorage(subscribers);
                return true;
            }
        }

        // Evict oldest subscriber if capacity reached
        if (subscribers.size() >= MAX_SUBSCRIBERS) {
            size_t oldestIdx = 0;
            uint32_t minTs = subscribers[0].added_at;
            for (size_t i = 1; i < subscribers.size(); i++) {
                if (subscribers[i].added_at < minTs) {
                    minTs = subscribers[i].added_at;
                    oldestIdx = i;
                }
            }
            subscribers.erase(subscribers.begin() + oldestIdx);
        }

        subscribers.push_back({endpoint, addedAt});
        saveToStorage(subscribers);
        return true;
    }

    size_t getSubscriberCount() const {
        std::vector<PushSubscriber> subscribers = loadFromStorage();
        return subscribers.size();
    }

    std::vector<PushSubscriber> getSubscribers() const {
        return loadFromStorage();
    }

    void clearSubscribers() {
#ifdef UNIT_TEST
        getTestSubscribers().clear();
#else
        Preferences prefs;
        if (prefs.begin("up_subs", false)) {
            prefs.remove("subs");
            prefs.end();
        }
#endif
    }

    String getSubscribersJson() const {
        std::vector<PushSubscriber> subscribers = loadFromStorage();
        JsonDocument doc;
        doc["topic"] = getTopic();
        JsonArray arr = doc["subscribers"].to<JsonArray>();
        for (const auto& sub : subscribers) {
            JsonObject obj = arr.add<JsonObject>();
            obj["endpoint"] = sub.endpoint;
            obj["added_at"] = sub.added_at;
        }
        std::string output;
        serializeJson(doc, output);
        return String(output.c_str());
    }

    void notifySubscribers(const String& message) {
#ifndef UNIT_TEST
        if (WiFi.status() != WL_CONNECTED) return;
        
        std::vector<PushSubscriber> subscribers = loadFromStorage();
        if (subscribers.empty()) return;

        DBG_INFO("[PushSub] Broadcasting push notification to %u subscribers...\n", (unsigned)subscribers.size());
        for (size_t i = 0; i < subscribers.size(); i++) {
            const auto& sub = subscribers[i];
            HTTPClient http;
            http.begin(sub.endpoint);
            http.setTimeout(3000);
            http.addHeader("Content-Type", "text/plain");
            int code = http.POST(message);
            DBG_INFO("[PushSub] POST -> %s | HTTP %d\n", sub.endpoint.c_str(), code);
            http.end();

            if (i + 1 < subscribers.size()) {
                delay(3000);
            }
        }
#endif
    }
};

#endif // PUSH_SUBSCRIBER_MANAGER_H
