# REAMP Anomaly Detection Benchmarking and Evaluation Protocol

## 1. Objective & Scientific Rigor

In compliance with [`AGENTS.md`](file:///home/mosud/Documents/dev/regenova/AGENTS.md) Rule 3 (*Evidence over assumptions*) and Rule 9 (*No fake completion*), this document defines the formal validation protocol, metric definitions, and synthetic ground-truth dataset generator for evaluating the REAMP Anomaly Detection Framework.

Benchmark metrics must NEVER be fabricated or assumed. They are measured directly by running the automated evaluation harness against reproducible, ground-truth labeled telemetry streams.

---

## 2. Evaluation Metrics Formulation

The performance of each detection level and the integrated orchestrator is quantified using standard binary classification metrics over temporal evaluation windows:

```
                      Actual Positive (Anomaly)      Actual Negative (Normal)
Predicted Positive       True Positive (TP)             False Positive (FP)
Predicted Negative       False Negative (FN)            True Negative (TN)
```

### 2.1 Precision ($P$)
The fraction of detected anomaly events that correspond to genuine physical or data faults:
$$P = \frac{TP}{TP + FP}$$
*Target*: $P \ge 0.90$. Minimizes costly false dispatches and operator alert fatigue.

### 2.2 Recall / True Positive Rate ($R$ / $TPR$)
The fraction of true operational anomalies successfully captured by the framework:
$$R = \frac{TP}{TP + FN}$$
*Target*: $R \ge 0.90$. Ensures critical equipment failures are not missed.

### 2.3 $F_1$ Score
The harmonic mean of Precision and Recall:
$$F_1 = 2 \cdot \frac{P \cdot R}{P + R} = \frac{2 \cdot TP}{2 \cdot TP + FP + FN}$$
*Target*: $F_1 \ge 0.90$.

### 2.4 False Positive Rate ($FPR$)
The proportion of nominal operational observations falsely flagged as anomalies:
$$FPR = \frac{FP}{FP + TN}$$
*Target*: $FPR \le 0.05$ ($5\%$).

### 2.5 Detection Latency ($\Delta \tau_{detect}$)
The temporal lag between anomaly onset ($t_{injection}$) and detection emission ($t_{detection}$):
$$\Delta \tau_{detect} = t_{detection} - t_{injection}$$
- Level 1 target: $\le 1$ sample ($< 1\ \text{s}$ at 1 Hz).
- Level 2 target: $\le 3$ samples ($< 3\ \text{s}$).
- Level 3 target: $\le 5$ samples ($< 5\ \text{s}$).
- Level 4 target: $\le 2$ samples ($< 2\ \text{s}$).

---

## 3. Synthetic Benchmark Generation Methodology

To ensure full reproducibility without proprietary NDA constraints, the benchmark generator creates a 1,000-sample operational stream ($1\ \text{Hz}$ or $1\ \text{minute}$ interval) incorporating a realistic diurnal solar curve, ambient temperature profile, and Gaussian measurement noise ($\sigma = 2\%$).

Ten distinct anomaly injection episodes are precisely seeded at known timestamp indices:

| Index Range | Anomaly Episode Description | Injected Signature | Primary Expected Level |
| :--- | :--- | :--- | :--- |
| **50 – 55** | Impossible physical value | $G_{poa} = -50.0\ \text{W/m}^2$ | Level 1 (`IMPOSSIBLE_VALUE`) |
| **120 – 125**| Severe AC Overvoltage | $V_{ac} = 560.0\ \text{V}$ ($+16\%$ above rated 480V) | Level 1 (`THRESHOLD_VIOLATION`) |
| **200 – 210**| Unexpected Inverter Trip | $P_{ac} \to 0.0\ \text{kW}$ while $G_{poa} = 850\ \text{W/m}^2$ | Level 1 (`UNEXPECTED_SHUTDOWN`) |
| **280 – 290**| Communication Link Loss | Heartbeat gap $> 60\ \text{s}$ | Level 1 (`COMMUNICATION_TIMEOUT`) |
| **360 – 370**| Transient Current Spike | $I_{ac} = \mu + 6 \sigma$ transient pulse | Level 2 (`STATISTICAL_ZSCORE`) |
| **450 – 500**| Gradual Soiling Power Drift | Linear $-20\%$ generation decay over 50 samples | Level 2 (`STATISTICAL_EWMA`) |
| **580 – 620**| Blown String Fuse Step Drop | Abrupt $-15\%$ step drop in current and power | Level 2 (`CHANGE_POINT_CUSUM`)|
| **700 – 720**| Non-linear Multivariate Anomaly | Elevated heatsink temp paired with sub-nominal power | Level 3 (`ML_ISOLATION_FOREST`) |
| **800 – 810**| Transducer Residual Mismatch | $P_{ac}$ telemetry desynchronized from $V \cdot I$ | Level 4 (`PHYSICAL_RESIDUAL`) |
| **900 – 920**| Spatial Peer Array Outlier | Target inverter generates $40\%$ less than 5 cohort peers | Level 4 (`PEER_OUTLIER`) |

All remaining intervals represent nominal operational generation ($S_{ground\_truth} = \text{NORMAL}$).

---

## 4. Automated Benchmark Execution Protocol

The automated test runner [`tests/test_phase8_anomaly.py`](file:///home/mosud/Documents/dev/regenova/tests/test_phase8_anomaly.py) iterates through the 1,000 observations, invokes the multi-level detection engine, compares the emitted anomaly events against the ground-truth binary mask, and compiles the exact confusion matrix:

```python
precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
```

Results are printed to test output and recorded in [`docs/PHASE_8_REPORT.md`](file:///home/mosud/Documents/dev/regenova/docs/PHASE_8_REPORT.md).
