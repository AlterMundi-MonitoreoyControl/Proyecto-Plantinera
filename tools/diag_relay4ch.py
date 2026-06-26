#!/usr/bin/env python3
"""
Diagnóstico para módulo de relé Modbus 4CH (LC-Modbus-4R-D7)
Default addr: 255 (0xFF), baudrate: 9600

Pruebas que realiza:
  1. FC01 — Leer estado de coils (relés 1-4)
  2. FC02 — Leer entradas optoaisladas (IN1-IN4)
  3. FC05 — Escribir coil 1 ON y luego OFF (prueba de escritura)
  Usa también broadcast addr=0 para FC05 si el addr normal falla.
"""

import serial
import struct
import time
import sys

PORT    = "/dev/ttyUSB2"
BAUD    = 9600
TIMEOUT = 1.0

# Dirección a probar (puede pasarse como arg)
ADDRESSES = [255, 1, 2, 3] if len(sys.argv) < 2 else [int(sys.argv[1])]

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
    """FC01 — Lee 4 coils desde reg 0x0000"""
    frame = build_frame(addr, 0x01, 0x00, 0x00, 0x00, 0x04)  # start=0, qty=4
    raw = transact(ser, frame, 2, "FC01 ReadCoils x4")
    if raw and len(raw) >= 4 and raw[1] == 0x01:
        byte_count = raw[2]
        coil_byte  = raw[3]
        states = [(coil_byte >> i) & 1 for i in range(4)]
        print(f"  ✅ FC01 OK — Relés: R1={states[0]} R2={states[1]} R3={states[2]} R4={states[3]}")
        return True
    elif raw and raw[1] & 0x80:
        print(f"  ❌ Excepción Modbus: código {raw[2]:#04x}")
    return False

def test_fc02_read_inputs(ser, addr):
    """FC02 — Lee 4 discrete inputs desde reg 0x0000"""
    frame = build_frame(addr, 0x02, 0x00, 0x00, 0x00, 0x04)
    raw = transact(ser, frame, 2, "FC02 ReadInputs x4")
    if raw and len(raw) >= 4 and raw[1] == 0x02:
        byte_count = raw[2]
        in_byte    = raw[3]
        states = [(in_byte >> i) & 1 for i in range(4)]
        print(f"  ✅ FC02 OK — Entradas: IN1={states[0]} IN2={states[1]} IN3={states[2]} IN4={states[3]}")
        return True
    elif raw and raw[1] & 0x80:
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

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  Diagnóstico Relay 4CH — Puerto: {PORT} @ {BAUD} baud")
    print(f"{'='*55}\n")

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD,
            bytesize=8, parity='N', stopbits=1,
            timeout=TIMEOUT
        )
    except Exception as e:
        print(f"❌ No se pudo abrir {PORT}: {e}")
        sys.exit(1)

    print(f"✅ Puerto {PORT} abierto\n")
    time.sleep(0.2)

    found_addr = None

    for addr in ADDRESSES:
        print(f"\n{'─'*45}")
        print(f"🔎 Probando dirección {addr} (0x{addr:02X})")
        print(f"{'─'*45}")

        ok1 = test_fc01_read_coils(ser, addr)
        time.sleep(0.1)
        ok2 = test_fc02_read_inputs(ser, addr)

        if ok1 or ok2:
            found_addr = addr
            print(f"\n🎉 ¡Dispositivo encontrado en addr={addr}!")
            print("   Probando escritura FC05...")
            time.sleep(0.1)
            test_fc05_toggle(ser, addr)
            break
        else:
            print(f"  — Sin respuesta en addr={addr}")

    if found_addr is None:
        # Último recurso: broadcast para descubrir la dirección
        dev_addr = test_read_device_addr(ser)
        if dev_addr:
            found_addr = dev_addr

    print(f"\n{'='*55}")
    if found_addr:
        print(f"✅ RESULTADO: dispositivo encontrado en addr={found_addr}")
    else:
        print("❌ RESULTADO: ninguna respuesta recibida")
        print("\n   Posibles causas:")
        print("   • Cableado A+/B- invertido")
        print("   • Baudrate diferente (prueba 4800 ó 19200 como arg2)")
        print("   • Módulo sin alimentación DC7-24V")
        print("   • Puerto serie en uso por otro proceso (monitor serial)")
    print(f"{'='*55}\n")

    ser.close()

if __name__ == "__main__":
    main()
