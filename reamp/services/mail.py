"""
REGENOVA Email Dispatcher & User Management Notification Service.
Handles transactional email operations for:
- User onboarding and email confirmation
- Password reset and recovery workflows
- Operator credentials and access provisioning
- Operational alerts and notifications

Loads configuration from environment variables or local .env file.
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any
from dataclasses import dataclass


def load_dotenv(filepath: Optional[str] = None) -> None:
    """
    Parses a key-value .env file and injects entries into os.environ.
    Does not overwrite existing environment variables.
    Standard-library only, zero external dependencies.
    """
    if filepath is None:
        # Check current working directory, then repo root
        candidates = [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                filepath = c
                break

    if not filepath or not os.path.isfile(filepath):
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    # Also strip inline comments after spaces
                    if " #" in val:
                        val = val.split(" #", 1)[0].strip()
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass


# Automatically attempt to load .env on module import
load_dotenv()


@dataclass
class MailConfig:
    """Configuration structure for REGENOVA SMTP mail services."""
    debug: bool = False
    server: str = "email-smtp.us-east-1.amazonaws.com"
    port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    username: str = ""
    password: str = ""
    default_sender: str = "noreply@serverafrica.net"


def get_mail_config() -> MailConfig:
    """Builds a MailConfig instance from current environment variables."""
    load_dotenv()

    def parse_bool(val: str, default: bool = False) -> bool:
        if not val:
            return default
        clean = val.strip().lower()
        return clean in ("true", "1", "yes", "on")

    def parse_int(val: str, default: int = 587) -> int:
        try:
            return int(val.strip())
        except (ValueError, TypeError):
            return default

    debug_val = os.environ.get("REGENOVA_MAIL_DEBUG", "False")
    server_val = os.environ.get("REGENOVA_MAIL_SERVER", "email-smtp.us-east-1.amazonaws.com").strip().strip("'\"")
    port_val = parse_int(os.environ.get("REGENOVA_MAIL_PORT", "587"), 587)
    use_tls_val = parse_bool(os.environ.get("REGENOVA_MAIL_USE_TLS", "True"), True)
    use_ssl_val = parse_bool(os.environ.get("REGENOVA_MAIL_USE_SSL", "False"), False)
    username_val = os.environ.get("REGENOVA_MAIL_USERNAME", "").strip().strip("'\"")
    password_val = os.environ.get("REGENOVA_MAIL_PASSWORD", "").strip().strip("'\"")
    sender_val = os.environ.get("REGENOVA_MAIL_DEFAULT_SENDER", "noreply@serverafrica.net").strip().strip("'\"")

    return MailConfig(
        debug=parse_bool(debug_val, False),
        server=server_val,
        port=port_val,
        use_tls=use_tls_val,
        use_ssl=use_ssl_val,
        username=username_val,
        password=password_val,
        default_sender=sender_val,
    )


def send_email(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    sender: Optional[str] = None,
    config: Optional[MailConfig] = None,
) -> bool:
    """
    Dispatches an email via SMTP with STARTTLS or SSL encryption.
    Returns True on successful handoff, False on failure.
    """
    cfg = config or get_mail_config()
    from_sender = sender or cfg.default_sender

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_sender
    msg["To"] = to_email

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    if html_content:
        msg.attach(MIMEText(html_content, "html", "utf-8"))

    if not cfg.server or not cfg.username or not cfg.password:
        return False

    try:
        if cfg.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.server, cfg.port, context=context) as server:
                server.login(cfg.username, cfg.password)
                server.sendmail(from_sender, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(cfg.server, cfg.port) as server:
                if cfg.debug:
                    server.set_debuglevel(1)
                if cfg.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                server.login(cfg.username, cfg.password)
                server.sendmail(from_sender, [to_email], msg.as_string())
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# User Management Notification Helpers
# -----------------------------------------------------------------------------

def send_email_confirmation(
    to_email: str,
    user_name: str,
    confirmation_token: str,
    base_url: str = "https://regenova.cloud",
) -> bool:
    """Sends account verification and email confirmation message."""
    confirm_url = f"{base_url}/confirm-email?token={confirmation_token}&email={to_email}"
    subject = "REGENOVA - Confirm Your Operator Account Email"

    text = f"""Hello {user_name},

Thank you for registering on REGENOVA - Renewable Energy Asset Intelligence & Management Platform.

Please confirm your work email address by visiting the link below:
{confirm_url}

Security token: {confirmation_token}

If you did not request this registration, please disregard this message.

