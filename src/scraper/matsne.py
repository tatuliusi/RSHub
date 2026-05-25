"""
Scraper for matsne.gov.ge - the Georgian legislative portal.
Uses httpx (async HTTP) + BeautifulSoup for parsing static HTML.
Targets the Georgian Tax Code in both Georgian (ka) and English (en).
"""

import asyncio
import re
from datetime import datetime
from typing import AsyncIterator

import httpx
from bs4 import BeautifulSoup

from src.scraper.change_detector import compute_hash, has_changed
from src.scraper.models import RawDocument

MATSNE_BASE = "https://matsne.gov.ge"

# Tax Code document IDs on matsne.gov.ge
TAX_CODE_URLS = {
    "ka": "https://matsne.gov.ge/ka/document/view/1043717",
    "en": "https://matsne.gov.ge/en/document/view/1043717",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RSHub-Scraper/1.0; research project)",
    "Accept-Language": "ka,en;q=0.9",
}


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    resp = await client.get(url, timeout=30.0)
    resp.raise_for_status()
    return resp.text


def _parse_article_pages(soup: BeautifulSoup, lang: str) -> list[dict]:
    """
    Matsne serves the full law as a single paginated HTML document.
    Each top-level section maps to a chapter, each article is a <div> or <article>.
    Returns a list of {article_number, title, text, url}.
    """
    articles = []

    # The law text is inside .law-text or .document-content container
    container = soup.find(class_="law-text") or soup.find(class_="document-content") or soup.find("article")
    if not container:
        # Fallback: grab the largest text block
        container = soup.find("body")

    # Look for article markers - Georgian: "მუხლი N" / English: "Article N"
    article_pattern = re.compile(
        r"(მუხლი\s+\d+|Article\s+\d+)", re.IGNORECASE | re.UNICODE
    )

    current_article: dict | None = None
    current_text_parts: list[str] = []

    for elem in container.find_all(["h1", "h2", "h3", "h4", "p", "div", "li"]):
        text = elem.get_text(separator=" ", strip=True)
        if not text:
            continue

        match = article_pattern.match(text)
        if match:
            if current_article and current_text_parts:
                current_article["text"] = "\n".join(current_text_parts).strip()
                articles.append(current_article)

            # Extract article number
            num_match = re.search(r"\d+", match.group(0))
            article_num = num_match.group(0) if num_match else ""

            current_article = {
                "article_number": article_num,
                "title": text[:200],
                "text": "",
                "lang": lang,
            }
            current_text_parts = [text]
        elif current_article is not None:
            current_text_parts.append(text)

    # Flush last article
    if current_article and current_text_parts:
        current_article["text"] = "\n".join(current_text_parts).strip()
        articles.append(current_article)

    return articles


def _get_last_modified(soup: BeautifulSoup) -> str:
    """Extract the last amendment date from the matsne page."""
    # Matsne shows "შეიცვალა: DD.MM.YYYY" or similar
    for tag in soup.find_all(string=re.compile(r"\d{2}\.\d{2}\.\d{4}")):
        date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", tag)
        if date_match:
            d, m, y = date_match.groups()
            return f"{y}-{m}-{d}"
    return datetime.utcnow().strftime("%Y-%m-%d")


async def scrape_tax_code(lang: str = "ka") -> AsyncIterator[RawDocument]:
    """Yields one RawDocument per article of the Georgian Tax Code."""
    url = TAX_CODE_URLS.get(lang, TAX_CODE_URLS["ka"])

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        html = await _fetch(client, url)
        soup = BeautifulSoup(html, "lxml")
        last_modified = _get_last_modified(soup)
        articles = _parse_article_pages(soup, lang)

        for art in articles:
            full_text = art["text"]
            content_hash = compute_hash(full_text)
            article_url = f"{url}#article-{art['article_number']}"

            if not has_changed(article_url, content_hash):
                continue

            yield RawDocument(
                url=article_url,
                source_type="tax_code",
                language=lang,
                raw_html="",  # not stored for size reasons
                text=full_text,
                title=art["title"],
                last_modified=last_modified,
                content_hash=content_hash,
                article_number=art["article_number"],
            )


async def scrape_all_tax_code() -> list[RawDocument]:
    """Scrapes both Georgian and English versions of the Tax Code."""
    docs: list[RawDocument] = []
    for lang in ("ka", "en"):
        async for doc in scrape_tax_code(lang):
            docs.append(doc)
        await asyncio.sleep(1)  # polite delay between language versions
    return docs
