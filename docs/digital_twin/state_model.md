# REAMP Digital Twin State Space and Physics Model Specifications

## 1. Overview

This document specifies the mathematical formulations, data schemas, and state space representations for the REAMP Digital Twin, with primary focus on a utility-scale Solar Photovoltaic Inverter reference asset.

---

## 2. Mathematical Physics Models (Expected State)

The digital twin executes continuous first-principles physics models to compute expected nominal operation given instantaneous environmental inputs:
- $G_{\text{poa}}$: Plane-of-Array Irradiance ($\text{W/m}^2$)
- $T_{\text{amb}}$: Ambient Air Temperature ($^\circ\text{C}$)
- $v_{\text{wind}}$: Ambient Wind Speed ($\text{m/s}$)

### 2.1 PV Array Cell Temperature ($T_{\text{cell}}$)
Estimated via the standard King / Sandia photovoltaic thermal formulation:
$$T_{\text{cell}} = T_{\text{amb}} + G_{\text{poa}} \times \exp\left( -a - b \times v_{\text{wind}} \right) + \frac{G_{\text{poa}}}{G_0} \times \Delta T_{\text{cond}}$$
where $a = -3.56$, $b = -0.075$, and $\Delta T_{\text{cond}} \approx 3^\circ\text{C}$ for open-rack silicon modules.

### 2.2 Expected DC Array Generation ($P_{\text{dc,expected}}$)
$$P_{\text{dc,expected}} = P_{\text{dc,rated}} \times \left( \frac{G_{\text{poa}}}{1000.0} \right) \times \left[ 1.0 + \gamma \times (T_{\text{cell}} - 25.0) \right] \times \eta_{\text{soiling}}$$
where:
- $P_{\text{dc,rated}}$ is total connected DC module capacity ($\text{kW}$);
- $\gamma \approx -0.0038 \, ( -0.38\%/^\circ\text{C})$ is the module power temperature coefficient;
- $\eta_{\text{soiling}}$ is estimated array clean factor ($0.98$ nominal).

### 2.3 Expected Inverter Efficiency Curve ($\eta_{\text{inv}}$)
Modeled via the 3-parameter empirical inverter conversion curve:
$$\eta_{\text{inv}}(p) = \frac{p}{p + p_0 + k \cdot p^2}$$
where $p = P_{\text{dc}} / P_{\text{ac,rated}}$, $p_0 \approx 0.008$ represents inverter tare/self-consumption losses, and $k \approx 0.025$ represents internal resistive conduction losses. At nominal capacity ($p \approx 1.0$), $\eta_{\text{inv}} \approx 96.8\text{--}98.5\%$.

### 2.4 Expected AC Generation ($P_{\text{ac,expected}}$)
$$P_{\text{ac,expected}} = \min\left( P_{\text{ac,rated}}, \, P_{\text{dc,expected}} \times \eta_{\text{inv}}\left(\frac{P_{\text{dc,expected}}}{P_{\text{ac,rated}}}\right) \right)$$
If $P_{\text{dc,expected}} \times \eta_{\text{inv}} > P_{\text{ac,rated}}$, the inverter operates in clipping mode, and $P_{\text{ac,expected}}$ is capped at nameplate rating $P_{\text{ac,rated}}$.

### 2.5 Expected Heatsink Temperature ($T_{\text{heatsink,expected}}$)
Modeled using a lumped-parameter thermal dissipation network:
$$P_{\text{loss}} = \max\left( 0.0, \, P_{\text{dc,expected}} - P_{\text{ac,expected}} \right)$$
$$T_{\text{heatsink,expected}} = T_{\text{amb}} + P_{\text{loss}} \times R_{\text{th}}$$
where $R_{\text{th}}$ ($^\circ\text{C/kW}$) is the effective thermal resistance of the heatsink and forced-air cooling fan array ($R_{\text{th}} \approx 1.8^\circ\text{C/kW}$ for a $500\text{ kW}$ inverter with active fans).

---

## 3. Residual Formulation & Early Degradation Indices

