# Dev Brain

Persistent memory for LLM-assisted development. A [Graphiti](https://github.com/getzep/graphiti)-powered temporal knowledge graph that captures your project's decisions, experiments, problems, and concepts across working sessions — so context is never lost.

## Why?

If you use Claude Code, Cursor, or any LLM assistant for development, you've hit this:

- **"Didn't we already try that?"** — An experiment from 3 weeks ago that failed, but nobody remembers why.
- **"What did we decide about X?"** — An architectural decision buried in a chat log that's long gone.
- **"What's blocking Y?"** — A problem identified last month that's still open but lost in noise.

Dev Brain solves this by ingesting your development artifacts (session notes, git commits, specs) into a queryable knowledge graph with temporal awareness. Start a new session, ask the Brain what happened, and get real answers with provenance.

## How It Works

```
Session Notes ──┐
Git Commits ────┤──► Graphiti ──► Neo4j Knowledge Graph ──► MCP Server ──► Claude Code
Spec Documents ─┘     (LLM)        (entities + edges)        (8 tools)      (queries)
```

1. **Ingest** your development history (sessions, commits, specs/ADRs)
2. Graphiti uses Gemini to **extract entities** (Decision, Problem, Experiment, Concept, etc.) and **relationships** (SUPERSEDES, VALIDATES, CONTRADICTS, BLOCKS)
3. Everything lands in **Neo4j** as a temporal knowledge graph
4. Query via **MCP tools** from Claude Code, or directly via Cypher

## Quick Start

```bash
# Clone
git clone https://github.com/TritonII/dev-brain.git
cd dev-brain

# Install dependencies
uv sync

# Start local Neo4j (or use Aura)
docker-compose up -d

# Configure environment
cp .env.example .env
# Edit .env with your Neo4j credentials and Gemini API key

# Run tests
uv run python -m pytest tests/ -v

# Ingest a session summary
uv run python -m ingestion.session_ingestor --file docs/sessions/TEMPLATE.md

# Bulk backfill (sessions + specs + last 90 days of commits)
uv run python -m ingestion.bulk_backfill --all --commits-since 2025-01-01

# Start MCP server (for Claude Code integration)
uv run python -m brain_mcp.run_server
```

## Architecture

| Layer | Choice |
|-------|--------|
| Graph DB | Neo4j (local via Docker or Neo4j Aura) |
| Memory framework | [Graphiti](https://github.com/getzep/graphiti) (graphiti-core 0.28+) |
| LLM | Gemini 2.5 Flash via Vertex AI (or API key) |
| Embeddings | text-embedding-005 at 768 dimensions |
| MCP server | Custom wrapper over Graphiti (stdio transport) |
| Language | Python 3.11+ |

## Entity Types

| Entity | Description |
|--------|-------------|
| **DevSession** | A working session between a developer and an LLM assistant |
| **Decision** | An architectural or product decision with rationale |
| **Artifact** | A concrete output (spec, commit, PR, test result) |
| **Problem** | An unresolved issue blocking progress |
| **Experiment** | An attempted approach with measurable outcome |
| **Concept** | A cross-cutting idea or pattern (e.g. Circuit Breaker) |

### Relationship Types

| Edge | From → To | Meaning |
|------|-----------|---------|
| `SUPERSEDES` | Decision → Decision | New decision replaces an older one |
| `DERIVED_FROM` | Artifact → Artifact | Causal origin |
| `VALIDATES` | Experiment → Decision | Evidence supports |
| `CONTRADICTS` | Experiment → Decision | Evidence refutes |
| `BLOCKS` | Problem → Decision | Dependency blocker |
| `EMERGED_FROM` | Decision → DevSession | Provenance to source session |
| `REFERENCES` | any → any | Soft link |
| `TESTED_BY` | Decision → Experiment | Inverse of VALIDATES |
| `APPLIES_TO` | Concept → Decision | Concept used in context |

## MCP Integration (Claude Code)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "dev-brain": {
      "command": "/path/to/dev-brain/.venv/bin/python",
      "args": ["-m", "brain_mcp.run_server"],
      "cwd": "/path/to/dev-brain"
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| **search_brain** | Combined semantic search — entities + facts + episodes |
| **search_nodes** | Find entity nodes by semantic similarity |
| **search_facts** | Find relationships/edges between entities |
| **get_recent_activity** | Recent episodes by time, filterable by source type |
| **get_entity_neighbors** | Deep-dive: find an entity and all its connections |
| **get_active_decisions** | Active decisions, optionally filtered by domain |
| **get_open_problems** | Open problems, optionally filtered by severity |
| **ingest_session_note** | Write a session note directly into the Brain |

## CLI Commands

```bash
# Session ingestion
uv run python -m ingestion.session_ingestor --file <path>
uv run python -m ingestion.session_ingestor --dir <path> --since 2026-01-01

# Commit ingestion
uv run python -m ingestion.commit_ingestor --repo primary
uv run python -m ingestion.commit_ingestor --all --since 2026-01-01

# Spec ingestion
uv run python -m ingestion.spec_ingestor --repo primary
uv run python -m ingestion.spec_ingestor --file <path>

# Bulk backfill
uv run python -m ingestion.bulk_backfill --sessions --specs --commits-since 2025-01-01

# Git hooks
uv run python -m hooks.install_hooks
uv run python -m hooks.install_hooks --dry-run

# Smoke tests (requires backfilled data)
uv run python -m queries.smoke_tests

# Spot-check audit
uv run python -m queries.spot_check
```

## Commit Message Conventions

Use these prefixes in commit messages for richer entity extraction:

| Prefix | Extracts |
|--------|----------|
| `Decision: <text>` | Decision entity (status=active) |
| `Fix: <text>` | Problem (resolved) + Decision |
| `Experiment: <text>` | Experiment entity |
| `Refs: <path>` | References edge to Artifact |

## Project Structure

```
dev-brain/
├── config/
│   ├── settings.py             # Pydantic BaseSettings + safety guards
│   └── graphiti_init.py        # Graphiti client factory (Vertex AI + API key)
├── entities/
│   ├── dev_session.py          # DevSession schema
│   ├── decision.py             # Decision schema
│   ├── artifact.py             # Artifact schema
│   ├── problem.py              # Problem schema
│   ├── experiment.py           # Experiment schema
│   ├── concept.py              # Concept schema
│   └── relationship_hints.py   # 9 edge types
├── ingestion/
│   ├── session_ingestor.py     # Markdown session files → episodes
│   ├── commit_ingestor.py      # Git commits → episodes
│   ├── spec_ingestor.py        # Specs/ADRs → episodes
│   ├── bulk_backfill.py        # Orchestrates all ingestors
│   └── idempotency.py          # SHA-256 content-hash dedup
├── brain_mcp/
│   └── run_server.py           # MCP server with 8 tools
├── queries/
│   ├── smoke_tests.py          # 10 acceptance criteria queries
│   └── spot_check.py           # Extraction quality audit
├── hooks/
│   ├── install_hooks.py        # Git hook installer
│   └── post-commit             # Auto-ingest hook script
├── tests/                      # Pytest suite
├── docs/
│   ├── INGESTION_GUIDE.md      # How to extend entity/edge types
│   ├── QUERY_COOKBOOK.md        # Example queries (MCP + Cypher)
│   └── sessions/TEMPLATE.md    # Session summary template
├── docker-compose.yml          # Local Neo4j
├── pyproject.toml              # uv package config
└── .env.example                # Environment variable template
```

## Safety

- **Database isolation**: Configurable `BLOCKED_DB_NAMES` prevents writing to production databases
- **Group ID isolation**: `GRAPHITI_GROUP_ID` scopes all Brain nodes (safe to share a Neo4j instance)
- **Read-only mode**: `GRAPHITI_READ_ONLY=true` disables all ingestion
- **Idempotency**: Content-hash deduplication prevents duplicate episodes
- **Credential scrubbing**: Passwords and API keys redacted from log output
- **Budget protection**: Pre-flight checklist includes Gemini API budget alert setup

## Configuration

All settings via environment variables (`.env` file):

| Variable | Required | Description |
|----------|----------|-------------|
| `NEO4J_URI` | Yes | Neo4j connection URI |
| `NEO4J_USER` | Yes | Neo4j username |
| `NEO4J_PASSWORD` | Yes | Neo4j password |
| `GOOGLE_CLOUD_PROJECT` | * | GCP project for Vertex AI |
| `GEMINI_API_KEY` | * | Gemini API key (fallback) |
| `PRIMARY_REPO_PATH` | Yes | Path to your main project repo |
| `SECONDARY_REPO_PATH` | No | Path to a second repo |
| `GRAPHITI_GROUP_ID` | No | Node isolation key (default: `dev_brain`) |
| `GRAPHITI_READ_ONLY` | No | Disable ingestion (default: `false`) |
| `BLOCKED_DB_NAMES` | No | Comma-separated production DB names |

\* One of `GOOGLE_CLOUD_PROJECT` or `GEMINI_API_KEY` is required.

## License

MIT — see [LICENSE](LICENSE).
