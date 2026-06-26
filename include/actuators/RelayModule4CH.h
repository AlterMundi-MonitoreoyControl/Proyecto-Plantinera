#ifndef RELAY_MODULE_4CH_H
#define RELAY_MODULE_4CH_H

#include "../ModbusManager.h"
#include "../core/ActuatorBase.h"
#include "../core/ControlMediator.h"
#include "../debug.h"
#include <Arduino.h>

/**
 * 4-Channel RS485 Modbus Relay Module (LC-Modbus-4R-D7)
 *
 * Provides four IActuator channels via getChannel(ch), ch = 0..3.
 * actuatorId encoding: bits[7:4] = Modbus address, bits[3:0] = channel (0-3).
 * Use RelayModule4CH::makeActuatorId(addr, ch) to build the ID.
 *
 * Features:
 * - 4 Relays (NO/NC), 10A/250VAC
 * - 4 Optocoupler digital inputs (IN1-IN4, DC3.3-30V)
 * - Modbus RTU (9600 8N1 default), addr default 0xFF (255)
 *
 * Addressing:
 * - Relay ch:   FC05 write coil at coil address ch (0x0000 – 0x0003)
 * - Input ch:   FC02 read discrete input at addr ch (0x0000 – 0x0003)
 */
class RelayModule4CH {
public:
    /** Build actuatorId: high nibble = Modbus address, low nibble = channel */
    static uint8_t makeActuatorId(uint8_t modbusAddr, uint8_t channel) {
        return (uint8_t)((modbusAddr << 4) | (channel & 0x0F));
    }

    class ChannelActuator : public ActuatorBase {
    private:
        RelayModule4CH* _module;
        uint8_t _channel;
        String _nameCache;
        uint32_t _startTime;
        uint32_t _durationMs;
        bool _inverted;

    public:
        ChannelActuator(RelayModule4CH* module, uint8_t channel)
            : _module(module), _channel(channel), _startTime(0), _durationMs(0), _inverted(false) {}

        void configure(uint32_t maxOn, uint32_t minOff, bool inverted) {
            ActuatorBase::configure(maxOn, minOff);
            _inverted = inverted;
        }

        void updateName() {
            _nameCache = _module->getAlias();
            if (_nameCache.length() == 0) {
                _nameCache = "Relay4 " + String(_module->getAddress());
            }
            _nameCache += " CH" + String(_channel + 1);
        }

        uint8_t getId() const override {
            return RelayModule4CH::makeActuatorId(_module->getAddress(), _channel);
        }
        const char* getName() const override { return _nameCache.c_str(); }
        bool begin() override { return true; }

        void _turnOn(uint32_t effDuration) override {
            _durationMs = effDuration;
            if (effDuration > 0) _startTime = millis();
            _module->setRelay(_channel, _inverted ? false : true);
        }

        void _turnOff() override {
            if (getState() == true) {
                _recordTurnOff();
            }
            _durationMs = 0;
            _module->setRelay(_channel, _inverted ? true : false);
        }

        void tick() override {
            if (_durationMs > 0 && (millis() - _startTime >= _durationMs)) {
                _durationMs = 0;
                if (getState() == true) {
                    _recordTurnOff();
                }
                _module->setRelay(_channel, _inverted ? true : false);
            }
        }

        bool getState() const override { return _module->getState(_channel) ^ _inverted; }

        bool getStatus() const override {
            return _module->_active;
        }
    };

private:
    uint8_t _address;
    String  _alias;
    bool    _relayState[4];
    bool    _inputState[4];

    bool _active;
    int  _failureCount;
    int  _inactiveCheckCount;

    static bool _cbComplete;
    static bool _cbError;

    static bool modbusCallback(Modbus::ResultCode event, uint16_t transactionId, void* data) {
        _cbComplete = true;
        _cbError = (event != Modbus::EX_SUCCESS);
        DBG_VERBOSE("[Relay4 CB] %d\n", event);
        return true;
    }

    ChannelActuator _ch0;
    ChannelActuator _ch1;
    ChannelActuator _ch2;
    ChannelActuator _ch3;

public:
    RelayModule4CH(uint8_t address = 255, String alias = "")
        : _address(address), _alias(alias),
          _active(false), _failureCount(0), _inactiveCheckCount(0),
          _ch0(this, 0), _ch1(this, 1), _ch2(this, 2), _ch3(this, 3) {
        for (int i = 0; i < 4; i++) {
            _relayState[i] = false;
            _inputState[i] = false;
        }
        _ch0.updateName();
        _ch1.updateName();
        _ch2.updateName();
        _ch3.updateName();
    }

