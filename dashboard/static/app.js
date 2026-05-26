// Dev Brain Visualizer Application Logic

let cy = null;
let currentView = "visualizer";
let activeSidebarTab = "inspect";
let graphData = { nodes: [], edges: [] };
let allNodesDates = []; // Stores dates sorted to compute timeline ranges

// Color map for node types
const TYPE_COLORS = {
    "DevSession": "#3b82f6",   // Blue
    "Decision": "#10b981",     // Emerald Green
    "Problem": "#ef4444",      // Rose Red
    "Experiment": "#a855f7",   // Violet Purple
    "Concept": "#eab308",      // Amber Yellow
    "Artifact": "#64748b",     // Slate Gray
    "Entity": "#6366f1"        // Default Indigo
};

// Shape map for node types
const TYPE_SHAPES = {
    "DevSession": "round-rectangle",
    "Decision": "diamond",
    "Problem": "octagon",
    "Experiment": "hexagon",
    "Concept": "ellipse",
    "Artifact": "rectangle"
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    await checkDatabaseHealth();
    await reloadAllData();
}

function setupEventListeners() {
    // Timeline slider change listener
    const slider = document.getElementById("timeline-slider");
    slider.addEventListener("input", (e) => {
        filterGraphByTimeline(parseFloat(e.target.value));
    });
}

// Database Connection Indicator Check
async function checkDatabaseHealth() {
    try {
        const res = await fetch("/api/health");
        const data = await res.json();
        const indicator = document.getElementById("health-status");
        if (data.status === "ok") {
            if (data.database === "demo_mode") {
                indicator.innerText = "Demo Mode Active (Mock)";
                indicator.parentElement.className = "flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs glow-purple";
                indicator.previousElementSibling.className = "w-1.5 h-1.5 rounded-full bg-purple-400 dot-blink";
            } else {
                indicator.innerText = "Neo4j Connected";
                indicator.parentElement.className = "flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs";
                indicator.previousElementSibling.className = "w-1.5 h-1.5 rounded-full bg-emerald-400 dot-blink";
            }
        } else {
            showErrorStatus(data.message || "Connection error");
        }
    } catch (e) {
        showErrorStatus("Server Unreachable");
    }
}

function showErrorStatus(message) {
    const indicator = document.getElementById("health-status");
    indicator.innerText = `Database Offline (${message.substring(0, 15)})`;
    indicator.parentElement.className = "flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs";
    indicator.previousElementSibling.className = "w-1.5 h-1.5 rounded-full bg-rose-400";
}

// Trigger data reload across views
async function reloadAllData() {
    await loadGraphData();
    if (currentView === "decisions") await loadDecisions();
    if (currentView === "problems") await loadProblems();
}

// ── API: Load & Render Cytoscape Graph ──────────────────────────────────────

async function loadGraphData() {
    try {
        const res = await fetch("/api/graph");
        if (!res.ok) throw new Error("Failed to fetch graph data");
        
        graphData = await res.json();
        
        // Sort and populate timeline boundaries
        extractNodeTimestamps();
        
        // Render or update the visualizer
        renderCytoscape();
    } catch (e) {
        console.error("Error loading graph data:", e);
        showNotification("Error", "Could not fetch graph data from Neo4j.", "error");
    }
}

function extractNodeTimestamps() {
    allNodesDates = graphData.nodes
        .map(n => n.created_at ? new Date(n.created_at) : null)
        .filter(d => d && !isNaN(d.getTime()))
        .sort((a, b) => a - b);
        
    const startLabel = document.getElementById("timeline-start");
    const endLabel = document.getElementById("timeline-end");
    const timelineLabel = document.getElementById("timeline-label");
    
    if (allNodesDates.length > 0) {
        const formatOptions = { month: "short", day: "numeric", year: "2-digit" };
        startLabel.innerText = allNodesDates[0].toLocaleDateString("en-US", formatOptions);
        endLabel.innerText = allNodesDates[allNodesDates.length - 1].toLocaleDateString("en-US", formatOptions);
        timelineLabel.innerText = "All History (Active)";
    } else {
        startLabel.innerText = "-";
        endLabel.innerText = "-";
        timelineLabel.innerText = "No Nodes Ingested";
    }
}

