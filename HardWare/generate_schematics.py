#!/usr/bin/env python3
"""Genera esquemáticos SVG del hardware del Proyecto Plantinera."""

import schemdraw
import schemdraw.elements as elm
from schemdraw import flow
import os

OUT = os.path.join(os.path.dirname(__file__), 'schematics')
os.makedirs(OUT, exist_ok=True)

# --- Configuración visual ---
schemdraw.theme('default')
GLOBAL_CONFIG = {'fontsize': 11, 'unit': 3.2, 'lw': 1.6, 'font': 'sans-serif'}

# Paleta — un color por señal lógica (consistente en los 6 esquemas)
TITLE_COLOR = '#111827'  # gris casi negro
NOTE_COLOR  = '#6b7280'  # gris medio para notas al pie
C_I2C_SDA   = '#2563eb'  # azul     — SDA
C_I2C_SCL   = '#16a34a'  # verde    — SCL
C_ONEWIRE   = '#9333ea'  # violeta  — 1-Wire
C_ADC       = '#0d9488'  # teal     — señales ADC
C_RS485_TX  = '#ea580c'  # naranja  — TX/DI
C_RS485_RX  = '#0284c7'  # celeste  — RX/RO
C_RS485_DE  = '#7c3aed'  # violeta  — DE/RE
C_BUS_A     = '#15803d'  # verde    — A+ (D+)
C_BUS_B     = '#1e40af'  # azul     — B- (D-)
C_GPIO      = '#92400e'  # marrón   — salidas GPIO (relays)
C_VCC       = '#dc2626'  # rojo     — alimentación
C_GND       = '#172554'  # azul osc — masa
C_WARN      = '#b91c1c'  # rojo osc — advertencias


def add_title(d, text, pad=1.4):
    """Título centrado por encima del bounding box real del dibujo, con una
    línea separadora tenue al estilo de hoja de datos.

    Se llama al FINAL de cada función (con todos los elementos ya añadidos)
    para que la posición sea exacta y nunca se solape con el esquema.
    """
    bb = d.get_bbox()
    cx = (bb.xmin + bb.xmax) / 2
    rule_y = bb.ymax + pad * 0.55
    d.add(elm.Line().at((bb.xmin, rule_y)).to((bb.xmax, rule_y))
          .color('#d1d5db').linewidth(1.0))
    d.add(elm.Label().at((cx, rule_y + 0.3)).label(text, fontsize=15,
          color=TITLE_COLOR, halign='center', valign='bottom'))


def add_footer(d, text, pad=1.2):
    """Nota al pie centrada por debajo del bounding box real del dibujo."""
    bb = d.get_bbox()
    cx = (bb.xmin + bb.xmax) / 2
    y = bb.ymin - pad
    d.add(elm.Label().at((cx, y)).label(text, fontsize=9, color=NOTE_COLOR,
                                        halign='center', valign='top'))



