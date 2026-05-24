import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/cache/scraper_state.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_hashes (
            url TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            source_type TEXT
        )
        """
    )
    conn.commit()
    return conn


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def has_changed(url: str, new_hash: str) -> bool:
    """Returns True if the document is new or its content changed."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT content_hash FROM document_hashes WHERE url = ?", (url,)
    ).fetchone()
    conn.close()
    if row is None:
        return True
    return row[0] != new_hash


def record_hash(url: str, content_hash: str, source_type: str = "") -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO document_hashes (url, content_hash, last_seen, source_type)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            content_hash = excluded.content_hash,
            last_seen = excluded.last_seen
        """,
        (url, content_hash, datetime.utcnow().isoformat(), source_type),
    )
    conn.commit()
    conn.close()


def get_all_urls_by_type(source_type: str) -> list[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT url FROM document_hashes WHERE source_type = ?", (source_type,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]
