# REGENOVA (REAMP) - Framework Vision and System Overview

**Document Identifier**: `REAMP-DOC-01`  
**Phase**: Phase 1 - Framework Vision and Requirements  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Executive Vision & Purpose

**REGENOVA** is an open, production-oriented, research-grade software framework engineered to optimize the lifecycle, operational performance, health assessment, anomaly detection, predictive maintenance, and risk-adjusted financial returns of heterogeneous renewable energy assets, consolidating and incorporating the **Renewable Energy Asset Intelligence and Management Framework (REAMP)** core architecture.

Modern renewable energy infrastructure suffers from severe operational fragmentation: disparate telemetry formats, proprietary SCADA silos, dark data, uncalibrated anomaly alerts, opaque AI models ("black boxes"), and disconnected computerised maintenance management systems (CMMS).

REGENOVA (incorporating REAMP) solves this by establishing a unified, technology-agnostic data and analytical framework that transforms high-frequency, noisy raw telemetry into actionable, explainable, and audited decision support.

---

## 2. System Scope

### 2.1 In-Scope Capabilities
- **Multi-Technology Domain Modeling**: Native support for Solar PV, Wind Energy, Battery Energy Storage Systems (BESS), and Hybrid Plants.
- **Canonical Asset Hierarchy**: Strict 8-level conceptual mapping (`Organisation → Portfolio → Project → Site → Energy System → Asset → Component → Sensor`).
- **Resilient Edge-to-Cloud Telemetry**: Store-and-forward buffering, protocol translation (Modbus, OPC UA, MQTT, DNP3), edge inference, and cloud ingestion.
- **Data Quality & Provenance**: Automated validation, quality scoring, missing data handling, and sensor drift detection.
- **Asset Health & Performance Intelligence**: Multi-factor degradation modeling, temperature-compensated performance ratio (PR), capacity factor tracking, and degradation rate analysis.
- **Explainable Anomaly Detection & Predictive Maintenance**: Physics-informed machine learning, anomaly root cause analysis, remaining useful life (RUL) estimation, and work order generation.
- **Financial & Risk Intelligence**: Revenue loss attribution, penalty risk calculation, degradation-adjusted asset valuation, and maintenance ROI analysis.
- **Human-in-the-Loop Governance**: Audited decision workflows for automated recommendations.
- **Bootstrap 5.3 Light Visual System**: Friendly, professional, accessible, high-contrast UI design.

### 2.2 Out-of-Scope (Phase 1 Boundary)
- Direct physical control or automated tripping of high-voltage circuit breakers (Safety-critical emergency shutdown remains in hardware relays/SCADA PLCs).
- Commodity energy trading market execution (REAMP provides yield forecasts and availability data, but does not execute direct market bids).
- Proprietary SCADA firmware replacement.

---

## 3. Framework Objectives

### 3.1 Primary Operational Objectives
1. **Reduce Unplanned Down-Time**: Achieve a >25% reduction in mean time to repair (MTTR) through early anomaly detection and prescriptive maintenance diagnostics.
2. **Optimize Performance Ratio (PR)**: Identify micro-inefficiencies (e.g., inverter clipping, tracker misalignment, soot/soiling accumulation, pitch lag, cell degradation) before major failures occur.
3. **Guarantee Data Integrity**: Ensure 100% of incoming telemetry is tagged with explicit data quality metadata and confidence scores.

### 3.2 Research Objectives
1. **Physics-Informed AI / Hybrid Models**: Combine empirical physics models (e.g., PV single-diode equations, Wind power curves, BESS equivalent circuit models) with deep learning for physics-guided anomaly detection.
2. **Explainable AI (XAI)**: Provide feature importance attribution (e.g., SHAP, integrated gradients) for every asset health risk score.
3. **Cross-Technology Knowledge Transfer**: Support domain adaptation algorithms capable of transferring failure patterns across asset types.

### 3.3 Commercial Objectives
1. **Lower Total Cost of Ownership (TCO)**: Eliminate expensive proprietary vendor lock-in for asset management software.
2. **Extend Asset Useful Life**: Mitigate accelerated thermal/mechanical degradation via operational recommendations.
3. **Enhance Bankability**: Provide immutable audit trails and transparent health records for project financing and insurance underwriting.

---

## 4. Target Personas and Organisations

### 4.1 Target Organisations
- **Independent Power Producers (IPPs)** managing gigawatt-scale multi-technology portfolios.
- **Renewable Energy Asset Owners & Investors** seeking asset health visibility and financial loss attribution.
- **Original Equipment Manufacturers (OEMs)** evaluating component field reliability.
- **Operation & Maintenance (O&M) Providers** requiring dispatch optimization and CMMS integration.
- **Research Institutions & Universities** studying grid integration, degradation, and renewable energy AI applications.

