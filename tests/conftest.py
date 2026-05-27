"""
Test configuration.
Stubs out heavy external dependencies so pure-function unit tests can run
without the full project stack installed (no Redis, Qdrant, Anthropic, torch, etc.).
Integration tests that actually need these modules should be placed in a
separate tests/integration/ directory and skipped in CI when deps are absent.
"""

import sys
from unittest.mock import MagicMock

_HEAVY_DEPS = [
    "anthropic",
    "redis",
    "redis.asyncio",
    "langfuse",
    "langfuse.decorators",
    "langgraph",
    "langgraph.graph",
    "qdrant_client",
    "qdrant_client.models",
    "FlagEmbedding",
    "torch",
    "apscheduler",
    "apscheduler.schedulers.asyncio",
    "apscheduler.triggers.cron",
    "playwright",
    "bs4",
    "lxml",
    "tenacity",
    "pydantic_settings",
    "fastapi",
    "sse_starlette",
    "sse_starlette.sse",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.base",
]

for _mod in _HEAVY_DEPS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# tenacity needs special treatment: @retry must return a decorator
import tenacity as _tenacity_stub
_tenacity_stub.retry = lambda *a, **kw: (lambda f: f)
_tenacity_stub.stop_after_attempt = MagicMock(return_value=None)
_tenacity_stub.wait_exponential = MagicMock(return_value=None)
_tenacity_stub.retry_if_exception_type = MagicMock(return_value=None)
