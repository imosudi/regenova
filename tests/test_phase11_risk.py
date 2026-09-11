"""
REAMP Phase 11 Automated Verification Suite — Risk and Financial Intelligence.
Validates:
1. Mathematical Risk Formulation: Risk = Probability x Consequence.
2. Itemized Financial Loss: Lost Energy x Energy Value + Downtime + Maintenance + Replacement.
3. Configurable Economic Assumptions (No fake energy prices).
4. Safety Consequence Override Gate.
5. Fleet Asset Prioritization and Quality Gate Explainability:
   "A user must be able to understand why an asset has been prioritised."
"""

import os
import sys
import unittest

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.risk.models import (
    RiskTier,
    AssetCriticality,
    SafetySeverity,
    FinancialAssumptions,
    EventRiskProfile,
)
from reamp.risk.engine import RiskAndFinancialEngine


class TestPhase11RiskAndFinancialIntelligence(unittest.TestCase):
    """Test suite validating Phase 11 Risk and Financial Intelligence Engine."""

    def setUp(self):
        """Initializes standard engine with explicit PPA assumptions."""
        self.assumptions = FinancialAssumptions(
            currency="USD",
            energy_tariff_per_kwh=0.12,  # $0.12 / kWh PPA flat rate
            downtime_penalty_per_hour=50.0,
            technician_hourly_rate=90.0,
            crane_mobilization_cost=2500.0,
            source_reference="Bifacial-Solar-PPA-Contract-2024",
        )
        self.engine = RiskAndFinancialEngine(default_assumptions=self.assumptions)

    def test_01_mathematical_risk_and_financial_breakdown(self):
        """
        Validates Risk = Probability x Consequence, itemized financial loss decomposition,
        and ensures all 6 required output fields exist on EventRiskProfile.
        """
        profile = self.engine.calculate_event_risk(
            event_id="EVT-2026-1001",
            asset_id="INV-WEST-01",
            technical_severity="MAJOR",
            operational_consequence="Inverter IGBT overheating causing 40% generation curtailment",
            failure_probability=0.75,
            estimated_energy_loss_kwh=1500.0,
            asset_criticality=AssetCriticality.TIER_2_MAJOR,
            safety_severity=SafetySeverity.MODERATE,
            maintenance_lead_time_days=3,
            requires_special_tooling=False,
            expected_downtime_hours=2.5,
            maintenance_labor_hours=3.0,
            spare_parts_cost=120.0,
            asset_replacement_capital_cost=15000.0,
            confidence=0.92,
        )

        # 1. Verify 6 Required Output Fields
        self.assertEqual(profile.technical_severity, "MAJOR")
        self.assertIn("IGBT overheating", profile.operational_consequence)
        self.assertEqual(profile.estimated_energy_loss_kwh, 1500.0)
        self.assertGreater(profile.estimated_financial_impact, 0.0)
        self.assertEqual(profile.confidence, 0.92)
        self.assertIn("energy_tariff_applied", profile.assumptions)

        # 2. Verify Financial Loss Decomposition:
        # Energy Revenue Loss: 1500 kWh * $0.12 = $180.00
        fb = profile.financial_breakdown
        self.assertEqual(fb.energy_revenue_loss, 180.00)
        # Downtime Penalty: 2.5 hours * $50 = $125.00
        self.assertEqual(fb.downtime_penalty, 125.00)
        # Maintenance Cost: 3h * $90 labor ($270) + $120 parts = $390.00
        self.assertEqual(fb.maintenance_cost, 390.00)
        # Catastrophic Replacement Risk: 0.75 * $15,000 = $11,250.00
        self.assertEqual(fb.catastrophic_replacement_risk, 11250.00)

        # Total Financial Impact
        expected_total = 180.00 + 125.00 + 390.00 + 11250.00
        self.assertAlmostEqual(fb.total_financial_impact, expected_total, places=1)
        self.assertAlmostEqual(profile.estimated_financial_impact, expected_total, places=1)

        # 3. Verify Risk = Probability x Consequence
        cb = profile.consequence_breakdown
        expected_risk = round(0.75 * cb.composite_consequence_score, 1)
        self.assertAlmostEqual(profile.composite_risk_score, expected_risk, places=1)
        self.assertIn(profile.risk_tier, [RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.EXTREME])

    def test_02_assumption_configurability_no_fake_prices(self):
        """
        Validates that tariffs and costs are NEVER hardcoded.
        Changing the configured tariff changes the energy revenue loss in exact proportion.
        """
        # Baseline tariff ($0.10)
        assump_low = FinancialAssumptions(energy_tariff_per_kwh=0.10)
        prof_low = self.engine.calculate_event_risk(
            event_id="EVT-T1",
            asset_id="INV-01",
            technical_severity="MINOR",
            operational_consequence="Derate",
            failure_probability=0.50,
            estimated_energy_loss_kwh=1000.0,
            assumptions_override=assump_low,
        )
        self.assertEqual(prof_low.financial_breakdown.energy_revenue_loss, 100.00)

        # High tariff ($0.30)
        assump_high = FinancialAssumptions(energy_tariff_per_kwh=0.30)
        prof_high = self.engine.calculate_event_risk(
            event_id="EVT-T2",
            asset_id="INV-01",
            technical_severity="MINOR",
            operational_consequence="Derate",
            failure_probability=0.50,
            estimated_energy_loss_kwh=1000.0,
            assumptions_override=assump_high,
        )
        self.assertEqual(prof_high.financial_breakdown.energy_revenue_loss, 300.00)
        self.assertEqual(prof_high.financial_breakdown.energy_revenue_loss / prof_low.financial_breakdown.energy_revenue_loss, 3.0)

        # Audit transparency check
        self.assertEqual(prof_high.assumptions["energy_tariff_applied"], 0.30)

    def test_03_safety_consequence_override(self):
        """
        Validates that an acute safety hazard (e.g. thermal runaway risk)
        immediately escalates the risk tier to EXTREME, overriding small generation loss.
        """
        profile = self.engine.calculate_event_risk(
            event_id="EVT-BESS-THERMAL",
            asset_id="BESS-RACK-03",
            technical_severity="CRITICAL",
            operational_consequence="Cell temperature gradient exceeding safety margin; risk of thermal runaway",
            failure_probability=0.15,  # Low probability, but severe hazard
            estimated_energy_loss_kwh=50.0,  # Minimal energy loss
            asset_criticality=AssetCriticality.TIER_2_MAJOR,
            safety_severity=SafetySeverity.CATASTROPHIC,  # Safety score = 100
            expected_downtime_hours=1.0,
            maintenance_labor_hours=1.0,
        )

        self.assertTrue(profile.consequence_breakdown.is_safety_override)
        self.assertEqual(profile.risk_tier, RiskTier.EXTREME)
        self.assertGreaterEqual(profile.composite_risk_score, 85.0)

    def test_04_fleet_asset_prioritization_and_ranking(self):
        """
        Submits multiple assets with varying failure modes and verifies
        fleet-wide sorting: Safety emergencies first, followed by highest risk & financial loss.
        """
        # Asset 1: Low-criticality string with small energy loss
        p1 = self.engine.calculate_event_risk(
            event_id="EVT-STR-01",
            asset_id="STR-04-A",
            technical_severity="MINOR",
            operational_consequence="Blown string fuse",
            failure_probability=0.90,
            estimated_energy_loss_kwh=40.0,
            asset_criticality=AssetCriticality.TIER_3_BALANCE_OF_PLANT,
            safety_severity=SafetySeverity.NEGLIGIBLE,
        )

        # Asset 2: Central Inverter with high generation loss under peak sun
        p2 = self.engine.calculate_event_risk(
            event_id="EVT-INV-02",
            asset_id="INV-CENTRAL-02",
            technical_severity="MAJOR",
            operational_consequence="IGBT failure causing 500 kW generation loss",
            failure_probability=0.80,
            estimated_energy_loss_kwh=3500.0,
            asset_criticality=AssetCriticality.TIER_2_MAJOR,
            safety_severity=SafetySeverity.MODERATE,
            spare_parts_cost=500.0,
            asset_replacement_capital_cost=30000.0,
        )

        # Asset 3: BESS Rack with acute thermal runaway hazard
        p3 = self.engine.calculate_event_risk(
            event_id="EVT-BESS-01",
            asset_id="BESS-RACK-01",
            technical_severity="CRITICAL",
            operational_consequence="Cell temperature gradient runaway alert",
            failure_probability=0.30,
            estimated_energy_loss_kwh=100.0,
            asset_criticality=AssetCriticality.TIER_2_MAJOR,
            safety_severity=SafetySeverity.CATASTROPHIC,
        )

        ranking = self.engine.rank_fleet_assets([p1, p2, p3])

        # Verifications
        self.assertEqual(len(ranking), 3)
        # Rank 1 must be the safety emergency (BESS-RACK-01)
        self.assertEqual(ranking[0].asset_id, "BESS-RACK-01")
        self.assertEqual(ranking[0].dominant_driver, "ACUTE_SAFETY_HAZARD")
        self.assertEqual(ranking[0].risk_tier, RiskTier.EXTREME)

        # Rank 2 must be the major inverter (INV-CENTRAL-02)
        self.assertEqual(ranking[1].asset_id, "INV-CENTRAL-02")
        self.assertGreater(ranking[1].estimated_financial_impact, 10000.0)

        # Rank 3 must be the balance-of-plant string (STR-04-A)
        self.assertEqual(ranking[2].asset_id, "STR-04-A")

    def test_05_quality_gate_explainability(self):
        """
        Quality Gate Test:
        "A user must be able to understand why an asset has been prioritised."
        Verifies that explain_prioritization produces transparent, audit-ready
        explanations with numerical attribution and operational drivers.
        """
        profile = self.engine.calculate_event_risk(
            event_id="EVT-INV-EXPLAIN",
            asset_id="INV-EAST-04",
            technical_severity="MAJOR",
            operational_consequence="Severe cooling degradation derating active capacity",
            failure_probability=0.85,
            estimated_energy_loss_kwh=2200.0,
            asset_criticality=AssetCriticality.TIER_2_MAJOR,
            safety_severity=SafetySeverity.MODERATE,
            maintenance_lead_time_days=4,
            spare_parts_cost=250.0,
        )

        explanation, driver = self.engine.explain_prioritization(profile, rank=1, total_assets=15)

        # 1. Check dominant driver identification
        self.assertIn(driver, ["PRODUCTION_LOSS", "ASSET_CRITICALITY", "SAFETY_CONSEQUENCE", "MAINTENANCE_LOGISTICS"])

        # 2. Check explanation readability and completeness
        self.assertIn("Rank #1 of 15", explanation)
        self.assertIn("INV-EAST-04", explanation)
        self.assertIn("Score:", explanation)
        self.assertIn("Failure Probability: 85.0%", explanation)
        self.assertIn("Total financial exposure is $", explanation)
        self.assertIn("confidence", explanation)

        # 3. Print sample explanation for report evidence
        print("\n================================================================")
        print("SAMPLE QUALITY GATE EXPLAINABILITY OUTPUT:")
        print(explanation)
        print("================================================================\n")


if __name__ == "__main__":
    unittest.main()
