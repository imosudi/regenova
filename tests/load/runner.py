"""
REAMP Phase 17 Master Scalability & Resilience Benchmark Runner.
Executes load sweeps (10 -> 10,000 assets), edge gateway scaling, database performance,
and infrastructure failure testing. Outputs structured results to results/scalability/.
"""

import os
import sys
import json
import time
import datetime
from typing import Dict, Any

from tests.load.test_asset_scaling import run_asset_scaling_benchmark
from tests.load.test_edge_fog_scaling import run_edge_fog_scaling_benchmark
from tests.load.test_database_performance import run_database_performance_benchmark
from tests.resilience.test_infrastructure_failures import run_all_resilience_tests


def print_banner(text: str) -> None:
    sep = "=" * 80
    print(f"\n{sep}\n {text} \n{sep}")


def main() -> None:
    t_start = time.perf_counter()
    timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print_banner("REAMP PHASE 17 - SCALABILITY & RESILIENCE BENCHMARK RUNNER")
    print(f"Execution Start: {timestamp_iso}")
    print("Evaluating progressive load scaling (10 -> 10,000 assets) and infrastructure fault resilience...\n")

    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "scalability"))
    os.makedirs(results_dir, exist_ok=True)

    # 1. Asset Load Scaling Benchmark
    print(">>> [1/4] Running Asset Scaling Load Benchmark (10 -> 10,000 assets)...")
    res_asset_scaling = run_asset_scaling_benchmark([10, 100, 1000, 10000])
    t10k = res_asset_scaling["tier_10000_assets"]
    print(f"    [DONE] Tier 10k: Throughput: {t10k['throughput_obs_per_sec']} obs/s | Latency: {t10k['mean_latency_ms']} ms | Peak Mem: {t10k['peak_memory_mb']} MB")

    # 2. Edge/Fog Gateway Scaling Benchmark
    print(">>> [2/4] Running Edge/Fog Multi-Gateway Scaling Benchmark (10 -> 250 gateways)...")
    res_edge_scaling = run_edge_fog_scaling_benchmark([10, 50, 100, 250])
    gw250 = res_edge_scaling["tier_250_gateways"]
    print(f"    [DONE] Gateways 250: Buffered: {gw250['total_observations']} | Loss Rate: {gw250['data_loss_rate_pct']:.4f}% | Backlog Drained: {gw250['backlog_drained']}")

    # 3. Database & Storage Performance Benchmark
    print(">>> [3/4] Running Database Batching & Temporal Window Query Benchmark...")
    res_db = run_database_performance_benchmark()
    b1000 = next(b for b in res_db["batching_evaluations"] if b["batch_size"] == 1000)
    q1h = next(q for q in res_db["query_evaluations"] if q["query_type"] == "1_hour_window")
    print(f"    [DONE] Batch Insert: {b1000['throughput_rows_sec']} rows/s | 1h Query: {q1h['mean_latency_ms']} ms ({q1h['queries_per_sec']} QPS)")

    # 4. Resilience & Infrastructure Fault Injection
    print(">>> [4/4] Running Infrastructure Fault Injection & Failure Testing (7 scenarios)...")
    res_resilience = run_all_resilience_tests()
    passed_scenarios = sum(1 for s in res_resilience.values() if s["status"] == "PASSED")
    print(f"    [DONE] Resilience Scenarios: {passed_scenarios} / {len(res_resilience)} passed successfully.")

    total_duration_s = round(time.perf_counter() - t_start, 3)

    # Compile Structured Reports
    load_summary = {
        "timestamp": timestamp_iso,
        "total_runtime_s": total_duration_s,
        "asset_scaling": res_asset_scaling,
        "edge_fog_scaling": res_edge_scaling,
        "database_performance": res_db,
    }

    resilience_summary = {
        "timestamp": timestamp_iso,
        "total_runtime_s": total_duration_s,
        "scenarios": res_resilience,
        "scenarios_passed_count": passed_scenarios,
        "total_scenarios_count": len(res_resilience),
    }

    # Quality Gate Evaluations
    gates = {
        "gate_01_scaling_throughput_adequate": all(t["throughput_obs_per_sec"] >= 1000.0 for t in res_asset_scaling.values()),
        "gate_02_sub_5ms_pipeline_latency": all(t["mean_latency_ms"] <= 5.0 for t in res_asset_scaling.values()),
        "gate_03_memory_footprint_bounded": t10k["peak_memory_mb"] <= 25.0,
        "gate_04_edge_fog_zero_loss": all(g["data_loss_rate_pct"] == 0.0 and g["backlog_drained"] for g in res_edge_scaling.values()),
        "gate_05_database_batching_efficiency": b1000["throughput_rows_sec"] >= 30000.0,
        "gate_06_database_sub_5ms_query": q1h["mean_latency_ms"] <= 5.0,
        "gate_07_gateway_crash_zero_loss": res_resilience["SCENARIO_01_GATEWAY_FAILURE"]["zero_data_loss"] is True,
        "gate_08_broker_partition_fifo": (res_resilience["SCENARIO_02_BROKER_PARTITION"]["fifo_order_preserved"] is True and res_resilience["SCENARIO_02_BROKER_PARTITION"]["data_loss_rate_pct"] == 0.0),
        "gate_09_database_rollback_intact": res_resilience["SCENARIO_03_DATABASE_INTERRUPTION"]["rollback_executed"] is True,
        "gate_10_delayed_telemetry_stable": res_resilience["SCENARIO_04_DELAYED_TELEMETRY"]["health_model_stable"] is True,
        "gate_11_cold_restart_audit_intact": res_resilience["SCENARIO_05_SERVICE_RESTART"]["audit_chain_intact"] is True,
        "gate_12_edge_autonomous_safety_trip": res_resilience["SCENARIO_06_PARTIAL_CLOUD_FAILURE"]["local_safety_trip_triggered"] is True,
        "gate_13_burst_spike_zero_loss": res_resilience["SCENARIO_07_BURST_TRAFFIC_SPIKE"]["zero_dropped_burst_packets"] is True,
    }

    load_summary["gates"] = gates
    load_summary["all_gates_passed"] = all(gates.values())

    # Write JSON files to results/scalability/
    load_summary_path = os.path.join(results_dir, "load_benchmark_summary.json")
    with open(load_summary_path, "w", encoding="utf-8") as f:
        json.dump(load_summary, f, indent=2)

    resilience_summary_path = os.path.join(results_dir, "resilience_summary.json")
    with open(resilience_summary_path, "w", encoding="utf-8") as f:
        json.dump(resilience_summary, f, indent=2)

    print_banner("PHASE 17 BENCHMARK QUALITY GATES")
    for g_name, g_pass in gates.items():
        status = "[PASS]" if g_pass else "[FAIL]"
        print(f"  {status} {g_name}")

    print(f"\nTotal Execution Time: {total_duration_s:.2f} seconds")
    print(f"Load Benchmark Output:       {load_summary_path}")
    print(f"Resilience Benchmark Output: {resilience_summary_path}")

    if not all(gates.values()):
        print("\n[ERROR] One or more Phase 17 quality gates failed!")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All 13 Scalability & Resilience Quality Gates Passed Successfully!\n")


if __name__ == "__main__":
    main()
