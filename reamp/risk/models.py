"""
REAMP Risk and Financial Intelligence Data Models.
Standardized dataclasses and enums for probabilistic risk quantification,
financial loss attribution, configurable economic assumptions, and explainable prioritization.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List


class RiskTier(str, Enum):
    """Operational risk classification tiers."""
    EXTREME = "EXTREME"  # Immediate intervention (< 4 hours) or safety emergency
    HIGH = "HIGH"        # Urgent maintenance dispatch (< 24-48 hours)
    MEDIUM = "MEDIUM"    # Scheduled remediation (< 14 days)
    LOW = "LOW"          # Routine monitoring / deferrable (< 60 days)


class AssetCriticality(str, Enum):
    """Topological plant single-point-of-failure criticality."""
    TIER_1_CRITICAL = "TIER_1_CRITICAL"       # Substation, Interconnect, Central Inverter (Score: 100)
    TIER_2_MAJOR = "TIER_2_MAJOR"             # Individual Inverter, Wind Turbine, BESS Rack (Score: 75)
    TIER_3_BALANCE_OF_PLANT = "TIER_3_BOP"    # String, Combiner, Tracker, Sensor (Score: 25)

    @property
    def score(self) -> float:
        scores = {
            AssetCriticality.TIER_1_CRITICAL: 100.0,
            AssetCriticality.TIER_2_MAJOR: 75.0,
            AssetCriticality.TIER_3_BALANCE_OF_PLANT: 25.0,
        }
        return scores.get(self, 50.0)


class SafetySeverity(str, Enum):
    """Physical personnel, environmental, and thermal hazard tiers."""
    CATASTROPHIC = "CATASTROPHIC" # Thermal runaway, arc flash, blade throw (Score: 100)
    SEVERE = "SEVERE"             # Severe overheating, insulation breakdown (Score: 70)
    MODERATE = "MODERATE"         # Secondary temperature breach (Score: 30)
    NEGLIGIBLE = "NEGLIGIBLE"     # Benign electrical drift, no physical hazard (Score: 0)

    @property
    def score(self) -> float:
        scores = {
            SafetySeverity.CATASTROPHIC: 100.0,
            SafetySeverity.SEVERE: 70.0,
            SafetySeverity.MODERATE: 30.0,
            SafetySeverity.NEGLIGIBLE: 0.0,
        }
        return scores.get(self, 0.0)


@dataclass
class FinancialAssumptions:
    """
    Configurable economic and market parameters.
    No tariffs or prices are hardcoded; all valuations require explicit or documented assumptions.
    """
    currency: str = "USD"
    energy_tariff_per_kwh: float = 0.10
    peak_energy_tariff_per_kwh: Optional[float] = None
    downtime_penalty_per_hour: float = 0.0
    technician_hourly_rate: float = 85.0
    crane_mobilization_cost: float = 0.0
    discount_rate_annual: float = 0.05
    source_reference: str = "Configured PPA contract defaults"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinancialImpactBreakdown:
    """Itemized breakdown of economic exposure."""
    energy_revenue_loss: float
    downtime_penalty: float
    maintenance_cost: float
    catastrophic_replacement_risk: float

    @property
    def total_financial_impact(self) -> float:
        return (
            self.energy_revenue_loss
            + self.downtime_penalty
            + self.maintenance_cost
            + self.catastrophic_replacement_risk
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_financial_impact"] = round(self.total_financial_impact, 2)
        d["energy_revenue_loss"] = round(self.energy_revenue_loss, 2)
        d["downtime_penalty"] = round(self.downtime_penalty, 2)
        d["maintenance_cost"] = round(self.maintenance_cost, 2)
        d["catastrophic_replacement_risk"] = round(self.catastrophic_replacement_risk, 2)
        return d


@dataclass
class ConsequenceBreakdown:
    """Multi-vector consequence scores normalized to [0, 100]."""
    production_score: float
    criticality_score: float
    safety_score: float
    maintenance_score: float
    composite_consequence_score: float
    is_safety_override: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventRiskProfile:
    """
    Canonical output required for each significant operational event:
    Technical severity, operational consequence, estimated energy loss,
    estimated financial impact, confidence, and audit assumptions.
    """
    event_id: str
    asset_id: str
    technical_severity: str
    operational_consequence: str
    estimated_energy_loss_kwh: float
    estimated_financial_impact: float
    financial_breakdown: FinancialImpactBreakdown
    failure_probability: float
    consequence_breakdown: ConsequenceBreakdown
    composite_risk_score: float
    risk_tier: RiskTier
    confidence: float
    assumptions: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_tier"] = self.risk_tier.value if isinstance(self.risk_tier, RiskTier) else self.risk_tier
        d["financial_breakdown"] = self.financial_breakdown.to_dict()
        d["consequence_breakdown"] = self.consequence_breakdown.to_dict()
        return d


@dataclass
class AssetPrioritizationRecord:
    """
    Fleet-wide ranking entry satisfying the Phase 11 Quality Gate:
    A user must be able to understand why an asset has been prioritized.
    """
    rank: int
    asset_id: str
    event_id: str
    composite_risk_score: float
    risk_tier: RiskTier
    estimated_financial_impact: float
    dominant_driver: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_tier"] = self.risk_tier.value if isinstance(self.risk_tier, RiskTier) else self.risk_tier
        return d
