"""
Planner agent: decomposes the user's question into retrievable sub-queries.
Uses Claude Haiku 4.5 with prompt caching on the system prompt.
"""

import json
import logging
from functools import lru_cache

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.agents.state import AgentState, SubQuery
from src.agents.prompts import PLANNER_SYSTEM, build_planner_messages
from src.config import get_settings
from src.observability import observe

log = logging.getLogger(__name__)

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


@lru_cache(maxsize=1)
def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def _call_api(messages: list[dict]) -> str:
    settings = get_settings()
    response = await _get_client().messages.create(
        model=settings.planner_model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": PLANNER_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    return response.content[0].text.strip()


@observe(name="planner")
async def planner_node(state: AgentState) -> dict:
    messages = build_planner_messages(
        user_query=state["user_query"],
        conversation_history=state.get("conversation_history", []),
        critic_feedback=state.get("critic_feedback", ""),
        failed_check=state.get("failed_check", ""),
    )

    raw = await _call_api(messages)

    try:
        parsed = json.loads(raw)
        sub_queries = [
            SubQuery(
                query=sq["query"],
                source_hint=sq.get("source_hint", "any"),
                priority=sq.get("priority", 1),
            )
            for sq in parsed["sub_queries"]
        ]
        log.info(
            "Planner: decomposed into %d sub-queries (iteration %d)",
            len(sub_queries),
            state.get("iteration_count", 0),
        )
    except (json.JSONDecodeError, KeyError) as e:
        log.warning("Planner returned invalid JSON, using raw query as single sub-query: %s", e)
        sub_queries = [SubQuery(query=state["user_query"], source_hint="any")]

    return {
        "sub_queries": sub_queries,
        "status": "retrieving",
    }
