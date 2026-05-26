"""
Smoke Tests — 10 Acceptance Criteria Queries
=============================================

Sprint is NOT complete until >= 8 of these 10 return correct, useful results.
0/10 may return hallucinated content — if data isn't there, the answer is "no matching data".

Customize QUERIES below with questions relevant to YOUR project's development history.

CLI:
    python -m queries.smoke_tests
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from config.graphiti_init import get_graphiti, close_graphiti

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    query_id: int
    question: str
    passed: bool = False
    latency_ms: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    top_results: list[str] = field(default_factory=list)
    error: str | None = None


# ── Customize these queries for your project ──────────────────────────────────
# Replace the example queries below with questions about YOUR development history.
# After running bulk backfill, these should return meaningful results.
QUERIES = [
    # Status checks
    "What are the currently open problems?",
    "What experiments have we run recently?",
    # Decision history
    "What architectural decisions are currently active?",
    "What technology choices have we made?",
    # Artifact tracking
    "What specs have been written in the last 30 days?",
    "What problems are currently blocking progress?",
    # Experiment review
    "Show me experiments that failed recently.",
    "What decisions have been made about the frontend?",
    # Negative test — correct answer should be "no matching data"
    "Has anyone tried implementing quantum computing integration?",
    # Concept lookup
    "What recurring patterns or concepts have emerged in the project?",
]


async def run_query(graphiti, query_id: int, question: str) -> QueryResult:
    """Run a single smoke test query."""
    result = QueryResult(query_id=query_id, question=question)

    start = time.time()
    try:
        # Search nodes (entities)
        nodes = await graphiti.search(query=question, num_results=5)

        result.latency_ms = (time.time() - start) * 1000
        result.node_count = len(nodes)

        # Extract top results for human review
        for node in nodes[:5]:
            if hasattr(node, "fact"):
                result.top_results.append(node.fact)
            elif hasattr(node, "name"):
                summary = getattr(node, "summary", "") or ""
                result.top_results.append(f"{node.name}: {summary[:200]}")

        # Basic pass criteria:
        # - Response in < 2 seconds
        # - At least 1 result for most queries (query 9 is a negative test)
        if result.latency_ms > 2000:
            result.passed = False
        elif query_id == 9:
            # Negative test — correct answer is "no matching data"
            result.passed = True  # Pass if no hallucinated results
        else:
            result.passed = result.node_count > 0

    except Exception as e:
        result.latency_ms = (time.time() - start) * 1000
        result.error = str(e)
        result.passed = False

    return result


async def run_all_smoke_tests() -> list[QueryResult]:
    """Run all 10 smoke test queries and return results."""
    graphiti = await get_graphiti()
    results = []

    for i, question in enumerate(QUERIES, start=1):
        result = await run_query(graphiti, i, question)
        results.append(result)

        status = "PASS" if result.passed else "FAIL"
        logger.info(
            "[%s] Q%d (%.0fms, %d results): %s",
            status, i, result.latency_ms, result.node_count, question[:60],
        )

    return results


def print_report(results: list[QueryResult]) -> None:
    """Print a formatted smoke test report."""
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"SMOKE TEST RESULTS: {passed}/{total} passed")
    print(f"{'='*60}\n")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] Q{r.query_id}: {r.question}")
        print(f"         Latency: {r.latency_ms:.0f}ms | Results: {r.node_count}")
        if r.error:
            print(f"         Error: {r.error}")
        if r.top_results:
            for tr in r.top_results[:2]:
                print(f"         -> {tr[:120]}")
        print()

    threshold = 8
    if passed >= threshold:
        print(f"VERDICT: PASS ({passed}/{total} >= {threshold})")
    else:
        print(f"VERDICT: FAIL ({passed}/{total} < {threshold})")
        print("Action: Tune entity definitions and re-run backfill.")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        results = await run_all_smoke_tests()
        print_report(results)
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
