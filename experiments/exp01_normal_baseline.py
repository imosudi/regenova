"""
REAMP Experiment 01 — Normal Operation & Baseline Calibration.

Test Condition:
- Nominal 24-hour diurnal clear-sky cycle (1,440 continuous 1-minute observations).
- Standard ambient temperatures (18C to 34C), peak irradiance ~980 W/m^2.

Evaluated Metrics:
- False-Positive Rate (target: <= 0.005, ideal: 0)
- Ingestion Latency (mean, p95, p99 in ms)
- Processing Throughput (observations per second)
- Steady-state Health Index (mean >= 98.0)
- Performance Ratio stability (PR ~ 1.0)
"""

import time
from typing import Dict, Any

from experiments.common import (
    generate_diurnal_solar_telemetry,
    ConfusionMatrix,
    save_experiment_result,
)
from reamp.mvp import REAMPApplicationMVP


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    app = REAMPApplicationMVP(storage_db=":memory:")
    app.initialize_default_topology()
    asset_id = "ASSET-INV-01"

    dataset = generate_diurnal_solar_telemetry(n_samples=1440, seed=seed)

    latencies_ms = []
    health_scores = []
    prs = []
    cm = ConfusionMatrix()

    start_total = time.perf_counter()

    for row in dataset:
        t0 = time.perf_counter()
        res = app.process_telemetry_packet(
            asset_id=asset_id,
            telemetry=row,
        )
        t_elapsed = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(t_elapsed)

        health_scores.append(res["composite_health_index"])
        prs.append(res["performance_ratio"])

        # Ground truth: normal sample (is_anomaly = False)
        anomalies_flagged = res["anomalies_detected"]
        if anomalies_flagged > 0:
            cm.false_positives += 1
        else:
            cm.true_negatives += 1

    total_time_s = time.perf_counter() - start_total
    throughput_obs_sec = round(len(dataset) / total_time_s, 2)

    latencies_sorted = sorted(latencies_ms)
    p95_idx = int(len(latencies_sorted) * 0.95)
    p99_idx = int(len(latencies_sorted) * 0.99)

    results = {
        "experiment_id": "EXP01_NORMAL_BASELINE",
        "description": "24-Hour Nominal Diurnal Operation Benchmark",
        "sample_count": len(dataset),
        "seed": seed,
        "detection_metrics": cm.to_dict(),
        "performance_metrics": {
            "mean_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 3),
            "p95_latency_ms": round(latencies_sorted[p95_idx], 3),
            "p99_latency_ms": round(latencies_sorted[p99_idx], 3),
            "throughput_obs_per_sec": throughput_obs_sec,
            "total_execution_time_s": round(total_time_s, 4),
        },
        "asset_condition_metrics": {
            "mean_health_index": round(sum(health_scores) / len(health_scores), 2),
            "min_health_index": round(min(health_scores), 2),
            "mean_performance_ratio": round(sum(prs) / len(prs), 3),
        },
        "audit_chain_valid": app.audit_logger.verify_chain_integrity()[0],
    }

    save_experiment_result("EXP01_NORMAL_BASELINE", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Completed {res['sample_count']} samples:")
    print(f"  FPR:        {res['detection_metrics']['false_positive_rate'] * 100:.2f}%")
    print(f"  Throughput: {res['performance_metrics']['throughput_obs_per_sec']} obs/sec")
    print(f"  Mean Latency:{res['performance_metrics']['mean_latency_ms']} ms")
    print(f"  Mean Health:{res['asset_condition_metrics']['mean_health_index']} / 100")
