"""
REAMP Phase 10 Automated Verification Suite - O&M and CMMS Integration.
Validates the complete 12-stage closed-loop maintenance lifecycle:
Anomaly -> Diagnosis -> Severity -> Risk -> Production Impact -> Recommendation
-> Work Order -> Assignment -> Execution -> Verification -> Closure -> Feedback.

Enforces:
1. Strict Human-in-the-Loop (HITL) safety gating (PermissionError on unapproved dispatch).
2. Technician skill qualification and parts inventory reservation/consumption.
3. Automated OEM warranty claim recovery.
4. Complete end-to-end traceability chain:
   Asset -> Anomaly -> Decision -> Work Order -> Action -> Result.
"""

import unittest
import datetime
import os
import sys

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.maintenance.models import (
    MaintenanceRecommendation,
    MaintenanceParadigm,
    MaintenancePriority,
    MaintenanceUrgency,
    PriorityScoreBreakdown,
)
from reamp.cmms.models import (
    IncidentSeverity,
    IncidentStatus,
    WorkOrderStatus,
    MaintenanceType,
    Technician,
    SparePart,
    WarrantyRecord,
    WarrantyStatus,
    WarrantyClaimStatus,
)
from reamp.cmms.inventory import InventoryManager
from reamp.cmms.workflow import CMMSWorkflowEngine


