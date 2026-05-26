"""
Spot-Check Audit — Phase 2 Exit Gate
=====================================

Queries the graph for 50 randomly-sampled entities and outputs a review file
for manual verification of extraction quality.

Acceptance threshold:
  >= 90% correct -> proceed to Phase 3
  70-89% correct -> tune entity docstrings, re-run backfill, re-audit
  < 70% correct -> stop and investigate extraction quality

CLI:
    python -m queries.spot_check
"""

import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path

from config.graphiti_init import get_graphiti, close_graphiti

logger = logging.getLogger(__name__)

ENTITY_TYPES_TO_SAMPLE = ["DevSession", "Decision", "Problem", "Experiment", "Concept"]
SAMPLES_PER_TYPE = 10


async def sample_entities(graphiti) -> list[dict]:
    """Sample entities from the graph for spot-check review."""
    entities = []

    for entity_type in ENTITY_TYPES_TO_SAMPLE:
        try:
            # Search for entities of this type
            results = await graphiti.search(
                query=f"All {entity_type} entities",
                num_results=20,
            )

            # Sample up to SAMPLES_PER_TYPE
            sampled = random.sample(results, min(SAMPLES_PER_TYPE, len(results)))

            for node in sampled:
                entity = {
                    "type": entity_type,
                    "name": getattr(node, "name", "unknown"),
                    "summary": getattr(node, "summary", ""),
                }

                # Extract custom attributes if available
                if hasattr(node, "attributes") and node.attributes:
                    entity["attributes"] = node.attributes

                entities.append(entity)

        except Exception as e:
            logger.error("Failed to sample %s entities: %s", entity_type, e)

    return entities


def generate_review_file(entities: list[dict]) -> Path:
    """Generate the spot-check review markdown file."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    review_file = log_dir / f"spot_check_{timestamp}.md"

    lines = [
        "# Spot-Check Audit — Extraction Quality Review",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Total entities sampled:** {len(entities)}",
        f"**Types sampled:** {', '.join(ENTITY_TYPES_TO_SAMPLE)}",
        "",
        "## Acceptance Threshold",
        "- >= 90% correct -> proceed to Phase 3",
        "- 70-89% correct -> tune entity docstrings, re-run backfill, re-audit",
        "- < 70% correct -> stop and investigate",
        "",
        "---",
        "",
    ]

    for i, entity in enumerate(entities, start=1):
        lines.append(f"## Entity {i}: {entity['type']}")
        lines.append("")
        lines.append("**Extracted fields:**")

        if entity.get("attributes"):
            for key, val in entity["attributes"].items():
                lines.append(f"- {key}: {val}")
        else:
            lines.append(f"- name: {entity['name']}")
            if entity.get("summary"):
                lines.append(f"- summary: {entity['summary'][:300]}")

        lines.append("")
        lines.append(f"**Entity name:** {entity['name']}")
        lines.append("")
        lines.append("**Reviewer verdict:** [ ] correct  [ ] partial  [ ] wrong")
        lines.append("**Notes:**")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append("")
    lines.append(f"Total entities reviewed: {len(entities)}")
    lines.append("Correct: ___ / ___")
    lines.append("Partial: ___ / ___")
    lines.append("Wrong: ___ / ___")
    lines.append("Accuracy: ___%")
    lines.append("")
    lines.append("**Verdict:** [ ] PASS (>=90%)  [ ] ITERATE (70-89%)  [ ] STOP (<70%)")
    lines.append("")

    review_file.write_text("\n".join(lines), encoding="utf-8")
    return review_file


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    try:
        graphiti = await get_graphiti()
        entities = await sample_entities(graphiti)

        if not entities:
            print("No entities found in graph. Run backfill first.")
            return

        review_file = generate_review_file(entities)
        print(f"Spot-check review generated: {review_file}")
        print(f"  {len(entities)} entities sampled across {len(ENTITY_TYPES_TO_SAMPLE)} types")
        print(f"\nReview the file and mark each entity correct/partial/wrong.")
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
