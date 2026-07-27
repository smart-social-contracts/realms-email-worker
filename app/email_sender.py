"""SMTP email sending for the Realms Email Worker."""

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

from email_validator import EmailNotValidError, validate_email

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "mail.privateemail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
DEFAULT_FROM = os.environ.get("ALERT_EMAIL_FROM", SMTP_USER or "noreply@realmsgos.dev")


def _default_from_address() -> str:
    return DEFAULT_FROM


def _validate_address(address: str) -> str:
    """Return a normalized email address or raise ValueError."""
    try:
        info = validate_email(address, check_deliverability=False)
        return info.normalized
    except EmailNotValidError as exc:
        raise ValueError(f"Invalid email address: {address}") from exc


def send_email(
    to: str,
    subject: str,
    body: str,
    from_name: str = "",
    from_address: str = "",
    reply_to: str = "",
) -> Dict[str, Any]:
    """Send a single email via SMTP."""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials are not configured (SMTP_HOST, SMTP_USER, SMTP_PASSWORD)")

    from_address = from_address or _default_from_address()
    if not from_address:
        raise ValueError("No from address configured")

    to = _validate_address(to)
    from_address = _validate_address(from_address)

    msg = EmailMessage()
    msg["Subject"] = subject
    display_name = from_name or from_address.split("@")[0]
    msg["From"] = f"{display_name} <{from_address}>"
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = _validate_address(reply_to)
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent to {to}: {subject}")
        return {"success": True, "to": to}
    except Exception as exc:
        logger.error(f"Failed to send email to {to}: {exc}")
        raise
