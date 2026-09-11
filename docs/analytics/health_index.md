# REAMP — Asset Health Index Mathematical Formulation

**Document Identifier**: `REAMP-ANL-01`  
**Phase**: Phase 6 — Asset Health Model  
**Status**: Approved / Mathematical Specification  
**Last Updated**: 2026-09-11  

---

## 1. Formulation of the Composite Index

The **Asset Health Index ($AHI$)** is a normalized composite scalar metric:
$$AHI = \sum_{i=1}^M w_i^* \cdot S_i, \quad AHI \in [0.0, 100.0]$$

Where:
- $M \le 7$ is the number of available health dimensions.
- $S_i \in [0.0, 100.0]$ is the normalized sub-index score for dimension $i$ ($100.0 = \text{pristine condition}$, $0.0 = \text{failed/unusable}$).
- $w_i^*$ is the normalized weight of dimension $i$, satisfying $\sum_{i=1}^M w_i^* = 1.0$.

---

## 2. Mathematical Formulations of the 7 Sub-Indices

### 2.1 Performance Sub-Index ($S_{perf}$)
Quantifies energy conversion efficiency relative to weather-adjusted physics expectations:
- **Solar PV**: Uses temperature-compensated Performance Ratio ($PR_{STC}$):
  $$S_{perf} = \min\left(100.0, \max\left(0.0, 100.0 \times \frac{PR_{STC}}{PR_{nominal}}\right)\right)$$
  *(Typical nominal $PR_{nominal} = 0.82$. If measured $PR_{STC} = 0.656$, $S_{perf} = 80.0$)*.
- **Wind Energy**: Uses power coefficient efficiency ratio ($C_p / C_{p,expected}$).
- **BESS**: Uses measured Round-Trip Efficiency ($RTE / RTE_{nameplate}$).

---

### 2.2 Thermal Stress Sub-Index ($S_{therm}$)
Evaluates thermal acceleration of component aging using non-linear Arrhenius penalties:
$$S_{therm} = 100.0 \times \max\left(0.0, 1.0 - \left(\frac{\max(0.0, T_{measured} - T_{nominal})}{T_{critical} - T_{nominal}}\right)^\gamma\right)$$

Where:
- $T_{measured}$ is the highest operating temperature measured on the asset (e.g., inverter heatsink, transformer oil, or battery cell).
- $T_{nominal}$ is the continuous rated operating temperature limit (e.g., $65.0^\circ\text{C}$ for inverter heatsink).
- $T_{critical}$ is the maximum trip safety limit (e.g., $95.0^\circ\text{C}$).
- $\gamma \ge 1.5$ is the non-linear acceleration exponent modeling thermal fatigue.

*Example*: If $T_{measured} \le 65^\circ\text{C}$, $S_{therm} = 100.0$. If $T_{measured} = 80^\circ\text{C}$ with $\gamma = 1.5$, $S_{therm} \approx 64.6$. If $T_{measured} \ge 95^\circ\text{C}$, $S_{therm} = 0.0$.

---

### 2.3 Availability Sub-Index ($S_{avail}$)
Measures productive operating time over the evaluation window (e.g., 30 days):
$$S_{avail} = 100.0 \times \frac{t_{operational}}{t_{operational} + t_{unplanned\_outage}}$$
Planned maintenance windows are excluded from the denominator.

---

### 2.4 Communication Sub-Index ($S_{comm}$)
Quantifies the reliability and latency of the telemetry pipeline:
$$S_{comm} = 100.0 \times \left(1.0 - \text{PacketDropRate}\right) \times \max\left(0.0, 1.0 - \frac{\text{Latency}_{p95}}{2000\text{ ms}}\right)$$
If communication status is `OFFLINE`, $S_{comm} = 0.0$. If `BUFFERED`, $S_{comm} = 75.0$ (delayed but preserved).

---

### 2.5 Fault History Sub-Index ($S_{fault}$)
Applies an exponential time-decay penalty for operational trips and alarms over the preceding 14 days:
$$\text{Penalty} = \sum_{k=1}^K W_{severity}(A_k) \cdot e^{-\lambda (t_{now} - t_k)}$$
$$S_{fault} = \max(0.0, 100.0 - \text{Penalty})$$

Severity weights:
- `LOW`: $W = 2.0$
- `MEDIUM`: $W = 8.0$
- `HIGH`: $W = 25.0$
- `EMERGENCY`: $W = 60.0$
- Half-life parameter: $\lambda = \frac{\ln(2)}{3.0\text{ days}}$ (penalties decay by $50\%$ every 3 days).

---

### 2.6 Degradation Sub-Index ($S_{deg}$)
Accounts for irreversible hardware wear from calendar aging and operational throughput:
- **Calendar Degradation Component**:
  $$D_{cal} = \min\left(1.0, \frac{\text{Age in Years}}{\text{Design Life in Years}}\right)$$
- **Cycle Degradation Component (BESS / Mechanical Switches)**:
  $$D_{cyc} = \min\left(1.0, \frac{\text{Equivalent Full Cycles}}{\text{Rated Cycle Life}}\right)$$
- Composite Degradation Score:
  $$S_{deg} = 100.0 \times \left(1.0 - \max(D_{cal}, D_{cyc})\right)$$

---

### 2.7 Sensor Data Quality Sub-Index ($S_{dq}$)
Measures the trustworthiness of the underlying observation data feed:
$$S_{dq} = 100.0 \times \frac{\sum_{j=1}^N \mathbf{1}_{\{quality_j = \text{'VALID'}\}}}{N} \times \bar{C}_{sensor}$$
Where $\bar{C}_{sensor}$ is the mean sensor confidence score ($0.0–1.0$).

---

## 3. Technology Profile Weight Matrices

Different renewable energy technologies face fundamentally distinct degradation physics. The table below specifies REAMP's default weight distributions:

| Dimension | Symbol | Solar PV Inverter Profile | Wind Turbine Profile | BESS Storage Profile | Transformer / Substation |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Performance** | $S_{perf}$ | **0.25** | **0.25** | **0.20** | 0.05 |
| **Thermal Stress** | $S_{therm}$ | **0.25** | 0.15 | **0.30** | **0.35** |
| **Availability** | $S_{avail}$ | 0.15 | 0.15 | 0.10 | 0.15 |
| **Communication** | $S_{comm}$ | 0.05 | 0.05 | 0.05 | 0.05 |
| **Fault History** | $S_{fault}$ | 0.15 | **0.20** | 0.15 | **0.20** |
| **Degradation** | $S_{deg}$ | 0.10 | 0.15 | 0.15 | 0.15 |
| **Sensor Quality** | $S_{dq}$ | 0.05 | 0.05 | 0.05 | 0.05 |
| **Total Weight** | $\sum w_i$ | **1.00** | **1.00** | **1.00** | **1.00** |
