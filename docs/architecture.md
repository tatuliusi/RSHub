# System Architecture: RSHub Multi-Agent Tax RAG

## 1. Overview

RSHub answers Georgian tax questions by combining a live knowledge base of official documents with a multi-agent pipeline that plans, retrieves, synthesizes, and verifies before returning anything to the user. Every response includes inline citations so the user can trace each claim to its source.

The system is built for Individual Entrepreneurs and small businesses in Georgia navigating the Georgian Tax Code and Revenue Service guidance on rs.ge. These users are typically non-accountants who need accurate, source-backed answers, not summaries that might be hallucinated.

The architecture is split into five layers: data sources, knowledge base, agent pipeline, API, and frontend. Each layer is independently replaceable.

---

## 2. Layer 1: Data Sources and Ingestion

### Sources

The knowledge base is built from three categories of documents:

1. **Georgian Tax Code** (matsne.gov.ge) in Georgian and partial English translation. This is a large structured legal document organized by article and sub-article.
2. **Revenue Service circulars and guidance** (rs.ge). These are less structured, frequently updated HTML pages including thematic guides, FAQ sections, and official interpretations.
3. **Declaration forms and instructions** from rs.ge and the Ministry of Finance. These have fixed formats (PDF, HTML) and are referenced frequently in practical questions.

### Scraping Strategy

Two scrapers handle the two site types differently.

**rs.ge scraper (Playwright):** rs.ge renders content dynamically with JavaScript. Playwright controls a headless Chromium instance, waits for network idle, then extracts the rendered HTML. This handles pagination, accordion sections, and dynamically loaded tables.

**matsne.gov.ge scraper (httpx + BeautifulSoup):** The legislative portal serves static HTML. Using a full browser here would be unnecessary overhead. httpx sends async HTTP requests and BeautifulSoup parses the HTML tree. This is significantly faster than Playwright for bulk document collection.

The two scrapers share a common output format: a raw document record with fields for URL, fetched timestamp, raw HTML, source type (tax_code, circular, form, guidance), language (ka, en), and a SHA-256 hash of the content.

### Change Detection

Before re-indexing a document, the ingestion pipeline computes the SHA-256 hash of its extracted text and compares it to the stored hash in a simple SQLite or PostgreSQL tracking table. Only documents with a changed hash get re-chunked and re-embedded. This avoids redundant embedding API calls and keeps index updates fast.

### Scheduling

APScheduler runs the scraper jobs on a configurable schedule (for example, every 24 hours for tax code documents, every 6 hours for rs.ge guidance). The schedule is defined in `src/scraper/scheduler.py`. During development or thesis demo, scraping can also be triggered manually.

---

## 3. Layer 2: Knowledge Base

### Chunking Strategy

The thesis originally proposed flat article-level chunking. This architecture uses a parent-child structure instead.

**Parent chunk:** One full article or guidance section. Stored with its metadata but not directly used for retrieval. Used to provide surrounding context when a child chunk is retrieved.

**Child chunk:** One paragraph or sub-article (typically 100 to 400 tokens). This is what gets embedded and indexed. The child stores a reference to its parent.

This structure solves a common RAG failure mode: retrieving a paragraph without enough context to understand it. When a child chunk is returned, the pipeline fetches its parent and passes both to the Synthesizer, giving the model the relevant excerpt plus its full legal context.

For Tax Code articles, the boundary is article -> sub-article -> paragraph. For circulars and guidance, it is section heading -> paragraph. For forms, it is field group -> individual field instructions.

### Metadata Schema

Every chunk stored in Qdrant carries this metadata:

```json
{
  "source": "tax_code | circular | form | guidance",
  "article_number": "91",
  "language": "ka | en",
  "last_modified": "2024-11-15",
  "url": "https://matsne.gov.ge/...",
  "status": "active | superseded",
  "parent_id": "uuid-of-parent-chunk",
  "doc_hash": "sha256..."
}
```

The `status` field is set to `superseded` when a newer version of the same article is indexed. The Retriever filters these out before returning results, so outdated law never reaches the Synthesizer.

### Embedding and Indexing

