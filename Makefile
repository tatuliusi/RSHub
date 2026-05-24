.PHONY: install install-browsers infra infra-down ingest api frontend check logs

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
	.venv/bin/pip install -e ".[dev]"
	@echo "\nDone. Activate with: source .venv/bin/activate"

install-browsers:
	.venv/bin/playwright install chromium --with-deps

# ── Infrastructure ────────────────────────────────────────────────────────────

infra:
	docker compose up -d qdrant redis
	@echo "Waiting for Qdrant and Redis to be ready..."
	@sleep 3
	@curl -sf http://localhost:6333/healthz > /dev/null && echo "Qdrant: OK" || echo "Qdrant: not ready yet"
	@docker exec rshub_redis redis-cli ping && echo "Redis: OK" || echo "Redis: not ready yet"

infra-down:
	docker compose down

# ── Data ingestion ────────────────────────────────────────────────────────────

ingest:
	PYTHONPATH=. .venv/bin/python -m src.ingestion.run

ingest-taxcode:
	PYTHONPATH=. .venv/bin/python -c "
import asyncio
from src.scraper.matsne import scrape_all_tax_code
from src.ingestion.run import ingest_documents
async def run():
    docs = await scrape_all_tax_code()
    print(f'Scraped {len(docs)} documents')
    await ingest_documents(docs)
asyncio.run(run())
"

ingest-rsge:
	PYTHONPATH=. .venv/bin/python -c "
import asyncio
from src.scraper.rs_ge import scrape_all_rs_ge
from src.ingestion.run import ingest_documents
async def run():
    docs = await scrape_all_rs_ge()
    print(f'Scraped {len(docs)} documents')
    await ingest_documents(docs)
asyncio.run(run())
"

# ── Running ───────────────────────────────────────────────────────────────────

api:
	PYTHONPATH=. .venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	PYTHONPATH=. .venv/bin/python -m src.scraper.scheduler

frontend:
	cd frontend && npm install && npm run dev

# ── Verification ──────────────────────────────────────────────────────────────

check:
	@echo "=== Infrastructure ==="
	@curl -sf http://localhost:6333/healthz > /dev/null && echo "Qdrant: running" || echo "Qdrant: NOT running"
	@docker exec rshub_redis redis-cli ping 2>/dev/null && echo "Redis: running" || echo "Redis: NOT running"
	@echo "\n=== API ==="
	@curl -sf http://localhost:8000/health | python3 -m json.tool || echo "API: NOT running"
	@echo "\n=== Qdrant collection ==="
	@curl -sf http://localhost:6333/collections/tax_chunks | python3 -m json.tool 2>/dev/null || echo "Collection 'tax_chunks': does not exist yet (run 'make ingest')"

check-index:
	@curl -sf "http://localhost:6333/collections/tax_chunks" | python3 -m json.tool

logs-api:
	docker compose logs -f api

eval:
	PYTHONPATH=. .venv/bin/python -m src.evaluation.evaluator \
		--test-set src/evaluation/test_set.json \
		--output src/evaluation/results.json
