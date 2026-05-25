from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


@dataclass
class RawDocument:
    url: str
    source_type: Literal["tax_code", "circular", "form", "guidance"]
    language: Literal["ka", "en"]
    raw_html: str
    text: str
    title: str
    last_modified: str
    content_hash: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    article_number: str = ""
    extra_meta: dict = field(default_factory=dict)