# ---------------------------------------------------------------------------
# 1. Bus I2C: SCD30 + BME280
# ---------------------------------------------------------------------------
def draw_i2c_sensors():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_i2c_sensors.svg'), show=False) as d:
        d.config(**GLOBAL_CONFIG)

        # ESP32 — solo pines SDA/SCL, sin símbolos de power dentro del IC
        esp = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='SDA21', side='right', slot='1/2'),
                elm.IcPin(name='SCL22', side='right', slot='2/2'),
            ],
            edgepadW=0.5, edgepadH=1.5,
            pinspacing=1.5, lsize=12,
        ).label('ESP32', loc='center', fontsize=12))

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
        d.add(elm.Line().at(esp.SDA21).to(scd.SSDA).color(C_I2C_SDA)
              .label('SDA (GPIO21)', loc='top', fontsize=8))
        d.add(elm.Line().at(esp.SCL22).to(scd.SSCL).color(C_I2C_SCL)
              .label('SCL (GPIO22)', loc='bottom', fontsize=8))

        # Coordenadas de derivación al BME280 (junctions sobre los buses)
        pu_sda_x = esp.SDA21[0] + 3.5   # punto de derivación en línea SDA
        pu_scl_x = esp.SDA21[0] + 6.0   # punto de derivación en línea SCL

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
        d.add(elm.Line().at((pu_sda_x, esp.SDA21[1])).down().toy(bme.BSDA[1]).color(C_I2C_SDA))
        d.add(elm.Line().right().tox(bme.BSDA[0]).color(C_I2C_SDA))

        # Derivar SCL al BME280 desde pu_scl_x
        d.add(elm.Dot().at((pu_scl_x, esp.SCL22[1])))
        d.add(elm.Line().at((pu_scl_x, esp.SCL22[1])).down().toy(bme.BSCL[1]).color(C_I2C_SCL))
        d.add(elm.Line().right().tox(bme.BSCL[0]).color(C_I2C_SCL))

        add_footer(d, 'Bus I2C compartido (GPIO21/22)  •  SCD30: pico 75mA — verificar regulador 3V3')
        add_title(d, 'Bus I2C — SCD30 + BME280')

    print('  ✓ sch_i2c_sensors.svg')


# ---------------------------------------------------------------------------
# 2. Bus OneWire: DS18B20 × 3
# ---------------------------------------------------------------------------
def draw_onewire():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_onewire.svg'), show=False) as d:
        d.config(**GLOBAL_CONFIG)

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

        # DS18B20 — cada sensor como caja con DQ arriba (al bus) y VDD/GND
        # cableados manualmente a rails comunes abajo. Visualmente claro.
        drop = 2.5
        sensor_xs = [4.0, 7.5, 11.0]
        box_w = 1.8
        box_h = 1.8

        # Coordenadas de los rails
        rail_v_y = -drop - box_h - 1.2   # rail 3.3V
        rail_g_y = rail_v_y - 1.5        # rail GND

        for i, xpos in enumerate(sensor_xs):
            # Bajada del bus a DQ del sensor
            d.add(elm.Dot().at((xpos, 0)))
            d.add(elm.Line().at((xpos, 0)).down(drop))

            # Caja del DS18B20 con DQ en el medio del borde superior
            box_top_y = -drop
            box_left  = xpos - box_w / 2
            box_right = xpos + box_w / 2
            box_bot   = box_top_y - box_h

            d.add(elm.Line().at((box_left, box_top_y)).to((box_right, box_top_y)))
            d.add(elm.Line().at((box_right, box_top_y)).to((box_right, box_bot)))
            d.add(elm.Line().at((box_right, box_bot)).to((box_left, box_bot)))
            d.add(elm.Line().at((box_left, box_bot)).to((box_left, box_top_y)))
            d.add(elm.Label().at((xpos, box_top_y - box_h / 2))
                  .label(f'DS18B20\n#{i + 1}', fontsize=8))

            # VDD: línea desde la esquina inferior-izquierda al rail 3.3V
            vdd_x = box_left + 0.4
            d.add(elm.Line().at((vdd_x, box_bot)).down().toy(rail_v_y).color(C_VCC))
            d.add(elm.Dot().at((vdd_x, rail_v_y)))
            d.add(elm.Label().at((vdd_x - 0.55, box_bot - 0.55))
                  .label('VDD', fontsize=7, color=C_VCC))

            # GND: línea desde la esquina inferior-derecha al rail GND
            gnd_x = box_right - 0.4
            d.add(elm.Line().at((gnd_x, box_bot)).down().toy(rail_g_y).color(C_GND))
            d.add(elm.Dot().at((gnd_x, rail_g_y)))
            d.add(elm.Label().at((gnd_x + 0.55, box_bot - 0.55))
                  .label('GND', fontsize=7, color=C_GND))

        # Rails horizontales (3.3V rojo, GND azul oscuro)
        # rail_right con holgura para que los símbolos de power no toquen
        # la etiqueta GND del último sensor
        rail_left  = sensor_xs[0] - 1.2
        rail_right = sensor_xs[-1] + 2.8
        d.add(elm.Line().at((rail_left, rail_v_y)).to((rail_right, rail_v_y)).color(C_VCC))
        d.add(elm.Line().at((rail_left, rail_g_y)).to((rail_right, rail_g_y)).color(C_GND))

        # Símbolos de power al extremo derecho del rail
        d.add(elm.Vdd().at((rail_right, rail_v_y)).label('3.3V', fontsize=8))
        d.add(elm.Ground().at((rail_right, rail_g_y)))

        add_footer(d, 'Pull-up 4.7kΩ OBLIGATORIO (sin él OneWire no funciona)  •  '
                      'Resolución 12-bit (750ms)  •  Máx ~10 sensores  •  Cable máx 3m')
        add_title(d, 'Bus 1-Wire — DS18B20 (×N)')

    print('  ✓ sch_onewire.svg')


