"""Handle email bounces and complaints from Resend webhooks.

For now, hard bounces are logged and the address is added to a local suppression
list so the worker stops sending to it. In the future this can call back to the
realm canister to disable email for that user.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

SUPPRESS_LIST_PATH = Path(os.environ.get("EMAIL_SUPPRESS_LIST_PATH", "./suppress_list.txt"))


def _load_suppressed() -> set:
    """Load the set of suppressed email addresses."""
    if not SUPPRESS_LIST_PATH.exists():
        return set()
    return set(line.strip().lower() for line in SUPPRESS_LIST_PATH.read_text().splitlines() if line.strip())


def _save_suppressed(addresses: set) -> None:
    """Save the suppression list to disk."""
    SUPPRESS_LIST_PATH.write_text("\n".join(sorted(addresses)) + "\n")


def is_suppressed(address: str) -> bool:
    """Return True if the address should not receive email."""
    return address.strip().lower() in _load_suppressed()


def suppress_address(address: str) -> None:
    """Add an address to the suppression list."""
    normalized = address.strip().lower()
    suppressed = _load_suppressed()
    if normalized in suppressed:
        return
    suppressed.add(normalized)
    _save_suppressed(suppressed)
    logger.info(f"Suppressed email address: {normalized}")


async def handle_resend_webhook(payload: Dict[str, Any]) -> None:
    """Process a Resend webhook event.

    Resend events look like:
    {
      "type": "bounce",
      "created_at": "...",
      "email_id": "...",
      "to": "user@example.com",
      "bounce": {
        "type": "hard_bounce",
        "message": "..."
      }
    }
    """
    event_type = payload.get("type", "")
    to_address = payload.get("to", "").strip().lower()
    if not to_address:
        return

    if event_type == "bounce":
        bounce = payload.get("bounce", {})
        bounce_type = bounce.get("type", "")
        if bounce_type in ("hard_bounce", "soft_bounce"):
            logger.warning(f"Resend bounce ({bounce_type}) for {to_address}")
        if bounce_type == "hard_bounce":
            suppress_address(to_address)
    elif event_type == "complaint":
        logger.warning(f"Resend spam complaint for {to_address}")
        suppress_address(to_address)
    elif event_type == "delivery.delivered":
        logger.info(f"Resend delivery confirmed for {to_address}")
    else:
        logger.info(f"Resend webhook event: {event_type} for {to_address}")
