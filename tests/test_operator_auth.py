"""
Tests for REGENOVA Operations Portal Access Login Enforcement and Operator Authentication.
Validates:
1. Multi-tenant operator credentials verification (Helios, Aurora, Solaria).
2. Universal fallback operator credentials.
3. Cryptographic HMAC session tokens (OPR-SEC-...).
4. Rejection of invalid credentials, unknown users, and tenant mismatches.
5. Token verification endpoint (/api/operator/verify and /api/operator/session).
6. Presence of Operator Authentication Gateway and password toggle in web/portal.html.
7. Zero em dashes in modified source files.
"""

import unittest
import os
import json
from web_server import GLOBAL_STATE, dispatch_api_request


class TestOperatorAuthentication(unittest.TestCase):
    def setUp(self):
        self.state = GLOBAL_STATE

    def test_01_helios_operator_login_success(self):
        """Validates login for Helios Global Chief Engineer and Operator."""
        # Chief Engineer with tenant password
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "elena.rostova@helios.energy",
            "password": "Helios2026!",
            "tenant_id": "ORG-HELIOS-GLOBAL"
        })
        self.assertEqual(code, 200)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["token"].startswith("OPR-SEC-"))
        self.assertEqual(res["user"]["email"], "elena.rostova@helios.energy")
        self.assertEqual(res["user"]["tenant_id"], "ORG-HELIOS-GLOBAL")
        self.assertEqual(res["tenant"]["tenant_id"], "ORG-HELIOS-GLOBAL")

        # Operator with universal password
        code2, res2 = dispatch_api_request("POST", "/api/operator/login", {
            "email": "marcus.vance@helios.energy",
            "password": "password"
        })
        self.assertEqual(code2, 200)
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(res2["user"]["name"], "Marcus Vance")

    def test_02_aurora_operator_login_success(self):
        """Validates login for Aurora Nordic operator accounts."""
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "astrid.lindgren@aurora.energy",
            "password": "Aurora2026!",
            "tenant_id": "ORG-AURORA-NORDIC"
        })
        self.assertEqual(code, 200)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tenant"]["tenant_id"], "ORG-AURORA-NORDIC")
        self.assertEqual(res["user"]["name"], "Astrid Lindgren")

    def test_03_solaria_operator_login_success(self):
        """Validates login for Solaria Iberia operator accounts."""
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "javier.morales@solaria.energy",
            "password": "Solaria2026!"
        })
        self.assertEqual(code, 200)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tenant"]["tenant_id"], "ORG-SOLARIA-ESP")

    def test_04_invalid_credentials_rejected(self):
        """Validates that bad passwords return HTTP 401."""
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "elena.rostova@helios.energy",
            "password": "WrongPassword123!"
        })
        self.assertEqual(code, 401)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Invalid password", res["message"])

    def test_05_unknown_user_rejected(self):
        """Validates that non-existent users return HTTP 401."""
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "nonexistent.operator@unknown.energy",
            "password": "password"
        })
        self.assertEqual(code, 401)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("not found", res["message"])

    def test_06_tenant_mismatch_rejected(self):
        """Validates that an operator cannot authenticate against an unauthorized tenant partition."""
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "elena.rostova@helios.energy",
            "password": "Helios2026!",
            "tenant_id": "ORG-SOLARIA-ESP"
        })
        self.assertEqual(code, 401)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("assigned to tenant partition", res["message"])

    def test_07_token_verification(self):
        """Validates session verification for valid and invalid tokens."""
        # 1. Login to get token
        code, res = dispatch_api_request("POST", "/api/operator/login", {
            "email": "elena.rostova@helios.energy",
            "password": "Helios2026!"
        })
        token = res["token"]

        # 2. Verify via POST /api/operator/verify
        v_code, v_res = dispatch_api_request("POST", "/api/operator/verify", {"token": token})
        self.assertEqual(v_code, 200)
        self.assertTrue(v_res["valid"])
        self.assertEqual(v_res["user"]["email"], "elena.rostova@helios.energy")

        # 3. Verify via GET /api/operator/session with query parameter
        g_code, g_res = dispatch_api_request("GET", "/api/operator/session", query_params={"token": token})
        self.assertEqual(g_code, 200)
        self.assertTrue(g_res["valid"])

        # 4. Invalid token rejected
        bad_code, bad_res = dispatch_api_request("POST", "/api/operator/verify", {"token": "OPR-SEC-FAKETOKEN999"})
        self.assertEqual(bad_code, 401)
        self.assertFalse(bad_res.get("valid", True))

    def test_08_portal_html_gateway_enforced(self):
        """Validates that web/portal.html contains the login gateway and hides the app layout."""
        portal_path = os.path.join(os.path.dirname(__file__), "..", "web", "portal.html")
        with open(portal_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Gateway exists
        self.assertIn('id="portalLoginScreen"', content)
        self.assertNotIn('id="portalTenantSelect"', content)
        self.assertNotIn('Quick Fill Operator Credentials', content)
        self.assertIn('id="portalLoginEmail"', content)
        self.assertIn('id="portalLoginPassword"', content)
        self.assertIn('id="portalCheckShowPassword"', content)
        self.assertIn('id="portalTogglePasswordBtn"', content)
        self.assertIn('id="btnOperatorLoginSubmit"', content)

        # App layout is hidden by default
        self.assertIn('id="portalAppLayout"', content)
        self.assertIn('class="reamp-app-layout d-none"', content)

        # Topbar operator badge and logout button exist
        self.assertIn('id="topbar-operator-badge"', content)
        self.assertIn('id="btnOperatorLogout"', content)

    def test_09_zero_em_dashes_enforced(self):
        """Validates zero em dashes in touched files."""
        base_dir = os.path.join(os.path.dirname(__file__), "..")
        files_to_check = [
            os.path.join(base_dir, "web", "portal.html"),
            os.path.join(base_dir, "web", "app.js"),
            os.path.join(base_dir, "web", "index.html"),
            os.path.join(base_dir, "web_server.py"),
            os.path.join(base_dir, "api_server.py"),
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                data = f.read()
            self.assertNotIn("—", data, f"Found em dash in {fpath}")


if __name__ == "__main__":
    unittest.main()
