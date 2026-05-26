"""
Session Ingestor
================

Ingests session summary markdown files into the Dev Brain knowledge graph.

Input: Markdown files with YAML frontmatter at docs/sessions/SESSION_SUMMARY_YYYY-MM-DD.md
Output: Graphiti episodes with extracted entities (DevSession, Decision, Problem, etc.)

CLI:
    python -m ingestion.session_ingestor --file docs/sessions/SESSION_SUMMARY_2026-04-24.md
    python -m ingestion.session_ingestor --dir docs/sessions/ --since 2026-01-01
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import frontmatter
from graphiti_core.nodes import EpisodeType

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings
from entities import ENTITY_TYPES, EDGE_TYPES
from ingestion.idempotency import is_already_ingested, mark_ingested

logger = logging.getLogger(__name__)


async def ingest_session_file(file_path: Path) -> dict:
    """
    Ingest a single session summary file.

    Returns:
        Dict with ingestion results (entities_created, edges_created, etc.)
    """
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        logger.warning("GRAPHITI_READ_ONLY=true — skipping ingestion of %s", file_path.name)
        return {"skipped": True, "reason": "read_only"}

    # Parse frontmatter + body
    post = frontmatter.load(str(file_path))
    body = post.content
    metadata = post.metadata

    # Check idempotency
    if is_already_ingested(body):
        logger.info("Already ingested: %s (skipping)", file_path.name)
        return {"skipped": True, "reason": "already_ingested"}

    # Extract structured fields from frontmatter
    import datetime as dt_module
    session_date = metadata.get("session_date")
    if isinstance(session_date, str):
        session_date = datetime.fromisoformat(session_date)
    elif isinstance(session_date, datetime):
        pass
    elif isinstance(session_date, dt_module.date):
        # YAML auto-parses YYYY-MM-DD as date, not datetime
        session_date = datetime(session_date.year, session_date.month, session_date.day)
    else:
        # Fall back to file modification time
        session_date = datetime.fromtimestamp(file_path.stat().st_mtime)

    graphiti = await get_graphiti()

    logger.info("Ingesting session: %s (date=%s)", file_path.name, session_date)

    try:
        result = await asyncio.wait_for(
            graphiti.add_episode(
                name=file_path.stem,
                episode_body=body,
                source=EpisodeType.text,
                source_description="session_summary",
                reference_time=session_date,
                group_id=settings.GRAPHITI_GROUP_ID,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
            ),
            timeout=300,  # 5 min per episode — prevents Gemini API hangs
        )
    except asyncio.TimeoutError:
        logger.error("Timeout ingesting %s (exceeded 300s)", file_path.name)
        return {"file": file_path.name, "error": "timeout_300s"}

    mark_ingested(body)

    # Build result summary
    summary = {
        "file": str(file_path.name),
        "session_date": session_date.isoformat(),
        "entities_created": len(result.nodes),
        "edges_created": len(result.edges),
        "entity_names": [n.name for n in result.nodes],
    }

    logger.info(
        "Ingested %s: %d entities, %d edges",
        file_path.name,
        len(result.nodes),
        len(result.edges),
    )

    return summary


async def ingest_directory(
    dir_path: Path,
    since: datetime | None = None,
) -> list[dict]:
    """Ingest all session files in a directory."""
    results = []
    for md_file in sorted(dir_path.glob("*.md")):
        if md_file.name == "TEMPLATE.md":
            continue

        # Optional date filter
        if since:
            try:
                post = frontmatter.load(str(md_file))
                file_date = post.metadata.get("session_date")
                if isinstance(file_date, str):
                    file_date = datetime.fromisoformat(file_date)
                if file_date and file_date < since:
                    continue
            except Exception:
                pass  # If we can't parse date, ingest anyway

        try:
            result = await ingest_session_file(md_file)
            results.append(result)
        except Exception as e:
            logger.error("Failed to ingest %s: %s", md_file.name, e)
            results.append({"file": md_file.name, "error": str(e)})

    return results


def _save_log(results: list[dict], label: str) -> None:
    """Save ingestion results to logs/."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"session_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    logger.info("Results saved to %s", log_file)


async def main():
    parser = argparse.ArgumentParser(description="Ingest session summaries into Dev Brain")
    parser.add_argument("--file", type=Path, help="Single session file to ingest")
    parser.add_argument("--dir", type=Path, help="Directory of session files")
    parser.add_argument("--since", type=str, help="Only ingest sessions after this date (YYYY-MM-DD)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    since = datetime.fromisoformat(args.since) if args.since else None

    try:
        if args.file:
            result = await ingest_session_file(args.file)
            _save_log([result], args.file.stem)
            print(json.dumps(result, indent=2, default=str))
        elif args.dir:
            results = await ingest_directory(args.dir, since=since)
            _save_log(results, "batch")
            ingested = [r for r in results if not r.get("skipped")]
            print(f"Ingested {len(ingested)} / {len(results)} session files")
        else:
            parser.print_help()
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
