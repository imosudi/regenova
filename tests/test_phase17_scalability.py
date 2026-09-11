"""
REAMP Phase 17 Automated Scalability & Resilience Test Suite.
Verifies progressive load scaling tiers, edge/fog concurrency, database batching/indexing,
and all 7 infrastructure failure recovery scenarios.
"""

import os
import json
import unittest

from tests.load.test_asset_scaling import run_asset_scaling_benchmark
from tests.load.test_edge_fog_scaling import run_edge_fog_scaling_benchmark
from tests.load.test_database_performance import run_database_performance_benchmark
from tests.resilience.test_infrastructure_failures import run_all_resilience_tests


class TestPhase17ScalabilityAndResilience(unittest.TestCase):
    """Rigorous unit and integration validation for REAMP Phase 17."""

    def test_01_asset_scaling_tiers(self):
        """Validates progressive asset scaling across 10, 100, and 1,000 asset tiers."""
        res = run_asset_scaling_benchmark([10, 100, 1000])

        for tier_name in ["tier_10_assets", "tier_100_assets", "tier_1000_assets"]:
            t = res[tier_name]
            self.assertGreaterEqual(
                t["throughput_obs_per_sec"], 1000.0,
                f"Throughput for {tier_name} must exceed 1,000 obs/sec"
            )
            self.assertLessEqual(
                t["mean_latency_ms"], 5.0,
                f"Mean processing latency for {tier_name} must remain <= 5.0 ms"
            )
            self.assertLessEqual(
                t["peak_memory_mb"], 15.0,
                f"Memory usage for {tier_name} must remain <= 15.0 MB"
            )

    def test_02_edge_fog_distributed_scaling(self):
        """Validates distributed edge gateway scaling and 0.00% data loss."""
        res = run_edge_fog_scaling_benchmark([10, 50])

        for gw_tier in ["tier_10_gateways", "tier_50_gateways"]:
            g = res[gw_tier]
            self.assertEqual(g["data_loss_rate_pct"], 0.0, f"Data loss must be 0.00% for {gw_tier}")
            self.assertTrue(g["backlog_drained"], f"Buffer backlog must be completely drained for {gw_tier}")
            self.assertGreater(g["buffering_throughput_obs_sec"], 5000.0)

    def test_03_database_batching_and_queries(self):
        """Validates database commit batching speed and sub-5ms temporal queries."""
        res = run_database_performance_benchmark()

        b1000 = next(b for b in res["batching_evaluations"] if b["batch_size"] == 1000)
        self.assertGreaterEqual(
            b1000["throughput_rows_sec"], 30000.0,
            "1000-row batching throughput must exceed 30,000 rows/sec"
        )

        q1h = next(q for q in res["query_evaluations"] if q["query_type"] == "1_hour_window")
        self.assertLessEqual(
            q1h["mean_latency_ms"], 5.0,
            "1-hour window query latency must be <= 5.0 ms"
        )

    def test_04_resilience_all_7_failure_scenarios(self):
        """Validates 100% recovery across all 7 infrastructure failure scenarios."""
        res = run_all_resilience_tests()

        expected_scenarios = [
            "SCENARIO_01_GATEWAY_FAILURE",
            "SCENARIO_02_BROKER_PARTITION",
            "SCENARIO_03_DATABASE_INTERRUPTION",
            "SCENARIO_04_DELAYED_TELEMETRY",
            "SCENARIO_05_SERVICE_RESTART",
            "SCENARIO_06_PARTIAL_CLOUD_FAILURE",
            "SCENARIO_07_BURST_TRAFFIC_SPIKE",
        ]

        for sc_id in expected_scenarios:
            self.assertIn(sc_id, res, f"Scenario {sc_id} must be evaluated")
            self.assertEqual(
                res[sc_id]["status"], "PASSED",
                f"Scenario {sc_id} ({res[sc_id]['name']}) must pass recovery gate"
            )

    def test_05_master_summary_artifacts_exist(self):
        """Validates that Phase 17 master runner outputs valid JSON artifacts."""
        results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results", "scalability"))
        load_summary_path = os.path.join(results_dir, "load_benchmark_summary.json")
        resilience_summary_path = os.path.join(results_dir, "resilience_summary.json")

        self.assertTrue(os.path.exists(load_summary_path), "load_benchmark_summary.json must exist")
        self.assertTrue(os.path.exists(resilience_summary_path), "resilience_summary.json must exist")

        with open(load_summary_path, "r", encoding="utf-8") as f:
            load_data = json.load(f)
        self.assertTrue(load_data.get("all_gates_passed"), "All 13 quality gates in load summary must be passed")

        with open(resilience_summary_path, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        self.assertEqual(res_data.get("scenarios_passed_count"), 7)


if __name__ == "__main__":
    unittest.main()
