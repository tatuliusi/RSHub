# RSHub: Multi-Agent Tax RAG System

## What This Project Is

RSHub is a multi-agent RAG (Retrieval-Augmented Generation) system for Georgian tax consultation. It is aimed at Individual Entrepreneurs and small businesses in Georgia who struggle to navigate the fragmented, frequently updated information across the Revenue Service portal (rs.ge) and the Georgian Tax Code on matsne.gov.ge.

The system answers tax questions in Georgian and English with inline source citations, so every factual claim in the response is traceable back to a specific article, circular, or form. A Critic agent validates each answer before it reaches the user, triggering regeneration if citations are wrong or source documents are outdated.

This is a bachelor's thesis project at the Business and Technology University of Georgia (BTU), built by Tatia Gabunia and Demetri Natidze.

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Agent orchestration | LangGraph | Supports cyclic graphs for the Critic retry loop, explicit state management |
| LLM: Planner + Critic | Claude Haiku 4.5 | Structured decomposition and verification tasks; cost-efficient |
| LLM: Synthesizer | Claude Sonnet 4.6 | Complex answer generation with inline citations; quality matters here |
| Embeddings | BGE-M3 (FlagEmbedding) | Best multilingual embedding model with Georgian support, 8192-token context |
| Reranker | bge-reranker-v2-m3 | Cross-encoder companion to BGE-M3; significantly improves precision at top-K |
| Vector store | Qdrant | Native hybrid (dense + sparse) search, runs locally in Docker |
| Semantic cache | Redis | Caches embedding lookups and similar-query results to cut latency and API cost |
| Scraping | Playwright + BeautifulSoup | Both rs.ge and matsne.gov.ge use JS-rendered content; Playwright fetches, BS4 parses |
| Ingestion scheduler | APScheduler | Periodic re-scraping with change detection |
| Backend API | FastAPI (async) | SSE streaming, OpenAPI schema, async agent execution |
| Frontend | Next.js 14 + Tailwind | Progressive response streaming, agent trace visualization |
| Observability | Langfuse | Traces every LLM call and agent step with latency and token counts |
| Deployment | Docker Compose | Single-command local setup |

## Project Structure

```
RSHub/
├── CLAUDE.md
├── docs/
│   └── architecture.md          # Full architecture document
├── src/
│   ├── scraper/
│   │   ├── rs_ge.py             # Playwright scraper for rs.ge
│   │   ├── matsne.py            # Playwright scraper for matsne.gov.ge (JS document viewer)
│   │   ├── scheduler.py         # APScheduler setup
│   │   └── change_detector.py  # SHA-256 hash comparison for re-indexing
│   ├── ingestion/
│   │   ├── chunker.py           # Article-level + parent-child chunking
│   │   ├── embedder.py          # BGE-M3 batch embedding
│   │   └── indexer.py           # Qdrant upsert with metadata
│   ├── retrieval/
│   │   ├── searcher.py          # Qdrant hybrid search (dense + sparse)
│   │   └── reranker.py          # bge-reranker-v2-m3 cross-encoder
│   ├── agents/
│   │   ├── planner.py           # Query decomposition into sub-queries
│   │   ├── retriever_agent.py   # Parallel retrieval per sub-query, accumulates across retries
│   │   ├── synthesizer.py       # Answer generation with citations
│   │   ├── critic.py            # Citation + currency + coverage checks
│   │   ├── graph.py             # LangGraph state machine definition
│   │   ├── prompts.py           # System prompts for all agents
│   │   └── state.py             # AgentState TypedDict and dataclasses
│   ├── api/
│   │   ├── main.py              # FastAPI app with SSE endpoint
│   │   ├── routes/
│   │   │   ├── chat.py          # POST /chat (SSE streaming)
│   │   │   └── health.py        # GET /health
│   │   └── middleware/
│   │       └── rate_limit.py    # Redis-based rate limiting
│   ├── cache/
│   │   └── semantic_cache.py    # Redis + BGE-M3 query deduplication (session-partitioned)
│   ├── observability.py         # Langfuse @observe re-export + init
│   └── evaluation/
│       ├── test_set.json        # 50 hand-crafted questions with reference answers
│       └── evaluator.py         # RAGAS + citation_correctness scoring
├── frontend/                    # Next.js 14 app
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Getting Started (Local)

```bash
# Copy env template
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and LANGFUSE_* keys

# Start infrastructure (Qdrant, Redis)
docker compose up -d qdrant redis

# Install Python dependencies
pip install -e ".[dev]"

# Run ingestion (scrape + embed + index)
python -m src.ingestion.run

# Start API
uvicorn src.api.main:app --reload

# Start frontend
cd frontend && npm install && npm run dev
```

## Key Environment Variables

```
ANTHROPIC_API_KEY=
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
BGE_M3_DEVICE=cpu        # or cuda
MAX_CRITIC_ITERATIONS=3
HYBRID_ALPHA=0.65        # weight for dense vs sparse (0=sparse only, 1=dense only)
TOP_K_RETRIEVAL=20       # initial retrieval count before reranking
TOP_K_FINAL=5            # final count after reranking
```

## Agent Flow Summary

```
User query
  -> semantic cache check (session-partitioned, BGE-M3 similarity ≥ 0.92 → return cached)
  -> Planner (Haiku 4.5): decomposes into sub-queries
  -> [Retriever x N] (parallel, thread pool): hybrid search + rerank per sub-query
       accumulates chunks across retries (does not discard prior results)
  -> Synthesizer (Sonnet 4.6): generates answer with inline citations
  -> Critic (Haiku 4.5): checks citation grounding, source currency, sub-query coverage
       uses real chunk status field (not hardcoded "active")
     - APPROVED -> stream response to user
     - REJECTED -> back to Planner with error context (max 3 iterations → fail_safe)
```

All LLM nodes are `async def` using `AsyncAnthropic` so the event loop is never blocked.
All three nodes are wrapped with Langfuse `@observe` for tracing (no-op if keys not set).

## Evaluation

Run RAGAS evaluation against the 50-question test set:

```bash
python -m src.evaluation.evaluator --test-set src/evaluation/test_set.json
```

Metrics: faithfulness, answer_relevancy, context_precision, context_recall, citation_correctness (custom).