# ---------------------------------------------------------------------------
# 3. Sensores ADC: Capacitivo + HD38 con protección
# ---------------------------------------------------------------------------
def draw_adc_soil():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_adc_soil.svg'), show=False) as d:
        d.config(**GLOBAL_CONFIG)

        # === ESP32 (solo pines ADC relevantes) ===
        # pinspacing 5.5: separa los 2 sensores sin que sus power rails colisionen,
        # manteniendo la caja compacta.
        esp = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='GPIO35', side='right', slot='2/2'),  # arriba
                elm.IcPin(name='GPIO34', side='right', slot='1/2'),  # abajo
            ],
            edgepadW=1.2, edgepadH=1.0,
            pinspacing=5.5, lsize=11,
        ).label('ESP32', loc='center', fontsize=12))

        # === HD38 (sensor 5V) — alineado con GPIO35 (línea arriba) ===
        # edgepadW amplio para que el label central no se solape con los pines
        hd_gap = 7.0
        hd = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='HVCC',  side='top',    slot='1/1'),
                elm.IcPin(name='HAOUT', side='left',   slot='1/1'),
                elm.IcPin(name='HGND',  side='bottom', slot='1/1'),
            ],
            edgepadW=1.5, edgepadH=1.0,
            pinspacing=1.5, lsize=9,
        ).at((esp.GPIO35[0] + hd_gap, esp.GPIO35[1])).anchor('HAOUT')
         .label('HD38\n(suelo)', loc='center', fontsize=9))

        # === Capacitivo (sensor 3.3V) — alineado con GPIO34 (línea abajo) ===
        cap = d.add(elm.Ic(
            pins=[
                elm.IcPin(name='CVCC',  side='top',    slot='1/1'),
                elm.IcPin(name='CAOUT', side='left',   slot='1/1'),
                elm.IcPin(name='CGND',  side='bottom', slot='1/1'),
            ],
            edgepadW=1.5, edgepadH=1.0,
            pinspacing=1.5, lsize=9,
        ).at((esp.GPIO34[0] + hd_gap, esp.GPIO34[1])).anchor('CAOUT')
         .label('Capacitivo\n(suelo)', loc='center', fontsize=9))

        # === Conexiones AOUT (color por nivel: rojo=riesgo 5V, teal=seguro) ===
        d.add(elm.Line().at(esp.GPIO35).to(hd.HAOUT).color(C_WARN)
              .label('AOUT (0-5V)', loc='top', fontsize=7))
        d.add(elm.Line().at(esp.GPIO34).to(cap.CAOUT).color(C_ADC)
              .label('AOUT (0-3.3V)', loc='top', fontsize=7))

        # === Power rails de cada sensor ===
        d.add(elm.Vdd().at(hd.HVCC).label('5V', fontsize=8, color=C_WARN))
        d.add(elm.Ground().at(hd.HGND))
        d.add(elm.Vdd().at(cap.CVCC).label('3.3V', fontsize=8, color=C_WARN))
        d.add(elm.Ground().at(cap.CGND))

        # === Warning sobre el HD38 a 5V → GPIO35 (debajo de la línea AOUT) ===
        warn_x = (esp.GPIO35[0] + hd.HAOUT[0]) / 2
        d.add(elm.Label().at((warn_x, esp.GPIO35[1] - 0.7))
              .label('(!) puede superar 3.3V', fontsize=7, color=C_WARN))

        add_footer(d, 'HD38 a 5V: AO puede entregar hasta 5V — sin proteccion en este HW (medir antes).\n'
                      'GPIO34 y GPIO35 son ADC1 (OK con WiFi). NO usar ADC2 con WiFi activo.\n'
                      'Atenuacion ADC 11dB -> rango lineal util ~0.15-2.5V.')
        add_title(d, 'Sensores de suelo — HD38 + Capacitivo (ADC)')

    print('  ✓ sch_adc_soil.svg')


