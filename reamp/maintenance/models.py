"""
REAMP Predictive Maintenance Data Models.
Standardized dataclasses and enums for degradation tracking, RUL estimation,
multi-criteria priority scoring, and four-paradigm maintenance recommendations.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
import datetime


class MaintenanceParadigm(str, Enum):
    """Four distinct maintenance operating modes."""
    REACTIVE = "REACTIVE"               # Urgent repair post-trip / failure
    CONDITION_BASED = "CONDITION_BASED" # Threshold-driven by current health index
    PREDICTIVE = "PREDICTIVE"           # Trajectory & RUL forecasting
    PRESCRIPTIVE = "PRESCRIPTIVE"       # Optimized action, timing, and spares dispatch


class MaintenanceUrgency(str, Enum):
    """Operational intervention time horizon."""
    IMMEDIATE_HOURS = "IMMEDIATE_HOURS" # < 4-12 hours (trip, safety, severe overheating)
    URGENT_DAYS = "URGENT_DAYS"         # < 48 hours (CBM threshold breach)
    PLANNED_WEEKS = "PLANNED_WEEKS"     # < 14-30 days (RUL expiration window)
    ROUTINE_MONTHS = "ROUTINE_MONTHS"   # < 60 days (minor non-critical wear)


class MaintenancePriority(str, Enum):
    """Operational priority tiers for maintenance resource allocation."""
    P1_CRITICAL = "P1_CRITICAL" # Immediate safety hazard or total plant bottleneck
    P2_HIGH = "P2_HIGH"         # Urgent failure risk on major generation asset
    P3_MEDIUM = "P3_MEDIUM"     # Planned intervention within standard O&M cycle
    P4_LOW = "P4_LOW"           # Routine or deferrable task


class EvidenceSufficiency(str, Enum):
    """Quality gate classification for prediction evidence integrity."""
    SUFFICIENT = "SUFFICIENT"     # Full statistically valid trajectory (N >= 5, R2 >= 0.70)
    PARTIAL = "PARTIAL"           # Emerging trend with wider uncertainty
    INSUFFICIENT = "INSUFFICIENT" # Sparse or noisy data; precise RUL refused


@dataclass
class RULPrediction:
    """Remaining Useful Life estimation with explicit uncertainty propagation."""
    predicted_rul_hours: Optional[float]
    rul_confidence_interval: Tuple[float, float]
    failure_probability_30d: float
    evidence_sufficiency: EvidenceSufficiency
    uncertainty_flag: bool
    degradation_rate_per_1000h: float
    r_squared: float
    model_name: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence_sufficiency"] = (
            self.evidence_sufficiency.value
            if isinstance(self.evidence_sufficiency, EvidenceSufficiency)
            else self.evidence_sufficiency
        )
        return d


@dataclass
class PriorityScoreBreakdown:
    """Explainable factor scores summing to the composite risk priority score."""
    failure_probability_contrib: float
    criticality_contrib: float
    production_impact_contrib: float
    safety_contrib: float
    cost_avoidance_contrib: float
    spares_logistics_contrib: float
    composite_priority_score: float
    is_safety_override: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PriorityWeightsConfig:
    """Configurable weights for multi-criteria risk priority calculation."""
    weight_failure: float = 0.25
    weight_criticality: float = 0.20
    weight_production: float = 0.20
    weight_safety: float = 0.15
    weight_cost: float = 0.10
    weight_logistics: float = 0.10
    safety_override_threshold: float = 85.0


@dataclass
class MaintenanceRecommendation:
    """
    Canonical explainable work order recommendation.
    Integrates condition intelligence, failure predictions, and prescriptive actions.
    """
    recommendation_id: str
    asset_id: str
    timestamp: str
    paradigm: MaintenanceParadigm
    urgency: MaintenanceUrgency
    priority: MaintenancePriority
    rul_prediction: Optional[RULPrediction]
    priority_breakdown: PriorityScoreBreakdown
    recommended_action: str
    required_spares: List[str]
    estimated_downtime_hours: float
    estimated_avoided_cost_usd: float
    explanation: str
    model_version: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["paradigm"] = self.paradigm.value if isinstance(self.paradigm, MaintenanceParadigm) else self.paradigm
        d["urgency"] = self.urgency.value if isinstance(self.urgency, MaintenanceUrgency) else self.urgency
        d["priority"] = self.priority.value if isinstance(self.priority, MaintenancePriority) else self.priority
        if self.rul_prediction:
            d["rul_prediction"] = self.rul_prediction.to_dict()
        d["priority_breakdown"] = self.priority_breakdown.to_dict()
        return d
