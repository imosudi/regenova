"""
REAMP Phase 15 - MVP Integration Automated Test Suite.

Validates:
1. Authentication & Security (HMAC token issue, tamper check, expiry)
2. Multi-Tenant Hierarchy (Org -> Portfolio -> Site)
3. Asset Registry & Status Tracking
4. Sensor Registry
5. Ingestion & HMAC Telemetry Packet Verification
6. Time-Series Storage & SQLite Edge Buffer
7. Unified SCADA Dashboard State Aggregator
8. Deterministic Asset Health Model Derating
9. Multi-Level Anomaly Detection Integration
10. Real-Time Alerting Engine & Deduplication
11. CMMS Maintenance & Mandatory HITL Safety Gate
12. Executive Operational & Financial Governance Report
13. Unified Programmatic API Facade
14. Tamper-Evident SHA-256 Audit Chain Verification
15. Unbroken 10-Stage Pipeline End-to-End Integration
"""

import copy
import datetime
import json
import os
import sys
import unittest

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.mvp import (
    Organization,
    Portfolio,
    Site,
    AssetRecord,
    SensorRecord,
    TechnologyType,
    AssetStatus,
    AlertRecord,
    AlertSeverity,
    AlertStatus,
    REAMPApplicationMVP,
    REAMPAppAPI,
)
from reamp.security.models import SecurityRole, Permission, SecurityToken
from reamp.cmms.models import WorkOrderStatus, MaintenanceType


