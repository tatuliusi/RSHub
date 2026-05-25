"""
Scraper for matsne.gov.ge - the Georgian legislative portal.
Uses Playwright for JS-rendered content (the document viewer renders articles dynamically).
Targets the Georgian Tax Code in both Georgian (ka) and English (en).
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import AsyncIterator

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.scraper.change_detector import compute_hash, has_changed
from src.scraper.models import RawDocument

MATSNE_BASE = "https://matsne.gov.ge"

TAX_CODE_URLS = {
    "ka": "https://matsne.gov.ge/ka/document/view/1043717",
    "en": "https://matsne.gov.ge/en/document/view/1043717",
}

PAGE_TIMEOUT = 60_000  # ms — matsne.gov.ge is slow


def _parse_articles(html: str, lang: str) -> list[dict]:
    """
    Parses rendered HTML for article-level content.
    Matsne renders the law as a flat sequence of paragraphs after JS load.
    Tries multiple container selectors; falls back to body text.
    """
    soup = BeautifulSoup(html, "lxml")

    # Try known matsne.gov.ge post-render selectors (JS fills these in)
    container = (
        soup.find("div", class_="document-text")
        or soup.find("div", class_="law-text")
        or soup.find("div", class_="document-content")
        or soup.find("div", id="documentText")
        or soup.find("div", id="lawText")
        or soup.find("main")
        or soup.find("body")
    )

    if not container:
        return []

    # Georgian: "მუხლი N" | English: "Article N"
    article_pattern = re.compile(
        r"^(მუხლი\s+\d+|Article\s+\d+)", re.IGNORECASE | re.UNICODE
    )

    articles: list[dict] = []
    current_article: dict | None = None
    current_parts: list[str] = []

    for elem in container.find_all(["h1", "h2", "h3", "h4", "p", "div", "li", "span"]):
        # Skip deeply nested elements already captured by a parent
        if elem.find_parent(["h1", "h2", "h3", "h4"]):
            continue
        text = elem.get_text(separator=" ", strip=True)
        if not text or len(text) < 3:
            continue

        match = article_pattern.match(text)
        if match:
            if current_article and current_parts:
                current_article["text"] = "\n".join(current_parts).strip()
                if len(current_article["text"]) > 50:  # skip empty stubs
                    articles.append(current_article)

            num_match = re.search(r"\d+", match.group(0))
            article_num = num_match.group(0) if num_match else ""
            current_article = {
                "article_number": article_num,
                "title": text[:200],
                "text": "",
                "lang": lang,
            }
            current_parts = [text]
        elif current_article is not None:
            current_parts.append(text)

    if current_article and current_parts:
        current_article["text"] = "\n".join(current_parts).strip()
        if len(current_article["text"]) > 50:
            articles.append(current_article)

    return articles


def _get_last_modified(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(string=re.compile(r"\d{2}\.\d{2}\.\d{4}")):
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", tag)
        if m:
            d, mo, y = m.groups()
            return f"{y}-{mo}-{d}"
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def scrape_tax_code(lang: str = "ka") -> AsyncIterator[RawDocument]:
    """Yields one RawDocument per article of the Georgian Tax Code."""
    url = TAX_CODE_URLS.get(lang, TAX_CODE_URLS["ka"])

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; RSHub-Scraper/1.0; research project)",
            locale="ka-GE" if lang == "ka" else "en-US",
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
            # Give JS document viewer extra time to populate article elements
            await page.wait_for_timeout(3000)
            html = await page.content()
        finally:
            await browser.close()

    last_modified = _get_last_modified(html)
    articles = _parse_articles(html, lang)

    if not articles:
        import logging
        logging.getLogger(__name__).warning(
            "matsne.py: no articles parsed from %s — page structure may have changed", url
        )

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
            raw_html="",
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
        await asyncio.sleep(2)
    return docs
