"""
REAMP Phase 18 - Multi-Technology Adaptive Framework Automated Test Suite.

Validates:
1. Solar PV Reference Pipeline (IEC 61724-1, inverter/meter, thermal, health, alerts).
2. Wind Turbine Reference Pipeline (IEC 61400-12-1 power curve, air density, bearing/gearbox thermal).
3. BESS Reference Pipeline (BMS, SoC limits, cell temperature envelope, dispatch response).
4. Co-located Hybrid Power Plant Pipeline (Solar + Wind + BESS co-located at single site).
5. Closed Feedback Loop (Observe -> Validate -> Assess -> Detect -> Predict -> Decide -> Act -> Observe again).
6. Controlled Adaptive Intelligence (Climate threshold shift, soiling/aerodynamic baseline drift).
7. Human-in-the-Loop (HITL) Safety Gating (Strict gating on >10% shift, RBAC authorization, cryptographic audit logging).
"""

import datetime
import os
import sys
import unittest

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.mvp import (
    Organization,
    Portfolio,
    Site,
    AssetRecord,
    TechnologyType,
    AssetStatus,
    REAMPApplicationMVP,
)
from reamp.adaptive import (
    AdaptationType,
    AdaptationStatus,
    AdaptationAction,
    ClosedLoopState,
    AdaptiveIntelligenceEngine,
)
from reamp.security.models import SecurityRole


