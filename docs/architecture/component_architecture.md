# REAMP - Component Architecture Specification

**Document Identifier**: `REAMP-ARC-02`  
**Phase**: Phase 3 - Reference Architecture  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Modular Monolith Component Architecture

REAMP organizes core business capabilities into 10 decoupled Python/C++ software modules. Each module maintains strict encapsulation, interacting with adjacent modules via typed domain interfaces and events.

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                           REAMP Application Host                          │
├─────────────────┬─────────────────┬──────────────────┬────────────────────┤
│ Ingestion Module│ Data Quality Mod│ Health Engine Mod│ Performance Module │
├─────────────────┼─────────────────┼──────────────────┼────────────────────┤
│ Anomaly Module  │ Predictive CMMS │ Financial Module │ Digital Twin Mod   │
├─────────────────┴─────────────────┴──────────────────┴────────────────────┤
│                XAI & Human-in-the-Loop Governance Module                  │
├───────────────────────────────────────────────────────────────────────────┤
│                Bootstrap 5.3 Light Presentation Client Module             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Specifications & Requirement Mappings

### 2.1 Ingestion & Telemetry Component (`reamp.ingestion`)
- **Primary Function**: Ingests Modbus, OPC UA, MQTT, and gRPC telemetry streams; attaches temporal provenance; routes payloads.
- **Inputs**: Raw protocol frames / JSON streams.
- **Outputs**: Enriched `TelemetryRecord` objects.
- **Mapped Requirements**: `FR-ING-001`, `FR-ING-002`, `FR-ING-003`.

### 2.2 Data Quality & Provenance Component (`reamp.data_quality`)
- **Primary Function**: Executes physical range checks, static freeze detection, timestamp sequence checks, and sensor drift calibration checks.
- **Inputs**: Raw `TelemetryRecord`.
- **Outputs**: Quality-tagged `EnrichedTelemetryRecord` (`VALID`, `INVALID`, `MISSING`, `STALE`, `UNCERTAIN`).
- **Mapped Requirements**: `FR-DQ-001`, `FR-DQ-002`, `FR-DQ-003`.

### 2.3 Asset Health Component (`reamp.health`)
- **Primary Function**: Computes normalized Asset Health Index ($AHI \in [0, 100]$) for assets and energy systems.
- **Inputs**: Enriched telemetry time-series, operating temperature, stress hours, maintenance logs.
- **Outputs**: `AssetHealthIndexScore` object.
- **Mapped Requirements**: `FR-HLT-001`, `FR-HLT-002`.

### 2.4 Performance Intelligence Component (`reamp.performance`)
- **Primary Function**: Calculates IEC 61724-1 temperature-compensated $PR_{STC}$ for Solar PV, Wind power curve efficiency $C_p$, and BESS Round-Trip Efficiency ($RTE$).
- **Inputs**: Irradiance, ambient/module temp, nacelle wind speed, cell charge/discharge power.
- **Outputs**: `PerformanceMetrics` object.
- **Mapped Requirements**: `FR-PRF-001`, `FR-PRF-002`, `FR-PRF-003`.

### 2.5 Anomaly Detection & Diagnostics Component (`reamp.anomaly`)
- **Primary Function**: Executes Isolation Forest and physics-guided autoencoders to detect multi-variate operational anomalies and perform fault-tree root cause diagnostics.
- **Inputs**: Multi-sensor time-series vector.
- **Outputs**: `AnomalyAlert` object with probability distribution over probable root causes.
- **Mapped Requirements**: `FR-ANO-001`, `FR-ANO-002`.

### 2.6 Predictive Maintenance & CMMS Component (`reamp.cmms`)
- **Primary Function**: Predicts component Remaining Useful Life ($RUL$) and automatically drafts CMMS work orders (`WO-xxx`).
- **Inputs**: Asset health trends, vibration spectrums, component cycle counts.
- **Outputs**: `DraftWorkOrder` object.
- **Mapped Requirements**: `FR-MAIN-001`, `FR-MAIN-002`.

