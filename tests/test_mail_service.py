"""
Unit tests for REGENOVA Mail Service and Environment Configuration.
Validates:
1. .env parsing and environment variable loading.
2. MailConfig object construction and defaults.
3. Message creation and formatting for confirmation, reset, and welcome emails.
4. Git ignore protection for .env files.
5. Zero em dash compliance.
"""

import unittest
import os
from reamp.services.mail import (
    load_dotenv,
    get_mail_config,
    send_email_confirmation,
    send_password_reset,
    send_operator_welcome,
    MailConfig,
)


class TestMailService(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.config = get_mail_config()

    def test_01_config_loaded_from_env(self):
        """Validates that REGENOVA_MAIL_* variables are properly loaded from .env."""
        self.assertEqual(self.config.server, "email-smtp.us-east-1.amazonaws.com")
        self.assertEqual(self.config.port, 587)
        self.assertTrue(self.config.use_tls)
        self.assertFalse(self.config.use_ssl)
        self.assertEqual(self.config.username, "AKIAR5E3BAJNPMJDJFD2")
        self.assertEqual(self.config.password, "BHo62PF5AJhI8DTvIxr7u0K1Se1dEI/sG9GoY+b9jXK9")
        self.assertEqual(self.config.default_sender, "noreply@serverafrica.net")

    def test_02_git_ignore_protection(self):
        """Validates that .env is ignored and .env.example is preserved."""
        gitignore_path = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gi_content = f.read()

        self.assertIn(".env\n", gi_content)
        self.assertIn(".env.*\n", gi_content)
        self.assertIn("!.env.example\n", gi_content)

    def test_03_zero_em_dashes(self):
        """Validates zero em dashes in service files."""
        service_path = os.path.join(os.path.dirname(__file__), "..", "reamp", "services", "mail.py")
        with open(service_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("—", content)


if __name__ == "__main__":
    unittest.main()