class TestPhase10CMMSIntegration(unittest.TestCase):
    """Test suite validating Phase 10 O&M and CMMS integration."""

    def setUp(self):
        """Initializes inventory catalog, technicians, warranties, and workflow engine."""
        # 1. Warehouse Spare Parts Catalog
        self.fan_part = SparePart(
            part_sku="FAN-48V-DC-120MM",
            name="Inverter High-Flow 48V DC Cooling Fan",
            category="COOLING",
            quantity_on_hand=5,
            quantity_reserved=0,
            reorder_threshold=2,
            unit_cost_usd=120.0,
            lead_time_days=4,
        )
        self.fuse_part = SparePart(
            part_sku="FUSE-1500V-30A",
            name="1500V DC Solar String Fuse",
            category="ELECTRICAL",
            quantity_on_hand=10,
            quantity_reserved=0,
            reorder_threshold=3,
            unit_cost_usd=25.0,
            lead_time_days=2,
        )
        self.inventory = InventoryManager([self.fan_part, self.fuse_part])

        # 2. Workflow Engine
        self.cmms = CMMSWorkflowEngine(self.inventory)

        # 3. Register Technicians
        self.tech_hvac = Technician(
            technician_id="TECH-001",
            name="Alice Morgan",
            skills=["INVERTER_SPECIALIST", "COOLING_HVAC", "GENERAL_MAINTENANCE"],
            hourly_rate_usd=90.0,
            is_available=True,
        )
        self.tech_junior = Technician(
            technician_id="TECH-002",
            name="Bob Miller",
            skills=["GENERAL_MAINTENANCE"],
            hourly_rate_usd=60.0,
            is_available=True,
        )
        self.cmms.register_technician(self.tech_hvac)
        self.cmms.register_technician(self.tech_junior)

        # 4. Register Asset Warranty
        self.inv_warranty = WarrantyRecord(
            warranty_id="WAR-SMA-2024-001",
            asset_id="INV-WEST-01",
            subsystem="INVERTER",
            oem_vendor="SMA Solar Technology",
            warranty_start="2024-01-01T00:00:00Z",
            warranty_end="2029-01-01T00:00:00Z",
            terms="Full OEM parts and labor replacement for inverter thermal and power module defects.",
            status=WarrantyStatus.ACTIVE,
        )
        self.cmms.register_warranty(self.inv_warranty)

    def test_01_hitl_safety_gating_enforcement(self):
        """
        AI Safety Gate:
        Verifies that work orders default to PENDING_HITL_APPROVAL
        and CANNOT be dispatched without explicit human approval.
        """
        # Create incident
        incident = self.cmms.create_incident(
            asset_id="INV-WEST-01",
            subsystem="INVERTER",
            severity=IncidentSeverity.MAJOR,
            title="Inverter IGBT Overheating",
            description="Bridge B temperature exceeds 88C under 85% load.",
            anomaly_id="ANOM-20260911-0042",
        )

        # Create algorithmic recommendation
        rec = MaintenanceRecommendation(
            recommendation_id="REC-2026-901",
            asset_id="INV-WEST-01",
            timestamp="2026-09-11T12:00:00Z",
            paradigm=MaintenanceParadigm.CONDITION_BASED,
            urgency=MaintenanceUrgency.URGENT_DAYS,
            priority=MaintenancePriority.P2_HIGH,
            rul_prediction=None,
            priority_breakdown=PriorityScoreBreakdown(
                failure_probability_contrib=22.0,
                criticality_contrib=18.0,
                production_impact_contrib=16.0,
                safety_contrib=10.0,
                cost_avoidance_contrib=8.0,
                spares_logistics_contrib=5.0,
                composite_priority_score=79.0,
            ),
            recommended_action="Inspect and replace cooling fan FAN-48V-DC-120MM.",
            required_spares=["FAN-48V-DC-120MM"],
            estimated_downtime_hours=2.0,
            estimated_avoided_cost_usd=1400.0,
            explanation="Elevated IGBT temperature gradient indicates partial fan bearing failure.",
            model_version="reamp-cbm-v1.0",
        )

        # Generate draft work order
        wo = self.cmms.create_work_order_from_recommendation(
            incident_id=incident.incident_id,
            recommendation=rec,
            required_skill="COOLING_HVAC",
        )

        # 1. Check default status
        self.assertEqual(wo.status, WorkOrderStatus.PENDING_HITL_APPROVAL)
        self.assertEqual(incident.status, IncidentStatus.WORK_ORDER_CREATED)

        # 2. Attempt dispatch BEFORE human approval -> MUST raise PermissionError
        with self.assertRaises(PermissionError) as ctx:
            self.cmms.assign_and_dispatch(
                work_order_id=wo.work_order_id,
                technician_id="TECH-001",
            )
        self.assertIn("HITL Gating Violation", str(ctx.exception))
        self.assertIn("Explicit human approval is required", str(ctx.exception))

        # 3. Test Rejection flow
        wo_rejected = self.cmms.reject_work_order(
            work_order_id=wo.work_order_id,
            rejected_by="Lead Engineer Smith",
            rejection_reason="Sensor decalibrated, site visit cancelled.",
        )
        self.assertEqual(wo_rejected.status, WorkOrderStatus.REJECTED)
        self.assertEqual(incident.status, IncidentStatus.CLOSED)

    def test_02_technician_skill_and_inventory_reservation(self):
        """
        Validates technician skill matching and inventory reservation barriers.
        """
        incident = self.cmms.create_incident(
            asset_id="INV-WEST-01",
            subsystem="INVERTER",
            severity=IncidentSeverity.CRITICAL,
            title="Inverter Internal Fan Locked",
            description="Zero RPM feedback on cooling fan.",
        )
        rec = MaintenanceRecommendation(
            recommendation_id="REC-2026-902",
            asset_id="INV-WEST-01",
            timestamp="2026-09-11T12:00:00Z",
            paradigm=MaintenanceParadigm.REACTIVE,
            urgency=MaintenanceUrgency.IMMEDIATE_HOURS,
            priority=MaintenancePriority.P1_CRITICAL,
            rul_prediction=None,
            priority_breakdown=PriorityScoreBreakdown(
                failure_probability_contrib=25.0,
                criticality_contrib=20.0,
                production_impact_contrib=20.0,
                safety_contrib=15.0,
                cost_avoidance_contrib=10.0,
                spares_logistics_contrib=10.0,
                composite_priority_score=100.0,
                is_safety_override=True,
            ),
            recommended_action="Replace seized 48V cooling fan.",
            required_spares=["FAN-48V-DC-120MM"],
            estimated_downtime_hours=1.5,
            estimated_avoided_cost_usd=3500.0,
            explanation="Fan seized causing inverter emergency trip.",
            model_version="reamp-reactive-v1.0",
        )
        wo = self.cmms.create_work_order_from_recommendation(
            incident_id=incident.incident_id,
            recommendation=rec,
            required_skill="COOLING_HVAC",
        )

        # Human approves
        self.cmms.approve_work_order(wo.work_order_id, approved_by="Chief Engineer Miller")

        # Attempt to assign technician lacking required skill
        with self.assertRaises(ValueError) as ctx:
            self.cmms.assign_and_dispatch(
                work_order_id=wo.work_order_id,
                technician_id="TECH-002",  # Bob only has GENERAL_MAINTENANCE
            )
        self.assertIn("lacks required skill certification", str(ctx.exception))

        # Assign qualified technician
        wo_dispatched = self.cmms.assign_and_dispatch(
            work_order_id=wo.work_order_id,
            technician_id="TECH-001",
            parts_allocation={"FAN-48V-DC-120MM": 1},
        )
        self.assertEqual(wo_dispatched.status, WorkOrderStatus.DISPATCHED)
        self.assertEqual(wo_dispatched.assigned_technician_id, "TECH-001")

        # Check that 1 fan was reserved
        part = self.inventory.get_part("FAN-48V-DC-120MM")
        self.assertEqual(part.quantity_on_hand, 5)
        self.assertEqual(part.quantity_reserved, 1)
        self.assertEqual(part.available_quantity, 4)

    def test_03_end_to_end_12_stage_lifecycle_and_traceability(self):
        """
        Quality Gate Test:
        Executes the complete 12-stage lifecycle and verifies unbroken lineage:
        Asset -> Anomaly -> Decision -> Work Order -> Action -> Result.
        Also verifies warranty claim generation and inventory consumption.
        """
        asset_id = "INV-WEST-01"
        anomaly_id = "ANOM-20260911-0088"

        # Stage 1: Anomaly Ingestion & Stage 2-3: Diagnosis & Severity
        incident = self.cmms.create_incident(
            asset_id=asset_id,
            subsystem="INVERTER",
            severity=IncidentSeverity.MAJOR,
            title="IGBT Heat Sink Thermal Dissipation Failure",
            description="Phase B heatsink delta-T increased from 4.2C to 18.6C.",
            anomaly_id=anomaly_id,
        )
        self.assertEqual(incident.status, IncidentStatus.OPEN)

        # Stage 4-6: Risk, Production Impact & Maintenance Recommendation
        rec = MaintenanceRecommendation(
            recommendation_id="REC-2026-903",
            asset_id=asset_id,
            timestamp="2026-09-11T13:00:00Z",
            paradigm=MaintenanceParadigm.REACTIVE,
            urgency=MaintenanceUrgency.URGENT_DAYS,
            priority=MaintenancePriority.P2_HIGH,
            rul_prediction=None,
            priority_breakdown=PriorityScoreBreakdown(
                failure_probability_contrib=20.0,
                criticality_contrib=18.0,
                production_impact_contrib=17.0,
                safety_contrib=12.0,
                cost_avoidance_contrib=8.0,
                spares_logistics_contrib=5.0,
                composite_priority_score=80.0,
            ),
            recommended_action="Replace cooling fan FAN-48V-DC-120MM and clean heatsink fins.",
            required_spares=["FAN-48V-DC-120MM"],
            estimated_downtime_hours=2.0,
            estimated_avoided_cost_usd=2200.0,
            explanation="Thermal delta-T breach.",
            model_version="reamp-cbm-v1.0",
        )

        # Stage 7: Work Order Draft Generation
        wo = self.cmms.create_work_order_from_recommendation(
            incident_id=incident.incident_id,
            recommendation=rec,
            required_skill="INVERTER_SPECIALIST",
        )
        self.assertEqual(wo.status, WorkOrderStatus.PENDING_HITL_APPROVAL)

        # Stage 8: Human-in-the-Loop (HITL) Decision Gate
        wo_approved = self.cmms.approve_work_order(
            work_order_id=wo.work_order_id,
            approved_by="Lead Eng. Sarah Chen",
            decision_notes="Confirmed IGBT temperature rise; approved for urgent fan replacement.",
        )
        self.assertEqual(wo_approved.status, WorkOrderStatus.APPROVED)
        self.assertIsNotNone(wo_approved.hitl_approval)
        self.assertEqual(wo_approved.hitl_approval.approved_by, "Lead Eng. Sarah Chen")

        # Stage 9: Technician Assignment & Inventory Reservation
        wo_dispatched = self.cmms.assign_and_dispatch(
            work_order_id=wo.work_order_id,
            technician_id="TECH-001",
            parts_allocation={"FAN-48V-DC-120MM": 1},
        )
        self.assertEqual(wo_dispatched.status, WorkOrderStatus.DISPATCHED)

        # Stage 10: Field Execution & Maintenance Logging
        self.cmms.start_work(wo.work_order_id)
        self.assertEqual(self.cmms.get_work_order(wo.work_order_id).status, WorkOrderStatus.IN_PROGRESS)

        log = self.cmms.complete_work(
            work_order_id=wo.work_order_id,
            actions_taken="Replaced damaged fan FAN-48V-DC-120MM, vacuumed heatsink, renewed thermal grease.",
            labor_hours_actual=1.5,
            parts_consumed={"FAN-48V-DC-120MM": 1},
            root_cause_found="Bearing seizure in secondary cooling fan.",
            downtime_minutes=90.0,
        )
        self.assertEqual(self.cmms.get_work_order(wo.work_order_id).status, WorkOrderStatus.COMPLETED)
        self.assertEqual(log.total_parts_cost_usd, 120.0)

        # Check inventory permanent deduction
        part = self.inventory.get_part("FAN-48V-DC-120MM")
        self.assertEqual(part.quantity_on_hand, 4)
        self.assertEqual(part.quantity_reserved, 0)

        # Stage 11: Post-Maintenance Verification
        wo_verified = self.cmms.verify_work_order(
            work_order_id=wo.work_order_id,
            post_telemetry_healthy=True,
            verification_notes="Post-repair thermal delta-T stabilized at 2.8C under 100% capacity.",
        )
        self.assertEqual(wo_verified.status, WorkOrderStatus.VERIFIED)

        # Stage 12: Closure, Warranty Claim & Feedback
        traceability = self.cmms.close_work_order(
            work_order_id=wo.work_order_id,
            closed_by="Chief O&M Director",
        )
        self.assertEqual(self.cmms.get_work_order(wo.work_order_id).status, WorkOrderStatus.CLOSED)

        # Verify Quality Gate Traceability:
        # Asset -> Anomaly -> Decision -> Work Order -> Action -> Result
        self.assertIsNotNone(traceability)
        self.assertEqual(traceability.asset_id, asset_id)
        self.assertEqual(traceability.anomaly_id, anomaly_id)
        self.assertEqual(traceability.decision_id, wo.hitl_approval.approval_id)
        self.assertEqual(traceability.work_order_id, wo.work_order_id)
        self.assertEqual(traceability.action_id, log.log_id)
        self.assertIn("Successfully verified post-repair", traceability.result)

        # Verify Automatic OEM Warranty Claim Generation
        wo_final = self.cmms.get_work_order(wo.work_order_id)
        self.assertIsNotNone(wo_final.warranty_claim)
        claim = wo_final.warranty_claim
        self.assertEqual(claim.warranty_id, "WAR-SMA-2024-001")
        self.assertEqual(claim.status, WarrantyClaimStatus.SUBMITTED)
        # Expected claim: 1.5h * $90 = $135 labor + $120 parts = $255
        self.assertAlmostEqual(claim.labor_cost_usd, 135.0, places=1)
        self.assertAlmostEqual(claim.parts_cost_usd, 120.0, places=1)
        self.assertAlmostEqual(claim.claimed_amount_usd, 255.0, places=1)

        # Verify incident resolved and closed
        inc_final = self.cmms.get_incident(incident.incident_id)
        self.assertEqual(inc_final.status, IncidentStatus.CLOSED)
        self.assertIsNotNone(inc_final.resolved_at)

        # Verify Asset History Logged
        history = self.cmms.get_asset_maintenance_history(asset_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["downtime_minutes"], 90.0)
        self.assertEqual(history[0]["warranty_claimed_usd"], 255.0)

    def test_04_inventory_reorder_point_alerts(self):
        """
        Validates inventory low-stock alerts when stock breaches reorder thresholds.
        """
        # Consume 3 fans leaving 2 on hand (threshold is 2)
        self.inventory.reserve_parts({"FAN-48V-DC-120MM": 3})
        self.inventory.consume_parts({"FAN-48V-DC-120MM": 3})

        alerts = self.inventory.check_reorder_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["part_sku"], "FAN-48V-DC-120MM")
        self.assertEqual(alerts[0]["available_quantity"], 2)
        self.assertGreaterEqual(alerts[0]["reorder_recommended_quantity"], 5)

        # Restock
        self.inventory.restock("FAN-48V-DC-120MM", 10)
        alerts_after = self.inventory.check_reorder_alerts()
        self.assertEqual(len(alerts_after), 0)

    def test_05_preventive_maintenance_workflow(self):
        """
        Validates planned preventive maintenance and inspection work order flow.
        """
        pm_wo = self.cmms.create_preventive_work_order(
            asset_id="WIND-TURBINE-04",
            title="Annual Hydraulic Pitch System Fluid Sampling",
            recommended_action="Extract 500ml hydraulic oil sample and replace breather filter.",
            priority=MaintenancePriority.P3_MEDIUM,
            required_skill="GENERAL_MAINTENANCE",
            estimated_labor_hours=3.0,
            maintenance_type=MaintenanceType.INSPECTION,
        )
        self.assertEqual(pm_wo.maintenance_type, MaintenanceType.INSPECTION)
        self.assertEqual(pm_wo.status, WorkOrderStatus.PENDING_HITL_APPROVAL)

        # Approve and dispatch to Bob Miller (Junior tech)
        self.cmms.approve_work_order(pm_wo.work_order_id, approved_by="O&M Supervisor")
        self.cmms.assign_and_dispatch(pm_wo.work_order_id, "TECH-002")

        # Execute inspection
        self.cmms.start_work(pm_wo.work_order_id)
        log = self.cmms.complete_work(
            work_order_id=pm_wo.work_order_id,
            actions_taken="Sample extracted; breather filter replaced; no leaks observed.",
            labor_hours_actual=2.5,
            parts_consumed={},
            downtime_minutes=45.0,
        )
        self.assertEqual(log.labor_hours_actual, 2.5)

        # Verify and close
        self.cmms.verify_work_order(pm_wo.work_order_id, post_telemetry_healthy=True)
        traceability = self.cmms.close_work_order(pm_wo.work_order_id)

        self.assertIsNotNone(traceability)
        self.assertIsNone(traceability.anomaly_id)  # PM has no triggering anomaly
        self.assertEqual(pm_wo.status, WorkOrderStatus.CLOSED)


if __name__ == "__main__":
    unittest.main()
