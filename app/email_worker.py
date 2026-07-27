"""Background polling worker that fetches pending emails from the realm and sends them."""

import json
import logging
import os
import time
from threading import Thread
from typing import Any, Dict

from app.canister_client import REALM_CANISTER_ID, get_pending_email_notifications, mark_email_sent
from app.email_sender import send_email

logger = logging.getLogger(__name__)

EMAIL_POLL_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLL_INTERVAL_SECONDS", "60"))


def _process_pending(canister_id: str) -> None:
    """Fetch pending emails from the canister and send them."""
    pending = get_pending_email_notifications(canister_id)
    if not pending.get("success"):
        logger.warning(f"Could not fetch pending emails: {pending.get('error')}")
        return

    notifications = pending.get("data", {}).get("notifications", [])
    if not notifications:
        return

    logger.info(f"Processing {len(notifications)} pending email notifications")
    for notification in notifications:
        notification_id = notification.get("id")
        to_address = notification.get("to_address")
        subject = notification.get("title", "Realms notification")
        body = notification.get("message", "")
        if not to_address:
            logger.warning(f"Skipping notification {notification_id}: no recipient")
            continue

        try:
            send_email(
                to=to_address,
                subject=subject,
                body=body,
            )
            mark_email_sent(canister_id, notification_id, True, "")
            logger.info(f"Sent email for notification {notification_id}")
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"Failed to send email for notification {notification_id}: {error_msg}")
            mark_email_sent(canister_id, notification_id, False, error_msg)


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
