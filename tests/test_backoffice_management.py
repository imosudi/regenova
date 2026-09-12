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


if __name__ == "__main__":
    unittest.main()
