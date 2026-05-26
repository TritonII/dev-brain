"""
Dev Brain MCP Server
====================

Exposes the Dev Brain knowledge graph to Claude Code and Claude Desktop
via the Model Context Protocol.

Transport: stdio (for Claude Code / Claude Desktop)

Tools:
  - search_brain: Combined semantic search across entities, facts, and episodes
  - search_nodes: Find entity nodes by semantic similarity
  - search_facts: Find relationships/edges between entities
  - get_recent_activity: Recent development episodes by time
  - get_entity_neighbors: Deep-dive into one entity's connections
  - get_active_decisions: Active architectural decisions
  - get_open_problems: Open/investigating problems
  - ingest_session_note: Write a session note directly into the Brain

Usage:
    python -m brain_mcp.run_server

Claude Code config (~/.claude/settings.json):
    {
      "mcpServers": {
        "dev-brain": {
          "command": "<path-to-dev-brain>/.venv/Scripts/python.exe",
          "args": ["-m", "brain_mcp.run_server"],
          "cwd": "<path-to-dev-brain>"
        }
      }
    }
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure dev-brain/ is on the path when run as module
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings

logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(
    "dev-brain",
    instructions=(
        "Dev Brain is a temporal knowledge graph of development history. "
        "It contains entities (DevSession, Decision, Problem, Experiment, Concept, Artifact), "
        "relationships (SUPERSEDES, VALIDATES, CONTRADICTS, BLOCKS, DERIVED_FROM, etc.), "
        "and episodes (ingested sessions, specs, git commits). "
        "Use search_brain for general queries, search_nodes for entity lookup, "
        "search_facts for relationships, and get_recent_activity for timeline context. "
        "Always cite source episodes when answering questions."
    ),
)


def _format_node(node, score: float | None = None) -> str:
    """Format an EntityNode for display."""
    name = getattr(node, "name", "unnamed")
    summary = getattr(node, "summary", "") or ""
    attrs = getattr(node, "attributes", {}) or {}
    created = getattr(node, "created_at", None)

    parts = [f"**{name}**"]
    if score is not None:
        parts[0] += f" (score: {score:.2f})"
    if summary:
        parts.append(summary)
    if attrs:
        attr_lines = "\n".join(f"  - {k}: {v}" for k, v in attrs.items() if v)
        if attr_lines:
            parts.append(attr_lines)
    if created:
        parts.append(f"  _created: {created}_")

    return "\n".join(parts)


def _format_edge(edge, score: float | None = None) -> str:
    """Format an EntityEdge for display."""
    fact = getattr(edge, "fact", str(edge))
    name = getattr(edge, "name", "")
    valid_at = getattr(edge, "valid_at", None)

    parts = []
    if name:
        header = f"**[{name}]** {fact}"
    else:
        header = f"**Fact:** {fact}"
    if score is not None:
        header += f" (score: {score:.2f})"
    parts.append(header)
    if valid_at:
        parts.append(f"  _valid_at: {valid_at}_")

    return "\n".join(parts)


def _format_episode(episode) -> str:
    """Format an EpisodicNode for display."""
    name = getattr(episode, "name", "unnamed")
    source_desc = getattr(episode, "source_description", "")
    valid_at = getattr(episode, "valid_at", None)
    content = getattr(episode, "content", "") or ""

    # Truncate content for readability
    if len(content) > 500:
        content = content[:500] + "..."

    parts = [f"**{name}** ({source_desc})"]
    if valid_at:
        parts.append(f"  _date: {valid_at}_")
    if content:
        parts.append(f"  {content}")

    return "\n".join(parts)


# ── Tool: search_brain ──────────────────────────────────────────────────────

@mcp.tool()
async def search_brain(query: str, num_results: int = 10) -> str:
    """
    Combined semantic search across the Dev Brain — returns entities, facts, and episodes.

    This is the primary search tool. Use it for broad questions about development history,
    architectural decisions, past experiments, known problems, or any technical concept.

    Args:
        query: Natural language question (e.g. "What decisions about caching strategy?")
        num_results: Max results per category (default 10)
    """
    from graphiti_core.search.search_config import SearchConfig, NodeSearchConfig, EdgeSearchConfig, EpisodeSearchConfig
    from graphiti_core.search.search_config_recipes import (
        NODE_HYBRID_SEARCH_RRF,
        EDGE_HYBRID_SEARCH_RRF,
    )

    settings = get_settings()
    graphiti = await get_graphiti()

    # Combined search: nodes + edges (RRF reranking, no cross-encoder dependency)
    config = SearchConfig(
        node_config=NODE_HYBRID_SEARCH_RRF.node_config,
        edge_config=EDGE_HYBRID_SEARCH_RRF.edge_config,
        limit=num_results,
    )

    results = await graphiti.search_(
        query=query,
        config=config,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    output_parts = []

    # Nodes (entities)
    if results.nodes:
        output_parts.append(f"### Entities ({len(results.nodes)} found)\n")
        for i, node in enumerate(results.nodes):
            score = results.node_reranker_scores[i] if i < len(results.node_reranker_scores) else None
            output_parts.append(f"{i+1}. {_format_node(node, score)}")

    # Edges (facts/relationships)
    if results.edges:
        output_parts.append(f"\n### Facts ({len(results.edges)} found)\n")
        for i, edge in enumerate(results.edges):
            score = results.edge_reranker_scores[i] if i < len(results.edge_reranker_scores) else None
            output_parts.append(f"{i+1}. {_format_edge(edge, score)}")

    if not output_parts:
        return f"No results found for: {query}"

    return "\n\n".join(output_parts)


# ── Tool: search_nodes ──────────────────────────────────────────────────────

@mcp.tool()
async def search_nodes(query: str, num_results: int = 10) -> str:
    """
    Search for entity nodes in the Dev Brain by semantic similarity.

    Returns DevSession, Decision, Problem, Experiment, Concept, and Artifact entities.
    Use this when you want to find specific entities rather than relationships.

    Args:
        query: Natural language description of what you're looking for
        num_results: Max results (default 10)
    """
    from graphiti_core.search.search_config import SearchConfig
    from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

    settings = get_settings()
    graphiti = await get_graphiti()

    config = SearchConfig(
        node_config=NODE_HYBRID_SEARCH_RRF.node_config,
        limit=num_results,
    )

    results = await graphiti.search_(
        query=query,
        config=config,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    if not results.nodes:
        return f"No entities found for: {query}"

    output_parts = [f"**{len(results.nodes)} entities found:**\n"]
    for i, node in enumerate(results.nodes):
        score = results.node_reranker_scores[i] if i < len(results.node_reranker_scores) else None
        output_parts.append(f"{i+1}. {_format_node(node, score)}")

    return "\n\n".join(output_parts)


# ── Tool: search_facts ──────────────────────────────────────────────────────

@mcp.tool()
async def search_facts(query: str, num_results: int = 10) -> str:
    """
    Search for relationships (facts/edges) in the Dev Brain.

    Returns temporal facts like SUPERSEDES, VALIDATES, CONTRADICTS, BLOCKS, DERIVED_FROM.
    Each fact connects two entities and has a natural language description.

    Args:
        query: Natural language question about relationships
        num_results: Max results (default 10)
    """
    settings = get_settings()
    graphiti = await get_graphiti()

    # graphiti.search() returns list[EntityEdge] — focused on facts
    edges = await graphiti.search(
        query=query,
        num_results=num_results,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    if not edges:
        return f"No relationships found for: {query}"

    output_parts = [f"**{len(edges)} facts found:**\n"]
    for i, edge in enumerate(edges):
        output_parts.append(f"{i+1}. {_format_edge(edge)}")

    return "\n\n".join(output_parts)


# ── Tool: get_recent_activity ────────────────────────────────────────────────

@mcp.tool()
async def get_recent_activity(last_n: int = 10, source_type: str | None = None) -> str:
    """
    Get recent development activity from the knowledge graph.

    Returns the most recent episodes (session summaries, spec ingestions, git commits)
    ordered by time. Useful for understanding what was worked on recently.

    Args:
        last_n: Number of recent episodes to return (default 10, max 50)
        source_type: Optional filter — "session_summary", "spec", "adr", "git_commit", etc.
    """
    from graphiti_core.nodes import EpisodeType

    settings = get_settings()
    graphiti = await get_graphiti()

    last_n = min(last_n, 50)

    episodes = await graphiti.retrieve_episodes(
        reference_time=datetime.now(timezone.utc),
        last_n=last_n,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    if source_type:
        episodes = [e for e in episodes if source_type.lower() in (getattr(e, "source_description", "") or "").lower()]

    if not episodes:
        msg = "No recent episodes found."
        if source_type:
            msg += f" (filter: {source_type})"
        return msg

    output_parts = [f"**{len(episodes)} recent episodes:**\n"]
    for i, ep in enumerate(episodes):
        output_parts.append(f"{i+1}. {_format_episode(ep)}")

    return "\n\n".join(output_parts)


# ── Tool: get_entity_neighbors ───────────────────────────────────────────────

@mcp.tool()
async def get_entity_neighbors(entity_name: str, num_results: int = 10) -> str:
    """
    Deep-dive into a specific entity — find it and return all connected facts and neighbors.

    First searches for the entity by name, then uses BFS (breadth-first search) to find
    all relationships radiating from it. Useful for understanding an entity's full context.

    Args:
        entity_name: Name or description of the entity to explore
        num_results: Max related facts to return (default 10)
    """
    from graphiti_core.search.search_config import SearchConfig
    from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

    settings = get_settings()
    graphiti = await get_graphiti()

    # Step 1: Find the entity
    node_config = SearchConfig(
        node_config=NODE_HYBRID_SEARCH_RRF.node_config,
        limit=1,
    )
    node_results = await graphiti.search_(
        query=entity_name,
        config=node_config,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    if not node_results.nodes:
        return f"Entity not found: {entity_name}"

    center_node = node_results.nodes[0]
    center_uuid = center_node.uuid

    # Step 2: Search for facts connected to this entity
    edges = await graphiti.search(
        query=entity_name,
        center_node_uuid=center_uuid,
        num_results=num_results,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    output_parts = [
        f"### Entity: {_format_node(center_node)}\n",
        f"### Connected Facts ({len(edges)} found)\n",
    ]
    for i, edge in enumerate(edges):
        output_parts.append(f"{i+1}. {_format_edge(edge)}")

    return "\n\n".join(output_parts)


# ── Tool: get_active_decisions ───────────────────────────────────────────────

@mcp.tool()
async def get_active_decisions(domain: str | None = None) -> str:
    """
    Get active architectural and product decisions from the knowledge graph.

    Uses semantic search to find Decision entities. Optionally filter by domain.

    Args:
        domain: Optional domain filter — e.g. "architecture", "extraction_pipeline",
                "frontend", "data_model", "infrastructure", "product", "tooling"
    """
    settings = get_settings()
    graphiti = await get_graphiti()

    query = "active architectural decisions"
    if domain:
        query = f"active decisions about {domain}"

    from graphiti_core.search.search_config import SearchConfig
    from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

    config = SearchConfig(
        node_config=NODE_HYBRID_SEARCH_RRF.node_config,
        limit=25,
    )

    results = await graphiti.search_(
        query=query,
        config=config,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    if not results.nodes:
        return "No active decisions found." + (f" (domain: {domain})" if domain else "")

    # Filter to nodes that look like decisions (by name or summary)
    decision_nodes = []
    for node in results.nodes:
        name = (getattr(node, "name", "") or "").lower()
        summary = (getattr(node, "summary", "") or "").lower()
        if any(kw in name or kw in summary for kw in ("decision", "chose", "adopted", "selected", "architecture", "design")):
            decision_nodes.append(node)

    if not decision_nodes:
        # Fall back to all results if keyword filter is too strict
        decision_nodes = results.nodes[:10]

    output_parts = [f"**Active Decisions** ({len(decision_nodes)} found):\n"]
    for i, node in enumerate(decision_nodes):
        output_parts.append(f"{i+1}. {_format_node(node)}")

    return "\n\n".join(output_parts)


# ── Tool: get_open_problems ──────────────────────────────────────────────────

@mcp.tool()
async def get_open_problems(severity: str | None = None) -> str:
    """
    Get open or investigating problems from the knowledge graph.

    Uses semantic search to find Problem entities and related issues.

    Args:
        severity: Optional filter — "critical", "high", "medium", "low"
    """
    settings = get_settings()
    graphiti = await get_graphiti()

    query = "open problems bugs issues blockers"
    if severity:
        query = f"{severity} severity problems and issues"

    from graphiti_core.search.search_config import SearchConfig
    from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

    config = SearchConfig(
        node_config=NODE_HYBRID_SEARCH_RRF.node_config,
        limit=25,
    )

    results = await graphiti.search_(
        query=query,
        config=config,
        group_ids=[settings.GRAPHITI_GROUP_ID],
    )

    if not results.nodes:
        return "No open problems found." + (f" (severity: {severity})" if severity else "")

    # Filter to nodes that look like problems
    problem_nodes = []
    for node in results.nodes:
        name = (getattr(node, "name", "") or "").lower()
        summary = (getattr(node, "summary", "") or "").lower()
        if any(kw in name or kw in summary for kw in ("problem", "bug", "issue", "error", "fail", "block", "broke", "regression")):
            problem_nodes.append(node)

    if not problem_nodes:
        problem_nodes = results.nodes[:10]

    output_parts = [f"**Open Problems** ({len(problem_nodes)} found):\n"]
    for i, node in enumerate(problem_nodes):
        output_parts.append(f"{i+1}. {_format_node(node)}")

    return "\n\n".join(output_parts)


# ── Tool: ingest_session_note ────────────────────────────────────────────────

@mcp.tool()
async def ingest_session_note(title: str, content: str) -> str:
    """
    Write a session note directly into the Dev Brain knowledge graph.

    Use this at the end of a development session to capture decisions, problems encountered,
    experiments tried, and key learnings. The Brain will automatically extract entities
    and relationships from the content.

    Tips for richer extraction:
    - Mention decisions explicitly: "Decision: We chose X over Y because..."
    - Mention problems: "Problem: The API returns 500 because..."
    - Mention experiments: "Experiment: Tried caching strategy X..."
    - Reference files: "Changed backend/config.py to add..."

    Args:
        title: Short title for the session (e.g. "API caching sprint")
        content: Full session content — decisions, problems, learnings, changes made
    """
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        return "GRAPHITI_READ_ONLY=true — ingestion disabled."

    graphiti = await get_graphiti()

    from graphiti_core.nodes import EpisodeType
    from entities import ENTITY_TYPES, EDGE_TYPES

    try:
        result = await asyncio.wait_for(
            graphiti.add_episode(
                name=f"session_note_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                episode_body=f"# {title}\n\n{content}",
                source=EpisodeType.text,
                source_description="session_note_mcp",
                reference_time=datetime.now(timezone.utc),
                group_id=settings.GRAPHITI_GROUP_ID,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
            ),
            timeout=300,
        )

        entities = [n.name for n in result.nodes] if result.nodes else []
        edges_count = len(result.edges) if result.edges else 0

        return (
            f"Session note ingested: **{title}**\n"
            f"- Entities extracted: {len(entities)} — {', '.join(entities[:10])}\n"
            f"- Relationships created: {edges_count}"
        )
    except asyncio.TimeoutError:
        return f"Timeout ingesting session note (exceeded 300s). The note was not saved."
    except Exception as e:
        return f"Error ingesting session note: {e}"


# ── Server entry point ───────────────────────────────────────────────────────

def main():
    """Run the MCP server with stdio transport."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol — logs go to stderr
    )
    logger.info("Starting Dev Brain MCP server (stdio transport)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
