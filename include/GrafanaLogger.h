#ifndef GRAFANA_LOGGER_H
#define GRAFANA_LOGGER_H

/**
 * GrafanaLogger — C++ port of tools/log.lua
 *
 * Provides:
 *  - safePost()              : guarded HTTP POST with all preflight checks
 *  - isGrafanaReachable()    : cached reachability state
 *  - sendNtfy()              : push notification via ntfy.sh
 *  - addError()              : throttled error registration
 *  - throttleCheck()         : per-key rate limiter with jitter (anti-starvation)
 *
 * Mirrors the log.lua concepts:
 *   throttle_interval        → MIN_POST_INTERVAL_MS
 *   throttle_type_interval   → used in addError()
 *   safe_http_post()         → safePost()
 *   log.send_to_ntfy()       → sendNtfy()
 */

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <esp_system.h>   // esp_reset_reason()
#include <time.h>
#include <map>

#include "constants.h"
#include "debug.h"

// --- Tuneable constants -------------------------------------------------------

// Minimum ms between any two Grafana POSTs for the same sensor key
static constexpr uint32_t GRAFANA_MIN_POST_INTERVAL_MS = 5000;

// Minimum heap before skipping any HTTP call (matches log.lua min_heap = 20000)
static constexpr uint32_t GRAFANA_MIN_HEAP_BYTES = 20000;

// Back-off schedule when Grafana is unreachable (ms)
static constexpr uint32_t GRAFANA_BACKOFF_INITIAL_MS  =   10000;  //  10 s
static constexpr uint32_t GRAFANA_BACKOFF_SECOND_MS   =   30000;  //  30 s
static constexpr uint32_t GRAFANA_BACKOFF_THIRD_MS    =   60000;  //   1 min
static constexpr uint32_t GRAFANA_BACKOFF_MAX_MS      =  300000;  //   5 min

// How often to confirm Grafana is still reachable when "online" (ms)
static constexpr uint32_t GRAFANA_CONFIRM_INTERVAL_MS = 120000;  //  2 min

// HTTP timeout for Grafana POST (ms) — keep short to avoid blocking loop()
static constexpr int GRAFANA_HTTP_TIMEOUT_MS = 500;

// -----------------------------------------------------------------------------

class GrafanaLogger {
public:
    // Singleton accessor
    static GrafanaLogger& getInstance() {
        static GrafanaLogger instance;
        return instance;
    }

    // Deleted copy/move
    GrafanaLogger(const GrafanaLogger&)            = delete;
    GrafanaLogger& operator=(const GrafanaLogger&) = delete;

    /**
     * Call once from setup() after WiFi is configured.
     * Derives the NTFY topic from the MAC address (unique per device).
     * topic URL: http://ntfy.sh/moni-{MAC_NO_COLONS}
     */
    void begin() {
        String mac = WiFi.macAddress();
        mac.replace(":", "");
        mac.toLowerCase();
        _ntfyUrl = "http://ntfy.sh/moni-" + mac;
        _initialized = true;
        DBG_INFO("[GrafanaLogger] NTFY topic: %s\n", _ntfyUrl.c_str());

        // Capture reset reason immediately — report will be sent once WiFi connects
        _resetReason = _resetReasonStr();
        _pendingResetReport = true;
        _resetReportAfterMs = millis() + 10000; // 10 s grace for WiFi to connect
        DBG_INFO("[GrafanaLogger] Reset reason: %s (report deferred until online)\n",
                 _resetReason.c_str());
    }

