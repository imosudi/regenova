"""
REAMP Phase 16 - Experimental Validation Common Utilities.

Provides shared scientific evaluation harnesses, mathematical metric computers
(Precision, Recall, F1, FPR, FNR, MAE, RMSE, R2, Latency, Throughput),
deterministic synthetic dataset generators, and result serializers.
"""

import os
import sys
import math
import time
import json
import random
import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@dataclass
class ConfusionMatrix:
    """Standardized binary confusion matrix and classification metrics."""
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def total_samples(self) -> int:
        return self.true_positives + self.false_positives + self.true_negatives + self.false_negatives

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return round(self.true_positives / denom, 4) if denom > 0 else 1.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return round(self.true_positives / denom, 4) if denom > 0 else 1.0

    @property
    def f1_score(self) -> float:
        p = self.precision
        r = self.recall
        denom = p + r
        return round(2.0 * (p * r) / denom, 4) if denom > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        denom = self.false_positives + self.true_negatives
        return round(self.false_positives / denom, 4) if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        denom = self.true_positives + self.false_negatives
        return round(self.false_negatives / denom, 4) if denom > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "total_samples": self.total_samples,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
        }


def calculate_regression_metrics(y_true: List[float], y_pred: List[float]) -> Dict[str, float]:
    """Computes MAE, RMSE, and R-squared between ground truth and predicted sequences."""
    n = len(y_true)
    if n == 0 or len(y_pred) != n:
        raise ValueError("Invalid sample lengths for regression calculation.")

    mae = sum(abs(yt - yp) for yt, yp in zip(y_true, y_pred)) / n
    mse = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred)) / n
    rmse = math.sqrt(mse)

    mean_true = sum(y_true) / n
    ss_tot = sum((yt - mean_true) ** 2 for yt in y_true)
    ss_res = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "sample_count": n,
    }


def generate_diurnal_solar_telemetry(
    n_samples: int = 1440,
    seed: int = 42,
    rated_kw: float = 2500.0,
    inject_cloud_events: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generates a deterministic synthetic 24-hour diurnal profile (1-minute intervals).
    Uses standard solar elevation curve with realistic heatsink thermal response.
    """
    random.seed(seed)
    observations = []
    base_time = datetime.datetime(2026, 6, 21, 0, 0, 0, tzinfo=datetime.timezone.utc)

    for i in range(n_samples):
        dt = base_time + datetime.timedelta(minutes=i)
        hour_fraction = dt.hour + dt.minute / 60.0

        # Sunlight between 06:00 and 19:00
        if 6.0 <= hour_fraction <= 19.0:
            zenith_progress = (hour_fraction - 6.0) / 13.0
            solar_sin = math.sin(math.pi * zenith_progress)
            poa_raw = 980.0 * solar_sin
            t_amb = 22.0 + (12.0 * solar_sin)
        else:
            poa_raw = 0.0
            t_amb = 18.0

        # Optional cloud events
        if inject_cloud_events and 11.5 <= hour_fraction <= 13.0:
            poa_raw *= random.uniform(0.2, 0.45)  # Sudden cloud shading ramp

        # Realistic noise
        poa = max(0.0, poa_raw + (random.uniform(-5.0, 5.0) if poa_raw > 0 else 0.0))

        # First-principles conversion
        if poa > 20.0:
            from reamp.performance.solar import SolarPerformanceModel
            from reamp.performance.models import SolarParameters
            params = SolarParameters(
                rated_dc_kw=2750.0,
                rated_ac_kw=2500.0,
                gamma_pmp=-0.0038,
                inverter_efficiency=0.985,
            )
            sim = SolarPerformanceModel.calculate_expected_power(params, poa, t_amb)
            p_dc = sim["p_dc_expected"]
            p_ac = sim["p_ac_expected"]
            # Normal heatsink temperature model: T_amb + P_loss * R_th
            p_loss = max(0.0, p_dc - p_ac)
            t_hs = t_amb + (p_loss * 0.08)
        else:
            p_dc = 0.0
            p_ac = 0.0
            t_hs = t_amb

        observations.append({
            "timestamp": dt.isoformat(),
            "minute_index": i,
            "hour": hour_fraction,
            "poa_irradiance": round(poa, 2),
            "ambient_temp": round(t_amb, 2),
            "dc_power_kw": round(p_dc, 2),
            "ac_power_kw": round(p_ac, 2),
            "heatsink_temp": round(t_hs, 2),
            "voltage_dc_v": 820.0 if p_dc > 0 else 0.0,
            "current_dc_a": round(p_dc / 0.82, 1) if p_dc > 0 else 0.0,
            "voltage_ac_v": 480.0,
            "wind_speed_m_per_s": round(random.uniform(1.5, 4.0), 1),
        })

    return observations


def save_experiment_result(experiment_id: str, result_dict: Dict[str, Any]) -> str:
    """Saves experiment output to results/ directory."""
    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"{experiment_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2)
    return out_path