### 2.7 Risk & Financial Intelligence Component (`reamp.financial`)
- **Primary Function**: Translates lost energy generation (kWh) into monetary financial loss ($/€/£) using PPA tariffs and computes risk-adjusted asset depreciation.
- **Inputs**: Energy loss kWh, PPA tariff schedules, asset health index.
- **Outputs**: `FinancialLossReport` object.
- **Mapped Requirements**: `FR-RSK-001`, `FR-RSK-002`.

### 2.8 Digital Twin Component (`reamp.digital_twin`)
- **Primary Function**: Maintains real-time in-memory state machines for every asset and executes "What-If" historical playback simulations.
- **Inputs**: Real-time telemetry events / Historical state logs.
- **Outputs**: `DigitalTwinState` snapshot.
- **Mapped Requirements**: `FR-TWN-001`, `FR-TWN-002`.

### 2.9 XAI & Governance Component (`reamp.governance`)
- **Primary Function**: Computes SHAP feature importance explanations for AI predictions and manages the 2-step Human-in-the-Loop decision approval queue.
- **Inputs**: ML model predictions, feature vectors, user approval requests.
- **Outputs**: `XAIExplanation` object & `AuditLogEntry`.
- **Mapped Requirements**: `FR-XAI-001`, `FR-XAI-002`, `FR-SEC-002`.

### 2.10 Presentation UI Component (`reamp.presentation`)
- **Primary Function**: Renders Bootstrap 5.3 Light Theme dashboards, real-time alert feeds, and field mobile views.
- **Inputs**: REST / WebSocket APIs.
- **Outputs**: Responsive HTML5 / Bootstrap 5.3 UI DOM.
- **Mapped Requirements**: `FR-UI-001`, `FR-UI-002`, `FR-UI-003`.

---

## 3. Non-Functional Requirements (NFR) Traceability Matrix

Every quantitative quality attribute defined in `docs/requirements/non_functional_requirements.md` is assigned to concrete architectural components and runtime policies:

| NFR Identifier | Name | Target Metric | Responsible Component / Mechanism |
| :--- | :--- | :--- | :--- |
| `NFR-AVL-001` | Cloud Availability | $\ge 99.9\%$ uptime | Kubernetes Multi-AZ Replica Deployments, Health Probes |
| `NFR-AVL-002` | Edge Continuity | $\ge 99.99\%$ local logging | `reamp/edge-agent` + SQLite Store-and-Forward Buffer |
| `NFR-SCL-001` | Throughput Scaling | Up to 100,000 events/sec | `reamp/telemetry-ingestion` HPA Horizontal Scaling |
| `NFR-SCL-002` | Asset Portfolio Scaling | 10M channels / 500 plants | TimescaleDB Hypertables + Redis State Caching |
| `NFR-PRF-001` | Ingestion Latency | $\le 500\text{ ms}$ (95th pct) | Async FastAPI Stream Ingestion + Redis Pipeline Batching |
| `NFR-PRF-002` | Query Latency | $\le 200\text{ ms}$ real-time state | Redis In-Memory State Cache + TimescaleDB Continuous Aggregates |
| `NFR-PRF-003` | Alert Dispatch Latency | $\le 2.0\text{ s}$ anomaly alert | Redis Pub/Sub + WebSocket Dispatch Gateway |
| `NFR-SEC-001` | Encryption Standard | TLS 1.3 in transit, AES-256 at rest | Ingress TLS Termination + PostgreSQL Transparent Data Encryption |
| `NFR-SEC-002` | Multi-Tenant Isolation | 0 cross-tenant data leakage | PostgreSQL Row Level Security (RLS) + Tenant-scoped JWT claims |
| `NFR-SEC-003` | Secret Management | 0 plaintext secrets in code | Kubernetes Secrets / HashiCorp Vault + `.env` injection |
| `NFR-MNT-001` | Clean Architecture | Decoupled domain core | Hexagonal Ports & Adapters (`reamp.core` vs drivers) |
| `NFR-MNT-002` | Test Coverage | $\ge 80\%$ line coverage, strict typing | Python `pytest` + `mypy --strict` compliance |
| `NFR-INT-001` | Open API Standards | OpenAPI 3.0, ProtoBuf3, OpenTelemetry | FastAPI OpenAPI specs + OpenTelemetry SDK exporters |
| `NFR-INT-002` | CMMS & ERP Standards | REST Webhooks, OAuth2 | `reamp.cmms` Outbound Integration Adapter |
| `NFR-OBS-001` | Structured JSON Logs | 100% JSON logs with correlation IDs | Python `structlog` + W3C `traceparent` context injector |
| `NFR-OBS-002` | Health Diagnostics | `/healthz`, `/readyz` $\le 50\text{ ms}$ | FastAPI Native Probe Handlers on all cloud containers |
| `NFR-PRT-001` | Container Execution | 100% OCI Container Compliant | Multi-stage Dockerfiles (`python:3.11-slim`, Alpine) |
| `NFR-PRT-002` | Hardware Agnostic Edge | x86_64 & ARM64, $\le 256\text{ MB RAM}$ | Multi-arch container builds (`linux/amd64`, `linux/arm64`) |
| `NFR-RES-001` | Network Degradation | Zero data dropout on WAN loss | 72h SQLite Edge Buffer + Exponential Backoff Reconnection |
| `NFR-RES-002` | Database Recovery | $\text{RTO} \le 30\text{ s}$, $\text{RPO} \le 1.0\text{ s}$ | PostgreSQL Streaming Replication + WAL Archiving |

