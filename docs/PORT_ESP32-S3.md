# Port a ESP32-S3

Notas del port del firmware (originalmente ESP32 clásico) a **ESP32-S3**
(probado en una placa **ESP32-S3-DevKitC / WROOM-1 N16R8**: 16 MB flash, 8 MB PSRAM).

> El ESP32-S3 es otra arquitectura: distinto layout de flash y, sobre todo,
> **distinto mapeo de GPIO**. Un binario de ESP32 clásico **no corre** en S3.

## Cómo compilar / flashear

Environment nuevo: **`esp32s3_multi`** (espeja `esp32dev_multi`, mismo set de
sensores/flags, pero `board = esp32-s3-devkitc-1` y `board_upload.flash_size = 16MB`).

```bash
pio run -e esp32s3_multi -t upload --upload-port <PUERTO>
```

### Puertos USB de la DevKitC-1
- **Puerto "USB" nativo** (VID `303A`): **no** auto-resetea → para flashear hay
  que entrar a modo descarga a mano (mantener **BOOT**, tocar **RST**, soltar BOOT).
- **Puerto "UART"/"COM"** (chip puente CH34x, VID `1A86`): **sí auto-resetea** y
  además expone los logs de debug por serie. **Recomendado** para flashear y monitorear.

## Cambios hechos en el port

1. **Env `esp32s3_multi`** en `platformio.ini` (board S3 + flash 16 MB).
2. **Pin del sensor capacitivo** (`include/sensors/SensorCapacitive.h`):
   en S3 el **GPIO34 no existe como ADC** → `CAPACITIVE_PIN` es condicional por target:
   - ESP32-S3 → **GPIO5** (ADC1_CH4)
   - ESP32 clásico → **GPIO34** (ADC1_CH6, sin cambios)
   También se usa `CAPACITIVE_PIN` como default en `SensorManager.h` y `configFile.cpp`
   (antes `34` hardcodeado).
3. **Pin del sensor HD-38** (`include/sensors/HD38Sensor.h`): mismo caso que el
   capacitivo → `HD38_PIN` condicional: S3 → **GPIO6** (ADC1_CH5), clásico →
   **GPIO35**. En N16R8 el GPIO35 además lo usa la PSRAM octal. Default usado
   también en `SensorManager.h`.
4. **IP del Access Point** (`lib/WifiManager/WiFiManager.cpp` vía `WiFiManager.h`
   `StaConfig`): estaba en `192.168.16.10`; se corrigió a **`192.168.4.1`** para
   coincidir con el README y con la app (`DIRECT_MODE_IP`). (Bug previo, no exclusivo de S3.)

## ⚠️ Pendiente / a revisar

- **Pines digitales en S3:** OneWire (GPIO4), RS485 `rx/tx/de` (16/17/18) y relés
  GPIO (default 2) son válidos en S3 → **sin cambios**. (Al configurar pines a mano,
  evitar igual strapping 0/3/45/46, USB nativo 19/20 y flash/PSRAM 26-37.)
- **UI web** (`src/web_assets.cpp`): el formulario todavía pre-llena `pin 34`/`35` y
  limita `max=39` (rango del clásico; S3 llega a 48). Es solo la ayuda visual del form
  (la config también se setea por API); queda pendiente hacerlo target-aware.
- **App: requests en paralelo** — *resuelto del lado de la app*: `loadHubData` ahora
  pide en **serie** (no `Promise.all`) para no saturar el `WebServer` de 1 conexión del ESP32.

## Verificación realizada (modo Directo)

- **Firmware** sirviendo en `192.168.4.1`: `/api/status`, `/config`, `/actual`,
  `/api/relays` devuelven datos reales.
- **App (modo Directo)** mostrando datos reales del chip (HubHome + Detalle Sensor).
- **Actuador (escritura):** `POST /api/relay/toggle?addr=<pin>&ch=0` sobre un relé
  GPIO de prueba cambia el estado `false ↔ true`.
- **Fix del capacitivo verificado:** tras el fix, el boot muestra
  `[Capacitive] pin 5 ... OK` y lecturas ADC reales, **sin** el error
  `Pin 34 is not ADC pin!`.
