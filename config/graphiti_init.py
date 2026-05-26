"""
Graphiti Client Initialization
==============================

Initializes the Graphiti knowledge graph client with:
- Strategy 1: Gemini via Vertex AI (GCP credits)
- Strategy 2: Gemini via API key (fallback)

Uses Neo4jDriver with explicit database parameter for isolation.

Note: Graphiti's default cross-encoder requires OpenAI. We provide a
pass-through implementation since we use Gemini exclusively.
"""

import json
import logging
from typing import Optional

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig

from .settings import get_settings

logger = logging.getLogger(__name__)

# --- Monkeypatch: temporal types → ISO string in json.dumps ---
# Graphiti's `to_prompt_json()` calls `json.dumps()` on data that may contain
# `neo4j.time.DateTime` or Python `datetime` objects. Neither is natively serializable.
import datetime as _dt

_original_json_default = json.JSONEncoder().default


def _patched_json_default(self, obj):
    # Python datetime types
    if isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
        return obj.isoformat()
    # Neo4j temporal types
    try:
        from neo4j.time import DateTime as Neo4jDateTime, Date as Neo4jDate, Time as Neo4jTime
        if isinstance(obj, (Neo4jDateTime, Neo4jDate, Neo4jTime)):
            return obj.iso_format()
    except ImportError:
        pass
    return _original_json_default(obj)


json.JSONEncoder.default = _patched_json_default

_client: Optional[Graphiti] = None


class _PassThroughCrossEncoder(CrossEncoderClient):
    """Cross-encoder that returns passages in original order with linear scores.

    Graphiti defaults to OpenAI's reranker which requires an API key.
    Since we use Gemini exclusively, this pass-through avoids the OpenAI dependency.
    Semantic retrieval quality comes from Gemini embeddings — reranking is optional.
    """

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        # Return all passages with linearly decreasing scores (preserves original order)
        if not passages:
            return []
        n = len(passages)
        return [(p, 1.0 - i / max(n, 1)) for i, p in enumerate(passages)]


def _build_gemini_clients() -> tuple[GeminiClient, GeminiEmbedder]:
    """Build Gemini LLM client and embedder with Vertex AI fallback."""
    settings = get_settings()

    # Strategy 1: Vertex AI (uses GCP credits, no API key needed)
    if settings.GOOGLE_CLOUD_PROJECT:
        try:
            import google.genai as genai

            vertex_client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION,
            )

            llm_client = GeminiClient(
                config=LLMConfig(model=settings.GEMINI_MODEL),
                client=vertex_client,
            )
            embedder = GeminiEmbedder(
                config=GeminiEmbedderConfig(embedding_model="text-embedding-005", embedding_dim=768),
                client=vertex_client,
            )
            logger.info(
                "Gemini initialized via Vertex AI (project=%s, model=%s)",
                settings.GOOGLE_CLOUD_PROJECT,
                settings.GEMINI_MODEL,
            )
            return llm_client, embedder

        except Exception as e:
            logger.warning("Vertex AI initialization failed (%s), falling back to API key", e)

    # Strategy 2: Gemini API key
    if settings.GEMINI_API_KEY:
        llm_client = GeminiClient(
            config=LLMConfig(
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
            )
        )
        embedder = GeminiEmbedder(
            config=GeminiEmbedderConfig(
                api_key=settings.GEMINI_API_KEY,
                embedding_model="text-embedding-005", embedding_dim=768,
            )
        )
        logger.info("Gemini initialized via API key (model=%s)", settings.GEMINI_MODEL)
        return llm_client, embedder

    raise RuntimeError(
        "No Gemini credentials configured. Set GOOGLE_CLOUD_PROJECT (for Vertex AI) "
        "or GEMINI_API_KEY in your .env file."
    )


async def get_graphiti() -> Graphiti:
    """Get or create the Graphiti singleton client."""
    global _client

    if _client is not None:
        return _client

    settings = get_settings()
    llm_client, embedder = _build_gemini_clients()

    # Use Neo4jDriver with explicit database for isolation
    graph_driver = Neo4jDriver(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        database=settings.NEO4J_DATABASE,
    )

    _client = Graphiti(
        llm_client=llm_client,
        embedder=embedder,
        graph_driver=graph_driver,
        cross_encoder=_PassThroughCrossEncoder(),
    )

    # Build indices and constraints on first init
    await _client.build_indices_and_constraints()
    logger.info(
        "Graphiti client ready (database=%s, group_id=%s)",
        settings.NEO4J_DATABASE,
        settings.GRAPHITI_GROUP_ID,
    )
    return _client


async def close_graphiti() -> None:
    """Close the Graphiti client and release resources."""
    global _client
    if _client is not None:
        try:
            await _client.close()
            logger.info("Graphiti client closed")
        except Exception as e:
            logger.error("Error closing Graphiti: %s", e)
        finally:
            _client = None
