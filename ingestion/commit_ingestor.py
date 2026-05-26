"""
Commit Ingestor
===============

Ingests git commits from configured repos into the Dev Brain knowledge graph.

Cursor-based: tracks the last ingested commit per repo in ingestion/state/.
Convention keywords in commit messages trigger richer extraction instructions:
  - "Decision:" -> forces Decision entity creation
  - "Fix:" -> creates Problem (resolved) + Decision
  - "Experiment:" -> creates Experiment
  - "Refs:" -> creates REFERENCES edge to Artifact

CLI:
    python -m ingestion.commit_ingestor --repo primary
    python -m ingestion.commit_ingestor --repo primary --single HEAD
    python -m ingestion.commit_ingestor --all --since 2026-01-01
"""

import argparse
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from git import Repo
from graphiti_core.nodes import EpisodeType

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings
from entities import ENTITY_TYPES, EDGE_TYPES
from ingestion.idempotency import is_already_ingested, mark_ingested

logger = logging.getLogger(__name__)

_STATE_DIR = Path(__file__).parent / "state"

# Keywords that trigger richer extraction instructions
_KEYWORD_PATTERNS = {
    "decision": re.compile(r"^Decision:", re.IGNORECASE | re.MULTILINE),
    "fix": re.compile(r"^Fix:", re.IGNORECASE | re.MULTILINE),
    "experiment": re.compile(r"^Experiment:", re.IGNORECASE | re.MULTILINE),
    "refs": re.compile(r"^Refs:", re.IGNORECASE | re.MULTILINE),
}


