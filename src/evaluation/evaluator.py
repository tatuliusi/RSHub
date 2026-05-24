"""
Evaluation harness using RAGAS metrics + custom citation_correctness.
Compares the multi-agent pipeline against a naive RAG baseline.

Usage:
  python -m src.evaluation.evaluator --test-set src/evaluation/test_set.json
"""

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

CITATION_PATTERN = re.compile(r"\[([^\]]+)\]")


def _citation_correctness(answer: str, required_citations: list[str]) -> float:
    """
    Checks what fraction of required citation keywords appear in the answer's citations.
    Returns 0.0 to 1.0.
    """
    if not required_citations:
        return 1.0
    cited_texts = " ".join(CITATION_PATTERN.findall(answer)).lower()
    found = sum(1 for kw in required_citations if kw.lower() in cited_texts)
    return found / len(required_citations)


async def _run_pipeline(question: str) -> dict:
    """Runs the full multi-agent pipeline for a question."""
    from src.agents.graph import pipeline, build_initial_state

    graph = pipeline()
    state = build_initial_state(user_query=question, session_id="eval")
    result = await graph.ainvoke(state)
    return {
        "answer": result.get("final_answer", ""),
        "sources": result.get("final_sources", []),
        "low_confidence": result.get("low_confidence", False),
        "iterations": result.get("iteration_count", 0),
    }


async def _run_naive_baseline(question: str) -> dict:
    """
    Naive RAG baseline: single retrieval + direct generation, no agents, no Critic.
    Uses Haiku 4.5 for generation.
    """
    import anthropic
    from src.retrieval.searcher import hybrid_search
    from src.retrieval.reranker import rerank
    from src.config import get_settings

    settings = get_settings()
    results = hybrid_search(question, top_k=20)
    reranked = rerank(question, results, top_k=5)

    context = "\n\n---\n\n".join(
        f"[Source: {r.source}, Article {r.article_number}]\n{r.text}"
        for r in reranked
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.planner_model,  # Haiku for baseline
        max_tokens=1024,
        system="You are a Georgian tax assistant. Answer based on the provided context. Cite sources with article numbers.",
        messages=[
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ],
    )
    return {
        "answer": response.content[0].text,
        "sources": [],
        "low_confidence": False,
        "iterations": 1,
    }


async def evaluate(test_set_path: str, output_path: str | None = None) -> dict:
    test_cases = json.loads(Path(test_set_path).read_text())
    log.info("Loaded %d test cases", len(test_cases))

    pipeline_results = []
    baseline_results = []

    for i, case in enumerate(test_cases):
        log.info("Running case %d/%d: %s", i + 1, len(test_cases), case["id"])

        # Multi-agent pipeline
        try:
            pipeline_out = await _run_pipeline(case["question"])
        except Exception as e:
            log.warning("Pipeline failed for %s: %s", case["id"], e)
            pipeline_out = {"answer": "", "sources": [], "low_confidence": True, "iterations": 0}

        # Naive baseline
        try:
            baseline_out = await _run_naive_baseline(case["question"])
        except Exception as e:
            log.warning("Baseline failed for %s: %s", case["id"], e)
            baseline_out = {"answer": "", "sources": [], "low_confidence": True, "iterations": 0}

        # Citation correctness
        pipeline_cc = _citation_correctness(pipeline_out["answer"], case.get("required_citations", []))
        baseline_cc = _citation_correctness(baseline_out["answer"], case.get("required_citations", []))

        pipeline_results.append({
            "id": case["id"],
            "question": case["question"],
            "reference": case["reference_answer"],
            "answer": pipeline_out["answer"],
            "citation_correctness": pipeline_cc,
            "low_confidence": pipeline_out["low_confidence"],
            "iterations": pipeline_out["iterations"],
        })

        baseline_results.append({
            "id": case["id"],
            "answer": baseline_out["answer"],
            "citation_correctness": baseline_cc,
        })

        await asyncio.sleep(1)  # avoid rate limiting

    # Compute RAGAS metrics if available
    ragas_pipeline = _compute_ragas(pipeline_results, test_cases)
    ragas_baseline = _compute_ragas(baseline_results, test_cases)

    # Summary
    pipeline_cc_avg = sum(r["citation_correctness"] for r in pipeline_results) / len(pipeline_results)
    baseline_cc_avg = sum(r["citation_correctness"] for r in baseline_results) / len(baseline_results)
    pipeline_low_conf = sum(1 for r in pipeline_results if r["low_confidence"]) / len(pipeline_results)

    summary = {
        "pipeline": {
            "citation_correctness": pipeline_cc_avg,
            "low_confidence_rate": pipeline_low_conf,
            **ragas_pipeline,
        },
        "baseline": {
            "citation_correctness": baseline_cc_avg,
            **ragas_baseline,
        },
        "n": len(test_cases),
    }

    log.info("Evaluation summary: %s", json.dumps(summary, indent=2))

    output = {"summary": summary, "pipeline_results": pipeline_results, "baseline_results": baseline_results}

    if output_path:
        Path(output_path).write_text(json.dumps(output, indent=2, ensure_ascii=False))
        log.info("Results saved to %s", output_path)

    return output


def _compute_ragas(results: list[dict], test_cases: list[dict]) -> dict:
    """Attempts RAGAS evaluation. Returns empty dict if RAGAS is not installed."""
    try:
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from datasets import Dataset

        data = {
            "question": [r["question"] if "question" in r else tc["question"] for r, tc in zip(results, test_cases)],
            "answer": [r["answer"] for r in results],
            "contexts": [[""] for _ in results],  # placeholder - in real eval pass retrieved chunks
            "ground_truth": [tc["reference_answer"] for tc in test_cases],
        }
        dataset = Dataset.from_dict(data)
        scores = ragas_evaluate(dataset, metrics=[faithfulness, answer_relevancy])
        return {"faithfulness": scores["faithfulness"], "answer_relevancy": scores["answer_relevancy"]}
    except ImportError:
        log.warning("RAGAS not installed. Install with: pip install -e '.[eval]'")
        return {}
    except Exception as e:
        log.warning("RAGAS evaluation failed: %s", e)
        return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-set", default="src/evaluation/test_set.json")
    parser.add_argument("--output", default="src/evaluation/results.json")
    args = parser.parse_args()
    asyncio.run(evaluate(args.test_set, args.output))
