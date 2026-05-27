#!/usr/bin/env python3
"""Genera esquemáticos SVG del hardware del Proyecto Plantinera."""

import schemdraw
import schemdraw.elements as elm
from schemdraw import flow
import os

OUT = os.path.join(os.path.dirname(__file__), 'schematics')
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Bus I2C: SCD30 + BME280
# ---------------------------------------------------------------------------
def draw_i2c_sensors():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_i2c_sensors.svg'), show=False) as d:
        d.config(fontsize=11, unit=3)

        # ESP32 — solo pines SDA/SCL, sin símbolos de power dentro del IC
        esp = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='SDA21', side='right', slot='1/2'),
                elm.IcPin(name='SCL22', side='right', slot='2/2'),
            ],
            edgepadW=0.5, edgepadH=1.5,
            pinspacing=1.5, lsize=12,
        ).label('ESP32 S v1.1', loc='center', fontsize=11))

        # Alimentación ESP32 — a la izquierda del IC, sin superposición
        d.add(elm.Vdd().at((esp.SDA21[0] - 3.5, esp.SDA21[1])).label('3.3V'))
        d.add(elm.Ground().at((esp.SCL22[0] - 3.5, esp.SCL22[1])))

        # SCD30 — anclada en SSDA alineado con SDA21
        scd = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='SSDA', side='left',  slot='1/2'),
                elm.IcPin(name='SSCL', side='left',  slot='2/2'),
                elm.IcPin(name='SVCC', side='right', slot='1/2'),
                elm.IcPin(name='SGND', side='right', slot='2/2'),
            ],
            edgepadW=0.5, edgepadH=1.5,
            pinspacing=1.5, lsize=11,
        ).at((esp.SDA21[0] + 9, esp.SDA21[1])).anchor('SSDA')
         .label('SCD30\n(0x61) CO₂/T/H', loc='center', fontsize=9))

        d.add(elm.Vdd().at(scd.SVCC).label('3.3V'))
        d.add(elm.Ground().at(scd.SGND))

        # Conexiones SDA y SCL horizontales
        d.add(elm.Line().at(esp.SDA21).to(scd.SSDA).color('blue')
              .label('SDA (GPIO21)', loc='top', fontsize=8))
        d.add(elm.Line().at(esp.SCL22).to(scd.SSCL).color('green')
              .label('SCL (GPIO22)', loc='bottom', fontsize=8))

        # Pull-ups en zona libre ENCIMA del bus, a la derecha del bus
        # — separadas horizontalmente para no cruzar entre sí
        pu_sda_x = esp.SDA21[0] + 3.5   # alineado con SDA (línea baja)
        pu_scl_x = esp.SDA21[0] + 6.0   # separado 2.5 unidades a la derecha

        d.add(elm.Dot().at((pu_sda_x, esp.SDA21[1])))
        d.add(elm.Resistor().at((pu_sda_x, esp.SDA21[1])).up(2.5)
              .label('4.7kΩ', loc='right', fontsize=8))
        d.add(elm.Vdd().label('3.3V'))

        d.add(elm.Dot().at((pu_scl_x, esp.SCL22[1])))
        d.add(elm.Resistor().at((pu_scl_x, esp.SCL22[1])).up(2.5)
              .label('4.7kΩ', loc='right', fontsize=8))
        d.add(elm.Vdd().label('3.3V'))

        # BME280 — debajo y alineada con SCD30
        bme_x = scd.SSDA[0]
        bme_y = esp.SDA21[1] - 6

        bme = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='BSDA', side='left',  slot='1/2'),
                elm.IcPin(name='BSCL', side='left',  slot='2/2'),
                elm.IcPin(name='BVCC', side='right', slot='1/2'),
                elm.IcPin(name='BGND', side='right', slot='2/2'),
            ],
            edgepadW=0.5, edgepadH=1.5,
            pinspacing=1.5, lsize=11,
        ).at((bme_x, bme_y)).anchor('BSDA')
         .label('BME280\n(0x76) T/H/P', loc='center', fontsize=9))

        d.add(elm.Vdd().at(bme.BVCC).label('3.3V'))
        d.add(elm.Ground().at(bme.BGND))

        # Derivar SDA al BME280: bajar desde pu_sda_x (por donde pasa el bus SDA)
        d.add(elm.Dot().at((pu_sda_x, esp.SDA21[1])))
        d.add(elm.Line().at((pu_sda_x, esp.SDA21[1])).down().toy(bme.BSDA[1]).color('blue'))
        d.add(elm.Line().right().tox(bme.BSDA[0]).color('blue'))

        # Derivar SCL al BME280 desde pu_scl_x
        d.add(elm.Dot().at((pu_scl_x, esp.SCL22[1])))
        d.add(elm.Line().at((pu_scl_x, esp.SCL22[1])).down().toy(bme.BSCL[1]).color('green'))
        d.add(elm.Line().right().tox(bme.BSCL[0]).color('green'))

        d.add(elm.Label().at(((esp.SDA21[0] + bme_x) / 2, bme_y - 3.5))
              .label('Bus I2C compartido — Pull-ups 4.7kΩ externos\n'
                     'SCD30: pico 75mA — verificar regulador 3V3',
                     fontsize=9, color='gray'))

    print('  ✓ sch_i2c_sensors.svg')


