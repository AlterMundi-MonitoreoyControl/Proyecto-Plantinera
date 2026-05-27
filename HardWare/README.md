# Proyecto Plantinera — Documentación de Hardware

Esquemáticos y guía de montaje para el sistema de monitoreo ESP32 S v1.1 (32 pines físicos: 16 por lado, 3×GND).

> **Nota de variante de placa**: el DevKit "ESP32 S v1.1" expone 32 pines (16 por lado). Verificar contra la serigrafía física si la placa tiene diferente número de GND o pines de alimentación.

## 📌 Tabla de Pinout

| GPIO | Función | Periférico | Protocolo | Notas |
|------|---------|-----------|-----------|-------|
| 21 | SDA | SCD30 + BME280 | I2C | Bus compartido |
| 22 | SCL | SCD30 + BME280 | I2C | Bus compartido |
| 4 | Data | DS18B20 × N | 1-Wire | Pull-up 4.7kΩ obligatorio |
| 34 | ADC IN | Sensor capacitivo | ADC1_CH6 | Input-only, 3.3V max |
| 35 | ADC IN | HD38 (suelo) | ADC1_CH7 | ⚠ Requiere protección si VCC=5V |
| 17 | TX | MAX485 (DI) | UART2 | RS485 transmisión |
| 16 | RX | MAX485 (RO) | UART2 | RS485 recepción |
| 18 | DE/RE | MAX485 | GPIO | Half-duplex control |

> **Nota:** GPIO34/35 son ADC1 (funcionan con WiFi activo). NO usar pines ADC2 (GPIO0,2,4,12-15,25-27) para lectura analógica con WiFi habilitado.

---

## 🔌 Conexiones por Bus

### I2C (GPIO21/22)
| Origen | Destino | Señal |
|--------|---------|-------|
| ESP32 GPIO21 | SCD30 SDA | I2C Data |
| ESP32 GPIO21 | BME280 SDA | I2C Data |
| ESP32 GPIO22 | SCD30 SCL | I2C Clock |
| ESP32 GPIO22 | BME280 SCL | I2C Clock |
| ESP32 3.3V | SCD30 VCC | Alimentación |
| ESP32 3.3V | BME280 VCC | Alimentación |

### OneWire (GPIO4)
| Origen | Destino | Señal |
|--------|---------|-------|
| ESP32 GPIO4 | DS18B20 DQ (todos) | Data bus |
| ESP32 3.3V | R 4.7kΩ → GPIO4 | Pull-up (obligatorio) |
| ESP32 3.3V | DS18B20 VDD (todos) | Alimentación |

### RS485 Modbus (GPIO16/17/18)
| Origen | Destino | Señal |
|--------|---------|-------|
| ESP32 GPIO17 | MAX485 DI | TX data |
| MAX485 RO | ESP32 GPIO16 | RX data |
| ESP32 GPIO18 | MAX485 DE+RE | Direction control |
| MAX485 A (D+) | Bus A | RS485 differential + |
| MAX485 B (D−) | Bus B | RS485 differential − |
| Bus A/B | TH-MB-04S | Sensor temp/hum (addr 1) |
| Bus A/B | Relay 2CH | Módulo relay (addr 2) |

### ADC Suelo (GPIO34/35)
| Origen | Destino | Señal |
|--------|---------|-------|
| Capacitivo AOUT | ESP32 GPIO34 | Analog (directo) |
| HD38 AOUT | 10kΩ → ESP32 GPIO35 | Analog (con protección) |

---

## 📐 Esquemáticos

### Diagrama General del Sistema
![Diagrama de bloques del sistema completo](schematics/sch_full_system.svg)

### Pinout ESP32 S v1.1
![Pinout del ESP32 con funciones asignadas](schematics/sch_esp32_pinout.svg)

### Bus I2C — SCD30 + BME280
![Esquemático del bus I2C con SCD30 y BME280](schematics/sch_i2c_sensors.svg)

### Bus OneWire — DS18B20
![Esquemático del bus OneWire con DS18B20 en cadena](schematics/sch_onewire.svg)

### Sensores ADC — Suelo
![Esquemático de sensores ADC con protección recomendada](schematics/sch_adc_soil.svg)

### Bus RS485 — Modbus RTU
![Esquemático del bus RS485 con MAX485, sensor TH y relay](schematics/sch_rs485_modbus.svg)

---

## 📦 BOM (Bill of Materials)

