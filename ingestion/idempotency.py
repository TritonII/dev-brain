"""
Idempotency Layer
=================

Content-hash based deduplication to prevent duplicate episode ingestion.
Every ingestor checks the hash store before calling add_episode().

Hash store: ingestion/state/ingested_hashes.json
Format: { "<sha256_hex>": "<iso_timestamp>" }
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_DIR = Path(__file__).parent / "state"
_HASH_FILE = _STATE_DIR / "ingested_hashes.json"


def _load_hashes() -> dict[str, str]:
    """Load the hash store from disk."""
    if not _HASH_FILE.exists():
        return {}
    try:
        return json.loads(_HASH_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load hash store: %s", e)
        return {}


def _save_hashes(hashes: dict[str, str]) -> None:
    """Persist the hash store to disk."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _HASH_FILE.write_text(
        json.dumps(hashes, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def content_hash(content: str) -> str:
    """Compute SHA-256 hex digest of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def is_already_ingested(episode_body: str) -> bool:
    """Check if this content has already been ingested."""
    h = content_hash(episode_body)
    hashes = _load_hashes()
    return h in hashes


def mark_ingested(episode_body: str) -> None:
    """Record that this content has been ingested."""
    h = content_hash(episode_body)
    hashes = _load_hashes()
    hashes[h] = datetime.now(timezone.utc).isoformat()
    _save_hashes(hashes)


def get_ingested_count() -> int:
    """Return the number of previously ingested episodes."""
    return len(_load_hashes())


def clear_hashes() -> None:
    """Clear all ingestion records. Use with caution."""
    _save_hashes({})
    logger.info("Cleared all ingestion hashes")
