"""
Scraper for rs.ge - the Georgian Revenue Service portal.
Uses Playwright for JS-rendered content.
Targets circulars, guidance pages, and declaration form instructions.
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from src.scraper.change_detector import compute_hash, has_changed, record_hash
from src.scraper.models import RawDocument

RS_BASE = "https://www.rs.ge"

# Seed URLs - starting points for the scraper
SEED_URLS = [
    # Individual entrepreneur section
    "https://www.rs.ge/Default.aspx?sec=10",
    # Small business guidance
    "https://www.rs.ge/Default.aspx?sec=11",
    # Tax payer information hub
    "https://www.rs.ge/Default.aspx?sec=60",
    # VAT section
    "https://www.rs.ge/Default.aspx?sec=30",
    # Declaration forms and instructions
    "https://www.rs.ge/Default.aspx?sec=40",
]

# Patterns of page URLs to follow (stay within rs.ge guidance content)
FOLLOW_PATTERNS = [
    r"rs\.ge/Default\.aspx\?.*sec=\d+",
    r"rs\.ge/[a-z]{2}/.+",
    r"rs\.ge/GovDoc/",
]

MAX_PAGES_PER_SEED = 50
PAGE_TIMEOUT = 30_000  # ms


async def _wait_and_get_html(page: Page, url: str) -> str:
    await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
    return await page.content()


def _extract_text_and_title(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")

    # Remove navigation, footer, scripts
    for tag in soup(["nav", "footer", "script", "style", "header", "aside"]):
        tag.decompose()

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Main content area (rs.ge uses .content-area or #main-content)
    main = (
        soup.find(id="main-content")
        or soup.find(class_="content-area")
        or soup.find(class_="main-content")
        or soup.find("main")
        or soup.find("body")
    )

    text = main.get_text(separator="\n", strip=True) if main else ""
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, title


def _guess_source_type(url: str, title: str) -> str:
    url_lower = url.lower()
    title_lower = title.lower()
    if "sec=40" in url_lower or "form" in title_lower or "declaration" in title_lower or "deklaraci" in title_lower:
        return "form"
    if "circular" in title_lower or "circulari" in title_lower or "განმარტება" in title_lower:
        return "circular"
    return "guidance"


def _get_last_modified_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(string=re.compile(r"\d{2}\.\d{2}\.\d{4}")):
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", tag)
        if m:
            d, mo, y = m.groups()
            return f"{y}-{mo}-{d}"
    return datetime.utcnow().strftime("%Y-%m-%d")


def _is_followable(url: str) -> bool:
    return any(re.search(p, url) for p in FOLLOW_PATTERNS)


async def scrape_rs_ge(seed_url: str, max_pages: int = MAX_PAGES_PER_SEED) -> AsyncIterator[RawDocument]:
    """
    Crawls rs.ge starting from seed_url.
    Yields a RawDocument for each unique guidance/circular/form page found.
    """
    visited: set[str] = set()
    queue: list[str] = [seed_url]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; RSHub-Scraper/1.0; research)",
            locale="ka-GE",
        )
        page = await context.new_page()

        pages_fetched = 0
        while queue and pages_fetched < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                html = await _wait_and_get_html(page, url)
            except Exception:
                continue

            pages_fetched += 1
            text, title = _extract_text_and_title(html)

            if len(text) < 100:
                # Skip near-empty pages
                pass
            else:
                content_hash = compute_hash(text)
                if has_changed(url, content_hash):
                    record_hash(url, content_hash, "guidance")
                    last_modified = _get_last_modified_from_html(html)
                    source_type = _guess_source_type(url, title)

                    yield RawDocument(
                        url=url,
                        source_type=source_type,
                        language="ka",
                        raw_html="",
                        text=text,
                        title=title,
                        last_modified=last_modified,
                        content_hash=content_hash,
                    )

            # Collect links to follow
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/"):
                    href = RS_BASE + href
                elif not href.startswith("http"):
                    continue
                if href not in visited and _is_followable(href):
                    queue.append(href)

            await asyncio.sleep(0.5)  # polite crawl delay

        await browser.close()


async def scrape_all_rs_ge() -> list[RawDocument]:
    docs: list[RawDocument] = []
    for seed in SEED_URLS:
        async for doc in scrape_rs_ge(seed):
            docs.append(doc)
    return docs
