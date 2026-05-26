"""
Bulk Backfill
=============

One-shot script that ingests historical data into the Dev Brain.
Processes in order: sessions (richest) -> specs -> commits.

Includes rate limiting, error recovery, and progress tracking.
Idempotent — safe to run multiple times.

CLI:
    python -m ingestion.bulk_backfill --sessions --specs --commits-since 2026-01-25
    python -m ingestion.bulk_backfill --all --commits-since 2026-01-25
"""

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings
from ingestion.idempotency import get_ingested_count

logger = logging.getLogger(__name__)


async def run_backfill(
    sessions: bool = False,
    specs: bool = False,
    commits: bool = False,
    commits_since: datetime | None = None,
    delay: float = 0.5,
) -> dict:
    """
    Run the bulk backfill pipeline.

    Args:
        sessions: Ingest session summaries
        specs: Ingest spec/ADR files
        commits: Ingest git commits
        commits_since: Only commits after this date
        delay: Seconds between episodes (rate limiting)

    Returns:
        Summary dict with counts per source type
    """
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        logger.error("GRAPHITI_READ_ONLY=true — cannot run backfill")
        return {"error": "read_only"}

    # Ensure Graphiti client is ready
    await get_graphiti()

    summary = {
        "started_at": datetime.now().isoformat(),
        "pre_existing_episodes": get_ingested_count(),
        "sessions": None,
        "specs": None,
        "commits": None,
    }

    start = time.time()

    # Phase 1: Sessions (richest semantic content — gives Graphiti the strongest scaffold)
    if sessions:
        from ingestion.session_ingestor import ingest_directory

        session_dir = Path(settings.PRIMARY_REPO_PATH) / "docs" / "sessions"
        if session_dir.exists():
            logger.info("=== Phase 1: Ingesting sessions from %s ===", session_dir)
            results = await ingest_directory(session_dir)
            summary["sessions"] = {
                "total": len(results),
                "ingested": len([r for r in results if not r.get("skipped")]),
                "skipped": len([r for r in results if r.get("skipped")]),
                "errors": len([r for r in results if "error" in r]),
            }
            logger.info("Sessions: %s", summary["sessions"])
            await asyncio.sleep(delay)
        else:
            logger.warning("Session directory not found: %s", session_dir)

    # Phase 2: Specs
    if specs:
        from ingestion.spec_ingestor import ingest_repo_specs

        logger.info("=== Phase 2: Ingesting specs ===")
        for repo_name in ["primary", "secondary"]:
            try:
                repo_path_attr = (
                    settings.PRIMARY_REPO_PATH
                    if repo_name == "primary"
                    else settings.SECONDARY_REPO_PATH
                )
                if not repo_path_attr:
                    logger.info("Skipping %s (path not configured)", repo_name)
                    continue

                results = await ingest_repo_specs(repo_name)
                summary["specs"] = summary.get("specs") or {}
                summary["specs"][repo_name] = {
                    "total": len(results),
                    "ingested": len([r for r in results if not r.get("skipped")]),
                    "skipped": len([r for r in results if r.get("skipped")]),
                    "errors": len([r for r in results if "error" in r]),
                }
                logger.info("%s specs: %s", repo_name, summary["specs"][repo_name])
            except ValueError as e:
                logger.warning("Skipping %s: %s", repo_name, e)
            await asyncio.sleep(delay)

    # Phase 3: Commits (thinnest context — scaffold already built from sessions + specs)
    if commits:
        from ingestion.commit_ingestor import ingest_commits

        logger.info("=== Phase 3: Ingesting commits ===")
        for repo_name in ["primary", "secondary"]:
            try:
                repo_path_attr = (
                    settings.PRIMARY_REPO_PATH
                    if repo_name == "primary"
                    else settings.SECONDARY_REPO_PATH
                )
                if not repo_path_attr:
                    logger.info("Skipping %s (path not configured)", repo_name)
                    continue

                results = await ingest_commits(repo_name, since=commits_since)
                summary["commits"] = summary.get("commits") or {}
                summary["commits"][repo_name] = {
                    "total": len(results),
                    "ingested": len([r for r in results if "error" not in r and not r.get("skipped")]),
                    "errors": len([r for r in results if "error" in r]),
                }
                logger.info("%s commits: %s", repo_name, summary["commits"][repo_name])
            except ValueError as e:
                logger.warning("Skipping %s: %s", repo_name, e)

    elapsed = time.time() - start
    summary["elapsed_seconds"] = round(elapsed, 1)
    summary["post_episodes"] = get_ingested_count()
    summary["new_episodes"] = summary["post_episodes"] - summary["pre_existing_episodes"]

    return summary


async def main():
    parser = argparse.ArgumentParser(description="Bulk backfill Dev Brain knowledge graph")
    parser.add_argument("--sessions", action="store_true", help="Ingest session summaries")
    parser.add_argument("--specs", action="store_true", help="Ingest spec/ADR files")
    parser.add_argument("--commits", action="store_true", help="Ingest git commits")
    parser.add_argument("--all", action="store_true", help="Ingest everything")
    parser.add_argument("--commits-since", type=str, help="Only commits after this date (YYYY-MM-DD)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between episodes (seconds)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.all:
        args.sessions = args.specs = args.commits = True

    if not (args.sessions or args.specs or args.commits):
        parser.print_help()
        return

    commits_since = datetime.fromisoformat(args.commits_since) if args.commits_since else None

    try:
        summary = await run_backfill(
            sessions=args.sessions,
            specs=args.specs,
            commits=args.commits,
            commits_since=commits_since,
            delay=args.delay,
        )

        # Save summary
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_file.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

        print("\n=== Backfill Summary ===")
        print(json.dumps(summary, indent=2, default=str))
        print(f"\nResults saved to {log_file}")
    finally:
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
