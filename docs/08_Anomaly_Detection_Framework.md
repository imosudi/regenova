# REAMP Phase 8 — Multi-Level Anomaly Detection Framework

## 1. Executive Summary & Objective

The **REAMP Anomaly Detection Framework** establishes a multi-tiered, defense-in-depth analytical engine designed to detect, classify, and localize abnormal operating states in utility-scale renewable energy assets (Solar PV, Wind Turbines, BESS).

Traditional SCADA systems suffer from severe alert fatigue: a single cloud edge may trigger dozens of concurrent "low power" alarms, while slow, insidious faults like PID (Potential Induced Degradation), progressive bearing wear, or pyranometer calibration drift go unnoticed for months until catastrophic failure or major financial loss occurs.

The REAMP framework resolves this through a **4-tier layered architecture**:
1. **Level 1 — Deterministic Rule-Based**: Sub-second edge detection of hard safety limits, unexpected trips, communication blackouts, and physically impossible telemetry.
2. **Level 2 — Statistical & Time-Series**: Rolling statistical bands (Z-score, EWMA) and change-point algorithms (CUSUM) capturing transient spikes, step changes, and subtle mean drifts.
3. **Level 3 — Unsupervised Machine Learning**: Multi-variate tree-based Isolation Forest models detecting non-linear interactions across high-dimensional feature spaces without requiring labelled historical failure data.
4. **Level 4 — Contextual & Multi-Variate Residuals**: Physical first-principles constraint checking ($P_{ac}$ vs $V \cdot I$, $T_{cell}$ vs $P_{dc}$) and spatial peer comparisons (cross-inverter cohort Median Absolute Deviation analysis).

---

## 2. Multi-Level Detection Topology & Edge-Cloud Partition

The framework dynamically partitions analytical workloads across the REAMP edge-fog-cloud computing hierarchy based on latency requirements and computational intensity:

```
+-----------------------------------------------------------------------------------+
| LEVEL 1: RULE-BASED DETECTOR (Edge / Gateway — Latency: < 10 ms)                  |
| - Physical limit checks (Voltage, Current, Cell Temp, Inverter Heatsink)          |
| - Unexpected shutdown detection (OperatingState == RUNNING but Active Power == 0) |
| - Communication heartbeat watchdog (Signal loss > 30s)                            |
| - Impossible value screening (Negative irradiance, efficiency > 100%)             |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| LEVEL 2: STATISTICAL DETECTOR (Edge / Fog — Latency: < 500 ms)                    |
| - Sliding window Z-score filter for transient spikes                              |
| - Exponentially Weighted Moving Average (EWMA) with 3-sigma control limits        |
| - Cumulative Sum (CUSUM) change-point detection for step shifts                   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| LEVEL 3: MACHINE LEARNING DETECTOR (Fog / Cloud — Latency: < 5 s)                 |
| - Pure Python / NumPy Isolation Forest (zero heavy C-dependency lock-in)          |
| - Multi-variate isolation depth path-length scoring                               |
| - Non-linear interaction anomaly scoring s(x, n) in [0.0, 1.0]                    |
| - Feature attribution isolating the dominant driving variable                     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| LEVEL 4: CONTEXTUAL & SPATIAL DETECTOR (Cloud / Central Server — Latency: < 30 s)  |
| - Physical correlation residuals (P_ac vs V_ac * I_ac, Cell Temp vs DC Power)     |
| - Cross-inverter spatial peer analysis (Median Absolute Deviation vs Array Cohort)|
| - Weather-normalized residual check (Phase 7 expected-power comparison)           |
+-----------------------------------------------------------------------------------+
```

---

## 3. Canonical Anomaly Object Schema

