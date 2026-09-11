"""
REAMP CMMS Workflow Engine.
Orchestrates the 12-stage closed-loop maintenance lifecycle from anomaly ingestion
to human-in-the-loop (HITL) approval, qualified technician dispatch, execution logging,
downtime accounting, post-maintenance verification, warranty claims, and full traceability.
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid
import copy

from reamp.cmms.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    WorkOrder,
    WorkOrderStatus,
    MaintenanceType,
    HITLApprovalRecord,
    Technician,
    SparePart,
    SparePartUsage,
    MaintenanceLog,
    WarrantyRecord,
    WarrantyClaim,
    WarrantyClaimStatus,
    WarrantyStatus,
    TraceabilityRecord,
)
from reamp.cmms.inventory import InventoryManager
from reamp.maintenance.models import (
    MaintenanceRecommendation,
    MaintenanceParadigm,
    MaintenancePriority,
)


class CMMSWorkflowEngine:
    """
    Central CMMS Orchestrator managing end-to-end maintenance operations,
    HITL authorization barriers, and complete audit lineage.
    """

    def __init__(self, inventory_manager: Optional[InventoryManager] = None) -> None:
        self.inventory: InventoryManager = inventory_manager or InventoryManager()
        self.incidents: Dict[str, Incident] = {}
        self.work_orders: Dict[str, WorkOrder] = {}
        self.technicians: Dict[str, Technician] = {}
        self.warranties: Dict[str, List[WarrantyRecord]] = {}  # asset_id -> list[WarrantyRecord]
        self.warranty_claims: Dict[str, WarrantyClaim] = {}
        self.maintenance_logs: Dict[str, MaintenanceLog] = {}
        self.traceability_records: Dict[str, TraceabilityRecord] = {}
        self.asset_history: Dict[str, List[Dict[str, Any]]] = {}  # asset_id -> list of event summaries

    # -------------------------------------------------------------------------
    # 1. Registration & Management Helpers
    # -------------------------------------------------------------------------

    def register_technician(self, technician: Technician) -> None:
        """Registers a field technician in the CMMS."""
        self.technicians[technician.technician_id] = copy.deepcopy(technician)

    def register_warranty(self, warranty: WarrantyRecord) -> None:
        """Registers an equipment warranty coverage contract."""
        if warranty.asset_id not in self.warranties:
            self.warranties[warranty.asset_id] = []
        self.warranties[warranty.asset_id].append(copy.deepcopy(warranty))

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        """Retrieves a work order by ID."""
        return self.work_orders.get(work_order_id)

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieves an incident by ID."""
        return self.incidents.get(incident_id)

    def get_traceability_record(self, traceability_id_or_wo: str) -> Optional[TraceabilityRecord]:
        """Retrieves an immutable audit traceability record."""
        if traceability_id_or_wo in self.traceability_records:
            return self.traceability_records[traceability_id_or_wo]
        for tr in self.traceability_records.values():
            if tr.work_order_id == traceability_id_or_wo:
                return tr
        return None

    def get_asset_maintenance_history(self, asset_id: str) -> List[Dict[str, Any]]:
        """Retrieves historical downtime and completed work orders for an asset."""
        return self.asset_history.get(asset_id, [])

    # -------------------------------------------------------------------------
    # 2. Stage 1-5: Incident Creation & Ingestion
    # -------------------------------------------------------------------------

    def create_incident(
        self,
        asset_id: str,
        subsystem: str,
        severity: IncidentSeverity,
        title: str,
        description: str,
        anomaly_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Incident:
        """
        Ingests an anomaly or detected fault, creating an operational Incident.
        """
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        incident = Incident(
            incident_id=incident_id,
            asset_id=asset_id,
            subsystem=subsystem,
            anomaly_id=anomaly_id,
            severity=severity,
            title=title,
            description=description,
            detected_at=now_str,
            status=IncidentStatus.OPEN,
            metadata=metadata or {},
        )
        self.incidents[incident_id] = incident
        return incident

    # -------------------------------------------------------------------------
    # 3. Stage 6-7: Work Order Draft Generation (HITL Gated by Default)
    # -------------------------------------------------------------------------

    def create_work_order_from_recommendation(
        self,
        incident_id: str,
        recommendation: MaintenanceRecommendation,
        required_skill: str = "GENERAL_MAINTENANCE",
    ) -> WorkOrder:
        """
        Converts an algorithmic MaintenanceRecommendation into a draft WorkOrder.
        Enforces AI safety rule: Status MUST default to PENDING_HITL_APPROVAL.
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        # Map MaintenanceParadigm to MaintenanceType
        paradigm_map = {
            MaintenanceParadigm.REACTIVE: MaintenanceType.CORRECTIVE,
            MaintenanceParadigm.CONDITION_BASED: MaintenanceType.CONDITION_BASED,
            MaintenanceParadigm.PREDICTIVE: MaintenanceType.PREDICTIVE,
            MaintenanceParadigm.PRESCRIPTIVE: MaintenanceType.PREDICTIVE,
        }
        m_type = paradigm_map.get(recommendation.paradigm, MaintenanceType.CORRECTIVE)

        wo_id = f"WO-{uuid.uuid4().hex[:8].upper()}"
        work_order = WorkOrder(
            work_order_id=wo_id,
            asset_id=recommendation.asset_id,
            title=f"Maintenance for {recommendation.asset_id}: {incident.title}",
            maintenance_type=m_type,
            priority=recommendation.priority,
            recommended_action=recommendation.recommended_action,
            incident_id=incident_id,
            status=WorkOrderStatus.PENDING_HITL_APPROVAL,  # Strict HITL Gating
            required_skill=required_skill,
            estimated_labor_hours=recommendation.estimated_downtime_hours or 2.5,
            required_parts=copy.deepcopy(recommendation.required_spares),
            metadata={
                "recommendation_id": recommendation.recommendation_id,
                "urgency": recommendation.urgency.value if hasattr(recommendation.urgency, "value") else str(recommendation.urgency),
                "model_version": recommendation.model_version,
                "estimated_avoided_cost_usd": recommendation.estimated_avoided_cost_usd,
            },
        )

        self.work_orders[wo_id] = work_order
        incident.status = IncidentStatus.WORK_ORDER_CREATED
        return work_order

    def create_preventive_work_order(
        self,
        asset_id: str,
        title: str,
        recommended_action: str,
        priority: MaintenancePriority = MaintenancePriority.P3_MEDIUM,
        required_skill: str = "ELECTRICAL_INSPECTION",
        estimated_labor_hours: float = 3.0,
        required_parts: Optional[List[str]] = None,
        maintenance_type: MaintenanceType = MaintenanceType.PREVENTIVE,
    ) -> WorkOrder:
        """
        Creates a scheduled preventive maintenance or inspection work order.
        """
        wo_id = f"WO-{uuid.uuid4().hex[:8].upper()}"
        work_order = WorkOrder(
            work_order_id=wo_id,
            asset_id=asset_id,
            title=title,
            maintenance_type=maintenance_type,
            priority=priority,
            recommended_action=recommended_action,
            status=WorkOrderStatus.PENDING_HITL_APPROVAL,
            required_skill=required_skill,
            estimated_labor_hours=estimated_labor_hours,
            required_parts=required_parts or [],
        )
        self.work_orders[wo_id] = work_order
        return work_order

    # -------------------------------------------------------------------------
    # 4. Stage 8: Human-in-the-Loop (HITL) Decision Gate
    # -------------------------------------------------------------------------

    def approve_work_order(
        self,
        work_order_id: str,
        approved_by: str,
        decision_notes: str = "Approved for dispatch by designated authority.",
        override_priority: Optional[MaintenancePriority] = None,
    ) -> WorkOrder:
        """
        Records mandatory human approval, moving the work order from PENDING_HITL_APPROVAL to APPROVED.
        """
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        if wo.status != WorkOrderStatus.PENDING_HITL_APPROVAL and wo.status != WorkOrderStatus.DRAFT:
            raise ValueError(f"Cannot approve work order in status '{wo.status}'.")

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        approval = HITLApprovalRecord(
            approval_id=f"HITL-{uuid.uuid4().hex[:8].upper()}",
            work_order_id=work_order_id,
            approved_by=approved_by,
            decision="APPROVED",
            decision_timestamp=now_str,
            decision_notes=decision_notes,
            override_priority=override_priority,
        )

        wo.hitl_approval = approval
        if override_priority:
            wo.priority = override_priority
        wo.status = WorkOrderStatus.APPROVED
        return wo

    def reject_work_order(
        self,
        work_order_id: str,
        rejected_by: str,
        rejection_reason: str,
    ) -> WorkOrder:
        """
        Rejects a draft work order with justification, closing the loop safely.
        """
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        approval = HITLApprovalRecord(
            approval_id=f"HITL-{uuid.uuid4().hex[:8].upper()}",
            work_order_id=work_order_id,
            approved_by=rejected_by,
            decision="REJECTED",
            decision_timestamp=now_str,
            decision_notes=rejection_reason,
        )
        wo.hitl_approval = approval
        wo.status = WorkOrderStatus.REJECTED

        if wo.incident_id and wo.incident_id in self.incidents:
            self.incidents[wo.incident_id].status = IncidentStatus.CLOSED
            self.incidents[wo.incident_id].resolved_at = now_str

        return wo

    # -------------------------------------------------------------------------
    # 5. Stage 9: Technician Assignment & Spares Reservation
    # -------------------------------------------------------------------------

    def assign_and_dispatch(
        self,
        work_order_id: str,
        technician_id: str,
        parts_allocation: Optional[Dict[str, int]] = None,
        scheduled_start: Optional[str] = None,
    ) -> WorkOrder:
        """
        Assigns a qualified field technician and reserves required inventory.
        STRICT HITL CHECK: Raises PermissionError if work order has NOT been approved.
        """
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        # AI SAFETY GATE: Prohibit dispatch without explicit human authorization
        if wo.status != WorkOrderStatus.APPROVED:
            raise PermissionError(
                f"HITL Gating Violation: Cannot dispatch Work Order '{work_order_id}' "
                f"with status '{wo.status}'. Explicit human approval is required."
            )

        # Validate technician qualification & availability
        tech = self.technicians.get(technician_id)
        if not tech:
            raise ValueError(f"Technician '{technician_id}' not registered in CMMS.")
        if not tech.is_available:
            raise ValueError(f"Technician '{tech.name}' ({technician_id}) is currently unavailable.")
        if wo.required_skill != "GENERAL_MAINTENANCE" and wo.required_skill not in tech.skills:
            raise ValueError(
                f"Technician '{tech.name}' lacks required skill certification: '{wo.required_skill}'. "
                f"Possesses: {tech.skills}"
            )
        elif wo.required_skill == "GENERAL_MAINTENANCE" and "GENERAL_MAINTENANCE" not in tech.skills and not tech.skills:
            raise ValueError(
                f"Technician '{tech.name}' has no registered skill qualifications."
            )

        # Reserve inventory parts if requested
        if parts_allocation:
            self.inventory.reserve_parts(parts_allocation)
            wo.metadata["reserved_parts"] = parts_allocation
        elif wo.required_parts:
            # Default to 1 unit of each required part
            default_reqs = {sku: 1 for sku in wo.required_parts}
            # Only reserve if parts are available in catalog
            catalog_avail = self.inventory.check_availability(wo.required_parts)
            allocable = {sku: 1 for sku, avail in catalog_avail.items() if avail}
            if allocable:
                self.inventory.reserve_parts(allocable)
                wo.metadata["reserved_parts"] = allocable

        # Update assignment
        wo.assigned_technician_id = technician_id
        tech.assigned_work_orders.append(work_order_id)
        wo.scheduled_start = scheduled_start or datetime.datetime.now(datetime.timezone.utc).isoformat()
        wo.status = WorkOrderStatus.DISPATCHED
        return wo

    # -------------------------------------------------------------------------
    # 6. Stage 10: Execution & Maintenance Logging
    # -------------------------------------------------------------------------

    def start_work(self, work_order_id: str, start_time: Optional[str] = None) -> WorkOrder:
        """Marks that physical field work has commenced on site."""
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        if wo.status != WorkOrderStatus.DISPATCHED:
            raise ValueError(f"Cannot start work order in status '{wo.status}', must be DISPATCHED.")

        wo.actual_start = start_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
        wo.status = WorkOrderStatus.IN_PROGRESS
        return wo

    def complete_work(
        self,
        work_order_id: str,
        actions_taken: str,
        labor_hours_actual: float,
        parts_consumed: Dict[str, int],
        root_cause_found: str = "",
        downtime_minutes: float = 0.0,
        completion_time: Optional[str] = None,
    ) -> MaintenanceLog:
        """
        Logs completed physical maintenance, consumes parts from inventory,
        and records actual downtime and labor effort.
        """
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        if wo.status != WorkOrderStatus.IN_PROGRESS and wo.status != WorkOrderStatus.DISPATCHED:
            raise ValueError(f"Cannot complete work order in status '{wo.status}'.")

        now_str = completion_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
        wo.actual_end = now_str

        # Deduct consumed spare parts from warehouse stock
        usages: List[SparePartUsage] = []
        if parts_consumed:
            usages = self.inventory.consume_parts(parts_consumed)

        log_id = f"LOG-{uuid.uuid4().hex[:8].upper()}"
        log = MaintenanceLog(
            log_id=log_id,
            work_order_id=work_order_id,
            asset_id=wo.asset_id,
            technician_id=wo.assigned_technician_id or "UNKNOWN",
            performed_at=now_str,
            labor_hours_actual=labor_hours_actual,
            actions_taken=actions_taken,
            parts_consumed=usages,
            root_cause_found=root_cause_found,
            downtime_minutes=downtime_minutes,
        )

        wo.execution_log = log
        self.maintenance_logs[log_id] = log
        wo.status = WorkOrderStatus.COMPLETED

        # Relieve technician active assignment
        if wo.assigned_technician_id and wo.assigned_technician_id in self.technicians:
            tech = self.technicians[wo.assigned_technician_id]
            if work_order_id in tech.assigned_work_orders:
                tech.assigned_work_orders.remove(work_order_id)

        return log

    # -------------------------------------------------------------------------
    # 7. Stage 11: Post-Maintenance Verification
    # -------------------------------------------------------------------------

    def verify_work_order(
        self,
        work_order_id: str,
        post_telemetry_healthy: bool = True,
        verification_notes: str = "Telemetry confirmed normal parameters post-repair.",
    ) -> WorkOrder:
        """
        Evaluates post-maintenance condition to verify that anomalies have cleared
        and the asset operates within nominal bounds.
        """
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        if wo.status != WorkOrderStatus.COMPLETED:
            raise ValueError(f"Cannot verify work order in status '{wo.status}', must be COMPLETED.")

        if not post_telemetry_healthy:
            wo.metadata["verification_failure"] = verification_notes
            raise RuntimeError(f"Post-maintenance verification failed for {work_order_id}: {verification_notes}")

        wo.metadata["verification_notes"] = verification_notes
        wo.status = WorkOrderStatus.VERIFIED
        return wo

    # -------------------------------------------------------------------------
    # 8. Stage 12: Closure, Warranty Recovery & Closed-Loop Feedback
    # -------------------------------------------------------------------------

    def close_work_order(
        self,
        work_order_id: str,
        closed_by: str = "Chief O&M Engineer",
    ) -> TraceabilityRecord:
        """
        Formally closes the work order:
        1. Checks warranty coverage and creates OEM claim if applicable.
        2. Resolves and closes the linked incident.
        3. Records historical downtime and MTBF statistics.
        4. Synthesizes an immutable TraceabilityRecord satisfying the Phase 10 Quality Gate:
           Asset -> Anomaly -> Decision -> Work Order -> Action -> Result.
        """
        wo = self.work_orders.get(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        if wo.status != WorkOrderStatus.VERIFIED:
            raise ValueError(f"Cannot close work order in status '{wo.status}', must be VERIFIED first.")

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        incident = self.incidents.get(wo.incident_id) if wo.incident_id else None

        # 1. Warranty Claim Processing
        warranty_claim: Optional[WarrantyClaim] = None
        asset_warranties = self.warranties.get(wo.asset_id, [])
        log = wo.execution_log

        for w_rec in asset_warranties:
            # Check if corrective maintenance was performed during active warranty
            if wo.maintenance_type == MaintenanceType.CORRECTIVE and w_rec.is_covered(now_str):
                labor_rate = 85.0
                if wo.assigned_technician_id and wo.assigned_technician_id in self.technicians:
                    labor_rate = self.technicians[wo.assigned_technician_id].hourly_rate_usd
                labor_cost = (log.labor_hours_actual if log else 0.0) * labor_rate
                parts_cost = log.total_parts_cost_usd if log else 0.0
                total_claim = labor_cost + parts_cost

                claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
                warranty_claim = WarrantyClaim(
                    claim_id=claim_id,
                    warranty_id=w_rec.warranty_id,
                    asset_id=wo.asset_id,
                    work_order_id=wo.work_order_id,
                    claimed_amount_usd=round(total_claim, 2),
                    parts_cost_usd=round(parts_cost, 2),
                    labor_cost_usd=round(labor_cost, 2),
                    submitted_at=now_str,
                    status=WarrantyClaimStatus.SUBMITTED,
                    notes=f"Auto-generated claim for {w_rec.oem_vendor} covering {w_rec.subsystem}.",
                )
                self.warranty_claims[claim_id] = warranty_claim
                wo.warranty_claim = warranty_claim
                break  # Matched primary active warranty

        # 2. Close Incident
        if incident:
            incident.status = IncidentStatus.CLOSED
            incident.resolved_at = now_str

        # 3. Update Asset Maintenance History
        if wo.asset_id not in self.asset_history:
            self.asset_history[wo.asset_id] = []

        history_entry = {
            "work_order_id": wo.work_order_id,
            "incident_id": wo.incident_id,
            "closed_at": now_str,
            "maintenance_type": wo.maintenance_type.value if hasattr(wo.maintenance_type, "value") else str(wo.maintenance_type),
            "downtime_minutes": log.downtime_minutes if log else 0.0,
            "actions_taken": log.actions_taken if log else "",
            "warranty_claimed_usd": warranty_claim.claimed_amount_usd if warranty_claim else 0.0,
        }
        self.asset_history[wo.asset_id].append(history_entry)

        # 4. Synthesize Immutable Traceability Chain
        traceability_id = f"TRACE-{uuid.uuid4().hex[:8].upper()}"
        anomaly_id = incident.anomaly_id if incident else None
        diagnosis_desc = incident.title if incident else "Scheduled Preventive Maintenance"
        decision_id = wo.hitl_approval.approval_id if wo.hitl_approval else "AUTO-SYSTEM"
        action_id = log.log_id if log else "NO-ACTION-LOG"
        result_desc = (
            f"Successfully verified post-repair. Actions: {log.actions_taken if log else 'N/A'}. "
            f"Downtime: {log.downtime_minutes if log else 0.0} min."
        )

        traceability = TraceabilityRecord(
            traceability_id=traceability_id,
            asset_id=wo.asset_id,
            anomaly_id=anomaly_id,
            diagnosis=diagnosis_desc,
            decision_id=decision_id,
            work_order_id=wo.work_order_id,
            action_id=action_id,
            result=result_desc,
            created_at=now_str,
        )

        self.traceability_records[traceability_id] = traceability
        wo.traceability = traceability
        wo.status = WorkOrderStatus.CLOSED
        return traceability
