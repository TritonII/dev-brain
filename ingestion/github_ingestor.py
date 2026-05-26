"""
GitHub Issue & Pull Request Ingestor
===================================

Ingests collaborative context — including GitHub Issues and Pull Requests —
into the Dev Brain knowledge graph.

CLI:
    python -m ingestion.github_ingestor --repo TritonII/dev-brain --since 2026-01-01
    python -m ingestion.github_ingestor --repo owner/repo --token <your-pat> --limit 10
"""

import os
import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from graphiti_core.nodes import EpisodeType

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings
from entities import ENTITY_TYPES, EDGE_TYPES
from ingestion.idempotency import is_already_ingested, mark_ingested

logger = logging.getLogger(__name__)

# GitHub REST API base URL
_API_BASE_URL = "https://api.github.com"


class GitHubClient:
    """Simple wrapper over HTTPX to communicate with the GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
            
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)

    async def get_issues_and_prs(self, owner: str, repo: str, since: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Fetch issues and PRs (both open and closed) from GitHub repository."""
        url = f"{_API_BASE_URL}/repos/{owner}/{repo}/issues"
        params = {
            "state": "all",
            "per_page": min(limit, 100),
            "sort": "created",
            "direction": "asc"
        }
        if since:
            params["since"] = since

        logger.info("Fetching issues and PRs from GitHub: %s/%s", owner, repo)
        
        try:
            response = await self.client.get(url, params=params)
            
            if response.status_code == 401:
                raise ValueError("Unauthorized. Check your GITHUB_TOKEN.")
            elif response.status_code == 404:
                raise ValueError(f"Repository {owner}/{repo} not found. Is it private or misspelled?")
            elif response.status_code != 200:
                raise ValueError(f"GitHub API Error ({response.status_code}): {response.text}")
                
            issues = response.json()
            return issues[:limit]
            
        except Exception as e:
            logger.error("GitHub API Request failed: %s", e)
            raise

    async def get_pr_details(self, owner: str, repo: str, number: int) -> dict:
        """Fetch full details of a specific Pull Request (e.g. merge state)."""
        url = f"{_API_BASE_URL}/repos/{owner}/{repo}/pulls/{number}"
        try:
            res = await self.client.get(url)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.warning("Failed to fetch PR #%d details: %s", number, e)
        return {}

    async def close(self):
        await self.client.aclose()


def _build_issue_episode(issue: dict) -> str:
    """Format a GitHub Issue into a structured Markdown episode body."""
    number = issue.get("number")
    title = issue.get("title", "")
    state = issue.get("state", "open")
    author = issue.get("user", {}).get("login", "unknown")
    created_at = issue.get("created_at", "")
    closed_at = issue.get("closed_at", "") or "N/A"
    body = issue.get("body", "") or "No description provided."

    return (
        f"GitHub Issue #{number}: {title}\n"
        f"State: {state}\n"
        f"Author: {author}\n"
        f"Created At: {created_at}\n"
        f"Closed At: {closed_at}\n"
        f"\nDescription:\n{body}"
    )


def _build_pr_episode(pr_details: dict) -> str:
    """Format a GitHub Pull Request into a structured Markdown episode body."""
    number = pr_details.get("number")
    title = pr_details.get("title", "")
    state = pr_details.get("state", "open")
    author = pr_details.get("user", {}).get("login", "unknown")
    created_at = pr_details.get("created_at", "")
    merged_at = pr_details.get("merged_at", "") or "N/A"
    is_merged = pr_details.get("merged", False)
    body = pr_details.get("body", "") or "No description provided."

    return (
        f"GitHub Pull Request #{number}: {title}\n"
        f"State: {state}\n"
        f"Merged: {is_merged} (Merged At: {merged_at})\n"
        f"Author: {author}\n"
        f"Created At: {created_at}\n"
        f"\nDescription:\n{body}"
    )