Every detected anomaly across all four tiers is encapsulated in a standardized, immutable, typed **Anomaly Object**. In accordance with Phase 8 specifications, every anomaly object contains:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `anomaly_id` | `str` | Globally unique identifier (UUID v4 or structured format `ANOM-<asset>-<timestamp>`). |
| `asset_id` | `str` | Canonical identifier of the affected asset (e.g. `INV-001`, `WTG-04`, `BESS-RACK-02`). |
| `timestamp` | `str` | ISO 8601 UTC timestamp of detection. |
| `type` | `AnomalyType` | Enumerated taxonomy (`THRESHOLD_VIOLATION`, `UNEXPECTED_SHUTDOWN`, `COMMUNICATION_TIMEOUT`, `IMPOSSIBLE_VALUE`, `STATISTICAL_ZSCORE`, `STATISTICAL_EWMA`, `CHANGE_POINT_CUSUM`, `ML_ISOLATION_FOREST`, `PHYSICAL_RESIDUAL`, `PEER_OUTLIER`). |
| `severity` | `AnomalySeverity` | Discrete severity tier: `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `score` | `float` | Normalized anomaly score ($0.0 \le s \le 1.0$) indicating extremity. |
| `evidence` | `Dict[str, Any]` | Detailed explainability payload: observed value, expected baseline, threshold, z-score, residuals, and driving feature. |
| `confidence` | `float` | Metric confidence rating ($0.0 \le c \le 1.0$) accounting for sensor quality. |
| `detection_method`| `str` | Concrete tier and algorithm (e.g. `LEVEL_1_THRESHOLD`, `LEVEL_2_EWMA`, `LEVEL_3_ISOLATION_FOREST`, `LEVEL_4_PEER_MAD`). |
| `model_version` | `str` | Semantic version string of the evaluating detector (e.g. `1.0.0-phase8`). |
| `recommended_action`| `str` | Prescriptive operator guidance or automated dispatch instruction. |

---

## 4. Alert Suppression, Deduplication, and Arbitration

To eliminate alarm floods, the central orchestrator applies three deterministic arbitration rules:

1. **Subsumption Hierarchy**:
   If an asset suffers an `UNEXPECTED_SHUTDOWN` (Level 1), downstream Level 2 (Z-score drop) and Level 3 (ML anomaly) alerts triggered by the same power drop are suppressed and attached as supporting evidence to the primary Level 1 alarm.
2. **Temporal Deduplication**:
   Consecutive detections of the same anomaly type on the same asset within a configurable cooling window (e.g. 5 minutes) are grouped into a single ongoing incident, updating duration and peak score rather than spawning redundant notifications.
3. **Data Quality Gating**:
   If the ingestion pipeline flags telemetry as `INVALID` or `STALE` (Phase 4/5), Level 2, 3, and 4 statistical and ML detectors are suppressed, and a single `COMMUNICATION_TIMEOUT` or `IMPOSSIBLE_VALUE` Level 1 event is emitted with downgraded confidence.

---

## 5. Integration with Asset Health and Maintenance (CMMS)

The Anomaly Detection Framework directly feeds the broader REAMP lifecycle architecture:
- **Phase 6 Asset Health Index**: Detected anomalies decrement the $S_{fault}$ (Fault History) sub-index using exponential time-decay penalties based on severity.
- **Phase 10 CMMS Integration**: Anomalies of `HIGH` or `CRITICAL` severity automatically draft prioritized Corrective Maintenance (CM) work orders with pre-populated evidence payloads, reducing Mean Time to Repair (MTTR).
- **Phase 12 Digital Twin**: Persistent anomalous residuals trigger state machine transitions from `NOMINAL` to `DEGRADED` or `FAULT`.

---

## 6. Engineering Deliverables Summary

| Module | Location | Purpose |
| :--- | :--- | :--- |
| **Framework Specification** | `docs/08_Anomaly_Detection_Framework.md` | Primary architecture and edge-cloud topology. |
| **Methods Specification** | `docs/analytics/anomaly_methods.md` | Mathematical formulations for Levels 1–4. |
| **Evaluation Specification** | `docs/analytics/anomaly_evaluation.md` | Benchmarking methodology and metrics. |
| **Data Models** | `reamp/anomaly/models.py` | Typed dataclasses, enums, configurations. |
| **Level 1 Detector** | `reamp/anomaly/level1_rules.py` | Thresholds, shutdowns, timeouts, impossible values. |
| **Level 2 Detector** | `reamp/anomaly/level2_statistical.py` | Rolling Z-score, EWMA bands, CUSUM. |
| **Level 3 Detector** | `reamp/anomaly/level3_ml.py` | Pure-Python/NumPy Isolation Forest with explainability. |
| **Level 4 Detector** | `reamp/anomaly/level4_contextual.py` | Physical correlation and cross-inverter peer MAD. |
| **Orchestrator Engine** | `reamp/anomaly/engine.py` | Multi-tier coordination, suppression, arbitration. |
| **Verification Suite** | `tests/test_phase8_anomaly.py` | Comprehensive test suite + empirical benchmark. |
| **Completion Report** | `docs/PHASE_8_REPORT.md` | Formal phase completion report adhering to `AGENTS.md`. |
