"""
REAMP Phase 16 Automated Experimental Validation Test Suite.
Verifies all 9 experimental suites execute deterministically, satisfy quantitative quality gates,
and produce genuine scientific benchmarks matching AGENTS.md Rules 1-9.
"""

import unittest
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


class TestPhase16Experiments(unittest.TestCase):
    """Rigorous unit and integration validation for REAMP experimental validation suite."""

    def test_exp01_normal_baseline(self):
        """Experiment 01: Normal Diurnal Baseline & Throughput."""
        res = exp01_normal_baseline.run_experiment(seed=42)
        det = res["detection_metrics"]
        perf = res["performance_metrics"]

        self.assertEqual(det["false_positives"], 0, "Normal diurnal operation must produce zero false alarms")
        self.assertLessEqual(det["false_positive_rate"], 0.005)
        self.assertGreater(perf["throughput_obs_per_sec"], 500.0, "Throughput must exceed 500 observations/sec")
        self.assertLess(perf["mean_latency_ms"], 5.0, "Mean latency must be sub-5ms")

    def test_exp02_sensor_failure(self):
        """Experiment 02: Sensor Failure & Impossible Value Validation."""
        res = exp02_sensor_failure.run_experiment(seed=42)
        det = res["detection_metrics"]

        self.assertGreaterEqual(det["precision"], 0.95, "Sensor anomaly precision must exceed 95%")
        self.assertGreaterEqual(det["recall"], 0.95, "Sensor anomaly recall must exceed 95%")
        self.assertGreaterEqual(det["f1_score"], 0.95, "Sensor anomaly F1 must exceed 0.95")
        self.assertEqual(det["false_negatives"], 0, "Out-of-range sensor injections must not escape detection")

    def test_exp03_communication_failure(self):
        """Experiment 03: Communication Failure & Network Timeout."""
        res = exp03_communication_failure.run_experiment(seed=42)
        timeout = res["timeout_detection"]

        self.assertEqual(len(res["tested_drop_rates"]), 5)
        self.assertGreaterEqual(timeout["recall"], 0.95, "Watchdog timeout recall must be >= 95%")
        self.assertEqual(timeout["false_negatives"], 0, "No heartbeat expiration should be missed")

    def test_exp04_missing_data_weight_normalization(self):
        """Experiment 04: Active Weight Normalization & Refusal of False Precision."""
        res = exp04_missing_data.run_experiment(seed=42)
        evals = res["health_missingness_evaluations"]

        self.assertEqual(len(evals), 6)
        for e in evals:
            self.assertAlmostEqual(e["active_weights_sum"], 1.0, delta=0.001, msg="Active weights must sum to 1.0")

        # Uncertainty handling
        unc = res["predictive_uncertainty_handling"]
        self.assertEqual(unc["sparse_evidence_sufficiency"], "INSUFFICIENT", "Sparse history must refuse precise RUL")
        self.assertEqual(unc["rich_evidence_sufficiency"], "SUFFICIENT", "Rich history must allow RUL prediction")

    def test_exp05_noisy_data_statistical_filtering(self):
        """Experiment 05: Noisy Data & Statistical EWMA/CUSUM Filtering."""
        res = exp05_noisy_data.run_experiment(seed=42)
        evals = res["noise_evaluations"]

        self.assertEqual(len(evals), 4)
        for e in evals:
            self.assertGreaterEqual(e["f1_score"], 0.90, f"F1 score must exceed 0.90 for noise level {e['noise_sigma_kw']} kW")
            self.assertLessEqual(e["false_positive_rate"], 0.02, f"FPR must remain <= 2% under noise {e['noise_sigma_kw']} kW")

    def test_exp06_asset_degradation_and_rul(self):
        """Experiment 06: Progressive Asset Degradation & Weibull RUL Prediction."""
        res = exp06_asset_degradation.run_experiment(seed=42)
        metrics = res["rul_prediction_metrics"]

        self.assertGreaterEqual(metrics["r2"], 0.85, "RUL linear regression R^2 must exceed 0.85")
        self.assertLess(metrics["mae"], 60.0, "RUL MAE must be less than 60 operating hours")
        self.assertGreaterEqual(res["advance_warning_hours"], 24.0, "Must provide at least 24h early warning")
        self.assertIn("P1_CRITICAL", res["priority_transitions"]["all_priorities"])
        self.assertIn("P4_LOW", res["priority_transitions"]["all_priorities"])

    def test_exp07_equipment_fault_latency(self):
        """Experiment 07: Immediate Equipment Fault Detection Latency & HITL."""
        res = exp07_equipment_faults.run_experiment(seed=42)
        scenarios = res["scenarios"]

        self.assertEqual(len(scenarios), 3)
        for s in scenarios:
            self.assertEqual(s["latency_samples"], 0, f"Equipment fault latency must be 0 samples for {s['scenario']}")
            self.assertTrue(s["detected"])
            self.assertTrue(s["hitl_gate_enforced"])
            self.assertEqual(s["work_order_status"], "PENDING_HITL_APPROVAL")

    def test_exp08_environmental_disturbances(self):
        """Experiment 08: Rapid Cloud Transients & Weather-Adjusted False Alarm Rejection."""
        res = exp08_environmental_disturbances.run_experiment(seed=42)
        summary = res["summary"]

        self.assertEqual(summary["false_equipment_alarms"], 0, "Cloud shading must not trigger equipment alarms")
        self.assertEqual(summary["false_positive_rate"], 0.0)

    def test_exp09_edge_disconnection_and_audit(self):
        """Experiment 09: Edge Disconnection, Zero Data Loss, and Audit Integrity."""
        res = exp09_edge_disconnection.run_experiment(seed=42)

        self.assertEqual(res["outage_records_buffered"], 500)
        self.assertEqual(res["synced_records_count"], 500)
        self.assertEqual(res["data_loss_rate_pct"], 0.0, "Store-and-forward must produce 0.00% data loss")
        self.assertTrue(res["fifo_order_preserved"], "FIFO chronological order must be preserved")
        self.assertTrue(res["audit_integrity"]["is_valid"], "Cryptographic audit chain must remain intact")


if __name__ == "__main__":
    unittest.main()