# ---------------------------------------------------------------------------
# 4. Bus RS485: MAX485 + Sensor TH + Relay 2CH
# ---------------------------------------------------------------------------
def draw_rs485():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_rs485_modbus.svg'), show=False) as d:
        d.config(**GLOBAL_CONFIG)

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

        # === MAX485 (módulo C25B, alimentado a 5V) ===
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

        d.add(elm.Vdd().at(max485.MVCC).label('5V'))
        d.add(elm.Ground().at(max485.MGND))

        # === Conexiones ESP32 ↔ MAX485 ===
        # TX (3.3V → MAX485 DI): MAX485 VIH≈2V, 3.3V lógico HIGH es válido
        d.add(elm.Line().at(tx_pos).to(max485.DI)
              .color(C_RS485_TX).label('TX GPIO17', loc='top', fontsize=7))
        # DE/RE (3.3V → MAX485 DE): mismo análisis, OK
        d.add(elm.Line().at(de_pos).to(max485.DE)
              .color(C_RS485_DE).label('DE/RE GPIO18', loc='bottom', fontsize=7))

        # RX (MAX485 RO -> ESP32 RX): conexión directa, tal como está en el HW
        d.add(elm.Line().at(rx_pos).to(max485.RO)
              .color(C_RS485_RX).label('RX GPIO16', loc='top', fontsize=7))

        # === BUS UTP 4 conductores: VCC, B-, A+, GND ===
        # Las 4 líneas viajan paralelas. A+ y B- alineadas con DA/DB del MAX485.
        # MAX485 right-side slots: DA=1/2 (bottom), DB=2/2 (top) → y_b > y_a.
        y_a   = max485.DA[1]            # A+ (verde)
        y_b   = max485.DB[1]            # B- (azul)
        y_vcc = y_b + 1.5               # VCC (rojo, arriba de B-)
        y_gnd = y_a - 1.5               # GND (negro, debajo de A+)

        bus_x0 = max485.DA[0] + 2.0     # inicio del bus
        bus_x1 = bus_x0 + 12            # fin del bus (terminación 120Ω)

        # Conexión A+ y B- desde MAX485 al inicio del bus
        d.add(elm.Line().at(max485.DA).to((bus_x0, y_a)).color(C_BUS_A))
        d.add(elm.Line().at(max485.DB).to((bus_x0, y_b)).color(C_BUS_B))

        # Fuente de alimentación del bus (VCC y GND, externa, a la izquierda)
        ps_x = bus_x0 - 1.2
        d.add(elm.Vdd().at((ps_x, y_vcc + 0.8)).label('5-30V', fontsize=7, color=C_WARN))
        d.add(elm.Line().at((ps_x, y_vcc + 0.8)).to((ps_x, y_vcc)).color(C_VCC))
        d.add(elm.Line().at((ps_x, y_vcc)).to((bus_x0, y_vcc)).color(C_VCC))
        d.add(elm.Line().at((ps_x, y_gnd)).to((bus_x0, y_gnd)).color(C_GND))
        d.add(elm.Line().at((ps_x, y_gnd)).to((ps_x, y_gnd - 0.8)).color(C_GND))
        d.add(elm.Ground().at((ps_x, y_gnd - 0.8)))

        # Las 4 líneas horizontales del bus
        d.add(elm.Line().at((bus_x0, y_vcc)).to((bus_x1, y_vcc)).color(C_VCC))
        d.add(elm.Line().at((bus_x0, y_b)).to((bus_x1, y_b)).color(C_BUS_B))
        d.add(elm.Line().at((bus_x0, y_a)).to((bus_x1, y_a)).color(C_BUS_A))
        d.add(elm.Line().at((bus_x0, y_gnd)).to((bus_x1, y_gnd)).color(C_GND))

        # Labels de las 4 líneas
        d.add(elm.Label().at((bus_x0 + 0.3, y_vcc + 0.5)).label('VCC', fontsize=7, color=C_VCC))
        d.add(elm.Label().at((bus_x0 + 0.3, y_b   + 0.5)).label('B-',  fontsize=7, color=C_BUS_B))
        d.add(elm.Label().at((bus_x0 + 0.3, y_a   - 0.8)).label('A+',  fontsize=7, color=C_BUS_A))
        d.add(elm.Label().at((bus_x0 + 0.3, y_gnd - 0.8)).label('GND', fontsize=7, color=C_GND))

        # Label "Cable UTP" arriba del bus
        d.add(elm.Label().at((bus_x0 + 6, y_vcc + 1.5))
              .label('Cable UTP 4 pares (4 conductores usados)', fontsize=8, color=NOTE_COLOR))

        # === Helper: bornera x4 + dispositivo debajo ===
        def draw_node(x, dev_label):
            # Bornera: rectángulo vertical sobre las 4 líneas + dots
            bx = 0.45
            top = y_vcc + 0.6
            bot = y_gnd - 0.6
            d.add(elm.Line().at((x - bx, top)).to((x + bx, top)))
            d.add(elm.Line().at((x + bx, top)).to((x + bx, bot)))
            d.add(elm.Line().at((x + bx, bot)).to((x - bx, bot)))
            d.add(elm.Line().at((x - bx, bot)).to((x - bx, top)))
            for y in [y_vcc, y_b, y_a, y_gnd]:
                d.add(elm.Dot().at((x, y)))
            d.add(elm.Label().at((x + bx + 0.3, (top + bot) / 2))
                  .label('bornera\nx4', fontsize=6, color=NOTE_COLOR))

            # Caja del dispositivo, debajo de la bornera
            dev_w = 3.0
            dev_h = 1.6
            dev_top = y_gnd - 2.8
            dev_bot = dev_top - dev_h
            dev_l = x - dev_w / 2
            dev_r = x + dev_w / 2
            d.add(elm.Line().at((dev_l, dev_top)).to((dev_r, dev_top)))
            d.add(elm.Line().at((dev_r, dev_top)).to((dev_r, dev_bot)))
            d.add(elm.Line().at((dev_r, dev_bot)).to((dev_l, dev_bot)))
            d.add(elm.Line().at((dev_l, dev_bot)).to((dev_l, dev_top)))
            d.add(elm.Label().at((x, (dev_top + dev_bot) / 2))
                  .label(dev_label, fontsize=8))

            # 4 cables color-codificados de la bornera al dispositivo
            colors = [C_VCC, C_BUS_B, C_BUS_A, C_GND]
            for i, color in enumerate(colors):
                cable_x = x + (i - 1.5) * 0.3
                d.add(elm.Line().at((cable_x, bot)).to((cable_x, dev_top)).color(color))

        # Nodo 1: TH-MB-04S
        draw_node(bus_x0 + 4.0, 'TH-MB-04S\nAddr:1 (T/H)')

        # Nodo 2: Relay 2CH
        draw_node(bus_x0 + 8.5, 'Relay 2CH\nAddr:2')

        # === Terminación 120Ω entre A+ y B- al final del bus ===
        d.add(elm.Resistor().at((bus_x1, y_b)).down().toy(y_a)
              .label('120Ω\nterm', loc='right', fontsize=8))
        d.add(elm.Dot().at((bus_x1, y_b)))
        d.add(elm.Dot().at((bus_x1, y_a)))

        add_footer(d, 'Modulo C25B alimentado a 5V  •  RS485 Modbus RTU half-duplex\n'
                      'Bus cable UTP 4 pares: VCC + GND + A+ + B-  •  borneras x4 en cada nodo\n'
                      'Terminacion 120Ω al final del bus (entre A+ y B-)\n'
                      'DE/RE = GPIO18  •  9600 baud 8N1  •  Masa comun obligatoria')
        add_title(d, 'Bus RS485 — Modbus RTU (C25B/MAX485)')

    print('  ✓ sch_rs485_modbus.svg')


