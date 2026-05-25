"""
Critic agent: verifies the Synthesizer's draft answer.
Checks: citation grounding, source currency, coverage.
Uses Claude Haiku 4.5.
"""

import json
import logging

import anthropic

from src.agents.state import AgentState
from src.agents.prompts import CRITIC_SYSTEM, build_critic_messages
from src.config import get_settings
from src.observability import observe

log = logging.getLogger(__name__)


@observe(name="critic")
async def critic_node(state: AgentState) -> dict:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    draft = state.get("draft_answer", "")
    chunks = state.get("retrieved_chunks", [])
    sub_queries = state.get("sub_queries", [])
    iteration_count = state.get("iteration_count", 0)

    if not draft:
        return {
            "critic_verdict": "REJECTED",
            "critic_feedback": "No draft answer was generated.",
            "failed_check": "coverage",
            "iteration_count": iteration_count + 1,
        }

    messages = build_critic_messages(
        draft_answer=draft,
        chunks=chunks,
        sub_queries=sub_queries,
    )

    response = await client.messages.create(
        model=settings.critic_model,
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": CRITIC_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )

    raw = response.content[0].text.strip()

    try:
        parsed = json.loads(raw)
        verdict = parsed.get("verdict", "REJECTED")
        failed_check = parsed.get("failed_check") or ""
        reason = parsed.get("reason", "")
    except json.JSONDecodeError:
        log.warning("Critic returned invalid JSON: %s", raw[:200])
        verdict = "REJECTED"
        failed_check = "grounding"
        reason = f"Critic output could not be parsed: {raw[:200]}"

    log.info(
        "Critic verdict: %s (check: %s, iteration: %d)",
        verdict,
        failed_check or "none",
        iteration_count + 1,
    )

    return {
        "critic_verdict": verdict,
        "critic_feedback": reason,
        "failed_check": failed_check,
        "iteration_count": iteration_count + 1,
        "status": "done" if verdict == "APPROVED" else "planning",
    }
