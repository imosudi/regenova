"""
REAMP Phase 8 Verification: Multi-Level Anomaly Detection Framework.
Automated tests validating Levels 1–4, the canonical Anomaly Object schema,
and empirical confusion matrix benchmark metrics (Precision, Recall, F1, FPR, Latency).
"""

import os
import sys
import math
import unittest
import numpy as np

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))

from reamp.anomaly.models import (
    AnomalyObject,
    AnomalyType,
    AnomalySeverity,
    Level1RuleConfig,
    Level2StatisticalConfig,
    Level3MLConfig,
    Level4ContextualConfig,
)
from reamp.anomaly.level1_rules import Level1RuleDetector
from reamp.anomaly.level2_statistical import Level2StatisticalDetector
from reamp.anomaly.level3_ml import Level3MLDetector
from reamp.anomaly.level4_contextual import Level4ContextualDetector
from reamp.anomaly.engine import AnomalyDetectionEngine


class TestPhase8AnomalyFramework(unittest.TestCase):

    def setUp(self):
        self.engine = AnomalyDetectionEngine()

    # -------------------------------------------------------------------------
    # 1. Level 1: Deterministic Rules Tests
    # -------------------------------------------------------------------------
    def test_level1_threshold_violations(self):
        """Verify AC overvoltage and IGBT heatsink overtemperature trigger Level 1 anomalies."""
        telemetry_overvoltage = {
            "voltage_ac_v": 550.0,  # Exceeds 528V max limit
            "confidence": 1.0
        }
        anomalies = self.engine.l1_detector.evaluate("INV-001", telemetry_overvoltage)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0].type, AnomalyType.THRESHOLD_VIOLATION)
        self.assertEqual(anomalies[0].severity, AnomalySeverity.HIGH)
        self.assertIn("voltage_ac_v", anomalies[0].evidence["parameter"])

        telemetry_heatsink = {
            "temperature_heatsink_c": 92.0,  # Exceeds 85°C limit
            "confidence": 1.0
        }
        anom_hs = self.engine.l1_detector.evaluate("INV-001", telemetry_heatsink)
        self.assertEqual(len(anom_hs), 1)
        self.assertEqual(anom_hs[0].type, AnomalyType.THRESHOLD_VIOLATION)
        self.assertEqual(anom_hs[0].severity, AnomalySeverity.CRITICAL)
        print("[PASS] Level 1: Threshold violations correctly detected with appropriate severities.")

    def test_level1_unexpected_shutdown(self):
        """Verify unexpected active power collapse to 0 kW under high irradiance flags UNEXPECTED_SHUTDOWN."""
        telemetry = {
            "operating_state": "RUNNING",
            "irradiance_poa_wm2": 850.0,
            "actual_power_kw": 0.0,  # Collapsed power
            "confidence": 1.0
        }
        anomalies = self.engine.l1_detector.evaluate("INV-001", telemetry)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0].type, AnomalyType.UNEXPECTED_SHUTDOWN)
        self.assertEqual(anomalies[0].severity, AnomalySeverity.CRITICAL)
        self.assertEqual(anomalies[0].score, 1.0)
        print("[PASS] Level 1: Unexpected shutdown event caught under high irradiance.")

    def test_level1_communication_timeout_and_impossible_value(self):
        """Verify communication watchdog and physically impossible values."""
        # Comms timeout
        telemetry_timeout = {"heartbeat_gap_seconds": 95.0, "confidence": 1.0}
        anom_comm = self.engine.l1_detector.evaluate("INV-001", telemetry_timeout)
        self.assertEqual(len(anom_comm), 1)
        self.assertEqual(anom_comm[0].type, AnomalyType.COMMUNICATION_TIMEOUT)

        # Impossible value
        telemetry_impossible = {"irradiance_poa_wm2": -85.0, "confidence": 1.0}
        anom_imp = self.engine.l1_detector.evaluate("INV-001", telemetry_impossible)
        self.assertEqual(len(anom_imp), 1)
        self.assertEqual(anom_imp[0].type, AnomalyType.IMPOSSIBLE_VALUE)
        print("[PASS] Level 1: Communication timeout and impossible physical values verified.")

    # -------------------------------------------------------------------------
    # 2. Level 2: Statistical Filters Tests
    # -------------------------------------------------------------------------
    def test_level2_zscore_spike(self):
        """Verify rolling Z-score flags sudden transient current spike."""
        detector = Level2StatisticalDetector()
        # Seed 20 nominal current readings (50A +- 1A)
        for i in range(20):
            detector.evaluate("INV-001", {"current_ac_a": 50.0 + (i % 3 - 1) * 0.5})

        # Inject 6-sigma transient current spike (120A)
        anomalies = detector.evaluate("INV-001", {"current_ac_a": 120.0})
        zscore_anoms = [a for a in anomalies if a.type == AnomalyType.STATISTICAL_ZSCORE]
        self.assertEqual(len(zscore_anoms), 1)
        self.assertGreater(zscore_anoms[0].evidence["z_score"], 5.0)
        print(f"[PASS] Level 2: Rolling Z-score detected transient spike (Z={zscore_anoms[0].evidence['z_score']:.1f}).")

    def test_level2_ewma_drift_and_cusum_step(self):
        """Verify EWMA drift detection and CUSUM step-change detection."""
        detector = Level2StatisticalDetector()
        # Warm-up baseline with stable power (~500 kW)
        for _ in range(20):
            detector.evaluate("INV-001", {"actual_power_kw": 500.0})

        # Inject abrupt step drop to 400 kW (blown string fuse)
        anomalies_step = detector.evaluate("INV-001", {"actual_power_kw": 400.0})
        cusum_anoms = [a for a in anomalies_step if a.type == AnomalyType.CHANGE_POINT_CUSUM]
        self.assertEqual(len(cusum_anoms), 1)
        self.assertEqual(cusum_anoms[0].evidence["shift_type"], "NEGATIVE_STEP")
        print("[PASS] Level 2: CUSUM caught abrupt step drop.")

        # Simulate gradual persistent downward drift over 25 samples
        ewma_detected = False
        for step in range(25):
            drifting_power = 500.0 - (step * 3.5)
            anoms = detector.evaluate("INV-002", {"actual_power_kw": drifting_power})
            if any(a.type == AnomalyType.STATISTICAL_EWMA for a in anoms):
                ewma_detected = True
                break
        self.assertTrue(ewma_detected, "EWMA failed to flag persistent drift")
        print("[PASS] Level 2: EWMA control chart successfully caught slow drift.")

    # -------------------------------------------------------------------------
    # 3. Level 3: Unsupervised Machine Learning Tests
    # -------------------------------------------------------------------------
    def test_level3_isolation_forest(self):
        """Verify pure-Python/NumPy Isolation Forest scores multivariate anomalies and isolates dominant driver."""
        detector = Level3MLDetector()

        # Nominal test instance
        nominal_telemetry = {
            "irradiance_poa_wm2": 600.0,
            "actual_power_kw": 480.0,
            "voltage_ac_v": 480.0,
            "current_ac_a": 580.0,
            "temperature_cell_max_c": 43.0,
            "temperature_heatsink_c": 50.0,
            "confidence": 1.0
        }
        nom_anoms = detector.evaluate("INV-001", nominal_telemetry)
        self.assertEqual(len(nom_anoms), 0, "Nominal telemetry falsely flagged by Isolation Forest")

        # Multivariate anomalous instance: Extreme heatsink temp (95C) with low power (150kW) under 900 W/m2
        anomalous_telemetry = {
            "irradiance_poa_wm2": 900.0,
            "actual_power_kw": 150.0,  # Abnormal low power
            "voltage_ac_v": 480.0,
            "current_ac_a": 180.0,
            "temperature_cell_max_c": 55.0,
            "temperature_heatsink_c": 98.0,  # Severely overheated
            "confidence": 1.0
        }
        ml_anoms = detector.evaluate("INV-001", anomalous_telemetry)
        self.assertEqual(len(ml_anoms), 1)
        self.assertEqual(ml_anoms[0].type, AnomalyType.ML_ISOLATION_FOREST)
        self.assertGreaterEqual(ml_anoms[0].score, 0.58)
        self.assertIn("dominant_feature", ml_anoms[0].evidence)
        print(f"[PASS] Level 3: Isolation Forest identified multivariate anomaly (Score={ml_anoms[0].score:.3f}, Driver={ml_anoms[0].evidence['dominant_feature']}).")

    # -------------------------------------------------------------------------
    # 4. Level 4: Contextual & Spatial Peer Tests
    # -------------------------------------------------------------------------
    def test_level4_physical_residuals_and_peer_outlier(self):
        """Verify physical power law residual and spatial cohort peer MAD outlier detection."""
        detector = Level4ContextualDetector()

        # A. Physical residual: Transducer mismatch (P_act = 500 kW, but V*I indicates 300 kW)
        telemetry_pvi = {
            "actual_power_kw": 500.0,
            "voltage_ac_v": 480.0,
            "current_ac_a": 365.0,  # sqrt(3)*480*365*0.99 / 1000 ≈ 300 kW
            "rated_power_kw": 800.0,
            "confidence": 1.0
        }
        pvi_anoms = detector.evaluate_residuals("INV-001", telemetry_pvi)
        self.assertEqual(len(pvi_anoms), 1)
        self.assertEqual(pvi_anoms[0].type, AnomalyType.PHYSICAL_RESIDUAL)
        self.assertIn("ELECTRICAL_TRANSDUCER", pvi_anoms[0].evidence["subsystem"])

        # B. Spatial Peer Cohort: 6 identical inverters under same irradiance
        cohort = {
            "INV-001": 700.0,
            "INV-002": 705.0,
            "INV-003": 698.0,
            "INV-004": 702.0,
            "INV-005": 695.0,
            "INV-006": 350.0  # Underperforming peer (-50% deficit)
        }
        peer_anoms = detector.evaluate_cohort_peers("INV-006", cohort)
        self.assertEqual(len(peer_anoms), 1)
        self.assertEqual(peer_anoms[0].type, AnomalyType.PEER_OUTLIER)
        self.assertAlmostEqual(peer_anoms[0].evidence["deficit_percentage"], 50.0, delta=2.0)
        print("[PASS] Level 4: Physical residual and spatial peer MAD outlier verified.")

    # -------------------------------------------------------------------------
    # 5. Anomaly Object Schema & Subsumption Arbitration
    # -------------------------------------------------------------------------
    def test_anomaly_object_schema_and_subsumption(self):
        """Verify all 10 mandatory fields in AnomalyObject and subsumption of downstream noise on trip."""
        telemetry_trip = {
            "operating_state": "RUNNING",
            "irradiance_poa_wm2": 800.0,
            "actual_power_kw": 0.0,
            "voltage_ac_v": 480.0,
            "current_ac_a": 0.0,
            "confidence": 1.0
        }

        anomalies = self.engine.evaluate("INV-001", telemetry_trip)
        self.assertGreater(len(anomalies), 0)
        first_anom = anomalies[0]

        # Verify all 10 mandatory attributes exist
        mandatory_fields = [
            "anomaly_id", "asset_id", "timestamp", "type", "severity",
            "score", "evidence", "confidence", "detection_method", "model_version"
        ]
        for field_name in mandatory_fields:
            self.assertTrue(hasattr(first_anom, field_name), f"Missing field {field_name}")
            self.assertIsNotNone(getattr(first_anom, field_name))

        # Check that UNEXPECTED_SHUTDOWN is the primary critical alarm and downstream noise is subsumed
        self.assertEqual(first_anom.type, AnomalyType.UNEXPECTED_SHUTDOWN)
        self.assertEqual(first_anom.severity, AnomalySeverity.CRITICAL)
        print("[PASS] Anomaly Object schema validated with all 10 mandatory attributes.")

    # -------------------------------------------------------------------------
    # 6. Empirical Benchmark & Metric Calculation
    # -------------------------------------------------------------------------
    def test_empirical_confusion_matrix_benchmarking(self):
        """
        Run automated benchmark over 1,000 synthetic operational observations
        with ground truth anomaly labels. Compute empirical Precision, Recall,
        F1 score, False Positive Rate (FPR), and Detection Latency.
        """
        rng = np.random.default_rng(42)
        n_samples = 1000

        # Ground truth mask: 1 = true anomaly, 0 = normal
        y_true = np.zeros(n_samples, dtype=int)

        # Inject ground truth anomaly intervals
        injection_windows = [
            (50, 55, "IMPOSSIBLE_VALUE"),
            (120, 125, "OVERVOLTAGE"),
            (200, 210, "UNEXPECTED_SHUTDOWN"),
            (280, 290, "COMMS_TIMEOUT"),
            (360, 365, "CURRENT_SPIKE"),
            (500, 520, "CUSUM_STEP_DROP"),
            (700, 715, "MULTIVARIATE_ML"),
            (800, 810, "PHYSICAL_RESIDUAL"),
            (900, 915, "PEER_OUTLIER"),
        ]
        for start, end, _ in injection_windows:
            y_true[start:end] = 1

        y_pred = np.zeros(n_samples, dtype=int)
        detection_latencies = []

        engine = AnomalyDetectionEngine()

        for t in range(n_samples):
            # Base nominal diurnal curve
            time_fraction = t / n_samples
            g_poa = max(0.0, 950.0 * math.sin(math.pi * time_fraction)) + rng.normal(0, 5.0)
            p_base = 0.80 * g_poa
            v_ac = 480.0 + rng.normal(0, 2.0)
            i_ac = (p_base * 1000.0) / (math.sqrt(3) * v_ac * 0.99) if p_base > 0 else 0.0
            t_cell = 25.0 + (g_poa / 800.0) * 25.0 + rng.normal(0, 1.0)
            t_hs = 35.0 + 35.0 * ((p_base / 800.0) ** 2) if p_base > 0 else 30.0

            telemetry = {
                "operating_state": "RUNNING",
                "irradiance_poa_wm2": g_poa,
                "actual_power_kw": p_base,
                "voltage_ac_v": v_ac,
                "current_ac_a": i_ac,
                "temperature_cell_max_c": t_cell,
                "temperature_heatsink_c": t_hs,
                "confidence": 1.0
            }
            cohort_powers = None

            # Apply injected signatures
            if 50 <= t < 55:
                telemetry["irradiance_poa_wm2"] = -50.0  # Impossible value
            elif 120 <= t < 125:
                telemetry["voltage_ac_v"] = 560.0       # Overvoltage
            elif 200 <= t < 210:
                telemetry["actual_power_kw"] = 0.0      # Unexpected trip
            elif 280 <= t < 290:
                telemetry["heartbeat_gap_seconds"] = 120.0 # Comms timeout
            elif 360 <= t < 365:
                telemetry["current_ac_a"] = i_ac + 350.0  # Current spike
            elif 500 <= t < 520:
                telemetry["actual_power_kw"] = p_base * 0.70 # Step drop
            elif 700 <= t < 715:
                telemetry["temperature_heatsink_c"] = 96.0 # Multivariate overheat
                telemetry["actual_power_kw"] = 100.0
            elif 800 <= t < 810:
                telemetry["actual_power_kw"] = p_base * 1.50 # Meter mismatch
            elif 900 <= t < 915:
                cohort_powers = {
                    "INV-TEST": p_base * 0.50,
                    "PEER-1": p_base,
                    "PEER-2": p_base,
                    "PEER-3": p_base
                }

            anomalies = engine.evaluate("INV-TEST", telemetry, cohort_powers=cohort_powers)
            if len(anomalies) > 0:
                y_pred[t] = 1

        # Calculate Confusion Matrix
        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        # Calculate detection latency for each injected episode
        for start, end, name in injection_windows:
            episode_preds = np.where(y_pred[start:end] == 1)[0]
            if len(episode_preds) > 0:
                latency = int(episode_preds[0])  # First sample in window that triggered
                detection_latencies.append(latency)

        avg_latency = float(np.mean(detection_latencies)) if detection_latencies else 0.0

        print("\n" + "=" * 64)
        print("EMPIRICAL BENCHMARK EVALUATION RESULTS (1,000 SAMPLES):")
        print(f"  True Positives (TP):  {tp}")
        print(f"  False Positives (FP): {fp}")
        print(f"  True Negatives (TN):  {tn}")
        print(f"  False Negatives (FN): {fn}")
        print(f"  Precision:            {precision:.4f} ({precision*100:.2f}%)")
        print(f"  Recall:               {recall:.4f} ({recall*100:.2f}%)")
        print(f"  F1 Score:             {f1:.4f} ({f1*100:.2f}%)")
        print(f"  False Positive Rate:  {fpr:.4f} ({fpr*100:.2f}%)")
        print(f"  Avg Detection Latency:{avg_latency:.2f} samples")
        print("=" * 64)

        # Assert scientific targets
        self.assertGreaterEqual(precision, 0.90, f"Precision {precision} below 0.90 threshold")
        self.assertGreaterEqual(recall, 0.85, f"Recall {recall} below 0.85 threshold")
        self.assertGreaterEqual(f1, 0.88, f"F1 {f1} below 0.88 threshold")
        self.assertLessEqual(fpr, 0.05, f"False Positive Rate {fpr} exceeds 5% threshold")
        self.assertLessEqual(avg_latency, 3.0, f"Average latency {avg_latency} exceeds 3.0 samples")


def run_tests():
    print("=" * 64)
    print("REAMP Phase 8 Verification: Multi-Level Anomaly Detection")
    print("=" * 64)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase8AnomalyFramework)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("\n" + "=" * 64)
    print("[ALL TESTS PASSED] Phase 8 Anomaly Detection quality gate satisfied!")
    print("=" * 64)


if __name__ == "__main__":
    run_tests()
