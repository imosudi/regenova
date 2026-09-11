# REAMP - System Actors and Use Cases Specification

**Document Identifier**: `REAMP-REQ-UC-01`  
**Phase**: Phase 1 - Framework Vision and Requirements  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Primary System Actors

| Actor Identifier | Actor Name | Description | Key Interactivity |
| :--- | :--- | :--- | :--- |
| **ACT-01** | System Administrator | Controls tenant provisioning, RBAC roles, system health, security configurations. | Admin portal, CLI, Security API |
| **ACT-02** | Portfolio Manager | Monitors cross-portfolio yield, revenue loss, ESG compliance, high-level availability. | Bootstrap Light Portfolio Dashboard |
| **ACT-03** | Operations Manager | Manages day-to-day plant operations, active alerts, grid curtailments, plant dispatch. | Operations Console, Real-time Feeds |
| **ACT-04** | Maintenance Engineer | Performs diagnostic analysis, failure tree investigation, work order review. | Diagnostics Workbench, Health Engine |
| **ACT-05** | Field Technician | Executes physical repair, asset replacement, CMMS work order updates on-site. | Mobile Bootstrap View, Field App |
| **ACT-06** | Asset Owner / Investor | Evaluates financial ROI, degradation impact, asset bankability, warranty claims. | Financial Risk & Yield Reports |
| **ACT-07** | Data Scientist / Researcher | Builds, trains, validates physics-informed ML models and anomaly algorithms. | Analytics API, Model Governance |
| **ACT-08** | Edge Gateway System | Autonomous edge hardware logging telemetry, running local validation & store-forward. | Modbus/OPC UA protocols, Ingestion Gateway |

---

## 2. Core Use Cases (`UC-001` to `UC-012`)

### `UC-001`: Register and Provision New Renewable Energy Site
- **Primary Actor**: System Administrator (`ACT-01`)
- **Preconditions**: Administrator authenticated; site metadata & SCADA gateway details available.
- **Primary Flow**:
  1. Administrator creates site under an existing `Organisation → Portfolio → Project`.
  2. Selects technology adapter type (`Solar PV`, `Wind`, `BESS`, `Hybrid`).
  3. Uploads asset hierarchy schema file (JSON/YAML mapping inverters, strings, turbines, cells, sensors).
  4. System validates hierarchy schema integrity and provisions time-series channels.
  5. System issues secure API credentials / TLS certificates to local Edge Gateway (`ACT-08`).
- **Postconditions**: Site active in Asset Hierarchy; Edge Gateway initialized.

---

### `UC-002`: Real-Time Telemetry Ingestion and Quality Validation
- **Primary Actor**: Edge Gateway System (`ACT-08`)
- **Preconditions**: Edge Gateway connected to plant SCADA network; telemetry streams active.
- **Primary Flow**:
  1. Edge Gateway samples raw sensor data over Modbus TCP / OPC UA.
  2. Applies physical range checks and freeze checks locally.
  3. Enriches payload with quality metadata (`VALID`, `UNCERTAIN`, `STALE`, etc.) and timestamp.
  4. Transmits enriched payload to REAMP Cloud Ingestion Gateway.
  5. Ingestion engine commits records to time-series database and triggers real-time websocket broadcast.
- **Alternative Flow (Network Disconnect)**: If WAN connection fails, Edge Gateway routes payload to local SQLite/LevelDB store-and-forward queue.
- **Postconditions**: Telemetry stored with quality metadata; real-time views updated.

---

### `UC-003`: Portfolio Asset Health and Availability Monitoring
- **Primary Actor**: Portfolio Manager (`ACT-02`) / Operations Manager (`ACT-03`)
- **Preconditions**: User logged into REAMP Light Theme Web UI.
- **Primary Flow**:
  1. User navigates to Portfolio Overview.
  2. UI displays summary metrics: Total Installed Capacity (MW), Generation (MWh), Portfolio Health Index ($AHI$), and Active Anomalies count.
  3. User filters view by technology (`Solar PV`, `Wind`, `BESS`) or status (`Healthy`, `Warning`, `Critical`).
  4. User clicks on a degraded site to inspect underlying inverter/turbine health scores.
- **Postconditions**: User gains immediate visibility into portfolio degradation.

---

### `UC-004`: Solar PV Temperature-Compensated Performance Ratio (PR) Analysis
- **Primary Actor**: Maintenance Engineer (`ACT-04`)
- **Preconditions**: PV site streaming irradiance, ambient temp, module temp, and AC power data.
- **Primary Flow**:
  1. User selects PV Site Inverter station.
  2. System computes standard PR and temperature-compensated $PR_{STC}$ according to IEC 61724-1.
  3. System overlays measured DC power against expected theoretical yield based on single-diode model.
  4. System highlights delta ($PR$ drop due to thermal clipping vs soiling accumulation).
- **Postconditions**: Specific efficiency loss cause isolated.

---

### `UC-005`: Wind Turbine Power Curve Degradation Diagnostic
- **Primary Actor**: Maintenance Engineer (`ACT-04`)
- **Preconditions**: Nacelle anemometer wind speed ($m/s$) and generator active power ($kW$) telemetry ingested.
- **Primary Flow**:
  1. Diagnostics engine continuously maps wind speed vs power output against OEM reference power curve.
  2. System detects systematic under-performance in high wind speeds ($C_p$ drop).
  3. Engine analyzes pitch angle telemetry and yaw error data.
  4. Engine diagnoses pitch calibration drift as root cause.
