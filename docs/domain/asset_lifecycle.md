# REAMP - Asset Lifecycle State Machine Specification

**Document Identifier**: `REAMP-DOM-02`  
**Phase**: Phase 2 - Asset Ontology and Domain Model  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Lifecycle State Definitions

Every entity in REAMP at levels `EnergySystem`, `Asset`, and `Component` possesses an explicit, audited `LifecycleState`.

```text
 ┌─────────┐     ┌────────────────────┐     ┌──────────────┐     ┌─────────────┐
 │ PLANNED │────>│ UNDER_CONSTRUCTION │────>│ COMMISSIONED │────>│ OPERATIONAL │
 └─────────┘     └────────────────────┘     └──────────────┘     └─────────────┘
                                                                        │
                         ┌─────────────────┬────────────────────────────┤
                         │                 │                            │
                         ▼                 ▼                            ▼
                   ┌───────────┐     ┌───────────┐               ┌─────────────┐
                   │  DERATED  │     │ DEGRADED  │               │ MAINTENANCE │
                   └───────────┘     └───────────┘               └─────────────┘
                         │                 │                            │
                         └─────────────────┴─────────────┬──────────────┘
                                                         │
                                                         ▼
                                                ┌────────────────┐
                                                │ DECOMMISSIONED │
                                                └────────────────┘
```

### 1.1 State Specifications
1. **`PLANNED`**: Asset design finalized; procurement phase. Telemetry not yet online.
2. **`UNDER_CONSTRUCTION`**: Physical installation in progress. Edge gateway configured; test telemetry verification underway.
3. **`COMMISSIONED`**: Site acceptance testing (SAT) passed; Grid interconnection authorized.
4. **`OPERATIONAL`**: Asset fully functional, generating/storing energy under nominal control.
5. **`DERATED`**: Asset operating under active output restriction (e.g., thermal limit, inverter clipping, wind curtailment, grid operator dispatch limit).
6. **`DEGRADED`**: Asset operating with unrectified health impairment (e.g., cell capacity loss, pitch lag, fan failure).
7. **`MAINTENANCE`**: Asset taken offline or placed under technician isolation for preventive or corrective maintenance.
8. **`STANDBY`**: Asset healthy but disconnected or idle awaiting dispatch instructions (e.g., BESS awaiting peak arbitrage call).
9. **`DECOMMISSIONED`**: Asset permanently retired from service. Historical telemetry archived; operational alerts disabled.

---

## 2. State Transition Matrix

The table below defines permitted state transitions ($T_{ij}$):

| From \ To | `PLANNED` | `UNDER_CONSTRUCT` | `COMMISSIONED` | `OPERATIONAL` | `DERATED` | `DEGRADED` | `MAINTENANCE` | `STANDBY` | `DECOMMISSIONED` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`PLANNED`** | - | **VALID** | INVALID | INVALID | INVALID | INVALID | INVALID | INVALID | **VALID** |
| **`UNDER_CONSTRUCT`** | INVALID | - | **VALID** | INVALID | INVALID | INVALID | INVALID | INVALID | **VALID** |
| **`COMMISSIONED`** | INVALID | INVALID | - | **VALID** | INVALID | INVALID | **VALID** | **VALID** | **VALID** |
| **`OPERATIONAL`** | INVALID | INVALID | INVALID | - | **VALID** | **VALID** | **VALID** | **VALID** | **VALID** |
| **`DERATED`** | INVALID | INVALID | INVALID | **VALID** | - | **VALID** | **VALID** | **VALID** | **VALID** |
| **`DEGRADED`** | INVALID | INVALID | INVALID | **VALID** | **VALID** | - | **VALID** | **VALID** | **VALID** |
| **`MAINTENANCE`** | INVALID | INVALID | **VALID** | **VALID** | **VALID** | **VALID** | - | **VALID** | **VALID** |
| **`STANDBY`** | INVALID | INVALID | INVALID | **VALID** | **VALID** | **VALID** | **VALID** | - | **VALID** |
| **`DECOMMISSIONED`**| INVALID | INVALID | INVALID | INVALID | INVALID | INVALID | INVALID | INVALID | - |

