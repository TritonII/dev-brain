# Graphiti Extensions & Advanced Database Configurations

This guide covers advanced configurations leveraging the latest capabilities in the **Graphiti v0.28+** core framework to enhance your Dev Brain experience.

---

## 1. Thematic Clustering via Leiden Community Detection

As your Dev Brain grows, the graph will contain hundreds of individual Decisions, Problems, and Commits. To make sense of this data at scale, we support **Leiden Community Detection**.

### How It Works
1. **Clustering**: The Leiden algorithm analyzes the topology of your knowledge graph and groups strongly connected nodes into modular "communities" (e.g. all nodes related to "Auth", "Caching", or "Database").
2. **LLM Summarization**: Graphiti recursively performs pairwise merges of the summaries of all member entities in a community to synthesize a single high-level, human-readable macro-summary for that module.

### How to Run Community Building
We have created a dedicated CLI utility to run Leiden community detection:
```bash
uv run python -m queries.build_communities
```

*Note*: Because this runs summarizations over your entire graph, it is recommended to run this periodically (e.g. weekly or after large backfills) rather than on every single commit.

---

## 2. FalkorDB: Ultra-Lightweight Local Graph Alternative

While Neo4j is a powerful, production-grade database, it can be heavy to run locally on resource-constrained development machines. We support **FalkorDB** as a fast, low-footprint alternative.

FalkorDB is a low-latency graph database that runs directly inside Redis. It is incredibly quick to spin up and uses a fraction of the CPU/memory of Neo4j.

### Setting Up FalkorDB

1. **Spin up FalkorDB via Docker**:
   ```bash
   docker run -p 6379:6379 falkordb/falkordb:latest
   ```

2. **Configure your `.env`**:
   Adjust your connection parameters in `.env` to point to your FalkorDB instance:
   ```bash
   # Point to FalkorDB Redis protocol port
   NEO4J_URI=redis://localhost:6379
   NEO4J_USER=
   NEO4J_PASSWORD=
   NEO4J_DATABASE=falkor
   ```

3. **Re-run Ingestions**:
   Graphiti's driver automatically handles FalkorDB compatibility under the hood! You can run your backfills and visualizer dashboard exactly as before:
   ```bash
   # Run backfill
   uv run python -m ingestion.bulk_backfill --all
   
   # Start Web visualizer
   uv run python -m dashboard.server
   ```
