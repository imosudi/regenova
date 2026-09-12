"""
Automated unit tests for REAMP PostgreSQL storage backend and persistence integration.
Validates PostgresDatabaseManager, diagnostic status reporting, resilience fallback,
and API endpoint /api/database/status.
"""

import io
import json
import unittest
from reamp.storage.postgres import PostgresDatabaseManager, to_uuid_str
from web_server import application


class TestPostgresStorage(unittest.TestCase):
    def setUp(self):
        self.mgr = PostgresDatabaseManager()

    def test_01_deterministic_uuid(self):
        """Verify to_uuid_str produces consistent, valid UUID strings."""
        u1 = to_uuid_str("ORG-HELIOS-GLOBAL")
        u2 = to_uuid_str("ORG-HELIOS-GLOBAL")
        self.assertEqual(u1, u2)
        self.assertEqual(len(u1), 36)
        self.assertEqual(u1.count("-"), 4)

    def test_02_status_structure(self):
        """Verify get_status returns expected diagnostic schema."""
        status = self.mgr.get_status()
        self.assertIn("database", status)
        self.assertIn("status", status)
        self.assertIn("host", status)
        self.assertIn("dbname", status)
        self.assertIn("user", status)
        self.assertIn("tables_count", status)
        self.assertIn(status["status"], ("CONNECTED", "DISCONNECTED"))

    def test_03_fallback_on_unreachable_host(self):
        """Verify manager handles unreachable database hosts with graceful fallback."""
        bad_mgr = PostgresDatabaseManager(
            host="invalid-nonexistent-db-host.internal",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="fake",
            connect_timeout=1,
        )
        self.assertFalse(bad_mgr.test_connection())
        status = bad_mgr.get_status()
        self.assertEqual(status["status"], "DISCONNECTED")
        self.assertIsNotNone(status["last_error"])
        # Methods should return False gracefully instead of crashing
        self.assertFalse(bad_mgr.sync_organisation("TEST-ORG", "Test", "TEST"))
        self.assertFalse(bad_mgr.sync_user("USR-1", "TEST-ORG", "t@test.com", "Test", "OPERATOR"))

    def test_04_api_database_status_endpoint(self):
        """Verify /api/database/status returns HTTP 200 with status JSON."""
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/database/status",
            "wsgi.input": io.BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        resp_status = None
        resp_headers = None

        def start_response(status, headers):
            nonlocal resp_status, resp_headers
            resp_status = status
            resp_headers = dict(headers)

        body_bytes = b"".join(application(environ, start_response))
        self.assertIn("200", resp_status)
        self.assertIn("application/json", resp_headers.get("Content-Type", ""))
        data = json.loads(body_bytes.decode("utf-8"))
        self.assertEqual(data["database"], "PostgreSQL")
        self.assertIn(data["status"], ("CONNECTED", "DISCONNECTED"))


if __name__ == "__main__":
    unittest.main()