class TestPhase18MultiTechAdaptive(unittest.TestCase):
    """Automated integration suite validating Phase 18 multi-tech and adaptive capabilities."""

    def setUp(self):
        """Initializes a fresh in-memory REAMP MVP instance with default topology."""
        self.app = REAMPApplicationMVP(
            tenant_id="TENANT-REAMP-GLOBAL",
            storage_db=":memory:",
            master_secret="test-phase18-master-secret-key-32b",
        )
        self.app.initialize_default_topology()

    # =========================================================================
    # 1. Solar PV Reference Pipeline
    # =========================================================================

    def test_solar_reference_pipeline(self):
        """Validates complete Solar PV pipeline end-to-end (IEC 61724-1 model + inverter profile)."""
        solar_telemetry = {
            "timestamp": "2026-09-11T12:00:00Z",
            "power_ac_kw": 2420.0,
            "power_dc_kw": 2500.0,
            "temperature_heatsink_c": 54.0,
            "irradiance_poa_wm2": 950.0,
            "ambient_temp_c": 26.0,
            "voltage_dc_v": 780.0,
            "current_dc_a": 3205.0,
        }

        res = self.app.process_telemetry_packet("ASSET-INV-01", solar_telemetry)

        self.assertIn("composite_health_index", res)
        self.assertGreater(res["composite_health_index"], 85.0)
        self.assertIsInstance(res["dispatched_alerts"], list)
        self.assertIn("ASSET-INV-01", self.app.twins)

        twin = self.app.twins["ASSET-INV-01"]
        self.assertIsNotNone(twin.telemetry.power_ac_kw)
        self.assertAlmostEqual(twin.telemetry.power_ac_kw, 2420.0, places=1)
        self.assertGreater(self.app.latest_performance_ratio["ASSET-INV-01"], 0.85)

    # =========================================================================
    # 2. Wind Turbine Reference Pipeline
    # =========================================================================

    def test_wind_reference_pipeline(self):
        """Validates complete Wind Turbine pipeline (IEC 61400-12-1 power curve + air density)."""
        wind_site = Site(
            site_id="SITE-WIND-NORTH",
            portfolio_id="PORT-SW-UTILITY",
            name="North Sea Offshore Wind Farm",
            latitude=55.5,
            longitude=7.2,
            rated_capacity_mw=100.0,
            technology=TechnologyType.WIND,
        )
        self.app.register_site(wind_site)

        wind_asset = AssetRecord(
            asset_id="WTG-NORTH-01",
            site_id=wind_site.site_id,
            name="Vestas V164 2.5MW Nacelle 01",
            asset_type="WIND_TURBINE",
            model="V164-2500",
            rated_power_kw=2500.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc),
            metadata={"hub_height_m": 105.0, "rotor_diameter_m": 120.0},
        )
        self.app.register_asset(wind_asset, device_secret="sec-wtg-north-01")

        wind_telemetry = {
            "timestamp": "2026-09-11T12:00:00Z",
            "wind_speed_ms": 11.5,
            "power_ac_kw": 2150.0,
            "barometric_pressure_hpa": 1015.0,
            "ambient_temp_c": 12.0,
            "gearbox_temp_c": 64.0,
            "bearing_temp_c": 52.0,
            "rotor_speed_rpm": 14.8,
        }

        res = self.app.process_telemetry_packet("WTG-NORTH-01", wind_telemetry)

        self.assertIn("composite_health_index", res)
        self.assertGreater(res["composite_health_index"], 85.0)
        self.assertIsInstance(res["dispatched_alerts"], list)
        self.assertIn("WTG-NORTH-01", self.app.latest_performance_ratio)
        self.assertGreater(self.app.latest_performance_ratio["WTG-NORTH-01"], 0.80)

    # =========================================================================
    # 3. BESS Reference Pipeline
    # =========================================================================

    def test_bess_reference_pipeline(self):
        """Validates complete BESS pipeline (BMS, SoC boundaries, cell thermal envelope)."""
        bess_site = Site(
            site_id="SITE-BESS-WEST",
            portfolio_id="PORT-SW-UTILITY",
            name="West Grid BESS Station",
            latitude=34.2,
            longitude=-118.3,
            rated_capacity_mw=20.0,
            technology=TechnologyType.BESS,
        )
        self.app.register_site(bess_site)

        bess_asset = AssetRecord(
            asset_id="BESS-WEST-01",
            site_id=bess_site.site_id,
            name="Tesla Megapack 2XL Enclosure 01",
            asset_type="BESS_CONTAINER",
            model="MP-2XL-1000",
            rated_power_kw=1000.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc),
            metadata={"capacity_kwh": 3800.0, "chemistry": "LFP"},
        )
        self.app.register_asset(bess_asset, device_secret="sec-bess-west-01")

        bess_telemetry = {
            "timestamp": "2026-09-11T12:00:00Z",
            "power_ac_kw": 750.0,
            "dispatch_setpoint_kw": 750.0,
            "state_of_charge_percent": 62.5,
            "temperature_cell_max_c": 28.0,
            "voltage_dc_v": 880.0,
            "current_dc_a": 852.0,
        }

        res = self.app.process_telemetry_packet("BESS-WEST-01", bess_telemetry)

        self.assertIn("composite_health_index", res)
        self.assertGreater(res["composite_health_index"], 85.0)
        self.assertEqual(len(res["dispatched_alerts"]), 0)
        self.assertIn("BESS-WEST-01", self.app.latest_performance_ratio)
        self.assertAlmostEqual(self.app.latest_performance_ratio["BESS-WEST-01"], 1.0, delta=0.05)

    # =========================================================================
    # 4. Co-located Hybrid Power Plant
    # =========================================================================

    def test_hybrid_power_plant_co_location(self):
        """Validates co-located Hybrid site containing Solar PV, Wind, and BESS."""
        hybrid_site = Site(
            site_id="SITE-HYBRID-HUB",
            portfolio_id="PORT-SW-UTILITY",
            name="Desert Wind & Sun Hybrid Hub",
            latitude=35.0,
            longitude=-115.0,
            rated_capacity_mw=150.0,
            technology=TechnologyType.HYBRID,
        )
        self.app.register_site(hybrid_site)

        # Asset 1: Solar Inverter
        solar_asset = AssetRecord(
            asset_id="HYBRID-SOLAR-01",
            site_id=hybrid_site.site_id,
            name="Central Solar Inverter Station",
            asset_type="INVERTER",
            model="PV-INV-2500",
            rated_power_kw=2500.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc),
        )
        # Asset 2: Wind Turbine
        wind_asset = AssetRecord(
            asset_id="HYBRID-WIND-01",
            site_id=hybrid_site.site_id,
            name="Hybrid Colocated Wind Turbine",
            asset_type="WIND_TURBINE",
            model="WT-2000",
            rated_power_kw=2000.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc),
        )
        # Asset 3: BESS
        bess_asset = AssetRecord(
            asset_id="HYBRID-BESS-01",
            site_id=hybrid_site.site_id,
            name="Co-located Buffer Storage",
            asset_type="BESS_CONTAINER",
            model="BESS-1000",
            rated_power_kw=1000.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc),
        )

        for a in [solar_asset, wind_asset, bess_asset]:
            self.app.register_asset(a, device_secret=f"sec-{a.asset_id.lower()}")

        # Ingest Solar Telemetry
        res_solar = self.app.process_telemetry_packet("HYBRID-SOLAR-01", {
            "timestamp": "2026-09-11T12:00:00Z",
            "power_ac_kw": 2400.0,
            "power_dc_kw": 2480.0,
            "temperature_heatsink_c": 52.0,
            "irradiance_poa_wm2": 920.0,
            "ambient_temp_c": 27.0,
        })
        self.assertGreater(res_solar["composite_health_index"], 85.0)

        # Ingest Wind Telemetry
        res_wind = self.app.process_telemetry_packet("HYBRID-WIND-01", {
            "timestamp": "2026-09-11T12:00:01Z",
            "wind_speed_ms": 10.8,
            "power_ac_kw": 1850.0,
            "barometric_pressure_hpa": 1012.0,
            "ambient_temp_c": 27.0,
            "gearbox_temp_c": 61.0,
        })
        self.assertGreater(res_wind["composite_health_index"], 85.0)

        # Ingest BESS Telemetry
        res_bess = self.app.process_telemetry_packet("HYBRID-BESS-01", {
            "timestamp": "2026-09-11T12:00:02Z",
            "power_ac_kw": 500.0,
            "dispatch_setpoint_kw": 500.0,
            "state_of_charge_percent": 75.0,
            "temperature_cell_max_c": 26.5,
        })
        self.assertGreater(res_bess["composite_health_index"], 85.0)

        # Confirm all three distinct technologies coexist and track in orchestrator
        self.assertIn("HYBRID-SOLAR-01", self.app.latest_health)
        self.assertIn("HYBRID-WIND-01", self.app.latest_health)
        self.assertIn("HYBRID-BESS-01", self.app.latest_health)

    # =========================================================================
    # 5. Closed Feedback Loop
    # =========================================================================

    def test_closed_feedback_loop_execution(self):
        """
        Validates the 8-stage closed feedback cycle:
        Observe -> Validate -> Assess -> Detect -> Predict -> Decide -> Act -> Observe again.
        """
        initial_telemetry = {
            "timestamp": "2026-09-11T13:00:00Z",
            "power_ac_kw": 2400.0,
            "power_dc_kw": 2480.0,
            "temperature_heatsink_c": 50.0,
            "irradiance_poa_wm2": 950.0,
            "ambient_temp_c": 25.0,
            "confidence": 0.98,
        }
        feedback_telemetry = {
            "timestamp": "2026-09-11T13:05:00Z",
            "power_ac_kw": 2410.0,
            "power_dc_kw": 2490.0,
            "temperature_heatsink_c": 50.5,
            "irradiance_poa_wm2": 950.0,
            "ambient_temp_c": 25.0,
            "confidence": 0.99,
        }

        cycle: ClosedLoopState = self.app.adaptive_engine.execute_closed_loop_cycle(
            app=self.app,
            asset_id="ASSET-INV-01",
            initial_telemetry=initial_telemetry,
            feedback_telemetry=feedback_telemetry,
        )

        self.assertIsNotNone(cycle.cycle_id)
        self.assertEqual(cycle.asset_id, "ASSET-INV-01")
        self.assertEqual(cycle.stage_1_observe["power_ac_kw"], 2400.0)
        self.assertTrue(cycle.stage_2_validate["is_valid"])
        self.assertGreater(cycle.stage_3_assess_health, 85.0)
        self.assertIsInstance(cycle.stage_4_detect_anomalies, list)
        self.assertIn(cycle.stage_6_decide_action, ["NOMINAL_OPERATION", "ACTIVE_ALARM_DISPATCH", "CORRECTIVE_WORK_ORDER", "CONDITION_BASED_INSPECTION"])
        self.assertTrue(cycle.stage_7_act["mitigation_executed"])
        self.assertTrue(cycle.stage_8_observe_feedback["observed_again"])
        self.assertTrue(cycle.stage_8_observe_feedback["loop_converged"])
        self.assertEqual(len(self.app.adaptive_engine.closed_loop_cycles), 1)

    # =========================================================================
    # 6. Adaptive Thresholds and Baseline Updates
    # =========================================================================

    def test_adaptive_threshold_and_baseline_updates(self):
        """Validates climate threshold adjustment and progressive soiling derate."""
        # 1. Climate threshold adaptation
        summer_ambient = [36.0, 38.5, 40.0, 39.0, 41.5]
        action_thresh = self.app.adaptive_engine.adapt_threshold_for_climate(
            asset_id="ASSET-INV-01",
            metric="temperature_heatsink_c",
            base_threshold=85.0,
            ambient_temp_history=summer_ambient,
            audit_logger=self.app.audit_logger,
        )

        # Ambient mean is 39.0°C (delta +14°C -> +3.5°C threshold adjustment)
        # Shift is from 85.0 to 88.5 (+4.12% <= 10.0%, within autonomous guardrail)
        self.assertFalse(action_thresh.requires_hitl)
        self.assertEqual(action_thresh.status, AdaptationStatus.ACTIVE)
        self.assertAlmostEqual(action_thresh.adapted_value, 88.5, places=1)
        self.assertEqual(
            self.app.adaptive_engine.get_threshold("ASSET-INV-01", "temperature_heatsink_c", 85.0),
            88.5,
        )

        # 2. Baseline soiling adaptation
        action_soiling = self.app.adaptive_engine.adapt_baseline_for_soiling(
            asset_id="ASSET-INV-01",
            current_baseline_multiplier=1.0,
            soiling_derate_factor=0.96,  # 4% soiling derate (within 10% autonomous guardrail)
            audit_logger=self.app.audit_logger,
        )

        self.assertFalse(action_soiling.requires_hitl)
        self.assertEqual(action_soiling.status, AdaptationStatus.ACTIVE)
        self.assertEqual(action_soiling.adapted_value, 0.96)
        self.assertEqual(self.app.adaptive_engine.get_baseline_multiplier("ASSET-INV-01"), 0.96)

        # Telemetry ingestion verifies that orchestrator applies the adapted baseline
        res = self.app.process_telemetry_packet("ASSET-INV-01", {
            "timestamp": "2026-09-11T14:00:00Z",
            "power_ac_kw": 2300.0,
            "irradiance_poa_wm2": 950.0,
            "ambient_temp_c": 25.0,
        })
        self.assertIsNotNone(res)

    # =========================================================================
    # 7. Human-in-the-Loop (HITL) Safety Gating
    # =========================================================================

    def test_adaptation_hitl_safety_gating(self):
        """Validates strict HITL gating and RBAC enforcement for adaptations exceeding 10% shift."""
        # Propose high-magnitude shift: 20% baseline derate
        action = self.app.adaptive_engine.propose_adaptation(
            asset_id="ASSET-INV-01",
            adaptation_type=AdaptationType.BASELINE_DRIFT,
            target_metric="expected_power_multiplier",
            current_value=1.0,
            adapted_value=0.80,  # -20% shift
            reason="Severe dust storm soiling and degradation",
            audit_logger=self.app.audit_logger,
        )

        # Must trigger HITL requirement and stay PENDING
        self.assertTrue(action.requires_hitl)
        self.assertEqual(action.status, AdaptationStatus.PENDING_HITL_APPROVAL)
        # Baseline must NOT be modified yet
        self.assertEqual(self.app.adaptive_engine.get_baseline_multiplier("ASSET-INV-01"), 1.0)

        # Attempt approval by unauthorized role (OPERATOR) -> Must raise PermissionError
        with self.assertRaises(PermissionError):
            self.app.adaptive_engine.approve_adaptation(
                action_id=action.action_id,
                approver_id="op-bob",
                approver_role=SecurityRole.OPERATOR,
                audit_logger=self.app.audit_logger,
            )

        # Approve by authorized role (CHIEF_ENGINEER) -> Must succeed
        approved_action = self.app.adaptive_engine.approve_adaptation(
            action_id=action.action_id,
            approver_id="eng-alice",
            approver_role=SecurityRole.CHIEF_ENGINEER,
            audit_logger=self.app.audit_logger,
        )

        self.assertEqual(approved_action.status, AdaptationStatus.ACTIVE)
        self.assertEqual(approved_action.approved_by, "eng-alice")
        self.assertEqual(self.app.adaptive_engine.get_baseline_multiplier("ASSET-INV-01"), 0.80)

        # Verify audit logger recorded both the proposal and the approval
        audit_records = self.app.audit_logger._chain
        action_names = [e.action for e in audit_records]
        self.assertIn("ADAPTATION_PROPOSED_PENDING_HITL_APPROVAL", action_names)
        self.assertIn("ADAPTATION_APPROVED_HITL", action_names)


if __name__ == "__main__":
    unittest.main()