function renderCytoscape() {
    // Format nodes & edges for Cytoscape
    const cyNodes = graphData.nodes.map(n => ({
        data: {
            id: n.id,
            name: n.name,
            type: n.type,
            summary: n.summary,
            created_at: n.created_at,
            attributes: n.attributes,
            color: TYPE_COLORS[n.type] || TYPE_COLORS["Entity"],
            shape: TYPE_SHAPES[n.type] || "ellipse"
        }
    }));

    const cyEdges = graphData.edges.map(e => ({
        data: {
            id: e.id,
            source: e.source,
            target: e.target,
            type: e.type,
            fact: e.fact,
            valid_at: e.valid_at
        }
    }));

    // Initialize Cytoscape
    cy = cytoscape({
        container: document.getElementById("cy"),
        elements: [...cyNodes, ...cyEdges],
        style: [
            {
                selector: "node",
                style: {
                    "label": "data(name)",
                    "background-color": "data(color)",
                    "shape": "data(shape)",
                    "color": "#e2e8f0",
                    "font-size": "10px",
                    "font-family": "Outfit, sans-serif",
                    "font-weight": "500",
                    "text-valign": "bottom",
                    "text-margin-y": "5px",
                    "width": "22px",
                    "height": "22px",
                    "border-width": "1px",
                    "border-color": "#ffffff",
                    "border-opacity": "0.15",
                    "transition-property": "background-color, width, height, border-color",
                    "transition-duration": "0.2s"
                }
            },
            {
                selector: "edge",
                style: {
                    "width": 1.5,
                    "line-color": "rgba(99, 102, 241, 0.25)",
                    "target-arrow-color": "rgba(99, 102, 241, 0.45)",
                    "target-arrow-shape": "chevron",
                    "curve-style": "bezier",
                    "arrow-scale": 0.8,
                    "label": "data(type)",
                    "font-size": "6px",
                    "color": "#818cf8",
                    "font-family": "JetBrains Mono, monospace",
                    "text-background-opacity": 0.8,
                    "text-background-color": "#090d16",
                    "text-background-padding": "2px",
                    "text-background-shape": "round-rectangle",
                    "control-point-step-size": 40,
                    "transition-property": "line-color, target-arrow-color, width",
                    "transition-duration": "0.2s"
                }
            },
            // Highlights & Hover states
            {
                selector: "node:selected",
                style: {
                    "border-width": "2.5px",
                    "border-color": "#ffffff",
                    "width": "28px",
                    "height": "28px",
                    "font-size": "11px",
                    "font-weight": "700"
                }
            },
            {
                selector: "edge:selected",
                style: {
                    "width": 3,
                    "line-color": "#6366f1",
                    "target-arrow-color": "#6366f1",
                    "font-size": "7px",
                    "color": "#ffffff"
                }
            },
            // Semantic Search match nodes styling
            {
                selector: ".highlighted-match",
                style: {
                    "border-width": "3px",
                    "border-color": "#eab308", // Yellow border for semantic match
                    "width": "30px",
                    "height": "30px"
                }
            },
            {
                selector: ".faded",
                style: {
                    "opacity": 0.15
                }
            }
        ],
        layout: {
            name: "cose",
            nodeOverlap: 20,
            idealEdgeLength: 100,
            componentSpacing: 100,
            nodeRepulsion: 400000,
            edgeElasticity: 100,
            nestingElasticity: 5,
            gravity: 80,
            numIter: 1000,
            initialTemp: 200,
            coolingFactor: 0.95,
            minTemp: 1.0,
            animate: false
        }
    });

    // Custom layout optimization
    fitGraph();

    // Node & Edge selection event handlers
    cy.on("tap", "node", (evt) => {
        const node = evt.target;
        inspectNode(node.data());
    });

    cy.on("tap", "edge", (evt) => {
        const edge = evt.target;
        inspectEdge(edge.data());
    });

    cy.on("tap", (evt) => {
        if (evt.target === cy) {
            clearInspector();
        }
    });
}

