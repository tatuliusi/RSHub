"""
Background scheduler for periodic scraping and re-indexing.
Runs as a standalone process: python -m src.scraper.scheduler
"""

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import get_settings

log = logging.getLogger(__name__)


async def run_tax_code_ingestion() -> None:
    log.info("Starting Tax Code ingestion job")
    try:
        from src.scraper.matsne import scrape_all_tax_code
        from src.ingestion.run import ingest_documents

        docs = await scrape_all_tax_code()
        log.info("Scraped %d changed Tax Code articles", len(docs))
        if docs:
            await ingest_documents(docs)
            log.info("Ingestion complete for Tax Code")
    except Exception:
        log.exception("Tax Code ingestion job failed")


async def run_rs_ge_ingestion() -> None:
    log.info("Starting rs.ge ingestion job")
    try:
        from src.scraper.rs_ge import scrape_all_rs_ge
        from src.ingestion.run import ingest_documents

        docs = await scrape_all_rs_ge()
        log.info("Scraped %d changed rs.ge documents", len(docs))
        if docs:
            await ingest_documents(docs)
            log.info("Ingestion complete for rs.ge")
    except Exception:
        log.exception("rs.ge ingestion job failed")


async def _async_main() -> None:
    settings = get_settings()
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_tax_code_ingestion,
        CronTrigger.from_crontab(settings.scraper_tax_code_cron),
        id="tax_code",
        name="Tax Code ingestion",
        replace_existing=True,
    )

    scheduler.add_job(
        run_rs_ge_ingestion,
        CronTrigger.from_crontab(settings.scraper_rs_ge_cron),
        id="rs_ge",
        name="rs.ge ingestion",
        replace_existing=True,
    )

    scheduler.start()
    log.info("Scheduler started. Tax Code: %s, rs.ge: %s",
             settings.scraper_tax_code_cron, settings.scraper_rs_ge_cron)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        log.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
