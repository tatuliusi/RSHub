# Setup and Running Guide

## What you need before starting

- Python 3.11 or 3.12 (you have 3.12, that works)
- Docker Desktop running (you have it)
- Node.js 18+ (you have it)
- An Anthropic API key

---

## Step 1: Create the virtual environment and install dependencies

This is done once. The torch install is separate because it needs a specific PyTorch index URL for the CPU-only version (avoids downloading a 4GB CUDA build).

```bash
cd /home/tatuliusi/RSHub

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev]"
```

After this finishes (can take 5-10 minutes because FlagEmbedding + torch are large), install Playwright's Chromium browser:

```bash
playwright install chromium --with-deps
```

---

## Step 2: Set up your .env file

```bash
cp .env.example .env
```

Open `.env` and set your Anthropic key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Everything else has working defaults. You can leave Langfuse blank if you don't want tracing.

---

## Step 3: Start the database services

This starts Qdrant (vector database) and Redis (cache) in Docker:

```bash
docker compose up -d qdrant redis
```

Check they are running:

```bash
curl http://localhost:6333/healthz       # should return: {"title":"qdrant - Ready"}
docker exec rshub_redis redis-cli ping   # should return: PONG
```

### Where data lives

| What | Where |
|---|---|
| Vector index (all embeddings + document text) | Docker volume `qdrant_data`, managed by Docker at `/var/lib/docker/volumes/rshub_qdrant_data` |
| Semantic query cache + rate limit state | Docker volume `redis_data` |
| Scraper change detection database | `data/cache/scraper_state.db` (SQLite, created automatically) |
| BGE-M3 and reranker model weights | `~/.cache/huggingface/hub/` (downloaded on first embedding run, about 2.3GB total) |

The `data/` directory is local to the project. The Docker volumes persist between restarts. If you do `docker compose down -v` you delete the volumes and lose the index (you would need to re-ingest).

---

## Step 4: Run the scraper and ingest data into Qdrant

This scrapes the Georgian Tax Code from matsne.gov.ge and guidance from rs.ge, then chunks, embeds, and indexes everything.

```bash
# From the project root, with venv active:
PYTHONPATH=. python -m src.ingestion.run
```

What happens during ingestion:

1. **Scraper (matsne.gov.ge)**: fetches the Tax Code with httpx, parses article by article in both Georgian and English
2. **Scraper (rs.ge)**: launches a headless Chromium browser, crawls guidance pages starting from the seed URLs
3. **Change detection**: computes SHA-256 of each document's text, compares to previous run, skips unchanged documents
4. **Chunker**: creates parent chunk (full article) + child chunks (paragraphs) for each document
5. **Embedder**: BGE-M3 model generates dense (1024-dim) and sparse vectors for each child chunk. First run downloads the model (~2.3GB). This takes a few minutes.
6. **Indexer**: upserts all chunks into the Qdrant collection `tax_chunks` with full metadata

To run only one source:

```bash
# Tax Code only (faster, ~5 minutes):
PYTHONPATH=. python -c "
import asyncio
from src.scraper.matsne import scrape_all_tax_code
from src.ingestion.run import ingest_documents
async def run():
    docs = await scrape_all_tax_code()
    print(f'Scraped {len(docs)} articles')
    await ingest_documents(docs)
asyncio.run(run())
"

# rs.ge only:
PYTHONPATH=. python -c "
import asyncio
from src.scraper.rs_ge import scrape_all_rs_ge
from src.ingestion.run import ingest_documents
async def run():
    docs = await scrape_all_rs_ge()
    print(f'Scraped {len(docs)} documents')
    await ingest_documents(docs)
asyncio.run(run())
"
```

### Check how many documents are indexed

```bash
curl http://localhost:6333/collections/tax_chunks | python3 -m json.tool
```

Look for `"vectors_count"` in the response. After a full ingest you should see several hundred to a few thousand chunks.

---

## Step 5: Start the API

```bash
# With venv active, from project root:
PYTHONPATH=. uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Check it works:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"qdrant":"ok","redis":"ok"}}
```

Send a test question:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the VAT threshold for individual entrepreneurs?", "session_id": "test"}' \
  --no-buffer
```

You will see Server-Sent Events stream in the terminal: status updates, then answer tokens, then sources.

---

## Step 6: Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

---

## Running everything together (quick start after initial setup)

Once you have done setup steps 1-2 once, daily workflow is:

```bash
# Terminal 1: infrastructure
docker compose up -d qdrant redis

# Terminal 2: API (with venv active)
source .venv/bin/activate
PYTHONPATH=. uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: frontend
cd frontend && npm run dev

# Optional - Terminal 4: background scraper (runs on cron schedule)
source .venv/bin/activate
PYTHONPATH=. python -m src.scraper.scheduler
```

---

## Checking everything is working

```bash
# 1. Infrastructure
curl http://localhost:6333/healthz
docker exec rshub_redis redis-cli ping

# 2. API health
curl http://localhost:8000/health

# 3. Qdrant index stats (shows how many chunks are indexed)
curl http://localhost:6333/collections/tax_chunks | python3 -m json.tool

# 4. Full pipeline test (streams response to terminal)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the income tax rate for Small Business status in Georgia?","session_id":"test"}' \
  --no-buffer

# 5. Frontend
# Open http://localhost:3000 - you should see the chat interface
```

---

## Common problems

**"No module named X" when running python commands**
Make sure you have `source .venv/bin/activate` active and `PYTHONPATH=.` before the command.

**Qdrant collection does not exist yet**
You need to run `make ingest` or the ingestion command in Step 4. The collection is created automatically on first ingest.

**BGE-M3 model download is slow**
It downloads ~2.3GB on first use. This happens once and is cached in `~/.cache/huggingface/`. Subsequent runs load from disk in about 10-20 seconds.

**rs.ge scraper returns 0 documents**
rs.ge may have changed its HTML structure or block scrapers. Try running just the matsne.gov.ge scraper first to verify the full pipeline works, then debug rs.ge separately.

**API returns 429 Too Many Requests**
You hit the rate limit (10 requests/minute per IP). Wait 60 seconds or increase `RATE_LIMIT_PER_MINUTE` in `.env`.

---

## Running evaluation

After ingestion and with the API running:

```bash
PYTHONPATH=. python -m src.evaluation.evaluator \
  --test-set src/evaluation/test_set.json \
  --output src/evaluation/results.json
```

Results are saved to `src/evaluation/results.json`. RAGAS metrics require `pip install -e ".[eval]"` first.