# ---------------------------------------------------------------------------
# 5. Diagrama de bloques del sistema
# ---------------------------------------------------------------------------
def draw_full_system():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_full_system.svg'), show=False) as d:
        d.config(**GLOBAL_CONFIG)

        # ESP32 central, más alto para acomodar 3 buses por lado sin solapamientos
        esp_w, esp_h = 5.5, 9
        esp_cx, esp_cy = 0, 0

        esp_box = d.add(flow.Box(w=esp_w, h=esp_h).at((esp_cx, esp_cy)).label(
            'ESP32 DevKit V1\n30 pines\n\nWiFi + ESP-NOW'))

        esp_left_x  = esp_box.W[0]
        esp_right_x = esp_box.E[0]
        esp_top_y   = esp_box.N[1]
        esp_bot_y   = esp_box.S[1]

        # Y de conexión de cada bus a un lado del ESP32 (3 por lado, equiespaciados)
        # Lado izquierdo (top→bottom): I2C, 1-Wire, ADC
        y_i2c  = esp_cy + 3
        y_ow   = esp_cy
        y_adc  = esp_cy - 3
        # Lado derecho (top→bottom): RS485, GPIO Relays
        y_rs   = esp_cy + 2
        y_gpio = esp_cy - 2

        col_l_x = esp_left_x - 6     # centro de la columna izquierda
        col_r_x = esp_right_x + 6    # centro de la columna derecha
        box_w_l = 4.5
        box_h_std = 2.2

        # --- COLUMNA IZQUIERDA: I2C, 1-Wire, ADC ---
        i2c_box = d.add(flow.Box(w=box_w_l, h=box_h_std).at((col_l_x, y_i2c))
                        .label('I2C Bus\nSCD30 (CO2)\nBME280 (T/H/P)'))
        d.add(elm.Line().at(i2c_box.E).right().tox(esp_left_x).color(C_I2C_SDA))
        d.add(elm.Label().at(((i2c_box.E[0] + esp_left_x) / 2, i2c_box.E[1] + 0.4))
              .label('SDA=21 SCL=22', fontsize=8, color=C_I2C_SDA))

        ow_box = d.add(flow.Box(w=box_w_l, h=box_h_std).at((col_l_x, y_ow))
                       .label('1-Wire\nDS18B20 x N'))
        d.add(elm.Line().at(ow_box.E).right().tox(esp_left_x).color(C_ONEWIRE))
        d.add(elm.Label().at(((ow_box.E[0] + esp_left_x) / 2, ow_box.E[1] + 0.4))
              .label('GPIO4 + 4.7kΩ', fontsize=8, color=C_ONEWIRE))

        adc_box = d.add(flow.Box(w=box_w_l, h=box_h_std).at((col_l_x, y_adc))
                        .label('ADC Suelo\nCapacitivo (GPIO34)\nHD38 (GPIO35)'))
        d.add(elm.Line().at(adc_box.E).right().tox(esp_left_x).color(C_ADC))
        d.add(elm.Label().at(((adc_box.E[0] + esp_left_x) / 2, adc_box.E[1] + 0.4))
              .label('GPIO34/35', fontsize=8, color=C_ADC))

        # --- COLUMNA DERECHA: RS485, GPIO Relays ---
        rs_box = d.add(flow.Box(w=box_w_l, h=3.0).at((col_r_x, y_rs))
                       .label('RS485 Modbus\nMAX485 (C25B)\nSensor TH\nRelay 2CH'))
        d.add(elm.Line().at(rs_box.W).left().tox(esp_right_x).color(C_RS485_TX))
        d.add(elm.Label().at(((rs_box.W[0] + esp_right_x) / 2, rs_box.W[1] + 0.4))
              .label('TX=17 RX=16 DE/RE=18', fontsize=8, color=C_RS485_TX))

        gr_box = d.add(flow.Box(w=box_w_l, h=2.6).at((col_r_x, y_gpio))
                       .label('GPIO Relays\n(salidas digitales)\nconfig: GPIO 0-39\nlibres: 13, 19, 23,\n25-27, 32, 33'))
        d.add(elm.Line().at(gr_box.W).left().tox(esp_right_x).color(C_GPIO))
        d.add(elm.Label().at(((gr_box.W[0] + esp_right_x) / 2, gr_box.W[1] + 0.4))
              .label('GPIO out', fontsize=8, color=C_GPIO))

        # --- ALIMENTACIÓN: 5V USB debajo del ESP32, conexión vertical pura ---
        pw_box = d.add(flow.Box(w=3.5, h=1.8).at((esp_cx, esp_bot_y - 2.5))
                       .label('5V USB\n-> 3.3V reg').color(C_VCC))
        d.add(elm.Line().at(pw_box.N).up().toy(esp_bot_y).color(C_VCC))
        d.add(elm.Label().at((pw_box.N[0] + 1.2, (pw_box.N[1] + esp_bot_y) / 2))
              .label('5V / GND', fontsize=8, color=C_VCC))

        add_title(d, 'Diagrama en bloques — Sistema de monitoreo')

    print('  ✓ sch_full_system.svg')


