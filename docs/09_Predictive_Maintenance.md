# REAMP Phase 9 - Predictive Maintenance Framework

## 1. Executive Summary & Objective

The **REAMP Predictive Maintenance Framework** transforms real-time asset intelligence-synthesizing condition assessments (Phase 6), performance gaps (Phase 7), and multi-level anomalies (Phase 8)-into actionable maintenance predictions, failure horizons, and prioritized work orders.

Historically, renewable energy operations have relied on two inefficient extremes:
1. **Unplanned Reactive Maintenance**: Running equipment to failure, resulting in catastrophic collateral damage, emergency technician dispatches, and prolonged uncompensated downtime.
2. **Static Calendar-Based Maintenance**: Servicing assets on rigid calendar intervals (e.g. semi-annual inverter inspections) regardless of actual wear, leading to wasted technician hours and premature replacement of healthy components.

The REAMP framework implements an intelligent, evidence-grounded maintenance paradigm that models **failure probability ($P_f$)**, **degradation trajectories ($D(t)$)**, and **Remaining Useful Life (RUL)** while establishing an uncompromising **Quality Gate**:
> *The framework must never claim a precise failure prediction unless sufficient evidence exists. Where evidence is insufficient, return uncertainty explicitly.*

---

## 2. Four Maintenance Paradigms

To prevent operational ambiguity, the framework rigorously isolates and coordinates four distinct maintenance paradigms:

