"""Environment-driven settings shared by the API and the Streamlit UI.

Values are read when called, so callers must load `.env` first. Local runs keep
the development defaults; production is selected with `APP_ENV=production`.
"""

import os

DEFAULT_INNGEST_URL = "http://127.0.0.1:8288"

# Needed before a production process may accept work, with what each one is for.
PRODUCTION_REQUIREMENTS = {
    "OPENAI_API_KEY": "embeddings and written answers",
    "INNGEST_EVENT_KEY": "sending events to the workflow server",
    "INNGEST_SIGNING_KEY": "verifying requests between Inngest and this app",
    "INNGEST_BASE_URL": "the address of the workflow server",
    "QDRANT_URL": "the Qdrant server (local file storage is for development)",
}


def is_production() -> bool:
    """True when APP_ENV=production, which turns on request signing and checks."""
    return os.getenv("APP_ENV", "development").strip().lower() == "production"


def inngest_url() -> str:
    """Address of the Inngest server, used to send events and read run status."""
    configured = os.getenv("INNGEST_BASE_URL") or os.getenv("INNGEST_DEV_SERVER_URL")
    return (configured or DEFAULT_INNGEST_URL).strip().rstrip("/")


def missing_production_settings() -> list[str]:
    """List unset production settings; empty outside production."""
    if not is_production():
        return []
    return [
        f"{name} ({purpose})"
        for name, purpose in PRODUCTION_REQUIREMENTS.items()
        if not (os.getenv(name) or "").strip()
    ]


def require_production_settings() -> None:
    """Stop startup with one clear message instead of failing later mid-workflow."""
    missing = missing_production_settings()
    if missing:
        raise RuntimeError(
            "APP_ENV=production requires these settings: " + "; ".join(missing)
        )
