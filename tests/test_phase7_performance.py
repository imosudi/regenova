"""
REAMP Phase 7 Verification Suite: Performance Intelligence
Automated tests validating expected-generation modeling, loss attribution,
and the strict conceptual separation required by the Phase 7 Quality Gate:
1. Expected environmental variation
2. Under-performance
3. Missing data
4. Asset outage & curtailment
"""

import os
import sys
import unittest

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))

from reamp.performance.models import (
    OperatingState,
    LossCategory,
    PerformanceClassification,
    SolarParameters,
    WindParameters,
    BessParameters,
)
from reamp.performance.engine import PerformanceIntelligenceEngine
from reamp.performance.solar import SolarPerformanceModel
from reamp.performance.wind import WindPerformanceModel
from reamp.performance.bess import BessPerformanceModel


class TestPhase7PerformanceIntelligence(unittest.TestCase):

    def setUp(self):
        self.engine = PerformanceIntelligenceEngine()
        self.solar_params = SolarParameters(
            rated_dc_kw=1000.0,
            rated_ac_kw=800.0,   # DC/AC ratio = 1.25 (oversized DC array)
            gamma_pmp=-0.0038,   # -0.38% / degC
            nmot_c=45.0,
            soiling_factor=0.98,
            dc_loss_factor=0.98,
            inverter_efficiency=0.985,
            ppa_tariff_per_kwh=0.08
        )
        self.wind_params = WindParameters(
            rated_power_kw=2000.0,
            cut_in_speed_ms=3.0,
            rated_speed_ms=12.0,
            cut_out_speed_ms=25.0,
            ppa_tariff_per_kwh=0.07
        )
        self.bess_params = BessParameters(
            rated_power_kw=1000.0,
            rated_capacity_kwh=2000.0,
            rated_rte=0.88,
            ppa_tariff_per_kwh=0.10
        )

    # ------------------------------------------------------------------------
    # Scenario 1: Expected Environmental Variation (Overcast / Cloudy Day)
    # ------------------------------------------------------------------------
    def test_expected_environmental_variation_solar(self):
        """
        Verify that low generation caused by natural low irradiance (200 W/m2)
        is correctly classified as environmental variation, not an asset underperformance.
        """
        telemetry = {
            "operating_state": "RUNNING",
            "irradiance_poa_wm2": 200.0,
            "actual_power_kw": 185.0,
            "temperature_ambient_c": 18.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        result = self.engine.evaluate_solar("SOLAR-INV-001", self.solar_params, telemetry)

        # Expected power at 200 W/m2: ~ 1000 * 0.2 * 0.98 * 0.98 * ~1.0 * 0.985 ≈ 189 kW
        self.assertAlmostEqual(result.expected_power_kw, 189.26, delta=5.0)
        self.assertEqual(result.classification, PerformanceClassification.ENVIRONMENTAL_VARIATION)
        self.assertEqual(result.performance_gap_kw, 0.0)
        self.assertEqual(result.total_financial_loss, 0.0)
        # Verify PR_STC is healthy (> 0.90) despite low absolute generation
        self.assertGreater(result.weather_adjusted_pr, 0.90)

        # Check loss attribution contains RESOURCE_VARIATION
        categories = [l.category for l in result.losses]
        self.assertIn(LossCategory.RESOURCE_VARIATION, categories)
        self.assertNotIn(LossCategory.CONTROLLABLE_UNDERPERFORMANCE, categories)
        print("[PASS] Scenario 1: Low irradiance classified as ENVIRONMENTAL_VARIATION (no false alarm).")

    # ------------------------------------------------------------------------
    # Scenario 2: True Technical Underperformance (Soiling / String Fault)
    # ------------------------------------------------------------------------
    def test_true_underperformance_solar(self):
        """
        Verify that when weather conditions are prime (900 W/m2) but actual power
        is severely depressed (500 kW vs ~730 kW expected), the engine correctly
        identifies underperformance, quantifies performance gap, and calculates financial loss.
        """
        telemetry = {
            "operating_state": "RUNNING",
            "irradiance_poa_wm2": 900.0,
            "actual_power_kw": 500.0,
            "temperature_ambient_c": 25.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        duration_h = 2.0  # 2 hours evaluation
        result = self.engine.evaluate_solar("SOLAR-INV-001", self.solar_params, telemetry, duration_hours=duration_h)

        self.assertEqual(result.classification, PerformanceClassification.UNDERPERFORMING)
        self.assertGreater(result.performance_gap_kw, 150.0)
        self.assertLess(result.weather_adjusted_pr, 0.70)  # Severely depressed PR

        # Check financial loss calculation
        # gap (~230 kW) * 2.0 h * $0.08/kWh
        expected_min_loss = 150.0 * 2.0 * 0.08
        self.assertGreater(result.total_financial_loss, expected_min_loss)

        # Check loss waterfall isolates controllable underperformance
        underperf_losses = [l for l in result.losses if l.category == LossCategory.CONTROLLABLE_UNDERPERFORMANCE]
        self.assertEqual(len(underperf_losses), 1)
        self.assertAlmostEqual(underperf_losses[0].lost_power_kw, result.performance_gap_kw)
        print(f"[PASS] Scenario 2: True underperformance correctly flagged ({result.performance_gap_kw:.1f} kW gap, ${result.total_financial_loss:.2f} loss).")

    # ------------------------------------------------------------------------
    # Scenario 3: Missing Telemetry / Incomplete Data
    # ------------------------------------------------------------------------
    def test_missing_data_handling(self):
        """
        Verify that missing irradiance or power telemetry triggers MISSING_DATA,
        heavily penalizes confidence, and suppresses false equipment underperformance alarms.
        """
        telemetry_missing_poa = {
            "operating_state": "RUNNING",
            "irradiance_poa_wm2": None,  # Sensor drop
            "actual_power_kw": 400.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        result = self.engine.evaluate_solar("SOLAR-INV-001", self.solar_params, telemetry_missing_poa)

        self.assertEqual(result.classification, PerformanceClassification.MISSING_DATA)
        self.assertTrue(result.is_uncertain)
        self.assertLessEqual(result.confidence, 0.30)
        self.assertEqual(result.performance_gap_kw, 0.0)
        self.assertEqual(result.total_financial_loss, 0.0)
        self.assertIn("Critical telemetry", result.losses[0].explanation)
        print("[PASS] Scenario 3: Missing sensor telemetry gracefully flagged MISSING_DATA without false alarms.")

    # ------------------------------------------------------------------------
    # Scenario 4: Asset Outage & Grid Curtailment
    # ------------------------------------------------------------------------
    def test_asset_outage_and_curtailment(self):
        """
        Verify that an asset in FAULT_TRIPPED or CURTAILED state has its deficit
        attributed to availability downtime or grid curtailment, NOT physical degradation.
        """
        # A. Inverter Trip Outage
        telemetry_trip = {
            "operating_state": "FAULT_TRIPPED",
            "irradiance_poa_wm2": 800.0,
            "actual_power_kw": 0.0,
            "temperature_ambient_c": 25.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        result_trip = self.engine.evaluate_solar("SOLAR-INV-001", self.solar_params, telemetry_trip, duration_hours=1.0)
        self.assertEqual(result_trip.classification, PerformanceClassification.OUTAGE)
        self.assertGreater(result_trip.expected_power_kw, 600.0)
        self.assertEqual(result_trip.actual_power_kw, 0.0)
        self.assertEqual(result_trip.losses[0].category, LossCategory.ASSET_OUTAGE)
        self.assertGreater(result_trip.total_financial_loss, 40.0)

        # B. Grid Curtailment
        telemetry_curtailed = {
            "operating_state": "CURTAILED",
            "irradiance_poa_wm2": 1000.0,
            "actual_power_kw": 400.0,  # Curtailed to 400 kW while potential is 800 kW
            "curtailment_limit_kw": 400.0,
            "temperature_ambient_c": 25.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        result_curtail = self.engine.evaluate_solar("SOLAR-INV-001", self.solar_params, telemetry_curtailed, duration_hours=1.0)
        self.assertEqual(result_curtail.classification, PerformanceClassification.CURTAILED)
        self.assertEqual(result_curtail.losses[0].category, LossCategory.CURTAILMENT)
        self.assertAlmostEqual(result_curtail.losses[0].lost_power_kw, 400.0, delta=5.0)
        print("[PASS] Scenario 4: Outage and Curtailment correctly segregated from physical asset degradation.")

    # ------------------------------------------------------------------------
    # Scenario 5: IEC 61724-1 Temperature Compensation & Inverter Clipping
    # ------------------------------------------------------------------------
    def test_temperature_compensation_and_inverter_clipping(self):
        """
        Verify temperature derating and inverter saturation (clipping).
        Under 1100 W/m2 and 40°C ambient, array potential exceeds 800 kW AC rating.
        """
        telemetry_high_sun = {
            "operating_state": "RUNNING",
            "irradiance_poa_wm2": 1100.0,
            "actual_power_kw": 800.0,  # Inverter maxed out at rating
            "temperature_ambient_c": 35.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        result = self.engine.evaluate_solar("SOLAR-INV-001", self.solar_params, telemetry_high_sun)
        self.assertEqual(result.expected_power_kw, 800.0)
        self.assertEqual(result.actual_power_kw, 800.0)
        self.assertEqual(result.performance_gap_kw, 0.0)

        # Check that clipping loss was recorded in waterfall
        categories = [l.category for l in result.losses]
        self.assertIn(LossCategory.INVERTER_CLIPPING, categories)
        self.assertIn(LossCategory.THERMAL_DERATE, categories)
        print("[PASS] Scenario 5: IEC 61724-1 temperature derating and inverter clipping validated.")

    # ------------------------------------------------------------------------
    # Scenario 6: Multi-Technology Extensibility (Wind & BESS)
    # ------------------------------------------------------------------------
    def test_multi_technology_extensibility(self):
        """
        Verify Wind Turbine power curve tracking (IEC 61400-12-1) and BESS setpoint evaluation.
        """
        # A. Wind Turbine in Region II (8 m/s wind)
        wind_telemetry = {
            "operating_state": "RUNNING",
            "wind_speed_ms": 8.0,
            "actual_power_kw": 580.0,
            "pressure_barometric_hpa": 1013.25,
            "temperature_ambient_c": 15.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        wind_result = self.engine.evaluate_wind("WIND-TURBINE-001", self.wind_params, wind_telemetry)
        # Expected in Region II: ~ 2000 * (8^3 - 3^3) / (12^3 - 3^3) = 2000 * 485 / 1701 ≈ 570 kW
        self.assertAlmostEqual(wind_result.expected_power_kw, 570.25, delta=10.0)
        self.assertEqual(wind_result.classification, PerformanceClassification.NOMINAL)

        # B. BESS Setpoint Tracking
        bess_telemetry = {
            "operating_state": "RUNNING",
            "dispatch_setpoint_kw": 500.0,
            "actual_power_kw": 500.0,
            "state_of_charge_percent": 65.0,
            "temperature_cell_max_c": 28.0,
            "confidence": 1.0,
            "quality_status": "VALID"
        }

        bess_result = self.engine.evaluate_bess("BESS-RACK-001", self.bess_params, bess_telemetry)
        self.assertEqual(bess_result.expected_power_kw, 500.0)
        self.assertEqual(bess_result.actual_power_kw, 500.0)
        self.assertEqual(bess_result.performance_gap_kw, 0.0)
        print("[PASS] Scenario 6: Multi-technology extensibility (Wind power curve & BESS setpoint) verified.")


def run_tests():
    print("=" * 64)
    print("REAMP Phase 7 Verification: Performance Intelligence Engine")
    print("=" * 64)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase7PerformanceIntelligence)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("\n" + "=" * 64)
    print("[ALL TESTS PASSED] Phase 7 Performance Intelligence quality gate satisfied!")
    print("=" * 64)


if __name__ == "__main__":
    run_tests()
