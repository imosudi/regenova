# REGENOVA FlowField — Architecture Audit (F0)

## 1. Executive Overview

This document establishes the verified architectural baseline for **REGENOVA FlowField** (REGENOVA FlowField — IoT Integration, Telemetry & Event Flow Service) within the broader REGENOVA renewable energy platform ecosystem.

The audit was conducted strictly following the **REGENOVA Global AI Agent Operating Contract** (`AGENTS.md`) and the **FlowField Master Implementation Specification**.

---

## 2. Platform & Microservice Boundaries

The REGENOVA platform separates responsibilities cleanly across specialized microservices:

```text
                               REGENOVA CLOUD
                         (https://regenova.cloud/)
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       │                             │                             │
       ↓                             ↓                             ↓
regenova.cloud              backoffice.regenova.cloud        API & AI Services
(User Experience &          (Tenant, Asset, Device,          (https://api.regenova.cloud/)
 Portfolio Operations)       Super-admin Operations)
       │                             │
       ├─────────────────────────────┴─────────────────────────────┐
       │                                                           │
       ↓                                                           ↓
flowfield.regenova.cloud                                twinfield.regenova.cloud
(IoT/OT Ingestion, Protocols,                           (Digital Twin Lifecycle,
 Validation, Buffering, Routing)                         State & Topology API)
       │                                                           │
       └─────────────────────────────┬─────────────────────────────┘
                                     ↓
                    PostgreSQL 18 + TimescaleDB 2.25.1
                        (db.regenova.cloud:5432)
                       ├── regenova_db (Metadata)
                       └── regenova_timeseries_db (Hypertable Telemetry)
```

### FlowField Responsibilities
- **Protocol Integration**: MQTT, HTTP REST, WebSockets, Modbus, OPC-UA adapters.
- **Data Pipeline**: Ingest → Decode → Validate → Normalise → Enrich → Classify → Persist → Route → Publish → Audit.
- **Data Quality Assessment**: Verification against 9 canonical quality states (`VALID`, `STALE`, `MISSING`, `INVALID`, `ESTIMATED`, `SIMULATED`, `DUPLICATE`, `OUT_OF_ORDER`, `UNKNOWN`).
- **Resilience**: Local memory/disk buffering, rate limiting, dead-letter quarantine, controlled replay.

### Explicit Non-Responsibilities (Handled by Ecosystem)
- Authoritative digital-twin state & topology: Owned by **TwinField** (`https://twinfield.regenova.cloud/`).
- Tenant, user, and asset administrative lifecycle: Owned by **Backoffice** (`https://backoffice.regenova.cloud/`).
- Frontend portal and cross-asset portfolio management: Owned by **REGENOVA Platform** (`https://regenova.cloud/`).
- Heavy ML and predictive analytics: Owned by **Analytics/AI Services**.

---

## 3. Node-RED Execution Engine Architecture

Node-RED serves as the lightweight, event-driven orchestration engine. It does **not** define the domain logic; domain models and data contracts remain canonical across REGENOVA:
- Node-RED runs in headless/daemon mode under systemd (`flowfield.service`).
- Web Editor is strictly gated behind cryptographic authentication (`adminAuth` with bcrypt hash) and exposed only via authenticated TLS reverse proxy.
- Reusable subflows encapsulate common pipeline functions (`Validate Envelope`, `Normalise Telemetry`, `Persist TimescaleDB`, `Route TwinField`).

---

## 4. Current State Assessment
- **Status**: Greenfield setup.
- **Local Workspace**: `/home/mosud/flowfield/` created.
- **Production Server**: Directory `/home/mosud/flowfield/` ready for runtime provisioning.
- **No Existing Flow Collisions**: No legacy, undocumented, or unapproved flows exist in production.

---

## 5. Architectural Verdict
- **Design Alignment**: Fully aligned with REGENOVA multi-tenant architecture and TimescaleDB time-series strategy.
- **Status**: `READY` for Phase F1 (Runtime Baseline).
