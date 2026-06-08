#ifndef SENSOR_CAPACITIVE_H
#define SENSOR_CAPACITIVE_H

#include "ISensor.h"
#include "IMoistureSensor.h"
#include "SensorBase.h"
#include <Arduino.h>
#include "../debug.h"

// Pin ADC por defecto del sensor capacitivo.
// En ESP32-S3 el GPIO34 NO existe como ADC -> usamos GPIO5 (ADC1_CH4).
// En ESP32 clásico se mantiene GPIO34 (ADC1_CH6, input-only).
#if defined(CONFIG_IDF_TARGET_ESP32S3)
#define CAPACITIVE_PIN 5
#else
#define CAPACITIVE_PIN 34
#endif
#define ADC_MAX 4095
#define ADC_MIN 0

class SensorCapacitive : public SensorBase, public IMoistureSensor {
public:
    enum CalibMode { LINEAR, QUADRATIC };

private:
    int pin;
    float moisture;
    int rawValue;
    bool active;
    int dryValue;
    int wetValue;
    CalibMode calibMode;
    float calibA;
    float calibB;
    float calibC;

public:
    SensorCapacitive(int adcPin = CAPACITIVE_PIN, int dry = ADC_MAX, int wet = ADC_MIN)
        : SensorBase(SensorClass::ANALOG_ADC, (uint8_t)(adcPin >= 0 ? adcPin : 0xFF)),
          pin(adcPin), moisture(0), rawValue(0), active(false),
          dryValue(dry), wetValue(wet),
          calibMode(LINEAR), calibA(0), calibB(0), calibC(0) {}

    bool init() override {
        pinMode(pin, INPUT);
        analogReadResolution(12);              // 12-bit → 0-4095
        analogSetPinAttenuation(pin, ADC_11db);
        active = true;
        DBG_INFO("[Capacitive] pin %d, 12-bit, 3.3V range OK\n", pin);
        return true;
    }

    bool dataReady() override {
        return active;
    }

    bool read() override {
        if (!active) return false;

        rawValue = analogRead(pin);

        if (calibMode == QUADRATIC) {
            // y = a*x^2 + b*x + c — sin clamp (devuelve crudo)
            moisture = calibA * (float)rawValue * (float)rawValue
                     + calibB * (float)rawValue
                     + calibC;
            DBG_INFO("[Capacitive] pin=%d Raw=%d M=%.3f (a=%.6f b=%.6f c=%.3f)\n",
                     pin, rawValue, moisture, calibA, calibB, calibC);
        } else {
            moisture = map(rawValue, dryValue, wetValue, 0, 100);
            moisture = constrain(moisture, 0, 100);
            DBG_INFO("[Capacitive] pin=%d Raw=%d M=%.1f%% (dry=%d wet=%d)\n",
                     pin, rawValue, moisture, dryValue, wetValue);
        }
        return true;
    }

    int getRawValue() const { return rawValue; }
    int getDryValue() const { return dryValue; }
    int getWetValue() const { return wetValue; }
    int getPin()      const { return pin; }

    // IMoistureSensor
    float getMoisture() override { return moisture; }

    const char* getSensorType() override { return "Capacitive"; }

    const char* getSensorID() override {
        static char idString[16];
        snprintf(idString, sizeof(idString), "m-adc-%d", pin);
        return idString;
    }

    const char* getMeasurementsString() override {
        static char measString[32];
        snprintf(measString, sizeof(measString), "moisture=%.1f,Raw=%d", moisture, rawValue);
        return measString;
    }

    bool isActive() override { return active; }

    void setCalibration(int dry, int wet) {
        dryValue = dry;
        wetValue = wet;
        calibMode = LINEAR;
        DBG_INFO("[Capacitive] Cal LINEAR: dry=%d wet=%d\n", dry, wet);
    }

    void setQuadraticCalibration(float a, float b, float c) {
        calibA = a;
        calibB = b;
        calibC = c;
        calibMode = QUADRATIC;
        DBG_INFO("[Capacitive] Cal QUADRATIC: a=%.6f b=%.6f c=%.3f\n", a, b, c);
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

#endif // SENSOR_CAPACITIVE_H