function fitGraph() {
    if (cy) {
        cy.animate({
            fit: { padding: 40 },
            duration: 500,
            easing: "cubic-bezier(0.4, 0, 0.2, 1)"
        });
    }
}

function layoutGraph(layoutName) {
    if (cy) {
        cy.layout({
            name: layoutName,
            animate: true,
            animationDuration: 600,
            animationEasing: "cubic-bezier(0.4, 0, 0.2, 1)",
            fit: true,
            padding: 30
        }).run();
    }
}

// ── Feature: Dynamic Temporal Graph Slider ──────────────────────────────────

function filterGraphByTimeline(percent) {
    if (!cy || allNodesDates.length === 0) return;
    
    // Find target date cutoff based on slider percentage
    const index = Math.min(
        Math.floor((percent / 100) * (allNodesDates.length - 1)),
        allNodesDates.length - 1
    );
    const cutoffDate = allNodesDates[index];
    
    const formatOptions = { month: "short", day: "numeric", year: "2-digit", hour: "2-digit", minute: "2-digit" };
    const dateStr = cutoffDate.toLocaleDateString("en-US", formatOptions);
    
    document.getElementById("timeline-label").innerText = percent === 100 ? "All History (Active)" : `Graph at: ${dateStr}`;
    
    // Batch UI updates in Cytoscape for maximum performance
    cy.batch(() => {
        cy.nodes().forEach(node => {
            const nodeCreated = new Date(node.data("created_at"));
            
            if (nodeCreated && nodeCreated > cutoffDate) {
                node.style("display", "none");
            } else {
                node.style("display", "element");
            }
        });
    });
}

// ── UI: Inspector Sidebar Loading ──────────────────────────────────────────

function inspectNode(data) {
    document.getElementById("inspect-idle").className = "hidden";
    const activePanel = document.getElementById("inspect-active");
    activePanel.className = "flex flex-col gap-6";
    
    // Header & Badges
    const badge = document.getElementById("inspect-badge");
    badge.innerText = data.type;
    badge.style.backgroundColor = `${TYPE_COLORS[data.type]}20`;
    badge.style.color = TYPE_COLORS[data.type];
    badge.style.borderColor = `${TYPE_COLORS[data.type]}40`;
    badge.className = "inline-flex px-2 py-0.5 rounded text-[10px] uppercase font-semibold font-mono tracking-wider mb-2 border";

    document.getElementById("inspect-title").innerText = data.name;
    
    const createdDate = data.created_at ? new Date(data.created_at).toLocaleString() : "Unknown";
    document.getElementById("inspect-created").innerHTML = `<i class="fa-solid fa-calendar mr-1.5 text-white/30"></i>Created: ${createdDate}`;
    
    // Summary
    document.getElementById("inspect-summary").innerText = data.summary || "No description provided.";
    
    // Attributes
    const attrsContainer = document.getElementById("inspect-attrs");
    const attrsSection = document.getElementById("inspect-attrs-section");
    attrsContainer.innerHTML = "";
    
    if (data.attributes && Object.keys(data.attributes).length > 0) {
        attrsSection.className = "border-t border-white/5 pt-4";
        for (const [key, value] of Object.entries(data.attributes)) {
            if (!value) continue;
            
            const row = document.createElement("div");
            row.className = "flex justify-between items-start gap-4 py-1.5 border-b border-white/5";
            
            const keyEl = document.createElement("span");
            keyEl.className = "text-indigo-300 font-semibold truncate max-w-[120px]";
            keyEl.innerText = key;
            
            const valEl = document.createElement("span");
            valEl.className = "text-white/70 text-right break-words max-w-[200px]";
            valEl.innerText = typeof value === "object" ? JSON.stringify(value) : value;
            
            row.appendChild(keyEl);
            row.appendChild(valEl);
            attrsContainer.appendChild(row);
        }
    } else {
        attrsSection.className = "hidden";
    }

    // Neighbors / Relationships connected to this node
    const relsContainer = document.getElementById("inspect-relations");
    relsContainer.innerHTML = "";
    
    const connectedEdges = cy.getElementById(data.id).connectedEdges();
    
    if (connectedEdges.length > 0) {
        connectedEdges.forEach(edge => {
            const edgeData = edge.data();
            const isSource = edgeData.source === data.id;
            const neighborName = isSource 
                ? cy.getElementById(edgeData.target).data("name")
                : cy.getElementById(edgeData.source).data("name");
                
            const relBox = document.createElement("div");
            relBox.className = "p-3 rounded-xl bg-white/5 hover:bg-white/10 transition border border-white/5 cursor-pointer text-xs flex flex-col gap-1";
            relBox.onclick = () => {
                cy.getElementById(edgeData.id).select();
                inspectEdge(edgeData);
            };

            const header = document.createElement("div");
            header.className = "flex justify-between items-center";
            header.innerHTML = `
                <span class="font-semibold text-indigo-400 font-mono text-[10px] bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">${edgeData.type}</span>
                <span class="text-[9px] text-white/30 font-mono">${isSource ? "Outbound" : "Inbound"}</span>
            `;

            const detail = document.createElement("div");
            detail.className = "text-white/80 mt-1 leading-normal";
            detail.innerHTML = isSource 
                ? `→ **${neighborName}**: <span class="text-white/60">${edgeData.fact}</span>`
                : `← **${neighborName}**: <span class="text-white/60">${edgeData.fact}</span>`;

            relBox.appendChild(header);
            relBox.appendChild(detail);
            relsContainer.appendChild(relBox);
        });
    } else {
        relsContainer.innerHTML = `<p class="text-xs text-white/40 text-center py-4">No connected relationships.</p>`;
    }
}

