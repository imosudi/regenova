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
        # Infrastructure and Backoffice endpoints must be restricted to Backoffice only
        self.assertNotIn("Cloud Infrastructure", body)
        self.assertNotIn("db.regenova.cloud:5432", body)
        self.assertNotIn("backoffice.regenova.cloud", body)
        self.assertNotIn("Admin Backoffice", body)

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

    def test_british_english_consistency(self):
        """Verify strict British English consistency across Home Page and Operations Portal."""
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
        home_body = b"".join(body_parts).decode("utf-8")

        # Positive assertions for British English
        self.assertIn("Pre-Enrol Organisation", home_body)
        self.assertIn("Organisation Pre-Enrolment Application", home_body)
        self.assertIn("Standardised Photovoltaic Modelling", home_body)
        self.assertIn("Power Curve Normalisation", home_body)
        self.assertIn("Desert Hybrid Centre", home_body)
        self.assertIn("Arrhenius Ageing", home_body)
        self.assertIn("frequency stabilisation", home_body)
        self.assertIn("synchronise to the canonical enterprise schema", home_body)
        self.assertIn("tenant organisations are automatically resolved", home_body)
        self.assertIn("lifecycle optimisation", home_body)

        # Negative assertions against American English variants
        self.assertNotIn("Pre-Enrol Organization", home_body)
        self.assertNotIn("Standardized Photovoltaic Modeling", home_body)
        self.assertNotIn("Power Curve Normalization", home_body)
        self.assertNotIn("Desert Hybrid Center", home_body)
        self.assertNotIn("Arrhenius Aging", home_body)
        self.assertNotIn("frequency stabilization", home_body)
        self.assertNotIn("Chief Engineer authorization", home_body)


if __name__ == "__main__":
    unittest.main()
