# Proyecto Plantinera — Documentación de Hardware

Esquemáticos y guía de montaje para el sistema de monitoreo basado en **ESP32 DevKit V1** (ESP32-WROOM-32, `board=esp32dev`): 30 pines, 15 por lado, 2×GND.

> **Nota de variante de placa**: el pinout corresponde al **DevKit V1 / NodeMCU de 30 pines**. Si tu placa es la variante de 38 pines (NodeMCU-32S), el orden físico difiere — verificar contra la serigrafía. Las asignaciones GPIO↔función (I2C 21/22, OneWire 4, ADC 34/35, RS485 16/17/18) provienen del firmware y son las mismas en cualquier variante.

## 📌 Tabla de Pinout

| GPIO | Función | Periférico | Protocolo | Notas |
|------|---------|-----------|-----------|-------|
| 21 | SDA | SCD30 + BME280 | I2C | Bus compartido |
| 22 | SCL | SCD30 + BME280 | I2C | Bus compartido |
| 4 | Data | DS18B20 × N | 1-Wire | Pull-up 4.7kΩ obligatorio |
| 34 | ADC IN | Sensor capacitivo | ADC1_CH6 | Input-only, 3.3V max |
| 35 | ADC IN | HD38 (suelo) | ADC1_CH7 | ⚠ Requiere protección si VCC=5V |
| 17 | TX | C25B (DI) | UART2 | RS485 transmisión, 3.3V→5V OK |
| 16 | RX | C25B (RO) vía divisor | UART2 | ⚠ Divisor 1k/2k obligatorio (RO=5V) |
| 18 | DE/RE | C25B | GPIO | Half-duplex control, 3.3V→5V OK |

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

### RS485 Modbus (GPIO16/17/18) — módulo **C25B alimentado a 5V**
| Origen | Destino | Señal |
|--------|---------|-------|
| ESP32 5V (VIN) | C25B VCC | Alimentación módulo (MAX485 requiere 5V) |
| ESP32 GPIO17 | C25B DI | TX data (3.3V→MAX485 VIH≈2V, OK) |
| ESP32 GPIO18 | C25B DE+RE | Direction control (3.3V, OK) |
| C25B RO | **1kΩ serie** → GPIO16 | RX data (RO=5V, divisor obligatorio) |
| GPIO16 | **2kΩ** → GND | Pulldown divisor (5V → ~3.3V en el tap) |
| C25B A (D+) | Bus A | RS485 differential + |
| C25B B (D−) | Bus B | RS485 differential − |
| Bus A/B | TH-MB-04S | Sensor temp/hum (addr 1) |
| Bus A/B | Relay 2CH | Módulo relay (addr 2) |

> **⚠ Crítico:** el C25B es un MAX485 genuino sin level-shift onboard. Su pin RO entrega ~5V que **excede el máximo absoluto del ESP32 (3.6V)**. El divisor 1kΩ/2kΩ en RO→GPIO16 es **obligatorio** (5V × 2k/(1k+2k) = 3.33V). Sin el divisor, GPIO16 puede dañarse en el primer arranque.

### ADC Suelo (GPIO34/35)
| Origen | Destino | Señal |
|--------|---------|-------|
| Capacitivo AOUT | ESP32 GPIO34 | Analog (directo) |
| HD38 AOUT | 10kΩ → ESP32 GPIO35 | Analog (con protección) |

---

## 📐 Esquemáticos

### Diagrama General del Sistema
![Diagrama de bloques del sistema completo](schematics/sch_full_system.svg)

