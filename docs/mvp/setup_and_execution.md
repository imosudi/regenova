# REAMP MVP - Setup and Execution Guide

## 1. System Requirements & Environment

The REAMP framework is engineered to run on standard Linux/Unix edge and server environments without requiring heavy, platform-dependent binary dependencies.

- **Python Version**: Python 3.10+ (Tested on Python 3.12)
- **Core Runtime Dependencies**:
  - `numpy` (Numerical calculations and matrix operations)
  - `sqlite3` (Built-in standard library for local edge buffer and ACID relational registry)
  - `hashlib`, `hmac`, `secrets`, `dataclasses`, `typing`, `datetime` (Built-in standard library)
- **Virtual Environment Setup**:
  ```bash
  # From repository root
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install numpy pytest
  ```

---

## 2. Running the End-to-End MVP Demonstration

The repository includes a comprehensive, standalone executable demonstration script (`demo_mvp.py`) that initializes a multi-tenant utility-scale solar plant, streams edge telemetry, processes anomalies, updates the digital twin, derives deterministic health, triggers automated alerts, executes HITL work-order management, and compiles executive performance reports.

### Run the CLI Demonstration:
```bash
python3 demo_mvp.py
```

### Expected Output Summary:
The demonstration script executes the complete 10-stage pipeline:
1. **Hierarchy Initialization**: Creates Organization (`Helios Clean Energy`), Portfolio (`Southwest Utility Fleet`), Site (`Mojave Solar Station - 50MW`), Asset (`INV-01 - 2.5MW Central Inverter`), and Sensors (POA Pyranometer, Heatsink PT100, DC Power Meter, AC Power Meter).
2. **Ingestion & Security**: Generates HMAC-SHA256 signed edge packets, validates cryptographic nonces, and buffers them to the time-series store.
3. **Analytics & Twin Execution**: Feeds sensor readings to the Digital Twin and IEC 61724-1 loss engine, evaluating performance ratio ($PR$) and thermal equilibrium.
4. **Health & Anomaly**: Detects heatsink cooling degradation ($\Delta T = +24^\circ\text{C}$), computes multi-level anomaly scores, and derates the Inverter Health Index ($HI$).
5. **Alerting & HITL CMMS**: Emits a `CRITICAL` alert, auto-drafts Work Order `WO-0001` in `PENDING_HITL_APPROVAL` state, enforces access control gating, records human approval, reserves replacement fans from inventory, and closes the ticket.
6. **Executive Report & Audit Verification**: Renders executive operational metrics and verifies the cryptographic integrity of the SHA-256 hash-chained audit log.

---

## 3. Running Automated Integration & Regression Tests

Run the full automated test suite covering Phase 4 through Phase 15:
```bash
# Run the Phase 15 MVP test suite specifically
pytest tests/test_phase15_mvp.py -v

# Run the complete framework regression test suite
pytest tests/ -v
```

---

## 4. Programmatic API Facade Usage

The MVP exposes a unified programmatic interface `reamp.mvp.api.REAMPAppAPI` for SCADA integrations, external web APIs, and operator workstations.

```python
from reamp.mvp.orchestrator import REAMPApplicationMVP
from reamp.mvp.api import REAMPAppAPI

# 1. Initialize MVP Runtime (in-memory or persistent SQLite storage)
app = REAMPApplicationMVP(storage_db=":memory:")
app.initialize_default_topology()

# 2. Expose API Facade
api = REAMPAppAPI(app)

# 3. Authenticate Device/Operator
token = api.authenticate(client_id="secops-operator-01", role="OPERATIONS_MANAGER")

# 4. Ingest Edge Telemetry Packet
ingest_result = api.ingest_telemetry(
    asset_id="ASSET-INV-01",
    telemetry_data={
        "poa_irradiance": 850.0,
        "ambient_temp": 28.0,
        "dc_power_kw": 2100.0,
        "ac_power_kw": 1850.0,
        "heatsink_temp": 78.0
    },
    auth_token=token
)

# 5. Query Real-Time Unified Dashboard
dashboard = api.get_unified_dashboard(site_id="SITE-MOJAVE-01", auth_token=token)
print(f"Plant Generation: {dashboard['generation']['total_active_power_mw']} MW")
print(f"Asset Health Index: {dashboard['assets']['ASSET-INV-01']['health_index']}")
print(f"Active Alerts: {len(dashboard['active_alerts'])}")
```
