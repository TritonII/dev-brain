# Query Cookbook

Common queries for the Dev Brain knowledge graph.

## MCP Tool Queries (from Claude Code)

### Status Checks

```
search_brain("What are the currently open problems?")
search_brain("What problems are blocking the API migration?")
get_open_problems(severity="critical")
```

### Decision History

```
search_brain("What decisions have we made about caching strategy?")
get_active_decisions(domain="architecture")
get_active_decisions(domain="frontend")
```

### Experiment Review

```
search_brain("What experiments have we run on performance optimization?")
search_brain("Show me experiments that failed in the last 60 days")
```

### Concept Lookup

```
search_brain("What is the circuit breaker pattern in our codebase?")
search_brain("What concepts have emerged from recent sessions?")
```

### Artifact Search

```
search_brain("What specs have been written in the last 30 days?")
search_brain("What commits touched the authentication module?")
```

### Relationship Queries

```
search_facts("What decisions were derived from performance problems?")
search_facts("What experiments validate the caching approach?")
search_facts("What problems are blocking the migration?")
```

## Direct Cypher Queries (via Neo4j Browser)

### All Active Decisions

```cypher
MATCH (d:Entity)
WHERE d.summary CONTAINS 'decision' AND d.summary CONTAINS 'active'
RETURN d.name, d.summary, d.created_at
ORDER BY d.created_at DESC
```

### Open Problems with Blockers

```cypher
MATCH (p:Entity)
WHERE p.summary CONTAINS 'problem' OR p.summary CONTAINS 'issue'
OPTIONAL MATCH (p)-[r:BLOCKS]->(blocked)
RETURN p.name, p.summary, collect(blocked.name) AS blocks
```

### Experiment Success Rate

```cypher
MATCH (e:Entity)
WHERE e.summary CONTAINS 'experiment'
WITH e,
     CASE WHEN e.summary CONTAINS 'success: true' OR e.summary CONTAINS 'succeeded'
          THEN 1 ELSE 0 END AS success
RETURN count(e) AS total, sum(success) AS succeeded,
       round(100.0 * sum(success) / count(e)) AS success_rate_pct
```

### Decision Supersession Chain

```cypher
MATCH path = (newer:Entity)-[:SUPERSEDES*]->(older:Entity)
WHERE newer.summary CONTAINS 'decision'
RETURN path
```

### Recent Activity Timeline

```cypher
MATCH (ep:Episode)
RETURN ep.name, ep.source_description, ep.valid_at
ORDER BY ep.valid_at DESC
LIMIT 20
```

### Entity Type Distribution

```cypher
MATCH (n:Entity)
RETURN labels(n) AS types, count(n) AS count
ORDER BY count DESC
```

### Session -> Decision Provenance

```cypher
MATCH (s:Entity)-[:EMERGED_FROM]->(session:Entity)
WHERE session.summary CONTAINS 'session'
RETURN session.name AS session, collect(s.name) AS emerged_entities
```
