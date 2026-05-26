# Ingestion Guide

How to add new data sources and entity types to Dev Brain.

## Adding a New Entity Type

1. Create a Pydantic model in `entities/<name>.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class MyNewEntity(BaseModel):
    """Description of what this entity represents."""
    my_field: str = Field(description="What this field means")
    optional_field: Optional[str] = Field(default=None, description="...")
```

**Reserved field names** (used by Graphiti internally — do NOT use):
`uuid`, `name`, `group_id`, `labels`, `created_at`, `summary`, `attributes`, `name_embedding`

2. Register it in `entities/__init__.py`:

```python
from .my_new_entity import MyNewEntity

ENTITY_TYPES["MyNewEntity"] = MyNewEntity
```

3. Re-run bulk backfill to extract the new entity type from existing content:

```bash
uv run python -m ingestion.bulk_backfill --sessions --specs
```

Graphiti will re-extract entities using the updated type definitions. Idempotency prevents duplicate ingestion of unchanged content.

## Adding a New Edge Type

1. Add a Pydantic model in `entities/relationship_hints.py`:

```python
class MyEdge(BaseModel):
    """What this relationship means."""
    detail: Optional[str] = Field(default=None, description="...")
```

2. Register in the `EDGE_TYPES` dict in the same file.

## Adding a New Ingestor

1. Create `ingestion/<source>_ingestor.py`
2. Follow the pattern from `session_ingestor.py`:
   - Check `GRAPHITI_READ_ONLY` before ingesting
   - Check `is_already_ingested()` for idempotency
   - Call `graphiti.add_episode()` with entity_types and edge_types
   - Call `mark_ingested()` after success
   - Add CLI with `argparse`

## Commit Message Conventions

Use these prefixes in commit messages for richer extraction:

| Prefix | Triggers |
|--------|----------|
| `Decision: <text>` | Decision entity with status=active |
| `Fix: <text>` | Problem (resolved) + Decision entities |
| `Experiment: <text>` | Experiment entity |
| `Refs: <path>` | References edge to Artifact |

Commits without prefixes are still ingested as Artifact nodes.
