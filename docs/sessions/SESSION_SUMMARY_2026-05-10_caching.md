---
session_date: 2026-05-10
focus_area: backend API
outcome_status: productive
participants: [Developer, Claude-Opus-4]
---

# Dev Session: Caching Tier Implementation

## Context
Our API has been experiencing high concurrent loads, resulting in p99 latencies exceeding 800ms during peak hours. Today we focused on implementing a robust, distributed caching strategy.

## Decisions Made
- **Decision: We chose Redis over Memcached** for the caching layer.
  - **Rationale**: We require sub-millisecond key-value retrieval, but also need support for rich data types (hashes, sorted sets) and cache eviction policies (LRU) which Redis excels at out-of-the-box.
  - **Status**: Active
  - **Domain**: data_model

## Problems Encountered
- **Problem: High concurrent API response lag**.
  - **Severity**: High
  - **Status**: Investigating
  - **First Observed**: 2026-05-09

## Experiments Run
- **Experiment: Redis local cache versus in-memory dict**.
  - **Hypothesis**: Redis caching will lower CPU and memory footprints of the main API server process compared to in-memory Python dictionaries.
  - **Approach**: Set up a local Redis instance and measured memory usage during a load test of 10k requests.
  - **Outcome**: Process memory stayed flat at 110MB with Redis, whereas in-memory dictionary cache expanded process memory to 450MB and hit garbage collection spikes.
  - **Success**: True