---

## 3. Transition Triggers & Authority Requirements

| State Transition | Trigger Identifier | Trigger Category | Required Authority | Description / Precondition |
| :--- | :--- | :--- | :--- | :--- |
| `PLANNED` $\rightarrow$ `UNDER_CONSTRUCT` | `TRG-01` | Human Action | `Admin` / `Project Mgr` | Notice to Proceed (NTP) issued. |
| `UNDER_CONSTRUCT` $\rightarrow$ `COMMISSIONED` | `TRG-02` | Human Action | `Admin` / `Operations Mgr` | Site Acceptance Testing (SAT) sign-off. |
| `COMMISSIONED` $\rightarrow$ `OPERATIONAL` | `TRG-03` | Automated / Manual | `Operations Mgr` | Commercial Operation Date (COD) reached. |
| `OPERATIONAL` $\rightarrow$ `DERATED` | `TRG-04` | SCADA / AI Engine | System / Operator | Thermal limit reached or grid curtailment command received. |
| `OPERATIONAL` $\rightarrow$ `DEGRADED` | `TRG-05` | Health Engine | System (Automated) | Composite Asset Health Index ($AHI$) drops below 60. |
| `OPERATIONAL` $\rightarrow$ `MAINTENANCE` | `TRG-06` | CMMS Work Order | `Maintenance Eng` / Tech | Lockout/Tagout (LOTO) active; technician assigned. |
| `MAINTENANCE` $\rightarrow$ `OPERATIONAL` | `TRG-07` | CMMS Sign-off | `Maintenance Eng` | Post-maintenance inspection passed; LOTO removed. |
| Any $\rightarrow$ `DECOMMISSIONED` | `TRG-08` | Human Action | `Admin` / `Asset Owner` | Decommissioning authorization approved. |

---

## 4. State Operational Policies

Each state governs how REAMP microservices handle asset data:

```text
┌────────────────────┬────────────────────┬────────────────────┬────────────────────┐
│ Lifecycle State    │ Ingestion Policy   │ Alerting Policy    │ Accounting Policy  │
├────────────────────┼────────────────────┼────────────────────┼────────────────────┤
│ PLANNED            │ Reject Telemetry   │ Suppress Alerts    │ Asset Under Dev    │
│ UNDER_CONSTRUCTION │ Buffer Telemetry   │ Test Alerts Only   │ CIP (Capital)      │
│ COMMISSIONED       │ Active Ingestion   │ Active Alerts      │ COD Active         │
│ OPERATIONAL        │ Active Ingestion   │ Active Alerts      │ Full Depreciation  │
│ DERATED            │ Active Ingestion   │ Active (Derate Log)│ Curtailment Loss   │
│ DEGRADED           │ Active Ingestion   │ High Priority      │ Accel. Degradation │
│ MAINTENANCE        │ Active Ingestion   │ Suppress False Trip│ Down-time Loss     │
│ STANDBY            │ Active Ingestion   │ Nominal Alerts     │ Available Zero-Gen │
│ DECOMMISSIONED     │ Archive Only       │ Disabled           │ Fully Written Off  │
└────────────────────┴────────────────────┴────────────────────┴────────────────────┘
```

---

## 5. Audit Logging & State History Requirements

1. **State History Immutability**: All state transitions MUST be appended to an immutable `AssetLifecycleHistory` database record containing: `entity_id`, `previous_state`, `new_state`, `trigger_id`, `actor_id`, `timestamp_utc`, `reason_description`, and `supporting_telemetry_snapshot`.
2. **Audit Query API**: The domain layer shall expose historical state timelines allowing playback of asset states as of any past timestamp.
