"""Unit tests for the chunker module."""

import pytest
from src.ingestion.chunker import chunk_document, _split_into_paragraphs, MIN_CHILD_CHARS
from src.scraper.models import RawDocument


def _make_doc(text: str, article_number: str = "91") -> RawDocument:
    return RawDocument(
        url="https://example.com/article/91",
        source_type="tax_code",
        language="ka",
        raw_html="",
        text=text,
        title="Test Article",
        last_modified="2024-01-01",
        content_hash="abc123",
        article_number=article_number,
    )


def test_chunk_document_always_produces_parent():
    doc = _make_doc("Short article text.")
    chunks = chunk_document(doc)
    parents = [c for c in chunks if c.is_parent]
    assert len(parents) == 1
    assert parents[0].text == doc.text


def test_chunk_document_parent_child_relationship():
    long_text = "\n\n".join([f"Paragraph {i}: " + "word " * 50 for i in range(10)])
    doc = _make_doc(long_text)
    chunks = chunk_document(doc)

    parent = next(c for c in chunks if c.is_parent)
    children = [c for c in chunks if not c.is_parent]

    assert len(children) >= 1
    for child in children:
        assert child.parent_id == parent.chunk_id
        assert child.chunk_id != parent.chunk_id


def test_chunk_document_skips_short_paragraphs():
    text = "Valid paragraph with enough content.\n\nX\n\nAnother valid paragraph here with sufficient length."
    doc = _make_doc(text)
    chunks = chunk_document(doc)
    children = [c for c in chunks if not c.is_parent]
    for child in children:
        assert len(child.text.strip()) >= MIN_CHILD_CHARS


def test_chunk_document_metadata_propagated():
    doc = _make_doc("Some text about tax obligations.", article_number="42")
    chunks = chunk_document(doc)
    for chunk in chunks:
        assert chunk.article_number == "42"
        assert chunk.source == "tax_code"
        assert chunk.language == "ka"
        assert chunk.url == doc.url
        assert chunk.last_modified == doc.last_modified


def test_split_into_paragraphs_empty():
    assert _split_into_paragraphs("") == []


def test_split_into_paragraphs_single_block():
    text = "word " * 30  # ~30 words, under token limit
    result = _split_into_paragraphs(text)
    assert len(result) == 1


def test_split_into_paragraphs_respects_double_newlines():
    # Each block needs to exceed MIN_CHILD_CHARS (80) individually or in merged form
    block = "word " * 20  # ~100 chars
    text = f"{block}\n\n{block}\n\n{block}"
    result = _split_into_paragraphs(text)
    assert len(result) >= 1


def test_chunk_documents_multiple_docs():
    from src.ingestion.chunker import chunk_documents
    docs = [_make_doc(f"Article {i} " + "content " * 20) for i in range(3)]
    all_chunks = chunk_documents(docs)
    parents = [c for c in all_chunks if c.is_parent]
    assert len(parents) == 3
