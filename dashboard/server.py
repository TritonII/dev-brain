"""
Dev Brain Web Server
===================

FastAPI backend that exposes REST API endpoints for the interactive web dashboard.
Communicates directly with Neo4j and the Graphiti client.

FALLBACK DEMO MODE:
If Neo4j or Gemini credentials are not configured, the server automatically
enters "Demo Mode" to serve a rich, pre-populated mock dataset. This allows
developers to experience the visualizer and timeline slider out-of-the-box!
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

# Global flag to track Demo Mode fallback
IS_DEMO_MODE = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    global IS_DEMO_MODE
    try:
        settings = get_settings()
        logger.info("Initializing Graphiti client for dashboard...")
        await get_graphiti()
        logger.info("Graphiti client successfully initialized")
    except Exception as e:
        logger.error("Failed to initialize Graphiti client on startup: %s", e)
        logger.info("Neo4j database or Gemini offline. Enabling seamless DEMO MODE fallback.")
        IS_DEMO_MODE = True
    
    yield
    
    if not IS_DEMO_MODE:
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


# --- Direct Neo4j querying helper ---

async def execute_cypher(query: str, params: dict = None) -> list:
    """Helper to execute custom Cypher queries directly via Neo4jDriver."""
    if IS_DEMO_MODE:
        return []
    graphiti = await get_graphiti()
    driver = graphiti.graph_driver
    result = await driver.execute_query(query, **(params or {}))
    return result.records


# --- HIGH-FIDELITY SEED DATA FOR DEMO MODE ---

MOCK_NODES = [
    {
        "id": "node_session_1",
        "name": "Sprint 1: Caching Tier",
        "type": "DevSession",
        "summary": "Focused on implementing a robust, distributed caching strategy to address response delays.",
        "created_at": "2026-05-10T10:00:00Z",
        "attributes": {
            "focus_area": "backend API",
            "outcome_status": "productive",
            "participants": ["Developer", "Claude-Opus-4"]
        }
    },
    {
        "id": "node_decision_redis",
        "name": "Use Redis for Cache",
        "type": "Decision",
        "summary": "We chose Redis over Memcached for caching to support rich data types and LRU policies.",
        "created_at": "2026-05-10T10:30:00Z",
        "attributes": {
            "status": "active",
            "domain": "data_model",
            "rationale": "Redis offers sub-millisecond key-value retrieval and natively supports eviction policies (LRU)."
        }
    },
    {
        "id": "node_problem_lag",
        "name": "High API Response Lag",
        "type": "Problem",
        "summary": "Concurrent load is causing response latency to spike past 800ms during peak hours.",
        "created_at": "2026-05-09T18:00:00Z",
        "attributes": {
            "status": "resolved",
            "severity": "high",
            "first_observed": "2026-05-09T18:00:00Z",
            "resolved_at": "2026-05-20T12:00:00Z"
        }
    },
    {
        "id": "node_exp_redis",
        "name": "Redis vs In-Memory dict",
        "type": "Experiment",
        "summary": "Tested Redis local memory footprint vs unbounded in-memory Python dictionary cache.",
        "created_at": "2026-05-10T14:00:00Z",
        "attributes": {
            "hypothesis": "Redis will lower CPU and memory footprints of the main API server process compared to local dictionaries.",
            "approach": "Set up a local Redis instance and measured memory usage during a load test of 10k requests.",
            "outcome": "Process memory stayed flat at 110MB with Redis, whereas dict cache expanded process memory to 450MB.",
            "success": True
        }
    },
    {
        "id": "node_session_2",
        "name": "Sprint 2: Auth Strategy",
        "type": "DevSession",
        "summary": "Explored and compared scalable authentication frameworks for third-party developer integrations.",
        "created_at": "2026-05-15T09:00:00Z",
        "attributes": {
            "focus_area": "security",
            "outcome_status": "exploratory",
            "participants": ["Developer", "Gemini-2.5-Pro"]
        }
    },
    {
        "id": "node_decision_jwt",
        "name": "Stateless JWT Tokens",
        "type": "Decision",
        "summary": "Adopted stateless JWT tokens signed locally on gateways to avoid multi-region DB session checks.",
        "created_at": "2026-05-15T09:30:00Z",
        "attributes": {
            "status": "active",
            "domain": "architecture",
            "rationale": "Stateless signatures prevent centralized session database hits, avoiding regional latency bottlenecks."
        }
    },
    {
        "id": "node_exp_jwt",
        "name": "Stateless JWT Latency",
        "type": "Experiment",
        "summary": "Measured stateless JWT local gateway check speed against central DB session calls.",
        "created_at": "2026-05-15T13:00:00Z",
        "attributes": {
            "hypothesis": "Verifying stateless JWTs locally will reduce latency by at least 150ms compared to a central table query.",
            "approach": "Simulated 1,000 requests using local PyJWT verification versus multi-region queries.",
            "outcome": "Local JWT verification took 1.2ms on average, whereas multi-region database session lookups averaged 185ms.",
            "success": True
        }
    },
    {
        "id": "node_session_3",
        "name": "Sprint 3: Thread Panic",
        "type": "DevSession",
        "summary": "Investigated and resolved a sporadic thread deadlock freeze in local pools.",
        "created_at": "2026-05-20T11:00:00Z",
        "attributes": {
            "focus_area": "backend API",
            "outcome_status": "productive",
            "participants": ["Developer", "Claude-Code"]
        }
    },
    {
        "id": "node_decision_mutex",
        "name": "Thread-Safe Mutex Lock",
        "type": "Decision",
        "summary": "Chose a thread-safe local Mutex lock to isolate concurrency race conditions strictly within local process pools.",
        "created_at": "2026-05-20T11:30:00Z",
        "attributes": {
            "status": "active",
            "domain": "tooling",
            "rationale": "Local Mutex lock prevents thread collisions during shared cache writes without introducing network overhead."
        }
    },
    {
        "id": "node_artifact_spec",
        "name": "CACHING_SPEC.md",
        "type": "Artifact",
        "summary": "Architecture specifications document detailing API caching and Mutex strategies.",
        "created_at": "2026-05-10T16:00:00Z",
        "attributes": {
            "artifact_type": "spec",
            "path": "docs/specs/CACHING_SPEC.md"
        }
    }
]

MOCK_EDGES = [
    {
        "id": "edge_session1_redis",
        "source": "node_session_1",
        "target": "node_decision_redis",
        "type": "EMERGED_FROM",
        "fact": "Redis decision emerged during Caching Sprint.",
        "valid_at": "2026-05-10T10:30:00Z"
    },
    {
        "id": "edge_redis_lag",
        "source": "node_decision_redis",
        "target": "node_problem_lag",
        "type": "VALIDATES",
        "fact": "Redis implementation reduced latency spikes, addressing response lag.",
        "valid_at": "2026-05-10T15:00:00Z"
    },
    {
        "id": "edge_exp_redis",
        "source": "node_exp_redis",
        "target": "node_decision_redis",
        "type": "VALIDATES",
        "fact": "Memory load tests validated the choice of Redis LRU memory flatline efficiency.",
        "valid_at": "2026-05-10T14:30:00Z"
    },
    {
        "id": "edge_session2_jwt",
        "source": "node_session_2",
        "target": "node_decision_jwt",
        "type": "EMERGED_FROM",
        "fact": "JWT token choice emerged from Auth security Sprint.",
        "valid_at": "2026-05-15T09:30:00Z"
    },
    {
        "id": "edge_exp_jwt",
        "source": "node_exp_jwt",
        "target": "node_decision_jwt",
        "type": "VALIDATES",
        "fact": "Stateless verification local checks successfully validated at 1.2ms latency.",
        "valid_at": "2026-05-15T13:30:00Z"
    },
    {
        "id": "edge_session3_mutex",
        "source": "node_session_3",
        "target": "node_decision_mutex",
        "type": "EMERGED_FROM",
        "fact": "Mutex deadlock fix emerged from Thread Panic Sprint.",
        "valid_at": "2026-05-20T11:30:00Z"
    },
    {
        "id": "edge_mutex_lag",
        "source": "node_decision_mutex",
        "target": "node_problem_lag",
        "type": "VALIDATES",
        "fact": "Implementing Mutex locks successfully eliminated deadlocks, resolving load panics.",
        "valid_at": "2026-05-20T12:00:00Z"
    },
    {
        "id": "edge_spec_redis",
        "source": "node_decision_redis",
        "target": "node_artifact_spec",
        "type": "REFERENCES",
        "fact": "Redis cache configurations detailed in architecture spec doc.",
        "valid_at": "2026-05-10T16:00:00Z"
    }
]


# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    """Verify backend and database connectivity."""
    if IS_DEMO_MODE:
        return {"status": "ok", "database": "demo_mode"}
        
    try:
        graphiti = await get_graphiti()
        await graphiti.graph_driver.health_check()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/graph")
async def get_graph():
    """Retrieve all Entity nodes and relationships for visualizer rendering."""
    if IS_DEMO_MODE:
        return {
            "nodes": MOCK_NODES,
            "edges": MOCK_EDGES
        }

    settings = get_settings()
    group_id = settings.GRAPHITI_GROUP_ID

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
            
            for node in (n_node, m_node):
                if node is None:
                    continue
                
                uuid = node.get("uuid")
                if uuid in nodes_dict:
                    continue
                
                node_labels = list(node.labels)
                entity_type = "Entity"
                for label in node_labels:
                    if label != "Entity":
                        entity_type = label
                        break
                
                if entity_type == "Entity" and node.get("labels"):
                    props_labels = node.get("labels")
                    if isinstance(props_labels, list) and props_labels:
                        entity_type = props_labels[0]
                
                name = node.get("name", "Unnamed")
                summary = node.get("summary", "")
                created_at = node.get("created_at")
                
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
                
            if r_rel is not None and n_node is not None and m_node is not None:
                source_uuid = n_node.get("uuid")
                target_uuid = m_node.get("uuid")
                
                rel_type = r_rel.type
                fact = r_rel.get("fact", "")
                valid_at = r_rel.get("valid_at")
                
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
    if IS_DEMO_MODE:
        # Mock semantic search matches
        query_lower = query.lower()
        matched_nodes = []
        for n in MOCK_NODES:
            if query_lower in n["name"].lower() or query_lower in n["summary"].lower():
                matched_nodes.append({**n, "score": 0.9})
        
        matched_edges = []
        for e in MOCK_EDGES:
            if query_lower in e["type"].lower() or query_lower in e["fact"].lower():
                matched_edges.append({**e, "score": 0.85})
                
        return {"nodes": matched_nodes, "edges": matched_edges}

    settings = get_settings()
    try:
        graphiti = await get_graphiti()
        
        from graphiti_core.search.search_config import SearchConfig
        from graphiti_core.search.search_config_recipes import (
            NODE_HYBRID_SEARCH_RRF,
            EDGE_HYBRID_SEARCH_RRF,
        )
        
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
        
        nodes = []
        for i, node in enumerate(results.nodes):
            score = results.node_reranker_scores[i] if i < len(results.node_reranker_scores) else None
            
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
    if IS_DEMO_MODE:
        decisions = []
        for n in MOCK_NODES:
            if n["type"] == "Decision":
                node_status = n["attributes"].get("status", "active")
                if status and node_status.lower() != status.lower():
                    continue
                decisions.append({
                    "id": n["id"],
                    "name": n["name"],
                    "summary": n["summary"],
                    "status": node_status,
                    "rationale": n["attributes"].get("rationale", ""),
                    "domain": n["attributes"].get("domain", "architecture"),
                    "created_at": n["created_at"]
                })
        return decisions

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
    if IS_DEMO_MODE:
        problems = []
        for n in MOCK_NODES:
            if n["type"] == "Problem":
                node_status = n["attributes"].get("status", "investigating")
                if status:
                    if status.lower() == "open" and node_status.lower() == "resolved":
                        continue
                    elif status.lower() != "open" and node_status.lower() != status.lower():
                        continue
                problems.append({
                    "id": n["id"],
                    "name": n["name"],
                    "summary": n["summary"],
                    "status": node_status,
                    "severity": n["attributes"].get("severity", "medium"),
                    "first_observed": n["attributes"].get("first_observed", ""),
                    "created_at": n["created_at"]
                })
        return problems

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


@app.get("/api/story_log")
async def get_story_log():
    """Retrieve a chronological, hierarchical log of development sessions."""
    if IS_DEMO_MODE:
        return [
            {
                "id": "node_session_1",
                "date": "2026-05-10",
                "title": "Sprint 1: Caching Tier",
                "summary": "Focused on implementing a robust, distributed caching strategy to address response delays.",
                "decisions": [
                    {
                        "id": "node_decision_redis",
                        "name": "Use Redis for Cache",
                        "summary": "We chose Redis over Memcached for caching to support rich data types and LRU policies.",
                        "rationale": "Redis offers sub-millisecond key-value retrieval and natively supports eviction policies (LRU)."
                    }
                ],
                "problems": [
                    {
                        "id": "node_problem_lag",
                        "name": "High API Response Lag",
                        "summary": "Concurrent load is causing response latency to spike past 800ms during peak hours.",
                        "status": "resolved"
                    }
                ],
                "experiments": [
                    {
                        "id": "node_exp_redis",
                        "name": "Redis vs In-Memory dict",
                        "summary": "Tested Redis local memory footprint vs unbounded in-memory Python dictionary cache.",
                        "success": True
                    }
                ],
                "artifacts": [
                    {
                        "id": "node_artifact_spec",
                        "name": "CACHING_SPEC.md",
                        "summary": "Architecture specifications document detailing API caching and Mutex strategies."
                    }
                ]
            },
            {
                "id": "node_session_2",
                "date": "2026-05-15",
                "title": "Sprint 2: Auth Strategy",
                "summary": "Explored and compared scalable authentication frameworks for third-party developer integrations.",
                "decisions": [
                    {
                        "id": "node_decision_jwt",
                        "name": "Stateless JWT Tokens",
                        "summary": "Adopted stateless JWT tokens signed locally on gateways to avoid multi-region DB session checks.",
                        "rationale": "Stateless signatures prevent centralized session database hits, avoiding regional latency bottlenecks."
                    }
                ],
                "problems": [],
                "experiments": [
                    {
                        "id": "node_exp_jwt",
                        "name": "Stateless JWT Latency",
                        "summary": "Measured stateless JWT local gateway check speed against central DB session calls.",
                        "success": True
                    }
                ],
                "artifacts": []
            },
            {
                "id": "node_session_3",
                "date": "2026-05-20",
                "title": "Sprint 3: Thread Panic",
                "summary": "Investigated and resolved a sporadic thread deadlock freeze in local pools.",
                "decisions": [
                    {
                        "id": "node_decision_mutex",
                        "name": "Thread-Safe Mutex Lock",
                        "summary": "Chose a thread-safe local Mutex lock to isolate concurrency race conditions strictly within local process pools.",
                        "rationale": "Local Mutex lock prevents thread collisions during shared cache writes without introducing network overhead."
                    }
                ],
                "problems": [
                    {
                        "id": "node_problem_lag",
                        "name": "High API Response Lag",
                        "summary": "Concurrent load is causing response latency to spike past 800ms during peak hours.",
                        "status": "resolved"
                    }
                ],
                "experiments": [],
                "artifacts": []
            }
        ]

    settings = get_settings()
    group_id = settings.GRAPHITI_GROUP_ID
    
    # Query all DevSessions
    cypher_sessions = """
    MATCH (s:Entity)
    WHERE (s.group_id = $group_id OR $group_id IN s.group_ids)
      AND ('DevSession' IN labels(s) OR 'DevSession' IN s.labels)
    RETURN s
    ORDER BY s.session_date DESC, s.created_at DESC
    """
    
    try:
        session_records = await execute_cypher(cypher_sessions, {"group_id": group_id})
        story_log = []
        
        for record in session_records:
            s_node = record.get("s")
            if s_node is None:
                continue
            
            uuid = s_node.get("uuid")
            name = s_node.get("name", "Unnamed Session")
            summary = s_node.get("summary", "")
            created_at = s_node.get("created_at")
            
            # Extract date
            session_date = s_node.get("session_date") or created_at
            date_str = session_date.strftime("%Y-%m-%d") if hasattr(session_date, "strftime") else str(session_date)[:10]
            
            # Fetch all entities connected to this session
            cypher_connections = """
            MATCH (s:Entity {uuid: $uuid})-[r]-(e:Entity)
            WHERE e.group_id = $group_id OR $group_id IN e.group_ids
            RETURN e
            """
            conn_records = await execute_cypher(cypher_connections, {"uuid": uuid, "group_id": group_id})
            
            decisions = []
            problems = []
            experiments = []
            artifacts = []
            
            for conn_rec in conn_records:
                e_node = conn_rec.get("e")
                if e_node is None:
                    continue
                
                # Check entity labels
                e_labels = list(e_node.labels) if hasattr(e_node, "labels") else []
                e_type = "Entity"
                for label in e_labels:
                    if label != "Entity":
                        e_type = label
                        break
                if e_type == "Entity" and e_node.get("labels"):
                    props_labels = e_node.get("labels")
                    if isinstance(props_labels, list) and props_labels:
                        e_type = props_labels[0]
                
                # Parse attributes
                e_attrs = {}
                attrs_raw = e_node.get("attributes")
                if attrs_raw:
                    import json
                    if isinstance(attrs_raw, str):
                        try:
                            e_attrs = json.loads(attrs_raw)
                        except Exception:
                            pass
                    elif isinstance(attrs_raw, dict):
                        e_attrs = attrs_raw
                
                item = {
                    "id": e_node.get("uuid"),
                    "name": e_node.get("name", "Unnamed"),
                    "summary": e_node.get("summary", ""),
                    "attributes": e_attrs
                }
                
                if e_type == "Decision":
                    item["status"] = e_attrs.get("status") or e_node.get("status") or "active"
                    item["rationale"] = e_attrs.get("rationale") or e_node.get("rationale") or ""
                    decisions.append(item)
                elif e_type == "Problem":
                    item["status"] = e_attrs.get("status") or e_node.get("status") or "open"
                    problems.append(item)
                elif e_type == "Experiment":
                    item["success"] = e_attrs.get("success") or e_node.get("success") or False
                    experiments.append(item)
                elif e_type == "Artifact":
                    artifacts.append(item)
                    
            story_log.append({
                "id": uuid,
                "date": date_str,
                "title": name,
                "summary": summary,
                "decisions": decisions,
                "problems": problems,
                "experiments": experiments,
                "artifacts": artifacts
            })
            
        return story_log
        
    except Exception as e:
        logger.error("Error retrieving story log: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest")
async def ingest_session_note(payload: SessionNoteInput):
    """Ingest a session note directly into the Dev Brain."""
    if IS_DEMO_MODE:
        # Mock ingestion response in Demo Mode
        new_id = f"node_note_{len(MOCK_NODES) + 1}"
        MOCK_NODES.append({
            "id": new_id,
            "name": payload.title,
            "type": "DevSession",
            "summary": payload.content[:150] + "...",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "attributes": {"focus_area": "backend", "outcome_status": "productive", "participants": ["Developer"]}
        })
        return {
            "status": "success",
            "title": payload.title,
            "entities_extracted": 1,
            "entity_names": [payload.title],
            "relationships_created": 0
        }

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


@app.get("/api/draft_session")
async def draft_session():
    """Auto-draft a developer session summary using recent Git history and Gemini."""
    if IS_DEMO_MODE:
        # Mock session draft in Demo Mode
        mock_content = (
            "## Context\n"
            "Our query performance on the search endpoints has degraded as the node count grew past 100k. "
            "Today we focused on creating custom composite schemas and indices in our graph database.\n\n"
            "## Decisions Made\n"
            "- **Decision: Adopt Composite Schema Indexes** on Entity nodes.\n"
            "  - **Rationale**: Combining node properties `name` and `type` inside a single index constraint "
            "reduces lookup times from O(N) scans to O(1) B-tree traversals.\n"
            "  - **Status**: Active\n"
            "  - **Domain**: data_model\n\n"
            "## Problems Encountered\n"
            "- **Problem: High query traversal latency**.\n"
            "  - **Severity**: Medium\n"
            "  - **Status**: Resolved\n"
            "  - **First Observed**: 2026-05-24\n"
            "  - **Resolved At**: 2026-05-26\n\n"
            "## Experiments Run\n"
            "- **Experiment: Single Property vs Composite Indexes**.\n"
            "  - **Hypothesis**: Query lookups will drop below 10ms with composite indexing compared to 280ms on raw scans.\n"
            "  - **Approach**: Executed 500 parallel search requests against the seeded mock database before and after indexes.\n"
            "  - **Outcome**: p99 queries dropped to 4.2ms.\n"
            "  - **Success**: True"
        )
        return {
            "title": "Sprint 4: Database Optimization & Index Tuning",
            "content": mock_content
        }
        
    try:
        from ingestion.session_drafter import draft_session_summary
        title, content = await draft_session_summary()
        return {"title": title, "content": content}
    except Exception as e:
        logger.error("Failed to auto-draft session summary: %s", e)
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
