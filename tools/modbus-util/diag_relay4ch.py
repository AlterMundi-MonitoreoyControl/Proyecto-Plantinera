#!/usr/bin/env python3
"""
Diagnóstico y control para módulo de relé Modbus 4CH (LC-Modbus-4R-D7)
SKU: LC-Modbus-4R-D7 v 2.1 | Default addr: 255 (0xFF) | Default baud: 9600

══════════════════════════════════════════════════════
  COMANDOS
══════════════════════════════════════════════════════

  SCAN (descubrimiento via broadcast FC03):
    python diag_relay4ch.py
    python diag_relay4ch.py 100        — fallback directo a addr 100

  CONTROL DE RELÉS (FC05):
    python diag_relay4ch.py <addr> on  [1-4]   — enciende relé (default ch=1)
    python diag_relay4ch.py <addr> off [1-4]   — apaga relé
    Ejemplos:
      python diag_relay4ch.py 100 on           — enciende relé 1
      python diag_relay4ch.py 100 on  3        — enciende relé 3
      python diag_relay4ch.py 100 off 2        — apaga relé 2

  ESTADO (FC01 relés + FC02 entradas):
    python diag_relay4ch.py <addr> status
    Ejemplo:
      python diag_relay4ch.py 100 status

  CAMBIAR DIRECCIÓN (FC16 broadcast):
    python diag_relay4ch.py setaddr <nueva_addr>
    Ejemplo:
      python diag_relay4ch.py setaddr 5        — cambia addr a 5 (broadcast)
    ⚠️  Reconectar o reiniciar el módulo puede ser necesario para que tome efecto.
    ⚠️  Válido solo si hay UN único dispositivo en el bus.

══════════════════════════════════════════════════════
  HARDWARE
══════════════════════════════════════════════════════
  Alimentación : DC 7-24V (terminal VCC/GND o jack DC-005)
  RS485        : A+ → A+,  B- → B-
  TTL UART     : GND→GND, RXD→TXD host, TXD→RXD host
  Relés        : NO/NC/COM, 10A 250VAC
  Entradas     : IN1-IN4, optoacopladas DC 3.3-30V
  Baud rates   : 4800 / 9600 (default) / 19200
  Addr range   : 1-255, default 255 (0xFF)
"""

import serial
import struct
import time
import sys

PORT    = "/dev/ttyUSB2"
BAUD    = 9600
TIMEOUT = 1.0

# ── CRC16 Modbus ──────────────────────────────────────────────────────────────
def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)

def build_frame(addr, fc, *args) -> bytes:
    frame = bytes([addr, fc]) + bytes(args)
    return frame + crc16(frame)

def check_crc(frame: bytes) -> bool:
    if len(frame) < 2:
        return False
    return crc16(frame[:-2]) == frame[-2:]

# ── Transacción serial ────────────────────────────────────────────────────────
def transact(ser: serial.Serial, frame: bytes, expected_len: int, label: str):
    ser.reset_input_buffer()
    ser.write(frame)
    hex_sent = " ".join(f"{b:02X}" for b in frame)
    print(f"  → TX [{label}]: {hex_sent}")

    time.sleep(0.05)
    raw = ser.read(expected_len + 4)

    if not raw:
        print("  ← RX: <sin respuesta>")
        return None

    hex_recv = " ".join(f"{b:02X}" for b in raw)
    print(f"  ← RX: {hex_recv}")

    if not check_crc(raw):
        print("  ⚠️  CRC inválido")
        return None

    return raw

# ── Tests ─────────────────────────────────────────────────────────────────────
def test_fc01_read_coils(ser, addr):
    """FC01 — Lee 8 coils desde reg 0x0000 (datasheet: qty=0x08)"""
    frame = build_frame(addr, 0x01, 0x00, 0x00, 0x00, 0x08)  # start=0, qty=8
    raw = transact(ser, frame, 2, "FC01 ReadCoils x8")
    if raw and len(raw) >= 4 and raw[1] == 0x01:
        coil_byte = raw[3]
        states = [(coil_byte >> i) & 1 for i in range(4)]
        print(f"  ✅ FC01 OK — Relés: R1={states[0]} R2={states[1]} R3={states[2]} R4={states[3]}")
        return True
    elif raw and (raw[1] & 0x80):
        print(f"  ❌ Excepción Modbus: código {raw[2]:#04x}")
    return False