The digital twin continuously tracks discrepancies between physical observations and expected states:

| Residual | Mathematical Formula | Nominal Bound | Degradation Diagnosis When Exceeded |
| :--- | :--- | :--- | :--- |
| **Power Residual ($\Delta P$)** | $P_{\text{ac,actual}} - P_{\text{ac,expected}}$ | $[-15.0, +15.0]\text{ kW}$ | Negative gap ($\Delta P < -25\text{ kW}$) indicates string fuse blow, severe soiling, or MPPT tracking failure. |
| **Thermal Residual ($\Delta T$)**| $T_{\text{heatsink,actual}} - T_{\text{heatsink,expected}}$ | $[-4.0, +4.0]^\circ\text{C}$ | Positive gap ($\Delta T > +8^\circ\text{C}$) indicates cooling fan bearing wear, clogged air intake filters, or dried thermal paste. |
| **Efficiency Residual ($\Delta \eta$)**| $\eta_{\text{actual}} - \eta_{\text{expected}}$ | $[-0.01, +0.01]$ | Negative gap ($\Delta \eta < -0.025$) indicates IGBT switching degradation or DC link capacitor wear. |

---

## 4. Consolidated State Space Schema (`TwinFullState`)

A full digital twin snapshot synthesizes all 10 dimensions:

```json
{
  "timestamp": "2026-09-11T20:30:00Z",
  "sync_status": "SYNCHRONIZED",
  "identity": {
    "asset_id": "INV-WEST-01",
    "serial_number": "SMA-SC-500-CP-XT-8819",
    "manufacturer": "SMA Solar Technology",
    "model": "Sunny Central 500CP XT",
    "site_id": "SITE-SOLAR-PARK-B",
    "subsystem_ids": ["FAN-ARRAY-01", "IGBT-BRIDGE-A", "IGBT-BRIDGE-B", "DC-CAPACITORS"]
  },
  "configuration": {
    "rated_ac_power_kw": 500.0,
    "rated_dc_power_kw": 625.0,
    "nominal_voltage_ac": 400.0,
    "mppt_voltage_min": 550.0,
    "mppt_voltage_max": 850.0,
    "thermal_resistance_c_per_kw": 1.8,
    "temp_coefficient_pct_per_c": -0.0038
  },
  "telemetry": {
    "power_ac_kw": 462.4,
    "power_dc_kw": 475.2,
    "voltage_dc_v": 680.0,
    "current_dc_a": 698.8,
    "voltage_ac_v": 402.1,
    "temperature_heatsink_c": 64.2,
    "ambient_temperature_c": 28.0,
    "poa_irradiance_w_per_m2": 820.0,
    "operating_mode": "FEED_IN_NORMAL"
  },
  "expected_state": {
    "expected_power_ac_kw": 468.1,
    "expected_efficiency": 0.985,
    "expected_heatsink_temp_c": 56.4
  },
  "residuals": {
    "power_residual_kw": -5.7,
    "temperature_residual_c": 7.8,
    "efficiency_residual": -0.012
  },
  "health": {
    "composite_health_index": 76.5,
    "component_health": {
      "igbt": 82.0,
      "cooling": 68.0,
      "capacitors": 79.5
    }
  },
  "performance": {
    "performance_ratio": 0.812,
    "availability": 1.0,
    "curtailment_active": false
  },
  "anomalies": {
    "active_anomaly_count": 1,
    "active_anomalies": [
      {
        "anomaly_id": "ANOM-20260911-0088",
        "severity": "MAJOR",
        "root_cause": "COOLING_FAN_DEGRADATION"
      }
    ]
  },
  "maintenance": {
    "active_work_order_id": "WO-E984CA12",
    "work_order_status": "APPROVED",
    "assigned_technician": "Alice Morgan (TECH-001)",
    "historical_downtime_hours": 12.5
  },
  "predicted": {
    "predicted_rul_hours": 720.0,
    "rul_confidence_interval": [680.0, 760.0],
    "failure_probability_30d": 0.28,
    "risk_tier": "HIGH"
  }
}
```