def _get_cursor_file(repo_name: str) -> Path:
    """Path to cursor file tracking last ingested commit."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    return _STATE_DIR / f"last_commit_{repo_name.lower()}.txt"


def _read_cursor(repo_name: str) -> str | None:
    """Read the last ingested commit SHA for a repo."""
    cursor_file = _get_cursor_file(repo_name)
    if cursor_file.exists():
        return cursor_file.read_text(encoding="utf-8").strip()
    return None


def _write_cursor(repo_name: str, sha: str) -> None:
    """Update the cursor to the given commit SHA."""
    _get_cursor_file(repo_name).write_text(sha, encoding="utf-8")


def _build_episode_body(commit) -> str:
    """Build episode content from a git commit."""
    files_changed = []
    try:
        if commit.parents:
            diff = commit.parents[0].diff(commit)
            files_changed = [d.a_path or d.b_path for d in diff]
        else:
            # Initial commit
            files_changed = [item.path for item in commit.tree.traverse()]
    except Exception:
        pass

    files_section = "\n".join(f"  - {f}" for f in files_changed[:50])  # Cap at 50 files
    if len(files_changed) > 50:
        files_section += f"\n  ... and {len(files_changed) - 50} more files"

    return (
        f"Commit: {commit.hexsha}\n"
        f"Author: {commit.author.name}\n"
        f"Date: {commit.committed_datetime.isoformat()}\n"
        f"Message: {commit.message.strip()}\n"
        f"\nFiles changed:\n{files_section}"
    )


def _build_extraction_instructions(message: str) -> str | None:
    """Build custom extraction instructions based on commit message keywords."""
    instructions = []

    if _KEYWORD_PATTERNS["decision"].search(message):
        instructions.append(
            "This commit contains an explicit architectural decision. "
            "Extract a Decision entity with status='active'."
        )
    if _KEYWORD_PATTERNS["fix"].search(message):
        instructions.append(
            "This commit fixes a bug. Extract a Problem entity with status='resolved' "
            "and a Decision entity describing the fix approach."
        )
    if _KEYWORD_PATTERNS["experiment"].search(message):
        instructions.append(
            "This commit describes an experiment. Extract an Experiment entity "
            "with hypothesis, approach, outcome, and success fields."
        )
    if _KEYWORD_PATTERNS["refs"].search(message):
        instructions.append(
            "This commit references a spec or document. Extract a References edge "
            "linking the commit Artifact to the referenced Artifact."
        )

    return " ".join(instructions) if instructions else None


def _get_repo_path(repo_name: str) -> Path:
    """Resolve repo name to filesystem path."""
    settings = get_settings()
    name_lower = repo_name.lower()
    if name_lower == "primary":
        path = settings.PRIMARY_REPO_PATH
    elif name_lower == "secondary":
        path = settings.SECONDARY_REPO_PATH
    else:
        raise ValueError(
            f"Unknown repo: {repo_name}. Use 'primary' or 'secondary', "
            f"or configure PRIMARY_REPO_PATH / SECONDARY_REPO_PATH in .env"
        )

    if not path:
        raise ValueError(f"Repo path not configured for {repo_name}. Set in .env")
    return Path(path)


async def ingest_commits(
    repo_name: str,
    since: datetime | None = None,
    single_ref: str | None = None,
    max_commits: int | None = None,
) -> list[dict]:
    """
    Ingest git commits from a repo.

    Args:
        repo_name: "primary" or "secondary" (maps to env vars)
        since: Only ingest commits after this date
        single_ref: Ingest only this specific ref (e.g. "HEAD")
        max_commits: Cap the number of commits to ingest
    """
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        logger.warning("GRAPHITI_READ_ONLY=true — skipping commit ingestion")
        return [{"skipped": True, "reason": "read_only"}]

    repo_path = _get_repo_path(repo_name)
    repo = Repo(str(repo_path))
    graphiti = await get_graphiti()

    results = []

    if single_ref:
        # Ingest a single commit
        commit = repo.commit(single_ref)
        commits = [commit]
    else:
        # Get commits since cursor or date
        cursor_sha = _read_cursor(repo_name)

        rev_args = {}
        if cursor_sha:
            rev_args["rev"] = f"{cursor_sha}..HEAD"
        elif since:
            rev_args["rev"] = "HEAD"
            rev_args["since"] = since.isoformat()
        else:
            rev_args["rev"] = "HEAD"
            rev_args["max_count"] = max_commits or 500

        if max_commits:
            rev_args["max_count"] = max_commits

        commits = list(repo.iter_commits(**rev_args))
        commits.reverse()  # Oldest first for correct temporal ordering

    logger.info("Processing %d commits from %s", len(commits), repo_name)

    for i, commit in enumerate(commits):
        body = _build_episode_body(commit)

        if is_already_ingested(body):
            logger.debug("Skipping already-ingested commit %s", commit.hexsha[:8])
            continue

        custom_instructions = _build_extraction_instructions(commit.message)

        try:
            result = await asyncio.wait_for(
                graphiti.add_episode(
                    name=f"{repo_name.lower()}_{commit.hexsha[:8]}",
                    episode_body=body,
                    source=EpisodeType.text,
                    source_description=f"git_commit:{repo_name}",
                    reference_time=commit.committed_datetime,
                    group_id=settings.GRAPHITI_GROUP_ID,
                    entity_types=ENTITY_TYPES,
                    edge_types=EDGE_TYPES,
                    custom_extraction_instructions=custom_instructions,
                ),
                timeout=300,  # 5 min per episode — prevents Gemini API hangs
            )

            mark_ingested(body)

            summary = {
                "sha": commit.hexsha[:8],
                "message": commit.message.strip()[:100],
                "entities_created": len(result.nodes),
                "edges_created": len(result.edges),
            }
            results.append(summary)

            if (i + 1) % 10 == 0:
                logger.info("Progress: %d / %d commits", i + 1, len(commits))

        except Exception as e:
            logger.error("Failed to ingest commit %s: %s", commit.hexsha[:8], e)
            results.append({"sha": commit.hexsha[:8], "error": str(e)})

    # Update cursor to latest commit
    if commits and not single_ref:
        _write_cursor(repo_name, commits[-1].hexsha)
        logger.info("Cursor updated to %s", commits[-1].hexsha[:8])

    return results


async def main():
    parser = argparse.ArgumentParser(description="Ingest git commits into Dev Brain")
    parser.add_argument("--repo", type=str, help="Repo name: primary or secondary")
    parser.add_argument("--all", action="store_true", help="Ingest from all configured repos")
    parser.add_argument("--since", type=str, help="Only commits after this date (YYYY-MM-DD)")
    parser.add_argument("--single", type=str, help="Ingest a single ref (e.g. HEAD)")
    parser.add_argument("--max", type=int, help="Max commits to ingest")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    since = datetime.fromisoformat(args.since) if args.since else None

    try:
        repos = []
        if args.all:
            repos = ["primary", "secondary"]
        elif args.repo:
            repos = [args.repo]
        else:
            parser.print_help()
            return

        for repo_name in repos:
            try:
                results = await ingest_commits(
                    repo_name, since=since, single_ref=args.single, max_commits=args.max,
                )
                ingested = [r for r in results if "error" not in r and not r.get("skipped")]
                print(f"{repo_name}: Ingested {len(ingested)} / {len(results)} commits")
            except ValueError as e:
                logger.warning("Skipping %s: %s", repo_name, e)
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