# ---------------------------------------------------------------------------
# 2. Bus OneWire: DS18B20 × 3
# ---------------------------------------------------------------------------
def draw_onewire():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_onewire.svg'), show=False) as d:
        d.config(fontsize=11, unit=3)

        bus_len = 12

        # Etiqueta GPIO al inicio
        d.add(elm.Dot(open=True).at((0, 0)))
        d.add(elm.Label().at((-0.2, 0)).label('GPIO4', loc='left', fontsize=10))

        # Bus horizontal
        d.add(elm.Line().right(bus_len).at((0, 0)))
        d.add(elm.Dot(open=True).at((bus_len, 0)))
        d.add(elm.Label().at((bus_len + 0.2, 0)).label('(continúa)', loc='right', fontsize=8))

        # Pull-up 4.7kΩ
        pu_x = 1.8
        d.add(elm.Dot().at((pu_x, 0)))
        d.add(elm.Resistor().at((pu_x, 0)).up().label('4.7kΩ', loc='right', fontsize=10))
        d.add(elm.Vdd().label('3.3V'))

        # DS18B20 sensores — colgando debajo. DQ arriba, VDD/GND abajo
        drop = 2.5
        sensor_xs = [4.0, 7.5, 11.0]

        for i, xpos in enumerate(sensor_xs):
            d.add(elm.Dot().at((xpos, 0)))
            d.add(elm.Line().at((xpos, 0)).down(drop))

            ds = d.add(elm.Ic(
                pins=[
                    elm.IcPin(name=f'DQ{i}',  side='top',    slot='1/1'),
                    elm.IcPin(name=f'VDD{i}', side='bottom', slot='1/2'),
                    elm.IcPin(name=f'GND{i}', side='bottom', slot='2/2'),
                ],
                edgepadW=0.5, edgepadH=0.6,
                pinspacing=1.0, lsize=9,
            ).anchor(f'DQ{i}')
             .label(f'DS18B20\n#{i + 1}', loc='center', fontsize=8))

            # VDD: línea corta hacia abajo + etiqueta 3.3V (Vdd apuntaría hacia el IC)
            vdd_pin = getattr(ds, f'VDD{i}')
            d.add(elm.Line().at(vdd_pin).down(0.7))
            d.add(elm.Label().label('3.3V', loc='bottom', fontsize=7))
            d.add(elm.Ground().at(getattr(ds, f'GND{i}')))

        d.add(elm.Label().at((7, -drop - 4.2))
              .label('Pull-up 4.7kΩ OBLIGATORIO  •  Resolución 12-bit (750ms)\n'
                     'Máx ~10 sensores  •  Cable máx 3m  •  Cap 0.1µF VDD↔GND c/sensor',
                     fontsize=9, color='gray'))

    print('  ✓ sch_onewire.svg')