    /**
     * Guarded HTTP POST — the C++ equivalent of safe_http_post() in log.lua.
     *
     * Checks:
     *   1. WiFi connected
     *   2. Free heap >= GRAFANA_MIN_HEAP_BYTES
     *   3. Per-key throttle (GRAFANA_MIN_POST_INTERVAL_MS)
     *   4. Grafana reachable (cached; back-off when down)
     *
     * @param data      InfluxDB line-protocol string
     * @param key       Throttle key (usually sensorId)
     * @returns true if the POST was attempted
     */
    bool safePost(const String& data, const String& key = "default") {
        if (!_initialized) begin();

        // 1. WiFi check
        if (WiFi.status() != WL_CONNECTED) {
            DBG_VERBOSE("[GrafanaLogger] WiFi not connected, skipping POST\n");
            return false;
        }

        // 2. Heap check
        if (ESP.getFreeHeap() < GRAFANA_MIN_HEAP_BYTES) {
            DBG_ERROR("[GrafanaLogger] Low heap (%u B), skipping POST\n", ESP.getFreeHeap());
            _maybeNotifyLowHeap();
            return false;
        }

        // 3. Per-key throttle
        if (!_throttleCheck(key, GRAFANA_MIN_POST_INTERVAL_MS)) {
            return false;
        }

        // 4. Grafana reachability
        if (!_ensureGrafanaReachable()) {
            DBG_VERBOSE("[GrafanaLogger] Grafana unreachable, skipping POST (back-off %lums)\n",
                        (unsigned long)_backoffMs);
            return false;
        }

        // 5. Perform the POST
        return _doPost(data);
    }

    /**
     * Check (and cache) whether Grafana is reachable.
     * Called automatically by safePost(), but can also be called proactively.
     */
    bool isGrafanaReachable() const { return _grafanaReachable; }

    /**
     * Periodic background tick — call from loop() to run the
     * Grafana reachability probe and NTFY throttle timers.
     * Does NOT do any heavy work unless the probe interval has elapsed.
     */
    void tick() {
        if (!_initialized) return;

        // --- Send deferred reset report once WiFi comes up ------------------
        if (_pendingResetReport &&
            WiFi.status() == WL_CONNECTED &&
            millis() >= _resetReportAfterMs) {
            _pendingResetReport = false;
            String msg = "Device reset: " + _resetReason;
            DBG_INFO("[GrafanaLogger] Sending reset report: %s\n", msg.c_str());
            // Send to Grafana as "log" measurement (mirrors log.lua send_to_grafana)
            _sendGrafanaLog(msg);
            // Send to NTFY independently (one-time event — dedicated key, no throttle)
            sendNtfy("\xF0\x9F\x94\x84 " + msg, "_ntfy_reset_", 0);
        }

        // Periodically re-confirm Grafana is still reachable
        if (_grafanaReachable &&
            (millis() - _lastGrafanaCheck) > GRAFANA_CONFIRM_INTERVAL_MS) {
            _probeGrafana();
        }

        // If in back-off, check whether the cooldown has expired
        if (!_grafanaReachable && millis() >= _nextRetryMs) {
            _probeGrafana();
        }
    }

    /**
     * Send a push notification via ntfy.sh.
     * Mirrors log.send_to_ntfy() — fire-and-forget with independent back-off.
     *
     * NTFY and Grafana are fully decoupled:
     *   - Grafana down (LAN gone)  → NTFY still sends if internet is reachable
     *   - NTFY down (ntfy.sh gone) → Grafana still sends, NTFY silently skips
     *
     * @param message      Plain-text message
     * @param throttleKey  Per-event throttle key — different event types use
     *                     different keys so they never block each other.
     * @param throttleMs   Minimum ms between sends for this key (0 = no throttle)
     */
    void sendNtfy(const String& message,
                  const String& throttleKey = "_ntfy_",
                  uint32_t throttleMs = 30000) {
        if (!_initialized) begin();
        if (_ntfyUrl.isEmpty()) return;

        // NTFY has its OWN WiFi + heap check — independent of Grafana state
        if (WiFi.status() != WL_CONNECTED) return;
        if (ESP.getFreeHeap() < GRAFANA_MIN_HEAP_BYTES) return;

        // NTFY has its OWN throttle key — each event type passes its own key
        // so different alerts never block each other
        if (throttleMs > 0 && !_throttleCheck(throttleKey, throttleMs)) return;

        // NTFY has its OWN back-off — if ntfy.sh is down, skip silently
        // without affecting Grafana reachability state at all
        if (!_ntfyReachable) {
            if (millis() < _nextNtfyRetryMs) {
                DBG_VERBOSE("[GrafanaLogger] NTFY in back-off, skipping notification\n");
                return;
            }
            // Back-off expired — allow one attempt
        }

        DBG_INFO("[GrafanaLogger] NTFY -> %s\n", message.c_str());

        HTTPClient http;
        http.begin(_ntfyUrl);
        http.setTimeout(3000);
        http.addHeader("Content-Type", "text/plain");
        int code = http.POST(message);
        http.end();

        if (code == 200) {
            // Successful send — reset NTFY back-off if it was in failure state
            if (!_ntfyReachable) {
                DBG_INFO("[GrafanaLogger] NTFY reconnected\n");
                _ntfyReachable  = true;
                _ntfyBackoffMs  = 30000;
                _nextNtfyRetryMs = 0;
            }
        } else {
            _handleNtfyFailure(code);
        }
    }

