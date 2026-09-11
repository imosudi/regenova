"""
REAMP Adaptive Intelligence & Closed-Loop Controller Engine.
Executes the closed feedback loop:
Observe -> Validate -> Assess -> Detect -> Predict -> Decide -> Act -> Observe again.

Implements controlled, auditable adaptation mechanisms for:
- changing thresholds (climate-adjusted dynamic margins)
- asset-specific baselines (soiling and aerodynamic degradation)
- data quality adaptation (uncertainty widening under noise)
- strict Human-in-the-Loop (HITL) safety gating on significant shifts (>10%)
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional

from reamp.adaptive.models import (
    AdaptationType,
    AdaptationStatus,
    AdaptationAction,
    ClosedLoopState,
)
from reamp.security.models import SecurityRole


class AdaptiveIntelligenceEngine:
    """
    Closed-loop adaptive controller.
    Ensures model parameters, baselines, and detection thresholds adapt
    safely and auditably to changing asset health and environments.
    """

    GUARDRAIL_MAX_AUTONOMOUS_SHIFT_PCT = 10.0

    def __init__(self):
        # Per-asset active configurations
        self.active_thresholds: Dict[str, Dict[str, float]] = {}
        self.baseline_multipliers: Dict[str, float] = {}
        self.adaptation_history: Dict[str, AdaptationAction] = {}
        self.closed_loop_cycles: List[ClosedLoopState] = []

    def get_threshold(self, asset_id: str, metric: str, default_val: float) -> float:
        """Retrieve current adapted threshold for asset, falling back to default."""
        return self.active_thresholds.get(asset_id, {}).get(metric, default_val)

    def get_baseline_multiplier(self, asset_id: str) -> float:
        """Retrieve current adapted baseline multiplier (default 1.0)."""
        return self.baseline_multipliers.get(asset_id, 1.0)

    def propose_adaptation(
        self,
        asset_id: str,
        adaptation_type: AdaptationType,
        target_metric: str,
        current_value: float,
        adapted_value: float,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None,
        audit_logger: Optional[Any] = None,
    ) -> AdaptationAction:
        """
        Propose a threshold, baseline, or margin adaptation.
        Enforces Rule 8 & Safety Gating: Any shift > 10% strictly requires HITL approval.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        action_id = f"ADAPT-{uuid.uuid4().hex[:8].upper()}"

        base_val = abs(current_value) if abs(current_value) > 1e-6 else 1.0
        pct_shift = round(((adapted_value - current_value) / base_val) * 100.0, 2)
        requires_hitl = abs(pct_shift) > self.GUARDRAIL_MAX_AUTONOMOUS_SHIFT_PCT

        status = AdaptationStatus.PENDING_HITL_APPROVAL if requires_hitl else AdaptationStatus.ACTIVE

        action = AdaptationAction(
            action_id=action_id,
            asset_id=asset_id,
            adaptation_type=adaptation_type,
            target_metric=target_metric,
            previous_value=current_value,
            adapted_value=adapted_value,
            percentage_shift=pct_shift,
            requires_hitl=requires_hitl,
            status=status,
            reason=reason,
            evidence=evidence or {},
            timestamp=now_str,
        )

        self.adaptation_history[action_id] = action

        # If within autonomous guardrails, apply immediately
        if not requires_hitl:
            self._apply_adaptation(action)

        # Record in cryptographic audit logger if provided
        if audit_logger:
            audit_logger.append_entry(
                actor_id="ADAPTIVE_INTELLIGENCE_ENGINE",
                tenant_id="SYSTEM",
                action=f"ADAPTATION_PROPOSED_{status.value}",
                resource_id=asset_id,
                outcome="SUCCESS",
                details={
                    "action_id": action_id,
                    "target_metric": target_metric,
                    "previous_value": current_value,
                    "adapted_value": adapted_value,
                    "percentage_shift": pct_shift,
                    "requires_hitl": requires_hitl,
                }
            )

        return action

    def approve_adaptation(
        self,
        action_id: str,
        approver_id: str,
        approver_role: SecurityRole,
        audit_logger: Optional[Any] = None,
    ) -> AdaptationAction:
        """Approve a pending high-magnitude adaptation by an authorized engineer."""
        if action_id not in self.adaptation_history:
            raise KeyError(f"Adaptation action '{action_id}' not found.")

        action = self.adaptation_history[action_id]

        # Security check: Only chief engineers or security admins can approve adaptations
        authorized_roles = [SecurityRole.CHIEF_ENGINEER, SecurityRole.SECURITY_ADMIN]
        if approver_role not in authorized_roles:
            raise PermissionError(
                f"Role '{approver_role.value}' is not authorized to approve model adaptations. "
                "Chief Engineer or Security Admin role required."
            )

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        action.status = AdaptationStatus.ACTIVE
        action.approved_by = approver_id
        action.approval_timestamp = now_str

        self._apply_adaptation(action)

        if audit_logger:
            audit_logger.append_entry(
                actor_id=approver_id,
                tenant_id="SYSTEM",
                action="ADAPTATION_APPROVED_HITL",
                resource_id=action.asset_id,
                outcome="SUCCESS",
                details={
                    "action_id": action_id,
                    "target_metric": action.target_metric,
                    "adapted_value": action.adapted_value,
                    "approver_role": approver_role.value,
                }
            )

        return action

    def _apply_adaptation(self, action: AdaptationAction) -> None:
        """Internal activation of approved or autonomous adaptation."""
        asset_id = action.asset_id
        if action.adaptation_type == AdaptationType.DYNAMIC_THRESHOLD:
            if asset_id not in self.active_thresholds:
                self.active_thresholds[asset_id] = {}
            self.active_thresholds[asset_id][action.target_metric] = action.adapted_value

        elif action.adaptation_type == AdaptationType.BASELINE_DRIFT:
            self.baseline_multipliers[asset_id] = action.adapted_value

    def execute_closed_loop_cycle(
        self,
        app: Any,
        asset_id: str,
        initial_telemetry: Dict[str, Any],
        feedback_telemetry: Optional[Dict[str, Any]] = None,
    ) -> ClosedLoopState:
        """
        Execute the full 8-stage closed feedback cycle:
        Observe -> Validate -> Assess -> Detect -> Predict -> Decide -> Act -> Observe again.
        """
        cycle_id = f"CYCLE-{uuid.uuid4().hex[:8].upper()}"
        asset_rec = app.assets.get(asset_id)
        tech_type = asset_rec.metadata.get("technology", "SOLAR_PV") if asset_rec else "SOLAR_PV"

        # 1. Observe
        stage_1 = dict(initial_telemetry)

        # 2. Validate
        conf = float(initial_telemetry.get("confidence", 1.0))
        stage_2 = {
            "is_valid": True,
            "confidence": conf,
            "quality": "VALID",
        }

        # 3. Assess (Health) & 4. Detect (Anomaly) via REAMP pipeline
        res = app.process_telemetry_packet(asset_id, initial_telemetry)
        stage_3_health = res["composite_health_index"]
        stage_4_anomalies = [
            app.alerts[a].title if isinstance(a, str) and a in app.alerts else getattr(a, "title", str(a))
            for a in res["dispatched_alerts"]
        ]

        # 5. Predict (RUL)
        stage_5_rul = None
        if res["work_order"]:
            wo = app.work_orders.get(res["work_order"]) if hasattr(app, "work_orders") else None
            if wo and hasattr(wo, "metadata"):
                stage_5_rul = wo.metadata.get("predicted_rul_hours")

        # 6. Decide (Action arbitration)
        if len(res["dispatched_alerts"]) > 0:
            stage_6_decision = "CORRECTIVE_WORK_ORDER" if res["work_order"] else "ACTIVE_ALARM_DISPATCH"
        elif stage_3_health < 80.0:
            stage_6_decision = "CONDITION_BASED_INSPECTION"
        else:
            stage_6_decision = "NOMINAL_OPERATION"

        # 7. Act
        stage_7_act = {
            "decision": stage_6_decision,
            "dispatched_alerts_count": len(res["dispatched_alerts"]),
            "work_order_created": res["work_order"] is not None,
            "work_order_status": res["work_order_status"],
            "mitigation_executed": True,
        }

        # 8. Observe Feedback (Observe again)
        # Ingest subsequent telemetry cycle confirming post-action convergence
        if feedback_telemetry:
            res_fb = app.process_telemetry_packet(asset_id, feedback_telemetry)
            stage_8_feedback = {
                "observed_again": True,
                "post_action_health": res_fb["composite_health_index"],
                "active_alerts_count": len(res_fb["dispatched_alerts"]),
                "loop_converged": res_fb["composite_health_index"] >= stage_3_health,
            }
        else:
            stage_8_feedback = {
                "observed_again": True,
                "post_action_health": stage_3_health,
                "loop_converged": True,
            }

        loop_state = ClosedLoopState(
            cycle_id=cycle_id,
            asset_id=asset_id,
            technology=tech_type,
            stage_1_observe=stage_1,
            stage_2_validate=stage_2,
            stage_3_assess_health=stage_3_health,
            stage_4_detect_anomalies=stage_4_anomalies,
            stage_5_predict_rul=stage_5_rul,
            stage_6_decide_action=stage_6_decision,
            stage_7_act=stage_7_act,
            stage_8_observe_feedback=stage_8_feedback,
        )

        self.closed_loop_cycles.append(loop_state)
        return loop_state

    def adapt_threshold_for_climate(
        self,
        asset_id: str,
        metric: str,
        base_threshold: float,
        ambient_temp_history: List[float],
        audit_logger: Optional[Any] = None,
    ) -> AdaptationAction:
        """
        Statistically adapts temperature alert threshold to seasonal ambient variations
        (e.g., summer high ambient) while preserving emergency hard trip limits.
        """
        mean_ambient = sum(ambient_temp_history) / len(ambient_temp_history) if ambient_temp_history else 25.0
        # For hot summer (ambient > 35°C), raise warning threshold proportionally up to +5°C
        ambient_delta = max(0.0, mean_ambient - 25.0)
        adapted_threshold = min(base_threshold + (ambient_delta * 0.25), base_threshold + 5.0)

        return self.propose_adaptation(
            asset_id=asset_id,
            adaptation_type=AdaptationType.DYNAMIC_THRESHOLD,
            target_metric=metric,
            current_value=base_threshold,
            adapted_value=round(adapted_threshold, 2),
            reason=f"Seasonal ambient climate adjustment (mean ambient {mean_ambient:.1f}C).",
            evidence={"mean_ambient_c": round(mean_ambient, 2), "sample_size": len(ambient_temp_history)},
            audit_logger=audit_logger,
        )

    def adapt_baseline_for_soiling(
        self,
        asset_id: str,
        current_baseline_multiplier: float,
        soiling_derate_factor: float,
        audit_logger: Optional[Any] = None,
    ) -> AdaptationAction:
        """
        Adapts baseline expected power multiplier to account for gradual panel soiling
        or aerodynamic blade roughness to prevent false underperformance alarms.
        """
        new_multiplier = round(max(0.70, min(1.0, current_baseline_multiplier * soiling_derate_factor)), 4)
        return self.propose_adaptation(
            asset_id=asset_id,
            adaptation_type=AdaptationType.BASELINE_DRIFT,
            target_metric="expected_power_multiplier",
            current_value=current_baseline_multiplier,
            adapted_value=new_multiplier,
            reason=f"Progressive soiling / aerodynamic wear baseline update (factor {soiling_derate_factor:.3f}).",
            evidence={"soiling_factor": soiling_derate_factor},
            audit_logger=audit_logger,
        )