# ---------------------------------------------------------------------------
# 3. Sensores ADC: Capacitivo + HD38 con protección
# ---------------------------------------------------------------------------
def draw_adc_soil():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_adc_soil.svg'), show=False) as d:
        d.config(fontsize=11, unit=3)

        # --- HD38 con protección ---
        y0 = 0
        d.add(elm.Label().at((4.5, y0 + 3.5))
              .label('HD38 — CONEXION RECOMENDADA (con proteccion ADC)',
                     fontsize=11, color='green'))

        d.add(elm.Dot(open=True).at((0, y0)))
        d.add(elm.Label().at((0, y0)).label('HD38\nAOUT (0-5V)', loc='left', fontsize=9))

        r1 = d.add(elm.Resistor().right().at((0, y0)).label('10kΩ', loc='top', fontsize=9))
        jct = r1.end
        d.add(elm.Dot().at(jct))

        # Schottky a 3.3V
        d.add(elm.Diode().at(jct).up(2.2).label('BAT43', loc='right', fontsize=8))
        d.add(elm.Vdd().label('3.3V'))

        # Schottky a GND
        d.add(elm.Diode().at(jct).down(2.2).reverse().label('BAT43', loc='right', fontsize=8))
        d.add(elm.Ground())

        d.add(elm.Line().at(jct).right(3.5))
        d.add(elm.Dot(open=True))
        d.add(elm.Label().label('ESP32\nGPIO35', loc='right', fontsize=9))

        # --- Conexión directa (no recomendada) ---
        y1 = y0 - 7.5
        d.add(elm.Label().at((4.5, y1 + 1.2))
              .label('HD38 — CONEXION DIRECTA (no recomendada)',
                     fontsize=10, color='red'))

        d.add(elm.Dot(open=True).at((0, y1)))
        d.add(elm.Label().at((0, y1)).label('HD38\nAOUT (0-5V)', loc='left', fontsize=9))
        d.add(elm.Line().right(6).at((0, y1)).color('red').linestyle('--'))
        d.add(elm.Dot(open=True))
        d.add(elm.Label().label('ESP32\nGPIO35', loc='right', fontsize=9))

        # --- Capacitivo ---
        y2 = y1 - 5
        d.add(elm.Label().at((4.5, y2 + 1.2))
              .label('Sensor Capacitivo — conexion directa OK si VCC=3.3V',
                     fontsize=10, color='green'))

        d.add(elm.Dot(open=True).at((0, y2)))
        d.add(elm.Label().at((0, y2)).label('Capacitivo\nAOUT', loc='left', fontsize=9))
        d.add(elm.Line().right(6).at((0, y2)).color('green'))
        d.add(elm.Dot(open=True))
        d.add(elm.Label().label('ESP32\nGPIO34', loc='right', fontsize=9))

        # --- Notas ---
        y3 = y2 - 3.8
        d.add(elm.Label().at((4.5, y3))
              .label('ESP32 ADC max absoluto: 3.6V — HD38 a 5V puede enviar hasta 5V\n'
                     'GPIO34/35 son ADC1 (correcto con WiFi). NO usar ADC2 con WiFi\n'
                     'Atenuacion ADC 11dB -> rango lineal util: ~0.15-2.5V',
                     fontsize=9, color='darkred'))

    print('  ✓ sch_adc_soil.svg')


