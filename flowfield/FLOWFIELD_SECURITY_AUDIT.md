# REGENOVA FlowField — Security Audit (F0)

## 1. Perimeter & Transport Security

- **TLS**: Enforced across all public domains (`flowfield.regenova.cloud`, `twinfield.regenova.cloud`, etc.) via Let's Encrypt certificates.
- **Protocols**: TLS 1.3 negotiated with strong cipher suites (`TLS_AES_256_GCM_SHA384`).
- **HTTP**: All plain HTTP (port 80) requests are permanently redirected (`301 Moved Permanently`) to HTTPS.
- **Firewall**: Linux `iptables` blocks all external inbound ports except 22 (SSH), 80 (HTTP), 443 (HTTPS), 5432 (PostgreSQL), and 10000 (Webmin). All application runtimes bind to `127.0.0.1` and are reverse-proxied.

---

## 2. Node-RED Editor Security (Mandatory Requirement)

- **Vulnerability / Risk**: Exposing an unauthenticated Node-RED visual editor permits arbitrary JavaScript code execution (`Function` nodes) and physical server compromise.
- **Mitigation Strategy**:
  1. `adminAuth` must be enabled in `settings.js` prior to activating the public Apache proxy.
  2. Passwords must be hashed using `bcrypt` (cost factor 12+).
  3. API tokens or bearer authorization headers must be required for HTTP ingest endpoints.
  4. Node-RED runtime will execute under non-privileged service user `mosud`.

---

## 3. Database Security

- **Authentication**: SCRAM-SHA-256 enabled for `regenova_timeseries_db`.
- **Network Isolation**: `pg_hba.conf` only permits local socket and `127.0.0.1/32` connections for the time-series database.
- **Secrets Management**: Database passwords and credentials must be stored strictly in environment variables (`.env`) with `chmod 600`, never hard-coded in flow JSON files or committed to Git.

---

## 4. Message Integrity & Quality

- Non-negotiable Rule 7 from `AGENTS.md`: "Never allow invalid, missing, stale or low-confidence telemetry to be silently treated as trustworthy data."
- FlowField mandates validation against 9 canonical quality states:
  - `VALID`, `STALE`, `MISSING`, `INVALID`, `ESTIMATED`, `SIMULATED`, `DUPLICATE`, `OUT_OF_ORDER`, `UNKNOWN`.
- Malformed payloads are quarantined to a dead-letter table/queue rather than silently discarded or passed downstream.

---

## 5. Security Verdict
- **Status**: `READY` with clear security policies documented for Phase F1 implementation.
