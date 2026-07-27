"""Call Realms extension methods on a canister from the off-chain worker.

This module uses the ``dfx`` CLI by default. You can override the command
template via the ``EMAIL_WORKER_DFX_CALL_TEMPLATE`` environment variable if
you need a custom IC agent or remote node setup.
"""

import json
import logging
import os
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

REALM_CANISTER_ID = os.environ.get("REALM_CANISTER_ID", "")
DFX_IDENTITY = os.environ.get("DFX_IDENTITY", "")
DFX_NETWORK = os.environ.get("DFX_NETWORK", "local")
DFX_CALL_TEMPLATE = os.environ.get(
    "EMAIL_WORKER_DFX_CALL_TEMPLATE",
    "dfx {identity} canister --network {network} call {canister}",
)


def _candid_text(value: str) -> str:
    """Return a Candid text literal, safely quoted for dfx."""
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def call_extension(canister_id: str, extension_name: str, method_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Call a realm extension method via dfx and return the parsed JSON response."""
    if not canister_id:
        return {"success": False, "error": " REALM_CANISTER_ID not configured"}

    identity_flag = f"--identity {DFX_IDENTITY}" if DFX_IDENTITY else ""
    base = DFX_CALL_TEMPLATE.format(
        identity=identity_flag,
        network=DFX_NETWORK,
        canister=canister_id,
    )
    args_json = json.dumps(args)
    cmd = base.split() + [
        "extension_sync_call",
        _candid_text(extension_name),
        _candid_text(method_name),
        _candid_text(args_json),
    ]

    logger.debug(f"Running dfx command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error(f"dfx call failed: {exc.stderr}")
        return {"success": False, "error": exc.stderr}
    except json.JSONDecodeError as exc:
        logger.error(f"Could not parse dfx output: {exc}")
        return {"success": False, "error": "Invalid JSON from dfx"}


def get_pending_email_notifications(canister_id: str) -> Dict[str, Any]:
    """Fetch notifications queued for email delivery."""
    return call_extension(
        canister_id,
        "notifications",
        "get_pending_email_notifications",
        {},
    )


def mark_email_sent(
    canister_id: str,
    notification_id: str,
    success: bool,
    error: str = "",
) -> Dict[str, Any]:
    """Mark a notification's email as sent or failed."""
    return call_extension(
        canister_id,
        "notifications",
        "mark_email_sent",
        {
            "id": notification_id,
            "success": success,
            "error": error,
        },
    )
