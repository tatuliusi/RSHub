"""
Shared state type for the LangGraph agent pipeline.
All agents read from and write partial updates to this TypedDict.
"""

from typing import TypedDict, Literal, Any
from dataclasses import dataclass, field


@dataclass
class SubQuery:
    query: str
    source_hint: Literal["tax_code", "circular", "form", "guidance", "any"] = "any"
    priority: int = 1


@dataclass
class RetrievedChunk:
    chunk_id: str
    parent_id: str
    text: str
    parent_text: str
    source: str
    language: str
    article_number: str
    title: str
    last_modified: str
    url: str
    score: float
    sub_query: str
    status: str = "active"


@dataclass
class Source:
    article_number: str
    title: str
    url: str
    source_type: str
    last_modified: str


class AgentState(TypedDict):
    # Input
    user_query: str
    session_id: str
    conversation_history: list[dict]

    # Planner output
    sub_queries: list[SubQuery]

    # Retriever output
    retrieved_chunks: list[RetrievedChunk]

    # Synthesizer output
    draft_answer: str
    sources: list[Source]

    # Critic output
    critic_verdict: Literal["APPROVED", "REJECTED", ""]
    critic_feedback: str
    failed_check: Literal["grounding", "currency", "coverage", ""]

    # Control
    iteration_count: int
    status: str

    # Final output
    final_answer: str
    final_sources: list[Source]
    low_confidence: bool
