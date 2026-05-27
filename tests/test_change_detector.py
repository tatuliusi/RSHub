"""Unit tests for the change detector (SQLite-based scraper state)."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch


def test_compute_hash_deterministic():
    from src.scraper.change_detector import compute_hash
    h1 = compute_hash("hello world")
    h2 = compute_hash("hello world")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_differs_for_different_input():
    from src.scraper.change_detector import compute_hash
    assert compute_hash("text A") != compute_hash("text B")


def test_has_changed_true_for_new_url(tmp_path):
    db = tmp_path / "state.db"
    with patch("src.scraper.change_detector.DB_PATH", db):
        from src.scraper import change_detector as cd
        cd.DB_PATH = db
        assert cd.has_changed("https://example.com/new", "abc123") is True


def test_has_changed_false_for_same_hash(tmp_path):
    db = tmp_path / "state.db"
    with patch("src.scraper.change_detector.DB_PATH", db):
        from src.scraper import change_detector as cd
        cd.DB_PATH = db
        cd.record_hash("https://example.com/doc", "hash1", "tax_code")
        assert cd.has_changed("https://example.com/doc", "hash1") is False


def test_has_changed_true_after_content_update(tmp_path):
    db = tmp_path / "state.db"
    with patch("src.scraper.change_detector.DB_PATH", db):
        from src.scraper import change_detector as cd
        cd.DB_PATH = db
        cd.record_hash("https://example.com/doc", "oldhash", "tax_code")
        assert cd.has_changed("https://example.com/doc", "newhash") is True


def test_get_all_urls_by_type(tmp_path):
    db = tmp_path / "state.db"
    with patch("src.scraper.change_detector.DB_PATH", db):
        from src.scraper import change_detector as cd
        cd.DB_PATH = db
        cd.record_hash("https://a.com/1", "h1", "tax_code")
        cd.record_hash("https://a.com/2", "h2", "tax_code")
        cd.record_hash("https://b.com/1", "h3", "circular")

        tax_urls = cd.get_all_urls_by_type("tax_code")
        assert "https://a.com/1" in tax_urls
        assert "https://a.com/2" in tax_urls
        assert "https://b.com/1" not in tax_urls