    IActuator* getChannel(uint8_t ch) {
        switch (ch) {
            case 0: return &_ch0;
            case 1: return &_ch1;
            case 2: return &_ch2;
            case 3: return &_ch3;
        }
        return nullptr;
    }

    void configureChannel(uint8_t ch, uint32_t maxOn, uint32_t minOff, bool inverted) {
        switch (ch) {
            case 0: _ch0.configure(maxOn, minOff, inverted); break;
            case 1: _ch1.configure(maxOn, minOff, inverted); break;
            case 2: _ch2.configure(maxOn, minOff, inverted); break;
            case 3: _ch3.configure(maxOn, minOff, inverted); break;
        }
    }

    void setAlias(String alias) {
        _alias = alias;
        _ch0.updateName(); _ch1.updateName();
        _ch2.updateName(); _ch3.updateName();
    }
    String  getAlias()   const { return _alias; }
    uint8_t getAddress() const { return _address; }

    bool getState(uint8_t ch) const {
        if (ch < 4) return _relayState[ch];
        return false;
    }

    bool getInputState(uint8_t ch) const {
        if (ch < 4) return _inputState[ch];
        return false;
    }

    bool init() {
        DBG_VERBOSE("[Relay4 %d] Init...\n", _address);
        if (!ModbusManager::getInstance().isInitialized()) {
            DBG_ERROR("[Relay4 %d] Modbus not ready\n", _address);
            _active = false;
            return false;
        }
        if (syncState()) {
            _active = true;
            _failureCount = 0;
            DBG_INFO("[Relay4 %d] Init OK\n", _address);
        } else {
            _active = false;
            DBG_ERROR("[Relay4 %d] Not responding\n", _address);
        }
        return _active;
    }

    bool isActive() {
        if (_active) {
            _inactiveCheckCount = 0;
            return true;
        }
        if (!ModbusManager::getInstance().isInitialized()) return false;

        _inactiveCheckCount++;
        if (_inactiveCheckCount >= 10) {
            DBG_VERBOSE("[Relay4 %d] Recovery attempt\n", _address);
            _inactiveCheckCount = 0;
            return init();
        }
        return false;
    }

    /**
     * Set relay state (FC05)
     * @param ch    0–3
     * @param state true=ON, false=OFF
     */
    bool setRelay(uint8_t ch, bool state) {
        if (!isActive()) return false;
        ModbusRTU* mb = ModbusManager::getInstance().getModbus();
        if (!mb) return false;

        delay(20);
        DBG_VERBOSE("[Relay4 %d] ch%d -> %s\n", _address, ch, state ? "ON" : "OFF");

        mb->task();
        _cbComplete = false;
        _cbError    = false;

        if (!mb->writeCoil(_address, ch, state, modbusCallback)) return false;

        unsigned long start = millis();
        while (!_cbComplete && millis() - start < 250) {
            mb->task();
            delay(10);
        }

        if (_cbComplete && !_cbError) {
            if (ch < 4) _relayState[ch] = state;
            _failureCount = 0;
            DBG_VERBOSE("[Relay4 %d] ch%d OK\n", _address, ch);
            return true;
        }

        _failureCount++;
        DBG_ERROR("[Relay4 %d] ch%d FAIL (%d)\n", _address, ch, _failureCount);
        if (_failureCount >= 5) {
            _active = false;
            DBG_ERROR("[Relay4 %d] Disabled\n", _address);
        }
        return false;
    }

    bool toggleRelay(uint8_t ch) {
        if (ch >= 4) return false;
        if (!isActive()) return false;
        return setRelay(ch, !_relayState[ch]);
    }

    /**
     * Read coils 0–3 from device and update local cache (FC01)
     */
    bool syncState() {
        ModbusRTU* mb = ModbusManager::getInstance().getModbus();
        if (!mb) return false;

        delay(50);
        mb->task();
        _cbComplete = false;
        _cbError    = false;

        bool coils[8];
        if (mb->readCoil(_address, 0, coils, 8, modbusCallback)) {
            unsigned long start = millis();
            while (!_cbComplete && millis() - start < 250) {
                mb->task();
                delay(10);
            }
        }

        if (_cbComplete && !_cbError) {
            for (int i = 0; i < 4; i++) _relayState[i] = coils[i];
            _failureCount = 0;
            DBG_VERBOSE("[Relay4 %d] sync R0=%d R1=%d R2=%d R3=%d\n",
                        _address, _relayState[0], _relayState[1], _relayState[2], _relayState[3]);
            return true;
        }
        _failureCount++;
        DBG_ERROR("[Relay4 %d] sync FAIL (%d)\n", _address, _failureCount);
        if (_failureCount >= 5) { _active = false; }
        return false;
    }

