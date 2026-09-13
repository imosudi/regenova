# REGENOVA FlowField — Integration Audit (F0)

## 1. Upstream & Downstream Integration Surfaces

```text
    ┌──────────────────────┐
    │     IoT Devices /    │
    │  Gateways / SCADA    │
    └──────────┬───────────┘
               │  MQTT / HTTP / Modbus / OPC-UA
               ↓
    ┌──────────────────────┐
    │  REGENOVA FlowField  │
    └──────────┬───────────┘
               │
      ┌────────┼────────────────────────┬────────────────────────┐
      │        │                        │                        │
      ↓        ↓                        ↓                        ↓
TimescaleDB  TwinField API          REGENOVA API            Backoffice API
Telemetry    (twinfield.            (api.regenova.          (backoffice.
Store        regenova.cloud)        cloud)                  regenova.cloud)
```

---

## 2. TwinField Integration Surface (`https://twinfield.regenova.cloud/`)

- **Status**: Live, verified, version 0.3.0.
- **Protocol**: HTTP/1.1 REST + WebSockets (`ws://127.0.0.1:9000/`).
- **Telemetry Schema in TwinField**:
  - `TelemetryReading` (`app/domain/telemetry.py`):
    - `twin_id`: str
    - `component_id`: Optional[str]
    - `sensor_id`: Optional[str]
    - `metric`: str
    - `value`: Union[float, int, str, bool]
    - `unit`: Optional[str]
    - `quality`: DataQuality Enum (`VALID`, `STALE`, `MISSING`, `INVALID`, `ESTIMATED`, `SIMULATED`, `DUPLICATE`, `OUT_OF_ORDER`, `UNKNOWN`)
    - `event_time`: datetime (UTC)
    - `ingestion_time`: datetime (UTC)
    - `confidence`: float (0.0 to 1.0)
    - `provenance`: Optional[Provenance]
- **API Endpoint**:
  - Listed in root discovery: `POST /api/v1/twins/{twin_id}/telemetry`
  - FlowField will dispatch validated, normalised telemetry packets to TwinField via this interface.

---

## 3. REGENOVA Platform Integration Surface (`https://api.regenova.cloud/`)

- **Status**: Live, verified WSGI daemon API.
- **Protocol**: HTTPS REST.
- **Telemetry Endpoint**: `POST /api/telemetry/inject`
  - Accepts telemetry packets for specific asset IDs or standard scenarios (`blower_fault`, `soiling_derate`, `bess_discharge`, `nominal`).
  - Feeds into REAMP 10-stage processing pipeline and persists to `telemetry_observations`.

---

## 4. Backoffice Integration Surface (`https://backoffice.regenova.cloud/`)

- **Status**: Live, operational super-admin console.
- **Interface**: Consumes metadata from PostgreSQL and monitors tenant/facility/device state.
- **Interaction Boundary**: Backoffice configures assets, tenant partitions, and credentials. FlowField will query authoritative asset definitions and telemetry thresholds, but Backoffice will not directly manipulate Node-RED internals.

---

## 5. MQTT Broker Integration Surface

- **VHost**: `mosquitto.regenova.cloud` (DNS `130.61.63.86`, SSL certificate configured).
- **Current Broker State**: Mosquitto binary is not currently installed on the host.
- **Topic Hierarchy Target**:
  - Telemetry: `regenova/{tenant_id}/{site_id}/{asset_id}/telemetry`
  - Events: `regenova/{tenant_id}/{site_id}/{asset_id}/events/{event_type}`
  - Commands: `regenova/{tenant_id}/{site_id}/{asset_id}/commands/{command_id}`

---

## 6. Integration Verdict
- **Status**: `READY` for Phase F5 (MQTT) and F7 (TwinField Integration). Contracts are well-aligned across the codebase.