    /**
     * Throttled error registration — port of log.addError().
     *
     * Records the error internally; only calls sendNtfy() after
     * throttle_type_interval (default 4 min) to avoid flooding.
     *
     * @param errorType  Category string (e.g., "sensor", "grafana")
     * @param message    Human-readable description
     * @param intervalMs How often to re-notify (default 4 min)
     */
    void addError(const String& errorType,
                  const String& message,
                  uint32_t intervalMs = 240000) {
        // Store last two messages per type
        auto& vec = _errors[errorType];
        if (vec.size() >= 2) vec.erase(vec.begin());
        vec.push_back(message);

        // Per-type throttle key so errors of different types don't block each other
        String key = "_err_" + errorType;
        if (!_throttleCheck(key, intervalMs)) return;

        String alert = "[" + errorType + "] " + message;
        sendNtfy(alert, "_ntfy_err_" + errorType, 0); // throttle handled above
        DBG_ERROR("[GrafanaLogger] Error(%s): %s\n",
                  errorType.c_str(), message.c_str());
    }

    /**
     * Print all stored errors to serial.
     */
    void printAllErrors() const {
        for (auto& kv : _errors) {
            DBG_INFO("Errors[%s]:\n", kv.first.c_str());
            for (auto& msg : kv.second) {
                DBG_INFO("  - %s\n", msg.c_str());
            }
        }
    }

private:
    GrafanaLogger() {}

    // --- State ---------------------------------------------------------------
    bool     _initialized      = false;

    // Grafana reachability — independent state
    bool     _grafanaReachable = true;
    uint32_t _backoffMs        = GRAFANA_BACKOFF_INITIAL_MS;
    uint8_t  _failureCount     = 0;
    unsigned long _lastGrafanaCheck  = 0;
    unsigned long _nextRetryMs       = 0;

    // NTFY reachability — completely separate from Grafana state
    bool     _ntfyReachable    = true;
    uint32_t _ntfyBackoffMs    = 30000;   //  30 s initial
    uint8_t  _ntfyFailureCount = 0;
    unsigned long _nextNtfyRetryMs   = 0;

    // Device reset report (deferred until WiFi connects)
    bool     _pendingResetReport  = false;
    String   _resetReason;
    unsigned long _resetReportAfterMs = 0;

    unsigned long _lastLowHeapNotify = 0;
    String _ntfyUrl;

    // Per-key last-send timestamps (ms)
    std::map<String, unsigned long> _lastSent;

    // Error store: type → [last 2 messages]
    std::map<String, std::vector<String>> _errors;

    // --- Helpers -------------------------------------------------------------

    /**
     * Per-key rate limiter with random jitter (anti-starvation).
     * Mirrors log.throttle_check() from log.lua.
     */
    bool _throttleCheck(const String& key, uint32_t intervalMs) {
        unsigned long now = millis();

        // First call ever for this key: always allow.
        // Lua avoids this bug because time.get() returns Unix epoch (~1.7B s),
        // so (epoch - 0) >> any interval. millis() starts at 0, so we must
        // special-case the "never called" state explicitly.
        if (!_lastSent.count(key)) {
            _lastSent[key] = now;  // record without jitter so first interval is correct
            return true;
        }

        unsigned long last = _lastSent[key];

        // If last is in the future (jitter from a previous call), treat as blocked
        if (now < last) {
            DBG_VERBOSE("[GrafanaLogger] Throttle(%s): jitter pending (%lums)\n",
                        key.c_str(), (unsigned long)(last - now));
            return false;
        }

        unsigned long elapsed = now - last;
        if (elapsed < intervalMs) {
            DBG_VERBOSE("[GrafanaLogger] Throttle(%s): %lums left\n",
                        key.c_str(), (unsigned long)(intervalMs - elapsed));
            return false;
        }

        // Allow: add small jitter to stagger concurrent senders (mirrors log.lua)
        _lastSent[key] = now + (uint32_t)random(0, 5000);
        return true;
    }

