# REAMP — Functional Requirements Specification

**Document Identifier**: `REAMP-REQ-FR-01`  
**Phase**: Phase 1 — Framework Vision and Requirements  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Overview & Requirements Identification Scheme

Every functional requirement in REAMP is assigned a unique, stable identifier formatted as:

```text
FR-[CATEGORY]-[NUMBER]
```

Categories:
- `AST`: Asset Hierarchy & Domain Model
- `ING`: Ingestion, Edge & Connectivity
- `DQ`: Data Quality & Telemetry Provenance
- `HLT`: Asset Health & Condition Assessment
- `PRF`: Performance Intelligence & Degradation
- `ANO`: Anomaly Detection & Diagnostic AI
- `MAIN`: Predictive Maintenance & CMMS
- `RSK`: Risk & Financial Intelligence
- `TWN`: Digital Twin & Asset State
- `SEC`: Cybersecurity, Tenant & Governance
- `XAI`: Explainable AI & Human-in-the-Loop
- `UI`: Visual User Interface & Dashboards

---

## 2. Asset Hierarchy & Domain Model Requirements (`FR-AST`)

### `FR-AST-001`: Canonical 8-Level Asset Hierarchy Support
- **Description**: The system shall model all renewable energy infrastructure according to an 8-level hierarchy: `Organisation → Portfolio → Project → Site → Energy System → Asset → Component → Sensor`.
- **Target Phase**: Phase 2 (Domain Model)
- **Rationale**: Ensures uniform domain boundaries across all technology types.

### `FR-AST-002`: Heterogeneous Technology Schema Extensibility
- **Description**: The system shall provide technology-specific asset schema adapters for Solar PV, Wind Energy, BESS, and Hybrid microgrids without altering core domain entities.
- **Target Phase**: Phase 2 (Domain Model)
- **Rationale**: Prevents premature technology lock-in.

### `FR-AST-003`: Dynamic Asset Attribute & Metadata Registry
- **Description**: The system shall support runtime attachment of custom metadata, nameplate ratings, commissioning dates, GPS coordinates, and manufacturer specs to any asset entity.
- **Target Phase**: Phase 2 (Domain Model)

---

## 3. Ingestion, Edge & Connectivity Requirements (`FR-ING`)

### `FR-ING-001`: Multi-Protocol Telemetry Ingestion
- **Description**: The ingestion gateway shall accept telemetry over industrial protocols including Modbus TCP/RTU, OPC UA, MQTT, DNP3, and HTTP/gRPC.
- **Target Phase**: Phase 4 & Phase 5 (Data & Edge)

### `FR-ING-002`: Edge Store-and-Forward Buffering
- **Description**: Edge gateways shall locally buffer incoming time-series telemetry during network outages for up to 72 hours and automatically backfill the central cloud upon reconnection without data loss or duplicate creation.
- **Target Phase**: Phase 5 (Edge/Fog Integration)

### `FR-ING-003`: High-Frequency Telemetry Ingestion Scaling
- **Description**: The ingestion pipeline shall ingest up to 100,000 telemetry events per second per cluster with sub-second processing latency.
- **Target Phase**: Phase 4 & Phase 17 (Data & Scalability)

---

## 4. Data Quality & Telemetry Provenance Requirements (`FR-DQ`)

### `FR-DQ-001`: Telemetry Quality Metadata Enriched Schema
- **Description**: Every telemetry record ingested shall automatically attach metadata fields: `asset_id`, `sensor_id`, `metric`, `value`, `unit`, `timestamp`, `source`, `quality` (`VALID`, `INVALID`, `MISSING`, `STALE`, `UNCERTAIN`), `confidence_score` ($0.0–1.0$), and `communication_status`.
- **Target Phase**: Phase 4 (Data Architecture)

### `FR-DQ-002`: Automated Data Validation & Outlier Screening
- **Description**: Ingested data shall pass through physical range checks, freeze checks (static values over $N$ intervals), rate-of-change limits, and timestamp sequence checks.
- **Target Phase**: Phase 4 (Data Architecture)

### `FR-DQ-003`: Sensor Drift & Out-of-Calibration Alerting
- **Description**: The system shall continuously compare adjacent redundant sensors (e.g., dual pyranometers or inverter DC current sensors) to detect calibration drift exceeding $\pm 3\%$.
- **Target Phase**: Phase 4 & Phase 6 (Data & Health)

---

## 5. Asset Health & Condition Assessment Requirements (`FR-HLT`)

### `FR-HLT-001`: Composite Asset Health Index (AHI) Computation
- **Description**: The system shall calculate a normalized Asset Health Index ($AHI \in [0, 100]$) for every Asset and Energy System based on operating temperature, electrical stress, vibration, age, and maintenance history.
- **Target Phase**: Phase 6 (Asset Health Model)

### `FR-HLT-002`: Multi-Factor Thermal & Stress Degradation Modeling
- **Description**: The health engine shall compute thermal stress degradation for PV inverters, gearbox oil degradation for wind turbines, and cycle-based $SoH$ loss for BESS cells.
- **Target Phase**: Phase 6 (Asset Health Model)

---

## 6. Performance Intelligence & Yield Analysis Requirements (`FR-PRF`)

### `FR-PRF-001`: Temperature-Compensated Performance Ratio (PR) Calculation
- **Description**: For Solar PV assets, the system shall compute weather-adjusted and temperature-compensated Performance Ratio ($PR_{STC}$) according to IEC 61724-1 standards.
- **Target Phase**: Phase 7 (Performance Intelligence)

### `FR-PRF-002`: Wind Power Curve Efficiency Analysis ($C_p$)
- **Description**: For Wind assets, the system shall continuously map measured nacelle anemometer wind speed against active power output to detect power curve degradation ($C_p$).
- **Target Phase**: Phase 7 (Performance Intelligence)