- **Postconditions**: Anomaly flagged; diagnostic report prepared.

---

### `UC-006`: BESS State of Health (SoH) & Thermal Anomaly Detection
- **Primary Actor**: Operations Manager (`ACT-03`) / Maintenance Engineer (`ACT-04`)
- **Preconditions**: Battery rack telemetry streaming cell voltages, temperatures, and $SoC$.
- **Primary Flow**:
  1. BESS health module monitors cell temperature delta across Rack #4.
  2. System detects Cell #18 operating $8.5^\circ C$ hotter than adjacent cells during $1C$ discharge.
  3. Health engine updates BESS Rack $SoH$ estimation and triggers `WARNING` alert.
  4. System displays recommended maximum charge current derating to mitigate thermal runaway risk.
- **Postconditions**: Risk derating displayed; alert logged.

---

### `UC-007`: Explainable Anomaly Root Cause Analysis (RCA)
- **Primary Actor**: Maintenance Engineer (`ACT-04`)
- **Preconditions**: Multi-variate anomaly alert triggered on PV Inverter #2.
- **Primary Flow**:
  1. Engineer opens Anomaly Details page in REAMP UI.
  2. UI renders SHAP feature importance plot showing top contributors: `DC Input Current B` (65%), `Heat Sink Temp` (22%), `Grid Frequency` (13%).
  3. Diagnostic engine provides plain-text explanation: *"Inverter #2 MPPT String B exhibiting partial shading or string fuse failure."*
  4. Engineer confirms diagnosis with single click.
- **Postconditions**: Diagnostic decision validated; feedback recorded for ML model tuning.

---

### `UC-008`: Automated Predictive Maintenance Work Order Dispatch
- **Primary Actor**: Operations Manager (`ACT-03`) / Maintenance Engineer (`ACT-04`)
- **Preconditions**: Remaining Useful Life ($RUL$) for Wind Turbine #3 Gearbox Bearing calculated at $< 120 \text{ hours}$.
- **Primary Flow**:
  1. Predictive maintenance engine automatically drafts a high-priority CMMS Work Order (`WO-8942`).
  2. Work Order includes: Asset ID, required replacement part number (`GB-BEARING-99`), required skill tag (`Vibration Specialist`), estimated labor hours (8h).
  3. Operations Manager reviews draft in Human-in-the-Loop approval queue.
  4. Manager approves Work Order, triggering CMMS API dispatch.
- **Postconditions**: Work Order dispatched to CMMS; Field Technician assigned.

---

### `UC-009`: Financial Loss and Revenue Impact Calculation
- **Primary Actor**: Asset Owner / Investor (`ACT-06`) / Portfolio Manager (`ACT-02`)
- **Preconditions**: Energy curtailment or equipment down-time recorded; PPA tariff rates configured.
- **Primary Flow**:
  1. User selects "Financial Impact Report" for Site Alpha (Q3 2026).
  2. System aggregates lost energy generation ($142 \text{ MWh}$ lost due to inverter thermal derating).
  3. Financial engine applies time-of-use PPA contract rates ($142 \text{ MWh} \times \$85/\text{MWh} = \$12,070$).
  4. UI renders revenue loss breakdown pie chart (Unplanned Down-time vs Grid Curtailment vs Soiling).
- **Postconditions**: Financial loss report generated and exportable as PDF/CSV.

---

### `UC-010`: Digital Twin State Playback and Scenario Simulation
- **Primary Actor**: Data Scientist (`ACT-07`) / Operations Manager (`ACT-03`)
- **Preconditions**: Digital twin state machine active; historical telemetry stored.
- **Primary Flow**:
  1. User opens Digital Twin Explorer for Solar Site Bravo.
  2. User selects timestamp range corresponding to extreme weather event.
  3. User plays back digital twin state transitions (`RUNNING` → `DERATED` → `THERMAL_FAULT`).
  4. User runs "What-If" scenario: *"Simulate plant output if module washing had occurred 7 days prior."*
  5. System simulates single-diode yield under clean module conditions.
- **Postconditions**: Simulation results compared against actual historical yield.

---

### `UC-011`: Human-in-the-Loop Operational Recommendation Approval
- **Primary Actor**: Operations Manager (`ACT-03`)
- **Preconditions**: AI engine recommends automated operational change (e.g., derating wind turbine power output by 15% due to high turbulence).
- **Primary Flow**:
  1. System creates an Approval Task in the Manager's task queue.
  2. Manager inspects recommendation details: AI Confidence (94%), Supporting Features (Turbulence Intensity $I_u > 0.18$), Expected Risk Reduction.
  3. Manager selects `APPROVE WITH MODIFICATION` and adjusts derating to 10%.
  4. System logs Manager's identity, timestamp, and modification reason in audit trail.
- **Postconditions**: Operational command dispatched to plant control system; audit entry recorded.

---

### `UC-012`: Edge Store-and-Forward Network Recovery
- **Primary Actor**: Edge Gateway System (`ACT-08`)
- **Preconditions**: Network connection between Edge Gateway and Cloud restored after 12-hour cellular outage.
- **Primary Flow**:
  1. Edge Gateway detects active Cloud websocket connectivity.
  2. Gateway initiates store-and-forward sync protocol.
  3. Gateway streams buffered time-series records in compressed batches, preserving original sensor timestamps and quality tags.
  4. Cloud ingestion engine validates batch checksums and backfills time-series database.
  5. Gateway clears local buffer upon receipt of Cloud ACK.
- **Postconditions**: Zero telemetry data loss; Cloud database fully restored.
