"""
REAMP Risk and Financial Intelligence Engine.
Computes probabilistic risk (Risk = Probability x Consequence), itemized financial exposure,
fleet-wide asset rankings, and explainable prioritization narratives.
"""

from typing import Dict, Any, List, Optional
import copy

from reamp.risk.models import (
    RiskTier,
    AssetCriticality,
    SafetySeverity,
    FinancialAssumptions,
    FinancialImpactBreakdown,
    ConsequenceBreakdown,
    EventRiskProfile,
    AssetPrioritizationRecord,
)


class RiskAndFinancialEngine:
    """
    Translates technical condition streams into operational and financial consequences.
    Implements Risk = Probability x Consequence with multi-vector consequence decomposition,
    configurable economic models (no fake energy prices), and explainable asset prioritization.
    """

    def __init__(
        self,
        default_assumptions: Optional[FinancialAssumptions] = None,
        weight_production: float = 0.35,
        weight_criticality: float = 0.25,
        weight_safety: float = 0.25,
        weight_maintenance: float = 0.15,
        safety_override_threshold: float = 85.0,
    ) -> None:
        self.default_assumptions = default_assumptions or FinancialAssumptions()
        self.weight_production = weight_production
        self.weight_criticality = weight_criticality
        self.weight_safety = weight_safety
        self.weight_maintenance = weight_maintenance
        self.safety_override_threshold = safety_override_threshold

    def calculate_event_risk(
        self,
        event_id: str,
        asset_id: str,
        technical_severity: str,
        operational_consequence: str,
        failure_probability: float,
        estimated_energy_loss_kwh: float,
        asset_criticality: AssetCriticality = AssetCriticality.TIER_2_MAJOR,
        safety_severity: SafetySeverity = SafetySeverity.NEGLIGIBLE,
        maintenance_lead_time_days: int = 2,
        requires_special_tooling: bool = False,
        expected_downtime_hours: float = 2.0,
        maintenance_labor_hours: float = 2.0,
        spare_parts_cost: float = 0.0,
        asset_replacement_capital_cost: float = 0.0,
        confidence: float = 0.90,
        assumptions_override: Optional[FinancialAssumptions] = None,
        custom_tariff: Optional[float] = None,
    ) -> EventRiskProfile:
        """
        Evaluates the 6 required output fields for an operational event:
        1. Technical severity
        2. Operational consequence
        3. Estimated energy loss (kWh)
        4. Estimated financial impact ($)
        5. Confidence
        6. Assumptions dictionary
        along with composite risk score and risk tier.
        """
        # 1. Resolve Economic Assumptions (No hardcoded pricing)
        assump = assumptions_override or self.default_assumptions
        tariff = custom_tariff if custom_tariff is not None else assump.energy_tariff_per_kwh

        # 2. Itemized Financial Loss Modeling:
        # Lost Energy x Energy Value + Downtime Penalties + Maintenance Costs + Catastrophic Risk
        energy_revenue_loss = max(0.0, estimated_energy_loss_kwh * tariff)
        downtime_penalty = max(0.0, expected_downtime_hours * assump.downtime_penalty_per_hour)

        tooling_cost = assump.crane_mobilization_cost if requires_special_tooling else 0.0
        labor_cost = maintenance_labor_hours * assump.technician_hourly_rate
        maintenance_cost = labor_cost + spare_parts_cost + tooling_cost

        # Probability-weighted catastrophic replacement exposure
        catastrophic_risk = failure_probability * asset_replacement_capital_cost

        financial_breakdown = FinancialImpactBreakdown(
            energy_revenue_loss=round(energy_revenue_loss, 2),
            downtime_penalty=round(downtime_penalty, 2),
            maintenance_cost=round(maintenance_cost, 2),
            catastrophic_replacement_risk=round(catastrophic_risk, 2),
        )
        total_financial_impact = financial_breakdown.total_financial_impact

        # 3. Normalized Consequence Formulation (Scale: [0, 100])
        # Production Impact: normalized against standard day equivalent (e.g. 2,000 kWh reference)
        production_score = min(100.0, max(0.0, (estimated_energy_loss_kwh / 2000.0) * 100.0))
        criticality_score = asset_criticality.score
        safety_score = safety_severity.score

        # Maintenance logistics consequence (lead time + tooling)
        lead_time_score = min(50.0, (maintenance_lead_time_days / 14.0) * 50.0)
        tooling_score = 40.0 if requires_special_tooling else 10.0
        maint_score = min(100.0, lead_time_score + tooling_score)

        # Weighted Consequence Score
        composite_consequence = (
            self.weight_production * production_score
            + self.weight_criticality * criticality_score
            + self.weight_safety * safety_score
            + self.weight_maintenance * maint_score
        )

        # 4. Safety Override Gate
        is_safety_override = safety_score >= self.safety_override_threshold

        # 5. Composite Risk = Probability x Consequence
        # Clamped to [0, 100]
        clamped_prob = min(1.0, max(0.0, failure_probability))
        composite_risk_score = clamped_prob * composite_consequence

        if is_safety_override:
            risk_tier = RiskTier.EXTREME
            composite_risk_score = max(composite_risk_score, 85.0)
        elif composite_risk_score >= 75.0:
            risk_tier = RiskTier.EXTREME
        elif composite_risk_score >= 50.0:
            risk_tier = RiskTier.HIGH
        elif composite_risk_score >= 25.0:
            risk_tier = RiskTier.MEDIUM
        else:
            risk_tier = RiskTier.LOW

        consequence_breakdown = ConsequenceBreakdown(
            production_score=round(production_score, 1),
            criticality_score=round(criticality_score, 1),
            safety_score=round(safety_score, 1),
            maintenance_score=round(maint_score, 1),
            composite_consequence_score=round(composite_consequence, 1),
            is_safety_override=is_safety_override,
        )

        # 6. Audit Assumptions Record (Transparency & Governance)
        assumptions_record = {
            "currency": assump.currency,
            "energy_tariff_applied": tariff,
            "technician_hourly_rate": assump.technician_hourly_rate,
            "downtime_penalty_per_hour": assump.downtime_penalty_per_hour,
            "crane_mobilization_cost": assump.crane_mobilization_cost,
            "source_reference": assump.source_reference,
            "safety_override_triggered": is_safety_override,
            "weight_distribution": {
                "production": self.weight_production,
                "criticality": self.weight_criticality,
                "safety": self.weight_safety,
                "maintenance": self.weight_maintenance,
            },
        }

        return EventRiskProfile(
            event_id=event_id,
            asset_id=asset_id,
            technical_severity=technical_severity,
            operational_consequence=operational_consequence,
            estimated_energy_loss_kwh=round(estimated_energy_loss_kwh, 2),
            estimated_financial_impact=round(total_financial_impact, 2),
            financial_breakdown=financial_breakdown,
            failure_probability=round(clamped_prob, 3),
            consequence_breakdown=consequence_breakdown,
            composite_risk_score=round(composite_risk_score, 1),
            risk_tier=risk_tier,
            confidence=round(confidence, 2),
            assumptions=assumptions_record,
        )

    def rank_fleet_assets(
        self,
        event_profiles: List[EventRiskProfile],
    ) -> List[AssetPrioritizationRecord]:
        """
        Ranks operational assets across a portfolio or facility.
        Sorting order:
        1. Safety Override (Safety Hazard >= 85.0 always tops the queue)
        2. Composite Risk Score (Descending)
        3. Total Financial Impact (Descending tie-breaker)
        """
        # Sort key: (is_safety_override, composite_risk_score, total_financial_impact)
        sorted_profiles = sorted(
            event_profiles,
            key=lambda p: (
                1 if p.consequence_breakdown.is_safety_override else 0,
                p.composite_risk_score,
                p.estimated_financial_impact,
            ),
            reverse=True,
        )

        records: List[AssetPrioritizationRecord] = []
        for rank_idx, profile in enumerate(sorted_profiles, start=1):
            explanation, dominant_driver = self.explain_prioritization(
                profile,
                rank=rank_idx,
                total_assets=len(sorted_profiles),
            )
            records.append(
                AssetPrioritizationRecord(
                    rank=rank_idx,
                    asset_id=profile.asset_id,
                    event_id=profile.event_id,
                    composite_risk_score=profile.composite_risk_score,
                    risk_tier=profile.risk_tier,
                    estimated_financial_impact=profile.estimated_financial_impact,
                    dominant_driver=dominant_driver,
                    explanation=explanation,
                )
            )

        return records

    def explain_prioritization(
        self,
        profile: EventRiskProfile,
        rank: Optional[int] = None,
        total_assets: Optional[int] = None,
    ) -> tuple[str, str]:
        """
        Quality Gate Implementation:
        Produces a human-interpretable rationale explaining *why* an asset was prioritized.
        Returns: (explanation_text, dominant_driver)
        """
        cb = profile.consequence_breakdown
        fb = profile.financial_breakdown

        # Identify dominant driver
        if cb.is_safety_override:
            dominant_driver = "ACUTE_SAFETY_HAZARD"
            explanation = (
                f"Asset {profile.asset_id} holds top operational priority (Risk Tier: {profile.risk_tier.value}) "
                f"due to an acute safety hazard (Safety Score: {cb.safety_score}/100) overriding standard economic ranking. "
                f"Condition: '{profile.operational_consequence}'. Immediate personnel safety or thermal intervention required."
            )
            if rank and total_assets:
                explanation = f"Rank #{rank} of {total_assets}: " + explanation
            return explanation, dominant_driver

        # Compare consequence contributions
        contributions = {
            "PRODUCTION_LOSS": self.weight_production * cb.production_score,
            "ASSET_CRITICALITY": self.weight_criticality * cb.criticality_score,
            "SAFETY_CONSEQUENCE": self.weight_safety * cb.safety_score,
            "MAINTENANCE_LOGISTICS": self.weight_maintenance * cb.maintenance_score,
        }
        dominant_driver = max(contributions, key=contributions.get)

        rank_prefix = f"Rank #{rank} of {total_assets}: " if rank and total_assets else ""

        driver_narratives = {
            "PRODUCTION_LOSS": (
                f"primarily driven by high generation revenue loss (${fb.energy_revenue_loss} from "
                f"{profile.estimated_energy_loss_kwh} kWh lost energy) under active generation conditions."
            ),
            "ASSET_CRITICALITY": (
                f"primarily driven by high asset topological criticality ({cb.criticality_score}/100 single-point failure bottleneck)."
            ),
            "SAFETY_CONSEQUENCE": (
                f"primarily driven by elevated physical/thermal safety hazard ({cb.safety_score}/100)."
            ),
            "MAINTENANCE_LOGISTICS": (
                f"primarily driven by complex maintenance logistics, specialized tooling, and extended lead times."
            ),
        }

        explanation = (
            f"{rank_prefix}Asset {profile.asset_id} prioritized with {profile.risk_tier.value} risk "
            f"(Score: {profile.composite_risk_score}/100, Failure Probability: {profile.failure_probability * 100:.1f}%), "
            f"{driver_narratives.get(dominant_driver, 'driven by composite condition factors')}. "
            f"Total financial exposure is ${profile.estimated_financial_impact:.2f} with {profile.confidence * 100:.0f}% confidence."
        )

        return explanation, dominant_driver