def test_fc02_read_inputs(ser, addr):
    """FC02 — Lee 8 discrete inputs desde reg 0x0000 (datasheet: qty=0x08)"""
    frame = build_frame(addr, 0x02, 0x00, 0x00, 0x00, 0x08)  # start=0, qty=8
    raw = transact(ser, frame, 2, "FC02 ReadInputs x8")
    if raw and len(raw) >= 4 and raw[1] == 0x02:
        in_byte = raw[3]
        states = [(in_byte >> i) & 1 for i in range(4)]
        print(f"  ✅ FC02 OK — Entradas: IN1={states[0]} IN2={states[1]} IN3={states[2]} IN4={states[3]}")
        return True
    elif raw and (raw[1] & 0x80):
        print(f"  ❌ Excepción Modbus: código {raw[2]:#04x}")
    return False

def test_fc05_toggle(ser, addr):
    """FC05 — Enciende y apaga relé 1"""
    # ON
    frame_on  = build_frame(addr, 0x05, 0x00, 0x00, 0xFF, 0x00)
    raw = transact(ser, frame_on, 6, "FC05 WriteCoil1=ON")
    if raw and raw[1] == 0x05:
        print("  ✅ FC05 ON — Echo OK")
        time.sleep(0.5)
        # OFF
        frame_off = build_frame(addr, 0x05, 0x00, 0x00, 0x00, 0x00)
        raw2 = transact(ser, frame_off, 6, "FC05 WriteCoil1=OFF")
        if raw2 and raw2[1] == 0x05:
            print("  ✅ FC05 OFF — Echo OK")
            return True
    elif raw and raw[1] & 0x80:
        print(f"  ❌ Excepción Modbus: código {raw[2]:#04x}")
    return False

def test_read_device_addr(ser):
    """Lee dirección del dispositivo usando addr broadcast 0x00 (FC03 reg 0x0000)"""
    frame = build_frame(0x00, 0x03, 0x00, 0x00, 0x00, 0x01)
    print("\n🔍 Probando broadcast addr=0 para leer dirección de dispositivo...")
    raw = transact(ser, frame, 4, "FC03 ReadAddr broadcast")
    if raw and len(raw) >= 5 and raw[1] == 0x03:
        dev_addr = raw[4]
        print(f"  ✅ Dispositivo responde con dirección: {dev_addr} (0x{dev_addr:02X})")
        return dev_addr
    return None

# ── Cambiar dirección ─────────────────────────────────────────────────────────
def set_device_addr(ser, new_addr):
    """FC16 broadcast — Escribe la nueva dirección Modbus en el dispositivo.
    Datasheet cmd 7/8: 00 10 00 00 00 01 02 00 <addr> CRC
    El dispositivo responde haciendo eco del frame completo.
    """
    if not 1 <= new_addr <= 255:
        print(f"  ❌ Dirección inválida: {new_addr} (debe ser 1-255)")
        return False

    # FC16 Write Multiple Registers, broadcast addr=0
    frame = build_frame(0x00, 0x10, 0x00, 0x00, 0x00, 0x01, 0x02, 0x00, new_addr)
    # Response es eco completo del request (11 bytes según datasheet)
    raw = transact(ser, frame, 7, f"FC16 SetAddr→{new_addr}")
    if raw and len(raw) >= 2 and raw[1] == 0x10:
        print(f"  ✅ Dirección cambiada a {new_addr} (0x{new_addr:02X})")
        print("  ℹ️  Verificando con broadcast FC03...")
        time.sleep(0.3)
        confirmed = test_read_device_addr(ser)
        if confirmed == new_addr:
            print(f"  ✅ Confirmado: dispositivo responde en addr={new_addr}")
        else:
            print(f"  ⚠️  Broadcast reporta addr={confirmed} (esperaba {new_addr})")
            print("      El módulo puede necesitar reinicio para aplicar el cambio.")
        return True
    elif raw and (raw[1] & 0x80):
        print(f"  ❌ Excepción Modbus: código {raw[2]:#04x}")
    else:
        print("  ❌ Sin respuesta o respuesta inválida")
    return False

# ── Relay write ───────────────────────────────────────────────────────────────
def write_relay(ser, addr, channel, state):
    """FC05 — Enciende o apaga un relé individual. channel: 1-4, state: True=ON."""
    if not 1 <= channel <= 4:
        print(f"  ❌ Canal inválido: {channel} (debe ser 1-4)")
        return False
    reg = channel - 1  # relay 1 → 0x0000, relay 2 → 0x0001, ...
    data_hi = 0xFF if state else 0x00
    frame = build_frame(addr, 0x05, 0x00, reg, data_hi, 0x00)
    label = f"FC05 Relay{channel}={'ON' if state else 'OFF'}"
    raw = transact(ser, frame, 6, label)
    if raw and len(raw) >= 6 and raw[1] == 0x05:
        print(f"  ✅ Relé {channel} {'ON' if state else 'OFF'} — Echo OK")
        return True
    elif raw and (raw[1] & 0x80):
        print(f"  ❌ Excepción Modbus: código {raw[2]:#04x}")
    else:
        print("  ❌ Sin respuesta o respuesta inválida")
    return False