function inspectEdge(data) {
    document.getElementById("inspect-idle").className = "hidden";
    const activePanel = document.getElementById("inspect-active");
    activePanel.className = "flex flex-col gap-6";
    
    const badge = document.getElementById("inspect-badge");
    badge.innerText = "Relationship";
    badge.style.backgroundColor = "rgba(99, 102, 241, 0.1)";
    badge.style.color = "#818cf8";
    badge.style.borderColor = "rgba(99, 102, 241, 0.2)";
    badge.className = "inline-flex px-2 py-0.5 rounded text-[10px] uppercase font-semibold font-mono tracking-wider mb-2 border";

    const sourceName = cy.getElementById(data.source).data("name");
    const targetName = cy.getElementById(data.target).data("name");
    document.getElementById("inspect-title").innerText = `${sourceName} ──► ${targetName}`;
    
    const validAt = data.valid_at ? new Date(data.valid_at).toLocaleString() : "Unknown";
    document.getElementById("inspect-created").innerHTML = `<i class="fa-solid fa-calendar mr-1.5 text-white/30"></i>Validated: ${validAt}`;

    document.getElementById("inspect-summary").innerHTML = `
        <div class="font-mono text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded inline-block mb-3">${data.type}</div>
        <p class="text-white/80 leading-relaxed font-outfit text-md">"${data.fact}"</p>
    `;

    document.getElementById("inspect-attrs-section").className = "hidden";
    
    const relsContainer = document.getElementById("inspect-relations");
    relsContainer.innerHTML = `
        <div class="flex flex-col gap-2">
            <div class="p-3 bg-white/5 rounded-xl border border-white/5 flex flex-col gap-1 cursor-pointer" onclick="cy.getElementById('${data.source}').select(); inspectNode(cy.getElementById('${data.source}').data());">
                <span class="text-[9px] uppercase font-semibold font-mono text-indigo-400">Source Entity</span>
                <span class="text-sm font-semibold text-white">${sourceName}</span>
            </div>
            <div class="p-3 bg-white/5 rounded-xl border border-white/5 flex flex-col gap-1 cursor-pointer" onclick="cy.getElementById('${data.target}').select(); inspectNode(cy.getElementById('${data.target}').data());">
                <span class="text-[9px] uppercase font-semibold font-mono text-indigo-400">Target Entity</span>
                <span class="text-sm font-semibold text-white">${targetName}</span>
            </div>
        </div>
    `;
}

