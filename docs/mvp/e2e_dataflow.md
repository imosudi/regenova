# REAMP MVP — End-to-End Dataflow & Pipeline Specification

## 1. Overview of the 10-Stage Pipeline

The REAMP architecture bridges physical sensor hardware on the edge to executive financial and operational governance. The end-to-end integration is validated across 10 sequential pipeline stages:

```
[1. SENSOR]
   │  Analog / Digital readings (Irradiance, Temperature, Voltage, Current, Vibration)
   ▼
[2. GATEWAY]
   │  Edge sampling, Modbus RTU/TCP register polling, timestamp normalization
   ▼
[3. INGESTION]
   │  HMAC-SHA256 signature verification, anti-replay nonce validation, rate limiting
   ▼
[4. STORAGE]
   │  Local SQLite WAL buffering, central time-series aggregation, deduplication
   ▼
[5. ANALYTICS]
   │  IEC 61724-1 solar modeling, Sandia cell temperature, expected power & thermal state
   ▼
[6. HEALTH]
   │  Deterministic Component & Composite Health Index (HI ∈ [0, 100]), baseline derating
   ▼
[7. ANOMALY]
   │  L1 threshold rules, L2 EWMA/CUSUM shift detection, L3 Isolation Forest, L4 physical residuals
   ▼
[8. ALERT]
   │  Severity classification (INFO, WARNING, CRITICAL), deduplication, notification dispatch
   ▼
[9. MAINTENANCE]
   │  Predictive Weibull RUL estimation, CMMS work-order drafting, HITL approval gate
   ▼
[10. REPORT]
      Executive generation dashboard, loss attribution ($), avoided cost calculation, audit trail
```

---

## 2. Detailed Stage Specifications

### Stage 1: Sensor Hardware Layer
- **Physical Devices**:
  - Secondary standard thermopile pyranometer ($G_{\text{POA}}$ in $\text{W/m}^2$).
  - Platinum resistance temperature detector (PT100) mounted on inverter IGBT heatsink ($T_{\text{heatsink}}$ in $^\circ\text{C}$).
  - Calibrated revenue-grade power transducers ($P_{\text{dc}}$, $P_{\text{ac}}$ in $\text{kW}$).
- **Sample Rate**: $1\text{ Hz}$ to $10\text{ s}$ edge acquisition cycle.

### Stage 2: Edge Gateway Normalization
- **Gateway Role**: Modbus TCP/RTU polling engine (`reamp.edge.modbus`).
- **Data Structuring**: Packs heterogeneous raw registers into a normalized IEEE floating-point payload schema:
  ```json
  {
    "device_id": "GATEWAY-MOJAVE-01",
    "asset_id": "ASSET-INV-01",
    "timestamp": 1726084800.0,
    "measurements": {
      "poa_irradiance": 850.0,
      "ambient_temp": 28.0,
      "dc_power_kw": 2100.0,
      "ac_power_kw": 1850.0,
      "heatsink_temp": 78.0
    }
  }
  ```

### Stage 3: Security & Cryptographic Ingestion
- **Cryptographic Authentication**: The gateway signs the canonical JSON representation using a pre-shared device secret via HMAC-SHA256.
- **Header Envelope**:
  - `X-Device-ID`: Gateway hardware identifier.
  - `X-Signature`: HMAC-SHA256 digest.
  - `X-Nonce`: Unique monotonic transaction token preventing replay attacks.
  - `X-Timestamp`: Unix epoch timestamp to guard against clock skew ($|\Delta t| \le 300\text{s}$).
- **Defense Validation**: Replay cache inspects nonce; token bucket rate-limiter prevents denial-of-service.

### Stage 4: Resilient Time-Series Storage
- **Buffering & Persistence**: Packets are committed to an ACID SQLite database buffer with write-ahead logging (WAL) mode enabled.
- **Guarantees**: Provides zero-data-loss store-and-forward capability during transient wide-area network disconnects.

