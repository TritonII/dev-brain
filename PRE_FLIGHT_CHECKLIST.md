# Pre-Flight Checklist

Complete these items before running your first backfill.

## Required

- [ ] **Gemini API Budget Alert** — Set in GCP Console (recommended $20/month)
  - Navigate to: [GCP Console > Billing > Budgets & alerts](https://console.cloud.google.com/billing/budgets)
  - Scope: filter by your GCP project
  - Services: Vertex AI API
  - Threshold: **$20/month** with email alerts at 50%, 90%, 100%
  - Rationale: Steady state < $5/month. Alert catches runaway ingestion loops.

- [ ] **Neo4j database available** — either:
  - Local via `docker-compose up -d` (see `docker-compose.yml`)
  - Neo4j Aura cloud instance

- [ ] **Environment variables configured** — Copy `.env.example` to `.env` and fill in:
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - `GOOGLE_CLOUD_PROJECT` or `GEMINI_API_KEY`
  - `PRIMARY_REPO_PATH` (path to your main project repo)

## Optional

- [ ] `SECONDARY_REPO_PATH` (path to a second repo to track)
- [ ] `BLOCKED_DB_NAMES` (comma-separated list of production DB names to never write to)
- [ ] `GRAPHITI_READ_ONLY=true` (if you only want to query, not ingest)
