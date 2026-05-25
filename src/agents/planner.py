"""
Planner agent: decomposes the user's question into retrievable sub-queries.
Uses Claude Haiku 4.5 with prompt caching on the system prompt.
"""

import json
import logging

import anthropic

from src.agents.state import AgentState, SubQuery
from src.agents.prompts import PLANNER_SYSTEM, build_planner_messages
from src.config import get_settings

log = logging.getLogger(__name__)


async def planner_node(state: AgentState) -> dict:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = build_planner_messages(
        user_query=state["user_query"],
        conversation_history=state.get("conversation_history", []),
        critic_feedback=state.get("critic_feedback", ""),
        failed_check=state.get("failed_check", ""),
    )

    response = await client.messages.create(
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

    raw = response.content[0].text.strip()

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
