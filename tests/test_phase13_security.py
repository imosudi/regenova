"""
REAMP Phase 13 Automated Verification Suite — Cybersecurity and Trust Framework.
Validates:
1. Device telemetry HMAC signing, payload integrity, and anti-replay nonce protection.
2. Multi-tenant isolation (ABAC) and role-based capability enforcement (RBAC).
3. Denial-of-Service (DoS) mitigation via token-bucket rate limiting.
4. Tamper-evident hash-chained audit logging and mathematical verification.
5. Automated Interface Security Review across all implemented REAMP components (Quality Gate).
"""

import os
import sys
import unittest
import datetime
import time

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.security.models import (
    SecurityRole,
    Permission,
    UserIdentity,
    SecurityToken,
    AuditLogEntry,
)
from reamp.security.auth import (
    AuthenticationManager,
    AuthorizationManager,
)
from reamp.security.audit import (
    TamperEvidentAuditLogger,
)
from reamp.security.review import (
    InterfaceSecurityReviewer,
    SecurityReviewReport,
)


class TestPhase13CybersecurityFramework(unittest.TestCase):
    """Test suite validating Phase 13 Cybersecurity and Trust Framework."""

    def setUp(self):
        """Initializes security managers and test identities."""
        self.auth_mgr = AuthenticationManager(
            master_secret="reamp-test-secure-master-secret-key-32b",
            token_ttl_seconds=3600,
            max_clock_skew_seconds=30.0,
            rate_limit_per_second=20.0,
            burst_capacity=10,
        )
        self.audit_logger = TamperEvidentAuditLogger()
        self.reviewer = InterfaceSecurityReviewer(self.auth_mgr, self.audit_logger)

        # Reference Users
        self.user_viewer_t1 = UserIdentity(
            user_id="USR-VIEW-01",
            username="viewer_bob",
            tenant_id="TENANT-ALPHA",
            role=SecurityRole.VIEWER,
        )
        self.user_engineer_t1 = UserIdentity(
            user_id="USR-ENG-01",
            username="lead_sarah",
            tenant_id="TENANT-ALPHA",
            role=SecurityRole.CHIEF_ENGINEER,
        )
        self.user_operator_t2 = UserIdentity(
            user_id="USR-OP-02",
            username="operator_t2",
            tenant_id="TENANT-BETA",
            role=SecurityRole.OPERATOR,
        )

    def test_01_authentication_and_anti_replay(self):
        """
        Validates HMAC token issuance/verification and anti-replay defenses:
        - Fresh packets with valid HMAC pass verification
        - Duplicate nonces trigger 'Replay Attack Detected'
        - Stale timestamps trigger 'Packet Freshness Breach'
        - Tampered payloads fail SHA-256 integrity checks
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        device_id = "EDGE-GW-SOLAR-01"
        device_secret = "dev-secret-key-alpha-99881122"
        payload = '{"power_ac_kw": 482.5, "temperature_heatsink_c": 58.2}'

        # 1. Sign valid telemetry packet
        sig_packet = self.auth_mgr.sign_telemetry_packet(
            device_id=device_id,
            device_secret=device_secret,
            payload_str=payload,
            timestamp=now.isoformat(),
            nonce="nonce-unique-001",
        )

        # 2. Verify valid packet -> MUST succeed
        verified = self.auth_mgr.verify_telemetry_packet(
            packet_sig=sig_packet,
            device_secret=device_secret,
            payload_str=payload,
            current_time=now,
        )
        self.assertTrue(verified)

        # 3. Attempt Replay Attack with identical nonce -> MUST raise ValueError
        with self.assertRaises(ValueError) as ctx:
            self.auth_mgr.verify_telemetry_packet(
                packet_sig=sig_packet,
                device_secret=device_secret,
                payload_str=payload,
                current_time=now,
            )
        self.assertIn("Replay Attack Detected", str(ctx.exception))

        # 4. Attempt Stale Packet (> 30s in the past) -> MUST raise ValueError
        stale_time = (now - datetime.timedelta(seconds=45)).isoformat()
        stale_sig = self.auth_mgr.sign_telemetry_packet(
            device_id=device_id,
            device_secret=device_secret,
            payload_str=payload,
            timestamp=stale_time,
            nonce="nonce-unique-002",
        )
        with self.assertRaises(ValueError) as ctx:
            self.auth_mgr.verify_telemetry_packet(
                packet_sig=stale_sig,
                device_secret=device_secret,
                payload_str=payload,
                current_time=now,
            )
        self.assertIn("Packet Freshness Breach", str(ctx.exception))

        # 5. Payload Tampering (Adversary modifies power from 482.5 to 0.0) -> MUST fail
        tampered_payload = '{"power_ac_kw": 0.0, "temperature_heatsink_c": 58.2}'
        fresh_sig = self.auth_mgr.sign_telemetry_packet(
            device_id=device_id,
            device_secret=device_secret,
            payload_str=payload,
            timestamp=now.isoformat(),
            nonce="nonce-unique-003",
        )
        with self.assertRaises(ValueError) as ctx:
            self.auth_mgr.verify_telemetry_packet(
                packet_sig=fresh_sig,
                device_secret=device_secret,
                payload_str=tampered_payload,
                current_time=now,
            )
        self.assertIn("Payload Tampering Detected", str(ctx.exception))

    def test_02_multi_tenant_isolation_and_rbac(self):
        """
        Validates multi-tenant boundaries (ABAC) and role capability gating (RBAC).
        """
        # 1. Multi-Tenant Violation: User from TENANT-ALPHA accessing TENANT-BETA resource
        with self.assertRaises(PermissionError) as ctx:
            AuthorizationManager.authorize(
                actor=self.user_engineer_t1,
                required_permission=Permission.APPROVE_HITL,
                target_tenant_id="TENANT-BETA",  # Cross-tenant violation
            )
        self.assertIn("Multi-Tenant Isolation Violation", str(ctx.exception))

        # 2. RBAC Privilege Escalation Check: VIEWER attempting to approve HITL work order
        with self.assertRaises(PermissionError) as ctx:
            AuthorizationManager.authorize(
                actor=self.user_viewer_t1,
                required_permission=Permission.APPROVE_HITL,
                target_tenant_id="TENANT-ALPHA",
            )
        self.assertIn("Access Denied", str(ctx.exception))
        self.assertIn("lacks mandatory permission 'APPROVE_HITL'", str(ctx.exception))

        # 3. Legitimate Authorization: CHIEF_ENGINEER in TENANT-ALPHA approving work order
        allowed = AuthorizationManager.authorize(
            actor=self.user_engineer_t1,
            required_permission=Permission.APPROVE_HITL,
            target_tenant_id="TENANT-ALPHA",
        )
        self.assertTrue(allowed)

    def test_03_denial_of_service_rate_limiting(self):
        """
        Validates token-bucket rate limiting against volumetric request bursts.
        """
        client_id = "CLIENT-IP-192.168.1.100"

        # Allowed within burst capacity (10 tokens)
        allowed_count = 0
        for _ in range(10):
            if self.auth_mgr.check_rate_limit(client_id, current_time_epoch=1000.0):
                allowed_count += 1
        self.assertEqual(allowed_count, 10)

        # 11th consecutive immediate request must be rejected (rate limited)
        rejected = self.auth_mgr.check_rate_limit(client_id, current_time_epoch=1000.0)
        self.assertFalse(rejected)

        # After 0.5s elapsed, tokens refill (rate is 20/s, so 10 tokens refilled)
        refilled = self.auth_mgr.check_rate_limit(client_id, current_time_epoch=1000.5)
        self.assertTrue(refilled)

    def test_04_tamper_evident_hash_chained_audit_logger(self):
        """
        Validates append-only cryptographic hash chaining and tampering detection:
        - Verifies that an uncorrupted chain passes integrity check
        - Verifies that modifying any historical entry invalidates the chain
        """
        # Append series of audit entries
        self.audit_logger.append_entry(
            actor_id="USR-ENG-01",
            tenant_id="TENANT-ALPHA",
            action="APPROVE_WORK_ORDER",
            resource_id="WO-2026-0042",
            outcome="SUCCESS",
            details={"priority": "P2_HIGH", "technician": "Alice Morgan"},
        )
        self.audit_logger.append_entry(
            actor_id="USR-ENG-01",
            tenant_id="TENANT-ALPHA",
            action="DISPATCH_TECHNICIAN",
            resource_id="WO-2026-0042",
            outcome="SUCCESS",
            details={"technician_id": "TECH-001"},
        )
        self.audit_logger.append_entry(
            actor_id="SYS-DAEMON",
            tenant_id="TENANT-ALPHA",
            action="EXECUTE_PHYSICS_RESIDUAL_SCAN",
            resource_id="INV-WEST-01",
            outcome="SUCCESS",
            details={"residuals": {"power": -14.2, "temp": 5.1}},
        )

        # 1. Verify uncorrupted chain -> MUST pass
        is_intact, corrupted_idx = self.audit_logger.verify_chain_integrity()
        self.assertTrue(is_intact)
        self.assertIsNone(corrupted_idx)

        # 2. Adversary maliciously modifies the first entry's action
        entries = self.audit_logger.get_entries()
        self.assertEqual(len(entries), 3)

        # Tamper directly with the first record in-place
        self.audit_logger._chain[0].action = "REJECT_WORK_ORDER"  # Altered!

        # 3. Verify tampered chain -> MUST detect tampering at index 0
        is_intact_after, corrupted_idx_after = self.audit_logger.verify_chain_integrity()
        self.assertFalse(is_intact_after)
        self.assertEqual(corrupted_idx_after, 0)

    def test_05_quality_gate_interface_security_review(self):
        """
        Quality Gate Test:
        "Perform a security review of all implemented interfaces.
         Do not claim the system is secure merely because authentication exists."
        Executes automated security scan across all 6 core REAMP subsystems.
        """
        report: SecurityReviewReport = self.reviewer.perform_security_review()

        # Check completeness of the review
        self.assertEqual(report.total_interfaces_reviewed, 6)
        self.assertEqual(report.compliant_interfaces, 6)
        self.assertEqual(report.compliance_score_pct, 100.0)
        self.assertTrue(report.is_passing)
        self.assertEqual(len(report.vulnerabilities_identified), 0)

        # Validate that each interface satisfies all 5 defense-in-depth controls
        for res in report.interface_results:
            self.assertTrue(res.auth_enforced, f"{res.interface_name} missing auth enforcement")
            self.assertTrue(res.tenant_isolated, f"{res.interface_name} missing tenant isolation")
            self.assertTrue(res.input_validation, f"{res.interface_name} missing input validation")
            self.assertTrue(res.replay_mitigated, f"{res.interface_name} missing anti-replay")
            self.assertTrue(res.audit_logged, f"{res.interface_name} missing audit logging")
            self.assertTrue(res.is_fully_compliant)

        # Print audit summary for report evidence
        print("\n================================================================")
        print("PHASE 13 SECURITY AUDIT REPORT (QUALITY GATE EVALUATION):")
        print(f"  Interfaces Evaluated: {report.total_interfaces_reviewed}")
        print(f"  Compliant Interfaces: {report.compliant_interfaces}")
        print(f"  Compliance Score:     {report.compliance_score_pct}%")
        print(f"  Status:               {'PASSED' if report.is_passing else 'FAILED'}")
        print("================================================================\n")


if __name__ == "__main__":
    unittest.main()