### 4.2 Target User Personas

| Persona Identifier | Role / Title | Primary Responsibilities | Key System Needs |
| :--- | :--- | :--- | :--- |
| **PERS-01** | Portfolio Manager | Financial yield oversight, high-level availability tracking, ESG compliance. | Executive dashboards, revenue loss heatmaps, cross-site comparisons. |
| **PERS-02** | Operations Manager | Day-to-day plant operations, curtailment tracking, dispatch compliance. | Real-time plant status, active alert feeds, generation forecasts. |
| **PERS-03** | Maintenance Engineer | Root cause investigation, diagnostics, maintenance scheduling. | Diagnostic charts, remaining useful life estimates, anomaly explanations. |
| **PERS-04** | Field Technician | On-site inspections, component replacement, work order execution. | Mobile-responsive view, step-by-step repair guides, offline asset lookup. |
| **PERS-05** | Asset Owner / Investor | Long-term asset depreciation, warranty claims, bankability reviews. | Financial risk reports, degradation trends, immutable audit records. |
| **PERS-06** | Data Scientist / Researcher | Algorithm benchmarking, physics model validation, custom feature engineering. | Jupyter notebook API access, raw telemetry query endpoints, model metrics. |
| **PERS-07** | System Administrator | User access governance, tenant provisioning, system health monitoring. | Security role mapping, audit logs, resource consumption metrics. |

---

## 5. Supported Asset Technologies

REAMP decouples technology-specific physical physics from core domain services using an adapter-based design.

```text
┌─────────────────────────────────────────────────────────────────┐
│                    REAMP Core Domain Model                      │
└─────────────────────────────────────────────────────────────────┘
                               ▲
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Solar PV    │       │     Wind     │       │     BESS     │
│   Adapter    │       │   Adapter    │       │   Adapter    │
└──────────────┘       └──────────────┘       └──────────────┘
```

### 5.1 Solar Photovoltaic (PV)
- **Sub-systems**: Inverters (central/string), PV Strings, Combiner Boxes, Trackers (single-axis/dual-axis), Pyranometers, Weather Stations.
- **Key Metrics**: Irradiance ($W/m^2$), Module Temperature ($^\circ C$), String Current ($A$), DC/AC Ratio, Soiling Ratio, Performance Ratio ($PR$).

### 5.2 Wind Energy Systems
- **Sub-systems**: Rotor Blades, Pitch System, Gearbox, Main Bearing, Generator, Power Converter, Yaw System, Anemometers, Nacelle.
- **Key Metrics**: Wind Speed ($m/s$), Wind Direction ($^\circ$), Rotor RPM, Pitch Angle ($^\circ$), Gearbox Oil Temp ($^\circ C$), Power Curve Efficiency ($C_p$).

### 5.3 Battery Energy Storage Systems (BESS)
- **Sub-systems**: Battery Cells, Battery Racks/Modules, Battery Management System (BMS), Power Conversion System (PCS), HVAC/Thermal Control, Fire Suppression.
- **Key Metrics**: State of Charge ($SoC \%$), State of Health ($SoH \%$), Cell Voltage Delta ($mV$), Temperature Gradient ($^\circ C$), Charge/Discharge Rate ($C$-rate), Round-Trip Efficiency ($RTE \%$).

### 5.4 Hybrid Plants
- Integrated control and combined capacity modeling (e.g., Solar + BESS microgrid or Wind + Solar hybrid farm).

---

## 6. Operational Environments & Deployment Models

REAMP supports flexible deployment across edge, fog, and cloud tiers:

```text
 Physical Assets       Edge Tier              Fog Tier              Cloud Tier
 ┌──────────────┐   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
 │ Sensors      │──>│ Edge Gateway │─────>│ Site Server  │─────>│ Central Cloud│
 │ Inverters    │   │ Local Buffer │      │ Analytics    │      │ Global Twin  │
 │ Meters       │   │ Protocol Map │      │ Local Alert  │      │ Portfolio UI │
 └──────────────┘   └──────────────┘      └──────────────┘      └──────────────┘
```

