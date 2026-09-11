"""
REAMP Digital Twin Data Models.
Standardized dataclasses and enums representing the complete 10-dimensional asset state space,
physics-based expected states, residuals, synchronization statuses, and what-if simulation results.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime


class SyncStatus(str, Enum):
    """Real-time synchronization status between edge asset and cloud digital twin."""
    SYNCHRONIZED = "SYNCHRONIZED"                       # Telemetry latency <= 60s
    DEGRADED_COMMUNICATION = "DEGRADED_COMMUNICATION"   # 60s < Latency <= 300s
    OUT_OF_SYNC = "OUT_OF_SYNC"                         # Latency > 300s (stale)
    REPLAYING_BUFFER = "REPLAYING_BUFFER"               # Ingesting batched store-and-forward edge data


class InverterOperatingMode(str, Enum):
    """Operational state of the physical solar inverter."""
    FEED_IN_NORMAL = "FEED_IN_NORMAL"
    DERATED = "DERATED"
    CURTAILED = "CURTAILED"
    STANDBY = "STANDBY"
    TRIP_FAULT = "TRIP_FAULT"


@dataclass
class TwinIdentity:
    """Asset identity and topological hierarchy."""
    asset_id: str
    serial_number: str
    manufacturer: str
    model: str
    site_id: str
    subsystem_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InverterConfiguration:
    """Nameplate physical, electrical, and thermal parameters."""
    rated_ac_power_kw: float = 500.0
    rated_dc_power_kw: float = 625.0
    nominal_voltage_ac: float = 400.0
    mppt_voltage_min: float = 550.0
    mppt_voltage_max: float = 850.0
    thermal_resistance_c_per_kw: float = 1.8  # C / kW loss
    temp_coefficient_pct_per_c: float = -0.0038
    max_heatsink_temp_c: float = 88.0
    trip_heatsink_temp_c: float = 95.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ObservedTelemetryState:
    """Current live synchronized physical readings."""
    timestamp: str
    sequence_number: int
    power_ac_kw: float
    power_dc_kw: float
    voltage_dc_v: float
    current_dc_a: float
    voltage_ac_v: float
    temperature_heatsink_c: float
    ambient_temperature_c: float
    poa_irradiance_w_per_m2: float
    wind_speed_m_per_s: float = 2.0
    operating_mode: InverterOperatingMode = InverterOperatingMode.FEED_IN_NORMAL
    quality_flag: str = "GOOD"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["operating_mode"] = self.operating_mode.value if isinstance(self.operating_mode, InverterOperatingMode) else self.operating_mode
        return d


@dataclass
class PhysicsExpectedState:
    """Nominal expected values computed via internal first-principles models."""
    expected_cell_temperature_c: float
    expected_power_dc_kw: float
    expected_efficiency: float
    expected_power_ac_kw: float
    expected_heatsink_temp_c: float
    is_clipping: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StateResiduals:
    """Discrepancies between observed telemetry and expected physics state."""
    power_residual_kw: float
    temperature_residual_c: float
    efficiency_residual: float
    is_power_deviating: bool
    is_thermal_deviating: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealthStateSnapshot:
    """Integrated health scores from Phase 6."""
    composite_health_index: float
    component_health: Dict[str, float] = field(default_factory=dict)
    status: str = "GOOD"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceStateSnapshot:
    """Integrated performance metrics from Phase 7."""
    performance_ratio: float
    availability: float
    curtailment_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnomalyStateSnapshot:
    """Integrated anomaly events from Phase 8."""
    active_anomaly_count: int
    active_anomalies: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MaintenanceStateSnapshot:
    """Integrated CMMS maintenance records from Phase 10."""
    active_work_order_id: Optional[str] = None
    work_order_status: Optional[str] = None
    assigned_technician: Optional[str] = None
    historical_downtime_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PredictedStateSnapshot:
    """Integrated RUL and predictive risk from Phase 9 and Phase 11."""
    predicted_rul_hours: Optional[float] = None
    rul_confidence_interval: Optional[List[float]] = None
    failure_probability_30d: float = 0.05
    risk_tier: str = "LOW"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TwinFullState:
    """
    Consolidated 10-Dimensional Digital Twin State Representation:
    1. Identity, 2. Configuration, 3. Current Telemetry, 4. Historical Trajectory,
    5. Expected State, 6. Health State, 7. Performance State, 8. Anomaly State,
    9. Maintenance State, 10. Predicted State.
    """
    timestamp: str
    sync_status: SyncStatus
    identity: TwinIdentity
    configuration: InverterConfiguration
    telemetry: ObservedTelemetryState
    expected_state: PhysicsExpectedState
    residuals: StateResiduals
    health: HealthStateSnapshot
    performance: PerformanceStateSnapshot
    anomalies: AnomalyStateSnapshot
    maintenance: MaintenanceStateSnapshot
    predicted: PredictedStateSnapshot

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "sync_status": self.sync_status.value if isinstance(self.sync_status, SyncStatus) else self.sync_status,
            "identity": self.identity.to_dict(),
            "configuration": self.configuration.to_dict(),
            "telemetry": self.telemetry.to_dict(),
            "expected_state": self.expected_state.to_dict(),
            "residuals": self.residuals.to_dict(),
            "health": self.health.to_dict(),
            "performance": self.performance.to_dict(),
            "anomalies": self.anomalies.to_dict(),
            "maintenance": self.maintenance.to_dict(),
            "predicted": self.predicted.to_dict(),
        }
        return d


@dataclass
class SimulationScenario:
    """What-if simulation input parameters."""
    scenario_id: str
    name: str
    ambient_temp_offset_c: float = 0.0
    irradiance_override_w_per_m2: Optional[float] = None
    cooling_degradation_factor: float = 1.0  # multiplier on R_th (e.g. 2.0 = 50% fan failure)
    duration_hours: float = 4.0
    defer_maintenance_days: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimulationResult:
    """Forward-projected state outcome from what-if simulation."""
    scenario_id: str
    projected_power_ac_kw: float
    projected_heatsink_temp_c: float
    thermal_curtailment_pct: float
    projected_energy_loss_kwh: float
    projected_financial_loss_usd: float
    projected_failure_probability: float
    will_trip: bool
    time_to_trip_minutes: Optional[float]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
