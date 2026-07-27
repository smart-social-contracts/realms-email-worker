"""Email sending for the Realms Email Worker.

Primary transport: Resend HTTP API (https://resend.com).
Fallback transport: SMTP (any provider).

Resend is recommended for Realms GOS because it provides DKIM/SPF/DMARC
guidance, bounce/complaint webhooks, and reputation monitoring out of the box.
"""

import logging
import os
from typing import Any, Dict

import httpx
from email_validator import EmailNotValidError, validate_email

logger = logging.getLogger(__name__)

EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "resend").strip().lower()

# Resend settings
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_API_URL = os.environ.get("RESEND_API_URL", "https://api.resend.com/emails")

# SMTP fallback settings
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


def _format_from(from_name: str, from_address: str) -> str:
    """Return a From header value like 'Realms GOS <noreply@...>'."""
    display_name = from_name or from_address.split("@")[0]
    return f"{display_name} <{from_address}>"


def _send_resend(
    to: str,
    subject: str,
    text: str,
    html: str = "",
    from_address: str = "",
    reply_to: str = "",
) -> Dict[str, Any]:
    """Send a single email via the Resend HTTP API."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured")

    payload: Dict[str, Any] = {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"Resend email queued for {to}: {subject} (id={data.get('id')})")
        return {"success": True, "to": to, "provider_id": data.get("id")}
    except httpx.HTTPStatusError as exc:
        logger.error(f"Resend API error: {exc.response.status_code} {exc.response.text}")
        raise RuntimeError(f"Resend API error: {exc.response.text}") from exc
    except Exception as exc:
        logger.error(f"Failed to send via Resend: {exc}")
        raise


def _send_smtp(
    to: str,
    subject: str,
    text: str,
    html: str = "",
    from_name: str = "",
    from_address: str = "",
    reply_to: str = "",
) -> Dict[str, Any]:
    """Send a single email via SMTP."""
    import smtplib
    from email.message import EmailMessage

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials are not configured (SMTP_HOST, SMTP_USER, SMTP_PASSWORD)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _format_from(from_name, from_address)
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = _validate_address(reply_to)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    logger.info(f"SMTP email sent to {to}: {subject}")
    return {"success": True, "to": to}


def send_email(
    to: str,
    subject: str,
    text: str,
    html: str = "",
    from_name: str = "",
    from_address: str = "",
    reply_to: str = "",
) -> Dict[str, Any]:
    """Send a single email using the configured provider."""
    from_address = from_address or _default_from_address()
    if not from_address:
        raise ValueError("No from address configured")

    to = _validate_address(to)
    from_address = _validate_address(from_address)
    formatted_from = _format_from(from_name, from_address)

    if EMAIL_PROVIDER == "resend":
        return _send_resend(
            to=to,
            subject=subject,
            text=text,
            html=html,
            from_address=formatted_from,
            reply_to=reply_to,
        )

    return _send_smtp(
        to=to,
        subject=subject,
        text=text,
        html=html,
        from_name=from_name,
        from_address=from_address,
        reply_to=reply_to,
    )
