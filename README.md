# Dev Brain

Persistent memory for LLM-assisted development. A [Graphiti](https://github.com/getzep/graphiti)-powered temporal knowledge graph that captures your project's decisions, experiments, problems, and concepts across working sessions — so context is never lost.

Now supercharged with a **High-Fidelity Web Dashboard**, **GitHub Issues/PR Ingestion**, and **Thematic Community Clustering**.

---

## Why?

If you use Claude Code, Cursor, or any LLM assistant for development, you've hit this:

- **"Didn't we already try that?"** — An experiment from 3 weeks ago that failed, but nobody remembers why.
- **"What did we decide about X?"** — An architectural decision buried in a chat log that's long gone.
- **"What's blocking Y?"** — A problem identified last month that's still open but lost in noise.

Dev Brain solves this by ingesting your development history (session notes, git commits, specs, GitHub issues/PRs) into a queryable knowledge graph with temporal awareness. Start a new session, ask the Brain what happened, or load the visual visualizer to see how your project's mental model has evolved.

---

## How It Works

```
Session Notes ──┐
Git Commits ────┼──► Graphiti ──► Neo4j / FalkorDB ──┬──► MCP Server ──► Claude Code
Specs & ADRs ───┤                   (Knowledge Graph)└──► Web Visualizer Dashboard
GitHub Issues ──┘
```

1. **Ingest** your development history (sessions, commits, specs/ADRs, GitHub Issues/PRs).
2. Graphiti uses Gemini to **extract entities** (Decision, Problem, Experiment, Concept, etc.) and **relationships** (SUPERSEDES, VALIDATES, CONTRADICTS, BLOCKS).
3. Everything lands in **Neo4j** or **FalkorDB** as a temporal knowledge graph.
4. Query via **MCP tools** from Claude Code, inspect via the **Web Visualizer**, or query directly via Cypher.

---

## New Supercharged Features

### 1. High-Fidelity Web Visualizer & Dashboard
A premium dark-mode, glassmorphic dashboard served locally via **FastAPI** and rendered interactively with **Cytoscape.js**.
*   **Temporal Time-Travel Slider**: Slide to filter nodes dynamically by date and watch your graph grow chronological sequence.
*   **Interactive Node & Edge Inspector**: Click nodes to load Pydantic attributes (e.g. severity, status, domain) and immediately browse all inbound/outbound relationships.
*   **Direct Ingestion Panel**: Paste session notes directly from your browser and see the network update in real-time.
*   **Global Semantic Search**: Semantically highlights matches in the graph and zooms to relevant clusters.

### 2. GitHub Issues & Pull Requests Ingestor
Ingest full collaborative context (including issue states, bug details, pull requests, merge status, and link references) using the GitHub REST API.

### 3. Thematic Clustering (Leiden Community Detection)
Group strongly connected nodes in your graph into thematic communities (e.g., Caching, Security, UI) and synthesize macro-summaries of each module using Leiden clustering.

---

## Quick Start

### 1. Clone & Set Up
```bash
# Clone
git clone https://github.com/TritonII/dev-brain.git
cd dev-brain

# Install dependencies (creates .venv using super-fast uv manager)
uv sync
```

### 2. Configure Environment
```bash
# Configure environment
cp .env.example .env
# Edit .env with your Neo4j credentials, Gemini API key, and optional GITHUB_TOKEN
```

### 3. Start Local Databases (Choose One)
*   **Option A: Neo4j (Default)**:
    ```bash
    docker-compose up -d
    ```
*   **Option B: FalkorDB (Lightweight Graph Alternative)**:
    ```bash
    docker run -p 6379:6379 falkordb/falkordb:latest
    # Set NEO4J_URI=redis://localhost:6379 in your .env
    ```

### 4. Seed and Ingest Example Data
We have provided fictional developer session files inside `docs/sessions/` for end-to-end testing:
```bash
# Ingest sample sessions
uv run python -m ingestion.session_ingestor --dir docs/sessions/
```

### 5. Launch the Web Visualizer Dashboard
```bash
# Start FastAPI Web server
uv run python -m dashboard.server
# Open browser and navigate to: http://127.0.0.1:8000
```

---

## CLI Ingestion Commands

```bash
# Ingest local session files
uv run python -m ingestion.session_ingestor --file docs/sessions/SESSION_SUMMARY_2026-05-10_caching.md

# Backfill GitHub Issues and PRs
uv run python -m ingestion.github_ingestor --repo TritonII/dev-brain --limit 10

# Ingest local commits
uv run python -m ingestion.commit_ingestor --repo primary --max 50

# Run Leiden Community Clustering
uv run python -m queries.build_communities

# Run local pytest suite
uv run pytest tests/ -v
```

---

## Architecture Schema & Entity Types

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

---

## Detailed Documentation Guides

- 📘 **[Visualizer Web Dashboard Guide](docs/VISUALIZER_GUIDE.md)**
- 🐙 **[GitHub Issues/PR Ingestion Guide](docs/GITHUB_INGESTION_GUIDE.md)**
- 🚀 **[Graphiti Leiden Clustering & FalkorDB Guide](docs/GRAPHITI_EXTENSIONS.md)**
- 🔧 **[Core Ingestion Customization Guide](docs/INGESTION_GUIDE.md)**
- 🍳 **[Graphiti Query Cookbook](docs/QUERY_COOKBOOK.md)**
- 🤝 **[Developer Contribution Guidelines](CONTRIBUTING.md)**

---

## Safety & Security

- **Database isolation**: Configurable `BLOCKED_DB_NAMES` prevents writing to production databases.
- **Group ID isolation**: `GRAPHITI_GROUP_ID` scopes all Brain nodes (safe to share a Neo4j instance).
- **Read-only mode**: `GRAPHITI_READ_ONLY=true` disables all ingestion.
- **Idempotency**: Content-hash deduplication prevents duplicate episodes.
- **Credential scrubbing**: Passwords and API keys redacted from log output.

---

## License

MIT — see [LICENSE](LICENSE).