function clearInspector() {
    document.getElementById("inspect-idle").className = "flex flex-col items-center justify-center text-center py-20 text-white/30";
    document.getElementById("inspect-active").className = "hidden";
}

// ── Feature: Global Semantic Search Highlighting ─────────────────────────────

async function handleGlobalSearch() {
    const query = document.getElementById("global-search").value.trim();
    if (!query) {
        if (cy) {
            cy.elements().removeClass("highlighted-match faded");
            fitGraph();
        }
        return;
    }

    try {
        const res = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error("Search request failed");
        
        const data = await res.json();
        
        if (!cy) return;
        
        // Clear old highlights
        cy.elements().removeClass("highlighted-match faded");
        
        const matchNodeIds = data.nodes.map(n => n.id);
        
        if (matchNodeIds.length === 0) {
            showNotification("Search", "No semantic matches found.", "info");
            return;
        }
        
        // Style non-matching faded and matching nodes highlighted
        cy.batch(() => {
            cy.nodes().forEach(node => {
                if (matchNodeIds.includes(node.id())) {
                    node.addClass("highlighted-match");
                } else {
                    node.addClass("faded");
                }
            });
            cy.edges().addClass("faded");
        });
        
        // Zoom and animate layout to fit the matches
        const matchingElements = cy.nodes().filter(n => matchNodeIds.includes(n.id()));
        cy.animate({
            fit: { eles: matchingElements, padding: 80 },
            duration: 600,
            easing: "cubic-bezier(0.4, 0, 0.2, 1)"
        });
        
        showNotification("Search Complete", `Found ${matchNodeIds.length} semantic matches in graph`, "success");
        
    } catch (e) {
        console.error("Error doing semantic search:", e);
        showNotification("Search Failed", "An error occurred doing semantic search", "error");
    }
}

// ── UI: Tab Switching & Lists Rendering ──────────────────────────────────────

function switchView(viewName) {
    currentView = viewName;
    
    // Toggle active tabs class
    ["visualizer", "decisions", "problems"].forEach(v => {
        const tab = document.getElementById(`tab-${v}`);
        const view = document.getElementById(`view-${v}`);
        
        if (v === viewName) {
            tab.className = "px-3 py-1 text-xs rounded-md font-medium transition bg-indigo-600 text-white";
            view.classList.remove("hidden");
        } else {
            tab.className = "px-3 py-1 text-xs rounded-md font-medium transition text-white/70 hover:text-white";
            view.classList.add("hidden");
        }
    });

    // Populate data based on active view
    if (viewName === "decisions") loadDecisions("active");
    if (viewName === "problems") loadProblems("open");
}

