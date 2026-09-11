# REAMP Maintenance Modeling: Failure Probability, Degradation, and RUL

## 1. Overview & Principles

The REAMP predictive maintenance model transforms telemetry time-series and health assessments into failure horizons and remaining operational life forecasts.

In compliance with [`AGENTS.md`](file:///home/mosud/Documents/dev/regenova/AGENTS.md) Rule 3 (*Evidence over assumptions*) and Rule 8 (*AI safety and explainability*), the framework grounds all maintenance predictions in physical failure mechanisms, statistical hazard theory, and rigorous uncertainty propagation.

---

## 2. Component Failure Mechanisms

Predictive degradation tracking is mapped to discrete physical failure modes across renewable assets:

| Asset Subsystem | Primary Degradation Mechanism | Observable Condition Indicator | EOL Failure Threshold |
| :--- | :--- | :--- | :--- |
| **Solar Inverter DC-Link** | Electrolytic capacitor electrolyte vaporisation / drying. | Equivalent Series Resistance (ESR) increase; DC ripple voltage rise. | $\Delta \text{ESR} \ge +100\%$ or Ripple $> 8.0\ \text{V}$ |
| **Inverter IGBT Module** | Thermal-mechanical solder fatigue and wire-bond lift-off from power cycling. | Junction-to-case thermal resistance $R_{th,jc}$ increase; collector-emitter saturation voltage $V_{ce,sat}$ drift. | $\Delta R_{th} \ge +20\%$ or Heatsink Temp $> 95.0^\circ\text{C}$ |
| **PV Strings & Modules** | Potential Induced Degradation (PID), delamination, cell interconnect micro-cracking. | Weather-adjusted $PR_{STC}$ decline; open-circuit voltage drop. | $PR_{STC} \le 0.70$ ($30\%$ yield deficit) |
| **Wind Turbine Gearbox** | Rolling element bearing spalling, gear tooth micropitting, oil oxidation. | High-frequency vibration demodulation (envelope acceleration); debris particle count in lube oil. | RMS Vibration $> 4.5\ \text{mm/s}$ (ISO 10816-3) |
| **Wind Turbine Blade** | Leading edge erosion, structural composite delamination, ice accumulation. | Aerodynamic power coefficient $C_p$ derating; blade pitch asymmetry. | $C_p$ drop $> 15\%$ at rated wind |
| **BESS Battery Rack** | Solid Electrolyte Interphase (SEI) growth, cathode transition metal dissolution, lithium plating. | Capacity fade (State of Health $SOH$); internal DC resistance rise. | $SOH \le 75.0\%$ of nominal capacity |

---

## 3. Mathematical Formulations

### 3.1 Weibull Reliability & Failure Probability

The operational lifetime of renewable electromechanical components is modeled via the two-parameter Weibull distribution:
$$F(t) = P(T \le t) = 1 - e^{-\left(\frac{t}{\eta}\right)^\beta}$$
$$R(t) = 1 - F(t) = e^{-\left(\frac{t}{\eta}\right)^\beta}$$
The instantaneous hazard rate (failure rate) is:
$$h(t) = \frac{f(t)}{R(t)} = \frac{\beta}{\eta} \left(\frac{t}{\eta}\right)^{\beta - 1}$$

- When $\beta < 1.0$: Early "infant mortality" failure regime.
- When $\beta = 1.0$: Constant random failure rate (exponential distribution).
- When $\beta > 1.0$: Progressive wear-out degradation regime (typical for inverters and rotating equipment: $\beta \in [2.0, 3.5]$).

#### Conditional Failure Probability in Horizon $\Delta t$
Given that an asset has already survived operating time $t_0$, the conditional probability of failing in the upcoming window $\Delta t$ (e.g. 30 days $\approx 720$ hours) is:
$$P_f(\Delta t \mid t_0) = 1 - \frac{R(t_0 + \Delta t)}{R(t_0)} = 1 - e^{-\left[\left(\frac{t_0 + \Delta t}{\eta}\right)^\beta - \left(\frac{t_0}{\eta}\right)^\beta\right]}$$

---

### 3.2 Degradation Trajectory Regression and RUL

Let $(t_1, H_1), (t_2, H_2), \dots, (t_n, H_n)$ be historical health index observations (Phase 6 $AHI \in [0.0, 100.0]$) at operating hours $t_i$.

#### 1. Linear Degradation Rate Model
When degradation proceeds steadily over time:
$$H(t) = H_0 - \kappa \cdot t$$
The ordinary least-squares (OLS) slope $\kappa$ is computed as:
$$\kappa = \frac{\sum_{i=1}^n (t_i - \bar{t})(H_i - \bar{H})}{\sum_{i=1}^n (t_i - \bar{t})^2}$$
The standard error of the slope $s_\kappa$ is:
$$s_\kappa = \sqrt{\frac{\sum_{i=1}^n (H_i - \hat{H}_i)^2 / (n - 2)}{\sum_{i=1}^n (t_i - \bar{t})^2}}$$
Coefficient of determination:
$$R^2 = 1 - \frac{\sum_{i=1}^n (H_i - \hat{H}_i)^2}{\sum_{i=1}^n (H_i - \bar{H})^2}$$

#### 2. Remaining Useful Life (RUL) Point Estimate
Let $H_{current}$ be the latest evaluated health score and $H_{EOL} = 30.0$ be the end-of-life threshold:
$$\text{RUL}_{point} = \frac{H_{current} - H_{EOL}}{|\kappa|}$$

#### 3. Bounded Confidence Intervals
To account for regression uncertainty and stochastic noise:
$$\text{RUL}_{lower} = \frac{H_{current} - H_{EOL}}{|\kappa| + t_{crit} \cdot s_\kappa}$$
$$\text{RUL}_{upper} = \frac{H_{current} - H_{EOL}}{\max(0.0001, |\kappa| - t_{crit} \cdot s_\kappa)}$$
Where $t_{crit} = 1.645$ for a two-sided $90\%$ confidence interval.

---

## 4. Quality Gate: Evidence Sufficiency & Explicit Uncertainty

To fulfill `AGENTS.md` Rule 9 (*No fake completion*) and the Phase 9 Quality Gate:
> *"The framework must never claim a precise failure prediction unless sufficient evidence exists. Where evidence is insufficient, return uncertainty explicitly."*

The engine rigorously evaluates **Evidence Sufficiency**:

$$\text{Evidence Sufficiency} = \begin{cases}
\text{SUFFICIENT}, & \text{if } n \ge 5 \land R^2 \ge 0.70 \land \kappa < -0.0001 \land \bar{c} \ge 0.80 \\
\text{PARTIAL}, & \text{if } 3 \le n < 5 \lor (0.50 \le R^2 < 0.70) \\
\text{INSUFFICIENT}, & \text{if } n < 3 \lor R^2 < 0.50 \lor \bar{c} < 0.60 \lor \kappa \ge 0
\end{cases}$$

### Operational Action on Insufficient Evidence
When evidence sufficiency is `INSUFFICIENT`:
1. `predicted_rul_hours` is returned as `None` (no fabricated numeric prediction).
2. `rul_confidence_interval` is returned as `(0.0, 0.0)`.
3. `uncertainty_flag` is set to `True`.
4. Explanation states clearly:
   > *"Insufficient degradation history to establish a statistically valid RUL forecast ($n < 5$ or $R^2 < 0.70$). Condition-based monitoring active; continue baseline observation."*