Best regards,
REGENOVA Operations Team
"""

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.5; color: #212529;">
  <div style="max-width: 560px; margin: 0 auto; padding: 24px; border: 1px solid #dee2e6; border-radius: 8px;">
    <h3 style="color: #0d6efd; margin-top: 0;">REGENOVA Platform</h3>
    <p>Hello <strong>{user_name}</strong>,</p>
    <p>Please confirm your operator work email address to activate your access to the Operations Portal.</p>
    <div style="margin: 24px 0;">
      <a href="{confirm_url}" style="background: #0d6efd; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; display: inline-block;">Confirm Email Address</a>
    </div>
    <p style="font-size: 0.85rem; color: #6c757d;">Or copy and paste this verification URL:<br><code style="word-break: break-all;">{confirm_url}</code></p>
    <hr style="border: 0; border-top: 1px solid #dee2e6; margin: 20px 0;">
    <p style="font-size: 0.75rem; color: #6c757d; margin: 0;">Security Verification Token: <code>{confirmation_token}</code></p>
  </div>
</body>
</html>"""

    return send_email(to_email, subject, text, html)


def send_password_reset(
    to_email: str,
    user_name: str,
    reset_token: str,
    base_url: str = "https://regenova.cloud",
) -> bool:
    """Sends password reset and recovery instructions."""
    reset_url = f"{base_url}/reset-password?token={reset_token}&email={to_email}"
    subject = "REGENOVA - Password Reset Request"

    text = f"""Hello {user_name},

A password reset request was received for your REGENOVA Operations account.

To choose a new security password, visit the link below:
{reset_url}

Temporary reset token: {reset_token}

This link is valid for 60 minutes. If you did not request a password reset, please contact your security administrator immediately.

Best regards,
REGENOVA Security Administration
"""

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.5; color: #212529;">
  <div style="max-width: 560px; margin: 0 auto; padding: 24px; border: 1px solid #dee2e6; border-radius: 8px;">
    <h3 style="color: #0d6efd; margin-top: 0;">REGENOVA Platform</h3>
    <p>Hello <strong>{user_name}</strong>,</p>
    <p>A password reset request was received for your REGENOVA account. Click the button below to set a new password:</p>
    <div style="margin: 24px 0;">
      <a href="{reset_url}" style="background: #dc3545; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; display: inline-block;">Reset Your Password</a>
    </div>
    <p style="font-size: 0.85rem; color: #6c757d;">Or copy and paste this reset URL:<br><code style="word-break: break-all;">{reset_url}</code></p>
    <hr style="border: 0; border-top: 1px solid #dee2e6; margin: 20px 0;">
    <p style="font-size: 0.75rem; color: #6c757d; margin: 0;">Reset Token: <code>{reset_token}</code> (Expires in 60 minutes)</p>
  </div>
</body>
</html>"""

    return send_email(to_email, subject, text, html)


def send_operator_welcome(
    to_email: str,
    user_name: str,
    tenant_name: str,
    temp_password: Optional[str] = None,
    base_url: str = "https://regenova.cloud",
) -> bool:
    """Sends welcome notification and access credentials for newly provisioned operators."""
    login_url = f"{base_url}/portal.html"
    subject = f"REGENOVA - Operations Portal Access Granted ({tenant_name})"

    pwd_text = f"\nTemporary Initial Password: {temp_password}\n" if temp_password else ""
    pwd_html = f"<p>Temporary Initial Password: <code style='font-size: 1.1rem; color: #0d6efd;'>{temp_password}</code></p>" if temp_password else ""

    text = f"""Hello {user_name},

You have been provisioned as an authorized operator for {tenant_name} on the REGENOVA Asset Intelligence & Management platform.
{pwd_text}
You can access the Operations Portal here:
{login_url}

Please update your credentials upon initial login.

Best regards,
REGENOVA Operations Support
"""

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.5; color: #212529;">
  <div style="max-width: 560px; margin: 0 auto; padding: 24px; border: 1px solid #dee2e6; border-radius: 8px;">
    <h3 style="color: #0d6efd; margin-top: 0;">REGENOVA Operations Portal</h3>
    <p>Hello <strong>{user_name}</strong>,</p>
    <p>You have been assigned access to the <strong>{tenant_name}</strong> operational telemetry partition.</p>
    {pwd_html}
    <div style="margin: 24px 0;">
      <a href="{login_url}" style="background: #198754; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; display: inline-block;">Launch Operations Portal</a>
    </div>
    <hr style="border: 0; border-top: 1px solid #dee2e6; margin: 20px 0;">
    <p style="font-size: 0.75rem; color: #6c757d; margin: 0;">REGENOVA Asset Intelligence &bull; Conforms strictly to AC-FR-UI-001</p>
  </div>
</body>
</html>"""

    return send_email(to_email, subject, text, html)
