"""
Automated unit tests for REGENOVA user, facility, and device onboarding.
"""

import unittest
from reamp.mvp import REAMPApplicationMVP
from reamp.security.models import SecurityRole
from reamp.mvp.models import TechnologyType
from reamp.onboarding import (
    OnboardingManager,
    FacilityOnboardingRequest,
    DeviceOnboardingRequest,
)


class TestOnboardingManager(unittest.TestCase):
    def setUp(self):
        self.app = REAMPApplicationMVP(
            tenant_id="ORG-TEST-ONBOARD",
            storage_db=":memory:",
            master_secret="test-secret-32-bytes-long-key!",
        )
        self.app.initialize_default_topology()
        self.manager = OnboardingManager()

    def test_01_user_onboarding(self):
        user = self.manager.onboard_user(
            name="Elena Rostova",
            email="elena.rostova@helios.energy",
            role=SecurityRole.OPERATOR,
            tenant_id=self.app.tenant_id,
            actor_id="admin-01",
            audit_logger=self.app.audit_logger,
            auth_manager=self.app.auth_manager,
        )
        self.assertIsNotNone(user.user_id)
        self.assertEqual(user.name, "Elena Rostova")
        self.assertEqual(user.role, SecurityRole.OPERATOR)
        self.assertIn("READ_TELEMETRY", user.permissions)
        self.assertIn("DISPATCH_WORK_ORDER", user.permissions)
        self.assertEqual(self.manager.users[user.user_id].email, "elena.rostova@helios.energy")

        # Verify audit log recorded
        chain = self.app.audit_logger._chain
        self.assertTrue(any(e.action == "USER_ONBOARDED" and e.resource_id == user.user_id for e in chain))

    def test_02_facility_onboarding(self):
        req = FacilityOnboardingRequest(
            facility_id="SITE-SONORA-SOLAR",
            name="Sonora Desert PV Station",
            portfolio_id="PORT-SW-UTILITY",
            technology=TechnologyType.SOLAR_PV,
            latitude=31.8,
            longitude=-112.5,
            rated_capacity_mw=120.0,
        )
        res = self.manager.onboard_facility(self.app, req, actor_id="admin-01")
        self.assertEqual(res.status, "SUCCESS")
        self.assertIn("SITE-SONORA-SOLAR", self.app.sites)
        self.assertEqual(self.app.sites["SITE-SONORA-SOLAR"].rated_capacity_mw, 120.0)

        # Duplicate rejection
        res_dup = self.manager.onboard_facility(self.app, req, actor_id="admin-01")
        self.assertEqual(res_dup.status, "ERROR")

    def test_03_device_onboarding(self):
        # 1. Onboard Solar Inverter Device
        req_inv = DeviceOnboardingRequest(
            device_id="ASSET-INV-SONORA-01",
            facility_id="SITE-MOJAVE-01",
            name="Sonora Central Inverter 01",
            asset_type="INVERTER",
            model="Sungrow SG3125HV",
            rated_power_kw=3125.0,
            provision_digital_twin=True,
        )
        res_inv = self.manager.onboard_device(self.app, req_inv, actor_id="admin-01")
        self.assertEqual(res_inv.status, "SUCCESS")
        self.assertIn("ASSET-INV-SONORA-01", self.app.assets)
        self.assertIn("ASSET-INV-SONORA-01", self.app.twins)
        self.assertIn("ASSET-INV-SONORA-01", self.app.device_secrets)

        # 2. Ingest telemetry on newly onboarded device
        telemetry_res = self.app.process_telemetry_packet("ASSET-INV-SONORA-01", {
            "timestamp": "2026-09-11T12:00:00Z",
            "poa_irradiance": 900.0,
            "ambient_temp": 28.0,
            "dc_power_kw": 3000.0,
            "ac_power_kw": 2940.0,
            "heatsink_temp": 49.5,
        })
        self.assertGreater(telemetry_res["composite_health_index"], 85.0)

        # 3. Non-existent facility rejection
        req_bad = DeviceOnboardingRequest(
            device_id="ASSET-BAD",
            facility_id="SITE-DOES-NOT-EXIST",
            name="Bad Device",
            asset_type="INVERTER",
            model="X",
            rated_power_kw=100.0,
        )
        res_bad = self.manager.onboard_device(self.app, req_bad)
        self.assertEqual(res_bad.status, "ERROR")

    def test_04_user_listing(self):
        self.manager.onboard_user(
            name="Alice Wonder",
            email="alice@helios.energy",
            role=SecurityRole.VIEWER,
            tenant_id=self.app.tenant_id,
        )
        users = self.manager.list_users()
        self.assertGreaterEqual(len(users), 1)
        self.assertEqual(users[0]["email"], "alice@helios.energy")
        self.assertEqual(users[0]["role"], "VIEWER")


if __name__ == "__main__":

    unittest.main()
