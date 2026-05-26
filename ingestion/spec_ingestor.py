"""
Spec Ingestor
=============

Ingests markdown spec/ADR files from docs/ directories into the Dev Brain.

Tracks files by content hash — re-ingests when content changes (Graphiti handles
supersession automatically via bi-temporal model).

CLI:
    python -m ingestion.spec_ingestor --repo primary
    python -m ingestion.spec_ingestor --file docs/sprints/MY_SPEC.md
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from graphiti_core.nodes import EpisodeType

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings
from entities import ENTITY_TYPES, EDGE_TYPES
from ingestion.idempotency import is_already_ingested, mark_ingested

logger = logging.getLogger(__name__)

# Directories to scan for specs, relative to repo root
_SPEC_DIRS = [
    "docs/sprints",
    "docs/sessions",
    "docs/architecture",
    "docs/future_features",
]


def _classify_source(file_path: Path) -> str:
    """Classify a file as 'spec', 'adr', or 'session_summary'."""
    path_str = str(file_path).lower()
    if "architecture" in path_str or "adr" in path_str:
        return "adr"
    if "session" in path_str:
        return "session_summary"
    return "spec"


def _extract_reference_time(file_path: Path, content: str) -> datetime:
    """Extract a reference time from the file — frontmatter, filename date, or mtime."""
    import frontmatter as fm

    # Try frontmatter
    try:
        import datetime as dt_module
        post = fm.loads(content)
        for key in ("date", "session_date", "created", "created_at"):
            if key in post.metadata:
                val = post.metadata[key]
                if isinstance(val, datetime):
                    return val
                if isinstance(val, dt_module.date) and not isinstance(val, datetime):
                    # YAML auto-parses YYYY-MM-DD as date, not datetime
                    return datetime(val.year, val.month, val.day)
                if isinstance(val, str):
                    return datetime.fromisoformat(val)
    except Exception:
        pass

    # Try filename date patterns (e.g. SPRINT_2026-04-01.md or 2026-03-22_topic.md)
    import re

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
    if date_match:
        return datetime.fromisoformat(date_match.group(1))

    # Fall back to file modification time
    return datetime.fromtimestamp(file_path.stat().st_mtime)


async def ingest_spec_file(file_path: Path, repo_name: str = "primary") -> dict:
    """Ingest a single spec/doc file."""
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        logger.warning("GRAPHITI_READ_ONLY=true — skipping ingestion of %s", file_path.name)
        return {"skipped": True, "reason": "read_only"}

    content = file_path.read_text(encoding="utf-8")

    if is_already_ingested(content):
        logger.info("Already ingested (same content): %s", file_path.name)
        return {"skipped": True, "reason": "already_ingested", "file": file_path.name}

    source_type = _classify_source(file_path)
    ref_time = _extract_reference_time(file_path, content)

    graphiti = await get_graphiti()

    logger.info("Ingesting spec: %s (type=%s, date=%s)", file_path.name, source_type, ref_time)

    try:
        result = await asyncio.wait_for(
            graphiti.add_episode(
                name=file_path.stem,
                episode_body=content,
                source=EpisodeType.text,
                source_description=source_type,
                reference_time=ref_time,
                group_id=settings.GRAPHITI_GROUP_ID,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
            ),
            timeout=300,  # 5 min per episode — prevents Gemini API hangs
        )
    except asyncio.TimeoutError:
        logger.error("Timeout ingesting %s (exceeded 300s)", file_path.name)
        return {"file": file_path.name, "error": "timeout_300s"}

    mark_ingested(content)

    summary = {
        "file": file_path.name,
        "source_type": source_type,
        "reference_time": ref_time.isoformat(),
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


async def ingest_repo_specs(repo_name: str) -> list[dict]:
    """Ingest all spec files from a repo's docs/ directories."""
    settings = get_settings()
    name_lower = repo_name.lower()
    if name_lower == "primary":
        repo_path = Path(settings.PRIMARY_REPO_PATH)
    elif name_lower == "secondary":
        repo_path = Path(settings.SECONDARY_REPO_PATH)
    else:
        raise ValueError(f"Unknown repo: {repo_name}. Use 'primary' or 'secondary'.")

    if not repo_path or not repo_path.exists():
        raise ValueError(f"Repo path does not exist: {repo_path}")

    results = []
    for spec_dir in _SPEC_DIRS:
        dir_path = repo_path / spec_dir
        if not dir_path.exists():
            continue

        for md_file in sorted(dir_path.glob("*.md")):
            if md_file.name == "TEMPLATE.md":
                continue
            try:
                result = await ingest_spec_file(md_file, repo_name)
                results.append(result)
            except Exception as e:
                logger.error("Failed to ingest %s: %s", md_file.name, e)
                results.append({"file": md_file.name, "error": str(e)})

    return results


async def main():
    parser = argparse.ArgumentParser(description="Ingest spec files into Dev Brain")
    parser.add_argument("--repo", type=str, help="Repo name: primary or secondary")
    parser.add_argument("--file", type=Path, help="Single file to ingest")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    try:
        if args.file:
            result = await ingest_spec_file(args.file)
            print(json.dumps(result, indent=2, default=str))
        elif args.repo:
            results = await ingest_repo_specs(args.repo)
            ingested = [r for r in results if not r.get("skipped")]
            print(f"Ingested {len(ingested)} / {len(results)} spec files")
        else:
            parser.print_help()
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