class TestPhase15MVPIntegration(unittest.TestCase):
    """Automated integration suite validating the 14 capabilities of REAMP MVP."""

    def setUp(self):
        """Initializes a fresh in-memory REAMP MVP instance with default topology."""
        self.app = REAMPApplicationMVP(
            tenant_id="TENANT-SOLAR-CORP",
            storage_db=":memory:",
            master_secret="test-phase15-master-secret-key-32b",
        )
        self.app.initialize_default_topology()
        self.api = REAMPAppAPI(self.app)

    # =========================================================================
    # 1. Authentication & Security Tests
    # =========================================================================

    def test_01_auth_token_issuance_and_validation(self):
        """Verifies HMAC token generation, payload decoding, and signature verification."""
        token_str = self.api.authenticate(client_id="eng-alice", role=SecurityRole.CHIEF_ENGINEER)
        self.assertIsNotNone(token_str)

        identity = self.api._validate_token(token_str)
        self.assertEqual(identity.user_id, "eng-alice")
        self.assertEqual(identity.role, SecurityRole.CHIEF_ENGINEER)
        self.assertTrue(identity.has_permission(Permission.APPROVE_HITL))

    def test_02_auth_tampered_token_rejected(self):
        """Verifies that tampering with signed token payload raises PermissionError."""
        token_str = self.api.authenticate(client_id="eng-bob", role=SecurityRole.OPERATOR)
        data = json.loads(token_str)
        data["role"] = SecurityRole.SECURITY_ADMIN.value  # Privilege escalation tamper
        tampered_str = json.dumps(data)

        with self.assertRaises(PermissionError):
            self.api._validate_token(tampered_str)

    # =========================================================================
    # 2. Multi-Tenant Org / Portfolio / Site Hierarchy Tests
    # =========================================================================

    def test_03_organization_and_site_hierarchy(self):
        """Validates top-level multi-tenant hierarchy and retrieval."""
        self.assertIn(self.app.tenant_id, self.app.organizations)
        self.assertIn("PORT-SW-UTILITY", self.app.portfolios)
        self.assertIn("SITE-MOJAVE-01", self.app.sites)

        site = self.app.sites["SITE-MOJAVE-01"]
        self.assertEqual(site.technology, TechnologyType.SOLAR_PV)
        self.assertEqual(site.rated_capacity_mw, 50.0)

    # =========================================================================
    # 3. Asset & Sensor Registry Tests
    # =========================================================================

    def test_04_asset_and_sensor_registry(self):
        """Validates asset registration, nameplate data, and associated sensor catalog."""
        self.assertIn("ASSET-INV-01", self.app.assets)
        inv = self.app.assets["ASSET-INV-01"]
        self.assertEqual(inv.rated_power_kw, 2500.0)
        self.assertEqual(inv.status, AssetStatus.ACTIVE)

        # Check registered sensors
        sensors_for_inv = [s for s in self.app.sensors.values() if s.asset_id == "ASSET-INV-01"]
        self.assertGreaterEqual(len(sensors_for_inv), 5)
        types = {s.measurement_type for s in sensors_for_inv}
        self.assertIn("POA_IRRADIANCE", types)
        self.assertIn("HEATSINK_TEMP", types)
        self.assertIn("AC_POWER", types)

    # =========================================================================
    # 4. Telemetry Ingestion, SQLite Storage & Cryptographic Verification
    # =========================================================================

    def test_05_telemetry_packet_signing_and_ingestion(self):
        """Validates edge HMAC signing, timestamp verification, and SQLite storage."""
        token = self.api.authenticate("device-gateway", SecurityRole.SYSTEM_SERVICE)
        asset_id = "ASSET-INV-01"
        secret = self.app.device_secrets[asset_id]

        telemetry = {
            "poa_irradiance": 850.0,
            "ambient_temp": 28.0,
            "dc_power_kw": 2100.0,
            "ac_power_kw": 2040.0,
            "heatsink_temp": 48.0,
        }
        payload_str = json.dumps(telemetry, sort_keys=True)
        sig = self.app.auth_manager.sign_telemetry_packet(
            device_id="GATEWAY-01",
            device_secret=secret,
            payload_str=payload_str,
        )

        result = self.api.ingest_telemetry(
            asset_id=asset_id,
            telemetry_data=telemetry,
            packet_signature=sig,
            auth_token=token,
        )
        self.assertEqual(result["stage"], "COMPLETE")
        self.assertEqual(result["measured_power_kw"], 2040.0)
        self.assertGreater(result["performance_ratio"], 0.90)
        self.assertGreater(result["composite_health_index"], 90.0)

        # Verify buffered in SQLite
        unacked = self.app.edge_buffer.get_unacknowledged_batch(limit=10)
        self.assertGreaterEqual(len(unacked), 5)

    def test_06_telemetry_invalid_hmac_rejected(self):
        """Verifies that telemetry with an illegitimate signature is rejected."""
        token = self.api.authenticate("device-gateway", SecurityRole.SYSTEM_SERVICE)
        asset_id = "ASSET-INV-01"

        telemetry = {"poa_irradiance": 850.0, "heatsink_temp": 48.0}
        payload_str = json.dumps(telemetry, sort_keys=True)
        bad_sig = self.app.auth_manager.sign_telemetry_packet(
            device_id="GATEWAY-01",
            device_secret="wrong-illegitimate-secret-key",
            payload_str=payload_str,
        )

        with self.assertRaises(PermissionError):
            self.api.ingest_telemetry(
                asset_id=asset_id,
                telemetry_data=telemetry,
                packet_signature=bad_sig,
                auth_token=token,
            )

    # =========================================================================
    # 5. Deterministic Health & Multi-Level Anomaly Integration
    # =========================================================================

    def test_07_thermal_overheating_health_derating_and_anomaly(self):
        """
        Validates that acute heatsink temperature spike triggers:
        1. First-principles residual detection in digital twin
        2. Non-linear health index derating
        3. Multi-level anomaly detection
        4. Real-time alert creation
        """
        token = self.api.authenticate("ops-user", SecurityRole.OPERATOR)
        asset_id = "ASSET-INV-01"

        fault_telemetry = {
            "poa_irradiance": 900.0,
            "ambient_temp": 30.0,
            "dc_power_kw": 2200.0,
            "ac_power_kw": 1800.0,
            "heatsink_temp": 87.0,  # Critical overheating
        }

        res = self.api.ingest_telemetry(
            asset_id=asset_id,
            telemetry_data=fault_telemetry,
            auth_token=token,
        )

        # Health derated from 100
        self.assertLess(res["composite_health_index"], 88.0)
        self.assertGreater(res["temperature_residual_c"], 20.0)
        self.assertGreaterEqual(res["anomalies_detected"], 1)
        self.assertGreaterEqual(len(res["dispatched_alerts"]), 1)
        self.assertIsNotNone(res["work_order"])
        self.assertEqual(res["work_order_status"], WorkOrderStatus.PENDING_HITL_APPROVAL.value)

    # =========================================================================
    # 6. Real-Time Alerting Engine & Deduplication
    # =========================================================================

    def test_08_alert_lifecycle_and_deduplication(self):
        """Verifies alert creation, deduplication against redundant flood, ack and resolve."""
        token = self.api.authenticate("ops-user", SecurityRole.OPERATOR)
        asset_id = "ASSET-INV-01"

        telemetry = {"poa_irradiance": 900.0, "heatsink_temp": 88.0, "ac_power_kw": 2091.15, "dc_power_kw": 2125.0}

        # Ingest twice
        self.api.ingest_telemetry(asset_id, telemetry, auth_token=token)
        self.api.ingest_telemetry(asset_id, telemetry, auth_token=token)

        alerts = self.api.get_alerts(site_id="SITE-MOJAVE-01", auth_token=token)
        active_alerts = [a for a in alerts if a["status"] == AlertStatus.ACTIVE.value]

        # Deduplication ensures we don't duplicate active alerts for same asset & condition
        self.assertEqual(len(active_alerts), 1)
        alert_id = active_alerts[0]["alert_id"]

        # Acknowledge alert
        ack_res = self.api.acknowledge_alert(alert_id=alert_id, auth_token=token)
        self.assertEqual(ack_res["status"], AlertStatus.ACKNOWLEDGED.value)
        self.assertEqual(ack_res["acknowledged_by"], "ops-user")

        # Resolve alert
        resolve_res = self.api.resolve_alert(alert_id=alert_id, auth_token=token)
        self.assertEqual(resolve_res["status"], AlertStatus.RESOLVED.value)

    # =========================================================================
    # 7. CMMS Maintenance & Strict HITL Safety Gating
    # =========================================================================

    def test_09_hitl_safety_gating_blocks_unauthorized_dispatch(self):
        """
        NON-NEGOTIABLE SAFETY GATE:
        Automated predictive maintenance work orders MUST start in PENDING_HITL_APPROVAL.
        Dispatch attempts before human sign-off MUST raise PermissionError.
        """
        token = self.api.authenticate("engineer-hitl", SecurityRole.CHIEF_ENGINEER)
        asset_id = "ASSET-INV-01"

        telemetry = {"poa_irradiance": 910.0, "heatsink_temp": 89.0, "ac_power_kw": 1750.0, "dc_power_kw": 2250.0}
        res = self.api.ingest_telemetry(asset_id, telemetry, auth_token=token)
        wo_id = res["work_order"]

        wo = self.app.cmms_engine.get_work_order(wo_id)
        self.assertEqual(wo.status, WorkOrderStatus.PENDING_HITL_APPROVAL)

        # 1. Attempt dispatch WITHOUT approval -> MUST fail
        with self.assertRaises(PermissionError):
            self.app.dispatch_work_order(work_order_id=wo_id, technician_id="TECH-001")

        # 2. Human approval
        approved_wo = self.api.approve_work_order(
            work_order_id=wo_id,
            auth_token=token,
            notes="Chief engineer verified thermal anomaly. Authorized repair.",
        )
        self.assertEqual(approved_wo["status"], WorkOrderStatus.APPROVED.value)
        self.assertEqual(approved_wo["hitl_approval"]["approved_by"], "engineer-hitl")

        # 3. Reserve parts & Dispatch
        self.api.reserve_parts(work_order_id=wo_id, auth_token=token)
        dispatched_wo = self.api.dispatch_work_order(work_order_id=wo_id, technician_id="TECH-001", auth_token=token)
        self.assertEqual(dispatched_wo["status"], WorkOrderStatus.DISPATCHED.value)

        # 4. Complete & Close
        completed_wo = self.api.complete_work_order(work_order_id=wo_id, auth_token=token, labor_hours=2.0)
        self.assertEqual(completed_wo["status"], WorkOrderStatus.COMPLETED.value)

        closed_wo = self.api.close_work_order(work_order_id=wo_id, auth_token=token)
        self.assertEqual(closed_wo["status"], WorkOrderStatus.CLOSED.value)

    # =========================================================================
    # 8. Unified SCADA Dashboard State Aggregator
    # =========================================================================

    def test_10_unified_dashboard_aggregation(self):
        """Verifies that get_unified_dashboard aggregates generation, health, alerts, and assets."""
        token = self.api.authenticate("operator-dan", SecurityRole.OPERATOR)

        # Ingest baseline reading
        self.api.ingest_telemetry(
            asset_id="ASSET-INV-01",
            telemetry_data={"ac_power_kw": 2100.0, "heatsink_temp": 45.0, "poa_irradiance": 800.0},
            auth_token=token,
        )

        dash = self.api.get_unified_dashboard(site_id="SITE-MOJAVE-01", auth_token=token)
        self.assertEqual(dash["site_id"], "SITE-MOJAVE-01")
        self.assertEqual(dash["total_generation_mw"], 2.1)
        self.assertEqual(dash["rated_capacity_mw"], 50.0)
        self.assertGreater(dash["site_health_index"], 90.0)
        self.assertIn("ASSET-INV-01", dash["assets_summary"])
        self.assertEqual(dash["assets_summary"]["ASSET-INV-01"]["power_kw"], 2100.0)

    # =========================================================================
    # 9. Executive Operational & Financial Governance Report
    # =========================================================================

    def test_11_executive_report_generation(self):
        """Verifies calculation of financial loss attribution, avoided costs, and audit integrity."""
        token = self.api.authenticate("executive-vp", SecurityRole.SECURITY_ADMIN)

        report = self.api.get_executive_report(site_id="SITE-MOJAVE-01", auth_token=token)
        self.assertEqual(report["site_id"], "SITE-MOJAVE-01")
        self.assertGreaterEqual(report["total_generation_mwh"], 0.0)
        self.assertGreater(report["total_revenue_loss_usd"], 0.0)
        self.assertGreater(report["avoided_downtime_savings_usd"], 0.0)
        self.assertTrue(report["audit_chain_valid"])

    # =========================================================================
    # 10. Tamper-Evident SHA-256 Audit Trail Verification
    # =========================================================================

    def test_12_audit_chain_integrity_and_tamper_detection(self):
        """Verifies that cryptographic hash chaining catches unauthorized entry modifications."""
        token = self.api.authenticate("sec-auditor", SecurityRole.SECURITY_ADMIN)

        # Verify initial intact chain
        status = self.api.verify_audit_trail(auth_token=token)
        self.assertTrue(status["is_valid"])
        self.assertGreater(status["total_entries"], 0)
        self.assertIsNone(status["broken_entry_index"])

        # Simulate malicious retroactive tampering in the audit log
        chain = self.app.audit_logger._chain
        corrupt_idx = len(chain) // 2
        original_details = copy.deepcopy(chain[corrupt_idx].details)
        chain[corrupt_idx].details["unauthorized_edit"] = True

        # Check that verification detects the break
        valid, broken_idx = self.app.audit_logger.verify_chain_integrity()
        self.assertFalse(valid)
        self.assertEqual(broken_idx, corrupt_idx)

        # Restore and verify chain validity returns
        chain[corrupt_idx].details = original_details
        valid_restored, _ = self.app.audit_logger.verify_chain_integrity()
        self.assertTrue(valid_restored)

    # =========================================================================
    # 11. Unbroken 10-Stage Pipeline End-to-End Demonstration
    # =========================================================================

    def test_13_unbroken_10_stage_integration_pipeline(self):
        """
        Validates complete operational flow across all 10 stages:
        Sensor -> Gateway -> Ingestion -> Storage -> Analytics -> Health -> Anomaly -> Alert -> Maintenance -> Report
        """
        token = self.api.authenticate("lead-architect", SecurityRole.CHIEF_ENGINEER)
        asset_id = "ASSET-INV-01"
        secret = self.app.device_secrets[asset_id]

        # Stages 1-2: Sensor readings packaged by Edge Gateway
        sensor_packet = {
            "poa_irradiance": 950.0,
            "ambient_temp": 34.0,
            "dc_power_kw": 2400.0,
            "ac_power_kw": 1900.0,
            "heatsink_temp": 88.5,
        }

        # Stage 3: Ingestion & Gateway HMAC signing
        payload_str = json.dumps(sensor_packet, sort_keys=True)
        sig = self.app.auth_manager.sign_telemetry_packet(
            device_id="GATEWAY-MOJAVE-01",
            device_secret=secret,
            payload_str=payload_str,
        )

        # Stages 4-10: Ingestion, Storage, Digital Twin Analytics, Health, Anomaly, Alert, Maintenance, Governance
        result = self.api.ingest_telemetry(
            asset_id=asset_id,
            telemetry_data=sensor_packet,
            packet_signature=sig,
            auth_token=token,
        )

        # Assertions on pipeline outcomes
        self.assertEqual(result["stage"], "COMPLETE")
        self.assertGreater(result["temperature_residual_c"], 30.0)  # Stage 5 (Physics Twin)
        self.assertLess(result["composite_health_index"], 85.0)     # Stage 6 (Health)
        self.assertGreaterEqual(result["anomalies_detected"], 1)     # Stage 7 (Anomaly)
        self.assertGreaterEqual(len(result["dispatched_alerts"]), 1) # Stage 8 (Alert)
        self.assertIsNotNone(result["work_order"])                   # Stage 9 (CMMS)
        self.assertEqual(result["work_order_status"], WorkOrderStatus.PENDING_HITL_APPROVAL.value)
        self.assertTrue(result["audit_chain_valid"])                # Stage 10 (Governance)

        # Validate Executive Report reflects the integrated pipeline results
        exec_report = self.api.get_executive_report(site_id="SITE-MOJAVE-01", auth_token=token)
        self.assertTrue(exec_report["audit_chain_valid"])
        self.assertGreaterEqual(exec_report["critical_incidents_count"], 1)


if __name__ == "__main__":
    unittest.main()
