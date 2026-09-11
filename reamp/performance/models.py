"""
REAMP Performance Intelligence Data Models.
Strongly-typed dataclasses for expected performance modeling, loss attribution, and economic impact.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime


class OperatingState(str, Enum):
    """Operational state of the renewable asset."""
    RUNNING = "RUNNING"
    CURTAILED = "CURTAILED"
    FAULT_TRIPPED = "FAULT_TRIPPED"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"
    STANDBY = "STANDBY"


class LossCategory(str, Enum):
    """Standardized loss attribution categories in the waterfall decomposition."""
    RESOURCE_VARIATION = "RESOURCE_VARIATION"
    THERMAL_DERATE = "THERMAL_DERATE"
    INVERTER_CLIPPING = "INVERTER_CLIPPING"
    CURTAILMENT = "CURTAILMENT"
    ASSET_OUTAGE = "ASSET_OUTAGE"
    CONTROLLABLE_UNDERPERFORMANCE = "CONTROLLABLE_UNDERPERFORMANCE"
    MISSING_DATA = "MISSING_DATA"


class PerformanceClassification(str, Enum):
    """High-level classification of the asset's current performance state."""
    NOMINAL = "NOMINAL"
    ENVIRONMENTAL_VARIATION = "ENVIRONMENTAL_VARIATION"
    UNDERPERFORMING = "UNDERPERFORMING"
    CURTAILED = "CURTAILED"
    OUTAGE = "OUTAGE"
    MISSING_DATA = "MISSING_DATA"


@dataclass
class LossComponent:
    """Individual loss component in the waterfall decomposition."""
    category: LossCategory
    lost_power_kw: float
    lost_energy_kwh: float
    financial_loss: float
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, LossCategory) else self.category
        return d


@dataclass
class SolarParameters:
    """Physical and electrical specifications for a Solar PV plant or inverter block."""
    rated_dc_kw: float
    rated_ac_kw: float
    gamma_pmp: float = -0.0038        # Temperature coefficient of power (%/degC as decimal)
    nmot_c: float = 45.0              # Nominal Module Operating Temperature (degC)
    soiling_factor: float = 0.98      # Baseline optical transmission factor
    dc_loss_factor: float = 0.98      # DC wiring, mismatch, and diode losses
    inverter_efficiency: float = 0.985 # Inverter conversion efficiency
    ppa_tariff_per_kwh: float = 0.08  # Default PPA contract tariff ($/kWh)


@dataclass
class WindParameters:
    """Aerodynamic and electrical specifications for a wind turbine generator."""
    rated_power_kw: float
    cut_in_speed_ms: float = 3.0
    rated_speed_ms: float = 12.0
    cut_out_speed_ms: float = 25.0
    rotor_diameter_m: float = 120.0
    hub_height_m: float = 100.0
    air_density_ref: float = 1.225
    ppa_tariff_per_kwh: float = 0.07


@dataclass
class BessParameters:
    """Electrochemical and thermal specifications for a battery energy storage system."""
    rated_power_kw: float
    rated_capacity_kwh: float
    rated_rte: float = 0.88          # Round-Trip Efficiency specification (88%)
    min_soc: float = 0.05
    max_soc: float = 0.95
    thermal_optimum_c: float = 25.0
    ppa_tariff_per_kwh: float = 0.12


@dataclass
class PerformanceEvaluationResult:
    """Canonical explainable performance evaluation result."""
    asset_id: str
    technology_type: str
    operating_state: OperatingState
    classification: PerformanceClassification
    expected_power_kw: float
    actual_power_kw: float
    performance_gap_kw: float
    performance_ratio: Optional[float]
    weather_adjusted_pr: Optional[float]
    confidence: float
    is_uncertain: bool
    losses: List[LossComponent]
    total_lost_energy_kwh: float
    total_financial_loss: float
    explanation: str
    timestamp: str
    model_version: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["operating_state"] = self.operating_state.value if isinstance(self.operating_state, OperatingState) else self.operating_state
        d["classification"] = self.classification.value if isinstance(self.classification, PerformanceClassification) else self.classification
        d["losses"] = [l.to_dict() for l in self.losses]
        return d
