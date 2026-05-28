/**
 * test/testQuadraticCalibration.cpp
 *
 * Tests del modo de calibración cuadrática (issue #19) para sensores ADC:
 *   - SensorCapacitive
 *   - HD38Sensor
 *
 * Verifica:
 *  1. LINEAR (default) preserva el comportamiento previo (map dry/wet + clamp 0-100).
 *  2-3. QUADRATIC aplica y = a·x² + b·x + c con coeficientes arbitrarios.
 *  4-5. QUADRATIC NO clampea — devuelve crudo, incluso fuera de 0-100.
 *  6. HD38 con voltage_divider trunca raw a 0-3100 antes de aplicar la curva.
 *  7. setCalibration(dry, wet) vuelve a modo LINEAR tras un setQuadraticCalibration.
 *
 * Patrón: Unity + ArduinoFake — mockea `analogRead` para tests determinísticos.
 */

#include <unity.h>

#ifndef ARDUINO
#include <ArduinoFake.h>
using namespace fakeit;
#include "MockESP.h"  // proveé el global ESP (getEfuseMac) usado por SensorBase

// Stubs ESP32-specific no provistos por ArduinoFake — no-ops para tests nativos
#ifndef ADC_11db
#define ADC_11db 3
#endif
static inline void analogReadResolution(int) {}
static inline void analogSetPinAttenuation(int, int) {}
#else
#include <Arduino.h>
#endif

#include "sensors/SensorCapacitive.h"
#include "sensors/HD38Sensor.h"

// Helpers para mockear el entorno Arduino en tests nativos
#ifndef ARDUINO
// `map` está declarada como función en ArduinoFake — la redirigimos al cálculo real.
// `constrain` es macro en ArduinoFake, no requiere stub.
static long real_map(long x, long in_min, long in_max, long out_min, long out_max) {
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

static void setupFakes() {
    // pinMode y analogRead se llaman en init()/read() — fakeit exige
    // que estén explícitamente expectadas antes de invocarse.
    When(Method(ArduinoFake(), pinMode)).AlwaysReturn();
    When(Method(ArduinoFake(), analogRead)).AlwaysReturn(0);
    When(Method(ArduinoFake(), map)).AlwaysDo(real_map);
}
static void mockAnalogRead(int value) {
    When(Method(ArduinoFake(), analogRead)).AlwaysReturn(value);
}
#else
static void setupFakes() {}
static void mockAnalogRead(int) {}
#endif

// ── Helper: crear sensor capacitivo listo para leer ───────────────────────
static SensorCapacitive makeCap(int dry = 4095, int wet = 0) {
    setupFakes();
    SensorCapacitive s(34, dry, wet);
    s.init();
    return s;
}

static HD38Sensor makeHd38(bool voltageDivider = false) {
    setupFakes();
    HD38Sensor s(35, -1, voltageDivider, false, "hd38_test");
    s.init();
    return s;
}

// ── Tests ────────────────────────────────────────────────────────────────

void test_capacitive_default_is_linear() {
    SensorCapacitive s = makeCap(4095, 0);
    TEST_ASSERT_EQUAL_INT(SensorCapacitive::LINEAR, s.getCalibMode());

    mockAnalogRead(2048);
    s.read();
    // map(2048, 4095, 0, 0, 100) ≈ 50
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 50.0f, s.getMoisture());
}

void test_capacitive_quadratic_lineal_degenerate() {
    // y = 0.025·x - 50 expresada como cuadrática (a=0)
    SensorCapacitive s = makeCap();
    s.setQuadraticCalibration(0.0f, 0.025f, -50.0f);
    TEST_ASSERT_EQUAL_INT(SensorCapacitive::QUADRATIC, s.getCalibMode());

    mockAnalogRead(2000);
    s.read();
    // 0.025*2000 - 50 = 0
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, s.getMoisture());

    mockAnalogRead(4000);
    s.read();
    // 0.025*4000 - 50 = 50
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 50.0f, s.getMoisture());
}

void test_capacitive_quadratic_real_curve() {
    // y = 1e-6·x² - 0.005·x + 8
    SensorCapacitive s = makeCap();
    s.setQuadraticCalibration(1e-6f, -0.005f, 8.0f);

    mockAnalogRead(1000);
    s.read();
    // 1e-6*1000² + (-0.005)*1000 + 8 = 1 - 5 + 8 = 4
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 4.0f, s.getMoisture());
}

void test_capacitive_quadratic_no_clamp_high() {
    // Sin clamp: y = x con raw=4095 → 4095
    SensorCapacitive s = makeCap();
    s.setQuadraticCalibration(0.0f, 1.0f, 0.0f);

    mockAnalogRead(4095);
    s.read();
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 4095.0f, s.getMoisture());
}

void test_capacitive_quadratic_no_clamp_negative() {
    // Sin clamp: y = -x con raw=100 → -100 (negativo permitido)
    SensorCapacitive s = makeCap();
    s.setQuadraticCalibration(0.0f, -1.0f, 0.0f);

    mockAnalogRead(100);
    s.read();
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -100.0f, s.getMoisture());
}

void test_hd38_quadratic_with_voltage_divider_truncates_raw() {
    // HD38 con voltage_divider=true: raw se trunca a 0-3100 antes de la curva.
    // y = 0.001 * raw_truncado → con raw=4095 efectivo es 3100 → moisture=3.1
    HD38Sensor s = makeHd38(/*voltageDivider*/ true);
    s.setQuadraticCalibration(0.0f, 0.001f, 0.0f);

    mockAnalogRead(4095);
    s.read();
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 3.1f, s.getMoisture());
}

void test_setCalibration_reverts_to_linear() {
    // Tras un setQuadraticCalibration, llamar setCalibration(dry,wet)
    // debe volver el sensor a modo LINEAR.
    SensorCapacitive s = makeCap();
    s.setQuadraticCalibration(1e-6f, -0.005f, 8.0f);
    TEST_ASSERT_EQUAL_INT(SensorCapacitive::QUADRATIC, s.getCalibMode());

    s.setCalibration(4095, 0);
    TEST_ASSERT_EQUAL_INT(SensorCapacitive::LINEAR, s.getCalibMode());

    mockAnalogRead(2048);
    s.read();
    // Vuelve a ser lineal → ~50
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 50.0f, s.getMoisture());
}

// ── Entry point ──────────────────────────────────────────────────────────

void test_isolation_construct_only() {
    // Test minimal — solo construye el sensor sin init/read
    SensorCapacitive s(34, 4095, 0);
    TEST_ASSERT_EQUAL_INT(SensorCapacitive::LINEAR, s.getCalibMode());
}

void test_isolation_construct_and_init() {
    setupFakes();
    SensorCapacitive s(34, 4095, 0);
    bool ok = s.init();
    TEST_ASSERT_TRUE(ok);
    TEST_ASSERT_TRUE(s.isActive());
}

void runQuadraticCalibrationTests() {
    RUN_TEST(test_isolation_construct_only);
    RUN_TEST(test_isolation_construct_and_init);
    RUN_TEST(test_capacitive_default_is_linear);
    RUN_TEST(test_capacitive_quadratic_lineal_degenerate);
    RUN_TEST(test_capacitive_quadratic_real_curve);
    RUN_TEST(test_capacitive_quadratic_no_clamp_high);
    RUN_TEST(test_capacitive_quadratic_no_clamp_negative);
    RUN_TEST(test_hd38_quadratic_with_voltage_divider_truncates_raw);
    RUN_TEST(test_setCalibration_reverts_to_linear);
}
