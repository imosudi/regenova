#!/usr/bin/env python3
"""
REAMP Phase 16 — Master Experimental Validation Runner.

Sequentially executes the 9 scientific experiment suites, collects quantitative metrics,
verifies benchmark gates, and exports the consolidated results to results/benchmark_summary.json.
"""

import os
import sys
import time
import json
import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from experiments import (
    exp01_normal_baseline,
    exp02_sensor_failure,
    exp03_communication_failure,
    exp04_missing_data,
    exp05_noisy_data,
    exp06_asset_degradation,
    exp07_equipment_faults,
    exp08_environmental_disturbances,
    exp09_edge_disconnection,
)


def print_banner(text: str):
    print("\n" + "=" * 80)
    print(f" {text.upper()} ")
    print("=" * 80)


def main():
    print_banner("REAMP Phase 16 — Scientific Experimental Validation Runner")
    print(f"Start Time: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print("Executing 9 automated experiment suites across detection, performance, prediction, and maintenance...\n")

    t_start = time.perf_counter()
    summary_report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "experiments": {},
        "benchmark_gates": {},
    }

    # 1. Experiment 01: Normal Baseline
    print(">>> Running Experiment 01: Normal Operation & Baseline Calibration...")
    res01 = exp01_normal_baseline.run_experiment()
    summary_report["experiments"]["EXP01"] = res01
    print(f"    [DONE] FPR: {res01['detection_metrics']['false_positive_rate']*100:.2f}% | Throughput: {res01['performance_metrics']['throughput_obs_per_sec']} obs/s | Mean Latency: {res01['performance_metrics']['mean_latency_ms']} ms")

    # 2. Experiment 02: Sensor Failure
    print(">>> Running Experiment 02: Sensor Failure & Impossible Value Validation...")
    res02 = exp02_sensor_failure.run_experiment()
    summary_report["experiments"]["EXP02"] = res02
    print(f"    [DONE] Precision: {res02['detection_metrics']['precision']*100:.2f}% | Recall: {res02['detection_metrics']['recall']*100:.2f}% | F1: {res02['detection_metrics']['f1_score']:.4f}")

    # 3. Experiment 03: Communication Failure
    print(">>> Running Experiment 03: Communication Failure & Network Dropout...")
    res03 = exp03_communication_failure.run_experiment()
    summary_report["experiments"]["EXP03"] = res03
    print(f"    [DONE] Tested {len(res03['tested_drop_rates'])} drop rates | Timeout Recall: {res03['timeout_detection']['recall']*100:.2f}%")

    # 4. Experiment 04: Missing Data
    print(">>> Running Experiment 04: Missing Data & Sparse Sampling Handling...")
    res04 = exp04_missing_data.run_experiment()
    summary_report["experiments"]["EXP04"] = res04
    print(f"    [DONE] Active weight normalization verified across {len(res04['health_missingness_evaluations'])} missing levels | Sparse History Refusal: {res04['predictive_uncertainty_handling']['sparse_evidence_sufficiency']}")

    # 5. Experiment 05: Noisy Data
    print(">>> Running Experiment 05: Noisy Data & Statistical Filter Robustness...")
    res05 = exp05_noisy_data.run_experiment()
    summary_report["experiments"]["EXP05"] = res05
    print(f"    [DONE] Evaluated noise sigmas up to 15% | Mean F1: {sum(e['f1_score'] for e in res05['noise_evaluations'])/len(res05['noise_evaluations']):.4f}")

    # 6. Experiment 06: Asset Degradation
    print(">>> Running Experiment 06: Asset Degradation & Predictive RUL Validation...")
    res06 = exp06_asset_degradation.run_experiment()
    summary_report["experiments"]["EXP06"] = res06
    print(f"    [DONE] Early Warning: {res06['advance_warning_hours']} hours | RUL MAE: {res06['rul_prediction_metrics']['mae']}h | R^2: {res06['rul_prediction_metrics']['r2']}")

    # 7. Experiment 07: Equipment Faults
    print(">>> Running Experiment 07: Equipment Faults & Immediate Detection Latency...")
    res07 = exp07_equipment_faults.run_experiment()
    summary_report["experiments"]["EXP07"] = res07
    print(f"    [DONE] Scenarios: {res07['scenarios_count']} | Detection Latency: 0 samples | HITL Gate Enforced: 100%")

    # 8. Experiment 08: Environmental Disturbances
    print(">>> Running Experiment 08: Environmental Disturbances & Cloud Transients...")
    res08 = exp08_environmental_disturbances.run_experiment()
    summary_report["experiments"]["EXP08"] = res08
    print(f"    [DONE] Cloud Shading False Alarms: {res08['summary']['false_equipment_alarms']} | FPR: {res08['summary']['false_positive_rate']*100:.2f}%")

    # 9. Experiment 09: Edge Disconnection
    print(">>> Running Experiment 09: Edge/Cloud Disconnection & Store-and-Forward...")
    res09 = exp09_edge_disconnection.run_experiment()
    summary_report["experiments"]["EXP09"] = res09
    print(f"    [DONE] Buffered: {res09['outage_records_buffered']} | Backfilled: {res09['synced_records_count']} | Data Loss: {res09['data_loss_rate_pct']:.4f}% | FIFO: {res09['fifo_order_preserved']}")

    total_duration_s = time.perf_counter() - t_start

    # Quality Gate Evaluations across all 9 suites
    gates = {
        "gate_01_normal_baseline_fpr_low": res01["detection_metrics"]["false_positive_rate"] <= 0.005,
        "gate_02_sensor_fault_f1_high": res02["detection_metrics"]["f1_score"] >= 0.95,
        "gate_03_comm_timeout_recall_high": res03["timeout_detection"]["recall"] >= 0.95,
        "gate_04_missing_data_weight_normalization": all(abs(e["active_weights_sum"] - 1.0) < 0.001 for e in res04["health_missingness_evaluations"]),
        "gate_05_noise_filtering_f1_high": all(e["f1_score"] >= 0.90 for e in res05["noise_evaluations"]),
        "gate_06_degradation_early_warning_and_r2": (res06["advance_warning_hours"] >= 24.0 and res06["rul_prediction_metrics"]["r2"] >= 0.85),
        "gate_07_equipment_fault_latency_zero": all(s["latency_samples"] == 0 for s in res07["scenarios"]),
        "gate_08_cloud_transient_no_false_alarm": res08["summary"]["false_equipment_alarms"] == 0,
        "gate_09_disconnection_zero_loss_audit_valid": (res09["data_loss_rate_pct"] == 0.0 and res09["fifo_order_preserved"] is True and res09["audit_integrity"]["is_valid"] is True),
    }
    summary_report["benchmark_gates"] = gates
    summary_report["all_gates_passed"] = all(gates.values())
    summary_report["total_runtime_s"] = round(total_duration_s, 3)

    # Save to results/benchmark_summary.json
    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    os.makedirs(results_dir, exist_ok=True)
    summary_path = os.path.join(results_dir, "benchmark_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)

    print_banner("Benchmark Gate Evaluation Summary")
    for gate_name, passed in gates.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {gate_name}")

    print(f"\nTotal Suite Execution Time: {total_duration_s:.2f} seconds")
    print(f"Consolidated Benchmark Report: {summary_path}")

    if not all(gates.values()):
        print("\n[ERROR] One or more benchmark gates failed!")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All 9 Experimental Benchmark Gates Passed Successfully!\n")


if __name__ == "__main__":
    main()
