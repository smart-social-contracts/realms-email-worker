"""Background polling worker that fetches pending emails from the realm and sends them."""

import logging
import os
import time
from threading import Thread
from typing import Any, Dict

from app.canister_client import (
    REALM_CANISTER_ID,
    get_email_config,
    get_pending_email_notifications,
    mark_email_sent,
)
from app.email_bounce import is_suppressed
from app.email_sender import send_email
from app.templates import render_email

logger = logging.getLogger(__name__)

EMAIL_POLL_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLL_INTERVAL_SECONDS", "60"))
MAX_EMAILS_PER_POLL = int(os.environ.get("MAX_EMAILS_PER_POLL", "50"))
EMAIL_SEND_DELAY_SECONDS = float(os.environ.get("EMAIL_SEND_DELAY_SECONDS", "0.5"))


def _get_email_config(canister_id: str) -> Dict[str, Any]:
    """Fetch and return the realm email config, or a disabled fallback."""
    result = get_email_config(canister_id)
    if not result.get("success"):
        logger.warning(f"Could not fetch email config: {result.get('error')}")
        return {"enabled": False}
    return result.get("data", {}) or {"enabled": False}


def _process_pending(canister_id: str) -> None:
    """Fetch pending emails from the canister and send them."""
    email_config = _get_email_config(canister_id)
    # The canister already decides what to queue. Drain anything pending,
    # including admin tests and verification mail, even when the realm
    # master switch is off.

    pending = get_pending_email_notifications(canister_id)
    if not pending.get("success"):
        logger.warning(f"Could not fetch pending emails: {pending.get('error')}")
        return

    payload = pending.get("data", pending)
    if isinstance(payload, list):
        notifications = payload
    elif isinstance(payload, dict):
        notifications = payload.get("notifications", [])
        if isinstance(notifications, dict):
            notifications = notifications.get("notifications", [])
    else:
        notifications = []
    notifications = notifications[:MAX_EMAILS_PER_POLL]
    if not notifications:
        return

    logger.info(f"Processing {len(notifications)} pending email notifications")
    for notification in notifications:
        notification_id = notification.get("id")
        to_address = notification.get("to_address", "").strip().lower()
        event_type = notification.get("event_type", "notification")

        if not to_address:
            logger.warning(f"Skipping notification {notification_id}: no recipient")
            mark_email_sent(canister_id, notification_id, False, "No recipient")
            continue

        if is_suppressed(to_address):
            logger.warning(f"Skipping suppressed address: {to_address}")
            mark_email_sent(canister_id, notification_id, False, "Address suppressed")
            continue

        # Add realm logo to notification variables if not already present.
        notification.setdefault("logo_url", email_config.get("logo_url", ""))

        rendered = render_email(event_type, email_config, notification)
        try:
            send_email(
                to=to_address,
                subject=rendered["subject"],
                text=rendered["text"],
                html=rendered["html"],
                from_name=email_config.get("from_name", ""),
                from_address=email_config.get("from_address", ""),
                reply_to=email_config.get("reply_to", ""),
            )
            mark_email_sent(canister_id, notification_id, True, "")
            logger.info(f"Sent email for notification {notification_id}")
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"Failed to send email for notification {notification_id}: {error_msg}")
            mark_email_sent(canister_id, notification_id, False, error_msg)

        time.sleep(EMAIL_SEND_DELAY_SECONDS)


def _poll_loop() -> None:
    """Background loop that polls the canister for pending emails."""
    if not REALM_CANISTER_ID:
        logger.info("REALM_CANISTER_ID not set; email pull worker is disabled.")
        return

    logger.info(f"Starting email pull worker for canister {REALM_CANISTER_ID}")
    while True:
        try:
            _process_pending(REALM_CANISTER_ID)
        except Exception as exc:
            logger.error(f"Email poll loop error: {exc}")
        time.sleep(EMAIL_POLL_INTERVAL_SECONDS)


def start_email_worker() -> None:
    """Start the background email polling thread."""
    thread = Thread(target=_poll_loop, daemon=True)
    thread.start()
