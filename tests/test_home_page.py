#!/usr/bin/env python3
"""
Automated unit tests for REGENOVA Public Home Page and Portal Routing.
Requirement: AC-FR-UI-001 (Strict Light Theme), Public Landing, Pre-Enrolment.
"""

import io
import json
import os
import unittest
from web_server import application


class TestHomePageRouting(unittest.TestCase):
    """Verifies the public Home Page, pre-enrolment endpoints, and portal routing."""

    def test_public_home_page_serving(self):
        """Verify that GET / returns the Public Home Page with expected sections."""
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
        self.assertIn("REGENOVA", body)
        self.assertIn("Pre-Enrol Your Generation Portfolio", body)
        self.assertIn("Operations Portal Access", body)
        self.assertIn("7-Dimension Asset Health Index", body)
        self.assertIn("Multi-Technology Generation Reference Pipelines", body)
        # Ensure strict AC-FR-UI-001 light theme and zero em dashes
        self.assertIn('data-bs-theme="light"', body)
        self.assertNotIn("—", body)

    def test_operations_portal_serving(self):
        """Verify that GET /portal and GET /portal.html return the Operations Dashboard."""
        for path in ["/portal", "/portal.html"]:
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
            self.assertIn("text/html", headers_dict.get("Content-Type", ""))
            self.assertIn("Fleet Overview", body)
            self.assertIn("Digital Twin & Telemetry", body)
            self.assertIn("Home", body)
            self.assertNotIn("—", body)

    def test_home_page_static_assets(self):
        """Verify serving of home.css and home.js."""
        for path in ["/home.css", "/home.js"]:
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
            self.assertGreater(len(body), 50)
            self.assertNotIn("—", body)


if __name__ == "__main__":
    unittest.main()