async function loadDecisions(status = "active") {
    // Toggle Active / Superseded style
    const activeBtn = document.getElementById("btn-decision-active");
    const supersededBtn = document.getElementById("btn-decision-superseded");
    
    if (status === "active") {
        activeBtn.className = "px-3 py-1.5 rounded-md transition bg-indigo-600 text-white font-medium";
        supersededBtn.className = "px-3 py-1.5 rounded-md transition text-white/70 hover:text-white font-medium";
    } else {
        supersededBtn.className = "px-3 py-1.5 rounded-md transition bg-indigo-600 text-white font-medium";
        activeBtn.className = "px-3 py-1.5 rounded-md transition text-white/70 hover:text-white font-medium";
    }

    try {
        const res = await fetch(`/api/decisions?status=${status}`);
        const decisions = await res.json();
        
        const body = document.getElementById("decisions-table-body");
        body.innerHTML = "";
        
        if (decisions.length === 0) {
            body.innerHTML = `
                <tr>
                    <td colspan="4" class="py-8 text-center text-white/30 text-xs">
                        No ${status} decisions found in the knowledge graph.
                    </td>
                </tr>
            `;
            return;
        }

        decisions.forEach(d => {
            const tr = document.createElement("tr");
            tr.className = "border-b border-white/5 hover:bg-white/5 transition cursor-pointer";
            tr.onclick = () => {
                switchView("visualizer");
                cy.getElementById(d.id).select();
                inspectNode(cy.getElementById(d.id).data());
            };

            const decidedDate = new Date(d.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

            tr.innerHTML = `
                <td class="py-3.5 px-4 font-semibold text-white font-outfit max-w-[200px] truncate">${d.name}</td>
                <td class="py-3.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">${d.domain}</span></td>
                <td class="py-3.5 px-4 text-white/60 max-w-[300px] truncate">${d.summary || d.rationale}</td>
                <td class="py-3.5 px-4 font-mono text-xs text-white/40">${decidedDate}</td>
            `;
            body.appendChild(tr);
        });
    } catch (e) {
        console.error("Error loading decisions table:", e);
    }
}

async function loadProblems(status = "open") {
    const openBtn = document.getElementById("btn-problem-open");
    const resolvedBtn = document.getElementById("btn-problem-resolved");
    
    if (status === "open") {
        openBtn.className = "px-3 py-1.5 rounded-md transition bg-indigo-600 text-white font-medium";
        resolvedBtn.className = "px-3 py-1.5 rounded-md transition text-white/70 hover:text-white font-medium";
    } else {
        resolvedBtn.className = "px-3 py-1.5 rounded-md transition bg-indigo-600 text-white font-medium";
        openBtn.className = "px-3 py-1.5 rounded-md transition text-white/70 hover:text-white font-medium";
    }

    try {
        const res = await fetch(`/api/problems?status=${status}`);
        const problems = await res.json();
        
        const container = document.getElementById("problems-list");
        container.innerHTML = "";
        
        if (problems.length === 0) {
            container.innerHTML = `
                <div class="col-span-full py-16 text-center text-white/30 text-xs">
                    No ${status} problems found. Outstanding job!
                </div>
            `;
            return;
        }

        problems.forEach(p => {
            const card = document.createElement("div");
            card.className = "p-5 rounded-2xl bg-white/5 border border-white/5 hover:border-white/10 hover:bg-white/10 transition cursor-pointer flex flex-col gap-2 relative overflow-hidden";
            card.onclick = () => {
                switchView("visualizer");
                cy.getElementById(p.id).select();
                inspectNode(cy.getElementById(p.id).data());
            };

            // Glow & Indicator based on severity
            let severityColor = "bg-yellow-400 text-yellow-400 border-yellow-400/20";
            if (p.severity.toLowerCase() === "critical") severityColor = "bg-rose-500 text-rose-500 border-rose-500/20";
            if (p.severity.toLowerCase() === "high") severityColor = "bg-orange-500 text-orange-500 border-orange-500/20";
            if (p.severity.toLowerCase() === "low") severityColor = "bg-slate-400 text-slate-400 border-slate-400/20";

            card.innerHTML = `
                <div class="flex justify-between items-center">
                    <span class="text-[10px] font-mono uppercase bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-0.5 rounded">Problem</span>
                    <span class="text-[9px] uppercase font-semibold font-mono border px-2 py-0.5 rounded ${severityColor}">${p.severity} Severity</span>
                </div>
                <h3 class="text-md font-bold font-outfit text-white mt-1 leading-tight">${p.name}</h3>
                <p class="text-xs text-white/50 leading-relaxed mt-1 flex-1">${p.summary}</p>
                <div class="text-[10px] font-mono text-white/30 border-t border-white/5 pt-2.5 mt-2.5 flex items-center justify-between">
                    <span>Observed: ${new Date(p.created_at).toLocaleDateString()}</span>
                    <span class="capitalize text-indigo-400 font-semibold">${p.status}</span>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading problems log:", e);
    }
}

// ── Ingest Note Panel Logic ──────────────────────────────────────────────────

function toggleSidebarTab(tabName) {
    activeSidebarTab = tabName;
    const inspectBtn = document.getElementById("sb-tab-inspect");
    const ingestBtn = document.getElementById("sb-tab-ingest");
    const inspectContent = document.getElementById("sb-content-inspect");
    const ingestContent = document.getElementById("sb-content-ingest");
    
    if (tabName === "inspect") {
        inspectBtn.className = "px-3 py-1 rounded bg-indigo-600 text-white font-medium transition";
        ingestBtn.className = "px-3 py-1 rounded text-white/60 hover:text-white font-medium transition";
        inspectContent.classList.remove("hidden");
        ingestContent.classList.add("hidden");
    } else {
        ingestBtn.className = "px-3 py-1 rounded bg-indigo-600 text-white font-medium transition";
        inspectBtn.className = "px-3 py-1 rounded text-white/60 hover:text-white font-medium transition";
        ingestContent.classList.remove("hidden");
        inspectContent.classList.add("hidden");
    }
}

async function submitSessionNote() {
    const title = document.getElementById("note-title").value.trim();
    const content = document.getElementById("note-content").value.trim();
    
    if (!title || !content) {
        showNotification("Validation Error", "Title and session summary are required.", "error");
        return;
    }

    const btn = document.getElementById("btn-submit-note");
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1.5"></i>Ingesting... (takes 5-20s)`;
    btn.disabled = true;

    try {
        const res = await fetch("/api/ingest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, content })
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Ingestion request failed");
        }
        
        const data = await res.json();
        
        showNotification(
            "Ingestion Successful", 
            `Extracted ${data.entities_extracted} entities and created ${data.relationships_created} relationships.`, 
            "success"
        );
        
        // Reset input fields
        document.getElementById("note-title").value = "";
        document.getElementById("note-content").value = "";
        
        // Refresh Visualizer Graph in background
        await loadGraphData();
        toggleSidebarTab("inspect");
        
    } catch (e) {
        console.error("Error submitting note:", e);
        showNotification("Ingestion Error", e.message || "Failed to ingest note into Dev Brain", "error");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// ── Global Custom Notifications ──────────────────────────────────────────────

function showNotification(title, description, type = "success") {
    const notif = document.getElementById("notification");
    const icon = document.getElementById("notif-icon");
    
    document.getElementById("notif-title").innerText = title;
    document.getElementById("notif-desc").innerText = description;
    
    // Style configurations based on notification type
    if (type === "success") {
        notif.className = "fixed bottom-6 right-6 z-50 transform translate-y-0 opacity-100 transition duration-300 flex items-center gap-4 px-5 py-4 rounded-2xl shadow-xl glass-card border border-emerald-500/30 glow-green text-emerald-300";
        icon.className = "fa-solid fa-circle-check text-emerald-400 text-xl";
    } else if (type === "error") {
        notif.className = "fixed bottom-6 right-6 z-50 transform translate-y-0 opacity-100 transition duration-300 flex items-center gap-4 px-5 py-4 rounded-2xl shadow-xl glass-card border border-rose-500/30 glow-red text-rose-300";
        icon.className = "fa-solid fa-circle-xmark text-rose-400 text-xl";
    } else { // info
        notif.className = "fixed bottom-6 right-6 z-50 transform translate-y-0 opacity-100 transition duration-300 flex items-center gap-4 px-5 py-4 rounded-2xl shadow-xl glass-card border border-indigo-500/30 glow-indigo text-indigo-300";
        icon.className = "fa-solid fa-circle-info text-indigo-400 text-xl";
    }

    // Dismiss after 4 seconds
    setTimeout(() => {
        notif.className = "fixed bottom-6 right-6 z-50 transform translate-y-24 opacity-0 transition duration-300 flex items-center gap-4 px-5 py-4 rounded-2xl shadow-xl glass-card border border-white/5";
    }, 4500);
}