async def ingest_github_items(
    repo_fullname: str,
    token: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 50
) -> list[dict]:
    """Orchestrates pulling issues/PRs from GitHub and ingesting them into Dev Brain."""
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        logger.warning("GRAPHITI_READ_ONLY=true — skipping GitHub ingestion")
        return [{"skipped": True, "reason": "read_only"}]

    if "/" not in repo_fullname:
        raise ValueError("Repo must be formatted as 'owner/name'")

    owner, repo_name = repo_fullname.split("/", 1)
    
    # Use provided token or look in environment variables
    github_token = token or os.getenv("GITHUB_TOKEN")
    
    client = GitHubClient(token=github_token)
    graphiti = await get_graphiti()
    
    since_str = since.isoformat() if since else None
    results = []

    try:
        items = await client.get_issues_and_prs(owner, repo_name, since=since_str, limit=limit)
        logger.info("Found %d items to process from GitHub", len(items))

        for item in items:
            number = item.get("number")
            is_pr = "pull_request" in item
            
            ref_time = datetime.fromisoformat(item.get("created_at").replace("Z", "+00:00"))
            
            if is_pr:
                # Fetch full details of PR to check merge status
                pr_details = await client.get_pr_details(owner, repo_name, number)
                # Fall back to original item if full details fetch fails
                episode_body = _build_pr_episode(pr_details or item)
                source_desc = "github_pull_request"
                
                custom_instructions = (
                    "This episode describes a GitHub Pull Request (PR) containing code changes. "
                    "Extract an Artifact entity (with artifact_type='commit_or_pr'). "
                    "Extract any Decision entities related to the architectural or product decisions described. "
                    "If the PR describes an implementation approach or experiment, extract an Experiment entity. "
                    "Look for keywords indicating references (e.g. 'closes #10' or 'addresses issue #5') "
                    "and link the PR Artifact to those Problems or Decisions."
                )
            else:
                episode_body = _build_issue_episode(item)
                source_desc = "github_issue"
                
                custom_instructions = (
                    "This episode describes a GitHub Issue (bug report or feature request). "
                    "Extract a Problem entity. If the state is 'closed', mark the Problem status='resolved' "
                    "and, if the text describes how it was resolved, extract a Decision entity representing the fix "
                    "along with a VALIDATES or SUPERSEDES edge to connect them."
                )

            # Idempotency Layer deduplication
            if is_already_ingested(episode_body):
                logger.info("Skipping already ingested GitHub #%d (%s)", number, source_desc)
                continue

            try:
                logger.info("Ingesting GitHub #%d (%s)...", number, source_desc)
                
                result = await asyncio.wait_for(
                    graphiti.add_episode(
                        name=f"github_{source_desc}_{number}",
                        episode_body=episode_body,
                        source=EpisodeType.text,
                        source_description=source_desc,
                        reference_time=ref_time,
                        group_id=settings.GRAPHITI_GROUP_ID,
                        entity_types=ENTITY_TYPES,
                        edge_types=EDGE_TYPES,
                        custom_extraction_instructions=custom_instructions
                    ),
                    timeout=300
                )
                
                mark_ingested(episode_body)
                
                summary = {
                    "number": number,
                    "type": source_desc,
                    "title": item.get("title")[:60],
                    "entities_created": len(result.nodes),
                    "edges_created": len(result.edges)
                }
                results.append(summary)
                
            except Exception as e:
                logger.error("Failed to ingest GitHub #%d: %s", number, e)
                results.append({"number": number, "type": source_desc, "error": str(e)})

    finally:
        await client.close()
        await close_graphiti()

    return results


async def main():
    parser = argparse.ArgumentParser(description="Ingest GitHub Issues & PRs into Dev Brain")
    parser.add_argument("--repo", required=True, type=str, help="Repository name (e.g. TritonII/dev-brain)")
    parser.add_argument("--token", type=str, help="GitHub Personal Access Token (PAT) for private repos")
    parser.add_argument("--since", type=str, help="Only ingest items after this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=50, help="Max number of items to ingest (default 50)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)

    try:
        results = await ingest_github_items(
            repo_fullname=args.repo,
            token=args.token,
            since=since,
            limit=args.limit
        )
        
        ingested = [r for r in results if "error" not in r]
        print(f"\nIngested {len(ingested)} / {len(results)} items successfully from GitHub.")
        for r in results:
            status = "FAIL" if "error" in r else "PASS"
            print(f"  [{status}] #{r['number']} ({r['type']}): {r.get('title', r.get('error'))}")
            
    except Exception as e:
        logger.error("Ingestion process failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
