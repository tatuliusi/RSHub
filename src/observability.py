"""
Langfuse observability setup.
Supports langfuse 2.x (langfuse.decorators) and 3.x (langfuse top-level).
Falls back to a no-op @observe decorator if langfuse is not installed or
keys are not configured, so the rest of the code never needs to change.
"""

import functools
import logging


def _noop_observe(*args, **kwargs):
    """No-op observe decorator used when Langfuse is unavailable."""
    if args and callable(args[0]):
        # Used as @observe without arguments
        return args[0]
    # Used as @observe(name="...") — return decorator
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*a, **kw):
            return await func(*a, **kw)
        return wrapper
    return decorator


try:
    from langfuse.decorators import observe  # langfuse 2.x
except ImportError:
    try:
        from langfuse import observe  # langfuse 3.x
    except ImportError:
        observe = _noop_observe  # type: ignore[assignment]


def init_langfuse() -> None:
    """Called at API startup to validate Langfuse credentials and log the status."""
    from src.config import get_settings
    settings = get_settings()
    log = logging.getLogger(__name__)

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        log.info("Langfuse observability enabled (host: %s)", settings.langfuse_host)
    else:
        log.warning(
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — tracing disabled."
        )
