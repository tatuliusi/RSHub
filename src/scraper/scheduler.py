"""
Background scheduler for periodic scraping and re-indexing.
Runs as a standalone process: python -m src.scraper.scheduler
"""

import asyncio
import logging
import signal
import sys

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


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_tax_code_ingestion,
        CronTrigger.from_crontab(settings.scraper_tax_code_cron if hasattr(settings, "scraper_tax_code_cron") else "0 2 * * *"),
        id="tax_code",
        name="Tax Code ingestion",
        replace_existing=True,
    )

    scheduler.add_job(
        run_rs_ge_ingestion,
        CronTrigger.from_crontab(settings.scraper_rs_ge_cron if hasattr(settings, "scraper_rs_ge_cron") else "0 */6 * * *"),
        id="rs_ge",
        name="rs.ge ingestion",
        replace_existing=True,
    )

    scheduler.start()
    log.info("Scheduler started. Tax Code: daily at 02:00, rs.ge: every 6 hours.")

    loop = asyncio.get_event_loop()

    def _shutdown(sig, frame):
        log.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
