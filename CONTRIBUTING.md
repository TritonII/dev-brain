# Contributing to Dev Brain

Welcome! Thank you for helping build the future of AI-assisted developer memory. 

Dev Brain is built on a modular, Pydantic-powered graph extraction layer. This guide details how to set up your environment, run tests, and extend the core schema (adding entity types, relationship types, or ingestors).

---

## Technical Stack

- **Python**: 3.11+
- **Graph Database**: Neo4j (local or Aura) or FalkorDB
- **LLM Engine**: Gemini 2.5 Flash
- **Knowledge Graph Client**: [Graphiti](https://github.com/getzep/graphiti) (v0.28+)
- **Package Manager**: `uv` (fast Rust-based package manager)

---

## Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/TritonII/dev-brain.git
   cd dev-brain
   ```

2. **Sync dependencies** (creates `.venv` and installs packages):
   ```bash
   uv sync
   ```

3. **Configure Environment Variables**:
   Copy the example and fill in your Gemini API key and Neo4j credentials:
   ```bash
   cp .env.example .env
   ```

4. **Verify Tests**:
   Run the pytest suite to ensure your local installation is fully correct:
   ```bash
   uv run pytest tests/ -v
   ```

---

## Extending the Graph Schema

One of the most common contributions is expanding Dev Brain to capture new project contexts (e.g., adding `Milestone` or `PRReview` entities).

### 1. Adding a New Entity Type

Dev Brain entities are standard Pydantic models.

1. Create a new schema file in `entities/` (e.g. `entities/milestone.py`):
   ```python
   from datetime import datetime
   from pydantic import BaseModel, Field

   class Milestone(BaseModel):
       """A major project milestone or release deadline."""
       title: str = Field(description="Title of the milestone")
       target_date: datetime = Field(description="Estimated delivery date")
       completed: bool = Field(default=False, description="Whether the milestone has been hit")
   ```
2. **Crucial Rule**: Graphiti has reserved fields. **Never** define these attributes in your Pydantic schemas:
   `uuid`, `name`, `group_id`, `labels`, `created_at`, `summary`, `attributes`, `name_embedding`.
3. Register your new entity in [entities/__init__.py](file:///C:/Users/Sturg/.gemini/antigravity/scratch/dev-brain/entities/__init__.py):
   ```python
   from .milestone import Milestone

   ENTITY_TYPES = {
       ...
       "Milestone": Milestone,
   }
   ```

### 2. Adding a New Relationship Edge Type

Relationships are registered as semantic prompts in [entities/relationship_hints.py](file:///C:/Users/Sturg/.gemini/antigravity/scratch/dev-brain/entities/relationship_hints.py).

To add a new edge, register its name and a short descriptive hint in `EDGE_TYPES`:
```python
EDGE_TYPES = {
    ...
    "ACHIEVED_IN": "Milestone was reached during a DevSession",
}
```

---

## Creating Custom Ingestors

If you want to feed data from a new source (e.g. Slack summaries, Jira tickets, Linear issues), you can build a new Ingestor.

1. Reference [ingestion/session_ingestor.py](file:///C:/Users/Sturg/.gemini/antigravity/scratch/dev-brain/ingestion/session_ingestor.py) or [ingestion/github_ingestor.py](file:///C:/Users/Sturg/.gemini/antigravity/scratch/dev-brain/ingestion/github_ingestor.py) as templates.
2. Ensure you check for already-ingested content using the idempotency layer:
   ```python
   from ingestion.idempotency import is_already_ingested, mark_ingested

   if is_already_ingested(content):
       return {"skipped": "already_ingested"}
   ```
3. Load the registered `ENTITY_TYPES` and `EDGE_TYPES`, and call `graphiti.add_episode()` inside an async lifecycle.

---

## Running the Web Dashboard Visualizer

We provide a beautiful FastAPI-served web dashboard to visualize your temporal memory graph.

1. Start your local server:
   ```bash
   uv run python -m dashboard.server
   ```
2. Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)
3. You can click on nodes, run semantic search queries, and play with the **Temporal Time Slider** to watch the graph grow!

## Continuous Integration (CI)

Every pull request will automatically trigger the GitHub Actions workflow defined in `.github/workflows/ci.yml`. This workflow runs your pytest suite across Python 3.11, 3.12, and 3.13. Ensure your tests pass before requesting a review.
