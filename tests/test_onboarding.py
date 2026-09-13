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

    def test_05_facility_site_id_fixed_prefix(self):
        """Verify site ID Code has fixed prefix based on tenant partition ID."""
        # 1. Prefix derivation
        self.assertEqual(OnboardingManager.derive_facility_prefix("ORG-HELIOS-GLOBAL"), "SITE-HELIOS-")
        self.assertEqual(OnboardingManager.derive_facility_prefix("ORG-AURORA-NORDIC"), "SITE-AURORA-")
        self.assertEqual(OnboardingManager.derive_facility_prefix("ORG-SOLARIA-ESP"), "SITE-SOLARIA-")
        self.assertEqual(OnboardingManager.derive_facility_prefix("ORG-CUSTOM-TENANT", "CUST"), "SITE-CUST-")

        # 2. Suffix auto-prefixing
        prefixed = OnboardingManager.validate_or_apply_facility_prefix("ATACAMA-03", "ORG-HELIOS-GLOBAL")
        self.assertEqual(prefixed, "SITE-HELIOS-ATACAMA-03")

        # 3. Valid prefix preserved
        valid = OnboardingManager.validate_or_apply_facility_prefix("SITE-HELIOS-ATACAMA-03", "ORG-HELIOS-GLOBAL")
        self.assertEqual(valid, "SITE-HELIOS-ATACAMA-03")

        # 4. Repeated prefix deduplication
        deduped = OnboardingManager.validate_or_apply_facility_prefix("SITE-HELIOS-SITE-HELIOS-ATACAMA-03", "ORG-HELIOS-GLOBAL")
        self.assertEqual(deduped, "SITE-HELIOS-ATACAMA-03")

        # 5. Short tenant code prefix normalization
        short_norm = OnboardingManager.validate_or_apply_facility_prefix("HELIOS-ATACAMA-03", "ORG-HELIOS-GLOBAL")
        self.assertEqual(short_norm, "SITE-HELIOS-ATACAMA-03")

        # 6. Leading dashes and whitespace cleanup
        clean = OnboardingManager.validate_or_apply_facility_prefix("  -ATACAMA-03  ", "ORG-HELIOS-GLOBAL")
        self.assertEqual(clean, "SITE-HELIOS-ATACAMA-03")

        # 7. Mismatched prefix rejected
        with self.assertRaises(ValueError) as ctx:
            OnboardingManager.validate_or_apply_facility_prefix("SITE-AURORA-ATACAMA-03", "ORG-HELIOS-GLOBAL", enforce=True)
        self.assertIn("must have fixed prefix 'SITE-HELIOS-'", str(ctx.exception))

        # 8. Empty ID rejected
        with self.assertRaises(ValueError) as ctx_empty:
            OnboardingManager.validate_or_apply_facility_prefix("   ", "ORG-HELIOS-GLOBAL")
        self.assertIn("cannot be empty", str(ctx_empty.exception))

    def test_06_device_asset_id_fixed_prefix(self):
        """Verify device asset ID has fixed prefix based on selected parent facility."""
        # 1. Prefix derivation
        self.assertEqual(OnboardingManager.derive_device_prefix("SITE-MOJAVE-01"), "SITE-MOJAVE-01-")
        self.assertEqual(OnboardingManager.derive_device_prefix("SITE-HELIOS-ATACAMA-03"), "SITE-HELIOS-ATACAMA-03-")

        # 2. Suffix auto-prefixing
        prefixed = OnboardingManager.validate_or_apply_device_prefix("INV-04", "SITE-MOJAVE-01")
        self.assertEqual(prefixed, "SITE-MOJAVE-01-INV-04")

        # 3. Valid prefix preserved
        valid = OnboardingManager.validate_or_apply_device_prefix("SITE-MOJAVE-01-INV-04", "SITE-MOJAVE-01")
        self.assertEqual(valid, "SITE-MOJAVE-01-INV-04")

        # 4. Short facility code normalization
        short_dev = OnboardingManager.validate_or_apply_device_prefix("MOJAVE-01-INV-04", "SITE-MOJAVE-01")
        self.assertEqual(short_dev, "SITE-MOJAVE-01-INV-04")

        # 5. Repeated prefix deduplication
        dedup_dev = OnboardingManager.validate_or_apply_device_prefix("SITE-MOJAVE-01-SITE-MOJAVE-01-INV-04", "SITE-MOJAVE-01")
        self.assertEqual(dedup_dev, "SITE-MOJAVE-01-INV-04")

        # 6. Leading dashes and whitespace cleanup
        clean_dev = OnboardingManager.validate_or_apply_device_prefix("  -INV-04  ", "SITE-MOJAVE-01")
        self.assertEqual(clean_dev, "SITE-MOJAVE-01-INV-04")

        # 7. Mismatched facility prefix rejected
        with self.assertRaises(ValueError) as ctx:
            OnboardingManager.validate_or_apply_device_prefix("SITE-WIND-NORTH-INV-04", "SITE-MOJAVE-01", enforce=True)
        self.assertIn("must have fixed prefix 'SITE-MOJAVE-01-'", str(ctx.exception))

        # 8. Empty device ID rejected
        with self.assertRaises(ValueError) as ctx_empty:
            OnboardingManager.validate_or_apply_device_prefix("   ", "SITE-MOJAVE-01")
        self.assertIn("cannot be empty", str(ctx_empty.exception))

    def test_07_api_onboarding_prefix_enforcement(self):
        """Verify API enforces fixed prefixes on facility and device onboarding endpoints."""
        from web_server import dispatch_api_request

        # 1. GET /api/onboarding/prefixes returns tenant and device prefixes
        code, pfx_data = dispatch_api_request("GET", "/api/onboarding/prefixes", headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code, 200)
        self.assertEqual(pfx_data["facility_prefix"], "SITE-HELIOS-")
        self.assertIn("SITE-MOJAVE-01", pfx_data["device_prefixes"])

        # 2. Auto-prefixing facility on POST /api/onboarding/facility
        code_fac, res_fac = dispatch_api_request("POST", "/api/onboarding/facility", {
            "name": "Atacama Solar IV",
            "facility_id": "ATACAMA-04",
            "rated_capacity_mw": 80.0,
            "technology": "SOLAR_PV",
            "latitude": -23.8,
            "longitude": -69.1,
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_fac, 200)
        self.assertEqual(res_fac["entity_id"], "SITE-HELIOS-ATACAMA-04")

        # 3. Mismatched tenant prefix rejected on POST /api/onboarding/facility
        code_bad_fac, res_bad_fac = dispatch_api_request("POST", "/api/onboarding/facility", {
            "name": "Fjord Facility Under Helios",
            "facility_id": "SITE-AURORA-BAD-01",
            "rated_capacity_mw": 10.0,
            "technology": "SOLAR_PV",
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_bad_fac, 400)
        self.assertIn("violates tenant partition rules", res_bad_fac["message"])

        # 4. Auto-prefixing device on POST /api/onboarding/device
        code_dev, res_dev = dispatch_api_request("POST", "/api/onboarding/device", {
            "name": "Mojave Inverter 09",
            "device_id": "INV-09",
            "facility_id": "SITE-MOJAVE-01",
            "asset_type": "INVERTER",
            "rated_power_kw": 2500.0,
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_dev, 200)
        self.assertEqual(res_dev["entity_id"], "SITE-MOJAVE-01-INV-09")

        # 5. Mismatched facility prefix rejected on POST /api/onboarding/device
        code_bad_dev, res_bad_dev = dispatch_api_request("POST", "/api/onboarding/device", {
            "name": "Mismatched Inverter",
            "device_id": "SITE-WIND-NORTH-INV-99",
            "facility_id": "SITE-MOJAVE-01",
            "asset_type": "INVERTER",
            "rated_power_kw": 2500.0,
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_bad_dev, 400)
        self.assertIn("violates parent facility rules", res_bad_dev["message"])

        # 6. Auto-deduplication on facility endpoint
        code_dedup_fac, res_dedup_fac = dispatch_api_request("POST", "/api/onboarding/facility", {
            "name": "Atacama Solar V",
            "facility_id": "SITE-HELIOS-SITE-HELIOS-ATACAMA-05",
            "rated_capacity_mw": 50.0,
            "technology": "SOLAR_PV",
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_dedup_fac, 200)
        self.assertEqual(res_dedup_fac["entity_id"], "SITE-HELIOS-ATACAMA-05")

        # 7. Auto-deduplication on device endpoint
        code_dedup_dev, res_dedup_dev = dispatch_api_request("POST", "/api/onboarding/device", {
            "name": "Mojave Inverter 10",
            "device_id": "SITE-MOJAVE-01-SITE-MOJAVE-01-INV-10",
            "facility_id": "SITE-MOJAVE-01",
            "asset_type": "INVERTER",
            "rated_power_kw": 2500.0,
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_dedup_dev, 200)
        self.assertEqual(res_dedup_dev["entity_id"], "SITE-MOJAVE-01-INV-10")

        # 8. Short tenant code normalization on facility endpoint
        code_short_fac, res_short_fac = dispatch_api_request("POST", "/api/onboarding/facility", {
            "name": "Atacama Solar VI",
            "facility_id": "HELIOS-ATACAMA-06",
            "rated_capacity_mw": 60.0,
            "technology": "SOLAR_PV",
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_short_fac, 200)
        self.assertEqual(res_short_fac["entity_id"], "SITE-HELIOS-ATACAMA-06")

        # 9. Short facility code normalization on device endpoint
        code_short_dev, res_short_dev = dispatch_api_request("POST", "/api/onboarding/device", {
            "name": "Mojave Inverter 11",
            "device_id": "MOJAVE-01-INV-11",
            "facility_id": "SITE-MOJAVE-01",
            "asset_type": "INVERTER",
            "rated_power_kw": 2500.0,
        }, headers={"x-tenant-id": "ORG-HELIOS-GLOBAL"})
        self.assertEqual(code_short_dev, 200)
        self.assertEqual(res_short_dev["entity_id"], "SITE-MOJAVE-01-INV-11")

        # Cleanup test entities from GLOBAL_STATE to preserve cross-suite test isolation
        from web_server import GLOBAL_STATE
        app_helios = GLOBAL_STATE.get_tenant_app("ORG-HELIOS-GLOBAL")
        for sid in ["SITE-HELIOS-ATACAMA-04", "SITE-HELIOS-ATACAMA-05", "SITE-HELIOS-ATACAMA-06"]:
            app_helios.sites.pop(sid, None)
        for did in ["SITE-MOJAVE-01-INV-09", "SITE-MOJAVE-01-INV-10", "SITE-MOJAVE-01-INV-11"]:
            app_helios.assets.pop(did, None)
            app_helios.twins.pop(did, None)
            app_helios.device_secrets.pop(did, None)


if __name__ == "__main__":
    unittest.main()
