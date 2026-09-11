# REAMP Anomaly Detection Mathematical Formulations and Algorithmic Methods

## 1. Overview

This document specifies the mathematical formulations, physical constraints, and algorithmic logic underlying the four tiers of the REAMP Anomaly Detection Framework.

---

## 2. Level 1: Deterministic Rule-Based Methods

### 2.1 Threshold Violations
Evaluates scalar metrics against configured operational envelope boundaries $[\theta_{min}, \theta_{max}]$:
$$A_{threshold} = \begin{cases} 
\text{TRUE}, & \text{if } x_t > \theta_{max} \text{ or } x_t < \theta_{min} \\
\text{FALSE}, & \text{otherwise}
\end{cases}$$
- **Severity Mapping**:
  - $\theta_{warning} < x_t \le \theta_{critical} \implies \text{Severity: } \text{HIGH}$
  - $x_t > \theta_{critical} \implies \text{Severity: } \text{CRITICAL}$

### 2.2 Unexpected Shutdown Detection
Identifies sudden complete loss of generation when primary environmental drivers indicate strong generating potential:
$$A_{shutdown} = \begin{cases}
\text{TRUE}, & \text{if } S_{op} = \text{RUNNING} \land P_{actual} \le P_{idle\_threshold} \land E_{resource} \ge E_{trigger\_threshold} \\
\text{FALSE}, & \text{otherwise}
\end{cases}$$
- **Solar PV Parameters**: $P_{actual} \le 1.0\ \text{kW} \land G_{poa} \ge 250.0\ \text{W/m}^2$.
- **Wind Parameters**: $P_{actual} \le 5.0\ \text{kW} \land v_{wind} \ge 4.0\ \text{m/s}$.

### 2.3 Communication Timeout Watchdog
Monitors elapsed time $\Delta \tau = t_{current} - t_{last\_heartbeat}$:
$$A_{comm\_timeout} = \begin{cases}
\text{TRUE}, & \text{if } \Delta \tau > \tau_{timeout} \\
\text{FALSE}, & \text{otherwise}
\end{cases}$$
- Default threshold: $\tau_{timeout} = 60.0\ \text{seconds}$ (configurable per adapter).

### 2.4 Physical Impossibility Constraints
Detects broken sensors, calibration inversions, and signal transmission corruption:
- $G_{poa} < -5.0\ \text{W/m}^2$ (negative solar irradiance)
- $P_{ac} > 2.5 \times P_{rated}$ (impossible power surge)
- $T_{cell} > 130.0^\circ\text{C}$ or $T_{cell} < -50.0^\circ\text{C}$ (thermocouple disconnect or short circuit)
- $\eta_{inverter} > 102.0\%$ (impossible energy generation violating first law of thermodynamics)

---

## 3. Level 2: Statistical & Time-Series Methods

### 3.1 Rolling Z-Score Outlier Detection
Measures deviation from local moving mean $\mu_t$ in units of moving standard deviation $\sigma_t$ over window $W$:
$$\mu_t = \frac{1}{W} \sum_{i=0}^{W-1} x_{t-i}, \quad \sigma_t = \sqrt{\frac{1}{W} \sum_{i=0}^{W-1} (x_{t-i} - \mu_t)^2}$$
$$z_t = \frac{|x_t - \mu_t|}{\sigma_t + \epsilon}$$
$$A_{zscore} = \begin{cases}
\text{TRUE}, & \text{if } z_t \ge z_{threshold} \\
\text{FALSE}, & \text{otherwise}
\end{cases}$$
- Standard threshold: $z_{threshold} = 3.0$ ($99.73\%$ confidence under Gaussian assumption).

### 3.2 Exponentially Weighted Moving Average (EWMA) Control Charts
Designed to detect subtle, persistent drift (e.g. progressive soiling, sensor calibration degradation):
$$S_t = \alpha x_t + (1 - \alpha) S_{t-1}, \quad 0 < \alpha \le 1$$
Dynamic control limits based on process standard deviation $\sigma_x$:
$$UCL_t = \mu_0 + L \cdot \sigma_x \sqrt{\frac{\alpha}{2 - \alpha} \left[1 - (1 - \alpha)^{2t}\right]}$$
$$LCL_t = \mu_0 - L \cdot \sigma_x \sqrt{\frac{\alpha}{2 - \alpha} \left[1 - (1 - \alpha)^{2t}\right]}$$
$$A_{ewma} = \begin{cases}
\text{TRUE}, & \text{if } S_t > UCL_t \text{ or } S_t < LCL_t \\
\text{FALSE}, & \text{otherwise}
\end{cases}$$
- Typical parameters: $\alpha = 0.20$, $L = 3.0$.

### 3.3 Two-Sided Cumulative Sum (CUSUM) Change-Point Detection
Detects abrupt step changes in process mean:
$$S_{H,t} = \max(0, S_{H,t-1} + (x_t - \mu_0) - k)$$
$$S_{L,t} = \max(0, S_{L,t-1} - (x_t - \mu_0) - k)$$
$$A_{cusum} = \begin{cases}
\text{TRUE}, & \text{if } S_{H,t} > h \text{ or } S_{L,t} > h \\
\text{FALSE}, & \text{otherwise}
\end{cases}$$
Where $k = \frac{\delta}{2} \sigma_0$ is the slack allowance parameter and $h = 5.0 \cdot \sigma_0$ is the decision threshold.