### 6.1 Operational Environments
1. **Edge Tier (Low latency, constrained compute)**: Industrial PCs (IPCs) or Raspberry Pi/ARM gateways situated at sub-station or inverter stations. Runs lightweight telemetry validation and store-and-forward logging.
2. **Fog Tier (Plant/Site level compute)**: On-site server clusters performing plant-level aggregation, local SCADA protocol ingestion, and offline alert generation.
3. **Cloud Tier (High compute, enterprise)**: Multi-tenant Kubernetes cluster hosting historical time-series analytics, digital twin state machines, predictive ML model training, and executive Bootstrap 5.3 UI.

### 6.2 Deployment Models
- **Fully Cloud-Native**: For sites with high-bandwidth, reliable fiber connections.
- **Hybrid Cloud/Edge**: Recommended production configuration. Critical store-and-forward and emergency notifications execute on-site; deep learning and historical analytics reside in cloud.
- **Air-Gapped / On-Premise**: Enterprise security configuration for isolated critical infrastructure.

---

## 7. Comprehensive Problem Domain Taxonomy

REAMP categorizes the operational challenges of renewable asset management into 15 structured domain pillars:

```text
 1. Asset Visibility     2. Telemetry Ingestion   3. Data Quality          4. Connectivity
 5. Asset Condition      6. Performance Intel.    7. Anomaly Detection     8. Failure Diagnostics
 9. Maintenance / CMMS  10. Financial / Loss     11. Risk & Depreciation  12. Cybersecurity
13. Regulatory Compliance 14. Scalability & Resilience 15. Explainable AI (XAI)
```

1. **Asset Visibility Taxonomy**: Asset tracking, hierarchy mapping, configuration drifting, warranty monitoring, location GIS mapping.
2. **Telemetry Ingestion Taxonomy**: Modbus RTU/TCP, OPC UA, MQTT, DNP3, IEC 60870-5-104, REST, high-frequency sampling (1Hz to 15min intervals).
3. **Data Quality Taxonomy**: Out-of-bounds detection, frozen sensor values, timestamps out-of-order, missing packet imputation, sensor drift calibration.
4. **Connectivity Taxonomy**: Intermittent cellular links, satellite backhaul latency, store-and-forward queues, signal degradation, packet loss recovery.
5. **Asset Condition Taxonomy**: Thermal stress, insulation degradation, mechanical vibration, state-of-health ($SoH$) loss, component wear.
6. **Performance Intelligence Taxonomy**: Weather-adjusted yield, temperature loss, curtailment loss, clipping loss, soiling loss, aerodynamic drag loss.
7. **Anomaly Detection Taxonomy**: Point anomalies, contextual anomalies, collective drift, multi-variate correlations, signature matching.
8. **Failure Diagnostics Taxonomy**: Root cause analysis (RCA), failure mode and effects analysis (FMEA), fault trees, remaining useful life (RUL).
9. **Maintenance / CMMS Taxonomy**: Work order lifecycle, preventive maintenance scheduling, spare parts inventory, field technician dispatching.
10. **Financial Impact Taxonomy**: Uncaptured revenue, contract penalties (PPA terms), degradation financial valuation, maintenance cost-benefit analysis.
11. **Risk & Depreciation Taxonomy**: Asset health index (AHI), technical risk ratings, insurance risk profiling, accelerated asset depreciation.
12. **Cybersecurity Taxonomy**: Role-Based Access Control (RBAC), tenant isolation, TLS 1.3 encryption, API key security, audit trails.
13. **Regulatory Compliance Taxonomy**: NERC CIP compliance, IEC 61400 (Wind), IEC 61724 (Solar PV), IEEE 1547 grid compliance.
14. **Scalability & Resilience Taxonomy**: Horizontal scaling, time-series partitioning, cache invalidation, grace degradation under network load.
15. **Explainable AI (XAI) Taxonomy**: Model feature importance, physics-guided constraint checking, confidence scoring, human-in-the-loop audit logs.

---

## 8. Architectural Principles & Operating Rules

All downstream implementation phases MUST comply with the non-negotiable rules defined in `AGENTS.md`:

1. **Mandatory UI Framework**: **Bootstrap 5.3.x** exclusively. Custom CSS must strictly complement Bootstrap standard utilities.
2. **Default Visual Theme**: **LIGHT** theme default. Clean, friendly, professional visual language prioritizing high contrast, clear typography, and restrained shadows.
3. **Data Integrity Standard**: Telemetry values must NEVER be silently converted or fabricated. Invalid data must carry explicit quality flags (`INVALID`, `MISSING`, `STALE`, `UNCERTAIN`).
4. **Human-in-the-Loop Governance**: AI recommendations must follow a two-step approval process (`AI Recommendation → Human Review → Operational Approval → Action Execution`).
