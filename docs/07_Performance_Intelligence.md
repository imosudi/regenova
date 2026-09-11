# REAMP Phase 7 — Performance Intelligence Framework

## 1. Executive Summary & Objective

The **Performance Intelligence Framework** is the analytical core of REAMP responsible for answering the central operational question:
> *Is this renewable energy asset producing the exact electrical output that physical laws and engineering specifications predict under the prevailing environmental and operational conditions?*

Traditional SCADA systems rely on static thresholds or unadjusted generation numbers. When cloudy weather reduces solar generation by 70%, static alarms may falsely alert on an "inverter power drop," or operators may fail to notice an inverter operating at 60% capacity during clear, peak irradiance.

The REAMP Performance Intelligence Engine eliminates this ambiguity by computing:
1. **Physics-Grounded Expected Generation**:
   $$P_{expected} = f(\text{Asset Characteristics}, \text{Environmental Conditions}, \text{Operating State})$$
2. **Deterministic Performance Gap**:
   $$\Delta P = P_{expected} - P_{actual}$$
3. **Transparent Loss Attribution**:
   Decomposing the delta into distinct, non-overlapping physical, operational, and environmental components.
4. **Economic Quantification**:
   Translating lost kWh into realized financial impact under prevailing Power Purchase Agreements (PPA) or merchant tariff schedules.

---

## 2. Theoretical Foundations & Standards Compliance

The framework adheres to authoritative international engineering standards:
- **IEC 61724-1:2021** (*Photovoltaic system performance monitoring — Guidelines for measurement, data exchange and analysis*):
  Defines temperature-corrected performance ratio ($PR_{STC}$), weather adjustment methodology, and sensor accuracy requirements.
- **IEC 61400-12-1:2022** (*Wind energy generation systems — Power performance measurements of electricity producing wind turbines*):
  Defines normalized power curves, air density corrections, and aerodynamic coefficient ($C_p$) tracking.
- **IEC 62933-2-1:2017** (*Electrical energy storage (EES) systems — Part 2-1: Unit parameters and testing methods*):
  Defines round-trip efficiency ($RTE$), auxiliary load losses, and capacity fade tracking.
- **Sandia National Laboratories / PVsyst Cell Temperature Model**:
  Empirical formulations relating plane-of-array ($POA$) irradiance, ambient temperature ($T_{amb}$), and Nominal Module Operating Temperature ($NMOT$).

---

## 3. Architecture & Operational Integration

```
                            +-------------------------------------------+
                            |       REAMP Canonical Telemetry           |
                            |   (Edge / Fog / SCADA Ingestion Bus)      |
                            +---------------------+---------------------+
                                                  |
                                                  v
                            +-------------------------------------------+
                            |         Data Quality & Validation         |
                            |   (Flag Invalid / Missing / Frozen Data)  |
                            +---------------------+---------------------+
                                                  |
                                                  v
                            +-------------------------------------------+
                            |      Operational State Evaluator          |
                            | (RUNNING, CURTAILED, FAULT, MAINTENANCE)  |
                            +---------------------+---------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                             |                             |
                    v                             v                             v
       +-------------------------+   +-------------------------+   +-------------------------+
       |   Solar PV Model        |   |   Wind Turbine Model    |   |       BESS Model        |
       |  - IEC 61724-1 PR_stc   |   |  - IEC 61400-12-1 Curve |   |  - Round-Trip Efficiency|
       |  - Cell Temp Derate     |   |  - Air Density Normaliz.|   |  - Auxiliary HVAC Loss  |
       |  - Inverter Clipping    |   |  - Betz Limit Tracking  |   |  - Thermal De-rating    |
       +------------+------------+   +------------+------------+   +------------+------------+
                    |                             |                             |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
                            +-------------------------------------------+
                            |         Performance Engine Core           |
                            |  1. Calculate Expected Power (P_exp)      |
                            |  2. Calculate Performance Gap (Delta P)   |
                            |  3. Synthesize Confidence Score           |
                            +---------------------+---------------------+
                                                  |
                                                  v
                            +-------------------------------------------+
                            |    Waterfall Loss Attribution Engine      |
                            |  - Environmental Resource Variation       |
                            |  - Thermal Derating                       |
                            |  - Inverter Clipping                      |
                            |  - Utility Curtailment                    |
                            |  - Equipment Outage / Trip                |
                            |  - Controllable Underperformance          |
                            +---------------------+---------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v                                                           v
       +-------------------------+                                 +-------------------------+
       |   Financial Engine      |                                 |    Asset Health Engine  |
       |  - Lost Energy (kWh)    |                                 |   (Phase 6 Sub-Index)   |
       |  - Economic Loss ($)    |                                 |  Updates S_perf dimension|
       +-------------------------+                                 +-------------------------+
```

