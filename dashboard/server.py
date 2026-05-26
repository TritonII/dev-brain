"""
Dev Brain Web Server
===================

FastAPI backend that exposes REST API endpoints for the interactive web dashboard.
Communicates directly with Neo4j and the Graphiti client.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure dev-brain/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.graphiti_init import get_graphiti, close_graphiti
from config.settings import get_settings
from entities import ENTITY_TYPES, EDGE_TYPES
from graphiti_core.nodes import EpisodeType

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    # Warm up settings and Graphiti client
    try:
        settings = get_settings()
        logger.info("Initializing Graphiti client for dashboard...")
        await get_graphiti()
        logger.info("Graphiti client successfully initialized")
    except Exception as e:
        logger.error("Failed to initialize Graphiti client on startup: %s", e)
    
    yield
    
    logger.info("Closing Graphiti client...")
    await close_graphiti()
    logger.info("Graphiti client closed")

app = FastAPI(
    title="Dev Brain Dashboard",
    description="Web Dashboard and Graph Visualizer for the Dev Brain Knowledge Graph",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas ---

class SessionNoteInput(BaseModel):
    title: str
    content: str


# --- Helper functions for direct Neo4j querying ---

async def execute_cypher(query: str, params: dict = None) -> list:
    """Helper to execute custom Cypher queries directly via Neo4jDriver."""
    graphiti = await get_graphiti()
    driver = graphiti.graph_driver
    
    # execute_query is an eager execution helper on Neo4jDriver
    result = await driver.execute_query(query, **(params or {}))
    return result.records


# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    """Verify backend and database connectivity."""
    try:
        graphiti = await get_graphiti()
        # Verify driver connectivity
        await graphiti.graph_driver.health_check()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/graph")
async def get_graph():
    """Retrieve all Entity nodes and relationships for visualizer rendering."""
    settings = get_settings()
    group_id = settings.GRAPHITI_GROUP_ID

    # Cypher query to fetch all entity nodes and edges within the group
    cypher = """
    MATCH (n:Entity)
    WHERE n.group_id = $group_id OR $group_id IN n.group_ids
    OPTIONAL MATCH (n)-[r]->(m:Entity)
    WHERE m.group_id = $group_id OR $group_id IN m.group_ids
    RETURN n, r, m
    """
    
    try:
        records = await execute_cypher(cypher, {"group_id": group_id})
        
        nodes_dict = {}
        edges_list = []
        
        for record in records:
            n_node = record.get("n")
            m_node = record.get("m")
            r_rel = record.get("r")
            
            # Helper to parse node details
            for node in (n_node, m_node):
                if node is None:
                    continue
                
                uuid = node.get("uuid")
                if uuid in nodes_dict:
                    continue
                
                # Determine entity type by checking Neo4j labels or the labels property
                node_labels = list(node.labels)
                entity_type = "Entity"
                for label in node_labels:
                    if label != "Entity":
                        entity_type = label
                        break
                
                # If Neo4j labels doesn't contain a specific type, check properties
                if entity_type == "Entity" and node.get("labels"):
                    props_labels = node.get("labels")
                    if isinstance(props_labels, list) and props_labels:
                        entity_type = props_labels[0]
                
                # Extract properties
                name = node.get("name", "Unnamed")
                summary = node.get("summary", "")
                created_at = node.get("created_at")
                
                # Try to parse attributes
                attributes = {}
                attrs_raw = node.get("attributes")
                if attrs_raw:
                    import json
                    if isinstance(attrs_raw, str):
                        try:
                            attributes = json.loads(attrs_raw)
                        except Exception:
                            pass
                    elif isinstance(attrs_raw, dict):
                        attributes = attrs_raw
                
                nodes_dict[uuid] = {
                    "id": uuid,
                    "name": name,
                    "type": entity_type,
                    "summary": summary,
                    "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                    "attributes": attributes
                }
                
            # Helper to parse edge details
            if r_rel is not None and n_node is not None and m_node is not None:
                source_uuid = n_node.get("uuid")
                target_uuid = m_node.get("uuid")
                
                rel_type = r_rel.type
                fact = r_rel.get("fact", "")
                valid_at = r_rel.get("valid_at")
                
                # Build unique edge ID
                edge_id = f"{source_uuid}-{rel_type}-{target_uuid}"
                
                edges_list.append({
                    "id": edge_id,
                    "source": source_uuid,
                    "target": target_uuid,
                    "type": rel_type,
                    "fact": fact,
                    "valid_at": valid_at.isoformat() if hasattr(valid_at, "isoformat") else str(valid_at)
                })
                
        return {
            "nodes": list(nodes_dict.values()),
            "edges": edges_list
        }
        
    except Exception as e:
        logger.error("Error retrieving graph data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_brain(query: str = Query(..., min_length=1), limit: int = 15):
    """Perform a hybrid semantic search across entities and relationships."""
    from graphiti_core.search.search_config import SearchConfig
    from graphiti_core.search.search_config_recipes import (
        NODE_HYBRID_SEARCH_RRF,
        EDGE_HYBRID_SEARCH_RRF,
    )
    
    settings = get_settings()
    try:
        graphiti = await get_graphiti()
        
        config = SearchConfig(
            node_config=NODE_HYBRID_SEARCH_RRF.node_config,
            edge_config=EDGE_HYBRID_SEARCH_RRF.edge_config,
            limit=limit,
        )
        
        results = await graphiti.search_(
            query=query,
            config=config,
            group_ids=[settings.GRAPHITI_GROUP_ID],
        )
        
        # Serialize node results
        nodes = []
        for i, node in enumerate(results.nodes):
            score = results.node_reranker_scores[i] if i < len(results.node_reranker_scores) else None
            
            # Determine type
            node_labels = list(node.labels) if hasattr(node, "labels") else []
            entity_type = "Entity"
            for label in node_labels:
                if label != "Entity":
                    entity_type = label
                    break
            if entity_type == "Entity" and hasattr(node, "labels") and getattr(node, "labels"):
                props_labels = getattr(node, "labels")
                if isinstance(props_labels, list) and props_labels:
                    entity_type = props_labels[0]

            nodes.append({
                "id": getattr(node, "uuid", None),
                "name": getattr(node, "name", "Unnamed"),
                "type": entity_type,
                "summary": getattr(node, "summary", ""),
                "score": score,
                "created_at": str(getattr(node, "created_at", "")),
                "attributes": getattr(node, "attributes", {}) or {}
            })
            
        # Serialize edge results
        edges = []
        for i, edge in enumerate(results.edges):
            score = results.edge_reranker_scores[i] if i < len(results.edge_reranker_scores) else None
            edges.append({
                "type": getattr(edge, "name", "REFERENCES"),
                "fact": getattr(edge, "fact", ""),
                "score": score,
                "valid_at": str(getattr(edge, "valid_at", ""))
            })
            
        return {"nodes": nodes, "edges": edges}
        
    except Exception as e:
        logger.error("Error searching brain: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/decisions")
async def get_decisions(status: str = "active"):
    """Retrieve decisions filtered by status."""
    settings = get_settings()
    group_id = settings.GRAPHITI_GROUP_ID
    
    cypher = """
    MATCH (n:Entity)
    WHERE (n.group_id = $group_id OR $group_id IN n.group_ids)
      AND ('Decision' IN labels(n) OR 'Decision' IN n.labels)
    RETURN n
    """
    
    try:
        records = await execute_cypher(cypher, {"group_id": group_id})
        decisions = []
        
        for record in records:
            node = record.get("n")
            if node is None:
                continue
            
            # Parse attributes
            attrs = {}
            attrs_raw = node.get("attributes")
            if attrs_raw:
                import json
                if isinstance(attrs_raw, str):
                    try:
                        attrs = json.loads(attrs_raw)
                    except Exception:
                        pass
                elif isinstance(attrs_raw, dict):
                    attrs = attrs_raw
            
            # Filtering by status (inside attributes or properties)
            node_status = attrs.get("status") or node.get("status") or "active"
            if status and node_status.lower() != status.lower():
                continue
                
            decisions.append({
                "id": node.get("uuid"),
                "name": node.get("name", "Unnamed"),
                "summary": node.get("summary", ""),
                "status": node_status,
                "rationale": attrs.get("rationale") or node.get("rationale") or "",
                "domain": attrs.get("domain") or node.get("domain") or "architecture",
                "created_at": str(node.get("created_at", ""))
            })
            
        return decisions
    except Exception as e:
        logger.error("Error retrieving decisions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/problems")
async def get_problems(status: str = None):
    """Retrieve problems filtered by status (e.g. open, resolved, investigating)."""
    settings = get_settings()
    group_id = settings.GRAPHITI_GROUP_ID
    
    cypher = """
    MATCH (n:Entity)
    WHERE (n.group_id = $group_id OR $group_id IN n.group_ids)
      AND ('Problem' IN labels(n) OR 'Problem' IN n.labels)
    RETURN n
    """
    
    try:
        records = await execute_cypher(cypher, {"group_id": group_id})
        problems = []
        
        for record in records:
            node = record.get("n")
            if node is None:
                continue
            
            # Parse attributes
            attrs = {}
            attrs_raw = node.get("attributes")
            if attrs_raw:
                import json
                if isinstance(attrs_raw, str):
                    try:
                        attrs = json.loads(attrs_raw)
                    except Exception:
                        pass
                elif isinstance(attrs_raw, dict):
                    attrs = attrs_raw
            
            node_status = attrs.get("status") or node.get("status") or "investigating"
            
            # Filter if status is specified
            # For problems, "open" typically maps to anything NOT "resolved"
            if status:
                if status.lower() == "open" and node_status.lower() == "resolved":
                    continue
                elif status.lower() != "open" and node_status.lower() != status.lower():
                    continue
                
            problems.append({
                "id": node.get("uuid"),
                "name": node.get("name", "Unnamed"),
                "summary": node.get("summary", ""),
                "status": node_status,
                "severity": attrs.get("severity") or node.get("severity") or "medium",
                "first_observed": str(attrs.get("first_observed") or node.get("first_observed") or ""),
                "created_at": str(node.get("created_at", ""))
            })
            
        return problems
    except Exception as e:
        logger.error("Error retrieving problems: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest")
async def ingest_session_note(payload: SessionNoteInput):
    """Ingest a session note directly into the Dev Brain."""
    settings = get_settings()
    if settings.GRAPHITI_READ_ONLY:
        raise HTTPException(status_code=400, detail="Database is configured in read-only mode")
        
    try:
        graphiti = await get_graphiti()
        
        result = await graphiti.add_episode(
            name=f"session_note_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            episode_body=f"# {payload.title}\n\n{payload.content}",
            source=EpisodeType.text,
            source_description="dashboard_ui",
            reference_time=datetime.now(timezone.utc),
            group_id=settings.GRAPHITI_GROUP_ID,
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
        )
        
        entities = [n.name for n in result.nodes] if result.nodes else []
        edges_count = len(result.edges) if result.edges else 0
        
        return {
            "status": "success",
            "title": payload.title,
            "entities_extracted": len(entities),
            "entity_names": entities,
            "relationships_created": edges_count
        }
        
    except Exception as e:
        logger.error("Error ingesting session note from dashboard: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Static Files Mounting ---

# Mount frontend files (HTML/CSS/JS) served from dashboard/static/
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
else:
    logger.warning("Static directory not found at %s. Please create it to serve the UI.", static_path)


def main():
    """Main entrypoint for running the server."""
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Starting Dev Brain Dashboard Server...")
    uvicorn.run("dashboard.server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