```
+-----------------------------------------------------------------------------------+
| 1. REACTIVE MAINTENANCE (Corrective / Unplanned)                                  |
| - Trigger: Hard equipment trip, breaker lockout, critical Level 1 anomaly event.   |
| - Objective: Rapid safe isolation, root-cause diagnosis, and emergency recovery.  |
| - Urgency: Immediate (Hours). Priority: P1 / P2.                                  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. CONDITION-BASED MAINTENANCE (CBM / Threshold-Driven)                           |
| - Trigger: Current condition index crosses static limit (e.g. Health Score < 50).  |
| - Objective: Remediate observed degraded state before sudden failure occurs.      |
| - Urgency: Urgent (Days). Priority: P2 / P3.                                      |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. PREDICTIVE MAINTENANCE (PdM / Trend & RUL Forecasting)                         |
| - Trigger: Statistically validated degradation trend extrapolating toward EOL.     |
| - Objective: Estimate Remaining Useful Life (RUL) with confidence intervals.      |
| - Urgency: Planned (Weeks). Priority: P2 / P3 / P4.                               |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 4. PRESCRIPTIVE DECISION SUPPORT (Optimized Actionable Dispatch)                  |
| - Trigger: Joint optimization of RUL, weather forecast, spares, and tariffs.     |
| - Objective: Recommend the exact operational window minimizing revenue loss.      |
| - Output: Fully pre-populated CMMS work order with parts and tooling checklist.   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Mathematical Foundations of Degradation & RUL

### 3.1 Weibull Hazard and Failure Probability Formulation
Asset life consumption follows the two-parameter Weibull distribution, widely validated in renewable energy reliability engineering (CIGRE, IEEE, IEC 60300-3-4):
- **Hazard Rate Function**:
  $$h(t) = \frac{\beta}{\eta} \left(\frac{t}{\eta}\right)^{\beta - 1}$$
- **Cumulative Failure Probability**:
  $$F(t) = P(T \le t) = 1 - e^{-(t / \eta)^\beta}$$
- **Reliability / Survival Function**:
  $$R(t) = e^{-(t / \eta)^\beta}$$
Where:
- $\beta$: Weibull shape parameter ($\beta = 1.0$ indicates random exponential failures; $\beta > 1.0$ indicates progressive wear-out aging). For solar inverters and wind gearboxes, $\beta \approx 2.5 - 3.5$.
- $\eta$: Characteristic life scale parameter (63.2% failure quantile).

### 3.2 Degradation Trajectory Extrapolation
Asset condition is tracked as an integrated health trajectory $H(t) \in [0.0, 100.0]$ over operating hours $t$:
$$H(t) = H_0 - \kappa_{deg} \cdot t^\gamma$$
The End-of-Life (EOL) threshold is defined at $H_{threshold} = 30.0$ (transition to `CRITICAL` condition).
When a monotonically declining trajectory is confirmed via linear or non-linear regression over $N \ge 5$ observation points:
$$\text{Degradation Rate } \kappa = \frac{d H}{d t} \approx \frac{\sum (t_i - \bar{t})(H_i - \bar{H})}{\sum (t_i - \bar{t})^2}$$
$$\text{Point Estimate RUL} = \frac{H_{current} - H_{threshold}}{|\kappa|}$$

### 3.3 Quality Gate: Explicit Uncertainty and Refusal of False Precision
A critical failure mode in predictive maintenance software is issuing false, overly confident RUL estimates (e.g. *"Bearing will fail in exactly 42 hours"*) when telemetry is sparse, noisy, or newly commissioned.

The REAMP engine enforces strict evidence sufficiency gates:
$$\text{Evidence Sufficiency} = \begin{cases}
\text{SUFFICIENT}, & \text{if } N_{points} \ge 5 \land R^2 \ge 0.70 \land \bar{c}_{telemetry} \ge 0.80 \\
\text{PARTIAL}, & \text{if } 3 \le N_{points} < 5 \lor (0.50 \le R^2 < 0.70) \\
\text{INSUFFICIENT}, & \text{if } N_{points} < 3 \lor \bar{c}_{telemetry} < 0.60
\end{cases}$$

- When `INSUFFICIENT`:
  - `predicted_rul_hours = None`
  - `uncertainty_flag = True`
  - Engine explicitly states: *"Insufficient degradation history to compute reliable RUL. Continue operational trending."*
- When `SUFFICIENT`:
  - Returns $[\text{RUL}_{lower}, \text{RUL}_{upper}]$ at $90\%$ confidence interval based on the standard error of regression slope $s_\kappa$.

---

## 4. Multi-Criteria Priority Model

Maintenance resources (technicians, cranes, specialized diagnostic equipment, spare inverters) are finite. The framework ranks candidate work orders using a composite **Risk Priority Score (RPS)**:

$$\text{RPS} = w_f \cdot S_{failure} + w_c \cdot S_{crit} + w_p \cdot S_{prod} + w_s \cdot S_{safe} + w_m \cdot S_{cost} + w_l \cdot S_{log}$$

Where $\sum w_i = 1.0$, and each factor is normalized to $[0.0, 100.0]$:
1. **Failure Probability Factor ($S_{failure}$)**: $100.0 \times P_f(\text{30-day horizon})$.
2. **Asset Criticality Factor ($S_{crit}$)**: High-voltage substation transformer ($100.0$) > Central Inverter ($75.0$) > String Inverter ($40.0$) > Combiner Box ($20.0$).
3. **Production Revenue Impact ($S_{prod}$)**: Expected lost energy value during remaining peak summer/wind months if unaddressed.
4. **Personnel Safety Hazard ($S_{safe}$)**: Fire risk, arc flash risk, mechanical structural fatigue ($0.0 - 100.0$).
5. **Maintenance Avoided Cost ($S_{cost}$)**: Financial ratio of preventative component repair vs catastrophic secondary replacement.
6. **Logistics & Spares Readiness ($S_{log}$)**: Penalized if replacement IGBTs or bearings are out of stock or have multi-week lead times.

### 4.1 Safety Override Gate
Regardless of economic score, if $S_{safe} \ge 85.0$ (e.g. thermal runaway or dielectric breakdown warning), the priority is automatically forced to **$P1$ (Critical Emergency)**.

### 4.2 Priority Tier Mapping

| Tier | Priority Code | Score Range | Operational Response Horizon | Workflow |
| :--- | :--- | :--- | :--- | :--- |
| **Emergency** | **P1** | $\text{RPS} \ge 80.0$ or Safety Override | $< 4$ Hours | Automated on-call technician dispatch; derate/trip asset if unattended. |
| **Urgent** | **P2** | $60.0 \le \text{RPS} < 80.0$ | $< 48$ Hours | Fast-track work order; allocate in-stock spares. |
| **Preventative**| **P3** | $40.0 \le \text{RPS} < 60.0$ | $< 14$ Days | Bundle with scheduled plant maintenance round; inspect during low-generation window. |
| **Routine** | **P4** | $\text{RPS} < 40.0$ | $< 60$ Days | Deferrable maintenance; routine cleaning and lubrication. |

---

## 5. Integration with Phase 10 CMMS and Digital Twin

The outputs of the predictive maintenance engine directly feed downstream operational workflows:
- **Phase 10 CMMS Integration**: Automatically constructs draft work orders populated with:
  - Asset ID, component tags, and physical location;
  - Recommended action and tooling checklist;
  - Required spare part SKU codes and inventory warehouse status;
  - Target completion date derived from RUL forecast.
- **Phase 12 Digital Twin**: Injects expected failure horizons into the asset digital twin state machine, updating future capacity forecasts in plant dispatch simulations.

---

## 6. Summary of Phase Deliverables

| Module | File Path | Purpose |
| :--- | :--- | :--- |
| **Framework Specification** | `docs/09_Predictive_Maintenance.md` | Primary architecture, four paradigms, and quality gates. |
| **Degradation Model Specification**| `docs/maintenance/maintenance_model.md` | Weibull hazard, RUL mathematics, and uncertainty criteria. |
| **Priority Model Specification** | `docs/maintenance/priority_model.md` | Multi-criteria priority formulas and tier assignments. |
| **Data Models** | `reamp/maintenance/models.py` | Typed dataclasses (`RULPrediction`, `MaintenanceRecommendation`). |
| **Degradation Engine** | `reamp/maintenance/degradation.py` | Trajectory regression, Weibull hazard, and RUL estimator. |
| **Priority Engine** | `reamp/maintenance/priority.py` | Multi-criteria risk scoring with safety override. |
| **Maintenance Orchestrator** | `reamp/maintenance/engine.py` | Paradigm arbitration and recommendation builder. |
| **Automated Verification Suite** | `tests/test_phase9_maintenance.py` | Verification of four paradigms, uncertainty gating, and priority tiers. |
| **Phase Completion Report** | `docs/PHASE_9_REPORT.md` | Formal phase report satisfying `AGENTS.md`. |
