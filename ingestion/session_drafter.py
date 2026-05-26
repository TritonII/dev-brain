"""
AI Session Summary Drafter
==========================

Analyzes recent git commit messages and changed files, prompting Gemini
to auto-draft a rich, highly structured developer session note.

Uses GitPython and the Graphiti LLM client.
"""

import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

from git import Repo
from config.settings import get_settings
from config.graphiti_init import get_graphiti

logger = logging.getLogger(__name__)


def _get_git_history(repo_path: Path, max_commits: int = 15) -> str:
    """Read the last N commits and changed files from the local Git repo."""
    try:
        repo = Repo(str(repo_path))
        if repo.bare:
            return "Error: Repository is bare."
        
        commits = list(repo.iter_commits("HEAD", max_count=max_commits))
        
        if not commits:
            return "No recent commits found in the repository."
            
        history_parts = []
        for i, commit in enumerate(commits, start=1):
            files_changed = []
            try:
                if commit.parents:
                    diff = commit.parents[0].diff(commit)
                    files_changed = [d.a_path or d.b_path for d in diff]
                else:
                    files_changed = [item.path for item in commit.tree.traverse()]
            except Exception:
                pass
                
            files_str = ", ".join(files_changed[:15])
            if len(files_changed) > 15:
                files_str += f" ... and {len(files_changed) - 15} more files"
                
            history_parts.append(
                f"Commit #{i}: {commit.hexsha[:8]}\n"
                f"Author: {commit.author.name}\n"
                f"Date: {commit.committed_datetime.isoformat()}\n"
                f"Message: {commit.message.strip()}\n"
                f"Files changed: {files_str}\n"
                f"----------------------------------------"
            )
            
        return "\n".join(history_parts)
    except Exception as e:
        logger.error("Failed to read git history: %s", e)
        return f"Error gathering git history: {e}"


async def draft_session_summary(repo_path_override: Optional[Path] = None) -> tuple[str, str]:
    """
    Compiles recent commits and prompts Gemini to draft a formatted session summary.
    
    Returns:
        Tuple of (draft_title, draft_content_markdown)
    """
    settings = get_settings()
    
    # Resolve repository path: use override, configured path, or fall back to dev-brain itself
    repo_path = repo_path_override
    if not repo_path:
        if settings.PRIMARY_REPO_PATH:
            repo_path = Path(settings.PRIMARY_REPO_PATH)
        else:
            repo_path = Path(__file__).parent.parent
            
    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    # Step 1: Compile Git history
    git_history = _get_git_history(repo_path)
    
    # Step 2: Initialize Graphiti LLM Client
    graphiti = await get_graphiti()
    llm = graphiti.llm_client
    
    prompt = (
        "You are an expert software architect and technical writer.\n"
        "Your task is to analyze the following recent git history (commits, authors, messages, and changed files) "
        "and auto-draft a rich, professional, and highly detailed developer session note.\n\n"
        "Recent Git History:\n"
        f"\"\"\"\n{git_history}\n\"\"\"\n\n"
        "Draft the session note strictly in Markdown format, capturing:\n"
        "1. Context (overall focus, high-level summary of what was worked on based on changed files).\n"
        "2. Decisions Made (identify key choices, use the explicit keyword 'Decision: We chose [Option A] over [Option B] because [Rationale]' for any architectural or engineering changes, status='active').\n"
        "3. Experiments Run (extract any experimental testing/hypotheses and outcomes, if mentioned).\n"
        "4. Problems Resolved / Encountered (extract bugs fixed or blockers identified, state severity).\n\n"
        "Guidelines:\n"
        "- Do not make up fake metrics; ground it strictly in the git messages.\n"
        "- Exclude any introduction or conversational framing. Output ONLY the drafted title and markdown content.\n"
        "- Output the response in JSON format containing two keys: 'title' (a short, catchy sprint-style title, e.g., 'API Caching Tier') and 'content' (the full Markdown body description)."
    )

    try:
        response_text = await llm.generate(prompt)
        
        # Parse JSON from LLM response (handling potential markdown packaging)
        import json
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        data = json.loads(clean_text.strip())
        return data.get("title", "Recent Development Sprint"), data.get("content", response_text)
        
    except Exception as e:
        logger.error("Failed to generate draft session via Gemini: %s", e)
        # Return fallback draft
        return "Recent Development Sprint", f"# Context\n\nRecent git commits analyzed:\n\n{git_history}"
