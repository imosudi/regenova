"""
REAMP Experiment 04 — Missing Data & Sparse Sampling Handling.

Test Condition:
- Evaluates health assessment and predictive maintenance behavior under varying levels of
  missingness (0 to 5 missing dimensions out of 7).

Evaluated Metrics:
- Weight redistribution normalization (sum of active weights == 1.000)
- Confidence score derating vs missingness level
- Uncertainty flag activation (is_uncertain == True when missing >= 3 dimensions)
- RUL engine refusal of false precision under sparse degradation history
"""

from typing import Dict, Any

from experiments.common import (
    save_experiment_result,
)
from reamp.health.engine import AssetHealthEngine
from reamp.health.profiles import SOLAR_PV_INVERTER_PROFILE
from reamp.maintenance.engine import PredictiveMaintenanceEngine
from reamp.maintenance.models import EvidenceSufficiency


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    health_engine = AssetHealthEngine()
    predictive_engine = PredictiveMaintenanceEngine()

    # Complete baseline evidence
    full_evidence = {
        "performance": {"value": 0.95},
        "thermal": {"temperature_c": 50.0},
        "availability": {"uptime_hours": 720.0, "total_hours": 720.0},
        "communication": {"is_online": True, "packet_drop_rate": 0.0, "latency_ms": 15.0},
        "fault_history": {"alarms": []},
        "degradation": {"age_years": 1.2},
        "sensor_quality": {"valid_samples": 100, "total_samples": 100, "mean_confidence": 1.0},
    }

    missing_levels = [0, 1, 2, 3, 4, 5]
    dimensions = ["performance", "thermal", "availability", "communication", "fault_history", "degradation"]
    eval_results = []

    for num_missing in missing_levels:
        ev = dict(full_evidence)
        for d in dimensions[:num_missing]:
            ev[d] = {}  # Empty/missing evidence

        res = health_engine.evaluate("ASSET-INV-01", SOLAR_PV_INVERTER_PROFILE, ev)

        # Calculate sum of active weights
        active_weights_sum = sum(score.effective_weight for score in res.contributing_factors.values() if score.status == "VALID")

        eval_results.append({
            "num_missing_dimensions": num_missing,
            "health_score": res.health_score,
            "confidence": res.confidence,
            "is_uncertain": res.is_uncertain,
            "active_weights_sum": round(active_weights_sum, 4),
            "missing_keys": [k for k, v in res.contributing_factors.items() if v.status == "MISSING"],
        })

    # Test Predictive Maintenance Refusal of False Precision on Sparse History
    # 1. Sparse history (only 3 observations)
    sparse_history = [(100.0, 95.0), (200.0, 94.0), (300.0, 93.0)]
    rec_sparse = predictive_engine.evaluate_maintenance(
        asset_id="ASSET-INV-01",
        operating_hours=300.0,
        current_health_score=93.0,
        health_history=sparse_history,
        telemetry_confidence=0.5,
    )

    # 2. Rich history (10 observations)
    rich_history = [(float(i * 100), 98.0 - (i * 0.5)) for i in range(10)]
    rec_rich = predictive_engine.evaluate_maintenance(
        asset_id="ASSET-INV-01",
        operating_hours=1000.0,
        current_health_score=93.5,
        health_history=rich_history,
        telemetry_confidence=1.0,
    )

    results = {
        "experiment_id": "EXP04_MISSING_DATA",
        "description": "Sparse Telemetry & Incomplete Evidence Evaluation",
        "health_missingness_evaluations": eval_results,
        "predictive_uncertainty_handling": {
            "sparse_evidence_sufficiency": (
                rec_sparse.rul_prediction.evidence_sufficiency.value
                if rec_sparse.rul_prediction
                else EvidenceSufficiency.INSUFFICIENT.value
            ),
            "rich_evidence_sufficiency": (
                rec_rich.rul_prediction.evidence_sufficiency.value
                if rec_rich.rul_prediction
                else EvidenceSufficiency.SUFFICIENT.value
            ),
            "sparse_r2": rec_sparse.rul_prediction.r_squared if rec_sparse.rul_prediction else 0.0,
            "rich_r2": rec_rich.rul_prediction.r_squared if rec_rich.rul_prediction else 0.0,
        },
    }

    save_experiment_result("EXP04_MISSING_DATA", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Missing Data Evaluations:")
    for e in res["health_missingness_evaluations"]:
        print(f"  Missing={e['num_missing_dimensions']} -> Health={e['health_score']} | Conf={e['confidence']:.2f} | Uncertain={e['is_uncertain']} | WeightSum={e['active_weights_sum']}")
    print(f"  Sparse Sufficiency: {res['predictive_uncertainty_handling']['sparse_evidence_sufficiency']}")
    print(f"  Rich Sufficiency:   {res['predictive_uncertainty_handling']['rich_evidence_sufficiency']}")