| # | Componente | Cantidad | Especificaciones | Función |
|---|-----------|----------|-----------------|---------|
| 1 | ESP32 S v1.1 DevKit | 1 | 31 pines, WiFi+BT | MCU principal |
| 2 | Zócalo con bornes a tornillo | 1 | 2×16 pines, paso 2.54mm | Montaje ESP32 |
| 3 | SCD30 | 1 | I2C, 3.3V, Sensirion | CO₂ / Temp / Humedad |
| 4 | BME280 | 0-1 | I2C, 3.3V, Bosch | Temp / Humedad / Presión |
| 5 | DS18B20 | 1-10 | 1-Wire, 3.3V, Dallas | Temperatura (cadena) |
| 6 | Resistor 4.7kΩ | 1 | 1/4W | Pull-up OneWire (obligatorio) |
| 7 | Sensor capacitivo v2.0 | 0-1 | ADC, 3.3V | Humedad de suelo |
| 8 | HD38 | 0-1 | ADC+Digital, LM393, 5V | Humedad de suelo |
| 9 | Resistor 10kΩ | 1* | 1/4W | Protección ADC (HD38) |
| 10 | Diodo Schottky BAT43 | 1* | Vf≈0.3V | Clamp ADC a 3.3V (HD38) |
| 11 | Módulo MAX485 | 0-1 | 3.3V-5V | Transceiver RS485 |
| 12 | TH-MB-04S | 0-1 | Modbus RTU, 5-30V | Sensor temp/hum remoto |
| 13 | Relay 2CH Modbus | 0-1 | Modbus RTU, 2×NO/NC | Actuador relay |
| 14 | Resistor 120Ω | 2* | 1/4W | Terminación bus RS485 |
| 15 | Fuente USB 5V | 1 | ≥1A recomendado | Alimentación |

*Componentes marcados con * son para protección/terminación recomendada.

---

## ⚡ Power Budget

| Componente | Consumo típico | Consumo pico | Notas |
|-----------|---------------|-------------|-------|
| ESP32 (WiFi activo) | ~80mA | ~240mA | TX WiFi peaks |
| SCD30 | 19mA | **75mA** | Pico durante medición |
| BME280 | 0.003mA | 3.6mA | Modo forced |
| DS18B20 (×1) | 1mA | 1.5mA | 12-bit conversion |
| Capacitivo | 5mA | 5mA | Continuo |
| HD38 + LM393 | 15mA | 15mA | Continuo |
| MAX485 | 0.5mA | 1mA | Half-duplex |
| **Total estimado** | **~120mA** | **~340mA** | |

> **Recomendación:** Fuente USB de 1A mínimo. El regulador 3.3V del DevKit típicamente soporta ~500mA, suficiente para esta configuración. Verificar si el pico del SCD30 (75mA) no causa brownout con WiFi TX simultáneo.

---

## ⚠️ Known Risks

### CRÍTICO: HD38 — Sobretensión en GPIO35

El sensor HD38 alimentado a **5V** puede enviar hasta 5V por su salida analógica (AOUT). El ESP32 tiene un **máximo absoluto de 3.6V** en sus pines ADC.

**Conexión sin protección PUEDE DAÑAR el ESP32.**

**Solución recomendada:**
```
                        3.3V
                          ↑
                    [Schottky BAT43]  ← clamp sobretensión
                          |
HD38 AOUT → [10kΩ serie] →●→ GPIO35
                          |
                    [Schottky BAT43]  ← clamp transitorios negativos
                          ↓
                         GND
```

**Alternativa:** Alimentar el HD38 a 3.3V (si el sensor funciona correctamente a ese voltaje).

### PRECAUCIÓN: Sensor Capacitivo

Algunos módulos capacitivos v1.x alimentados a 5V pueden dar AO hasta ~4.2V. **Alimentar a 3.3V** o verificar con multímetro que AO no supera 3.3V en condición seca.

### PRECAUCIÓN: Bus RS485

- **Terminación 120Ω** en ambos extremos del bus (obligatoria para cables >1m)
- **Masa común** entre ESP32, MAX485, sensor TH y relay (OBLIGATORIA)
- **Bias resistors 560Ω**: pull-up en A (→ 3.3V) y pull-down en B (→ GND) para idle definido — ver esquemático; obligatorio en tramos largos o con múltiples nodos

---

## 🔧 Troubleshooting

| Problema | Posible causa | Solución |
|---------|--------------|---------|
| SCD30/BME280 no detectado | Cableado I2C | Verificar SDA/SCL, 3.3V, GND |
| DS18B20 "0 sensors" | Pull-up faltante | Agregar 4.7kΩ entre GPIO4 y 3.3V |
| DS18B20 lee 85.0°C | Conversión incompleta | Aumentar delay, verificar cable |
| ADC siempre 0 o 4095 | Pin desconectado o saturado | Verificar conexión, voltaje <3.3V |
| ADC errático | Ruido | Agregar 0.1µF entre AOUT y GND |
| Modbus no responde | Polaridad RS485 | Swap A/B, verificar terminación |
| Modbus intermitente | Sin terminación/bias | Agregar 120Ω, verificar GND común |
| Brownout/reboot | Corriente insuficiente | Fuente ≥1A, verificar regulador |
| ESP32 se daña | HD38 5V→GPIO35 | Agregar protección (ver Known Risks) |

---

## 🔗 Referencias al Firmware

- **Definición de pines:** [`include/sensors/`](../include/sensors/) — cada sensor define su GPIO
- **Configuración:** [`docs/CONFIGURATION.md`](../docs/CONFIGURATION.md) — `config.json` con pines configurables
- **Sensores detallado:** [`docs/SENSORS.md`](../docs/SENSORS.md) — specs, implementación, troubleshooting

---

## 🔄 Regenerar Esquemáticos

```bash
cd HardWare
make setup        # Crear venv e instalar dependencias
make schematics   # Generar todos los SVG
make clean        # Eliminar SVG generados
```

Los esquemáticos se generan con [schemdraw](https://schemdraw.readthedocs.io/) (Python → SVG).
Editar `generate_schematics.py` para modificar los diagramas.
