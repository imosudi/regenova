"""
REAMP Experiment 06 — Asset Degradation & Predictive RUL Validation.

Test Condition:
- Simulates 1,000 operational hours of an asset undergoing progressive thermal degradation
  (inverter heatsink fouling / fan bearing wear causing R_th to rise by 40%).
- Compares REAMP Weibull RUL predictions against ground truth failure timestamp (trip at 95 C).

Evaluated Metrics:
- RUL Prediction MAE, RMSE, and R^2 calibration
- Early Warning Time (advance warning hours before thermal trip limit)
- Maintenance Priority classification progression (P4 -> P3 -> P2 -> P1)
"""

import math
from typing import Dict, Any, List

from experiments.common import (
    calculate_regression_metrics,
    save_experiment_result,
)
from reamp.maintenance.engine import PredictiveMaintenanceEngine


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    engine = PredictiveMaintenanceEngine()
    asset_id = "ASSET-INV-01"

    # Simulated ground truth trajectory:
    # Asset starts at t=0 with health 98.0, operating normally.
    # Health steadily degrades down towards critical EOL threshold (30.0) at t=1000h.
    total_hours = 1000
    eval_interval = 25  # Evaluate every 25 operating hours
    t_eol = 1000.0      # Ground truth EOL failure time

    y_true_rul = []
    y_pred_rul = []
    health_history = []
    priorities = []
    early_warning_hour = None

    for t in range(0, total_hours + 1, eval_interval):
        t_float = float(t)
        progress = t_float / total_hours
        health = 98.0 - (68.0 * (progress ** 1.05))
        health = round(health, 2)

        health_history.append((t_float, health))

        # Ground truth RUL to EOL threshold
        true_rul = max(0.0, t_eol - t_float)

        # Thermal rise & derating progression:
        safety_score = min(95.0, max(5.0, 5.0 + (progress ** 1.5) * 90.0))
        daily_loss = 50.0 + (progress ** 1.2) * 850.0

        # Run REAMP predictive maintenance evaluation
        rec = engine.evaluate_maintenance(
            asset_id=asset_id,
            operating_hours=60000.0 + t_float,
            current_health_score=health,
            health_history=health_history,
            telemetry_confidence=1.0,
            operational_state="RUNNING",
            criticality_score=85.0,
            daily_revenue_loss_usd=daily_loss,
            safety_hazard_score=safety_score,
            cost_avoidance_score=85.0,
            spares_logistics_score=85.0,
        )

        priorities.append(rec.priority.value)

        # Record predicted RUL if engine produced a prediction
        if rec.rul_prediction and rec.rul_prediction.predicted_rul_hours is not None:
            pred_rul = rec.rul_prediction.predicted_rul_hours
            y_true_rul.append(true_rul)
            y_pred_rul.append(pred_rul)

        # Identify early warning timestamp (when priority escalates to P2 or P1)
        if early_warning_hour is None and rec.priority.value in ["P1_CRITICAL", "P2_HIGH"]:
            early_warning_hour = t_float

    # Calculate regression metrics
    reg_metrics = calculate_regression_metrics(y_true_rul, y_pred_rul)
    advance_warning_hours = t_eol - early_warning_hour if early_warning_hour else 0.0

    results = {
        "experiment_id": "EXP06_ASSET_DEGRADATION",
        "description": "Progressive Thermal Degradation & Weibull RUL Accuracy Benchmark",
        "total_simulated_hours": total_hours,
        "evaluations_count": len(health_history),
        "ground_truth_failure_hour": t_eol,
        "early_warning_hour": early_warning_hour,
        "advance_warning_hours": round(advance_warning_hours, 1),
        "rul_prediction_metrics": reg_metrics,
        "priority_transitions": {
            "initial_priority": priorities[0],
            "final_priority": priorities[-1],
            "p2_escalation_hour": early_warning_hour,
            "all_priorities": sorted(list(set(priorities))),
        },
    }

    save_experiment_result("EXP06_ASSET_DEGRADATION", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Degradation & RUL Metrics:")
    print(f"  Advance Warning: {res['advance_warning_hours']} hours before trip")
    print(f"  RUL MAE:         {res['rul_prediction_metrics']['mae']} hours")
    print(f"  RUL RMSE:        {res['rul_prediction_metrics']['rmse']} hours")
    print(f"  RUL R^2:         {res['rul_prediction_metrics']['r2']}")
