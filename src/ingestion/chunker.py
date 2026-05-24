"""
Parent-child chunking strategy.

Parent chunk: one full article or guidance section (stored for context retrieval).
Child chunk: one paragraph/sub-article (embedded and indexed for search).

Each child stores a parent_id so the pipeline can fetch surrounding context
when a child is retrieved.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Literal

from src.scraper.models import RawDocument

MAX_CHILD_TOKENS_APPROX = 400  # rough token estimate via word count * 1.3
MIN_CHILD_CHARS = 80


@dataclass
class Chunk:
    chunk_id: str
    parent_id: str
    text: str
    is_parent: bool
    source: Literal["tax_code", "circular", "form", "guidance"]
    language: Literal["ka", "en"]
    article_number: str
    title: str
    last_modified: str
    url: str
    status: Literal["active", "superseded"] = "active"
    doc_hash: str = ""
    extra_meta: dict = field(default_factory=dict)


def _split_into_paragraphs(text: str) -> list[str]:
    """
    Splits text into paragraph-level chunks.
    Tries to keep legal sub-articles together (lines starting with numbers like "1.", "1.1.").
    """
    # Split on double newlines first
    raw_parts = re.split(r"\n{2,}", text.strip())
    paragraphs: list[str] = []
    current = []
    current_len = 0

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue

        part_words = len(part.split())
        approx_tokens = int(part_words * 1.3)

        if current_len + approx_tokens > MAX_CHILD_TOKENS_APPROX and current:
            merged = "\n\n".join(current)
            if len(merged) >= MIN_CHILD_CHARS:
                paragraphs.append(merged)
            current = [part]
            current_len = approx_tokens
        else:
            current.append(part)
            current_len += approx_tokens

    if current:
        merged = "\n\n".join(current)
        if len(merged) >= MIN_CHILD_CHARS:
            paragraphs.append(merged)

    return paragraphs


def chunk_document(doc: RawDocument) -> list[Chunk]:
    """
    Returns a list of Chunk objects for a single RawDocument.
    Always includes one parent chunk (full text) and N child chunks (paragraphs).
    """
    parent_id = str(uuid.uuid4())
    chunks: list[Chunk] = []

    parent_chunk = Chunk(
        chunk_id=parent_id,
        parent_id=parent_id,
        text=doc.text,
        is_parent=True,
        source=doc.source_type,
        language=doc.language,
        article_number=doc.article_number,
        title=doc.title,
        last_modified=doc.last_modified,
        url=doc.url,
        doc_hash=doc.content_hash,
    )
    chunks.append(parent_chunk)

    paragraphs = _split_into_paragraphs(doc.text)
    if not paragraphs:
        paragraphs = [doc.text]

    for para in paragraphs:
        if len(para.strip()) < MIN_CHILD_CHARS:
            continue
        child_id = str(uuid.uuid4())
        chunks.append(
            Chunk(
                chunk_id=child_id,
                parent_id=parent_id,
                text=para,
                is_parent=False,
                source=doc.source_type,
                language=doc.language,
                article_number=doc.article_number,
                title=doc.title,
                last_modified=doc.last_modified,
                url=doc.url,
                doc_hash=doc.content_hash,
            )
        )

    return chunks


def chunk_documents(docs: list[RawDocument]) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))
    return all_chunks
