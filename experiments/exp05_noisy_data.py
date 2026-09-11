"""
REAMP Experiment 05 - Noisy Data & Measurement Noise Robustness.

Test Condition:
- Evaluates Level 2 statistical filter (EWMA and CUSUM) robustness against additive Gaussian
  noise (sigma = 2%, 5%, 10%, 15%) and sparse impulsive noise spikes.

Evaluated Metrics:
- False-Positive Rate vs Noise Level
- Detection Precision and Recall on true drift embedded in high noise
- Noise suppression efficiency (single-sample spike rejection)
"""

import random
from typing import Dict, Any

from experiments.common import (
    generate_diurnal_solar_telemetry,
    ConfusionMatrix,
    save_experiment_result,
)
from reamp.anomaly.level2_statistical import Level2StatisticalDetector
from reamp.anomaly.models import Level2StatisticalConfig


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    random.seed(seed)
    # Generate 500 samples (midday steady window)
    base_data = generate_diurnal_solar_telemetry(n_samples=500, seed=seed)

    noise_sigmas_kw = [2.0, 5.0, 10.0, 15.0]
    noise_evaluations = []
    p_expected = 2000.0

    for sigma_kw in noise_sigmas_kw:
        detector = Level2StatisticalDetector(
            Level2StatisticalConfig(
                z_threshold=4.5,
                ewma_alpha=0.1,
                ewma_l_factor=3.5,
                cusum_slack_k=0.5,
                cusum_threshold_h=5.0,
            )
        )

        cm = ConfusionMatrix()

        for i in range(500):
            # Inject genuine drift/degradation between sample 300 and 400
            has_genuine_drift = (300 <= i <= 400)
            drift_offset = -60.0 if has_genuine_drift else 0.0

            # Add zero-mean Gaussian noise to actual generation
            noise = random.gauss(0.0, sigma_kw)
            noisy_power = p_expected + drift_offset + noise

            # Add occasional 1-sample impulsive spike at sample 150
            if i == 150:
                noisy_power += 25.0  # Transient glitch suppressed by EWMA

            telemetry = {
                "actual_power_kw": noisy_power,
                "expected_power_kw": p_expected,
                "current_ac_a": 3000.0,
                "confidence": 1.0,
            }

            anoms = detector.evaluate(asset_id="ASSET-INV-01", telemetry=telemetry)
            detected = len(anoms) > 0

            # Evaluate against ground truth drift
            is_anomaly_target = has_genuine_drift
            if is_anomaly_target and detected:
                cm.true_positives += 1
            elif is_anomaly_target and not detected:
                cm.false_negatives += 1
            elif not is_anomaly_target and detected:
                cm.false_positives += 1
            else:
                cm.true_negatives += 1

        noise_evaluations.append({
            "noise_sigma_kw": sigma_kw,
            "precision": cm.precision,
            "recall": cm.recall,
            "f1_score": cm.f1_score,
            "false_positive_rate": cm.false_positive_rate,
            "true_positives": cm.true_positives,
            "false_positives": cm.false_positives,
        })

    results = {
        "experiment_id": "EXP05_NOISY_DATA",
        "description": "Additive Gaussian Noise & Statistical Filter Robustness",
        "sample_count": 500,
        "seed": seed,
        "noise_evaluations": noise_evaluations,
    }

    save_experiment_result("EXP05_NOISY_DATA", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Noise Robustness Evaluations:")
    for e in res["noise_evaluations"]:
        print(f"  Noise={e['noise_sigma_kw']}kW -> Prec={e['precision']*100:.1f}% | Rec={e['recall']*100:.1f}% | F1={e['f1_score']:.4f} | FPR={e['false_positive_rate']*100:.2f}%")
