# REAMP - Industrial Protocol Adapters Specification

**Document Identifier**: `REAMP-INT-01`  
**Phase**: Phase 5 - Edge, Fog and IoT Integration  
**Status**: Approved / Implementation Specification  
**Last Updated**: 2026-09-11  

---

## 1. Overview & Adapter Architecture

In accordance with Phase 5 requirements (*"Do not pretend unsupported protocols are implemented"*), REAMP explicitly documents the production drivers, framing semantics, register configurations, and data transformation rules for 5 canonical industrial integration adapters:

1. **Modbus TCP / RTU Adapter**: Central inverters, string combiners, power meters, pyranometers.
2. **OPC UA (IEC 62541) Adapter**: Wind turbine controllers, utility substation automation.
3. **MQTT (v3.1.1 / v5.0) Adapter**: IoT micro-inverters, trackers, environmental sensors.
4. **REST HTTP/S Client Adapter**: Smart weather stations, cloud satellite irradiance APIs.
5. **SCADA Integration Gateway**: DNP3 / IEC 60870-5-104 / CSV bulk historians.

Each adapter inherits from the unified `BaseProtocolAdapter` interface, normalizing raw industrial protocol packets into canonical `TelemetryObservation` records.

---

## 2. Modbus TCP & RTU Adapter

- **Target Assets**: Solar PV Inverters (SMA, Sungrow), Janitza Power Meters, Kipp & Zonen Pyranometers.
- **Physical Transport**: RS-485 2-wire serial (RTU) and Ethernet TCP/IP on Port `502`.
- **Production Driver**: `pymodbus` (Python) / `libmodbus` (C/C++).
- **Register Configuration Schema**:
  ```json
  {
    "adapter_type": "MODBUS_TCP",
    "host": "192.168.1.101",
    "port": 502,
    "slave_id": 1,
    "polling_interval_sec": 1,
    "register_map": [
      {
        "register_type": "HOLDING_REGISTER",
        "address": 40001,
        "data_type": "UINT16",
        "word_order": "BIG_ENDIAN",
        "byte_order": "BIG_ENDIAN",
        "scale_factor": 0.1,
        "metric": "power_active_kw",
        "unit": "kW"
      },
      {
        "register_type": "INPUT_REGISTER",
        "address": 30025,
        "data_type": "FLOAT32",
        "word_order": "LITTLE_ENDIAN",
        "byte_order": "BIG_ENDIAN",
        "scale_factor": 1.0,
        "metric": "temp_heatsink_c",
        "unit": "degC"
      }
    ]
  }
  ```
- **Byte Parsing Logic**:
  - `UINT16`: $V = R_0 \times \text{scale\_factor}$
  - `INT16`: Two's complement conversion of $R_0 \times \text{scale\_factor}$
  - `FLOAT32`: IEEE 754 32-bit floating point decoded across two contiguous 16-bit registers:
    $$B = (R_0 \ll 16) \lor R_1 \quad (\text{or } (R_1 \ll 16) \lor R_0 \text{ if little-endian})$$

---

## 3. OPC UA Adapter (IEC 62541)

- **Target Assets**: Wind Turbines (Vestas, GE, Siemens Gamesa), Substation Bay Controllers.
- **Physical Transport**: Binary TCP (`opc.tcp://<host>:4840`).
- **Production Driver**: `asyncua` (Python) / Open62541 (C/C++).
- **NodeId Mapping Schema**:
  ```json
  {
    "adapter_type": "OPC_UA",
    "endpoint_url": "opc.tcp://10.20.0.15:4840",
    "security_policy": "Basic256Sha256",
    "security_mode": "SignAndEncrypt",
    "client_certificate_path": "/etc/reamp/certs/opcua_client.der",
    "client_private_key_path": "/etc/reamp/certs/opcua_client_key.pem",
    "nodes": [
      {
        "node_id": "ns=2;s=Turbine.Nacelle.WindSpeed",
        "metric": "wind_speed_ms",
        "unit": "m/s",
        "sampling_interval_ms": 1000,
        "deadband_absolute": 0.05
      },
      {
        "node_id": "ns=2;s=Turbine.Gearbox.BearingVibrationRMS",
        "metric": "vibration_velocity_rms_mms",
        "unit": "mm/s",
        "sampling_interval_ms": 500,
        "deadband_absolute": 0.01
      }
    ]
  }
  ```
- **Operational Pattern**: Uses OPC UA Server Monitored Items with DataChange filter callbacks to push values asynchronously, minimizing network polling overhead.

---

## 4. MQTT Protocol Adapter

- **Target Assets**: Distributed smart string monitors, solar trackers, edge IoT micro-sensors.
- **Physical Transport**: TCP over TLS 1.3 on Port `8883`.
- **Production Driver**: `paho-mqtt` (Python) / Mosquitto client.
- **Topic Subscription Taxonomy**:
  ```text
  Topic: reamp/field/{site_id}/{device_type}/{device_id}/telemetry
  ```
- **Payload Schema**:
  ```json
  {
    "timestamp": "2026-09-11T12:00:00Z",
    "device_id": "TRK-ZONE-04",
    "metrics": {
      "tracker_tilt_angle_deg": 32.4,
      "motor_current_a": 1.85,
      "wind_stow_active": false
    }
  }
  ```
- **QoS & Retention**:
  - Subscribe QoS: **QoS 1** (At least once).
  - Session Persistence: Clean Session = False, Client ID = `reamp-edge-{site_code}`.

---

## 5. REST HTTP/S Client Adapter

- **Target Assets**: On-site meteorological weather stations (Vaisala, Campbell Scientific), inverter web interfaces, cloud satellite irradiance feeds.
- **Physical Transport**: HTTP 1.1 / HTTP 2 over TLS 1.3 on Port `443`.
- **Production Driver**: Python standard library `urllib` / `requests`.
- **Configuration Schema**:
  ```json
  {
    "adapter_type": "REST_POLL",
    "endpoint_url": "https://192.168.1.50/api/v1/weather/current",
    "method": "GET",
    "headers": {
      "Authorization": "Bearer ${WEATHER_API_KEY}"
    },
    "polling_interval_sec": 10,
    "response_json_path_mappings": {
      "irradiance_poa_wm2": "$.sensors.poa_pyranometer.irradiance",
      "temp_ambient_c": "$.sensors.ambient_temp.degrees_c",
      "wind_speed_ms": "$.sensors.anemometer.speed_ms"
    }
  }
  ```

---

## 6. SCADA Gateway & Historian Adapter

- **Target Assets**: Existing enterprise SCADA historians (OSIsoft PI, Ignition, GE Vernova).
- **Supported Integration Patterns**:
  1. **DNP3 / IEC 60870-5-104 Outstation Client**: Edge connects as a master client to local SCADA RTU outstations.
  2. **Automated CSV / Parquet File Watcher**: Edge agent monitors an isolated inbound directory (`/var/spool/reamp/scada_drops/`), automatically parsing periodic minute-rollup dumps exported by legacy SCADA servers.