# ---------------------------------------------------------------------------
# 6. Pinout ESP32 DevKit V1 (30 pines, esp32dev / ESP32-WROOM-32)
# ---------------------------------------------------------------------------
def draw_esp32_pinout():
    with schemdraw.Drawing(file=os.path.join(OUT, 'sch_esp32_pinout.svg'), show=False) as d:
        d.config(**GLOBAL_CONFIG)

        # Orden FÍSICO real del DevKit V1 de 30 pines (15/lado), top -> bottom.
        # Cada entrada: (anchorname, etiqueta_mostrada, funcion, color de la paleta)
        GRAY = NOTE_COLOR
        pins_left = [
            ('EN',     'EN',     'Reset / Enable',  GRAY),
            ('GPIO36', 'GPIO36', 'ADC1_CH0 (VP)',   GRAY),
            ('GPIO39', 'GPIO39', 'ADC1_CH3 (VN)',   GRAY),
            ('GPIO34', 'GPIO34', 'Capacitivo IN',   C_ADC),
            ('GPIO35', 'GPIO35', 'HD38 IN  !!',     C_WARN),
            ('GPIO32', 'GPIO32', '—',               GRAY),
            ('GPIO33', 'GPIO33', '—',               GRAY),
            ('GPIO25', 'GPIO25', '—',               GRAY),
            ('GPIO26', 'GPIO26', '—',               GRAY),
            ('GPIO27', 'GPIO27', '—',               GRAY),
            ('GPIO14', 'GPIO14', '—',               GRAY),
            ('GPIO12', 'GPIO12', '—',               GRAY),
            ('GPIO13', 'GPIO13', '—',               GRAY),
            ('GNDL',   'GND',    'GND',             C_GND),
            ('VIN',    'VIN',    '5V Input',        C_VCC),
        ]
        pins_right = [
            ('GPIO23', 'GPIO23', '—',               GRAY),
            ('GPIO22', 'GPIO22', 'SCL (I2C)',       C_I2C_SCL),
            ('TX0',    'TX0',    'Serial TX0',      GRAY),
            ('RX0',    'RX0',    'Serial RX0',      GRAY),
            ('GPIO21', 'GPIO21', 'SDA (I2C)',       C_I2C_SDA),
            ('GPIO19', 'GPIO19', '—',               GRAY),
            ('GPIO18', 'GPIO18', 'DE/RE RS485',     C_RS485_DE),
            ('GPIO5',  'GPIO5',  '—',               GRAY),
            ('GPIO17', 'GPIO17', 'RS485 TX (TX2)',  C_RS485_TX),
            ('GPIO16', 'GPIO16', 'RS485 RX (RX2)',  C_RS485_RX),
            ('GPIO4',  'GPIO4',  '1-Wire',          C_ONEWIRE),
            ('GPIO2',  'GPIO2',  'LED interno',     GRAY),
            ('GPIO15', 'GPIO15', '—',               GRAY),
            ('GNDR',   'GND',    'GND',             C_GND),
            ('3V3',    '3V3',    '3.3V Power',      C_VCC),
        ]

        # slot '1/N' = abajo, 'N/N' = arriba. Las listas están en orden
        # top->bottom, así que invertimos: índice 0 -> slot N (arriba).
        nL = len(pins_left)
        nR = len(pins_right)
        ic_pins = []
        for i, (anchor, disp, _, _) in enumerate(pins_left):
            ic_pins.append(elm.IcPin(name=disp, anchorname=anchor, side='left',
                                     slot=f'{nL - i}/{nL}'))
        for i, (anchor, disp, _, _) in enumerate(pins_right):
            ic_pins.append(elm.IcPin(name=disp, anchorname=anchor, side='right',
                                     slot=f'{nR - i}/{nR}'))

        # Sin label central: el título superior ya identifica el chip y evita
        # que el texto choque con los nombres de pin de la fila central.
        esp = d.add(elm.Ic(
            pins=ic_pins,
            edgepadW=1.2, edgepadH=0.3,
            pinspacing=0.9, lsize=12,
        ))

        # Etiquetas de función alineadas al borde del pin (estilo datasheet):
        # las del lado izquierdo terminan junto al pin (right-aligned), las del
        # derecho arrancan junto al pin (left-aligned).
        for anchor, _, func, color in pins_left:
            pin_pos = getattr(esp, anchor)
            d.add(elm.Label().at((pin_pos[0] - 0.4, pin_pos[1]))
                  .label(func, fontsize=7.5, color=color, halign='right', valign='center'))

        for anchor, _, func, color in pins_right:
            pin_pos = getattr(esp, anchor)
            d.add(elm.Label().at((pin_pos[0] + 0.4, pin_pos[1]))
                  .label(func, fontsize=7.5, color=color, halign='left', valign='center'))

        add_footer(d, 'I2C (GPIO21/22)  •  RS485 (GPIO16/17/18)  •  1-Wire (GPIO4)  •  '
                      'ADC1 (GPIO34/35)\n'
                      'ADC1 (GPIO32-39) funciona con WiFi  •  NO usar ADC2 con WiFi activo\n'
                      'ESP32 DevKit V1 / WROOM-32 (board=esp32dev) — 30 pines, 15/lado')
        add_title(d, 'Pinout — ESP32 DevKit V1 (30 pines)')

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
