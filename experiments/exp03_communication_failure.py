"""
REAMP Experiment 03 - Communication Failure & Network Dropout.

Test Condition:
- Evaluates asset behavior under varying network packet drop rates (0%, 25%, 50%, 75%, 100%)
  and communication watchdog timeouts.

Evaluated Metrics:
- Communication Sub-Index derating sensitivity
- Confidence penalty propagation
- Timeout anomaly detection accuracy
- System error resilience (0 unhandled crashes)
"""

from typing import Dict, Any

from experiments.common import (
    ConfusionMatrix,
    save_experiment_result,
)
from reamp.health.engine import AssetHealthEngine
from reamp.health.profiles import SOLAR_PV_INVERTER_PROFILE
from reamp.mvp import REAMPApplicationMVP


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    app = REAMPApplicationMVP(storage_db=":memory:")
    app.initialize_default_topology()
    health_engine = AssetHealthEngine()

    drop_rates = [0.0, 0.25, 0.50, 0.75, 1.00]
    comm_evaluations = []

    for drop_rate in drop_rates:
        is_online = (drop_rate < 1.0)
        score, conf, status = health_engine.compute_communication_subindex(
            is_online=is_online,
            packet_drop_rate=drop_rate,
            latency_ms=50.0 + (drop_rate * 500.0),
        )

        # Evaluate full health result with this communication state
        evidence = {
            "performance": {"value": 1.0},
            "thermal": {"temperature_c": 45.0},
            "availability": {"uptime_hours": 720.0, "total_hours": 720.0},
            "communication": {"is_online": is_online, "packet_drop_rate": drop_rate, "latency_ms": 200.0},
            "fault_history": {"alarms": []},
            "degradation": {"age_years": 1.0},
            "sensor_quality": {"valid_samples": 100, "total_samples": 100, "mean_confidence": 1.0},
        }
        res = health_engine.evaluate("ASSET-INV-01", SOLAR_PV_INVERTER_PROFILE, evidence)

        comm_evaluations.append({
            "drop_rate": drop_rate,
            "is_online": is_online,
            "comm_subscore": score,
            "comm_confidence": conf,
            "composite_health": res.health_score,
            "health_confidence": res.confidence,
        })

    # Test L1 communication timeout anomaly
    cm = ConfusionMatrix()
    sample_normal = {"poa_irradiance": 800.0, "ac_power_kw": 1900.0, "heatsink_temp": 45.0, "heartbeat_gap_seconds": 10.0}
    res_norm = app.process_telemetry_packet("ASSET-INV-01", sample_normal)
    if res_norm["anomalies_detected"] == 0:
        cm.true_negatives += 1
    else:
        cm.false_positives += 1

    # Simulate communication timeout via canonical watchdog input (heartbeat gap > 300s or communication_lost=True)
    sample_timeout = {
        "poa_irradiance": 800.0,
        "ac_power_kw": 1900.0,
        "heatsink_temp": 45.0,
        "heartbeat_gap_seconds": 360.0,
        "communication_lost": True,
    }
    res_timeout = app.process_telemetry_packet("ASSET-INV-01", sample_timeout)
    if res_timeout["anomalies_detected"] > 0:
        cm.true_positives += 1
    else:
        cm.false_negatives += 1

    results = {
        "experiment_id": "EXP03_COMMUNICATION_FAILURE",
        "description": "Network Packet Drop & Watchdog Timeout Evaluation",
        "tested_drop_rates": drop_rates,
        "comm_evaluations": comm_evaluations,
        "timeout_detection": cm.to_dict(),
        "audit_chain_valid": app.audit_logger.verify_chain_integrity()[0],
    }

    save_experiment_result("EXP03_COMMUNICATION_FAILURE", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Communication Evaluations:")
    for e in res["comm_evaluations"]:
        print(f"  Drop={e['drop_rate']*100:.0f}% -> SubScore={e['comm_subscore']} | HealthScore={e['composite_health']} | Conf={e['health_confidence']:.2f}")
    print(f"  Timeout Recall: {res['timeout_detection']['recall'] * 100:.2f}%")
