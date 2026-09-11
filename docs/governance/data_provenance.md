# REAMP Data Provenance Graph and Lineage Model

## 1. Overview & Lineage Architecture

Data provenance tracks the complete history, transformations, and custody transfers of data throughout its operational lifecycle.

In renewable energy systems, an algorithmic failure or wrong maintenance decision must be auditable backwards to the originating physical sensor measurements, intermediate data cleaning stages, and algorithm versions.

REAMP implements an immutable **Directed Acyclic Graph (DAG)** of provenance nodes:

```mermaid
flowchart TD
    S1["Raw Pyranometer Telemetry\n(Sensor-01, Checksum: A1)"] --> P1["Weather Normalization (IEC 61724-1)\n(Node-01, Checksum: B2)"]
    S2["Raw Inverter Modbus Telemetry\n(Inverter-01, Checksum: A2)"] --> P2["Physical Residual Engine\n(Node-02, Checksum: B3)"]

    P1 --> A1["Multi-Level Anomaly Detector\n(Node-03, Checksum: C1)"]
    P2 --> A1

    A1 --> R1["Weibull Degradation Engine\n(Node-04, Checksum: D1)"]
    R1 --> DEC["AI Decision Record\n(AIDEC-2026-0042)"]
    
    DEC --> HITL["Human Approval Gate\n(Lead Eng. Sarah Chen)"]
    HITL --> WO["CMMS Work Order\n(WO-2026-0042)"]
```

---

## 2. Provenance Node Schema (`DataProvenanceNode`)

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `node_id` | `str` | Unique node identifier (`PROV-2026-0088`). |
| `data_type` | `str` | Type of data (`RAW_TELEMETRY`, `NORMALIZED_RESIDUAL`, `ANOMALY_EVENT`, `AI_RECOMMENDATION`). |
| `source_id` | `str` | Originating asset, edge gateway, or algorithmic module ID. |
| `timestamp` | `str` | ISO 8601 UTC timestamp of creation. |
| `payload_checksum` | `str` | SHA-256 cryptographic digest of data content. |
| `parent_node_ids` | `List[str]` | Directed links to immediate ancestor provenance nodes. |
| `transformation_step`| `str` | Narrative description of mathematical or logical transformation applied. |

---

## 3. Bidirectional Provenance Traversal

The provenance engine supports two critical operational investigations:
1. **Backward Lineage Traversal (Root Cause & Audit)**:
   - Starting from a final `WorkOrder` or `AIDecisionRecord`, traverse upstream to identify the exact raw sensor telemetry and model versions that justified the intervention.
2. **Forward Impact Analysis (Sensor Fault Blast Radius)**:
   - When a sensor is discovered to have been decalibrated or faulty over a 3-day window, traverse downstream to identify all anomaly detections, risk profiles, and work orders corrupted by the bad data.
