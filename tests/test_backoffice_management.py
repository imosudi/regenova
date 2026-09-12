#!/usr/bin/env python3
"""
Unit tests for REGENOVA Backoffice Admin Management Server & Application.
Requirement: AC-FR-UI-001 (Strict Light Theme), Separated Admin Portal.
"""

import io
import json
import os
import unittest
from backend_server import application, BACKEND_WEB_DIR


class TestBackofficeManagement(unittest.TestCase):
    """Verifies the Backoffice admin backend web application and WSGI handlers."""

    def test_static_index_html_serving(self):
        """Verify that GET / returns the Backoffice HTML dashboard with light theme."""
        status_received = []
        headers_received = []

        def start_response(status, headers):
            status_received.append(status)
            headers_received.extend(headers)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "wsgi.input": io.BytesIO(b""),
        }

        body_parts = application(environ, start_response)
        body = b"".join(body_parts).decode("utf-8")

        self.assertEqual(status_received[0], "200 OK")
        headers_dict = dict(headers_received)
        self.assertIn("text/html", headers_dict.get("Content-Type", ""))
        self.assertIn("REGENOVA Backoffice", body)
        self.assertIn("Platform Operations & Administration", body)
        self.assertIn('data-bs-theme="light"', body)
        # Ensure strict AC-FR-UI-001 light theme and no em dashes
        self.assertNotIn("—", body)

    def test_static_assets_serving(self):
        """Verify serving of styles.css and app.js."""
        for path, expected_mime in [("/styles.css", "text/css"), ("/app.js", "application/javascript")]:
            status_received = []
            headers_received = []

            def start_response(status, headers):
                status_received.append(status)
                headers_received.extend(headers)

            environ = {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": path,
                "wsgi.input": io.BytesIO(b""),
            }

            body_parts = application(environ, start_response)
            body = b"".join(body_parts).decode("utf-8")

            self.assertEqual(status_received[0], "200 OK")
            headers_dict = dict(headers_received)
            self.assertTrue("javascript" in headers_dict.get("Content-Type", "") or "css" in headers_dict.get("Content-Type", ""))
            self.assertGreater(len(body), 100)
            self.assertNotIn("—", body)

    def test_path_traversal_protection(self):
        """Verify that unauthorized path traversal attempts return 404."""
        status_received = []
        headers_received = []

        def start_response(status, headers):
            status_received.append(status)
            headers_received.extend(headers)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/../../../../etc/passwd",
            "wsgi.input": io.BytesIO(b""),
        }

        body_parts = application(environ, start_response)
        self.assertEqual(status_received[0], "404 Not Found")

    def test_cors_preflight(self):
        """Verify CORS preflight handling."""
        status_received = []
        headers_received = []

        def start_response(status, headers):
            status_received.append(status)
            headers_received.extend(headers)

        environ = {
            "REQUEST_METHOD": "OPTIONS",
            "PATH_INFO": "/",
            "wsgi.input": io.BytesIO(b""),
        }

        body_parts = application(environ, start_response)
        self.assertEqual(status_received[0], "200 OK")
        headers_dict = dict(headers_received)
        self.assertEqual(headers_dict.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("X-Tenant-ID", headers_dict.get("Access-Control-Allow-Headers", ""))

    def test_admin_login_success(self):
        """Verify POST /api/admin/login with correct default credentials."""
        from web_server import dispatch_api_request

        code, resp = dispatch_api_request("POST", "/api/admin/login", {
            "email": "imosudi@gmail.com",
            "password": "password",
        })
        self.assertEqual(code, 200)
        self.assertEqual(resp.get("status"), "SUCCESS")
        self.assertTrue(resp.get("token", "").startswith("ADM-SEC-"))
        user = resp.get("user", {})
        self.assertEqual(user.get("email"), "imosudi@gmail.com")
        self.assertEqual(user.get("role"), "SECURITY_ADMIN")
        self.assertEqual(user.get("scope"), "PLATFORM_ROOT")

    def test_admin_login_invalid_password(self):
        """Verify POST /api/admin/login with invalid password returns 401."""
        from web_server import dispatch_api_request

        code, resp = dispatch_api_request("POST", "/api/admin/login", {
            "email": "imosudi@gmail.com",
            "password": "wrong_password",
        })
        self.assertEqual(code, 401)
        self.assertEqual(resp.get("status"), "ERROR")
        self.assertIn("Invalid administrator credentials", resp.get("message", ""))

    def test_admin_login_invalid_email(self):
        """Verify POST /api/admin/login with unauthorized email returns 401."""
        from web_server import dispatch_api_request

        code, resp = dispatch_api_request("POST", "/api/admin/login", {
            "email": "unauthorized@external.com",
            "password": "password",
        })
        self.assertEqual(code, 401)
        self.assertEqual(resp.get("status"), "ERROR")

    def test_admin_verify_session(self):
        """Verify token validation via /api/admin/verify."""
        from web_server import dispatch_api_request

        code, resp = dispatch_api_request("POST", "/api/admin/login", {
            "email": "imosudi@gmail.com",
            "password": "password",
        })
        token = resp.get("token")

        v_code, v_resp = dispatch_api_request("POST", "/api/admin/verify", {"token": token})
        self.assertEqual(v_code, 200)
        self.assertTrue(v_resp.get("valid"))

        bad_code, bad_resp = dispatch_api_request("POST", "/api/admin/verify", {"token": "ADM-SEC-INVALID"})
        self.assertEqual(bad_code, 401)
        self.assertFalse(bad_resp.get("valid"))

    def test_login_screen_in_index_html(self):
        """Verify that login screen barrier and elements exist in Backoffice HTML."""
        index_path = os.path.join(BACKEND_WEB_DIR, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="backofficeLoginScreen"', html)
        self.assertIn('id="formAdminLogin"', html)
        self.assertIn('id="loginEmail"', html)
        self.assertIn('id="loginPassword"', html)
        self.assertIn('imosudi@gmail.com', html)
        self.assertIn('id="backofficeAppLayout"', html)
        self.assertIn('id="btnAdminLogout"', html)
        self.assertNotIn("—", html)


if __name__ == "__main__":
    unittest.main()