    /**
     * Read discrete inputs 0–3 (FC02) and inject readings into mediator
     */
    bool syncInputs(ControlMediator& mediator) {
        ModbusRTU* mb = ModbusManager::getInstance().getModbus();
        if (!mb) return false;

        mb->task();
        _cbComplete = false;
        _cbError    = false;

        bool inputs[8];
        if (!mb->readIsts(_address, 0, inputs, 8, modbusCallback)) {
            DBG_ERROR("[Relay4 %d] Input read error\n", _address);
            return false;
        }

        unsigned long start = millis();
        while (!_cbComplete && millis() - start < 250) {
            mb->task();
            delay(10);
        }

        if (_cbComplete && !_cbError) {
            for (int i = 0; i < 4; i++) _inputState[i] = inputs[i];
            _failureCount = 0;
            DBG_VERBOSE("[Relay4 %d] IN1=%d IN2=%d IN3=%d IN4=%d\n",
                        _address, _inputState[0], _inputState[1], _inputState[2], _inputState[3]);

            static uint32_t inputCounter = 1;
            inputCounter++;

            static const SensorVariable varIds[4] = {
                SensorVariable::DIGITAL_IN_1, SensorVariable::DIGITAL_IN_2,
                SensorVariable::DIGITAL_IN_3, SensorVariable::DIGITAL_IN_4
            };

            for (int i = 0; i < 4; i++) {
                SensorReading r;
                r.key.deviceId = (uint8_t)(ESP.getEfuseMac() & 0xFF);
                r.key.sensorId = _address;
                r.key.varId    = (uint8_t)varIds[i];
                r.value        = _inputState[i] ? 1.0f : 0.0f;
                r.counter      = inputCounter;
                mediator.onSensorReading(r);
            }
            return true;
        }

        _failureCount++;
        DBG_ERROR("[Relay4 %d] Input FAIL (%d)\n", _address, _failureCount);
        if (_failureCount >= 3) { _active = false; }
        return false;
    }

    String getStatusJSON() {
        String json = "{";
        json += "\"type\":\"relay_4ch\",";
        json += "\"address\":" + String(_address) + ",";
        json += "\"alias\":\"" + _alias + "\",";
        json += "\"active\":" + String(_active ? "true" : "false") + ",";
        json += "\"r0\":"  + String(_ch0.getState() ? 1 : 0) + ",";
        json += "\"r1\":"  + String(_ch1.getState() ? 1 : 0) + ",";
        json += "\"r2\":"  + String(_ch2.getState() ? 1 : 0) + ",";
        json += "\"r3\":"  + String(_ch3.getState() ? 1 : 0) + ",";
        json += "\"state\":["
              + String(_ch0.getState() ? "true" : "false") + ","
              + String(_ch1.getState() ? "true" : "false") + ","
              + String(_ch2.getState() ? "true" : "false") + ","
              + String(_ch3.getState() ? "true" : "false") + "],";
        json += "\"input_state\":["
              + String(_inputState[0] ? "true" : "false") + ","
              + String(_inputState[1] ? "true" : "false") + ","
              + String(_inputState[2] ? "true" : "false") + ","
              + String(_inputState[3] ? "true" : "false") + "]";
        json += "}";
        return json;
    }

    String getGrafanaString() {
        String s = "";
        s += "relay1=" + String(_ch0.getState() ? 1 : 0);
        s += ",relay2=" + String(_ch1.getState() ? 1 : 0);
        s += ",relay3=" + String(_ch2.getState() ? 1 : 0);
        s += ",relay4=" + String(_ch3.getState() ? 1 : 0);
        s += ",in1=" + String(_inputState[0] ? 1 : 0);
        s += ",in2=" + String(_inputState[1] ? 1 : 0);
        s += ",in3=" + String(_inputState[2] ? 1 : 0);
        s += ",in4=" + String(_inputState[3] ? 1 : 0);
        return s;
    }
};

#endif // RELAY_MODULE_4CH_H
