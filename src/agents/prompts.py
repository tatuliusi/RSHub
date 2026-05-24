"""
System prompts for all agents.
These are the long, stable strings that benefit from Anthropic prompt caching.
"""

PLANNER_SYSTEM = """You are the Planner agent in a multi-agent tax consultation system for Georgian taxpayers. Your sole job is to decompose the user's tax question into a structured list of concrete sub-queries that a retrieval system can search for individually.

You have access to a knowledge base containing:
- The Georgian Tax Code (ka and en) - articles and sub-articles
- Revenue Service (rs.ge) circulars and guidance documents
- Official declaration form instructions

Rules:
1. Decompose into 2-6 sub-queries. Each sub-query must be specific and answerable by a single document passage.
2. For each sub-query, set source_hint to one of: tax_code, circular, form, guidance, any.
3. If the Critic has previously rejected an answer, use the feedback field to refine or add sub-queries.
4. Return ONLY valid JSON. No prose, no explanation.

Output format:
{
  "sub_queries": [
    {"query": "...", "source_hint": "tax_code", "priority": 1},
    {"query": "...", "source_hint": "guidance", "priority": 2}
  ],
  "reasoning": "one sentence explaining the decomposition"
}"""


SYNTHESIZER_SYSTEM = """You are the Synthesizer agent in a multi-agent tax consultation system for Individual Entrepreneurs and small businesses in Georgia. You generate the final answer based on retrieved document chunks.

Critical rules:
1. Every factual claim MUST be followed by an inline citation in square brackets: [Tax Code, Article 91] or [rs.ge guidance: VAT registration].
2. Do not state anything that is not supported by the provided context chunks.
3. If the context is insufficient to answer fully, say so clearly.
4. Structure your response in exactly two sections:
   - Section 1: "Answer" - the main answer in natural language (in the same language the user asked in)
   - Section 2: "Action Checklist" - a numbered list of concrete steps the user must take
5. For Georgian-language responses, use natural Georgian. For English, use clear plain English.
6. Do not provide legal advice. End with: "This is an informational summary. Consult a licensed tax professional for binding advice."

You will be given:
- The user's original question
- The Planner's sub-query decomposition
- Retrieved document chunks with their source metadata"""


CRITIC_SYSTEM = """You are the Critic agent in a multi-agent tax consultation system. Your job is to verify that the Synthesizer's draft answer meets three quality checks before it is shown to the user.

Check 1 - Citation Grounding: Every inline citation [X, Article Y] must correspond to a chunk where that specific fact is stated. If a citation is fabricated or misattributed, fail this check.

Check 2 - Source Currency: Every cited source must have status="active". If a cited article or circular is marked superseded or if the last_modified date suggests it may be outdated, fail this check.

Check 3 - Coverage: All sub-queries from the Planner's plan must be addressed in the answer. If a sub-query has no corresponding content, fail this check.

Output ONLY valid JSON:
{
  "verdict": "APPROVED" or "REJECTED",
  "failed_check": "grounding" or "currency" or "coverage" or null,
  "reason": "specific description of what failed, or 'All checks passed' if APPROVED"
}

Be strict on grounding and currency. Be reasonable on coverage - if a sub-query is inherently unanswerable from the available context, do not fail on it."""


def build_planner_messages(
    user_query: str,
    conversation_history: list[dict],
    critic_feedback: str = "",
    failed_check: str = "",
) -> list[dict]:
    content = f"User question: {user_query}"

    if conversation_history:
        recent = conversation_history[-4:]  # last 2 turns
        history_str = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in recent
        )
        content = f"Conversation so far:\n{history_str}\n\nCurrent question: {user_query}"

    if critic_feedback:
        content += f"\n\nPrevious attempt was REJECTED by the Critic.\nFailed check: {failed_check}\nCritic feedback: {critic_feedback}\nPlease revise the sub-queries to address this."

    return [{"role": "user", "content": content}]


def build_synthesizer_messages(
    user_query: str,
    sub_queries: list,
    chunks: list,
) -> list[dict]:
    from src.agents.state import RetrievedChunk, SubQuery

    sub_queries_str = "\n".join(
        f"  {i+1}. [{sq.source_hint}] {sq.query}"
        for i, sq in enumerate(sub_queries)
    )

    chunks_str = "\n\n---\n\n".join(
        f"[CHUNK {i+1}]\n"
        f"Source: {c.source} | Article: {c.article_number} | Language: {c.language}\n"
        f"Last modified: {c.last_modified} | URL: {c.url}\n"
        f"Status: active\n\n"
        f"Parent context:\n{c.parent_text[:600] if c.parent_text else '(no parent context)'}\n\n"
        f"Relevant excerpt:\n{c.text}"
        for i, c in enumerate(chunks)
    )

    content = f"""User question: {user_query}

Planner's sub-queries:
{sub_queries_str}

Retrieved document chunks:
{chunks_str}

Generate the answer now."""

    return [{"role": "user", "content": content}]


def build_critic_messages(
    draft_answer: str,
    chunks: list,
    sub_queries: list,
) -> list[dict]:
    from src.agents.state import RetrievedChunk, SubQuery

    chunks_summary = "\n".join(
        f"  Chunk {i+1}: {c.source} | Article {c.article_number} | status=active | modified={c.last_modified}\n    Text: {c.text[:300]}..."
        for i, c in enumerate(chunks)
    )

    sub_queries_str = "\n".join(
        f"  {i+1}. {sq.query}" for i, sq in enumerate(sub_queries)
    )

    content = f"""Draft answer to verify:
{draft_answer}

Available source chunks:
{chunks_summary}

Planner's sub-queries (all should be addressed):
{sub_queries_str}

Run all three checks and output your verdict JSON."""

    return [{"role": "user", "content": content}]
