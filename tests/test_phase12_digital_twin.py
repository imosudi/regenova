"""
REAMP Phase 12 Automated Verification Suite — Digital Twin and Asset State.
Validates:
1. Complete 10-dimensional digital representation for a reference Solar PV asset (Quality Gate).
2. Physics-based expected state computation and real-time state residual tracking.
3. Edge-to-twin synchronization, clock-skew protection, and buffer re-synchronization.
4. Forward what-if simulation and operational sandboxing:
   - Ambient heatwave derating scenario;
   - Cooling fan failure trip horizon scenario;
   - Deferred maintenance degradation scenario.
"""

import os
import sys
import unittest
import datetime

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.digital_twin.models import (
    SyncStatus,
    TwinIdentity,
    InverterConfiguration,
    SimulationScenario,
    TwinFullState,
)
from reamp.digital_twin.synchronisation import DigitalTwinSyncEngine
from reamp.digital_twin.twin import SolarInverterDigitalTwin


class TestPhase12DigitalTwin(unittest.TestCase):
    """Test suite validating Phase 12 Digital Twin and Asset State framework."""

    def setUp(self):
        """Initializes a reference 500 kW Solar PV Inverter Digital Twin."""
        self.identity = TwinIdentity(
            asset_id="INV-WEST-01",
            serial_number="SMA-SC-500-CP-XT-8819",
            manufacturer="SMA Solar Technology",
            model="Sunny Central 500CP XT",
            site_id="SITE-SOLAR-PARK-B",
            subsystem_ids=["FAN-ARRAY-01", "IGBT-BRIDGE-A", "IGBT-BRIDGE-B", "DC-CAPACITORS"],
        )
        self.config = InverterConfiguration(
            rated_ac_power_kw=500.0,
            rated_dc_power_kw=625.0,
            nominal_voltage_ac=400.0,
            mppt_voltage_min=550.0,
            mppt_voltage_max=850.0,
            thermal_resistance_c_per_kw=1.8,
            temp_coefficient_pct_per_c=-0.0038,
            max_heatsink_temp_c=88.0,
            trip_heatsink_temp_c=95.0,
        )
        self.sync_engine = DigitalTwinSyncEngine(
            heartbeat_timeout_seconds=60.0,
            stale_timeout_seconds=300.0,
            max_future_drift_seconds=10.0,
        )
        self.twin = SolarInverterDigitalTwin(
            identity=self.identity,
            configuration=self.config,
            sync_engine=self.sync_engine,
        )

    def test_01_complete_10_dimensional_representation(self):
        """
        Quality Gate Test:
        Demonstrates a complete digital representation for at least one reference Solar asset.
        Verifies that get_state_snapshot() captures all 10 required dimensions:
        1. Identity, 2. Configuration, 3. Current Telemetry, 4. Historical Trajectory,
        5. Expected State, 6. Health State, 7. Performance State, 8. Anomaly State,
        9. Maintenance State, 10. Predicted State.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        now_str = now.isoformat()

        # Ingest live operational telemetry
        telemetry = {
            "timestamp": now_str,
            "sequence_number": 101,
            "power_ac_kw": 462.4,
            "power_dc_kw": 475.2,
            "voltage_dc_v": 680.0,
            "current_dc_a": 698.8,
            "voltage_ac_v": 402.1,
            "temperature_heatsink_c": 64.2,
            "ambient_temperature_c": 28.0,
            "poa_irradiance_w_per_m2": 820.0,
            "wind_speed_m_per_s": 2.5,
            "operating_mode": "FEED_IN_NORMAL",
        }
        self.twin.update_telemetry(telemetry, current_wall_clock=now)

        # Attach cross-phase intelligence streams
        self.twin.attach_health(
            health_index=76.5,
            component_scores={"igbt": 82.0, "cooling": 68.0, "capacitors": 79.5},
        )
        self.twin.attach_performance(pr=0.812, availability=1.0, curtailment=False)
        self.twin.attach_anomalies([
            {"anomaly_id": "ANOM-20260911-0088", "severity": "MAJOR", "root_cause": "COOLING_FAN_DEGRADATION"}
        ])
        self.twin.attach_maintenance(
            active_work_order_id="WO-E984CA12",
            status="APPROVED",
            technician="Alice Morgan (TECH-001)",
            downtime_hours=12.5,
        )
        self.twin.attach_predicted(
            rul_hours=720.0,
            ci=[680.0, 760.0],
            failure_prob_30d=0.28,
            risk_tier="HIGH",
        )

        # Generate full snapshot
        snapshot = self.twin.get_state_snapshot()
        self.assertIsInstance(snapshot, TwinFullState)

        # 1. Identity
        self.assertEqual(snapshot.identity.asset_id, "INV-WEST-01")
        self.assertEqual(snapshot.identity.model, "Sunny Central 500CP XT")

        # 2. Configuration
        self.assertEqual(snapshot.configuration.rated_ac_power_kw, 500.0)

        # 3. Telemetry
        self.assertEqual(snapshot.telemetry.power_ac_kw, 462.4)

        # 4. Historical Trajectory
        self.assertEqual(len(self.twin.historical_states), 1)

        # 5. Expected State
        self.assertGreater(snapshot.expected_state.expected_power_ac_kw, 400.0)
        self.assertGreater(snapshot.expected_state.expected_efficiency, 0.95)

        # 6. Health State
        self.assertEqual(snapshot.health.composite_health_index, 76.5)
        self.assertEqual(snapshot.health.component_health["cooling"], 68.0)

        # 7. Performance State
        self.assertEqual(snapshot.performance.performance_ratio, 0.812)

        # 8. Anomaly State
        self.assertEqual(snapshot.anomalies.active_anomaly_count, 1)

        # 9. Maintenance State
        self.assertEqual(snapshot.maintenance.active_work_order_id, "WO-E984CA12")

        # 10. Predicted State
        self.assertEqual(snapshot.predicted.predicted_rul_hours, 720.0)
        self.assertEqual(snapshot.predicted.risk_tier, "HIGH")

        # Verify JSON serializability
        d = snapshot.to_dict()
        self.assertIn("sync_status", d)
        self.assertIn("identity", d)
        self.assertIn("configuration", d)
        self.assertIn("telemetry", d)
        self.assertIn("expected_state", d)
        self.assertIn("residuals", d)
        self.assertIn("health", d)
        self.assertIn("performance", d)
        self.assertIn("anomalies", d)
        self.assertIn("maintenance", d)
        self.assertIn("predicted", d)

    def test_02_physics_expected_state_and_residuals(self):
        """
        Validates internal first-principles physics models:
        - IEC 61724-1 irradiance and temperature-derated power output
        - Inverter efficiency curve
        - Heatsink thermal model
        - Residual state tracking and anomaly flags
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # Nominal high irradiance telemetry (800 W/m2, 25C amb)
        # Expected AC should be ~444 kW with cell heating derate, heatsink ~50-55C
        telemetry = {
            "timestamp": now.isoformat(),
            "sequence_number": 1,
            "power_ac_kw": 410.0,  # ~34 kW lower than expected (underperforming)
            "power_dc_kw": 450.0,
            "voltage_dc_v": 650.0,
            "current_dc_a": 692.0,
            "voltage_ac_v": 400.0,
            "temperature_heatsink_c": 72.0,  # Elevated above ~50C expected
            "ambient_temperature_c": 25.0,
            "poa_irradiance_w_per_m2": 800.0,
            "wind_speed_m_per_s": 2.0,
        }
        snap = self.twin.update_telemetry(telemetry, current_wall_clock=now)

        # Check expected power calculation
        exp_ac = snap.expected_state.expected_power_ac_kw
        self.assertGreater(exp_ac, 430.0)
        self.assertLessEqual(exp_ac, 500.0)

        # Check residuals: Power residual must be negative and flagged
        self.assertLess(snap.residuals.power_residual_kw, -25.0)
        self.assertTrue(snap.residuals.is_power_deviating)

        # Check thermal residual: Heatsink is hotter than expected physics model
        self.assertGreater(snap.residuals.temperature_residual_c, 8.0)
        self.assertTrue(snap.residuals.is_thermal_deviating)

    def test_03_synchronization_and_staleness_watchdog(self):
        """
        Validates the state synchronization engine:
        - Transition from SYNCHRONIZED -> DEGRADED_COMMUNICATION -> OUT_OF_SYNC
        - Clock-skew detection and packet rejection
        - Replay reconciliation of store-and-forward edge buffers
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Fresh packet (age 5s) -> SYNCHRONIZED
        t_fresh = (now - datetime.timedelta(seconds=5)).isoformat()
        status_fresh = self.sync_engine.evaluate_sync_status(t_fresh, current_time=now)
        self.assertEqual(status_fresh, SyncStatus.SYNCHRONIZED)

        # 2. Delayed packet (age 90s) -> DEGRADED_COMMUNICATION
        t_lag = (now - datetime.timedelta(seconds=90)).isoformat()
        status_lag = self.sync_engine.evaluate_sync_status(t_lag, current_time=now)
        self.assertEqual(status_lag, SyncStatus.DEGRADED_COMMUNICATION)

        # 3. Stale packet (age 400s) -> OUT_OF_SYNC
        t_stale = (now - datetime.timedelta(seconds=400)).isoformat()
        status_stale = self.sync_engine.evaluate_sync_status(t_stale, current_time=now)
        self.assertEqual(status_stale, SyncStatus.OUT_OF_SYNC)

        # 4. Clock-skew violation: Packet 60s in the future -> ValueError
        t_future = (now + datetime.timedelta(seconds=60)).isoformat()
        with self.assertRaises(ValueError) as ctx:
            self.sync_engine.validate_packet({"timestamp": t_future}, current_time=now)
        self.assertIn("Clock Skew Violation", str(ctx.exception))

        # 5. Buffer reconciliation: Deduplication and sequence reordering
        raw_buffer = [
            {"timestamp": (now - datetime.timedelta(seconds=20)).isoformat(), "sequence_number": 3, "val": 30},
            {"timestamp": (now - datetime.timedelta(seconds=40)).isoformat(), "sequence_number": 1, "val": 10},
            {"timestamp": (now - datetime.timedelta(seconds=30)).isoformat(), "sequence_number": 2, "val": 20},
            {"timestamp": (now - datetime.timedelta(seconds=30)).isoformat(), "sequence_number": 2, "val": 20},  # duplicate
        ]
        reconciled = self.sync_engine.reconcile_edge_buffer(raw_buffer)
        self.assertEqual(len(reconciled), 3)
        self.assertEqual(reconciled[0]["sequence_number"], 1)
        self.assertEqual(reconciled[1]["sequence_number"], 2)
        self.assertEqual(reconciled[2]["sequence_number"], 3)

    def test_04_what_if_simulation_capabilities(self):
        """
        Validates forward what-if simulation scenarios:
        1. Ambient heatwave scenario (+15C) predicting thermal derating.
        2. Cooling fan failure scenario (2.5x thermal resistance) predicting emergency trip.
        3. Deferred maintenance scenario (30 days) predicting escalated failure probability.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        telemetry = {
            "timestamp": now.isoformat(),
            "sequence_number": 50,
            "power_ac_kw": 480.0,
            "power_dc_kw": 495.0,
            "voltage_dc_v": 700.0,
            "current_dc_a": 707.1,
            "voltage_ac_v": 400.0,
            "temperature_heatsink_c": 60.0,
            "ambient_temperature_c": 28.0,
            "poa_irradiance_w_per_m2": 950.0,
            "wind_speed_m_per_s": 2.0,
        }
        self.twin.update_telemetry(telemetry, current_wall_clock=now)

        # Scenario 1: Heatwave Simulation with Dusty Filter (+18C ambient offset and 1.6x R_th)
        scenario_heatwave = SimulationScenario(
            scenario_id="SIM-HEATWAVE-01",
            name="Severe Regional Heatwave with Filter Clogging",
            ambient_temp_offset_c=18.0,
            cooling_degradation_factor=1.6,
            duration_hours=4.0,
        )
        res_heatwave = self.twin.simulate_what_if(scenario_heatwave, tariff_per_kwh=0.12)
        self.assertGreater(res_heatwave.projected_heatsink_temp_c, 85.0)
        self.assertGreater(res_heatwave.projected_energy_loss_kwh, 0.0)
        self.assertGreater(res_heatwave.projected_financial_loss_usd, 0.0)
        self.assertIn("Heatwave", res_heatwave.explanation)

        # Scenario 2: Severe Cooling Subsystem Failure (2.5x R_th)
        scenario_fan_failure = SimulationScenario(
            scenario_id="SIM-FAN-FAIL",
            name="Cooling Fan Array Seizure",
            cooling_degradation_factor=2.5,
            duration_hours=2.0,
        )
        res_fan = self.twin.simulate_what_if(scenario_fan_failure, tariff_per_kwh=0.12)
        self.assertTrue(res_fan.will_trip)
        self.assertEqual(res_fan.thermal_curtailment_pct, 100.0)
        self.assertEqual(res_fan.projected_power_ac_kw, 0.0)
        self.assertIsNotNone(res_fan.time_to_trip_minutes)
        self.assertIn("Thermal trip triggered", res_fan.explanation)

        # Scenario 3: Deferred Maintenance (Postponing 30 days)
        scenario_deferred = SimulationScenario(
            scenario_id="SIM-DEFERRED-30D",
            name="Deferred Capacitor Replacement",
            defer_maintenance_days=30,
            duration_hours=24.0,
        )
        res_deferred = self.twin.simulate_what_if(scenario_deferred, tariff_per_kwh=0.12)
        # Failure probability must escalate over baseline
        self.assertGreater(res_deferred.projected_failure_probability, self.twin.predicted.failure_probability_30d)


if __name__ == "__main__":
    unittest.main()
