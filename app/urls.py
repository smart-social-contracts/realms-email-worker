"""URL helpers for email notification links."""

import os
import re
from typing import Any, Dict, Optional

_RAW_ICP0_LOGO_RE = re.compile(
    r"^https://([a-z0-9-]+)\.raw\.icp0\.io(?:/|$)",
    re.IGNORECASE,
)


def absolute_href(href: str, base_url: str) -> str:
    """Return an absolute URL for email links.

    - empty href → ""
    - already http:// or https:// → unchanged
    - relative path → joined with base_url (no trailing slash on base)
    - if no base_url, return href unchanged
    """
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if not base_url:
        return href
    base = base_url.rstrip("/")
    path = href if href.startswith("/") else f"/{href}"
    return f"{base}{path}"


def _base_url_from_logo_url(logo_url: str) -> str:
    match = _RAW_ICP0_LOGO_RE.match((logo_url or "").strip())
    if not match:
        return ""
    return f"https://{match.group(1)}.icp0.io"


def resolve_email_base_url(
    email_config: Dict[str, Any],
    notification: Optional[Dict[str, Any]] = None,
) -> str:
    """Resolve the public realm base URL for email links.

    Priority:
    1. REALM_PUBLIC_URL env (trailing slash stripped)
    2. email_config["base_url"]
    3. Derive from email_config or notification logo_url on *.raw.icp0.io
    """
    env_url = os.environ.get("REALM_PUBLIC_URL", "").strip().rstrip("/")
    if env_url:
        return env_url

    config_url = str(email_config.get("base_url") or "").strip().rstrip("/")
    if config_url:
        return config_url

    for logo_url in (
        email_config.get("logo_url", ""),
        (notification or {}).get("logo_url", ""),
    ):
        derived = _base_url_from_logo_url(str(logo_url or ""))
        if derived:
            return derived

    return ""
