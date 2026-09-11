"""
REAMP Adaptive Intelligence & Closed-Loop Control Models.
Defines data structures for dynamic threshold adaptation, baseline drift tracking,
closed-loop feedback state, and Human-in-the-Loop governance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional


class AdaptationType(str, Enum):
    DYNAMIC_THRESHOLD = "DYNAMIC_THRESHOLD"
    BASELINE_DRIFT = "BASELINE_DRIFT"
    DATA_QUALITY_MARGIN = "DATA_QUALITY_MARGIN"
    CONTROL_FEEDBACK = "CONTROL_FEEDBACK"


class AdaptationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PENDING_HITL_APPROVAL = "PENDING_HITL_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    REVERTED = "REVERTED"


@dataclass
class AdaptationAction:
    """A tracked, auditable adaptation of an operational threshold or baseline."""
    action_id: str
    asset_id: str
    adaptation_type: AdaptationType
    target_metric: str
    previous_value: float
    adapted_value: float
    percentage_shift: float
    requires_hitl: bool
    status: AdaptationStatus
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None


@dataclass
class ClosedLoopState:
    """State record for the 8-stage closed feedback loop."""
    cycle_id: str
    asset_id: str
    technology: str
    stage_1_observe: Dict[str, Any]
    stage_2_validate: Dict[str, Any]
    stage_3_assess_health: float
    stage_4_detect_anomalies: List[str]
    stage_5_predict_rul: Optional[float]
    stage_6_decide_action: str
    stage_7_act: Dict[str, Any]
    stage_8_observe_feedback: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