    /**
     * Ensure Grafana is reachable, handling back-off state.
     */
    bool _ensureGrafanaReachable() {
        if (_grafanaReachable) return true;

        // Still in back-off window
        if (millis() < _nextRetryMs) return false;

        // Back-off expired — probe now
        _probeGrafana();
        return _grafanaReachable;
    }

    /**
     * Non-blocking Grafana health probe.
     * Uses a short GET to the configured URL (expects any HTTP response).
     * Mirrors the spirit of log.lua safe_http_post preflight checks.
     */
    void _probeGrafana() {
        if (WiFi.status() != WL_CONNECTED) return;

        _lastGrafanaCheck = millis();

        HTTPClient http;
        // Probe base URL (expects 401/204/200 — any response means server is up)
        String probeUrl = String(URL);
        // Strip path from URL if present — we just need host reachability
        // URL format: http://host:port/write?... → probe http://host:port/
        int pathStart = probeUrl.indexOf('/', 7); // skip "http://"
        if (pathStart > 0) {
            probeUrl = probeUrl.substring(0, pathStart) + "/";
        }

        http.begin(probeUrl);
        http.setTimeout(3000);
        int code = http.GET();
        http.end();

        bool reachable = (code > 0); // any HTTP response = server alive

        if (reachable && !_grafanaReachable) {
            // Recovery
            _grafanaReachable = true;
            _failureCount     = 0;
            _backoffMs        = GRAFANA_BACKOFF_INITIAL_MS;
            _nextRetryMs      = 0;
            DBG_INFO("[GrafanaLogger] Grafana reconnected (HTTP %d)\n", code);
            sendNtfy("\xE2\x9C\x85 Grafana reconnected after downtime",
                     "_ntfy_g_up_", 60000);

        } else if (!reachable) {
            _failureCount++;
            _grafanaReachable = false;

            // Escalating back-off schedule (mirrors lua throttle_type_interval)
            if      (_failureCount == 1) _backoffMs = GRAFANA_BACKOFF_INITIAL_MS;
            else if (_failureCount == 2) _backoffMs = GRAFANA_BACKOFF_SECOND_MS;
            else if (_failureCount == 3) _backoffMs = GRAFANA_BACKOFF_THIRD_MS;
            else                          _backoffMs = GRAFANA_BACKOFF_MAX_MS;

            _nextRetryMs = millis() + _backoffMs;
            DBG_ERROR("[GrafanaLogger] Grafana unreachable (attempt %d), back-off %lus\n",
                      _failureCount, (unsigned long)(_backoffMs / 1000));

            // Only notify once on first failure (edge-detect) — use dedicated key
            if (_failureCount == 1) {
                sendNtfy("\xE2\x9A\xA0\xEF\xB8\x8F Grafana unreachable \xE2\x80\x94 data sends paused",
                         "_ntfy_g_down_", 60000);
            }
        }
    }

    /**
     * Perform the actual HTTP POST to Grafana.
     * Returns true on HTTP 204 (InfluxDB success).
     */
    bool _doPost(const String& data) {
        HTTPClient http;
        WiFiClient client;

        http.begin(client, URL);
        http.setTimeout(GRAFANA_HTTP_TIMEOUT_MS);
        http.addHeader("Content-Type", "text/plain");
        http.addHeader("Authorization", "Basic " + String(TOKEN_GRAFANA));

        int code = http.POST(data);
        http.end();

        if (code == 204) {
            // On first successful post after downtime, reset failure state
            if (_failureCount > 0 && !_grafanaReachable) {
                _grafanaReachable = true;
                _failureCount     = 0;
                _backoffMs        = GRAFANA_BACKOFF_INITIAL_MS;
            }
            return true;
        }

        DBG_ERROR("[GrafanaLogger] POST failed: HTTP %d\n", code);

        // Treat persistent errors as unreachable
        if (code <= 0) {
            // Connection-level failure — trigger reachability logic
            if (_grafanaReachable) {
                _grafanaReachable = false;
                _failureCount     = 1;
                _backoffMs        = GRAFANA_BACKOFF_INITIAL_MS;
                _nextRetryMs      = millis() + _backoffMs;
                sendNtfy("\xE2\x9A\xA0\xEF\xB8\x8F Grafana unreachable \xE2\x80\x94 data sends paused",
                         "_ntfy_g_down_", 60000);
            }
        }
        return false;
    }

