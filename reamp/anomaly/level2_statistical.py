"""
REAMP Level 2 Anomaly Detector: Statistical & Time-Series Engine.
Implements sliding-window rate-of-change Z-score, Exponentially Weighted Moving Average (EWMA),
and Cumulative Sum (CUSUM) change-point detection on operational residuals.
"""

import math
import uuid
import datetime
from collections import deque
from typing import Dict, Any, List, Optional
from reamp.anomaly.models import (
    AnomalyObject,
    AnomalyType,
    AnomalySeverity,
    Level2StatisticalConfig
)


class Level2StatisticalDetector:
    """Statistical time-series anomaly detector for spikes, drift, and step-changes."""

    MODEL_VERSION = "1.0.0-phase8"

    def __init__(self, config: Optional[Level2StatisticalConfig] = None):
        self.config = config or Level2StatisticalConfig()
        # Per-asset state tracking
        self.last_values: Dict[str, Dict[str, float]] = {}
        self.delta_history: Dict[str, Dict[str, deque]] = {}
        self.ewma_state: Dict[str, Dict[str, Any]] = {}
        self.cusum_state: Dict[str, Dict[str, Any]] = {}

    def _get_delta_history(self, asset_id: str, metric: str) -> deque:
        if asset_id not in self.delta_history:
            self.delta_history[asset_id] = {}
        if metric not in self.delta_history[asset_id]:
            self.delta_history[asset_id][metric] = deque(maxlen=self.config.rolling_window)
        return self.delta_history[asset_id][metric]

    def evaluate(
        self,
        asset_id: str,
        telemetry: Dict[str, Any],
        timestamp_str: Optional[str] = None
    ) -> List[AnomalyObject]:
        """Evaluate telemetry using rolling Z-score, EWMA, and CUSUM algorithms."""
        anomalies: List[AnomalyObject] = []
        now_str = timestamp_str or datetime.datetime.now(datetime.timezone.utc).isoformat()
        conf = float(telemetry.get("confidence", 1.0))

        if asset_id not in self.last_values:
            self.last_values[asset_id] = {}

        # ---------------------------------------------------------------------
        # 1. Rolling Z-Score on Rate of Change (Transient Spike Detection)
        # ---------------------------------------------------------------------
        i_ac = telemetry.get("current_ac_a")
        if i_ac is not None and isinstance(i_ac, (int, float)):
            i_ac_f = float(i_ac)
            if "current_ac_a" in self.last_values[asset_id]:
                delta = i_ac_f - self.last_values[asset_id]["current_ac_a"]
                hist = self._get_delta_history(asset_id, "current_ac_a")

                if len(hist) >= 10:
                    mean_delta = sum(hist) / len(hist)
                    var_delta = sum((x - mean_delta) ** 2 for x in hist) / len(hist)
                    std_delta = max(math.sqrt(var_delta), 1.0)
                    z_score = abs(delta - mean_delta) / std_delta

                    # Only flag if z_score exceeds threshold and absolute change indicates a true spike (>50A)
                    if z_score >= self.config.z_threshold and abs(delta) >= 50.0:
                        anomalies.append(AnomalyObject(
                            anomaly_id=f"ANOM-L2-Z-{uuid.uuid4().hex[:8]}",
                            asset_id=asset_id,
                            timestamp=now_str,
                            type=AnomalyType.STATISTICAL_ZSCORE,
                            severity=AnomalySeverity.MEDIUM if z_score < 5.0 else AnomalySeverity.HIGH,
                            score=round(min(1.0, z_score / 10.0), 3),
                            evidence={
                                "metric": "current_ac_a",
                                "observed_value": i_ac_f,
                                "step_delta": round(delta, 2),
                                "rolling_mean_delta": round(mean_delta, 2),
                                "rolling_std_delta": round(std_delta, 2),
                                "z_score": round(z_score, 2),
                                "threshold": self.config.z_threshold
                            },
                            confidence=conf,
                            detection_method="LEVEL_2_ROLLING_ZSCORE",
                            model_version=self.MODEL_VERSION,
                            recommended_action=f"Transient current spike detected (Z={z_score:.1f}, Delta={delta:.1f}A). Check inverter bridge for partial discharge."
                        ))

                hist.append(delta)
            self.last_values[asset_id]["current_ac_a"] = i_ac_f

        # ---------------------------------------------------------------------
        # 2. EWMA & CUSUM on Active Power Residual (Drift & Step Detection)
        # ---------------------------------------------------------------------
        p_act = telemetry.get("actual_power_kw")
        if p_act is not None and isinstance(p_act, (int, float)):
            p_act_f = float(p_act)

            # Determine baseline reference:
            # If weather telemetry is present, compute expected power baseline
            p_exp = telemetry.get("expected_power_kw")
            if p_exp is None:
                p_exp = telemetry.get("expected_power_ac_kw")
            if p_exp is None and "irradiance_poa_wm2" in telemetry:
                g_poa = telemetry["irradiance_poa_wm2"]
                if g_poa is not None:
                    p_exp = 0.80 * float(g_poa)

            if p_exp is not None:
                # Weather-normalized residual tracking
                res_val = p_act_f - float(p_exp)
                mu_0 = 0.0
                sig_0 = 15.0
                has_weather = True
            else:
                # Absolute power tracking (for constant baseline unit tests)
                res_val = p_act_f
                if asset_id not in self.ewma_state:
                    mu_0 = res_val
                else:
                    mu_0 = self.ewma_state[asset_id].get("mu_0", res_val)
                sig_0 = 20.0
                has_weather = False

            # --- A. EWMA Drift Detector ---
            if asset_id not in self.ewma_state:
                self.ewma_state[asset_id] = {
                    "s_prev": res_val,
                    "mu_0": mu_0,
                    "sigma_0": sig_0,
                    "t": 0
                }

            em = self.ewma_state[asset_id]
            em["t"] += 1
            t_step = em["t"]
            alpha = self.config.ewma_alpha
            s_curr = alpha * res_val + (1.0 - alpha) * em["s_prev"]
            em["s_prev"] = s_curr

            factor = math.sqrt((alpha / (2.0 - alpha)) * (1.0 - ((1.0 - alpha) ** (2 * t_step))))
            margin = self.config.ewma_l_factor * em["sigma_0"] * factor
            ucl = em["mu_0"] + margin
            lcl = em["mu_0"] - margin

            # Only flag EWMA if current residual is also outside normal bounds (prevents post-fault alert hangover)
            is_active_deviation = (abs(res_val) >= 30.0) if has_weather else True

            if t_step > 15 and (s_curr > ucl or s_curr < lcl) and is_active_deviation:
                drift_mag = abs(s_curr - em["mu_0"])
                anomalies.append(AnomalyObject(
                    anomaly_id=f"ANOM-L2-EWMA-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.STATISTICAL_EWMA,
                    severity=AnomalySeverity.MEDIUM,
                    score=round(min(1.0, drift_mag / (2.0 * margin)), 3),
                    evidence={
                        "metric": "actual_power_kw",
                        "ewma_smoothed": round(s_curr, 2),
                        "baseline_mean": round(em["mu_0"], 2),
                        "ucl": round(ucl, 2),
                        "lcl": round(lcl, 2),
                        "drift_direction": "UPWARD" if s_curr > ucl else "DOWNWARD"
                    },
                    confidence=conf,
                    detection_method="LEVEL_2_EWMA_CONTROL_CHART",
                    model_version=self.MODEL_VERSION,
                    recommended_action="Persistent generation drift detected. Inspect for progressive module soiling or tracking misalignment."
                ))

            # --- B. Two-Sided CUSUM Step-Change Detector ---
            if asset_id not in self.cusum_state:
                self.cusum_state[asset_id] = {
                    "s_high": 0.0,
                    "s_low": 0.0,
                    "mu_0": mu_0,
                    "sigma_0": sig_0
                }

            cm = self.cusum_state[asset_id]
            k_slack = self.config.cusum_slack_k * cm["sigma_0"]
            h_limit = 4.0 * cm["sigma_0"]

            s_high = max(0.0, cm["s_high"] + (res_val - cm["mu_0"]) - k_slack)
            s_low = max(0.0, cm["s_low"] - (res_val - cm["mu_0"]) - k_slack)
            cm["s_high"] = s_high
            cm["s_low"] = s_low

            if (s_high > h_limit or s_low > h_limit) and is_active_deviation:
                shift_dir = "POSITIVE_STEP" if s_high > h_limit else "NEGATIVE_STEP"
                peak_cusum = max(s_high, s_low)
                anomalies.append(AnomalyObject(
                    anomaly_id=f"ANOM-L2-CUSUM-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.CHANGE_POINT_CUSUM,
                    severity=AnomalySeverity.HIGH,
                    score=round(min(1.0, peak_cusum / (2.0 * h_limit)), 3),
                    evidence={
                        "metric": "actual_power_kw",
                        "observed_value": p_act_f,
                        "residual_value": round(res_val, 2),
                        "baseline_mean": round(cm["mu_0"], 2),
                        "shift_type": shift_dir,
                        "cusum_statistic": round(peak_cusum, 2),
                        "threshold_h": round(h_limit, 2)
                    },
                    confidence=conf,
                    detection_method="LEVEL_2_CUSUM_CHANGE_POINT",
                    model_version=self.MODEL_VERSION,
                    recommended_action=f"Abrupt step change detected in generation ({shift_dir}). Inspect for blown string fuse or module disconnection."
                ))
                # Reset accumulators to prevent repeat alarms on the same step
                cm["s_high"] = 0.0
                cm["s_low"] = 0.0
                if not has_weather:
                    cm["mu_0"] = res_val  # Adapt baseline to new state

        return anomalies