BGE-M3 from FlagEmbedding generates both dense and sparse vectors for each child chunk in a single forward pass. This is one of the main reasons to use BGE-M3: it produces all three representation types (dense cosine vectors, SPLADE-style sparse vectors, ColBERT late-interaction vectors) in one model. For this system, only dense and sparse are used.

Qdrant stores both vector types per document and supports hybrid search over them natively. The collection is configured with cosine distance for dense vectors and dot product for sparse.

---

## 4. Layer 3: The Agent Pipeline

### State Model

LangGraph manages state as a typed dictionary that flows through the graph nodes. The state at any point in the pipeline contains:

```python
class AgentState(TypedDict):
    user_query: str
    conversation_history: list[Message]
    sub_queries: list[SubQuery]        # set by Planner
    retrieved_chunks: list[Chunk]      # set by Retriever
    draft_answer: str                  # set by Synthesizer
    critic_feedback: str               # set by Critic if REJECTED
    iteration_count: int
    final_answer: str                  # set when Critic says APPROVED
    status: Literal["planning", "retrieving", "synthesizing", "verifying", "done", "failed"]
```

### Planner Agent (Claude Haiku 4.5)

The Planner receives the user's natural language question and breaks it into concrete, retrievable sub-queries. The output is a JSON list of sub-query objects, each with a query string and a hint about what source type is most likely to answer it (tax_code, circular, form).

Example: "I am an IT freelancer with Small Business status, annual income 50,000 GEL from a foreign client, what are my obligations?" becomes:

1. Small Business status income tax rate (tax_code)
2. Foreign-source income classification for individuals (tax_code + circular)
3. VAT registration threshold (tax_code)
4. Applicable declaration forms and deadlines (form + guidance)

The Planner also receives any Critic feedback from a previous iteration and refines the sub-queries accordingly. For example, if the Critic reported missing coverage on VAT registration, the Planner adds or sharpens the relevant sub-query.

The system prompt for the Planner is long and consistent across requests. Anthropic prompt caching is applied here so the system prompt is cached after the first call within a 5-minute window.

### Retriever (Python function, no LLM)

The Retriever is not an LLM agent. It is a deterministic Python function that runs hybrid search for each sub-query. Sub-queries are executed in parallel using asyncio, not sequentially. This is a latency improvement the thesis did not explicitly address.

For each sub-query:

1. BGE-M3 generates a dense vector and a sparse vector for the query string.
2. Qdrant performs a hybrid search using both vectors with the configured alpha weight.
3. Metadata filters exclude any chunks where `status = superseded`.
4. The top 20 candidates from Qdrant are passed to the reranker.
5. bge-reranker-v2-m3 (a cross-encoder) scores each (query, chunk) pair and returns the top 5.
6. For each returned child chunk, the pipeline fetches its parent chunk for context.

The hybrid search score formula is: `score = alpha * dense_score + (1 - alpha) * sparse_score`. The default alpha is 0.65, which was chosen as a starting point for Georgian text where dense vectors are less precise than for high-resource languages. This value is tuned empirically against the validation set.

The final retrieved set is the union of top-5 results across all sub-queries, deduplicated by chunk ID.

### Synthesizer Agent (Claude Sonnet 4.6)

The Synthesizer receives the Planner's structured sub-query plan and the full set of retrieved chunks, then generates the answer. Sonnet 4.6 is used here rather than Haiku because this is the step where quality matters most. The Planner and Critic are doing structured, lower-complexity tasks. The Synthesizer is doing the nuanced work of combining multiple legal sources into a coherent, accurate response.

The system prompt instructs the model to:
- Format every factual claim with an inline citation in square brackets, for example [Tax Code, Article 91]
- Structure the response in two sections: the main answer in natural Georgian, and a numbered checklist of concrete actions the user needs to take
- Not speculate beyond what the retrieved sources explicitly say
- Use the parent chunk context when the child chunk alone is ambiguous

The Synthesizer response goes directly to the Critic. It is never shown to the user until the Critic approves it.

Prompt caching is applied to the Synthesizer system prompt as well. Because the system prompt is the same for all requests, this saves significant tokens when the system is under load.