---

## 4. Level 3: Unsupervised Machine Learning (Isolation Forest)

### 4.1 Algorithmic Formulation
The Isolation Forest (iForest, Liu et al., 2008) exploits two quantitative properties of anomalies:
1. They are few in number;
2. They have attribute values distinct from normal instances.

An ensemble of $T$ randomized isolation trees ($iTrees$) recursively partitions an unlabeled multivariate training set $\mathbf{X} \in \mathbb{R}^{N \times D}$. At each tree node:
1. A feature dimension $d \in \{1, \dots, D\}$ is selected uniformly at random;
2. A split value $p \in [\min(X_{*,d}), \max(X_{*,d})]$ is selected uniformly at random;
3. Data is partitioned into left and right children until nodes are isolated ($|X| = 1$) or depth limit $d_{max} = \lceil \log_2(\text{sub\_sample\_size}) \rceil$ is reached.

### 4.2 Isolation Path Length and Anomaly Score
Let $h_t(\mathbf{x})$ be the path length (number of edges traversed) to isolate instance $\mathbf{x}$ in tree $t$. The expected path length is:
$$E(h(\mathbf{x})) = \frac{1}{T} \sum_{t=1}^T h_t(\mathbf{x})$$
The average path length of unsuccessful searches in a Binary Search Tree (BST) serves as the normalization factor:
$$c(n) = 2 \left(\ln(n - 1) + \gamma_{Euler}\right) - \frac{2(n - 1)}{n}, \quad \gamma_{Euler} \approx 0.5772156649$$
The normalized anomaly score $s(\mathbf{x}, n) \in [0.0, 1.0]$ is:
$$s(\mathbf{x}, n) = 2^{-\frac{E(h(\mathbf{x}))}{c(n)}}$$

- **Score Interpretation**:
  - $s \to 1.0$: $\mathbf{x}$ isolates with very short path lengths $\implies$ **Definite Anomaly**.
  - $s < 0.50$: $\mathbf{x}$ has long path lengths $\implies$ **Normal Instance**.
  - $s \approx 0.50$: The entire sample does not exhibit distinct anomalies.
- **Classification Threshold**: $s \ge 0.62$ triggers an anomaly alert.

### 4.3 Feature Contribution Attribution
To guarantee explainability (`AGENTS.md` Rule 8), for any anomalous point $\mathbf{x}$, the detector computes the partial derivative / isolated variance across each feature dimension:
$$\text{Attribution}_d = \frac{|\mathbf{x}_d - \text{median}(X_{*,d})|}{\text{IQR}(X_{*,d}) + \epsilon}$$
The feature with the highest attribution score is cited in `evidence["dominant_feature"]`.

---

## 5. Level 4: Contextual & Multi-Variate Methods

### 5.1 Physical Relationship Residuals
Checks consistency across coupled physical domains:

1. **Three-Phase AC Power vs Current-Voltage Law**:
   $$P_{calc} = \sqrt{3} \cdot V_{line} \cdot I_{line} \cdot \text{PowerFactor} \cdot 10^{-3}\ (\text{kW})$$
   $$\text{Residual}_{pvi} = \frac{|P_{actual} - P_{calc}|}{P_{rated}}$$
   If $\text{Residual}_{pvi} > 0.10$ ($10\%$ mismatch), a sensor calibration or transducer failure is flagged.

2. **Inverter Thermal vs Electrical Loading Residual**:
   Internal heatsink temperature rise $\Delta T = T_{heatsink} - T_{ambient}$ should track quadratic ohmic losses $I^2 R$:
   $$\Delta T_{expected} = k_{thermal} \cdot \left(\frac{P_{actual}}{P_{rated}}\right)^2$$
   If $\Delta T_{actual} - \Delta T_{expected} > 25.0^\circ\text{C}$, cooling fan failure, heat pipe leak, or dust blockage is diagnosed.

### 5.2 Cross-Inverter Spatial Peer Cohort Analysis
In large utility-scale PV plants, groups of inverters share identical irradiance, tilt, and ambient temperature. A single inverter underperforming its peers cannot be excused by cloud cover.

For a cohort of $N$ peer inverters reporting active powers $\{P_1, P_2, \dots, P_N\}$:
1. Compute the robust cohort median:
   $$\tilde{P} = \text{median}(P_1, \dots, P_N)$$
2. Compute the Median Absolute Deviation (MAD):
   $$\text{MAD} = \text{median}(|P_i - \tilde{P}|)$$
3. Compute Boris Iglewicz & David Hoaglin's Modified Z-Score:
   $$M_i = \frac{0.6745 \cdot (P_i - \tilde{P})}{\text{MAD} + \epsilon}$$
4. Decision rule:
   $$A_{peer,i} = \begin{cases}
   \text{TRUE}, & \text{if } M_i < -3.5 \land \tilde{P} > 0.15 \times P_{rated} \\
   \text{FALSE}, & \text{otherwise}
   \end{cases}$$
   This isolates the outlier inverter from its cohort with high statistical power and robust breakdown point ($50\%$).
