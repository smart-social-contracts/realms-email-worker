"""Load and render HTML email templates with Jinja2.

Default templates are stored as files in the worker repo. Realms can optionally
override templates via their manifest_data, but the file-based defaults keep
large HTML payloads out of the canister.
"""

import logging
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_template_string(template_content: str, variables: Dict[str, Any]) -> str:
    """Render a Jinja2 template string with variables."""
    template = jinja_env.from_string(template_content)
    return template.render(**variables)


def load_template_file(event_type: str) -> str:
    """Load the HTML template file for an event type, falling back to default."""
    template_path = TEMPLATES_DIR / f"{event_type}.html"
    if not template_path.exists():
        template_path = TEMPLATES_DIR / "default.html"
    if not template_path.exists():
        logger.warning(f"No HTML template found, using empty fallback for {event_type}")
        return ""
    return template_path.read_text(encoding="utf-8")


def get_template(event_type: str, email_config: Dict[str, Any]) -> str:
    """Return the HTML template for an event type.

    Order of preference:
    1. Per-event override from realm config.
    2. Default override from realm config.
    3. File-based template from the worker repo.
    """
    templates = email_config.get("templates") or {}
    event_template = templates.get(event_type, {})
    default_template = templates.get("default", {})

    if event_template.get("html"):
        return event_template["html"]
    if default_template.get("html"):
        return default_template["html"]

    return load_template_file(event_type)


def render_email(
    event_type: str,
    email_config: Dict[str, Any],
    notification: Dict[str, Any],
) -> Dict[str, str]:
    """Render the subject, text, and HTML bodies for a notification."""
    templates = email_config.get("templates") or {}
    event_template = templates.get(event_type, {})
    default_template = templates.get("default", {})

    subject_template = event_template.get("subject") or default_template.get("subject") or notification.get("title", "Realms notification")
    text_template = event_template.get("text") or default_template.get("text") or notification.get("message", "")

    html_template = get_template(event_type, email_config)
    if not html_template:
        html_template = "<p>{{ message }}</p><p><a href=\"{{ href }}\">Open in Realms</a></p>"

    variables = {
        "title": notification.get("title", ""),
        "message": notification.get("message", ""),
        "href": notification.get("href", ""),
        "logo_url": notification.get("logo_url", ""),
        "realm_name": email_config.get("from_name", "Realms GOS"),
        "from_address": email_config.get("from_address", ""),
    }

    return {
        "subject": render_template_string(subject_template, variables),
        "text": render_template_string(text_template, variables),
        "html": render_template_string(html_template, variables),
    }
