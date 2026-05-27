"""
Synthesizer agent: generates the answer with inline citations.
Uses Claude Sonnet 4.6 with prompt caching on the system prompt.
"""

import logging
import re
from functools import lru_cache

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.agents.state import AgentState, Source
from src.agents.prompts import SYNTHESIZER_SYSTEM, build_synthesizer_messages
from src.config import get_settings
from src.observability import observe

log = logging.getLogger(__name__)

# Matches citations like [Tax Code, Article 91] or [rs.ge guidance: VAT]
CITATION_PATTERN = re.compile(r"\[([^\]]+)\]")

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


@lru_cache(maxsize=1)
def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)


def _match_citation(cited: str, chunk) -> bool:
    """Returns True if `cited` (text inside brackets) refers to this chunk."""
    cited_lower = cited.lower()
    if chunk.article_number:
        pattern = r"(?:article|მუხლი)\s+" + re.escape(chunk.article_number) + r"\b"
        if re.search(pattern, cited_lower, re.IGNORECASE | re.UNICODE):
            return True
    if chunk.title and len(chunk.title) > 3:
        if chunk.title.lower() in cited_lower:
            return True
    return False


def _extract_sources(answer: str, chunks: list) -> list[Source]:
    """Extracts source metadata for all cited articles in the answer."""
    raw_cited = CITATION_PATTERN.findall(answer)
    cited_texts = [c for c in raw_cited if "http" not in c and len(c) > 2]

    sources: list[Source] = []
    seen_urls: set[str] = set()

    for chunk in chunks:
        for cited in cited_texts:
            if _match_citation(cited, chunk) and chunk.url not in seen_urls:
                seen_urls.add(chunk.url)
                sources.append(
                    Source(
                        article_number=chunk.article_number,
                        title=chunk.title,
                        url=chunk.url,
                        source_type=chunk.source,
                        last_modified=chunk.last_modified,
                    )
                )
    return sources


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def _call_api(messages: list[dict]) -> str:
    settings = get_settings()
    response = await _get_client().messages.create(
        model=settings.synthesizer_model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYNTHESIZER_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    return response.content[0].text.strip()


@observe(name="synthesizer")
async def synthesizer_node(state: AgentState) -> dict:
    sub_queries = state.get("sub_queries", [])
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        log.warning("Synthesizer called with no retrieved chunks")
        return {
            "draft_answer": "I could not find relevant information in the knowledge base to answer your question.",
            "sources": [],
            "status": "verifying",
        }

    messages = build_synthesizer_messages(
        user_query=state["user_query"],
        sub_queries=sub_queries,
        chunks=chunks,
    )

    draft = await _call_api(messages)
    sources = _extract_sources(draft, chunks)

    log.info(
        "Synthesizer: generated %d-char answer with %d sources",
        len(draft),
        len(sources),
    )

    return {
        "draft_answer": draft,
        "sources": sources,
        "status": "verifying",
    }
