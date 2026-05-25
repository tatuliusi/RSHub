"""
Langfuse observability setup.
Initialises the Langfuse client when API keys are present; is a no-op otherwise.
Import `observe` from here to decorate agent functions.
"""

from langfuse.decorators import observe  # noqa: F401 — re-exported for agents

from src.config import get_settings


def init_langfuse() -> None:
    """Called at API startup to validate Langfuse credentials and log the status."""
    import logging

    settings = get_settings()
    log = logging.getLogger(__name__)

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        # Langfuse SDK reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
        # automatically from env — we just confirm the keys are present.
        log.info("Langfuse observability enabled (host: %s)", settings.langfuse_host)
    else:
        log.warning(
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — tracing disabled. "
            "Set them in .env to enable observability."
        )
