"""
REAMP Multi-Criteria Maintenance Priority and Risk Ranking Engine.
Computes weighted composite risk priority scores (RPS) and enforces safety overrides.
"""

from typing import Tuple, Dict, Any, Optional
from reamp.maintenance.models import (
    MaintenancePriority,
    PriorityScoreBreakdown,
    PriorityWeightsConfig
)


class MultiCriteriaPriorityEngine:
    """
    Evaluates failure probability, asset criticality, production revenue impact,
    personnel safety, repair costs, and spares logistics to assign P1–P4 priorities.
    """

    def __init__(self, config: Optional[PriorityWeightsConfig] = None):
        self.config = config or PriorityWeightsConfig()

    def evaluate_priority(
        self,
        asset_id: str,
        failure_prob_30d: float,
        criticality_score: float,       # 0.0 - 100.0 (substation=100, inverter=75, string=40)
        daily_loss_usd: float,          # Lost revenue per day if degraded/out
        safety_score: float,            # 0.0 - 100.0 (fire/arc flash=100, cooling=40, nominal=0)
        cost_avoidance_score: float,    # 0.0 - 100.0 (high savings=100, routine=20)
        logistics_readiness: float      # 0.0 - 100.0 (in-stock on-site=100, long-lead=25)
    ) -> Tuple[MaintenancePriority, PriorityScoreBreakdown]:
        """
        Compute normalized factor contributions, composite priority score,
        and assign operational priority tier with safety override check.
        """
        # 1. Factor Normalizations (0.0 to 100.0)
        s_fail = min(100.0, max(0.0, float(failure_prob_30d) * 100.0))
        s_crit = min(100.0, max(0.0, float(criticality_score)))
        s_prod = 100.0 * min(1.0, max(0.0, float(daily_loss_usd) / 1000.0))
        s_safe = min(100.0, max(0.0, float(safety_score)))
        s_cost = min(100.0, max(0.0, float(cost_avoidance_score)))
        s_log = min(100.0, max(0.0, float(logistics_readiness)))

        # 2. Weighted Factor Contributions
        c_fail = round(self.config.weight_failure * s_fail, 2)
        c_crit = round(self.config.weight_criticality * s_crit, 2)
        c_prod = round(self.config.weight_production * s_prod, 2)
        c_safe = round(self.config.weight_safety * s_safe, 2)
        c_cost = round(self.config.weight_cost * s_cost, 2)
        c_log = round(self.config.weight_logistics * s_log, 2)

        composite_score = round(c_fail + c_crit + c_prod + c_safe + c_cost + c_log, 2)

        # 3. Safety Override Gate
        # Severe safety / fire / arc-flash hazard strictly forces P1 Critical
        is_safety_override = s_safe >= self.config.safety_override_threshold

        # 4. Priority Tier Mapping
        if is_safety_override or composite_score >= 80.0:
            priority = MaintenancePriority.P1_CRITICAL
        elif composite_score >= 60.0:
            priority = MaintenancePriority.P2_HIGH
        elif composite_score >= 40.0:
            priority = MaintenancePriority.P3_MEDIUM
        else:
            priority = MaintenancePriority.P4_LOW

        breakdown = PriorityScoreBreakdown(
            failure_probability_contrib=c_fail,
            criticality_contrib=c_crit,
            production_impact_contrib=c_prod,
            safety_contrib=c_safe,
            cost_avoidance_contrib=c_cost,
            spares_logistics_contrib=c_log,
            composite_priority_score=composite_score,
            is_safety_override=is_safety_override
        )

        return priority, breakdown
