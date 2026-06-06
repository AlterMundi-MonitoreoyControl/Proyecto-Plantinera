#ifndef HD38_SENSOR_H
#define HD38_SENSOR_H

#include "ISensor.h"
#include "IMoistureSensor.h"
#include "SensorBase.h"
#include <Arduino.h>
#include "../debug.h"

// Pin ADC por defecto del HD-38. En ESP32-S3 el GPIO35 no es ADC (y en N16R8
// lo usa la PSRAM octal): usamos GPIO6 (ADC1_CH5). Clásico: GPIO35 (ADC1_CH7).
#if defined(CONFIG_IDF_TARGET_ESP32S3)
#define HD38_PIN 6
#else
#define HD38_PIN 35
#endif

/**
 * Sensor HD-38 - Soil Moisture / Rain Sensor
 *
 * Features:
 *   - LM393 comparator IC
 *   - Supply voltage: 3.3-12V
 *   - Analog output: 0-Vin (requires 2:1 divider for ESP32 when used with 5V esp32 ADC only reads 3.3V)
 *   - Digital output: 0/3.3 V with adjustable threshold via potentiometer
 *
 * Wiring (analog with voltage divider):
 *   Sensor AOUT -> ESP32 ADC pin
 *   Sensor VCC  -> 3.3V
 *   Sensor GND  -> GND
 */
class HD38Sensor : public SensorBase, public IMoistureSensor {
public:
    enum CalibMode { LINEAR, QUADRATIC };

private:
    int analogPin;
    int digitalPin;
    bool useVoltageDivider;
    bool invertLogic;
    float moisture;
    int rawValue;
    bool digitalState;
    bool active;
    int dryValue;
    int wetValue;
    String sensorName;
    CalibMode calibMode;
    float calibA;
    float calibB;
    float calibC;

public:
    HD38Sensor(int aPin = HD38_PIN,
               int dPin = -1,
               bool voltageDivider = true,
               bool invert = false,
               const char* name = "HD38")
        : SensorBase(SensorClass::ANALOG_ADC, (uint8_t)(aPin >= 0 ? aPin : 0xFF)),
          analogPin(aPin),
          digitalPin(dPin),
          useVoltageDivider(voltageDivider),
          invertLogic(invert),
          moisture(0),
          rawValue(0),
          digitalState(false),
          active(false),
          dryValue(4095),
          wetValue(0),
          sensorName(name),
          calibMode(LINEAR),
          calibA(0), calibB(0), calibC(0) {}

    bool init() override {
        DBG_VERBOSE("[HD38] '%s': a=%d d=%d div=%s\n",
                      sensorName.c_str(), analogPin, digitalPin,
                      useVoltageDivider ? "y" : "n");

        if (analogPin >= 0) {
            pinMode(analogPin, INPUT);
            analogReadResolution(12);              // 12-bit → 0-4095
            analogSetPinAttenuation(analogPin, ADC_11db); // full 0-3.3V range
        }

        if (digitalPin >= 0) {
            pinMode(digitalPin, INPUT);
        }

        if (analogPin < 0 && digitalPin < 0) {
            DBG_ERROR("[HD38] No pins configured\n");
            active = false;
            return false;
        }

        active = true;
        DBG_INFO("[HD38] OK\n");
        return true;
    }

    bool dataReady() override {
        return active;
    }

    bool read() override {
        if (!active) return false;

        if (analogPin >= 0) {
            rawValue = analogRead(analogPin);

            if (useVoltageDivider) {
                rawValue = constrain(rawValue, 0, 3100);
            }

            if (calibMode == QUADRATIC) {
                // y = a*x^2 + b*x + c — sin clamp
                moisture = calibA * (float)rawValue * (float)rawValue
                         + calibB * (float)rawValue
                         + calibC;
                DBG_INFO("[HD38] '%s' pin=%d Raw=%d M=%.3f (a=%.6f b=%.6f c=%.3f)\n",
                         sensorName.c_str(), analogPin, rawValue, moisture, calibA, calibB, calibC);
            } else {
                moisture = map(rawValue, dryValue, wetValue, 0, 100);
                moisture = constrain(moisture, 0, 100);
                DBG_INFO("[HD38] '%s' pin=%d Raw=%d M=%.1f%% (dry=%d wet=%d)\n",
                         sensorName.c_str(), analogPin, rawValue, moisture, dryValue, wetValue);
            }
        }

        if (digitalPin >= 0) {
            digitalState = digitalRead(digitalPin);
            if (invertLogic) {
                digitalState = !digitalState;
            }
            DBG_VERBOSE("[HD38] '%s' D=%s\n",
                         sensorName.c_str(), digitalState ? "WET" : "DRY");
        }

        return true;
    }

    int getRawValue() const { return rawValue; }
    int getDryValue() const { return dryValue; }
    int getWetValue() const { return wetValue; }
    int getPin()      const { return analogPin; }

    // IMoistureSensor
    float getMoisture() override { return moisture; }

    const char* getSensorType() override {
        static char typeName[32];
        snprintf(typeName, sizeof(typeName), "hd38_%s", sensorName.c_str());
        return typeName;
    }

    const char* getSensorID() override {
        static char sensorId[32];
        snprintf(sensorId, sizeof(sensorId), "m-adc-%d", analogPin);
        return sensorId;
    }

    const char* getMeasurementsString() override {
        static char measString[64];
        snprintf(measString, sizeof(measString), "moisture=%.1f,Raw=%d", moisture, rawValue);
        return measString;
    }

    bool isActive() override { return active; }

    bool isWet() { return digitalState; }

    void setCalibration(int dry, int wet) {
        dryValue = dry;
        wetValue = wet;
        calibMode = LINEAR;
        DBG_INFO("[HD38] Cal LINEAR: dry=%d wet=%d\n", dry, wet);
    }

    void setQuadraticCalibration(float a, float b, float c) {
        calibA = a;
        calibB = b;
        calibC = c;
        calibMode = QUADRATIC;
        DBG_INFO("[HD38] Cal QUADRATIC: a=%.6f b=%.6f c=%.3f\n", a, b, c);
    }

    CalibMode getCalibMode() const { return calibMode; }
    float getCalibA()       const { return calibA; }
    float getCalibB()       const { return calibB; }
    float getCalibC()       const { return calibC; }

    // ── Mediator interface ────────────────────────────────────────────────
    SensorKey getKey() const override { return SensorBase::getKey(); }
    void notifyMediator(ControlMediator& mediator) override {
        if (!active) return;
        _notify(mediator, SensorVariable::MOISTURE, moisture);
        _notify(mediator, SensorVariable::RAW_ADC, rawValue);
    }
};

#endif // HD38_SENSOR_H
