# REAMP — Canonical Telemetry Model Specification

**Document Identifier**: `REAMP-DAT-02`  
**Phase**: Phase 4 — Data Architecture and Telemetry Model  
**Status**: Approved / Canonical Design  
**Last Updated**: 2026-09-11  

---

## 1. Overview & Architectural Principles

In compliance with `AGENTS.md` Rule 7 ("The framework must distinguish: value, timestamp, source, quality, confidence, availability, communication status"), the REAMP Telemetry Model defines a standardized, strongly typed telemetry observation schema.

Every physical reading ingested into REAMP—whether from a central solar inverter, wind turbine vibration accelerometer, BESS battery cell, or pyranometer—is normalized into this canonical format before downstream persistence or analytical consumption.

---

## 2. Mandatory Telemetry Observation Attributes

Every observation record encapsulates **10 mandatory attributes**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      Canonical Telemetry Observation                   │
├──────────────────────┬────────────────────────┬────────────────────────┤
│ 1. asset_id (UUID)   │ 2. sensor_id (UUID)    │ 3. metric (String)     │
├──────────────────────┼────────────────────────┼────────────────────────┤
│ 4. value (Float64)   │ 5. unit (String)       │ 6. timestamp (UTC ISO) │
├──────────────────────┼────────────────────────┼────────────────────────┤
│ 7. source (Enum)     │ 8. quality (Enum)      │ 9. confidence (0.0-1.0)│
├──────────────────────┴────────────────────────┴────────────────────────┤
│ 10. communication_status (Enum: ONLINE | DEGRADED | OFFLINE | BUFFERED) │
└────────────────────────────────────────────────────────────────────────┘
```

### Detailed Attribute Definitions:

| # | Attribute | Type | Nullable | Description & Domain Values |
| :- | :--- | :--- | :-: | :--- |
| 1 | `asset_id` | UUID | No | Canonical UUID of the parent Asset (`Level 6`). |
| 2 | `sensor_id` | UUID | No | Canonical UUID of the generating Sensor (`Level 8`). |
| 3 | `metric` | VARCHAR(64) | No | Standardized metric identifier (e.g., `power_active_kw`, `temp_cell_max_c`, `irradiance_poa_wm2`). |
| 4 | `value` | DOUBLE PRECISION | No | Physical measured reading in canonical units. |
| 5 | `unit` | VARCHAR(32) | No | Canonical engineering unit (e.g., `kW`, `degC`, `W/m2`, `m/s`, `V`, `A`). |
| 6 | `timestamp` | TIMESTAMPTZ | No | Microsecond-precision physical sampling timestamp in UTC (`YYYY-MM-DDTHH:MM:SS.ffffffZ`). |
| 7 | `source` | VARCHAR(32) | No | Data origin: `SCADA`, `INVERTER_MODBUS`, `BMS_CAN`, `MET_MAST`, `EDGE_ESTIMATED`. |
| 8 | `quality` | VARCHAR(16) | No | Quality classification: `VALID`, `INVALID`, `MISSING`, `STALE`, `UNCERTAIN`. |
| 9 | `confidence` | REAL | No | Calculated reliability score between `0.00` (zero confidence) and `1.00` (full confidence). |
| 10 | `communication_status` | VARCHAR(16) | No | Link state: `ONLINE`, `DEGRADED` (high packet drop), `OFFLINE`, `BUFFERED` (store-and-forward backfill). |

---

## 3. Protocol Buffers (Proto3) Wire Definition

To support high-throughput network transport (`NFR-INT-001`, `FR-ING-003`), REAMP defines the canonical observation format in ProtoBuf3:

```protobuf
syntax = "proto3";

package reamp.telemetry.v1;

import "google/protobuf/timestamp.proto";

enum QualityFlag {
  QUALITY_UNSPECIFIED = 0;
  VALID = 1;
  INVALID = 2;
  MISSING = 3;
  STALE = 4;
  UNCERTAIN = 5;
}

enum CommunicationStatus {
  STATUS_UNSPECIFIED = 0;
  ONLINE = 1;
  DEGRADED = 2;
  OFFLINE = 3;
  BUFFERED = 4;
}

message TelemetryObservation {
  string tenant_id = 1;
  string asset_id = 2;
  string sensor_id = 3;
  string metric = 4;
  double value = 5;
  string unit = 6;
  google.protobuf.Timestamp timestamp = 7;
  string source = 8;
  QualityFlag quality = 9;
  float confidence = 10;
  CommunicationStatus communication_status = 11;
  map<string, string> metadata = 12;
}

message TelemetryBatch {
  string device_uuid = 1;
  google.protobuf.Timestamp sent_at = 2;
  repeated TelemetryObservation observations = 3;
}
```

---

## 4. JSON Wire Format & Example Payloads

For HTTP REST batch ingestion (`POST /api/v1/telemetry/batch`), payloads are transmitted as JSON arrays:

### 4.1 Solar PV Inverter Observation Example
```json
{
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "asset_id": "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380b22",
  "sensor_id": "c2eebc99-9c0b-4ef8-bb6d-6bb9bd380c33",
  "metric": "power_active_kw",
  "value": 2450.8,
  "unit": "kW",
  "timestamp": "2026-09-11T12:00:00.000000Z",
  "source": "INVERTER_MODBUS",
  "quality": "VALID",
  "confidence": 1.0,
  "communication_status": "ONLINE"
}
```

### 4.2 Wind Turbine Gearbox Vibration Example
```json
{
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "asset_id": "d3eebc99-9c0b-4ef8-bb6d-6bb9bd380d44",
  "sensor_id": "e4eebc99-9c0b-4ef8-bb6d-6bb9bd380e55",
  "metric": "vibration_velocity_rms_mms",
  "value": 3.42,
  "unit": "mm/s",
  "timestamp": "2026-09-11T12:00:00.000000Z",
  "source": "SCADA",
  "quality": "VALID",
  "confidence": 0.98,
  "communication_status": "ONLINE"
}
```

### 4.3 BESS Battery Rack State of Charge Example
```json
{
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "asset_id": "f5eebc99-9c0b-4ef8-bb6d-6bb9bd380f66",
  "sensor_id": "a6eebc99-9c0b-4ef8-bb6d-6bb9bd380a77",
  "metric": "state_of_charge_pct",
  "value": 84.6,
  "unit": "%",
  "timestamp": "2026-09-11T12:00:00.000000Z",
  "source": "BMS_CAN",
  "quality": "VALID",
  "confidence": 0.95,
  "communication_status": "ONLINE"
}
```

---

## 5. Ingestion Batching & Compression Rules

1. **Batch Size Envelopes**:
   - Nominal batch size: `1,000 observations / batch`.
   - Maximum flush interval: `500 milliseconds`.
2. **Payload Compression**:
   - HTTP clients MUST transmit batches using `Content-Encoding: br` (Brotli) or `gzip`.
   - Compressing 1,000 JSON observations reduces payload size from $\approx 180\text{ KB}$ to $< 22\text{ KB}$ ($> 85\%$ bandwidth savings over cellular links).
3. **Idempotency & Deduplication**:
   - Ingestion endpoints enforce composite uniqueness over `(tenant_id, asset_id, metric, timestamp)`.
   - If an edge gateway re-transmits a previously acknowledged observation during store-and-forward backfill, the database executes an idempotent `ON CONFLICT (tenant_id, asset_id, metric, timestamp) DO UPDATE SET quality = EXCLUDED.quality, confidence = EXCLUDED.confidence`.
