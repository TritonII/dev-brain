# GitHub Ingestion Integration Guide

The **GitHub Ingestor** (`ingestion/github_ingestor.py`) allows you to pull issues and pull requests directly from your repository's history and feed them into the Dev Brain as structured memory. 

Collaborative decisions and bug tracking happen in PRs and Issues, not just commits. Ingesting them bridges the gap between raw code diffs and true design intent!

---

## 1. Prerequisites: Creating a GitHub Personal Access Token (PAT)

While public repositories can be queried anonymously, we highly recommend using a Personal Access Token to avoid GitHub API rate limits and to securely query private repositories.

1. Go to your GitHub account: **Settings > Developer settings > Personal access tokens > Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Give it a descriptive name (e.g. `Dev Brain Ingestion`).
4. Select the **`repo`** scope (covers issues and pull requests).
5. Click **Generate token** and copy the token character string.

---

## 2. Configuration

Add your token to your local environment file (`.env`):

```bash
# Add to .env
GITHUB_TOKEN=ghp_YourGitHubTokenHere123456
```

---

## 3. Running Ingestions

You can run the ingestor via the command line within your virtual environment:

### Ingest All History from a Repository
```bash
uv run python -m ingestion.github_ingestor --repo owner/name
```
*Example*: `uv run python -m ingestion.github_ingestor --repo TritonII/dev-brain`

### Ingest Incremental History (Since a Specific Date)
To only ingest issues and PRs created after a particular sprint:
```bash
uv run python -m ingestion.github_ingestor --repo owner/name --since 2026-05-01
```

### Limit the Number of Items Ingested
Perfect for quick tests and budget control:
```bash
uv run python -m ingestion.github_ingestor --repo owner/name --limit 10
```

---

## 4. How Issues & PRs Map to Graph Entities

- **GitHub Issues**:
  - Ingested as a `github_issue` episode.
  - Automatically extracts a **Problem** entity.
  - If the issue is **closed**, the Problem's status property maps to `resolved`. 
  - If the discussion details how it was fixed, it extracts a **Decision** entity representing the resolution approach.
- **GitHub Pull Requests**:
  - Ingested as a `github_pull_request` episode (fully checks merge status).
  - Automatically extracts an **Artifact** representing the PR.
  - Extracts any **Decision** or **Experiment** entities described in the PR description or commits.
  - Looks for closure keywords (e.g., "fixes #15", "closes #42") and constructs explicit **VALIDATES** or **SUPERSEDES** edges connecting the PR Artifact to those Issues or Decisions.

---

## 5. Verification

Once ingested:
1. Spin up the Visualizer (`uv run python -m dashboard.server`).
2. Type `GitHub Issue` in the semantic search bar to highlight all newly ingested issues.
3. Review extracted entities and edges inside the Inspector sidebar to see your team's collaborative memory visualized!