### `FR-PRF-003`: BESS Round-Trip Efficiency (RTE) & SoC Estimation
- **Description**: The system shall track charge/discharge energy throughput to calculate BESS Round-Trip Efficiency ($RTE \%$) and detect capacity fading.
- **Target Phase**: Phase 7 (Performance Intelligence)

---

## 7. Anomaly Detection & Diagnostics Requirements (`FR-ANO`)

### `FR-ANO-001`: Multi-Variate Anomaly Detection Engine
- **Description**: The system shall execute statistical (z-score, isolation forest) and physics-informed ML algorithms to flag abnormal operational deviations across correlated telemetry channels.
- **Target Phase**: Phase 8 (Anomaly Detection)

### `FR-ANO-002`: Automated Fault Root Cause Diagnostics (RCA)
- **Description**: Upon detecting an anomaly, the diagnostic engine shall execute fault-tree analysis and pattern matching to identify the top 3 probable root causes with associated likelihood probabilities.
- **Target Phase**: Phase 8 (Anomaly Detection)

---

## 8. Predictive Maintenance & CMMS Requirements (`FR-MAIN`)

### `FR-MAIN-001`: Remaining Useful Life (RUL) Estimation
- **Description**: The system shall predict the Remaining Useful Life (RUL in operational hours or cycles) for critical components (e.g., wind turbine gearboxes, inverter capacitors, battery cells).
- **Target Phase**: Phase 9 (Predictive Maintenance)

### `FR-MAIN-002`: Automated Prescriptive Work Order Generation
- **Description**: The system shall automatically generate draft CMMS work orders containing recommended maintenance actions, required spare parts, required skill levels, and priority level when an asset health score falls below defined thresholds.
- **Target Phase**: Phase 10 (O&M / CMMS Integration)

---

## 9. Risk & Financial Intelligence Requirements (`FR-RSK`)

### `FR-RSK-001`: Real-Time Production Loss Financial Quantification
- **Description**: The system shall convert energy yield loss (kWh) into monetary financial loss ($/€/£) using real-time Power Purchase Agreement (PPA) tariffs or spot market prices.
- **Target Phase**: Phase 11 (Risk & Financial Intelligence)

### `FR-RSK-002`: Risk-Adjusted Asset Valuation & Depreciation Modeling
- **Description**: The system shall compute technical risk-adjusted asset valuation, incorporating accelerated degradation into financial balance sheet projections.
- **Target Phase**: Phase 11 (Risk & Financial Intelligence)

---

## 10. Digital Twin & Asset State Requirements (`FR-TWN`)

### `FR-TWN-001`: Real-Time State Machine Digital Twin
- **Description**: The system shall maintain an in-memory, real-time digital twin representation of every Asset reflecting operational state (`RUNNING`, `DERATED`, `FAULT`, `MAINTENANCE`, `OFFLINE`).
- **Target Phase**: Phase 12 (Digital Twin)

### `FR-TWN-002`: Historical State Playback & What-If Simulation
- **Description**: The digital twin engine shall allow users to rewind asset states to any historical timestamp or simulate operational scenarios (e.g., increased ambient temperature or over-clocking).
- **Target Phase**: Phase 12 (Digital Twin)

---

## 11. Cybersecurity, Tenant & Governance Requirements (`FR-SEC`)

### `FR-SEC-001`: Multi-Tenant Isolation & Role-Based Access Control (RBAC)
- **Description**: The system shall enforce strict data isolation between corporate tenants and support granular RBAC (`Admin`, `Portfolio Manager`, `Operator`, `Engineer`, `Technician`, `Auditor`).
- **Target Phase**: Phase 13 (Cybersecurity)

### `FR-SEC-002`: Immutable Action Audit Logging
- **Description**: All user actions, configuration changes, work order approvals, and system overrides shall be stored in an immutable, append-only audit log.
- **Target Phase**: Phase 13 (Cybersecurity)

---

## 12. Explainable AI & Human-in-the-Loop Requirements (`FR-XAI`)

### `FR-XAI-001`: Feature Attribution & Explanation Summaries
- **Description**: Every AI anomaly alert or RUL prediction shall display feature importance rankings (e.g., SHAP values) explaining *why* the prediction was triggered.
- **Target Phase**: Phase 14 (Governance & Explainability)

### `FR-XAI-002`: Human-in-the-Loop Review & Operational Approval Workflow
- **Description**: Consequential operational recommendations (e.g., inverter curtailment or battery thermal shutdown) MUST require explicit human review and approval prior to downstream CMMS or SCADA execution.
- **Target Phase**: Phase 14 (Governance & Explainability)

---

## 13. Visual User Interface & Dashboard Requirements (`FR-UI`)

### `FR-UI-001`: Mandatory Bootstrap 5.3 Light Visual System
- **Description**: All primary client user interfaces MUST be built using Bootstrap 5.3.x in the **LIGHT** theme default, adhering to clean typography, clear grid layouts, and high visual accessibility.
- **Target Phase**: Phase 15 (MVP Integration)

### `FR-UI-002`: Multi-Device Responsive Layouts
- **Description**: All screens must automatically adapt to Desktop, Tablet, and Field Mobile screen dimensions using Bootstrap responsive utilities (`col-sm`, `col-md`, `col-lg`, `col-xl`).
- **Target Phase**: Phase 15 (MVP Integration)

### `FR-UI-003`: Accessible & Non-Color Status Indicators
- **Description**: Visual status elements must pair color indicators with explicit textual labels and iconography to ensure WCAG 2.1 AA accessibility compliance.
- **Target Phase**: Phase 15 (MVP Integration)