---

## 4. Edge-to-Cloud Wire Protocol Specification

To resolve protocol ambiguities, REAMP mandates the following wire standards:

1. **Primary Transport Protocol (Batch Ingestion)**:
   - **Wire Format**: HTTPS POST over **TLS 1.3 with Mutual Authentication (mTLS)** on port `8443`.
   - **Payload Format**: Compressed JSON or Protocol Buffers (`Content-Encoding: br` / `gzip`).
   - **Path**: `POST /api/v1/telemetry/batch`
   - **Header Authentication**: Client X.509 certificate verified against REAMP Device CA + `X-Device-UUID` header.
2. **Secondary Transport Protocol (Constrained Continuous Streams)**:
   - **Wire Format**: **MQTT over TLS 1.3** on port `8883` using QoS 1 (At least once delivery).
   - **Topic Hierarchy**: `reamp/{tenant_id}/{site_id}/{energy_system_id}/{asset_id}/telemetry`
3. **Internal Cloud Asynchronous Event Channels**:
   - Communication between `reamp.ingestion`, `reamp.data_quality`, `reamp.health`, and `reamp.anomaly` executes over **Redis Streams**:
     - `stream:telemetry:raw`: Stream of ingested raw batches.
     - `stream:telemetry:validated`: Stream of quality-enriched telemetry.
     - `stream:anomaly:detected`: Stream of confirmed operational anomalies.
     - `stream:workorder:drafted`: Stream of generated CMMS work orders awaiting HITL approval.

---

## 5. Observability & Tracing Architecture

Each component implements cross-cutting observability primitives:
- **Trace Context Propagation**: Every ingestion request receives or propagates W3C Trace Context headers (`traceparent: 00-{trace_id}-{span_id}-01`).
- **Telemetry Correlation Context**: Log records and spans automatically inject `{ "trace_id": "...", "tenant_id": "...", "asset_id": "...", "sensor_id": "..." }`.
- **Metrics Exposure**: Ingestion, health calculation, and queue lag metrics are exposed on `/metrics` in Prometheus format on port `9090`.
- **Liveness and Readiness Endpoints**: Every container exposes `/healthz` and `/readyz` for Kubernetes orchestrator monitoring.

