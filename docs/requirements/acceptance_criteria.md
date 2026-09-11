# REAMP — MVP Scope Boundary & Acceptance Criteria Matrix

**Document Identifier**: `REAMP-REQ-AC-01`  
**Phase**: Phase 1 — Framework Vision and Requirements  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. MVP Boundary Definition

To prevent scope creep while delivering a production-grade framework, REAMP explicitly demarcates capabilities into four lifecycle buckets:

```text
┌─────────────────────────────────────────────────────────────────┐
│                      REAMP Phase Roadmap                        │
└─────────────────────────────────────────────────────────────────┘
  Phase 1–15: Core MVP Boundary (Framework + Intelligence + UI)
  Phase 16:   Experimental Validation & Benchmarking
  Phase 17:   High-Scale Resilience & Distributed Edge
  Phase 18:   Multi-Technology Adaptive Framework
```

### 1.1 In-Scope MVP Boundary (Phase 1 through Phase 15)
- **Asset Hierarchy & Domain**: 8-level canonical model (`Organisation → ... → Sensor`) with Solar PV, Wind, and BESS domain adapters.
- **Data Ingestion & Quality**: Modbus/OPC UA/MQTT ingestion, store-and-forward buffering, quality metadata tags (`VALID`, `INVALID`, etc.).
- **Asset Health & Performance**: Asset Health Index ($AHI$), temperature-compensated $PR_{STC}$, Wind power curve $C_p$, BESS $SoH$.
- **Anomaly & Diagnostics**: Physics-informed multi-variate anomaly detection, fault-tree root cause diagnostics, $RUL$ estimates.
- **Maintenance & Risk**: Draft CMMS work order generation, PPA revenue loss calculation, technical risk scoring.
- **Digital Twin & XAI**: Real-time state machine twin, SHAP feature importance explanations, Human-in-the-loop approval task queue.
- **Bootstrap 5.3 Light UI**: Complete responsive frontend dashboard built in Bootstrap 5.3 in Light Theme default.

### 1.2 Phase 16–18 Advanced Scope
- Automated cross-site synthetic experiment generators (Phase 16).
- Autonomous self-healing distributed edge mesh networks (Phase 17).
- Zero-shot domain adaptation ML models across uncalibrated sensors (Phase 18).

### 1.3 Out-of-Scope (Explicit Exclusion)
- Automated safety-critical grid tripping or hardware relay control.
- Live energy spot market trading bids.
- Replacement of low-level SCADA PLC firmware.

---

## 2. Acceptance Criteria Matrix

### 2.1 Functional Acceptance Criteria (`AC-FR`)

| Requirement ID | Acceptance Criterion ID | Verifiable Acceptance Criteria | Verification Method |
| :--- | :--- | :--- | :--- |
| `FR-AST-001` | `AC-FR-AST-001` | Domain model validates and persists all 8 levels of asset hierarchy (`Organisation` down to `Sensor`) without schema violation. | Unit & DB Integration Test |
| `FR-AST-002` | `AC-FR-AST-002` | System instantiates Solar PV, Wind, and BESS asset instances using technology adapters without changing core entities. | Integration Test |
| `FR-ING-001` | `AC-FR-ING-001` | Gateway successfully ingests sample Modbus TCP, OPC UA, and MQTT streams into time-series DB. | End-to-End API Test |
| `FR-ING-002` | `AC-FR-ING-002` | Edge agent buffers 10,000 records during simulated WAN outage and backfills Cloud DB upon reconnection with 0 lost payloads. | Edge Failure Simulation |
| `FR-DQ-001` | `AC-FR-DQ-001` | 100% of stored telemetry records contain `quality`, `confidence_score`, `timestamp`, `source`, and `sensor_id` fields. | Schema Inspection |
| `FR-DQ-002` | `AC-FR-DQ-002` | Automated screening flags out-of-range value ($> 1500 \text{ W/m}^2$ irradiance) with `INVALID` quality tag. | Automated Data Unit Test |
| `FR-HLT-001` | `AC-FR-HLT-001` | Health engine computes $AHI \in [0, 100]$ score matching theoretical degradation formula within $\pm 0.1\%$ margin. | Benchmark Mathematical Test |
| `FR-PRF-001` | `AC-FR-PRF-001` | Performance module computes IEC 61724-1 $PR_{STC}$ given irradiance, module temp, and AC power telemetry. | Calculation Verification Test |
| `FR-ANO-001` | `AC-FR-ANO-001` | Anomaly engine detects synthetic inverter current imbalance within $\le 3$ evaluation cycles ($F_1 \ge 0.90$). | ML Benchmark Experiment |
| `FR-MAIN-001`| `AC-FR-MAIN-001`| Engine predicts RUL hours for bearing degradation and generates draft CMMS work order when $RUL < 120\text{h}$. | Workflow Integration Test |
| `FR-RSK-001` | `AC-FR-RSK-001` | Revenue loss engine converts $100\text{ kWh}$ lost generation at $\$0.10/\text{kWh}$ PPA rate into exact $\$10.00$ loss. | Unit Test |
| `FR-TWN-001` | `AC-FR-TWN-001` | Digital Twin state machine transitions from `RUNNING` to `FAULT` upon receiving critical fault payload within $\le 100\text{ms}$. | State Transition Test |
| `FR-XAI-001` | `AC-FR-XAI-001` | Anomaly alert API returns ranked SHAP feature list explaining top 3 contributing sensors. | API Schema Test |
| `FR-XAI-002` | `AC-FR-XAI-002` | Automated recommendation remains pending in approval queue until human user submits `APPROVE` request. | Workflow End-to-End Test |
| `FR-UI-001`  | `AC-FR-UI-001`  | All UI screens build strictly with Bootstrap 5.3.x in LIGHT theme without dark SCADA override. | UI Inspection & Accessibility Audit |

---

### 2.2 Non-Functional Acceptance Criteria (`AC-NFR`)

| Requirement ID | Acceptance Criterion ID | Verifiable Acceptance Criteria | Verification Method |
| :--- | :--- | :--- | :--- |
| `NFR-AVL-001` | `AC-NFR-AVL-001` | Ingestion & Core API services demonstrate $\ge 99.9\%$ uptime over automated 72-hour load test. | Soak / Load Testing |
| `NFR-SCL-001` | `AC-NFR-SCL-001` | Cluster ingests 100,000 events/sec while maintaining average CPU utilization $\le 75\%$. | JMeter / Locust Performance Test |
| `NFR-PRF-001` | `AC-NFR-PRF-001` | End-to-end ingestion latency (sensor to DB commit) $95\text{th percentile} \le 500\text{ ms}$. | APM Tracing / Metrics |
| `NFR-SEC-001` | `AC-NFR-SEC-001` | TLS 1.3 enforced on all HTTP/gRPC endpoints; SSL Labs test rating Grade A+. | Security Audit Scanner |
| `NFR-SEC-002` | `AC-NFR-SEC-002` | API requests from Tenant A attempting to access Tenant B asset ID return HTTP 403 Forbidden. | Penetration Unit Test |
| `NFR-MNT-002` | `AC-NFR-MNT-002` | Automated test suite achieves $\ge 80\%$ line coverage with 0 mypy strict type errors. | Coverage & Lint Script |
| `NFR-PRT-002` | `AC-NFR-PRT-002` | Edge container runs on ARM64 Raspberry Pi 4 with memory consumption $\le 256\text{ MB}$. | Hardware Execution Audit |
