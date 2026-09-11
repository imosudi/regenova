"""
REAMP Phase 9 Verification Suite: Predictive Maintenance
Automated tests validating failure probability modeling, degradation trajectories,
Quality Gate uncertainty enforcement (refusal of false precision), multi-criteria priority scoring,
and four-paradigm separation (Reactive, Condition-Based, Predictive, Prescriptive).
"""

import os
import sys
import unittest
from typing import List, Tuple

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))

from reamp.maintenance.models import (
    MaintenanceParadigm,
    MaintenanceUrgency,
    MaintenancePriority,
    EvidenceSufficiency,
    PriorityWeightsConfig,
)
from reamp.maintenance.degradation import DegradationEngine
from reamp.maintenance.priority import MultiCriteriaPriorityEngine
from reamp.maintenance.engine import PredictiveMaintenanceEngine


class TestPhase9PredictiveMaintenance(unittest.TestCase):

    def setUp(self):
        self.engine = PredictiveMaintenanceEngine()
        self.deg_engine = DegradationEngine()
        self.priority_engine = MultiCriteriaPriorityEngine()

    # -------------------------------------------------------------------------
    # 1. Quality Gate: Explicit Uncertainty on Insufficient Evidence
    # -------------------------------------------------------------------------
    def test_quality_gate_insufficient_evidence_refuses_fake_precision(self):
        """
        Verify that when degradation history is sparse (N < 5) or telemetry confidence
        is low (< 0.60), the engine strictly adheres to the Phase 9 Quality Gate:
        refuses to claim a precise RUL, sets predicted_rul_hours = None, and flags uncertainty.
        """
        # Case A: Only 2 observation points
        sparse_history: List[Tuple[float, float]] = [
            (1000.0, 85.0),
            (1200.0, 82.0)
        ]
        rul_pred = self.deg_engine.estimate_rul(
            history=sparse_history,
            current_health=82.0,
            operating_hours=1200.0,
            telemetry_confidence=1.0
        )

        self.assertIsNone(rul_pred.predicted_rul_hours, "Engine must not fabricate RUL on N < 5")
        self.assertEqual(rul_pred.evidence_sufficiency, EvidenceSufficiency.INSUFFICIENT)
        self.assertTrue(rul_pred.uncertainty_flag)
        self.assertEqual(rul_pred.rul_confidence_interval, (0.0, 0.0))
        self.assertIn("Quality Gate Triggered", rul_pred.explanation)

        # Case B: Sufficient points (N=6) but low telemetry confidence (0.45)
        degraded_history: List[Tuple[float, float]] = [
            (1000.0, 90.0), (1200.0, 86.0), (1400.0, 82.0),
            (1600.0, 78.0), (1800.0, 74.0), (2000.0, 70.0)
        ]
        rul_noisy = self.deg_engine.estimate_rul(
            history=degraded_history,
            current_health=70.0,
            operating_hours=2000.0,
            telemetry_confidence=0.45  # Low confidence sensor stream
        )
        self.assertIsNone(rul_noisy.predicted_rul_hours, "Engine must refuse RUL on low confidence data")
        self.assertEqual(rul_noisy.evidence_sufficiency, EvidenceSufficiency.INSUFFICIENT)
        self.assertTrue(rul_noisy.uncertainty_flag)
        print("[PASS] Quality Gate: Explicit uncertainty enforced on sparse/noisy data; false precision refused.")

    # -------------------------------------------------------------------------
    # 2. Quality Gate: Statistically Validated RUL on Sufficient Evidence
    # -------------------------------------------------------------------------
    def test_quality_gate_sufficient_evidence_calculates_bounded_rul(self):
        """
        Verify that with consistent degradation trajectory (N >= 5, R2 >= 0.70),
        the engine calculates credible RUL and bounded 90% confidence intervals.
        """
        # Linear degradation: 0.02 points/hour (20 points per 1000 hours)
        # Starting at 90.0 at t=0, dropping to 50.0 at t=2000
        trajectory: List[Tuple[float, float]] = [
            (0.0, 90.0),
            (400.0, 82.0),
            (800.0, 74.2),
            (1200.0, 66.1),
            (1600.0, 58.0),
            (2000.0, 50.0)
        ]
        rul_pred = self.deg_engine.estimate_rul(
            history=trajectory,
            current_health=50.0,
            operating_hours=2000.0,
            eol_threshold=30.0,
            telemetry_confidence=1.0
        )

        self.assertIsNotNone(rul_pred.predicted_rul_hours)
        self.assertEqual(rul_pred.evidence_sufficiency, EvidenceSufficiency.SUFFICIENT)
        self.assertFalse(rul_pred.uncertainty_flag)
        self.assertGreaterEqual(rul_pred.r_squared, 0.95)

        # Expected RUL = (50 - 30) / 0.02 = 1000 operating hours
        self.assertAlmostEqual(rul_pred.predicted_rul_hours, 1000.0, delta=50.0)

        # Confidence interval bounding
        lower, upper = rul_pred.rul_confidence_interval
        self.assertLess(lower, rul_pred.predicted_rul_hours)
        self.assertGreater(upper, rul_pred.predicted_rul_hours)
        print(f"[PASS] Quality Gate: RUL extrapolated successfully ({rul_pred.predicted_rul_hours:.0f}h [{lower:.0f}h - {upper:.0f}h]).")

    # -------------------------------------------------------------------------
    # 3. Separation of Four Maintenance Paradigms
    # -------------------------------------------------------------------------
    def test_four_maintenance_paradigms_separation(self):
        """
        Verify that the engine distinctly identifies and classifies all four paradigms:
        Reactive, Condition-Based, Predictive, and Prescriptive.
        """
        # A. Reactive Maintenance (Asset in FAULT_TRIPPED state)
        rec_reactive = self.engine.evaluate_maintenance(
            asset_id="INV-001",
            operating_hours=5000.0,
            current_health_score=35.0,
            operational_state="FAULT_TRIPPED"
        )
        self.assertEqual(rec_reactive.paradigm, MaintenanceParadigm.REACTIVE)
        self.assertEqual(rec_reactive.urgency, MaintenanceUrgency.IMMEDIATE_HOURS)
        self.assertEqual(rec_reactive.priority, MaintenancePriority.P1_CRITICAL)

        # B. Condition-Based Maintenance (Depressed health score 48.0, but sparse history N=2)
        rec_cbm = self.engine.evaluate_maintenance(
            asset_id="INV-002",
            operating_hours=8000.0,
            current_health_score=48.0,
            health_history=[(7800.0, 52.0), (8000.0, 48.0)],
            operational_state="RUNNING"
        )
        self.assertEqual(rec_cbm.paradigm, MaintenanceParadigm.CONDITION_BASED)
        self.assertEqual(rec_cbm.urgency, MaintenanceUrgency.PLANNED_WEEKS)
        self.assertIsNone(rec_cbm.rul_prediction.predicted_rul_hours)

        # C. Predictive Maintenance (Validated trend, but spares not yet on site)
        trajectory = [
            (0.0, 90.0), (400.0, 82.0), (800.0, 74.0),
            (1200.0, 66.0), (1600.0, 58.0), (2000.0, 50.0)
        ]
        rec_pdm = self.engine.evaluate_maintenance(
            asset_id="INV-003",
            operating_hours=2000.0,
            current_health_score=50.0,
            health_history=trajectory,
            spares_logistics_score=50.0  # Spares not yet on-site
        )
        self.assertEqual(rec_pdm.paradigm, MaintenanceParadigm.PREDICTIVE)
        self.assertIsNotNone(rec_pdm.rul_prediction.predicted_rul_hours)

        # D. Prescriptive Maintenance (Validated trend + spares & crew on-site)
        rec_prescriptive = self.engine.evaluate_maintenance(
            asset_id="INV-004",
            operating_hours=2000.0,
            current_health_score=50.0,
            health_history=trajectory,
            spares_logistics_score=95.0,  # Spares ready on site
            spares_list=["IGBT_MODULE_SKU_44", "THERMAL_PASTE"]
        )
        self.assertEqual(rec_prescriptive.paradigm, MaintenanceParadigm.PRESCRIPTIVE)
        self.assertIn("Prescriptive intervention", rec_prescriptive.recommended_action)
        print("[PASS] Four maintenance paradigms (Reactive, CBM, PdM, Prescriptive) cleanly segregated.")

    # -------------------------------------------------------------------------
    # 4. Multi-Criteria Priority Model & Safety Override Gate
    # -------------------------------------------------------------------------
    def test_multi_criteria_priority_and_safety_override(self):
        """
        Verify composite risk scoring, tier mapping (P1-P4), and safety override enforcement.
        """
        # A. High Failure Probability & High Criticality -> P1 Critical
        p1, b1 = self.priority_engine.evaluate_priority(
            asset_id="TX-SUBSTATION-01",
            failure_prob_30d=0.85,
            criticality_score=100.0,
            daily_loss_usd=2500.0,
            safety_score=30.0,
            cost_avoidance_score=90.0,
            logistics_readiness=80.0
        )
        self.assertEqual(p1, MaintenancePriority.P1_CRITICAL)
        self.assertGreaterEqual(b1.composite_priority_score, 80.0)

        # B. Routine / Low Criticality Asset -> P4 Low
        p4, b4 = self.priority_engine.evaluate_priority(
            asset_id="COMBINER-BOX-12",
            failure_prob_30d=0.05,
            criticality_score=20.0,
            daily_loss_usd=5.0,
            safety_score=0.0,
            cost_avoidance_score=20.0,
            logistics_readiness=100.0
        )
        self.assertEqual(p4, MaintenancePriority.P4_LOW)
        self.assertLess(b4.composite_priority_score, 40.0)

        # C. Safety Override: Small string inverter ($10/day loss), but severe thermal runaway hazard (95.0)
        p_safe, b_safe = self.priority_engine.evaluate_priority(
            asset_id="INV-SMALL-05",
            failure_prob_30d=0.20,
            criticality_score=40.0,
            daily_loss_usd=10.0,
            safety_score=95.0,  # Critical arc flash / fire risk
            cost_avoidance_score=30.0,
            logistics_readiness=50.0
        )
        self.assertEqual(p_safe, MaintenancePriority.P1_CRITICAL, "Safety hazard must override economic score")
        self.assertTrue(b_safe.is_safety_override)
        print("[PASS] Multi-criteria priority scoring and safety override gate verified.")

    # -------------------------------------------------------------------------
    # 5. Determinism and Mathematical Attribution
    # -------------------------------------------------------------------------
    def test_determinism_and_mathematical_attribution(self):
        """Verify identical inputs produce identical recommendations and score contributions sum to total."""
        trajectory = [
            (0.0, 95.0), (500.0, 88.0), (1000.0, 81.0),
            (1500.0, 74.0), (2000.0, 67.0)
        ]
        rec1 = self.engine.evaluate_maintenance(
            asset_id="INV-TEST",
            operating_hours=2000.0,
            current_health_score=67.0,
            health_history=trajectory,
            daily_revenue_loss_usd=100.0
        )
        rec2 = self.engine.evaluate_maintenance(
            asset_id="INV-TEST",
            operating_hours=2000.0,
            current_health_score=67.0,
            health_history=trajectory,
            daily_revenue_loss_usd=100.0
        )

        self.assertEqual(rec1.priority, rec2.priority)
        self.assertEqual(rec1.priority_breakdown.composite_priority_score, rec2.priority_breakdown.composite_priority_score)
        self.assertEqual(rec1.rul_prediction.predicted_rul_hours, rec2.rul_prediction.predicted_rul_hours)

        # Factor attribution sum check
        b = rec1.priority_breakdown
        contrib_sum = (
            b.failure_probability_contrib +
            b.criticality_contrib +
            b.production_impact_contrib +
            b.safety_contrib +
            b.cost_avoidance_contrib +
            b.spares_logistics_contrib
        )
        self.assertAlmostEqual(contrib_sum, b.composite_priority_score, delta=0.1)
        print("[PASS] Determinism and factor attribution verified.")


def run_tests():
    print("=" * 64)
    print("REAMP Phase 9 Verification: Predictive Maintenance Framework")
    print("=" * 64)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase9PredictiveMaintenance)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("\n" + "=" * 64)
    print("[ALL TESTS PASSED] Phase 9 Predictive Maintenance quality gate satisfied!")
    print("=" * 64)


if __name__ == "__main__":
    run_tests()