### Pinout ESP32 DevKit V1
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
| 1 | ESP32 DevKit V1 (WROOM-32) | 1 | 30 pines, WiFi+BT | MCU principal |
| 2 | Zócalo con bornes a tornillo | 1 | 2×16 pines, paso 2.54mm | Montaje ESP32 |
| 3 | SCD30 | 1 | I2C, 3.3V, Sensirion | CO₂ / Temp / Humedad |
| 4 | BME280 | 0-1 | I2C, 3.3V, Bosch | Temp / Humedad / Presión |
| 5 | DS18B20 | 1-10 | 1-Wire, 3.3V, Dallas | Temperatura (cadena) |
| 6 | Resistor 4.7kΩ | 1 | 1/4W | Pull-up OneWire (obligatorio) |
| 7 | Sensor capacitivo v2.0 | 0-1 | ADC, 3.3V | Humedad de suelo |
| 8 | HD38 | 0-1 | ADC+Digital, LM393, 5V | Humedad de suelo |
| 9 | Resistor 10kΩ | 1* | 1/4W | Protección ADC (HD38) |
| 10 | Diodo Schottky BAT43 | 2* | Vf≈0.3V | Clamp ADC (HD38) — a 3.3V y a GND |
| 11 | Módulo C25B (MAX485) | 0-1 | **5V** (azul básico) | Transceiver RS485 — RO requiere divisor |
| 12 | Resistor 1kΩ | 1** | 1/4W | **Divisor RO→GPIO16 (serie)** |
| 13 | Resistor 2kΩ | 1** | 1/4W | **Divisor RO→GPIO16 (pulldown a GND)** |
| 14 | TH-MB-04S | 0-1 | Modbus RTU, 5-30V | Sensor temp/hum remoto |
| 15 | Relay 2CH Modbus | 0-1 | Modbus RTU, 2×NO/NC | Actuador relay |
| 16 | Resistor 120Ω | 2* | 1/4W | Terminación bus RS485 (extremos) |
| 17 | Resistor 560Ω | 2* | 1/4W | Bias RS485 (1× a 3.3V en A, 1× a GND en B) |
| 18 | Fuente USB 5V | 1 | ≥1A recomendado | Alimentación |

*Componentes marcados con `*` son recomendados (protección/terminación/bias).
**Componentes marcados con `**` son **OBLIGATORIOS** si se usa el módulo C25B / MAX485 a 5V.

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
| C25B (MAX485) | 0.5mA | 1mA | Half-duplex — alimentado de **5V (VIN)**, no del rail 3.3V |
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

### CRÍTICO: C25B (MAX485) — Sobretensión en GPIO16

El módulo **C25B** es un MAX485 genuino: requiere alimentación a **5V** (no funciona confiable a 3.3V) y su salida **RO entrega ~5V**. El máximo absoluto de los pines del ESP32 es **3.6V**.

**Conectar RO directo a GPIO16 PUEDE DAÑAR el ESP32.**

**Solución obligatoria — divisor resistivo:**
```
C25B RO (5V) ─[1kΩ]─●─ GPIO16
                    │
                  [2kΩ]
                    │
                   GND
```
Tap = 5V × 2k/(1k+2k) = **3.33V** ✓ — dentro del rango seguro del ESP32. Los valores 1k/2k mantienen impedancia baja para el bit rate de 9600 baud sin degradar la señal. Las entradas DI/DE/RE del MAX485 aceptan los 3.3V del ESP32 sin level-shifter (VIH=2V).

**Alternativa:** usar un módulo con level-shift onboard (algunos C25B vienen con jumpers TERM/BIAS y traducción de nivel — verificar serigrafía) o un transceiver de 3.3V (MAX3485, SP3485).

### PRECAUCIÓN: Bus RS485

- **Terminación 120Ω** en ambos extremos del bus (obligatoria para cables >1m)
- **Masa común** entre ESP32, C25B, sensor TH y relay (OBLIGATORIA)
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
| C25B no transmite | VCC=3.3V (insuficiente) | Alimentar C25B a 5V (VIN), no a 3.3V |
| RX basura / sin datos | Falta divisor en RO | Agregar divisor 1k/2k entre RO y GPIO16 |
| Brownout/reboot | Corriente insuficiente | Fuente ≥1A, verificar regulador |
| ESP32 se daña | HD38 5V→GPIO35 | Agregar protección (ver Known Risks) |
| ESP32 se daña al conectar C25B | RO=5V directo a GPIO16 | Insertar divisor 1k/2k (obligatorio) |

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
