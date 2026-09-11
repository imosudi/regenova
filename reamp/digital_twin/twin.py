"""
REAMP Digital Twin Implementation.
Provides a reference Solar Photovoltaic Inverter Digital Twin with real-time state synchronization,
first-principles physics models, residual tracking, and what-if simulation sandbox.
"""

from typing import Dict, Any, List, Optional, Tuple
import datetime
import math
import copy

from reamp.digital_twin.models import (
    SyncStatus,
    InverterOperatingMode,
    TwinIdentity,
    InverterConfiguration,
    ObservedTelemetryState,
    PhysicsExpectedState,
    StateResiduals,
    HealthStateSnapshot,
    PerformanceStateSnapshot,
    AnomalyStateSnapshot,
    MaintenanceStateSnapshot,
    PredictedStateSnapshot,
    TwinFullState,
    SimulationScenario,
    SimulationResult,
)
from reamp.digital_twin.synchronisation import DigitalTwinSyncEngine


class SolarInverterDigitalTwin:
    """
    Active computational digital twin representing a utility-scale Solar PV Inverter.
    Combines real-time telemetry, internal physics models, state residual tracking,
    and forward what-if simulation.
    """

    def __init__(
        self,
        identity: TwinIdentity,
        configuration: Optional[InverterConfiguration] = None,
        sync_engine: Optional[DigitalTwinSyncEngine] = None,
        max_history_len: int = 1000,
    ) -> None:
        self.identity = copy.deepcopy(identity)
        self.config = copy.deepcopy(configuration or InverterConfiguration())
        self.sync_engine = sync_engine or DigitalTwinSyncEngine()
        self.max_history_len = max_history_len

        # Initial baseline states for all 10 dimensions
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self.sync_status: SyncStatus = SyncStatus.SYNCHRONIZED
        self.telemetry: ObservedTelemetryState = ObservedTelemetryState(
            timestamp=now_str,
            sequence_number=0,
            power_ac_kw=0.0,
            power_dc_kw=0.0,
            voltage_dc_v=0.0,
            current_dc_a=0.0,
            voltage_ac_v=0.0,
            temperature_heatsink_c=25.0,
            ambient_temperature_c=25.0,
            poa_irradiance_w_per_m2=0.0,
        )
        self.expected_state: PhysicsExpectedState = PhysicsExpectedState(
            expected_cell_temperature_c=25.0,
            expected_power_dc_kw=0.0,
            expected_efficiency=0.98,
            expected_power_ac_kw=0.0,
            expected_heatsink_temp_c=25.0,
        )
        self.residuals: StateResiduals = StateResiduals(
            power_residual_kw=0.0,
            temperature_residual_c=0.0,
            efficiency_residual=0.0,
            is_power_deviating=False,
            is_thermal_deviating=False,
        )
        self.health: HealthStateSnapshot = HealthStateSnapshot(
            composite_health_index=100.0,
            component_health={"igbt": 100.0, "cooling": 100.0, "capacitors": 100.0},
        )
        self.performance: PerformanceStateSnapshot = PerformanceStateSnapshot(
            performance_ratio=1.0,
            availability=1.0,
            curtailment_active=False,
        )
        self.anomalies: AnomalyStateSnapshot = AnomalyStateSnapshot(
            active_anomaly_count=0,
            active_anomalies=[],
        )
        self.maintenance: MaintenanceStateSnapshot = MaintenanceStateSnapshot(
            active_work_order_id=None,
            work_order_status=None,
            assigned_technician=None,
            historical_downtime_hours=0.0,
        )
        self.predicted: PredictedStateSnapshot = PredictedStateSnapshot(
            predicted_rul_hours=5000.0,
            rul_confidence_interval=[4500.0, 5500.0],
            failure_probability_30d=0.01,
            risk_tier="LOW",
        )

        self.historical_states: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. Physics Engine (Expected State Calculation)
    # -------------------------------------------------------------------------

    def compute_physics_expected(
        self,
        poa_irradiance: float,
        ambient_temp: float,
        wind_speed: float = 2.0,
        thermal_resistance_multiplier: float = 1.0,
    ) -> PhysicsExpectedState:
        """
        Executes internal first-principles physics model:
        1. King/Sandia PV cell temperature model
        2. Temperature-derated DC array generation
        3. Empirical 3-parameter inverter efficiency curve
        4. AC output with nameplate clipping
        5. Lumped-parameter heatsink dissipation
        """
        if poa_irradiance <= 5.0:
            return PhysicsExpectedState(
                expected_cell_temperature_c=ambient_temp,
                expected_power_dc_kw=0.0,
                expected_efficiency=0.0,
                expected_power_ac_kw=0.0,
                expected_heatsink_temp_c=ambient_temp,
                is_clipping=False,
            )

        # 1. Cell Temperature
        # King / Sandia thermal model: T_cell = T_amb + G * exp(-3.56 - 0.075 * v_wind) + 3.0 * (G / 1000)
        thermal_elevation = poa_irradiance * math.exp(-3.56 - 0.075 * wind_speed) + 3.0 * (poa_irradiance / 1000.0)
        cell_temp = ambient_temp + thermal_elevation

        # 2. DC Expected Generation
        temp_factor = 1.0 + self.config.temp_coefficient_pct_per_c * (cell_temp - 25.0)
        p_dc_expected = self.config.rated_dc_power_kw * (poa_irradiance / 1000.0) * max(0.5, temp_factor)

        # 3. Inverter Efficiency Curve: eta = p / (p + 0.008 + 0.025 * p^2)
        norm_load = p_dc_expected / self.config.rated_ac_power_kw
        if norm_load > 0.05:
            eff = norm_load / (norm_load + 0.008 + 0.025 * (norm_load ** 2))
            eff = max(0.85, min(0.985, eff))
        else:
            eff = 0.85

        # 4. AC Expected Generation with Nameplate Saturation
        p_ac_raw = p_dc_expected * eff
        is_clipping = p_ac_raw > self.config.rated_ac_power_kw
        p_ac_expected = min(self.config.rated_ac_power_kw, p_ac_raw)

        # 5. Heatsink Thermal Model: T_heatsink = T_amb + P_loss * R_th
        p_loss_kw = max(0.0, p_dc_expected - p_ac_expected)
        effective_r_th = self.config.thermal_resistance_c_per_kw * thermal_resistance_multiplier
        heatsink_temp = ambient_temp + (p_loss_kw * effective_r_th)

        return PhysicsExpectedState(
            expected_cell_temperature_c=round(cell_temp, 1),
            expected_power_dc_kw=round(p_dc_expected, 1),
            expected_efficiency=round(eff, 3),
            expected_power_ac_kw=round(p_ac_expected, 1),
            expected_heatsink_temp_c=round(heatsink_temp, 1),
            is_clipping=is_clipping,
        )

    # -------------------------------------------------------------------------
    # 2. Telemetry Ingestion & Synchronization
    # -------------------------------------------------------------------------

    def update_telemetry(
        self,
        telemetry: Dict[str, Any],
        current_wall_clock: Optional[datetime.datetime] = None,
        is_replaying_buffer: bool = False,
    ) -> TwinFullState:
        """
        Synchronizes live telemetry stream with digital twin state:
        - Validates packet timestamp & clock skew
        - Evaluates synchronization state
        - Runs physics engine to calculate expected state & residuals
        - Records historical trajectory
        """
        self.sync_engine.validate_packet(telemetry, current_wall_clock)

        # Update sync status
        self.sync_status = self.sync_engine.evaluate_sync_status(
            latest_telemetry_timestamp=telemetry["timestamp"],
            current_time=current_wall_clock,
            is_replaying_buffer=is_replaying_buffer,
        )

        op_mode_str = telemetry.get("operating_mode", "FEED_IN_NORMAL")
        try:
            op_mode = InverterOperatingMode(op_mode_str)
        except ValueError:
            op_mode = InverterOperatingMode.FEED_IN_NORMAL

        # Store observed telemetry
        self.telemetry = ObservedTelemetryState(
            timestamp=telemetry["timestamp"],
            sequence_number=telemetry.get("sequence_number", 0),
            power_ac_kw=float(telemetry.get("power_ac_kw", 0.0)),
            power_dc_kw=float(telemetry.get("power_dc_kw", 0.0)),
            voltage_dc_v=float(telemetry.get("voltage_dc_v", 0.0)),
            current_dc_a=float(telemetry.get("current_dc_a", 0.0)),
            voltage_ac_v=float(telemetry.get("voltage_ac_v", 0.0)),
            temperature_heatsink_c=float(telemetry.get("temperature_heatsink_c", 25.0)),
            ambient_temperature_c=float(telemetry.get("ambient_temperature_c", 25.0)),
            poa_irradiance_w_per_m2=float(telemetry.get("poa_irradiance_w_per_m2", 0.0)),
            wind_speed_m_per_s=float(telemetry.get("wind_speed_m_per_s", 2.0)),
            operating_mode=op_mode,
            quality_flag=telemetry.get("quality_flag", "GOOD"),
        )

        # Execute physics model
        self.expected_state = self.compute_physics_expected(
            poa_irradiance=self.telemetry.poa_irradiance_w_per_m2,
            ambient_temp=self.telemetry.ambient_temperature_c,
            wind_speed=self.telemetry.wind_speed_m_per_s,
        )

        # Calculate live state residuals
        actual_eff = (
            self.telemetry.power_ac_kw / self.telemetry.power_dc_kw
            if self.telemetry.power_dc_kw > 10.0
            else self.expected_state.expected_efficiency
        )

        power_residual = self.telemetry.power_ac_kw - self.expected_state.expected_power_ac_kw
        temp_residual = self.telemetry.temperature_heatsink_c - self.expected_state.expected_heatsink_temp_c
        eff_residual = actual_eff - self.expected_state.expected_efficiency

        self.residuals = StateResiduals(
            power_residual_kw=round(power_residual, 1),
            temperature_residual_c=round(temp_residual, 1),
            efficiency_residual=round(eff_residual, 3),
            is_power_deviating=abs(power_residual) > 25.0,
            is_thermal_deviating=temp_residual > 8.0,
        )

        # Update historical state buffer
        snapshot_dict = {
            "timestamp": self.telemetry.timestamp,
            "power_ac_kw": self.telemetry.power_ac_kw,
            "expected_power_ac_kw": self.expected_state.expected_power_ac_kw,
            "power_residual_kw": self.residuals.power_residual_kw,
            "temperature_heatsink_c": self.telemetry.temperature_heatsink_c,
            "expected_heatsink_temp_c": self.expected_state.expected_heatsink_temp_c,
            "temperature_residual_c": self.residuals.temperature_residual_c,
            "health_index": self.health.composite_health_index,
        }
        self.historical_states.append(snapshot_dict)
        if len(self.historical_states) > self.max_history_len:
            self.historical_states.pop(0)

        return self.get_state_snapshot()

    # -------------------------------------------------------------------------
    # 3. Multi-Domain Bridges (Attaching Health, Anomaly, CMMS, Predictive)
    # -------------------------------------------------------------------------

    def attach_health(self, health_index: float, component_scores: Optional[Dict[str, float]] = None) -> None:
        """Integrates condition health intelligence from Phase 6."""
        status = "GOOD" if health_index >= 80.0 else ("WARNING" if health_index >= 60.0 else "CRITICAL")
        self.health = HealthStateSnapshot(
            composite_health_index=round(health_index, 1),
            component_health=component_scores or {},
            status=status,
        )

    def attach_performance(self, pr: float, availability: float = 1.0, curtailment: bool = False) -> None:
        """Integrates performance intelligence from Phase 7."""
        self.performance = PerformanceStateSnapshot(
            performance_ratio=round(pr, 3),
            availability=round(availability, 3),
            curtailment_active=curtailment,
        )

    def attach_anomalies(self, active_anomalies: List[Dict[str, Any]]) -> None:
        """Integrates active anomaly events from Phase 8."""
        self.anomalies = AnomalyStateSnapshot(
            active_anomaly_count=len(active_anomalies),
            active_anomalies=copy.deepcopy(active_anomalies),
        )

    def attach_maintenance(
        self,
        active_work_order_id: Optional[str],
        status: Optional[str],
        technician: Optional[str] = None,
        downtime_hours: float = 0.0,
    ) -> None:
        """Integrates CMMS work order tracking from Phase 10."""
        self.maintenance = MaintenanceStateSnapshot(
            active_work_order_id=active_work_order_id,
            work_order_status=status,
            assigned_technician=technician,
            historical_downtime_hours=round(downtime_hours, 1),
        )

    def attach_predicted(
        self,
        rul_hours: Optional[float],
        ci: Optional[List[float]],
        failure_prob_30d: float,
        risk_tier: str = "LOW",
    ) -> None:
        """Integrates predictive RUL and risk from Phase 9 and Phase 11."""
        self.predicted = PredictedStateSnapshot(
            predicted_rul_hours=rul_hours,
            rul_confidence_interval=ci,
            failure_probability_30d=round(failure_prob_30d, 3),
            risk_tier=risk_tier,
        )

    # -------------------------------------------------------------------------
    # 4. State Snapshot Generation (Satisfies Phase 12 Quality Gate)
    # -------------------------------------------------------------------------

    def get_state_snapshot(self) -> TwinFullState:
        """
        Produces a consolidated 10-dimensional digital twin snapshot.
        Demonstrates complete representation for reference solar asset.
        """
        return TwinFullState(
            timestamp=self.telemetry.timestamp,
            sync_status=self.sync_status,
            identity=copy.deepcopy(self.identity),
            configuration=copy.deepcopy(self.config),
            telemetry=copy.deepcopy(self.telemetry),
            expected_state=copy.deepcopy(self.expected_state),
            residuals=copy.deepcopy(self.residuals),
            health=copy.deepcopy(self.health),
            performance=copy.deepcopy(self.performance),
            anomalies=copy.deepcopy(self.anomalies),
            maintenance=copy.deepcopy(self.maintenance),
            predicted=copy.deepcopy(self.predicted),
        )

    # -------------------------------------------------------------------------
    # 5. Forward Simulation & What-If Sandbox
    # -------------------------------------------------------------------------

    def simulate_what_if(
        self,
        scenario: SimulationScenario,
        tariff_per_kwh: float = 0.12,
    ) -> SimulationResult:
        """
        Runs forward operational simulation under hypothetical environmental
        stress, cooling degradation, or deferred maintenance windows.
        """
        sim_irradiance = (
            scenario.irradiance_override_w_per_m2
            if scenario.irradiance_override_w_per_m2 is not None
            else self.telemetry.poa_irradiance_w_per_m2
        )
        sim_ambient = self.telemetry.ambient_temperature_c + scenario.ambient_temp_offset_c

        # Execute physics under degraded thermal resistance
        sim_expected = self.compute_physics_expected(
            poa_irradiance=sim_irradiance,
            ambient_temp=sim_ambient,
            wind_speed=self.telemetry.wind_speed_m_per_s,
            thermal_resistance_multiplier=scenario.cooling_degradation_factor,
        )

        projected_hs_temp = sim_expected.expected_heatsink_temp_c
        projected_power = sim_expected.expected_power_ac_kw

        # Thermal Derating / Curtailment Check
        curtailment_pct = 0.0
        will_trip = False
        time_to_trip = None

        if projected_hs_temp >= self.config.trip_heatsink_temp_c:
            will_trip = True
            time_to_trip = round(max(5.0, 60.0 / scenario.cooling_degradation_factor), 1)
            projected_power = 0.0
            curtailment_pct = 100.0
            explanation = (
                f"Scenario '{scenario.name}': Thermal trip triggered! Heatsink temperature projected "
                f"at {projected_hs_temp:.1f}°C, exceeding trip limit ({self.config.trip_heatsink_temp_c}°C). "
                f"Estimated time to shutdown: {time_to_trip} minutes."
            )
        elif projected_hs_temp > self.config.max_heatsink_temp_c:
            # Linear derate: reduce power by 5% per degree C above max
            over_temp = projected_hs_temp - self.config.max_heatsink_temp_c
            curtailment_pct = min(80.0, over_temp * 5.0)
            projected_power = projected_power * (1.0 - (curtailment_pct / 100.0))
            explanation = (
                f"Scenario '{scenario.name}': Inverter enters thermal derating. Projected heatsink temp "
                f"{projected_hs_temp:.1f}°C exceeds threshold ({self.config.max_heatsink_temp_c}°C), "
                f"inducing {curtailment_pct:.1f}% capacity curtailment."
            )
        else:
            explanation = (
                f"Scenario '{scenario.name}': Inverter operates within safe thermal margins. "
                f"Projected heatsink temp is {projected_hs_temp:.1f}°C (max {self.config.max_heatsink_temp_c}°C)."
            )

        # Calculate projected energy and financial deficit
        nominal_generation = sim_expected.expected_power_ac_kw * scenario.duration_hours
        simulated_generation = projected_power * scenario.duration_hours
        energy_loss_kwh = max(0.0, nominal_generation - simulated_generation)
        financial_loss_usd = energy_loss_kwh * tariff_per_kwh

        # Projected failure probability (escalated if maintenance is deferred)
        base_pf = self.predicted.failure_probability_30d
        deferred_factor = 1.0 + (scenario.defer_maintenance_days / 15.0) * 0.5
        cooling_penalty = 1.0 + (scenario.cooling_degradation_factor - 1.0) * 0.4
        proj_pf = min(0.99, base_pf * deferred_factor * cooling_penalty)

        return SimulationResult(
            scenario_id=scenario.scenario_id,
            projected_power_ac_kw=round(projected_power, 1),
            projected_heatsink_temp_c=round(projected_hs_temp, 1),
            thermal_curtailment_pct=round(curtailment_pct, 1),
            projected_energy_loss_kwh=round(energy_loss_kwh, 1),
            projected_financial_loss_usd=round(financial_loss_usd, 2),
            projected_failure_probability=round(proj_pf, 3),
            will_trip=will_trip,
            time_to_trip_minutes=time_to_trip,
            explanation=explanation,
        )
