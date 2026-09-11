# REAMP Cybersecurity Threat Model & Vulnerability Analysis

## 1. Overview & Methodology

This document details the formal threat model for the REAMP framework. Analysis follows the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) mapped specifically to utility-scale renewable energy environments (Solar PV, Wind, BESS).

---

## 2. Exhaustive Analysis of Required Threat Vectors

| # | Threat Vector | STRIDE Category | Potential Physical / Operational Consequence | REAMP Defense-in-Depth Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Compromised Device** | Spoofing / Tampering | Adversary takes control of a field sensor, combiner box, or inverter controller via firmware exploit. | Least-privilege device roles; physical plausibility checks (Phase 8); anomalous behavior scoring; device quarantine. |
| **2** | **Spoofed Telemetry** | Spoofing / Tampering | Adversary injects fabricated normal telemetry to hide acute physical overheating or thermal runaway. | Mandatory HMAC-SHA256 device packet signatures; physics-based residual cross-checks (Phase 12) against spatial peer cohorts. |
| **3** | **Replay Attack** | Spoofing / Repudiation | Adversary captures valid historical telemetry frames and replays them to mask an ongoing physical shutdown or fault. | Monotonic nonce tracking and strict timestamp freshness validation ($\Delta t \le 30\text{s}$); duplicate nonces permanently rejected. |
| **4** | **Credential Theft** | Information Disclosure | Leaked API tokens, operator passwords, or gateway private keys. | Short-lived JWT/HMAC tokens; token revocation lists; strict tenant scope enforcement; MFA requirement for supervisory roles. |
| **5** | **Malicious Gateway** | Tampering / Eavesdropping | Rogue edge device placed on the field bus or compromised edge computing node altering measurements before upload. | Gateway hardware identity validation; end-to-end payload signature verification; peer cross-validation across neighboring gateways. |
| **6** | **API Abuse** | Denial of Service / Tampering | Automated bots or rogue scripts flooding REST/GraphQL endpoints with invalid queries or malformed requests. | Token-bucket rate limiting per IP and API key; schema validation filters; strict HTTP header inspection. |
| **7** | **Privilege Escalation** | Elevation of Privilege | An unprivileged `VIEWER` or field technician modifies supervisory thresholds or approves work orders. | Strict Role-Based and Attribute-Based Access Control (RBAC/ABAC); critical actions require `CHIEF_ENGINEER` or `SECURITY_ADMIN`. |
| **8** | **Denial of Service (DoS)**| Denial of Service | Volumetric packet floods on edge gateways or cloud ingestion endpoints preventing timely dispatch of safety commands. | Edge store-and-forward autonomy (Phase 5); token-bucket rate limiters; ingress traffic shedding; decoupled asynchronous ingestion queues. |
| **9** | **Data Tampering** | Tampering / Repudiation | Alteration of historical telemetry, maintenance logs, or financial loss metrics in the central database. | Tamper-evident hash-chained SHA-256 audit logging ($H_i = \text{SHA256}(H_{i-1} \parallel \text{data})$); immutable write-only database permissions. |
| **10**| **Unauthorized Config** | Elevation of Privilege | Malicious alteration of plant safety thresholds (e.g. elevating inverter trip temperature from $95^\circ\text{C}$ to $120^\circ\text{C}$). | Config changes require signed administrative approval, dual-authorization for safety thresholds, and permanent hash-chained audit trails. |
| **11**| **Supply-Chain Risk** | Tampering / Info Disclosure | Malicious code injected via untrusted third-party packages or backdoored OEM firmware updates. | Zero external heavy binary dependencies; pure Python core libraries; cryptographic package checksum verification. |

---

## 3. High-Impact Attack Scenarios & Mitigations

### Scenario A: Telemetry Spoofing to Mask Inverter Fire Hazard
- **Attack**: Adversary compromises an edge RTU and replays normal $50^\circ\text{C}$ heatsink temperatures while the physical inverter cooling fan is seized and physical temperatures exceed $100^\circ\text{C}$.
- **REAMP Detection**:
  1. *Replay Defense*: Nonce tracking catches duplicate frames and rejects them.
  2. *Physical Cross-Check*: The Digital Twin (Phase 12) runs concurrent physics models against live pyranometer irradiance; if pyranometer reads $900\text{ W/m}^2$ but power is curtailed without thermal elevation, an anomaly residual triggers.
  3. *Peer MAD Cohort (Phase 8)*: Inverter temperature is compared with neighboring inverters in the same array; deviation triggers an alert even if the local sensor packet is superficially valid.

### Scenario B: Unauthorized Work Order Forgery
- **Attack**: A compromised low-level technician account attempts to forge an urgent work order dispatching high-voltage contractors.
- **REAMP Defense**:
  - The CMMS Workflow Engine enforces HITL gating (`AGENTS.md` Rule 8). Dispatch strictly requires `APPROVE_HITL` permission held exclusively by `CHIEF_ENGINEER` or `SECURITY_ADMIN`.
  - Any dispatch call without valid cryptographic authorization raises an unhandled `PermissionError` and records a high-severity `SecurityIncident`.