    /**
     * Low-heap NTFY notification with 5-minute cooldown.
     */
    void _maybeNotifyLowHeap() {
        unsigned long now = millis();
        if (now - _lastLowHeapNotify > 300000UL) {
            _lastLowHeapNotify = now;
            sendNtfy("\xF0\x9F\x94\xB4 Low heap: " + String(ESP.getFreeHeap()) + " bytes",
                     "_ntfy_heap_", 300000);
        }
    }
    /**
     * Handle an NTFY send failure — updates NTFY-only back-off.
     * Does NOT touch _grafanaReachable or any Grafana state.
     */
    void _handleNtfyFailure(int code) {
        _ntfyFailureCount++;
        _ntfyReachable = false;

        // Escalating back-off for NTFY (independent of Grafana schedule)
        if      (_ntfyFailureCount == 1) _ntfyBackoffMs =  30000;  // 30 s
        else if (_ntfyFailureCount == 2) _ntfyBackoffMs =  60000;  //  1 min
        else if (_ntfyFailureCount == 3) _ntfyBackoffMs = 300000;  //  5 min
        else                              _ntfyBackoffMs = 600000;  // 10 min

        _nextNtfyRetryMs = millis() + _ntfyBackoffMs;
        DBG_VERBOSE("[GrafanaLogger] NTFY failed (HTTP %d, attempt %d), back-off %lus\n",
                    code, _ntfyFailureCount, (unsigned long)(_ntfyBackoffMs / 1000));
    }

    /**
     * Send a raw "log" measurement to Grafana (InfluxDB line protocol).
     * Mirrors log.lua send_to_grafana() — uses "log" measurement, not "medicionesCO2".
     * Bypasses throttle/back-off so critical events (reset) are always attempted.
     */
    void _sendGrafanaLog(const String& message) {
        if (WiFi.status() != WL_CONNECTED) return;
        if (ESP.getFreeHeap() < GRAFANA_MIN_HEAP_BYTES) return;

        // Build device tag from MAC (consistent with medicionesCO2 measurement)
        String mac = WiFi.macAddress();
        mac.replace(":", "");
        mac.toLowerCase();

        // Escape quotes inside message for InfluxDB line protocol
        String escaped = message;
        escaped.replace("\"", "\\\"" );

        unsigned long long ts = (unsigned long long)time(nullptr) * 1000000000ULL;
        String data = "log,device=moni-" + mac +
                      " message=\"" + escaped + "\" " +
                      String((uint64_t)ts);

        HTTPClient http;
        WiFiClient wc;
        http.begin(wc, URL);
        http.setTimeout(GRAFANA_HTTP_TIMEOUT_MS);
        http.addHeader("Content-Type", "text/plain");
        http.addHeader("Authorization", "Basic " + String(TOKEN_GRAFANA));
        int code = http.POST(data);
        http.end();

        if (code == 204) {
            DBG_INFO("[GrafanaLogger] Log entry sent to Grafana\n");
        } else {
            DBG_VERBOSE("[GrafanaLogger] Grafana log failed: HTTP %d\n", code);
        }
    }

    /**
     * Returns a human-readable string for the ESP32 reset reason.
     * Covers all esp_reset_reason_t values.
     */
    String _resetReasonStr() {
        switch (esp_reset_reason()) {
            case ESP_RST_POWERON:   return "Power-on";
            case ESP_RST_EXT:       return "External pin";
            case ESP_RST_SW:        return "Software (ESP.restart)";
            case ESP_RST_PANIC:     return "Exception/panic";
            case ESP_RST_INT_WDT:   return "Interrupt watchdog";
            case ESP_RST_TASK_WDT:  return "Task watchdog";
            case ESP_RST_WDT:       return "Other watchdog";
            case ESP_RST_DEEPSLEEP: return "Deep-sleep wake";
            case ESP_RST_BROWNOUT:  return "Brownout (low voltage)";
            case ESP_RST_SDIO:      return "SDIO reset";
            default:                return "Unknown (" + String((int)esp_reset_reason()) + ")";
        }
    }
};

#endif // GRAFANA_LOGGER_H