### Critic Agent (Claude Haiku 4.5)

The Critic checks the Synthesizer's draft answer against three criteria:

1. **Citation grounding:** Every fact in the answer that carries a citation must actually appear in the corresponding retrieved chunk. The Critic reads both the answer and the chunk and verifies the mapping.
2. **Source currency:** Every cited article or circular must have `status = active` in its metadata. If a cited source is superseded, the Critic rejects with a note about which citation failed.
3. **Coverage check:** The Critic checks whether the answer addresses all sub-queries from the Planner's plan. If a sub-query has no corresponding content in the answer, the Critic flags it as a coverage gap.

The Critic outputs a verdict and a structured reason:

```json
{
  "verdict": "APPROVED" | "REJECTED",
  "reason": "...",
  "failed_check": "grounding | currency | coverage | null"
}
```

If APPROVED, the answer goes to the API layer.

If REJECTED, the state goes back to the Planner with the Critic's reason. The Planner uses the `failed_check` type to decide what to do: add a new sub-query for a coverage gap, request stricter citation constraints for a grounding failure, or trigger re-scraping if a currency failure implies the knowledge base is stale.

The maximum number of iterations is 3. If the Critic rejects three times in a row, the system returns the best available draft with a clear disclaimer that the answer could not be fully verified against its sources.

### LangGraph Graph Definition

The graph has these nodes: `planner`, `retriever`, `synthesizer`, `critic`, `finalize`, `fail_safe`.

The edges are:
- `start` to `planner`
- `planner` to `retriever`
- `retriever` to `synthesizer`
- `synthesizer` to `critic`
- `critic` to `finalize` (when verdict is APPROVED)
- `critic` to `planner` (when verdict is REJECTED and iteration_count < 3)
- `critic` to `fail_safe` (when verdict is REJECTED and iteration_count >= 3)

The retrieval fan-out (parallel sub-queries) is implemented inside the `retriever` node using asyncio.gather, not as separate LangGraph nodes. This keeps the graph topology simple while still running retrievals in parallel.

---

## 5. Layer 4: API

### FastAPI Application

The backend exposes one primary endpoint: `POST /chat`. This accepts a JSON body with `query` and `session_id`, and returns a Server-Sent Events stream. SSE allows the frontend to display agent status updates in real time (for example, "Planner decomposed your question into 4 sub-queries", "Retrieving from knowledge base", "Generating answer...") and then stream the final answer token by token.

The streaming approach is important for perceived latency. The Synthesizer call can take several seconds. Without streaming, the user sees a blank screen until the full pipeline finishes.

Other endpoints:

- `GET /health`: Returns service health including Qdrant and Redis connectivity.
- `GET /sources`: Returns the list of indexed source documents with their last-modified dates.

### Rate Limiting

Redis stores a sliding window counter per IP address. The limit is configurable (default: 10 requests per minute per IP). This matters both for controlling Anthropic API costs and for preventing abuse in a demo deployment.

### Authentication

For the thesis demo, authentication is optional but the architecture includes JWT-based auth so it can be toggled on. A `POST /auth/token` endpoint issues tokens against a static admin credential defined in the environment. This is not production auth; it is just enough to gate access to the demo.

---

## 6. Layer 5: Frontend

### Next.js 14 Application

The frontend is a single chat interface built with Next.js 14 App Router and Tailwind CSS. The main view is a conversation thread with support for Georgian and English text rendering (the Noto Sans Georgian font is loaded via next/font).

### Streaming and Agent Trace

Each message from the API arrives as a stream of SSE events. The frontend handles two event types:

- `status`: A short string like "Retrieving from Tax Code..." that updates a small status indicator above the response being typed out.
- `token`: A single token appended to the response text in place.
- `sources`: A list of source citations (article number, document name, URL) that appear as a collapsible panel below the response.
- `done`: Signals that the stream is complete.

The agent trace (the sequence of status events) is preserved in the UI as an expandable "How this was answered" section. This is important for a thesis demonstration because it shows the evaluator what the agents actually did.

### Citations Display