# ---------------------------------------------------------------------------
# 4. Bus RS485: MAX485 + Sensor TH + Relay 2CH
# ---------------------------------------------------------------------------
def draw_rs485():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_rs485_modbus.svg'), show=False) as d:
        d.config(fontsize=10, unit=3)

        # === ESP32 — pines de señal a la derecha, GND propio abajo ===
        esp = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='TX17', side='right',  slot='1/3'),
                elm.IcPin(name='RX16', side='right',  slot='2/3'),
                elm.IcPin(name='DERE', side='right',  slot='3/3'),
                elm.IcPin(name='EGND', side='bottom', slot='1/1'),
            ],
            edgepadW=1.5, edgepadH=1.5,
            pinspacing=1.5, lsize=11,
        ).label('ESP32', loc='center', fontsize=12))

        # GND del ESP32 (masa común con el resto del bus)
        d.add(elm.Ground().at(esp.EGND))

        tx_pos = esp.TX17
        rx_pos = esp.RX16
        de_pos = esp.DERE

        # === MAX485 — misma pinspacing → conexiones horizontales ===
        gap = 5
        max485 = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='DI',   side='left',  slot='1/3'),
                elm.IcPin(name='RO',   side='left',  slot='2/3'),
                elm.IcPin(name='DE',   side='left',  slot='3/3'),
                elm.IcPin(name='MVCC', side='top',    slot='1/1'),
                elm.IcPin(name='MGND', side='bottom', slot='1/1'),
                elm.IcPin(name='DA',   side='right',  slot='1/2'),
                elm.IcPin(name='DB',   side='right',  slot='2/2'),
            ],
            edgepadW=0.5, edgepadH=1.2,
            pinspacing=1.5, lsize=10,
        ).at((tx_pos[0] + gap, tx_pos[1])).anchor('DI')
         .label('MAX485', loc='center', fontsize=11))

        d.add(elm.Vdd().at(max485.MVCC).label('3.3V'))
        d.add(elm.Ground().at(max485.MGND))

        # === Conexiones ESP32 → MAX485 (horizontales) ===
        d.add(elm.Line().at(tx_pos).to(max485.DI)
              .color('orange').label('TX GPIO17', loc='top', fontsize=7))
        d.add(elm.Line().at(rx_pos).to(max485.RO)
              .color('cyan').label('RX GPIO16', loc='top', fontsize=7))
        d.add(elm.Line().at(de_pos).to(max485.DE)
              .color('purple').label('DE/RE GPIO18', loc='bottom', fontsize=7))

        # === Bus A (verde) y B (azul) ===
        bus_len = 13
        bus_x0  = max485.DA[0]
        bus_a_y = max485.DA[1]
        bus_b_y = max485.DB[1]

        d.add(elm.Line().at(max485.DA).right(bus_len).color('green'))
        d.add(elm.Line().at(max485.DB).right(bus_len).color('blue'))

        # Labels A/B — a la izquierda del primer nodo, sin superposición
        d.add(elm.Label().at((bus_x0 + 0.5, bus_a_y + 0.6))
              .label('A (D+)', fontsize=8, color='darkgreen'))
        d.add(elm.Label().at((bus_x0 + 0.5, bus_b_y - 0.6))
              .label('B (D−)', fontsize=8, color='navy'))

        # === Bias resistors — A pull-up a 3.3V, B pull-down a GND ===
        # Separadas en x para que cada una cruce una sola línea (sin dot = sin conexión)
        bias_a_x = bus_x0 + 2.2
        bias_b_x = bus_x0 + 3.6

        # Bias A: pull-up desde la línea A (verde) hacia 3.3V
        d.add(elm.Dot().at((bias_a_x, bus_a_y)))
        d.add(elm.Resistor().at((bias_a_x, bus_a_y)).up(2.8)
              .label('560Ω\nbias A', loc='left', fontsize=7))
        d.add(elm.Vdd().label('3.3V', fontsize=7))

        # Bias B: pull-down desde la línea B (azul) hacia GND
        d.add(elm.Dot().at((bias_b_x, bus_b_y)))
        d.add(elm.Resistor().at((bias_b_x, bus_b_y)).down(2.8)
              .label('560Ω\nbias B', loc='right', fontsize=7))
        d.add(elm.Ground())

        # === TH-MB-04S — pines arriba, IC cuelga hacia abajo ===
        th_x  = bus_x0 + 6.0
        drop  = 2.8

        d.add(elm.Dot().at((th_x, bus_a_y)))
        d.add(elm.Dot().at((th_x, bus_b_y)))

        th = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='TA',   side='top',    slot='1/2'),
                elm.IcPin(name='TB',   side='top',    slot='2/2'),
                elm.IcPin(name='TPWR', side='bottom', slot='1/2'),
                elm.IcPin(name='TGND', side='bottom', slot='2/2'),
            ],
            edgepadW=0.6, edgepadH=0.5,
            pinspacing=1.2, lsize=8,
        ).at((th_x, bus_b_y - drop)).anchor('TA')
         .label('TH-MB-04S\nAddr:1 (T/H)', loc='center', fontsize=7))

        d.add(elm.Line().at((th_x, bus_a_y)).down().toy(th.TA[1]).color('green'))
        d.add(elm.Line().at((th_x, bus_b_y)).down().toy(th.TB[1]).color('blue'))
        d.add(elm.Line().at(th.TPWR).down(0.7))
        d.add(elm.Label().label('5-30V', loc='bottom', fontsize=6))
        d.add(elm.Ground().at(th.TGND))

        # === Relay 2CH ===
        rl_x  = bus_x0 + 10.0

        d.add(elm.Dot().at((rl_x, bus_a_y)))
        d.add(elm.Dot().at((rl_x, bus_b_y)))

        rl = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='RA',   side='top',    slot='1/2'),
                elm.IcPin(name='RB',   side='top',    slot='2/2'),
                elm.IcPin(name='RPWR', side='bottom', slot='1/2'),
                elm.IcPin(name='RGND', side='bottom', slot='2/2'),
            ],
            edgepadW=0.6, edgepadH=0.5,
            pinspacing=1.2, lsize=8,
        ).at((rl_x, bus_b_y - drop)).anchor('RA')
         .label('Relay 2CH\nAddr:2', loc='center', fontsize=7))

        d.add(elm.Line().at((rl_x, bus_a_y)).down().toy(rl.RA[1]).color('green'))
        d.add(elm.Line().at((rl_x, bus_b_y)).down().toy(rl.RB[1]).color('blue'))
        d.add(elm.Line().at(rl.RPWR).down(0.7))
        d.add(elm.Label().label('5-30V', loc='bottom', fontsize=6))
        d.add(elm.Ground().at(rl.RGND))

        # === Terminación 120Ω ===
        term_x = bus_x0 + bus_len
        d.add(elm.Resistor().at((term_x, bus_a_y)).down().toy(bus_b_y)
              .label('120Ω\nterm', loc='right', fontsize=8))

        # Nota — debajo de los grounds de TH/Relay
        note_y = bus_b_y - drop - 5.5
        note_x = bus_x0 + bus_len / 2
        d.add(elm.Label().at((note_x, note_y))
              .label('RS485 Modbus RTU — Half-duplex (DE/RE=GPIO18)\n'
                     'Terminacion 120Ω en extremos del bus  •  Masa comun OBLIGATORIA\n'
                     '9600 baud 8N1  •  Bias 560Ω en A/B  •  Cable max 1200m',
                     fontsize=9, color='gray'))

    print('  ✓ sch_rs485_modbus.svg')


