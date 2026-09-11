"""
REAMP Asset Health Data Models.
Dataclasses for health evaluation outputs, sub-index scores, and technology profiles.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, Tuple
import datetime


class HealthState(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    CRITICAL = "CRITICAL"


@dataclass
class DimensionScore:
    """Individual sub-index score and weight attribution for a single health dimension."""
    dimension: str
    score: float  # Normalized 0.0 - 100.0
    configured_weight: float  # Original weight
    effective_weight: float   # Weight after missing-data redistribution
    weighted_contribution: float  # score * effective_weight
    confidence: float  # 0.0 - 1.0
    measured_value: Optional[float] = None
    unit: str = ""
    status: str = "VALID"  # "VALID", "MISSING", "STALE", "UNCERTAIN"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealthProfileConfig:
    """Technology-specific weights, operational baselines, and physical stress limits."""
    technology_type: str
    model_version: str
    weights: Dict[str, float]  # e.g. {"performance": 0.25, "thermal": 0.25, ...}
    nominal_perf_ratio: float = 0.82
    nominal_temp_c: float = 65.0
    critical_temp_c: float = 95.0
    arrhenius_gamma: float = 1.5
    design_life_years: float = 25.0
    rated_cycle_life: int = 5000
    alarm_penalty_half_life_days: float = 3.0


@dataclass
class HealthEvaluationResult:
    """Canonical explainable health assessment output."""
    asset_id: str
    technology_type: str
    health_score: float  # Normalized 0.0 - 100.0
    health_state: HealthState
    confidence: float  # 0.0 - 1.0
    is_uncertain: bool
    contributing_factors: Dict[str, DimensionScore]
    timestamp: str
    model_version: str
    recommended_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["health_state"] = self.health_state.value if isinstance(self.health_state, HealthState) else self.health_state
        d["contributing_factors"] = {k: v.to_dict() for k, v in self.contributing_factors.items()}
        return d
