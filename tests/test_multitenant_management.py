#!/usr/bin/env python3
"""
Tests for REGENOVA Multi-Tenant User Enrolment, Isolated Tenant Activities, and User Management.
Validates:
1. Tenant enrolment and organization registry.
2. User enrolment scoped to specific tenants.
3. Strict tenant activity isolation across Fleet Overview, Sites, Assets, and Audit Trail.
4. User management lifecycle: role updates, status toggles (ACTIVE/SUSPENDED), and HMAC token regeneration.
5. API dispatching with X-Tenant-ID header resolution.
"""

import unittest
import uuid
import datetime

from reamp.onboarding.models import TenantOnboardingRequest, TenantRecord, UserRecord
from reamp.onboarding.manager import OnboardingManager
from reamp.security.models import SecurityRole
from web_server import GLOBAL_STATE, dispatch_api_request


class TestMultiTenantManagement(unittest.TestCase):
    """Integration and unit tests for multi-tenant enrolment and user management."""

    def setUp(self):
        self.onboarding = OnboardingManager()
        self.state = GLOBAL_STATE

    def test_tenant_enrolment_and_listing(self):
        """Verify tenant registration and directory listing."""
        tenant_id = f"ORG-TEST-{uuid.uuid4().hex[:6].upper()}"
        req = TenantOnboardingRequest(
            tenant_id=tenant_id,
            name="Test Renewable Holdings",
            code="TESTHOLD",
            billing_tier="UTILITY",
            admin_name="Dr. Test User",
            admin_email="test@holdings.energy",
        )
        res = self.onboarding.onboard_tenant(req)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.entity_id, tenant_id)

        # Duplicate enrolment rejected
        res_dup = self.onboarding.onboard_tenant(req)
        self.assertEqual(res_dup.status, "ERROR")

        # Listing includes newly registered tenant
        tenants = self.onboarding.list_tenants()
        tenant_ids = [t["tenant_id"] for t in tenants]
        self.assertIn(tenant_id, tenant_ids)

    def test_multitenant_user_enrolment(self):
        """Verify user enrolment strictly binds users to distinct tenants."""
        t1 = f"ORG-A-{uuid.uuid4().hex[:4].upper()}"
        t2 = f"ORG-B-{uuid.uuid4().hex[:4].upper()}"
        self.onboarding.onboard_tenant(TenantOnboardingRequest(tenant_id=t1, name="Tenant A", code="TA"))
        self.onboarding.onboard_tenant(TenantOnboardingRequest(tenant_id=t2, name="Tenant B", code="TB"))

        u1 = self.onboarding.onboard_user("User Alpha", "alpha@a.energy", SecurityRole.OPERATOR, tenant_id=t1)
        u2 = self.onboarding.onboard_user("User Beta", "beta@b.energy", SecurityRole.VIEWER, tenant_id=t2)

        self.assertEqual(u1.tenant_id, t1)
        self.assertEqual(u2.tenant_id, t2)
        self.assertIn("READ_TELEMETRY", u1.permissions)
        self.assertIn("DISPATCH_WORK_ORDER", u1.permissions)

        # Filtered listing
        users_t1 = self.onboarding.list_users(tenant_id=t1)
        users_t2 = self.onboarding.list_users(tenant_id=t2)

        self.assertEqual(len(users_t1), 1)
        self.assertEqual(users_t1[0]["user_id"], u1.user_id)
        self.assertEqual(len(users_t2), 1)
        self.assertEqual(users_t2[0]["user_id"], u2.user_id)

    def test_isolated_tenant_activities(self):
        """Verify that querying data for Tenant A does NOT return Tenant B data."""
        helios_id = "ORG-HELIOS-GLOBAL"
        aurora_id = "ORG-AURORA-NORDIC"
        solaria_id = "ORG-SOLARIA-ESP"

        # 1. Overview Isolation
        overview_helios = self.state.get_overview_data(helios_id)
        overview_aurora = self.state.get_overview_data(aurora_id)
        overview_solaria = self.state.get_overview_data(solaria_id)

        self.assertEqual(overview_helios["tenant_id"], helios_id)
        self.assertEqual(overview_aurora["tenant_id"], aurora_id)
        self.assertEqual(overview_solaria["tenant_id"], solaria_id)

        # Helios capacity is 300 MW across 4 sites, Aurora is 160 MW across 2 sites, Solaria is 80 MW across 1 site
        self.assertEqual(overview_helios["total_capacity_mw"], 300.0)
        self.assertEqual(overview_aurora["total_capacity_mw"], 160.0)
        self.assertEqual(overview_solaria["total_capacity_mw"], 80.0)
        self.assertEqual(overview_aurora["total_sites"], 2)
        self.assertEqual(overview_solaria["total_sites"], 1)

        # 2. Sites Isolation
        sites_aurora = self.state.get_sites_data(aurora_id)
        site_names_aurora = [s["name"] for s in sites_aurora]
        self.assertIn("Fjord Coastal Wind Park", site_names_aurora)
        self.assertIn("Arctic Sub-Zero BESS Facility", site_names_aurora)
        # Ensure no Helios sites leak into Aurora
        for s in sites_aurora:
            self.assertNotIn("Mojave", s["name"])
            self.assertNotIn("North Sea", s["name"])

        # 3. Assets Isolation
        assets_aurora = self.state.get_assets_data(aurora_id)
        asset_ids_aurora = [a["asset_id"] for a in assets_aurora]
        self.assertIn("TURB-FJORD-01", asset_ids_aurora)
        self.assertIn("BESS-ARCTIC-01", asset_ids_aurora)
        self.assertNotIn("ASSET-INV-01", asset_ids_aurora)

        # 4. Audit Trail Isolation
        audit_aurora = self.state.get_audit_chain_data(aurora_id)
        self.assertEqual(audit_aurora["tenant_id"], aurora_id)
        for e in audit_aurora["recent_entries"]:
            self.assertEqual(e["tenant_id"], aurora_id)

    def test_user_management_role_update(self):
        """Verify updating user role refreshes permissions and records audit entry."""
        user = self.state.onboarding.onboard_user(
            name="Engineer Candidate",
            email=f"candidate_{uuid.uuid4().hex[:4]}@helios.energy",
            role=SecurityRole.VIEWER,
            tenant_id="ORG-HELIOS-GLOBAL",
        )
        self.assertEqual(user.role, SecurityRole.VIEWER)
        self.assertNotIn("APPROVE_HITL", user.permissions)

        # Promote to Chief Engineer
        updated = self.state.onboarding.update_user_role(
            user_id=user.user_id,
            new_role=SecurityRole.CHIEF_ENGINEER,
            actor_id="SEC_ADMIN_TEST",
            audit_logger=self.state.app.audit_logger,
        )
        self.assertEqual(updated.role, SecurityRole.CHIEF_ENGINEER)
        self.assertIn("APPROVE_HITL", updated.permissions)
        self.assertIn("MODIFY_CONFIG", updated.permissions)

        # Verify audit trail contains USER_ROLE_UPDATED
        chain = self.state.app.audit_logger._chain
        actions = [e.action for e in chain]
        self.assertIn("USER_ROLE_UPDATED", actions)

    def test_user_management_status_toggle(self):
        """Verify suspending and reactivating users."""
        user = self.state.onboarding.onboard_user(
            name="Temporary Operator",
            email=f"temp_{uuid.uuid4().hex[:4]}@helios.energy",
            role=SecurityRole.OPERATOR,
            tenant_id="ORG-HELIOS-GLOBAL",
        )
        self.assertEqual(user.status, "ACTIVE")

        # Suspend
        suspended = self.state.onboarding.update_user_status(
            user_id=user.user_id,
            status="SUSPENDED",
            actor_id="SEC_ADMIN_TEST",
            audit_logger=self.state.app.audit_logger,
        )
        self.assertEqual(suspended.status, "SUSPENDED")

        # Re-activate
        reactivated = self.state.onboarding.update_user_status(
            user_id=user.user_id,
            status="ACTIVE",
            actor_id="SEC_ADMIN_TEST",
            audit_logger=self.state.app.audit_logger,
        )
        self.assertEqual(reactivated.status, "ACTIVE")

        # Invalid status rejected
        with self.assertRaises(ValueError):
            self.state.onboarding.update_user_status(user.user_id, "INVALID_STATUS")

    def test_token_regeneration(self):
        """Verify HMAC token regeneration."""
        app = self.state.get_tenant_app("ORG-HELIOS-GLOBAL")
        user = self.state.onboarding.onboard_user(
            name="Token User",
            email=f"token_{uuid.uuid4().hex[:4]}@helios.energy",
            role=SecurityRole.OPERATOR,
            tenant_id="ORG-HELIOS-GLOBAL",
            auth_manager=app.auth_manager,
        )
        initial_token = user.token
        self.assertIsNotNone(initial_token)

        new_token = self.state.onboarding.regenerate_user_token(
            user_id=user.user_id,
            auth_manager=app.auth_manager,
            actor_id="SEC_ADMIN_TEST",
            audit_logger=app.audit_logger,
        )
        self.assertNotEqual(initial_token, new_token)
        self.assertEqual(user.token, new_token)

    def test_dispatch_api_request_with_tenant_header(self):
        """Verify that dispatch_api_request honors X-Tenant-ID header."""
        # 1. Overview for Aurora via header
        status_code, data = dispatch_api_request(
            method="GET",
            path="/api/overview",
            headers={"X-Tenant-ID": "ORG-AURORA-NORDIC"},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(data["tenant_id"], "ORG-AURORA-NORDIC")
        self.assertEqual(data["total_capacity_mw"], 160.0)

        # 2. Sites for Solaria via header
        status_code, data = dispatch_api_request(
            method="GET",
            path="/api/sites",
            headers={"X-Tenant-ID": "ORG-SOLARIA-ESP"},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Andalusia Solar Generation Hub")

        # 3. Tenants endpoint
        status_code, data = dispatch_api_request(method="GET", path="/api/tenants")
        self.assertEqual(status_code, 200)
        tenant_ids = [t["tenant_id"] for t in data["tenants"]]
        self.assertIn("ORG-HELIOS-GLOBAL", tenant_ids)
        self.assertIn("ORG-AURORA-NORDIC", tenant_ids)
        self.assertIn("ORG-SOLARIA-ESP", tenant_ids)


if __name__ == "__main__":
    unittest.main()
