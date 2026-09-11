"""
REAMP Experiment 02 — Sensor Failure & Telemetry Validation.

Test Condition:
- Mixed stream of 600 observations:
  - 500 nominal telemetry records
  - 100 injected sensor fault records:
    - Impossible thermocouple temperatures (> 130 C or < -50 C)
    - Grid AC overvoltage (> 528 V limit)
    - Impossible negative irradiance (< 0 W/m^2)
    - Uncommanded power collapse under peak daylight (> 600 W/m^2)

Evaluated Metrics:
- Detection Precision, Recall, F1
- False-Positive Rate (FPR), False-Negative Rate (FNR)
"""

import random
from typing import Dict, Any

from experiments.common import (
    generate_diurnal_solar_telemetry,
    ConfusionMatrix,
    save_experiment_result,
)
from reamp.mvp import REAMPApplicationMVP


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    random.seed(seed)
    app = REAMPApplicationMVP(storage_db=":memory:")
    app.initialize_default_topology()
    asset_id = "ASSET-INV-01"

    # Generate 600 samples (covering morning through afternoon)
    base_data = generate_diurnal_solar_telemetry(n_samples=600, seed=seed)

    cm = ConfusionMatrix()

    for i, row in enumerate(base_data):
        # Inject sensor failures every 6th sample (100 total anomalies)
        is_sensor_fault = (i % 6 == 0)

        sample = dict(row)
        if is_sensor_fault:
            fault_mode = random.choice(["impossible_temp", "overvoltage", "negative_irradiance", "unexpected_shutdown"])
            if fault_mode == "impossible_temp":
                sample["temperature_cell_max_c"] = 175.0  # Impossible junction temp
                sample["heatsink_temp"] = 92.0
            elif fault_mode == "overvoltage":
                sample["voltage_ac_v"] = 620.0  # Overvoltage trip threshold
            elif fault_mode == "negative_irradiance":
                sample["poa_irradiance"] = -120.0  # Negative irradiance
            elif fault_mode == "unexpected_shutdown":
                sample["poa_irradiance"] = 850.0
                sample["ac_power_kw"] = 0.0  # Shutdown under high sun
                sample["dc_power_kw"] = 0.0
                sample["operating_state"] = "RUNNING"

        res = app.process_telemetry_packet(
            asset_id=asset_id,
            telemetry=sample,
        )

        detected = res["anomalies_detected"] > 0

        # Update Confusion Matrix
        if is_sensor_fault and detected:
            cm.true_positives += 1
        elif is_sensor_fault and not detected:
            cm.false_negatives += 1
        elif not is_sensor_fault and detected:
            cm.false_positives += 1
        else:
            cm.true_negatives += 1

    results = {
        "experiment_id": "EXP02_SENSOR_FAILURE",
        "description": "Sensor Fault & Impossible Telemetry Range Validation",
        "sample_count": len(base_data),
        "injected_faults_count": 100,
        "seed": seed,
        "detection_metrics": cm.to_dict(),
        "audit_chain_valid": app.audit_logger.verify_chain_integrity()[0],
    }

    save_experiment_result("EXP02_SENSOR_FAILURE", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Evaluation Results:")
    print(f"  Precision: {res['detection_metrics']['precision'] * 100:.2f}%")
    print(f"  Recall:    {res['detection_metrics']['recall'] * 100:.2f}%")
    print(f"  F1 Score:  {res['detection_metrics']['f1_score']:.4f}")
    print(f"  FPR:       {res['detection_metrics']['false_positive_rate'] * 100:.2f}%")
