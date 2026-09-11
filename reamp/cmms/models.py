"""
REAMP CMMS & Operations & Maintenance Data Models.
Standardized dataclasses and enums for incidents, work orders, human-in-the-loop (HITL)
governance, technicians, spare parts inventory, maintenance execution logs,
warranties, and end-to-end traceability chains.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime
import uuid

# Import MaintenancePriority from maintenance models for cross-layer continuity
from reamp.maintenance.models import MaintenancePriority


class IncidentSeverity(str, Enum):
    """Operational severity of detected condition or incident."""
    CRITICAL = "CRITICAL"         # Immediate safety hazard or total shutdown
    MAJOR = "MAJOR"               # Substantial power loss (> 20%) or acute degradation
    MINOR = "MINOR"               # Subsystem derating (< 10%) or early wear
    INFORMATIONAL = "INFORMATIONAL" # Telemetry anomaly or benign drift


class IncidentStatus(str, Enum):
    """Lifecycle status of an operational incident."""
    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    WORK_ORDER_CREATED = "WORK_ORDER_CREATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class WorkOrderStatus(str, Enum):
    """Governed lifecycle status of a maintenance work order."""
    DRAFT = "DRAFT"
    PENDING_HITL_APPROVAL = "PENDING_HITL_APPROVAL" # Default: AI proposed, waiting for human
    APPROVED = "APPROVED"                           # Human approved for dispatch
    DISPATCHED = "DISPATCHED"                       # Assigned to tech and dispatched
    IN_PROGRESS = "IN_PROGRESS"                     # Technician performing physical work
    COMPLETED = "COMPLETED"                         # Physical work done, awaiting verification
    VERIFIED = "VERIFIED"                           # Telemetry verified condition resolved
    CLOSED = "CLOSED"                               # Final sign-off & feedback complete
    REJECTED = "REJECTED"                           # Rejected by human operator


class MaintenanceType(str, Enum):
    """Classification of maintenance intervention."""
    CORRECTIVE = "CORRECTIVE"           # Urgent fix post-trip or fault
    PREVENTIVE = "PREVENTIVE"           # Scheduled periodic servicing
    CONDITION_BASED = "CONDITION_BASED" # Triggered by health index threshold
    PREDICTIVE = "PREDICTIVE"           # Triggered by RUL forecast
    INSPECTION = "INSPECTION"           # Audit, thermography, visual inspection


class WarrantyStatus(str, Enum):
    """Contractual coverage status."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    VOIDED = "VOIDED"