---

## 4. Rigorous Quality Gate Separation

The primary architectural challenge in performance intelligence is avoiding false positives and misattributions. The REAMP engine rigorously isolates four distinct operational phenomena:

| Operational Phenomenon | Telemetry Symptom | Engine Classification | Prescriptive Action |
| :--- | :--- | :--- | :--- |
| **Expected Environmental Variation** | Low irradiance ($G_{poa} < 200\ \text{W/m}^2$) or low wind ($v < 3\ \text{m/s}$); Actual power matches low physical expectation. | `RESOURCE_VARIATION` (Nominal $PR \approx 1.0$, $\Delta P \approx 0$) | None. Nominal operation under overcast or calm weather. |
| **True Under-Performance** | High irradiance ($950\ \text{W/m}^2$) or optimal wind ($10\ \text{m/s}$); Actual generation is significantly lower than physics predicts ($P_{act} \ll P_{exp}$). | `CONTROLLABLE_UNDERPERFORMANCE` (Low $PR$, Large positive $\Delta P$) | Flag soiling, string disconnection, blade icing, or tracking error; recommend inspection. |
| **Missing / Incomplete Data** | Null values, stale signals, communication timeout, or invalid sensor tags. | `MISSING_DATA` (Overall Confidence penalized to $< 0.50$) | Suppress false underperformance alarms; trigger telemetry repair work order. |
| **Asset Outage / Curtailment** | Operational state is `FAULT`, `TRIPPED`, `MAINTENANCE`, or `CURTAILED`. Actual generation is $0.0\ \text{kW}$. | `ASSET_OUTAGE` or `CURTAILMENT` (Attributed to availability, not physical underperformance) | Track availability downtime; do not corrupt degradation or health models with false degradation. |

---

## 5. Mathematical Model Formulations

### 5.1 Solar PV Expected Generation (IEC 61724-1)

#### 1. Effective Cell Temperature ($T_{cell}$)
When direct back-of-module temperature sensors are unavailable, cell temperature is estimated using the ambient temperature $T_{amb}$, plane-of-array irradiance $G_{poa}$, and the Nominal Module Operating Temperature ($NMOT$):
$$T_{cell} = T_{amb} + G_{poa} \cdot \left(\frac{NMOT - 20^\circ\text{C}}{800\ \text{W/m}^2}\right)$$

#### 2. Temperature Derating Factor ($f_{temp}$)
PV crystalline silicon modules experience a drop in bandgap efficiency at elevated temperatures:
$$f_{temp} = 1 + \gamma_{Pmp} \cdot (T_{cell} - 25^\circ\text{C})$$
where $\gamma_{Pmp}$ is the temperature coefficient of power (typically $-0.0035$ to $-0.0045\ /^\circ\text{C}$).

#### 3. Expected DC Power Output ($P_{dc,expected}$)
$$P_{dc,expected} = P_{dc,rated} \cdot \left(\frac{G_{poa}}{1000\ \text{W/m}^2}\right) \cdot f_{temp} \cdot \eta_{soiling} \cdot \eta_{wiring}$$

#### 4. Expected AC Power Output ($P_{ac,expected}$)
Taking into account inverter nominal conversion efficiency $\eta_{inv}$ and AC inverter nameplate capacity $P_{ac,rated}$:
$$P_{ac,uncapped} = P_{dc,expected} \cdot \eta_{inv}$$
$$P_{ac,expected} = \min(P_{ac,rated}, P_{ac,uncapped})$$

#### 5. Inverter Clipping Identification
When DC generation exceeds inverter AC capacity ($P_{ac,uncapped} > P_{ac,rated}$), the lost generation is attributed to deliberate engineering design (DC oversizing) rather than an equipment fault:
$$P_{loss,clipping} = P_{ac,uncapped} - P_{ac,expected}$$

#### 6. Weather-Adjusted Performance Ratio ($PR_{STC}$)
Standard Performance Ratio ($PR_{raw}$) reflects both weather and equipment efficiency:
$$PR_{raw} = \frac{P_{actual}}{P_{dc,rated} \cdot \left(\frac{G_{poa}}{1000\ \text{W/m}^2}\right)}$$
The temperature-compensated Performance Ratio ($PR_{STC}$) normalizes for ambient heat:
$$PR_{STC} = \frac{P_{actual}}{P_{dc,rated} \cdot \left(\frac{G_{poa}}{1000\ \text{W/m}^2}\right) \cdot \left[1 + \gamma_{Pmp} \cdot (T_{cell} - 25^\circ\text{C})\right]}$$