Each citation in the response text is rendered as a clickable footnote marker. Clicking it opens a side panel with the exact text of the retrieved chunk and a link to the source URL. This is the feature that differentiates the system from a standard chatbot. Every claim is auditable.

---

## 7. Semantic Cache

Before the query reaches the Planner, the API checks a Redis-based semantic cache. The query is embedded with BGE-M3, and the embedding is compared to cached query embeddings using cosine similarity. If a cached query has similarity above 0.92, the cached response is returned immediately.

Cache entries expire after 24 hours by default. When a scraping run detects that a source document has changed, it flushes related cache entries by source tag.

This cache is significant for a tax system where many users ask structurally similar questions (for example, "what is the VAT threshold" in different phrasings). It reduces both latency and API cost.

---

## 8. Infrastructure (Docker Compose)

The compose file defines five services:

1. **qdrant**: Official Qdrant image, port 6333, persistent volume for the vector index.
2. **redis**: Official Redis image, port 6379, used for cache and rate limiting.
3. **api**: The FastAPI application, built from `src/`, depends on qdrant and redis.
4. **worker**: APScheduler-based ingestion worker, runs the scraping and re-indexing jobs on schedule.
5. **frontend**: Next.js application, depends on api.

BGE-M3 and the reranker models are loaded by the api and worker services. On CPU, the initial model load takes 10 to 20 seconds but is amortized across all requests. If a GPU is available, `BGE_M3_DEVICE=cuda` switches both models to it.

---

## 9. Observability

Langfuse is used for LLM call tracing. Every call to the Anthropic API is wrapped with a Langfuse span that records the model, input tokens, output tokens, latency, and the agent role (planner, synthesizer, critic). The LangGraph graph run is recorded as a parent trace with child spans for each agent step.

This is useful during development to see exactly what each agent received and returned, to debug Critic rejections, and to identify which sub-queries consistently return low-quality results.

Standard Python logging (structured JSON) is written to stdout so Docker logs captures it. Log level is configurable per environment.

---

## 10. Evaluation

The evaluation harness in `src/evaluation/` runs against a 50-question test set built specifically for this domain. Each test case includes:

- The user question
- A reference answer written by a domain expert
- A list of specific Tax Code articles that must appear in the citations

Metrics run using RAGAS:

- **faithfulness**: Is every claim in the answer supported by the retrieved chunks?
- **answer_relevancy**: Does the answer address what was asked?
- **context_precision**: Of the chunks retrieved, how many were actually needed?
- **context_recall**: Were all the chunks needed to answer the question retrieved?

Custom metric added on top:

- **citation_correctness**: For each citation in the answer, does the cited article actually contain the stated fact? Scored as a ratio of correct citations to total citations.

Results are compared against a naive RAG baseline: single retrieval, no agents, no Critic, Claude Haiku 4.5 for generation.

---

## 11. Changes from the Thesis Proposal

The following decisions diverge from what the original thesis proposed, with reasons:

| Thesis | This architecture | Reason |
|---|---|---|
| Selenium + Playwright + BeautifulSoup | Playwright for dynamic, httpx for static | Selenium is redundant when Playwright is already present |
| Claude Haiku 4.5 for all agents | Haiku for Planner and Critic, Sonnet 4.6 for Synthesizer | Synthesis quality is the most important factor in answer accuracy |
| Retrieval unspecified as parallel or sequential | Explicit asyncio parallel retrieval per sub-query | Sequential retrieval of N sub-queries multiplies latency by N |
| Flat article-level chunks | Parent-child chunk structure | Retrieving context-free paragraphs misses cross-reference resolution |
| No reranker specified beyond BGE-M3 | bge-reranker-v2-m3 cross-encoder after initial retrieval | Cross-encoder reranking significantly improves precision vs. bi-encoder similarity alone |
| No caching layer | Redis semantic cache on queries | Major latency and cost saving for repeated or paraphrased questions |
| No streaming | FastAPI SSE + frontend streaming | Essential for usability given multi-second pipeline latency |
| No observability | Langfuse for agent tracing | Necessary to debug agent behavior and tune Critic thresholds |
| No prompt caching mentioned | Anthropic prompt caching on system prompts | 90% cost reduction on cached tokens for long system prompts |