### Stage 5: Physics-Informed Digital Twin Analytics
- **Simulation**: First-principles physical models (`reamp.digital_twin.physics`).
- **Expected Value Computation**:
  - $P_{\text{expected}} = P_{\text{dc}} \times \eta_{\text{inv}}(P_{\text{dc}})$.
  - $T_{\text{expected}} = T_{\text{ambient}} + \Delta T_{\text{rise}}(P_{\text{loss}}, \dot{V}_{\text{air}})$.
- **Residual Evaluation**:
  - Power Residual: $\Delta P = P_{\text{measured}} - P_{\text{expected}} = -250\text{ kW}$.
  - Heatsink Thermal Residual: $\Delta T = 78.0^\circ\text{C} - 54.0^\circ\text{C} = +24.0^\circ\text{C}$.

### Stage 6: Deterministic Health Index Derating
- **Subsystem Breakdown**:
  - Thermal / Cooling Subsystem Health: $HI_{\text{cooling}} = 100 - (\Delta T \times 2.1) = 49.6$.
  - Electrical Conversion Subsystem Health: $HI_{\text{elec}} = 78.2$.
- **Composite Asset Health Index**:
  $$HI_{\text{composite}} = \sum w_i \cdot HI_i = 62.4 \quad (\text{Derated from baseline } 95.0)$$

### Stage 7: Multi-Level Anomaly Detection
- **Level 1 (Rule-Based)**: Flags $T_{\text{heatsink}} > 75.0^\circ\text{C}$ (Threshold violation).
- **Level 2 (Statistical CUSUM)**: Detects statistically significant positive drift in thermal resistance ($S_n^+ > h$).
- **Level 3 (Unsupervised Isolation Forest)**: Flags multivariate anomaly score $s(x, n) = 0.74 > 0.60$.
- **Level 4 (Physical Residuals)**: Confirms $\Delta T = +24.0^\circ\text{C} > \text{threshold}(8.0^\circ\text{C})$.

### Stage 8: Real-Time Alert Dispatch
- **Alert Deduplication**: Correlates related alarms into a singular active incident.
- **Alert Model**:
  - `alert_id`: `ALT-MOJ-2026-0001`
  - `severity`: `CRITICAL`
  - `title`: `Inverter Heatsink Thermal Dissipation Failure`
  - `timestamp`: Current UTC timestamp
  - `status`: `ACTIVE`

### Stage 9: Predictive Maintenance & HITL CMMS Workflow
- **Weibull Reliability Assessment**: Calculates conditional probability of failure within 72 hours: $R(t) = e^{-(t/\eta)^\beta}$.
- **Work Order Auto-Generation**:
  - Generated Order: `WO-2026-0042`
  - Title: `Emergency Inspection and Replacement of Inverter Blower Fans`
  - Initial State: `PENDING_HITL_APPROVAL` (Mandatory safety gate).
- **Human-in-the-Loop Approval**:
  - Unauthorized dispatch attempts immediately fail with `PermissionError`.
  - Plant engineer approves via signed operational token.
  - State advances: `APPROVED` $\to$ `PARTS_RESERVED` $\to$ `DISPATCHED` $\to$ `RESOLVED` $\to$ `CLOSED`.

### Stage 10: Executive & Operational Governance Reporting
- **Financial Attribution**:
  - Curtailment Loss: $340.00\text{ USD}$ (Energy loss at contract PPA).
  - Avoided Catastrophic Replacement Cost: $15,000.00\text{ USD}$ (Prevented IGBT module thermal explosion).
- **Audit Lineage**:
  - Cryptographic append-only log links every action: Telemetry $\to$ Anomaly $\to$ Alert $\to$ Human Sign-off $\to$ Resolution.
  - Integrity validated via SHA-256 hash chaining ($H_i = \text{SHA256}(H_{i-1} \parallel \text{Event}_i)$).
