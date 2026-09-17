# Telemetry Stream — IoT Sensor Ingestion & Alert Engine

## Purpose

Design field-device telemetry systems for crop risk, irrigation, microclimate monitoring and edge-AI farming assistants.

## Sensor inputs

Common field signals:

- soil moisture,
- soil temperature,
- air temperature,
- relative humidity,
- rainfall / rain gauge,
- light intensity,
- leaf wetness,
- battery and solar status,
- camera inference result,
- pest-trap count.

## MQTT topic design

```text
agrishield/{region}/{village}/{farmId}/telemetry
agrishield/{region}/{village}/{farmId}/vision
agrishield/{region}/{village}/{farmId}/alerts
agrishield/{region}/{village}/{farmId}/commands
```

## Telemetry payload

```json
{
  "deviceId": "edge-001",
  "farmId": "farm-001",
  "timestamp": "2026-09-17T10:30:00+05:30",
  "soilMoisture": 31,
  "soilTemperature": 27.4,
  "airTemperature": 32.1,
  "humidity": 78,
  "rainfall": 4.2,
  "leafWetness": 0.71,
  "battery": 86,
  "solarCharging": true
}
```

## Alert trigger examples

| Condition | Possible Alert |
| --- | --- |
| Soil moisture below crop threshold | Irrigate today |
| High humidity + leaf wetness + vulnerable crop stage | Fungal disease risk |
| Rainfall above flood threshold | Waterlogging/flood alert |
| High temperature for consecutive days | Heat stress warning |
| Pest count above threshold | Pest outbreak watch |
| Low battery | Device maintenance needed |

## Edge-to-cloud strategy

1. Device reads sensors.
2. On-device model or threshold engine creates local alert.
3. Advisory is shown on display/voice/SMS immediately.
4. MQTT sync happens when network is available.
5. Cloud dashboard aggregates village and district patterns.

## Reliability rules

- Store readings locally when network fails.
- Batch sync to reduce bandwidth.
- Use timestamps from device and server.
- Validate impossible sensor readings.
- Keep SMS/display messages short.
- Do not require cloud response for critical local alerts.

