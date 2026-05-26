# Dev Brain Web Visualizer Guide

The **Dev Brain Dashboard & Visualizer** is a high-fidelity, premium dark-mode web application designed to bring your temporal knowledge graph to life. Instead of typing Cypher queries or filtering MCP text in your terminal, the Web Visualizer lets you see your project's decisions, problems, and experiments evolve visually.

---

## Quick Start

1. **Spin up the FastAPI server**:
   ```bash
   uv run python -m dashboard.server
   ```
2. **Access the Visualizer**:
   Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Interface Layout & Key Features

The visualizer workspace is split into three main areas: the **Header**, the **Visual Graph Workspace**, and the **Inspector/Ingestion Sidebar**.

### 1. The Global Header
- **Neo4j Connection Health Check**: In the top-right corner, an active green heartbeat indicator shows connection status. If your database goes offline, it automatically changes to a red warning state and displays the error.
- **Global Semantic Search**: A floating search bar that connects directly to Graphiti's hybrid semantic search.
- **View Toggle Tabs**: Easily switch between the **Visualizer**, the **Decisions Log** (a clean log of architectural choices), and the **Problems Board** (active bugs and blockers).

### 2. The Visual Graph Workspace
- **Custom-Styled Entity Nodes**: Different entity types are represented by unique colors and shapes with distinct neon glows:
  - 🔵 **DevSession** (Round-Rectangle): Developer sessions.
  - 🟢 **Decision** (Diamond): Key technical choices.
  - 🔴 **Problem** (Octagon): Issues and bugs.
  - 🟣 **Experiment** (Hexagon): Attempted hypotheses.
  - 🟡 **Concept** (Ellipse): Software design patterns.
  - ⚫ **Artifact** (Rectangle): Commits, specs, and code outputs.
- **Viewport Layout Controls**: Floating buttons in the top-left let you zoom, center (`Fit`), or reflow the layout using standard algorithms:
  - `cose` (default dynamic physics layout)
  - `grid` (structured blocks)
  - `circle` (modular layouts)
- **Temporal Time-Travel Slider**: A sleek timeline slider at the bottom of the graph. Sliding it back-and-forth dynamically filters out nodes based on their ingestion timestamps. This lets you visually "play back" how your project's architectural mental model grew over weeks of work!

### 3. The Inspector & Ingestion Sidebar
Toggle between the **Inspector** and **Ingest Note** tabs in the top-right:
- **Interactive Node & Edge Inspector**: Clicking any node or relationship line zooms the viewport in and loads comprehensive metadata:
  - Custom attributes defined in your Pydantic schemas (e.g. status, severity, domain, decided_at).
  - Creation dates.
  - A clean list of all **Connected Relationships** (inbound/outbound edges) with quick-click navigation to neighbor nodes.
- **Direct Session Ingestor**: An interactive markdown form where you can paste session summaries. The server routes these directly to Gemini for entity resolution and updates the live Cytoscape graph in real time without refreshing the page!

---

## Pro-Tips for Graph Navigation

- **Isolate Modules**: Double-click any node to select it, which dims all unrelated nodes and highlights its immediate connections.
- **Audit Decisions**: Switch to the **Decisions Tab** to review a chronological table of active choices. Click on any row to instantly jump back to the Visualizer, auto-selecting and centering that Decision node in the network!
