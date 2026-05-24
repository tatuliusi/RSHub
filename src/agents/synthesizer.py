"""
Synthesizer agent: generates the answer with inline citations.
Uses Claude Sonnet 4.6 with prompt caching on the system prompt.
"""

import logging
import re
from dataclasses import asdict

import anthropic

from src.agents.state import AgentState, Source
from src.agents.prompts import SYNTHESIZER_SYSTEM, build_synthesizer_messages
from src.config import get_settings

log = logging.getLogger(__name__)

# Matches citations like [Tax Code, Article 91] or [rs.ge guidance: VAT]
CITATION_PATTERN = re.compile(r"\[([^\]]+)\]")


def _extract_sources(answer: str, chunks: list) -> list[Source]:
    """Extracts source metadata for all cited articles in the answer."""
    cited_texts = CITATION_PATTERN.findall(answer)
    sources: list[Source] = []
    seen_urls: set[str] = set()

    for chunk in chunks:
        for cited in cited_texts:
            cited_lower = cited.lower()
            if (
                chunk.article_number and chunk.article_number in cited
            ) or chunk.title.lower() in cited_lower:
                if chunk.url not in seen_urls:
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


def synthesizer_node(state: AgentState) -> dict:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

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

    response = client.messages.create(
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

    draft = response.content[0].text.strip()
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
