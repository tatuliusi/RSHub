"""
Chat endpoint with SSE streaming.
Streams agent status updates in real time, then streams the final approved answer.

Event types:
  status  - pipeline step label ("Planning your question...", etc.)
  token   - one word/token of the final answer (streamed after Critic approval)
  sources - list of cited sources
  meta    - {"low_confidence": bool, "cached": bool}
  done    - end of stream
  error   - error message
"""

import asyncio
import json
import logging
from dataclasses import asdict, fields

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.agents.graph import pipeline, build_initial_state
from src.cache.semantic_cache import get_cached_response, set_cached_response

log = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: str = "default"
    conversation_history: list[dict] = []


def _sse(event_type: str, payload) -> dict:
    if isinstance(payload, str):
        data = {"type": event_type, "content": payload}
    else:
        data = {"type": event_type, **payload}
    return {"data": json.dumps(data, ensure_ascii=False)}


def _source_to_dict(source) -> dict:
    if hasattr(source, "__dataclass_fields__"):
        return asdict(source)
    if isinstance(source, dict):
        return source
    return vars(source)


def _tokenize(text: str) -> list[str]:
    """Splits text into streaming tokens (words + whitespace)."""
    tokens: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in (" ", "\n"):
            tokens.append(text[i])
            i += 1
        else:
            j = i + 1
            while j < len(text) and text[j] not in (" ", "\n"):
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


STATUS_LABELS = {
    "planning": "Planning your question...",
    "retrieving": "Searching the knowledge base...",
    "synthesizing": "Generating answer...",
    "verifying": "Verifying answer quality...",
    "done": "Answer ready",
}


async def _stream_pipeline(request: ChatRequest):
    try:
        # Semantic cache check
        cached = get_cached_response(request.query)
        if cached:
            yield _sse("status", "Retrieved from cache")
            for token in _tokenize(cached.get("answer", "")):
                yield _sse("token", token)
                await asyncio.sleep(0)
            yield _sse("sources", {"sources": cached.get("sources", [])})
            yield _sse("meta", {"low_confidence": False, "cached": True})
            yield _sse("done", "")
            return

        graph = pipeline()
        initial_state = build_initial_state(
            user_query=request.query,
            session_id=request.session_id,
            conversation_history=request.conversation_history,
        )

        prev_status = ""
        final_state = None

        # stream_mode="values" yields the complete state after each node runs
        async for state_snapshot in graph.astream(initial_state, stream_mode="values"):
            final_state = state_snapshot
            status = state_snapshot.get("status", "")

            if status and status != prev_status:
                prev_status = status
                label = STATUS_LABELS.get(status, status)
                yield _sse("status", label)

            # Notify on Critic rejection with iteration count
            iteration = state_snapshot.get("iteration_count", 0)
            verdict = state_snapshot.get("critic_verdict", "")
            if verdict == "REJECTED" and iteration > 0:
                yield _sse("status", f"Refining answer (attempt {iteration})...")

        if not final_state:
            yield _sse("error", "Pipeline did not produce a result")
            yield _sse("done", "")
            return

        answer = final_state.get("final_answer", "")
        sources = final_state.get("final_sources", [])
        low_confidence = final_state.get("low_confidence", False)

        if not answer:
            yield _sse("error", "No answer was generated")
            yield _sse("done", "")
            return

        # Stream answer tokens
        for token in _tokenize(answer):
            yield _sse("token", token)
            await asyncio.sleep(0)

        # Send sources and metadata
        sources_data = [_source_to_dict(s) for s in sources]
        yield _sse("sources", {"sources": sources_data})
        yield _sse("meta", {"low_confidence": low_confidence, "cached": False})
        yield _sse("done", "")

        # Cache high-confidence answers
        if not low_confidence:
            set_cached_response(request.query, {"answer": answer, "sources": sources_data})

    except Exception as e:
        log.exception("Pipeline error: %s", request.query[:80])
        yield _sse("error", str(e))
        yield _sse("done", "")


@router.post("/chat")
async def chat(request: ChatRequest):
    return EventSourceResponse(_stream_pipeline(request))
