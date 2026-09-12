"""
Tests for REGENOVA Dedicated API Server & WSGI Application (api_server.py).
Validates CORS headers, OPTIONS preflight, health discovery, route normalization,
and RESTful endpoints for https://api.regenova.cloud/.
"""

import io
import json
import unittest
from api_server import application, build_discovery_payload


def make_wsgi_request(method="GET", path="/", body=None, headers=None):
    """Helper to simulate WSGI environment call."""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "wsgi.input": io.BytesIO(body.encode("utf-8") if isinstance(body, str) else (body or b"")),
        "CONTENT_LENGTH": str(len(body)) if body else "0",
    }
    if headers:
        for k, v in headers.items():
            environ[f"HTTP_{k.upper().replace('-', '_')}"] = v

    response_status = None
    response_headers = None

    def start_response(status, headers_list):
        nonlocal response_status, response_headers
        response_status = status
        response_headers = dict(headers_list)

    body_chunks = application(environ, start_response)
    full_body = b"".join(body_chunks)
    return response_status, response_headers, full_body


class TestAPIServerWSGI(unittest.TestCase):
    def test_01_cors_options_preflight(self):
        """Verify CORS preflight OPTIONS returns 204 with expected CORS headers."""
        status, headers, body = make_wsgi_request("OPTIONS", "/api/overview")
        self.assertIn("204", status)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("GET", headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("OPTIONS", headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("Content-Type", headers.get("Access-Control-Allow-Headers", ""))
        self.assertEqual(body, b"")

    def test_02_discovery_root_endpoint(self):
        """Verify root / returns healthy discovery payload."""
        status, headers, body = make_wsgi_request("GET", "/")
        self.assertIn("200", status)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "healthy")
        self.assertIn("REGENOVA", data["service"])
        self.assertGreater(len(data["endpoints"]), 5)

    def test_03_health_endpoint(self):
        """Verify /health returns service discovery payload."""
        status, headers, body = make_wsgi_request("GET", "/health")
        self.assertIn("200", status)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "healthy")

    def test_04_overview_endpoints_direct_and_normalized(self):
        """Verify /api/overview and /overview both return identical valid fleet metrics."""
        status1, headers1, body1 = make_wsgi_request("GET", "/api/overview")
        self.assertIn("200", status1)
        d1 = json.loads(body1.decode("utf-8"))
        self.assertIn("total_generation_mw", d1)
        self.assertIn("fleet_health_index", d1)

        # Normalized path without /api prefix
        status2, headers2, body2 = make_wsgi_request("GET", "/overview")
        self.assertIn("200", status2)
        d2 = json.loads(body2.decode("utf-8"))
        self.assertEqual(d2["total_generation_mw"], d1["total_generation_mw"])

    def test_05_head_request(self):
        """Verify HEAD requests return HTTP 200 with empty body."""
        status, headers, body = make_wsgi_request("HEAD", "/api/sites")
        self.assertIn("200", status)
        self.assertEqual(body, b"")
        self.assertIn("application/json", headers.get("Content-Type", ""))

    def test_06_get_sites_and_assets(self):
        """Verify sites and assets endpoints."""
        status, _, body = make_wsgi_request("GET", "/api/sites")
        self.assertIn("200", status)
        sites = json.loads(body.decode("utf-8"))
        self.assertIsInstance(sites, list)
        self.assertGreaterEqual(len(sites), 3)

        status, _, body = make_wsgi_request("GET", "/api/assets")
        self.assertIn("200", status)
        assets = json.loads(body.decode("utf-8"))
        self.assertIsInstance(assets, list)
        self.assertGreaterEqual(len(assets), 3)

    def test_07_get_users_and_audit_chain(self):
        """Verify user directory and SHA-256 audit ledger status."""
        status, _, body = make_wsgi_request("GET", "/api/users")
        self.assertIn("200", status)
        users_data = json.loads(body.decode("utf-8"))
        self.assertIn("users", users_data)
        self.assertGreaterEqual(len(users_data["users"]), 4)

        status, _, body = make_wsgi_request("GET", "/api/audit-chain")
        self.assertIn("200", status)
        chain_data = json.loads(body.decode("utf-8"))
        self.assertTrue(chain_data["is_valid"])
        self.assertGreater(chain_data["total_entries"], 0)

    def test_08_post_user_onboarding(self):
        """Verify user onboarding via POST to /api/onboarding/user."""
        payload = json.dumps({
            "name": "Integration Test Engineer",
            "email": "integration.test@regenova.cloud",
            "role": "OPERATOR",
            "tenant_id": "ORG-HELIOS-GLOBAL",
        })
        status, headers, body = make_wsgi_request("POST", "/api/onboarding/user", body=payload)
        self.assertIn("200", status)
        res = json.loads(body.decode("utf-8"))
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["user"]["email"], "integration.test@regenova.cloud")
        self.assertIsNotNone(res["user"]["token"])

    def test_09_post_telemetry_inject(self):
        """Verify telemetry injection via POST /api/telemetry/inject."""
        payload = json.dumps({
            "asset_id": "ASSET-INV-01",
            "scenario": "HIGH_TEMP_SHADOW",
        })
        status, _, body = make_wsgi_request("POST", "/api/telemetry/inject", body=payload)
        self.assertIn("200", status)
        res = json.loads(body.decode("utf-8"))
        self.assertEqual(res["status"], "INGESTED")

    def test_10_not_found_endpoint(self):
        """Verify invalid routes return 404 JSON response."""
        status, headers, body = make_wsgi_request("GET", "/api/nonexistent-route-xyz")
        self.assertIn("404", status)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        res = json.loads(body.decode("utf-8"))
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
