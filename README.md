# Proyecto Plantinera

Firmware ESP32 para **monitoreo y control automatizado** de incubadoras y plantineras.
Mide sensores ambientales, actúa sobre relés mediante reglas configurables y transmite datos a Grafana/InfluxDB.

**Versión:** 0.2.12 · **Plataforma:** ESP32 · **Framework:** Arduino / PlatformIO

---

## Funcionalidades

- **Sensores:** CO2, temperatura, humedad, presión, humedad de suelo (múltiples simultáneos)
- **Control:** relés Modbus y GPIO controlados por reglas automáticas o manualmente via API
- **Reglas:** motor de automatización configurable (IF sensor > umbral → actuador ON por N ms)
- **Datos:** transmisión a InfluxDB/Grafana, salida RS485 opcional
- **Mesh:** ESP-NOW para nodos sensor sin WiFi (~100 m alcance)
- **Web UI:** configuración, dashboard en tiempo real y editor de reglas en el dispositivo
- **OTA:** actualizaciones de firmware vía WiFi desde releases de GitHub

---

## Sensores Soportados

| Sensor | Protocolo | Mide |
|--------|-----------|------|
| SCD30 | I2C | CO2, temperatura, humedad |
| BME280 | I2C | Temperatura, humedad, presión |
| DS18B20 | OneWire | Temperatura (múltiples en cadena) |
| Capacitive / HD38 | ADC | Humedad de suelo |
| Modbus TH | RS485 | Temperatura, humedad (remoto) |
| Modbus 7-en-1 | RS485 | N, P, K, pH, EC, temp, humedad |

---

## Hardware

**Pines por defecto:**

```
I2C (SCD30, BME280):   SDA=21, SCL=22
OneWire (DS18B20):     GPIO14  (pull-up 4.7kΩ a 3.3V)
Capacitive ADC:        GPIO34
RS485 (MAX485):        RX=16, TX=17, DE/RE=18
```

---

## Instalación

```bash
git clone https://github.com/AlterMundi-MonitoreoyControl/Proyecto-Plantinera
cd Proyecto-Plantinera

# Credenciales de InfluxDB y OTA
cp include/constants_private.h.example include/constants_private.h
# Editar: URL InfluxDB, token, repo GitHub para OTA

# Compilar y flashear
pio run -e esp32dev_multi --target upload
```

### Entornos de compilación

| Entorno | Sensores | Extras |
|---------|----------|--------|
| `esp32dev` | SCD30 | — |
| `esp32dev_multi` | Todos | RS485, ESP-NOW, debug |
| `esp32dev_multi_prod` | Todos | RS485, ESP-NOW, sin debug |
| `esp32dev_multi_ota` | Todos | OTA habilitado |
| `esp32dev_espnow` | Todos | Mesh ESP-NOW |
| `esp32dev_bme280` | BME280 | — |
| `esp32dev_capacitive` | Capacitive | — |

---

## Configuración inicial

1. Al primer arranque el ESP32 levanta un AP (`ESP32-{MAC}`)
2. Conectarse a ese AP
3. Ir a `http://192.168.4.1/settings`
4. Configurar WiFi, sensores y relés
5. Guardar → el dispositivo se conecta a la red y queda disponible en su IP local

---

## Uso

### API REST

El dispositivo expone una API REST en el puerto 80. Endpoints principales:

| Endpoint | Descripción |
|----------|-------------|
| `GET /actual` | Lecturas de todos los sensores y estado de actuadores |
| `GET /api/status` | Estado del sistema (WiFi, uptime, conteo de sensores) |
| `GET /config` | Configuración completa |
| `POST /config` | Actualizar configuración (merge parcial) |
| `GET /actuator/status` | Estado de todos los actuadores |
| `POST /actuator/command` | Comando manual a un actuador |
| `GET /rules` | Reglas de automatización |
| `POST /rules/save` | Guardar y aplicar reglas |
| `GET /espnow/status` | Estado del mesh ESP-NOW |
| `POST /restart` | Reiniciar dispositivo |

Ver [docs/API.md](docs/API.md) para la referencia completa con ejemplos.

### Motor de reglas

Las reglas se definen en JSON y se guardan en el dispositivo:

```json
{
  "rules": [
    {
      "expr": { "sensor": {"device": 0, "id": 1}, "cond": "GT", "value": 38.0 },
      "actuator": 16,
      "state": true,
      "priority": 2,
      "duration_ms": 30000
    }
  ]
}
```

> Si temperatura (sensor 1) > 38°C → activar relay (id 16) por 30 segundos.

Ver [docs/RULES.md](docs/RULES.md) para el esquema completo y el editor web (`/rules-editor`).

### Mesh ESP-NOW

Para instalaciones donde algunos nodos no tienen WiFi:

- **Gateway:** conectado a WiFi, recibe datos de nodos remotos y los reenvía a Grafana
- **Sensor:** sin WiFi, transmite lecturas al gateway por ESP-NOW

El rol se auto-detecta al arrancar. Ver [docs/ESPNOW.md](docs/ESPNOW.md).

---

## Troubleshooting

| Problema | Diagnóstico | Fix |
|----------|-------------|-----|
| Sensor no detectado | `pio device monitor` → buscar error de init | Verificar cableado y voltaje 3.3V |
| Sin datos en Grafana | `curl http://{IP}/actual` | Verificar URL/token en `constants_private.h` |
| ESP-NOW no sincroniza | `GET /espnow/status` | Verificar mismo canal WiFi en todos los nodos |
| WiFi no conecta | — | `POST /config/reset` → reconectar al AP |
| `401` en API | — | `GET /api/admin/info` → usar `-u admin:<pass>` |

---

## Documentación

- [API Reference](docs/API.md) — endpoints HTTP completos
- [Reglas](docs/RULES.md) — motor de automatización
- [Configuración](docs/CONFIGURATION.md) — `config.json` completo
- [Sensores](docs/SENSORS.md) — detalles de cada sensor
- [ESP-NOW](docs/ESPNOW.md) — protocolo mesh
- [Data Flow](docs/DATA_FLOW.md) — flujo de datos sensor → Grafana
