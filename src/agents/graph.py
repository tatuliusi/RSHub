"""
LangGraph state machine definition.
Wires together Planner -> Retriever -> Synthesizer -> Critic with conditional retry loop.
"""

from typing import Literal

from langgraph.graph import StateGraph, END

from src.agents.state import AgentState
from src.agents.planner import planner_node
from src.agents.retriever_agent import retriever_node_async as retriever_node
from src.agents.synthesizer import synthesizer_node
from src.agents.critic import critic_node
from src.config import get_settings


def finalize_node(state: AgentState) -> dict:
    return {
        "final_answer": state["draft_answer"],
        "final_sources": state.get("sources", []),
        "low_confidence": False,
        "status": "done",
    }


def fail_safe_node(state: AgentState) -> dict:
    """Returns the last draft with a low-confidence disclaimer."""
    draft = state.get("draft_answer", "")
    disclaimer = (
        "\n\n---\n"
        "Note: This answer could not be fully verified against its sources after "
        f"{state.get('iteration_count', 0)} attempts. "
        "Please verify the cited articles directly before acting on this information."
    )
    return {
        "final_answer": draft + disclaimer,
        "final_sources": state.get("sources", []),
        "low_confidence": True,
        "status": "done",
    }


def _route_after_critic(state: AgentState) -> Literal["finalize", "fail_safe", "planner"]:
    settings = get_settings()
    verdict = state.get("critic_verdict", "REJECTED")
    iterations = state.get("iteration_count", 0)

    if verdict == "APPROVED":
        return "finalize"
    if iterations >= settings.max_critic_iterations:
        return "fail_safe"
    return "planner"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("fail_safe", fail_safe_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "synthesizer")
    graph.add_edge("synthesizer", "critic")

    graph.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "finalize": "finalize",
            "fail_safe": "fail_safe",
            "planner": "planner",
        },
    )

    graph.add_edge("finalize", END)
    graph.add_edge("fail_safe", END)

    return graph


def get_compiled_graph():
    return build_graph().compile()


# Module-level compiled graph (loaded once)
_compiled_graph = None


def pipeline() -> object:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = get_compiled_graph()
    return _compiled_graph


def build_initial_state(
    user_query: str,
    session_id: str,
    conversation_history: list[dict] | None = None,
) -> AgentState:
    return AgentState(
        user_query=user_query,
        session_id=session_id,
        conversation_history=conversation_history or [],
        sub_queries=[],
        retrieved_chunks=[],
        draft_answer="",
        sources=[],
        critic_verdict="",
        critic_feedback="",
        failed_check="",
        iteration_count=0,
        status="planning",
        final_answer="",
        final_sources=[],
        low_confidence=False,
    )
