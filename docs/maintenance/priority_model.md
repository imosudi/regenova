# REAMP Maintenance Priority and Risk Ranking Model

## 1. Overview & Operational Need

Renewable energy power plants frequently operate with hundreds of concurrent generation assets spread across remote geographic regions. Plant operators and O&M contractors cannot dispatch technicians to every minor anomaly or sub-optimal reading.

The **REAMP Priority Model** provides a mathematically rigorous, configurable multi-criteria decision framework that ranks maintenance actions based on true operational and commercial risk.

---

## 2. Multi-Criteria Priority Formulation

The composite **Risk Priority Score (RPS $\in [0.0, 100.0]$)** is formulated as a normalized multi-attribute utility function:

$$\text{RPS} = w_f \cdot S_{failure} + w_c \cdot S_{crit} + w_p \cdot S_{prod} + w_s \cdot S_{safe} + w_m \cdot S_{cost} + w_l \cdot S_{log}$$

Subject to:
$$\sum_{i \in \{f, c, p, s, m, l\}} w_i = 1.0, \quad w_i \ge 0$$

### 2.1 Criteria Definitions and Scoring Functions

| Criterion | Weight ($w_i$) | Physical Meaning | Normalization Formula ($0.0 - 100.0$) |
| :--- | :--- | :--- | :--- |
| **Failure Probability ($S_{failure}$)** | $0.25$ | Probability of in-service failure within 30 days. | $S_{failure} = 100.0 \times P_f(30\text{d} \mid t_0)$ |
| **Asset Criticality ($S_{crit}$)** | $0.20$ | Topological importance to plant-wide generation. | Main Substation Transformer: $100.0$<br>Central Inverter / BESS Container: $75.0$<br>String Inverter / Feeder: $40.0$<br>Combiner Box / Tracker: $20.0$ |
| **Production Revenue Impact ($S_{prod}$)** | $0.20$ | Commercial loss rate under prevailing PPA tariff. | $S_{prod} = 100.0 \times \min\left(1.0, \frac{\text{Lost Generation Value (\$/day)}}{\$1,000.00}\right)$ |
| **Personnel & Environmental Safety ($S_{safe}$)** | $0.15$ | Threat to human life, arc flash hazard, fire risk. | Fire / Arc Flash Risk: $100.0$<br>Insulation Breakdown: $75.0$<br>Cooling Degradation: $40.0$<br>Nominal Safety: $0.0$ |
| **Maintenance Cost Avoidance ($S_{cost}$)** | $0.10$ | Ratio of catastrophic replacement cost to minor servicing. | Minor preventative intervention avoiding major rebuild: $100.0$<br>Routine cleaning: $20.0$ |
| **Spares & Logistics Readiness ($S_{log}$)** | $0.10$ | Availability of technicians, tooling, and parts. | In-stock on-site with certified crew: $100.0$<br>Long-lead procurement ($> 4$ weeks): $25.0$ |

---

## 3. Safety Override Rule

Human life and severe fire hazards strictly supersede commercial optimization:

$$\text{If } S_{safe} \ge 85.0 \implies \text{Priority Tier} = \mathbf{P1\ (CRITICAL)}$$

Even if an asset has low nameplate capacity or low financial revenue impact, a confirmed thermal runaway warning or high-voltage insulation dielectric breakdown immediately forces an emergency ticket.

---

## 4. Priority Tiers and SLA Workflows

| Tier | Priority Code | Score Threshold | Maximum Dispatch SLA | Prescriptive Operational Workflow |
| :--- | :--- | :--- | :--- | :--- |
| **Emergency** | **P1** | $\text{RPS} \ge 80.0$ or Safety Override | $< 4$ Hours | Immediate automated push alert to on-call field lead. If asset is unattended and thermal/safety limits are breached, signal supervisory trip/derate command. |
| **Urgent** | **P2** | $60.0 \le \text{RPS} < 80.0$ | $< 48$ Hours | Fast-track work order. Reserve warehouse spares (IGBT modules, contactors). Schedule crew dispatch during low-irradiance / low-wind morning hours. |
| **Preventative** | **P3** | $40.0 \le \text{RPS} < 60.0$ | $< 14$ Days | Queue for upcoming bi-weekly maintenance run. Bundle with nearby string checks to minimize truck rolls. |
| **Routine** | **P4** | $\text{RPS} < 40.0$ | $< 60$ Days | Deferrable maintenance. Log to seasonal maintenance list (e.g. array washing, vegetation mowing, air filter change). |

---

## 5. Mathematical Explainability & Provenance

In accordance with `AGENTS.md` Rule 8, every generated maintenance recommendation includes a complete mathematical factor breakdown:
- The exact contributing score $w_i \cdot S_i$ for each of the six dimensions;
- Verification that $\sum (w_i \cdot S_i) = \text{RPS}$;
- The explicit rule triggering priority assignment.
