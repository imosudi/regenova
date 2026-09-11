"""
REAMP Predictive Maintenance Engine.
Central orchestrator synthesizing asset health, performance gaps, and anomaly events
to produce explainable, prioritized maintenance recommendations across all four paradigms.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple
from reamp.maintenance.models import (
    MaintenanceParadigm,
    MaintenanceUrgency,
    MaintenancePriority,
    EvidenceSufficiency,
    RULPrediction,
    PriorityScoreBreakdown,
    MaintenanceRecommendation,
    PriorityWeightsConfig
)
from reamp.maintenance.degradation import DegradationEngine
from reamp.maintenance.priority import MultiCriteriaPriorityEngine


class PredictiveMaintenanceEngine:
    """
    Unified predictive maintenance orchestrator.
    Determines failure horizons, assigns multi-criteria priorities,
    enforces Quality Gate uncertainty constraints, and builds prescriptive work orders.
    """

    MODEL_VERSION = "1.0.0-phase9"

    def __init__(self, priority_config: Optional[PriorityWeightsConfig] = None):
        self.degradation_engine = DegradationEngine()
        self.priority_engine = MultiCriteriaPriorityEngine(priority_config)

    def evaluate_maintenance(
        self,
        asset_id: str,
        operating_hours: float,
        current_health_score: float,
        health_history: Optional[List[Tuple[float, float]]] = None,
        telemetry_confidence: float = 1.0,
        active_anomalies: Optional[List[Dict[str, Any]]] = None,
        operational_state: str = "RUNNING",
        daily_revenue_loss_usd: float = 50.0,
        criticality_score: float = 75.0,
        safety_hazard_score: float = 0.0,
        cost_avoidance_score: float = 80.0,
        spares_logistics_score: float = 90.0,
        spares_list: Optional[List[str]] = None
    ) -> MaintenanceRecommendation:
        """
        Synthesize condition intelligence into an actionable maintenance recommendation.
        Rigorously separates Reactive, Condition-Based, Predictive, and Prescriptive paradigms.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec_id = f"REC-MAINT-{uuid.uuid4().hex[:8]}"
        active_anoms = active_anomalies or []
        history = health_history or []
        spares = spares_list or ["STANDARD_INSPECTION_TOOLKIT"]

        has_trip = (operational_state.upper() in ("FAULT_TRIPPED", "OFFLINE")) or any(
            a.get("type") in ("UNEXPECTED_SHUTDOWN", "THRESHOLD_VIOLATION") and a.get("severity") == "CRITICAL"
            for a in active_anoms
        )

        # ---------------------------------------------------------------------
        # 1. Evaluate Degradation Trajectory & RUL
        # ---------------------------------------------------------------------
        rul_prediction = self.degradation_engine.estimate_rul(
            history=history,
            current_health=current_health_score,
            operating_hours=operating_hours,
            telemetry_confidence=telemetry_confidence
        )

        # ---------------------------------------------------------------------
        # 2. Multi-Criteria Priority Evaluation
        # ---------------------------------------------------------------------
        priority, breakdown = self.priority_engine.evaluate_priority(
            asset_id=asset_id,
            failure_prob_30d=rul_prediction.failure_probability_30d,
            criticality_score=criticality_score,
            daily_loss_usd=daily_revenue_loss_usd,
            safety_score=safety_hazard_score,
            cost_avoidance_score=cost_avoidance_score,
            logistics_readiness=spares_logistics_score
        )

        # ---------------------------------------------------------------------
        # 3. Arbitrate Maintenance Paradigm & Urgency
        # ---------------------------------------------------------------------
        if has_trip:
            # Paradigm 1: Reactive Maintenance (Trip / Hard Outage)
            paradigm = MaintenanceParadigm.REACTIVE
            urgency = MaintenanceUrgency.IMMEDIATE_HOURS
            priority = MaintenancePriority.P1_CRITICAL
            action = "Emergency reactive repair: Safe-isolate asset, inspect trip code, verify insulation resistance, and clear fault."
            est_downtime = 6.0
            explanation = "Unplanned trip / hard fault event detected. Immediate technician intervention required to restore generation."

        elif rul_prediction.evidence_sufficiency == EvidenceSufficiency.SUFFICIENT and rul_prediction.predicted_rul_hours is not None:
            rul_h = rul_prediction.predicted_rul_hours

            if spares_logistics_score >= 80.0:
                # Paradigm 4: Prescriptive Decision Support (RUL known + spares available)
                paradigm = MaintenanceParadigm.PRESCRIPTIVE
                if rul_h <= 120.0:
                    urgency = MaintenanceUrgency.URGENT_DAYS
                elif rul_h <= 720.0:
                    urgency = MaintenanceUrgency.PLANNED_WEEKS
                else:
                    urgency = MaintenanceUrgency.ROUTINE_MONTHS

                action = (
                    f"Prescriptive intervention: Schedule component overhaul within next {rul_h*0.8:.0f}h. "
                    "Pre-allocate warehouse spares and perform service during scheduled low-resource window."
                )
                est_downtime = 4.0
                explanation = (
                    f"Prescriptive optimization active: Degradation trajectory indicates {rul_h:.0f}h RUL. "
                    "Parts and technician readiness confirmed for minimal downtime window."
                )
            else:
                # Paradigm 3: Predictive Maintenance (Forecasting with lead time alert)
                paradigm = MaintenanceParadigm.PREDICTIVE
                urgency = MaintenanceUrgency.PLANNED_WEEKS if rul_h <= 720.0 else MaintenanceUrgency.ROUTINE_MONTHS
                action = (
                    f"Predictive component overhaul: Component projected to reach EOL in {rul_h:.0f} hours. "
                    "Expedite spare parts procurement."
                )
                est_downtime = 8.0
                explanation = f"Statistically validated degradation trend (R2={rul_prediction.r_squared:.2f}). RUL forecasted at {rul_h:.0f} hours."

        elif current_health_score < 60.0:
            # Paradigm 2: Condition-Based Maintenance (Threshold-driven without trajectory)
            paradigm = MaintenanceParadigm.CONDITION_BASED
            urgency = MaintenanceUrgency.URGENT_DAYS if current_health_score < 45.0 else MaintenanceUrgency.PLANNED_WEEKS
            action = "Condition-based inspection: Health index degraded below threshold. Conduct on-site thermal scan and mechanical inspection."
            est_downtime = 2.0
            explanation = (
                f"Condition-based alert: Current health index ({current_health_score:.1f}) is depressed. "
                "Insufficient historical depth for RUL forecasting; threshold-driven remediation active."
            )

        else:
            # Routine / Nominal Operation
            paradigm = MaintenanceParadigm.CONDITION_BASED
            urgency = MaintenanceUrgency.ROUTINE_MONTHS
            priority = MaintenancePriority.P4_LOW
            action = "Nominal operation: Continue standard condition monitoring and bi-monthly scheduled maintenance."
            est_downtime = 0.0
            explanation = "Asset operating in healthy state. No immediate corrective intervention indicated."

        # Estimate avoided cost based on catastrophic replacement vs preventative fix
        avoided_cost = round(daily_revenue_loss_usd * 14.0 + 1500.0, 2)

        return MaintenanceRecommendation(
            recommendation_id=rec_id,
            asset_id=asset_id,
            timestamp=now_str,
            paradigm=paradigm,
            urgency=urgency,
            priority=priority,
            rul_prediction=rul_prediction,
            priority_breakdown=breakdown,
            recommended_action=action,
            required_spares=spares,
            estimated_downtime_hours=est_downtime,
            estimated_avoided_cost_usd=avoided_cost,
            explanation=explanation,
            model_version=self.MODEL_VERSION
        )
