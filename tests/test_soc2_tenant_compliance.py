"""
Unit and integration tests for REAMP SOC 2 Type II Tenant Separation Compliance.
Covers:
- AICPA SOC 2 Trust Services Criteria CC6.1, CC6.3, CC6.6, CC6.7, CC7.2, PI1.1
- Cross-tenant boundary enforcement and fallback elimination
- Role-based least privilege mutation gating (Viewer vs Operator vs Chief Engineer)
- Tamper-evident SHA-256 audit ledger logging for boundary infractions
- Zero em dash rule enforcement and British English consistency
"""

import unittest
from reamp.mvp import REAMPApplicationMVP
from reamp.security.soc2_audit import SOC2ComplianceAuditor, SOC2AuditReport
from reamp.security.models import SecurityRole
from web_server import GLOBAL_STATE, dispatch_api_request


class TestSOC2TenantCompliance(unittest.TestCase):
    """Test suite validating platform-wide SOC 2 Type II multi-tenant compliance."""

    def setUp(self) -> None:
        self.state = GLOBAL_STATE

    def test_soc2_compliance_auditor_all_controls_pass(self) -> None:
        """Verify automated SOC 2 compliance scanner evaluates and passes all controls at 100%."""
        auditor = SOC2ComplianceAuditor(self.state)
        report: SOC2AuditReport = auditor.audit_platform()

        self.assertTrue(report.is_compliant, f"SOC 2 audit failed with deficiencies: {report.deficiencies}")
        self.assertEqual(report.compliance_score_pct, 100.0)
        self.assertEqual(report.controls_evaluated, 6)
        self.assertEqual(report.controls_passed, 6)
        self.assertEqual(len(report.deficiencies), 0)

        control_ids = {r.control_id for r in report.control_results}
        expected_controls = {"CC6.1-A", "CC6.3-A", "CC6.6-A", "CC6.7-A", "CC7.2-A", "PI1.1-A"}
        self.assertEqual(control_ids, expected_controls)

        for result in report.control_results:
            self.assertTrue(result.passed, f"Control {result.control_id} failed: {result.evidence}")
            self.assertTrue(len(result.evidence) > 0)

    def test_soc2_cc6_1_asset_detail_isolation_no_fallback(self) -> None:
        """Verify CC6.1: Querying a foreign asset returns 404 with zero cross-tenant fallback leakage."""
        # Query Aurora asset under Helios tenant partition
        code, res = self.state.get_asset_detail_data("TURB-FJORD-01", "ORG-HELIOS-GLOBAL")
        self.assertEqual(code, 404)
        self.assertIn("not found in tenant partition 'ORG-HELIOS-GLOBAL'", res.get("error", ""))

        # Query valid Helios asset under Helios tenant partition
        helios_app = self.state.get_tenant_app("ORG-HELIOS-GLOBAL")
        valid_helios_asset = list(helios_app.assets.keys())[0]
        code2, res2 = self.state.get_asset_detail_data(valid_helios_asset, "ORG-HELIOS-GLOBAL")
        self.assertEqual(code2, 200)
        self.assertEqual(res2["asset_id"], valid_helios_asset)

    def test_soc2_cc6_6_telemetry_foreign_asset_injection_blocked(self) -> None:
        """Verify CC6.6: Telemetry injection for a foreign asset is strictly rejected at the edge."""
        # Attempt to inject Aurora asset telemetry into Helios partition
        res = self.state.inject_telemetry(
            {"asset_id": "TURB-FJORD-01", "scenario": "nominal"},
            tenant_id="ORG-HELIOS-GLOBAL"
        )
        self.assertEqual(res.get("status"), "ERROR")
        self.assertIn("does not belong to tenant partition", res.get("message", ""))

        # Dispatch via API router
        code, api_res = dispatch_api_request(
            "POST",
            "/api/telemetry/inject",
            {"asset_id": "TURB-FJORD-01", "scenario": "nominal"},
            headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"}
        )
        self.assertEqual(code, 400)
        self.assertEqual(api_res.get("status"), "ERROR")

    def test_soc2_cc6_3_rbac_viewer_denied_mutations(self) -> None:
        """Verify CC6.3: Viewer role is denied all state mutation actions (least privilege)."""
        viewer = next(
            u for u in self.state.onboarding.users.values()
            if u.tenant_id == "ORG-HELIOS-GLOBAL" and u.role == SecurityRole.VIEWER
        )
        headers = {"authorization": f"Bearer {viewer.token}"}

        # 1. Alert acknowledgement
        code, res = dispatch_api_request("POST", "/api/alerts/acknowledge", {"alert_id": "ALT-INV-01"}, headers=headers)
        self.assertEqual(code, 403)
        self.assertEqual(res.get("status"), "ERROR")
        self.assertIn("Viewers cannot acknowledge alerts", res.get("message", ""))

        # 2. Work order approval
        code, res = dispatch_api_request("POST", "/api/work-orders/approve", {"work_order_id": "WO-001"}, headers=headers)
        self.assertEqual(code, 403)
        self.assertEqual(res.get("status"), "ERROR")
        self.assertIn("Chief Engineer authority", res.get("message", ""))

        # 3. Adaptation proposal
        code, res = dispatch_api_request("POST", "/api/adaptations/propose", {"shift_pct": -10.0}, headers=headers)
        self.assertEqual(code, 403)
        self.assertEqual(res.get("status"), "ERROR")

    def test_soc2_cc6_3_operator_restricted_from_chief_engineer_approvals(self) -> None:
        """Verify CC6.3: Operator can acknowledge alerts but cannot approve work orders or adaptations."""
        operator = next(
            u for u in self.state.onboarding.users.values()
            if u.tenant_id == "ORG-HELIOS-GLOBAL" and u.role == SecurityRole.OPERATOR
        )
        headers = {"authorization": f"Bearer {operator.token}"}

        # Work order approval denied to Operator
        code, res = dispatch_api_request("POST", "/api/work-orders/approve", {"work_order_id": "WO-001"}, headers=headers)
        self.assertEqual(code, 403)
        self.assertIn("Chief Engineer authority", res.get("message", ""))

        # Adaptation approval denied to Operator
        code, res = dispatch_api_request("POST", "/api/adaptations/approve", {"action_id": "ACT-001"}, headers=headers)
        self.assertEqual(code, 403)
        self.assertIn("Chief Engineer authority", res.get("message", ""))

    def test_soc2_cc7_2_tamper_evident_security_boundary_logging(self) -> None:
        """Verify CC7.2: Security boundary violations immutably log to SHA-256 audit ledger."""
        operator = next(
            u for u in self.state.onboarding.users.values()
            if u.tenant_id == "ORG-HELIOS-GLOBAL" and u.role == SecurityRole.OPERATOR
        )
        aurora_user = next(
            u for u in self.state.onboarding.users.values()
            if u.tenant_id == "ORG-AURORA-NORDIC"
        )
        headers = {"authorization": f"Bearer {operator.token}"}

        # Attempt cross-tenant user modification
        code, res = dispatch_api_request(
            "POST",
            "/api/users/toggle-status",
            {"user_id": aurora_user.user_id},
            headers=headers
        )
        self.assertEqual(code, 403)

        app = self.state.get_tenant_app("ORG-HELIOS-GLOBAL")
        last_entry = app.audit_logger._chain[-1]
        self.assertEqual(last_entry.action, "SECURITY_BOUNDARY_VIOLATION")
        self.assertEqual(last_entry.actor_id, operator.email)
        self.assertEqual(last_entry.outcome, "DENIED")

        is_valid, _ = app.audit_logger.verify_chain_integrity()
        self.assertTrue(is_valid)

    def test_soc2_endpoint_get_audit(self) -> None:
        """Verify GET /api/soc2/audit serves complete, compliant SOC 2 report in JSON."""
        code, report_dict = dispatch_api_request("GET", "/api/soc2/audit")
        self.assertEqual(code, 200)
        self.assertTrue(report_dict["is_compliant"])
        self.assertEqual(report_dict["compliance_score_pct"], 100.0)
        self.assertEqual(report_dict["controls_evaluated"], 6)
        self.assertEqual(report_dict["controls_passed"], 6)
        self.assertIsInstance(report_dict["control_results"], list)
        self.assertEqual(len(report_dict["control_results"]), 6)

    def test_zero_em_dashes_enforcement(self) -> None:
        """Enforce strict Zero Em Dash policy across SOC 2 compliance code."""
        import os
        files_to_check = [
            "reamp/security/soc2_audit.py",
            "web_server.py",
        ]
        for fpath in files_to_check:
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.assertNotIn("\u2014", content, f"Found forbidden em dash in {fpath}")

    def test_british_english_consistency(self) -> None:
        """Enforce British English spelling in SOC 2 compliance module strings."""
        with open("reamp/security/soc2_audit.py", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertNotIn("authorization.", content.lower())
            self.assertNotIn("authorized.", content.lower())


if __name__ == "__main__":
    unittest.main()