---

### 5.2 Wind Turbine Power Curve (IEC 61400-12-1)

Expected wind power follows a four-region aerodynamic curve:
1. **Region I ($0 \le v < v_{cut\_in}$)**:
   Below cut-in speed (typically $< 3.0\ \text{m/s}$), expected power is $0.0\ \text{kW}$.
2. **Region II ($v_{cut\_in} \le v < v_{rated}$)**:
   Aerodynamic power follows cubic wind speed adjusted for air density:
   $$P_{expected}(v) = 0.5 \cdot \rho \cdot A_{rotor} \cdot C_p(v) \cdot v^3$$
   where $\rho = \rho_0 \cdot \left(\frac{P_{baro}}{1013.25}\right) \cdot \left(\frac{288.15}{T_{amb} + 273.15}\right)$.
3. **Region III ($v_{rated} \le v \le v_{cut\_out}$)**:
   Active pitch control limits power to nameplate rating:
   $$P_{expected}(v) = P_{rated}$$
4. **Region IV ($v > v_{cut\_out}$)**:
   High-wind storm safety shutdown (typically $> 25.0\ \text{m/s}$):
   $$P_{expected}(v) = 0.0\ \text{kW}$$

---

### 5.3 BESS Throughput and Round-Trip Efficiency (IEC 62933-2-1)

BESS expected power and energy balance:
- During discharge:
  $$P_{expected} = \min(P_{setpoint}, P_{rated\_discharge}) \cdot \eta_{discharge} \cdot f_{temp}(T_{cell})$$
- Round-Trip Efficiency ($RTE$):
  $$RTE = \frac{\int P_{discharge}\ dt}{\int P_{charge}\ dt}$$
  Benchmarked against factory specification (typically $85.0\% - 92.0\%$). Losses are decomposed into electrochemical internal resistance ($I^2 R$), auxiliary HVAC cooling loads, and thermal de-rating.

---

## 6. Financial Loss Quantification

Every performance gap over an evaluation interval of duration $\Delta t$ (hours) is translated into economic loss:
$$\text{Lost Energy (kWh)} = \Delta P\ (\text{kW}) \cdot \Delta t\ (\text{hours})$$
$$\text{Financial Loss (\$)} = \text{Lost Energy (kWh)} \cdot \text{Tariff Rate (\$/kWh)}$$

The engine categorizes financial loss by responsibility:
- **Recoverable Losses** (Operator responsibility): Soiling, delayed maintenance, avoidable string trips.
- **Contractual Losses** (Offtaker / Grid operator responsibility): Utility curtailment with take-or-pay compensation clauses.
- **Design / Uncontrollable Losses**: Thermal derating, inverter clipping, solar resource scarcity.

---

## 7. Operational State & Confidence Synthesis

The engine calculates evaluation confidence ($0.0 - 1.0$) based on:
1. **Telemetry Freshness & Validity**: Penalized if irradiance, power, or temperature signals are flagged `STALE` or `INVALID`.
2. **Environmental Measurement Quality**: Penalized if pyranometer or anemometer telemetry is missing or out of plausible physical limits.
3. **State Consistency**: If an asset is reporting `RUNNING` but producing zero generation while current and voltage telemetry are null, confidence is downgraded and flagged as ambiguous.

---

## 8. Summary of Framework Deliverables

| Module | Location | Description |
| :--- | :--- | :--- |
| **Architecture Specification** | `docs/07_Performance_Intelligence.md` | Primary framework documentation and standard compliance. |
| **Performance Model Specification** | `docs/analytics/performance_model.md` | Mathematical formulations for Solar, Wind, and BESS. |
| **Loss Attribution Specification** | `docs/analytics/loss_attribution.md` | Taxonomy, formulas, and waterfall breakdown of losses. |
| **Data Models** | `reamp/performance/models.py` | Typed dataclasses for metrics, states, attributions, configs. |
| **Solar Model** | `reamp/performance/solar.py` | IEC 61724-1 reference implementation with NMOT cell temp. |
| **Wind Model** | `reamp/performance/wind.py` | IEC 61400-12-1 power curve with density normalization. |
| **BESS Model** | `reamp/performance/bess.py` | Round-trip efficiency and thermal de-rating model. |
| **Engine Orchestrator** | `reamp/performance/engine.py` | Central engine with state gating, confidence, and loss attribution. |
| **Test Verification Suite** | `tests/test_phase7_performance.py` | Automated tests executing all quality gate scenarios. |
| **Phase Completion Report** | `docs/PHASE_7_REPORT.md` | Formal phase report satisfying `AGENTS.md`. |
