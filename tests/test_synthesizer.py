"""Unit tests for synthesizer helpers (no LLM calls)."""

import pytest
from src.agents.synthesizer import _match_citation, _extract_sources, CITATION_PATTERN
from src.agents.state import RetrievedChunk


def _make_chunk(article_number: str = "91", title: str = "VAT Registration", url: str = "https://example.com/91"):
    return RetrievedChunk(
        chunk_id="c1",
        parent_id="p1",
        text="Some legal text.",
        parent_text="",
        source="tax_code",
        language="ka",
        article_number=article_number,
        title=title,
        last_modified="2024-01-01",
        url=url,
        score=0.9,
        sub_query="test",
        status="active",
    )


class TestMatchCitation:
    def test_matches_article_number_english(self):
        chunk = _make_chunk(article_number="91")
        assert _match_citation("Tax Code, Article 91", chunk)

    def test_matches_article_number_georgian(self):
        chunk = _make_chunk(article_number="91")
        assert _match_citation("საგადასახადო კოდექსი, მუხლი 91", chunk)

    def test_no_partial_match_article_number(self):
        chunk = _make_chunk(article_number="91")
        # "Article 910" should not match article 91
        assert not _match_citation("Tax Code, Article 910", chunk)

    def test_matches_title(self):
        chunk = _make_chunk(article_number="", title="VAT Registration")
        assert _match_citation("rs.ge guidance: VAT Registration", chunk)

    def test_no_match_wrong_article(self):
        chunk = _make_chunk(article_number="91")
        assert not _match_citation("Tax Code, Article 92", chunk)

    def test_no_match_short_title(self):
        chunk = _make_chunk(article_number="", title="VAT")
        # Title length <= 3 should not match
        assert not _match_citation("rs.ge guidance: VAT", chunk)


class TestExtractSources:
    def test_extracts_cited_source(self):
        chunk = _make_chunk(article_number="91", url="https://example.com/91")
        answer = "VAT applies to all registered businesses [Tax Code, Article 91]."
        sources = _extract_sources(answer, [chunk])
        assert len(sources) == 1
        assert sources[0].article_number == "91"
        assert sources[0].url == "https://example.com/91"

    def test_deduplicates_by_url(self):
        chunk = _make_chunk(article_number="91", url="https://example.com/91")
        answer = "First claim [Tax Code, Article 91]. Second claim [Tax Code, Article 91]."
        sources = _extract_sources(answer, [chunk])
        assert len(sources) == 1

    def test_no_sources_for_uncited_chunks(self):
        chunk = _make_chunk(article_number="92", url="https://example.com/92")
        answer = "VAT applies [Tax Code, Article 91]."
        sources = _extract_sources(answer, [chunk])
        assert len(sources) == 0

    def test_skips_http_in_brackets(self):
        chunk = _make_chunk(article_number="91")
        answer = "See [https://example.com] for details [Tax Code, Article 91]."
        sources = _extract_sources(answer, [chunk])
        # Should only match article citation, not the URL bracket
        urls_in_sources = {s.url for s in sources}
        assert "https://example.com" not in urls_in_sources