# ---------------------------------------------------------------------------
# 5. Diagrama de bloques del sistema
# ---------------------------------------------------------------------------
def draw_full_system():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_full_system.svg'), show=False) as d:
        d.config(fontsize=11, unit=3)

        esp_w, esp_h = 5.5, 7.5
        esp_cx, esp_cy = 0, 0

        esp_box = d.add(flow.Box(w=esp_w, h=esp_h).at((esp_cx, esp_cy)).label(
            'ESP32 S v1.1\n32 pines\n\nWiFi / ESP-NOW\nWeb Server\nGrafana / InfluxDB'))

        # Anchors del ESP32
        esp_left_x  = esp_box.W[0]
        esp_right_x = esp_box.E[0]
        esp_top_y   = esp_box.N[1]
        esp_bot_y   = esp_box.S[1]

        # --- I2C (izquierda, arriba) ---
        i2c_box = d.add(flow.Box(w=4.5, h=2.8).at((esp_left_x - 6, esp_cy + 1.8))
                        .label('I2C Bus\nSCD30 (CO2)\nBME280 (T/H/P)'))
        # Conectar borde derecho de I2C al borde izquierdo de ESP32
        d.add(elm.Line().at(i2c_box.E).right().tox(esp_left_x).color('blue'))
        d.add(elm.Label().at(((i2c_box.E[0] + esp_left_x) / 2, i2c_box.E[1] + 0.4))
              .label('SDA=21 SCL=22', fontsize=8, color='blue'))

        # --- 1-Wire (izquierda, abajo) ---
        ow_box = d.add(flow.Box(w=4.5, h=2.2).at((esp_left_x - 6, esp_cy - 1.8))
                       .label('1-Wire\nDS18B20 x N'))
        d.add(elm.Line().at(ow_box.E).right().tox(esp_left_x).color('purple'))
        d.add(elm.Label().at(((ow_box.E[0] + esp_left_x) / 2, ow_box.E[1] + 0.4))
              .label('GPIO4 + 4.7kOhm', fontsize=8, color='purple'))

        # --- RS485 (derecha) ---
        rs_box = d.add(flow.Box(w=4.5, h=3.0).at((esp_right_x + 6, esp_cy))
                       .label('RS485 Modbus\nMAX485\nSensor TH\nRelay 2CH'))
        d.add(elm.Line().at(rs_box.W).left().tox(esp_right_x).color('orange'))
        d.add(elm.Label().at(((rs_box.W[0] + esp_right_x) / 2, rs_box.W[1] + 0.4))
              .label('TX=17 RX=16 DE/RE=18', fontsize=8, color='orange'))

        # --- Grafana / Cloud (arriba) ---
        cl_box = d.add(flow.Box(w=4.0, h=2.0).at((esp_cx, esp_top_y + 3.5))
                       .label('Grafana / InfluxDB'))
        d.add(elm.Line().at(cl_box.S).down().toy(esp_top_y).color('gray'))
        d.add(elm.Label().at((cl_box.S[0] + 1.2, (cl_box.S[1] + esp_top_y) / 2))
              .label('WiFi / ESP-NOW', fontsize=8, color='gray'))

        # --- ADC Suelo (abajo) ---
        adc_box = d.add(flow.Box(w=5.0, h=2.5).at((esp_cx, esp_bot_y - 4))
                        .label('ADC Suelo\nCapacitivo (GPIO34)\nHD38 (GPIO35)  !!'))
        d.add(elm.Line().at(adc_box.N).up().toy(esp_bot_y).color('green'))
        d.add(elm.Label().at((adc_box.N[0] + 1.2, (adc_box.N[1] + esp_bot_y) / 2))
              .label('!! Prot. GPIO35', fontsize=8, color='red'))

        # --- Alimentación (debajo-izquierda) ---
        pw_box = d.add(flow.Box(w=3.5, h=1.8).at((esp_left_x - 6, esp_bot_y - 3))
                       .label('5V USB\n-> 3.3V reg').color('red'))
        # Línea vertical hasta el borde izquierdo del ESP32
        d.add(elm.Line().at(pw_box.E).right().tox(esp_left_x).color('red'))
        d.add(elm.Line().at((esp_left_x, pw_box.E[1])).up().toy(esp_bot_y).color('red'))

        # --- GPIO Relays TBD ---
        d.add(flow.Box(w=4.0, h=1.8).at((esp_right_x + 6, esp_bot_y - 2.5))
              .label('GPIO Relays\n(proxim.)').color('lightgray'))

    print('  ✓ sch_full_system.svg')