# ── Main ──────────────────────────────────────────────────────────────────────
def open_port():
    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD,
            bytesize=8, parity='N', stopbits=1,
            timeout=TIMEOUT
        )
        print(f"✅ Puerto {PORT} abierto\n")
        time.sleep(0.2)
        return ser
    except Exception as e:
        print(f"❌ No se pudo abrir {PORT}: {e}")
        sys.exit(1)

def run_scan(ser, addresses):
    """Descubre el dispositivo via broadcast FC03, luego prueba FC01/FC02/FC05."""
    found_addr = None

    # Paso 1: broadcast FC03 para leer dirección real del dispositivo
    dev_addr = test_read_device_addr(ser)
    if dev_addr is not None:
        found_addr = dev_addr
        print(f"\n{'─'*45}")
        print(f"🔎 Probando addr={found_addr} (0x{found_addr:02X}) hallada por broadcast")
        print(f"{'─'*45}")
        time.sleep(0.1)
        ok1 = test_fc01_read_coils(ser, found_addr)
        time.sleep(0.1)
        ok2 = test_fc02_read_inputs(ser, found_addr)
        time.sleep(0.1)
        test_fc05_toggle(ser, found_addr)
    else:
        # Fallback: escanear las direcciones provistas manualmente
        print("\n⚠️  Broadcast sin respuesta, probando direcciones manuales...")
        for addr in addresses:
            print(f"\n{'─'*45}")
            print(f"🔎 Probando dirección {addr} (0x{addr:02X})")
            print(f"{'─'*45}")
            ok1 = test_fc01_read_coils(ser, addr)
            time.sleep(0.1)
            ok2 = test_fc02_read_inputs(ser, addr)
            if ok1 or ok2:
                found_addr = addr
                print(f"\n🎉 ¡Dispositivo encontrado en addr={addr}!")
                time.sleep(0.1)
                test_fc05_toggle(ser, addr)
                break
            else:
                print(f"  — Sin respuesta en addr={addr}")

    print(f"\n{'='*55}")
    if found_addr is not None:
        print(f"✅ RESULTADO: dispositivo encontrado en addr={found_addr}")
    else:
        print("❌ RESULTADO: ninguna respuesta recibida")
        print("\n   Posibles causas:")
        print("   • Cableado A+/B- invertido")
        print("   • Baudrate diferente (prueba 4800 ó 19200)")
        print("   • Módulo sin alimentación DC7-24V")
        print("   • Puerto serie en uso por otro proceso (monitor serial)")
    print(f"{'='*55}\n")

def main():
    args = sys.argv[1:]

    print(f"\n{'='*55}")
    print(f"  Relay 4CH — Puerto: {PORT} @ {BAUD} baud")
    print(f"{'='*55}\n")

    # ── setaddr ───────────────────────────────────────────────────────────────
    # Usage: diag_relay4ch.py setaddr <new_addr>
    if len(args) >= 2 and args[0].lower() == "setaddr":
        new_addr = int(args[1])
        ser = open_port()
        set_device_addr(ser, new_addr)
        ser.close()
        return

    # ── write / on / off ─────────────────────────────────────────────────────
    # Usage: diag_relay4ch.py <addr> on|off [channel]
    if len(args) >= 2 and args[1].lower() in ("on", "off"):
        addr    = int(args[0])
        state   = args[1].lower() == "on"
        channel = int(args[2]) if len(args) >= 3 else 1
        ser = open_port()
        write_relay(ser, addr, channel, state)
        ser.close()
        return

    # ── status ────────────────────────────────────────────────────────────────
    # Usage: diag_relay4ch.py <addr> status
    if len(args) >= 2 and args[1].lower() == "status":
        addr = int(args[0])
        ser = open_port()
        print(f"🔎 Estado del dispositivo addr={addr} (0x{addr:02X})")
        test_fc01_read_coils(ser, addr)
        time.sleep(0.1)
        test_fc02_read_inputs(ser, addr)
        ser.close()
        return

    # ── scan ──────────────────────────────────────────────────────────────────
    addresses = [5, 1, 2, 3] if not args else [int(args[0])]
    ser = open_port()
    run_scan(ser, addresses)
    ser.close()

if __name__ == "__main__":
    main()