class WarrantyClaimStatus(str, Enum):
    """Reimbursement status of an OEM warranty claim."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"


@dataclass
class Incident:
    """Operational incident representing a detected anomaly or asset failure."""
    incident_id: str
    asset_id: str
    subsystem: str
    anomaly_id: Optional[str]
    severity: IncidentSeverity
    title: str
    description: str
    detected_at: str
    status: IncidentStatus = IncidentStatus.OPEN
    resolved_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value if isinstance(self.severity, IncidentSeverity) else self.severity
        d["status"] = self.status.value if isinstance(self.status, IncidentStatus) else self.status
        return d


@dataclass
class HITLApprovalRecord:
    """Audit record capturing explicit human-in-the-loop authorization."""
    approval_id: str
    work_order_id: str
    approved_by: str
    decision: str  # "APPROVED" or "REJECTED"
    decision_timestamp: str
    decision_notes: str
    override_priority: Optional[MaintenancePriority] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.override_priority:
            d["override_priority"] = (
                self.override_priority.value
                if isinstance(self.override_priority, MaintenancePriority)
                else self.override_priority
            )
        return d


@dataclass
class Technician:
    """Qualified field technician available for maintenance operations."""
    technician_id: str
    name: str
    skills: List[str]  # e.g., ["HIGH_VOLTAGE", "INVERTER_SPECIALIST", "BESS_SAFETY"]
    is_available: bool = True
    hourly_rate_usd: float = 85.0
    assigned_work_orders: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SparePart:
    """Warehouse inventory spare part record."""
    part_sku: str
    name: str
    category: str
    quantity_on_hand: int
    quantity_reserved: int = 0
    reorder_threshold: int = 2
    unit_cost_usd: float = 150.0
    lead_time_days: int = 3

    @property
    def available_quantity(self) -> int:
        return max(0, self.quantity_on_hand - self.quantity_reserved)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["available_quantity"] = self.available_quantity
        return d


@dataclass
class SparePartUsage:
    """Record of spare parts consumed during maintenance execution."""
    part_sku: str
    quantity: int
    unit_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        return self.quantity * self.unit_cost_usd

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_cost_usd"] = self.total_cost_usd
        return d


@dataclass
class MaintenanceLog:
    """Execution log for completed on-site physical work."""
    log_id: str
    work_order_id: str
    asset_id: str
    technician_id: str
    performed_at: str
    labor_hours_actual: float
    actions_taken: str
    parts_consumed: List[SparePartUsage] = field(default_factory=list)
    root_cause_found: str = ""
    downtime_minutes: float = 0.0

    @property
    def total_parts_cost_usd(self) -> float:
        return sum(p.total_cost_usd for p in self.parts_consumed)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["parts_consumed"] = [p.to_dict() for p in self.parts_consumed]
        d["total_parts_cost_usd"] = self.total_parts_cost_usd
        return d


@dataclass
class WarrantyRecord:
    """Equipment warranty coverage record."""
    warranty_id: str
    asset_id: str
    subsystem: str
    oem_vendor: str
    warranty_start: str
    warranty_end: str
    terms: str
    status: WarrantyStatus = WarrantyStatus.ACTIVE

    def is_covered(self, event_date_str: str) -> bool:
        """Determines if the specified event timestamp falls within active warranty bounds."""
        if self.status != WarrantyStatus.ACTIVE:
            return False
        event_dt = datetime.datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
        start_dt = datetime.datetime.fromisoformat(self.warranty_start.replace("Z", "+00:00"))
        end_dt = datetime.datetime.fromisoformat(self.warranty_end.replace("Z", "+00:00"))
        return start_dt <= event_dt <= end_dt

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, WarrantyStatus) else self.status
        return d


@dataclass
class WarrantyClaim:
    """Warranty recovery claim submitted to OEM equipment vendor."""
    claim_id: str
    warranty_id: str
    asset_id: str
    work_order_id: str
    claimed_amount_usd: float
    parts_cost_usd: float
    labor_cost_usd: float
    submitted_at: str
    status: WarrantyClaimStatus = WarrantyClaimStatus.DRAFT
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, WarrantyClaimStatus) else self.status
        return d


@dataclass
class TraceabilityRecord:
    """
    Immutable audit chain verifying end-to-end lineage:
    Asset -> Anomaly -> Decision -> Work Order -> Action -> Result
    """
    traceability_id: str
    asset_id: str
    anomaly_id: Optional[str]
    diagnosis: str
    decision_id: str
    work_order_id: str
    action_id: str
    result: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkOrder:
    """
    Canonical CMMS Work Order.
    Governs technician dispatch, resource allocation, and closed-loop verification.
    """
    work_order_id: str
    asset_id: str
    title: str
    maintenance_type: MaintenanceType
    priority: MaintenancePriority
    recommended_action: str
    incident_id: Optional[str] = None
    status: WorkOrderStatus = WorkOrderStatus.PENDING_HITL_APPROVAL
    required_skill: str = "GENERAL_MAINTENANCE"
    estimated_labor_hours: float = 2.0
    required_parts: List[str] = field(default_factory=list)
    assigned_technician_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None
    hitl_approval: Optional[HITLApprovalRecord] = None
    execution_log: Optional[MaintenanceLog] = None
    warranty_claim: Optional[WarrantyClaim] = None
    traceability: Optional[TraceabilityRecord] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["maintenance_type"] = (
            self.maintenance_type.value
            if isinstance(self.maintenance_type, MaintenanceType)
            else self.maintenance_type
        )
        d["priority"] = (
            self.priority.value
            if isinstance(self.priority, MaintenancePriority)
            else self.priority
        )
        d["status"] = (
            self.status.value
            if isinstance(self.status, WorkOrderStatus)
            else self.status
        )
        if self.hitl_approval:
            d["hitl_approval"] = self.hitl_approval.to_dict()
        if self.execution_log:
            d["execution_log"] = self.execution_log.to_dict()
        if self.warranty_claim:
            d["warranty_claim"] = self.warranty_claim.to_dict()
        if self.traceability:
            d["traceability"] = self.traceability.to_dict()
        return d