# ---------------------------------------------------------------------------
# 6. Pinout ESP32 S v1.1
# ---------------------------------------------------------------------------
def draw_esp32_pinout():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_esp32_pinout.svg'), show=False) as d:
        d.config(fontsize=9, unit=3)

        pins_left = [
            ('3V3',    '3.3V Power',     'red'),
            ('EN',     'Reset/Enable',   'gray'),
            ('GPIO36', 'ADC1_CH0 (VP)',  'gray'),
            ('GPIO39', 'ADC1_CH3 (VN)', 'gray'),
            ('GPIO34', 'Capacitivo IN',  'blue'),
            ('GPIO35', 'HD38 IN  !!',    'red'),
            ('GPIO32', '—',              'gray'),
            ('GPIO33', '—',              'gray'),
            ('GPIO25', '—',              'gray'),
            ('GPIO26', '—',              'gray'),
            ('GPIO27', '—',              'gray'),
            ('GPIO14', '—',              'gray'),
            ('GPIO12', '—',              'gray'),
            ('GND1',   'GND',            'black'),
            ('GPIO13', '—',              'gray'),
            ('VIN',    '5V Input',       'red'),
        ]
        pins_right = [
            ('GPIO23', '—',              'gray'),
            ('GPIO22', 'SCL (I2C)',      'blue'),
            ('TX0',    'Serial TX0',     'gray'),
            ('RX0',    'Serial RX0',     'gray'),
            ('GPIO21', 'SDA (I2C)',      'blue'),
            ('GND2',   'GND',            'black'),
            ('GPIO19', '—',              'gray'),
            ('GPIO18', 'DE/RE RS485',    'orange'),
            ('GPIO5',  '—',              'gray'),
            ('GPIO17', 'RS485 TX',       'orange'),
            ('GPIO16', 'RS485 RX',       'orange'),
            ('GPIO4',  '1-Wire',         'purple'),
            ('GPIO0',  'Boot button',    'gray'),
            ('GPIO2',  'LED interno',    'gray'),
            ('GPIO15', '—',              'gray'),
            ('GND3',   'GND',            'black'),
        ]

        ic_pins = []
        for i, (name, _, _) in enumerate(pins_left):
            ic_pins.append(elm.IcPin(name=name, side='left',
                                     slot=f'{i + 1}/{len(pins_left)}'))
        for i, (name, _, _) in enumerate(pins_right):
            ic_pins.append(elm.IcPin(name=name, side='right',
                                     slot=f'{i + 1}/{len(pins_right)}'))

        esp = d.add(elm.Ic(
            pins=ic_pins,
            edgepadW=1.2, edgepadH=0.3,
            pinspacing=0.9, lsize=12,
        ).label('ESP32\nS v1.1', loc='center', fontsize=11))

        for name, func, color in pins_left:
            pin_pos = getattr(esp, name)
            d.add(elm.Label().at((pin_pos[0] - 4.2, pin_pos[1]))
                  .label(func, fontsize=7, color=color))

        for name, func, color in pins_right:
            pin_pos = getattr(esp, name)
            d.add(elm.Label().at((pin_pos[0] + 4.2, pin_pos[1]))
                  .label(func, fontsize=7, color=color))

        # Leyenda — debajo del pin más bajo (3V3 / GPIO23, slot inferior)
        legend_y = getattr(esp, '3V3')[1] - 2.5
        d.add(elm.Label().at((esp.center[0], legend_y))
              .label('Azul: I2C (GPIO21/22)  Naranja: RS485 (GPIO16/17/18)  Violeta: 1-Wire (GPIO4)\n'
                     'Rojo: GPIO35 requiere proteccion (HD38 5V -> Schottky clamp a 3.3V y GND)\n'
                     'ADC1 (GPIO32-39) funciona con WiFi  •  NO usar ADC2 con WiFi activo',
                     fontsize=8, color='gray'))

    print('  ✓ sch_esp32_pinout.svg')


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print('Generando esquemáticos...')
    draw_esp32_pinout()
    draw_i2c_sensors()
    draw_onewire()
    draw_adc_soil()
    draw_rs485()
    draw_full_system()
    print(f'\n✅ Todos los esquemáticos generados en {OUT}/')
