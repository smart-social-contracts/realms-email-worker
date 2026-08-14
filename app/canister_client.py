"""Call Realms extension methods on a canister from the off-chain worker.

This module uses the ``dfx`` CLI by default. You can override the command
template via the ``EMAIL_WORKER_DFX_CALL_TEMPLATE`` environment variable if
you need a custom IC agent or remote node setup.
"""

import json
import logging
import os
import subprocess
from typing import Any, Dict

logger = logging.getLogger(__name__)

REALM_CANISTER_ID = os.environ.get("REALM_CANISTER_ID", "")
DFX_IDENTITY = os.environ.get("DFX_IDENTITY", "")
DFX_NETWORK = os.environ.get("DFX_NETWORK", "local")
DFX_CALL_TEMPLATE = os.environ.get(
    "EMAIL_WORKER_DFX_CALL_TEMPLATE",
    "dfx --run-deprecated {identity} canister --network {network} call --output json {canister}",
)
CANISTER_CANDID_PATH = os.environ.get(
    "CANISTER_CANDID_PATH",
    "/srv/dev/realms/src/realm_backend/realm_backend.did",
)


def _candid_text(value: str) -> str:
    """Return a Candid text literal, safely quoted for dfx."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _parse_extension_output(stdout: str) -> Dict[str, Any]:
    """Unwrap dfx JSON ``{success, response}`` into the extension payload."""
    outer = json.loads(stdout)
    if not isinstance(outer, dict):
        return {"success": False, "error": "Unexpected dfx JSON"}
    if outer.get("success") is False:
        return outer
    response = outer.get("response", outer)
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            return {"success": False, "error": response}
    if isinstance(response, dict):
        return response
    return {"success": True, "data": response}


def call_extension(
    canister_id: str,
    extension_name: str,
    method_name: str,
    args: Dict[str, Any],
    query: bool = False,
) -> Dict[str, Any]:
    """Call a realm extension method via dfx and return the parsed JSON response."""
    if not canister_id:
        return {"success": False, "error": "REALM_CANISTER_ID not configured"}

    identity_flag = f"--identity {DFX_IDENTITY}" if DFX_IDENTITY else ""
    # `--query` is a flag on `call`, so it must sit before the canister id:
    #   dfx ... call --output json --query CANISTER extension_call ...
    canister_token = f"--query {canister_id}" if query else canister_id
    base = DFX_CALL_TEMPLATE.format(
        identity=identity_flag,
        network=DFX_NETWORK,
        canister=canister_token,
    )
    method = "extension_call" if query else "extension_sync_call"
    candid_arg = (
        f"({_candid_text(extension_name)}, "
        f"{_candid_text(method_name)}, "
        f"{_candid_text(json.dumps(args))})"
    )
    cmd = base.split() + [method, candid_arg]

    env = os.environ.copy()
    env.setdefault("TERM", "xterm")
    env.setdefault("DFX_WARNING", "-mainnet_plaintext_identity")
    if CANISTER_CANDID_PATH:
        env.setdefault("CANISTER_CANDID_PATH", CANISTER_CANDID_PATH)

    logger.debug(f"Running dfx command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
            env=env,
            cwd=os.environ.get("DFX_PROJECT_ROOT", "/srv/dev/realms"),
        )
        return _parse_extension_output(result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error(f"dfx call failed: {exc.stderr}")
        return {"success": False, "error": exc.stderr}
    except json.JSONDecodeError as exc:
        logger.error(f"Could not parse dfx output: {exc}")
        return {"success": False, "error": "Invalid JSON from dfx"}


def get_email_config(canister_id: str) -> Dict[str, Any]:
    """Fetch the realm's email configuration."""
    return call_extension(
        canister_id,
        "realm_settings",
        "get_email_config",
        {},
        query=True,
    )


def get_pending_email_notifications(canister_id: str) -> Dict[str, Any]:
    """Fetch notifications queued for email delivery."""
    return call_extension(
        canister_id,
        "notifications",
        "get_pending_email_notifications",
        {},
        query=True,
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
