// Node type → display config (colour, icon label, priority in chain)
const NODE_CONFIG = {
  api_request:  { color: "#7c3aed", border: "#9b5cf6", icon: "⟡", label: "API Request"   },
  endpoint:     { color: "#1e3a5f", border: "#3b82f6", icon: "⌁", label: "Endpoint"      },
  exception:    { color: "#4c1a1e", border: "#ef4444", icon: "⚠", label: "Exception"     },
  stack_trace:  { color: "#1c2a1c", border: "#22c55e", icon: "≡", label: "Stack Trace"   },
  function:     { color: "#1a2a3c", border: "#38bdf8", icon: "ƒ", label: "Function"      },
  source_file:  { color: "#1f1a10", border: "#f59e0b", icon: "📄", label: "Source File"  },
  past_incident:{ color: "#2a1540", border: "#c084fc", icon: "⏳", label: "Past Incident" },
  git_blame:    { color: "#0f1f1f", border: "#2dd4bf", icon: "⎇", label: "Git Blame"     },
  commit:       { color: "#0f1a0f", border: "#4ade80", icon: "◆", label: "Commit"        },
  diff:         { color: "#1a1a0a", border: "#eab308", icon: "±", label: "Diff"          },
  deploy:       { color: "#101828", border: "#60a5fa", icon: "⬆", label: "Deploy"        },
  test_result:  { color: "#0f1a15", border: "#34d399", icon: "✓", label: "Test Result"   },
};

function getNodeConfig(nodeType) {
  return NODE_CONFIG[nodeType] || { color: "#1a1a2e", border: "#6366f1", icon: "◉", label: nodeType };
}

function GraphNode({ node }) {
  const cfg = getNodeConfig(node.node_type);
  const data = node.data || {};

  return (
    <div
      className="graph-node"
      style={{ borderColor: cfg.border, background: cfg.color }}
    >
      <div className="graph-node-type-row">
        <span className="graph-node-icon">{cfg.icon}</span>
        <span className="graph-node-type" style={{ color: cfg.border }}>
          {cfg.label}
        </span>
        <span className="graph-node-id">#{node.id}</span>
      </div>
      <div className="graph-node-label">{node.label}</div>

      {/* Show relevant data fields — never raw secrets */}
      {node.node_type === "api_request" && (
        <div className="graph-node-meta">
          {data.http_method && <span className="meta-tag">{data.http_method}</span>}
          {data.status_code && <span className="meta-tag">HTTP {data.status_code}</span>}
          {data.environment && <span className="meta-tag">{data.environment}</span>}
        </div>
      )}
      {node.node_type === "exception" && (
        <div className="graph-node-meta">
          {data.exception_type && <span className="meta-tag">{data.exception_type}</span>}
        </div>
      )}
      {node.node_type === "function" && (
        <div className="graph-node-meta">
          {data.function_name && <span className="meta-tag">fn: {data.function_name}</span>}
          {data.line_number && <span className="meta-tag">L{data.line_number}</span>}
        </div>
      )}
      {node.node_type === "source_file" && (
        <div className="graph-node-meta">
          {data.file_path && <span className="meta-tag">{data.file_path}</span>}
          {data.line_number && <span className="meta-tag">L{data.line_number}</span>}
        </div>
      )}
      {node.node_type === "past_incident" && (
        <div className="graph-node-meta">
          {data.matched_incident_id && (
            <span className="meta-tag">Incident #{data.matched_incident_id}</span>
          )}
          {data.exception_type && <span className="meta-tag">{data.exception_type}</span>}
        </div>
      )}
    </div>
  );
}

function GraphEdge({ edge, nodeMap }) {
  const src = nodeMap[edge.source_node_id];
  const tgt = nodeMap[edge.target_node_id];
  if (!src || !tgt) return null;
  const srcCfg = getNodeConfig(src.node_type);

  return (
    <div className="graph-edge-row">
      <span className="graph-edge-src" style={{ color: srcCfg.border }}>
        {src.label}
      </span>
      <span className="graph-edge-arrow">
        <span className="graph-edge-label">{edge.relationship}</span>
        →
      </span>
      <span className="graph-edge-tgt" style={{ color: getNodeConfig(tgt.node_type).border }}>
        {tgt.label}
      </span>
    </div>
  );
}

// Core RCA chain: api_request → endpoint → exception → stack_trace → function → source_file
const CHAIN_ORDER = [
  "api_request", "endpoint", "exception", "stack_trace", "function", "source_file",
];

function sortNodesForDisplay(nodes) {
  const chainNodes = [];
  const otherNodes = [];
  for (const type of CHAIN_ORDER) {
    const matches = nodes.filter((n) => n.node_type === type);
    chainNodes.push(...matches);
  }
  for (const node of nodes) {
    if (!CHAIN_ORDER.includes(node.node_type)) otherNodes.push(node);
  }
  return { chainNodes, otherNodes };
}

export default function EvidenceGraphView({
  graphData = null,
  loading = false,
  error = null,
  onBuild,
  onRebuild,
}) {
  if (loading) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 3: EVIDENCE GRAPH</p>
            <h3>Constructing Evidence Graph...</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <span
            className="live-dot loading"
            style={{ margin: "0 auto 12px", display: "block", width: 7, height: 7, borderRadius: "50%", background: "#fbbf24" }}
          />
          <p>Building node graph from incident telemetry and collected evidence...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 3: EVIDENCE GRAPH</p>
            <h3>Evidence Graph</h3>
          </div>
        </div>
        <div className="error-banner">
          <span>⚠️ {error}</span>
          {onBuild && (
            <button className="view-all" onClick={onBuild} style={{ color: "#fb7185" }}>
              Retry Build
            </button>
          )}
        </div>
      </section>
    );
  }

  // "Ready to Build" state — evidence collected but graph not yet built
  if (!graphData) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 3: EVIDENCE GRAPH</p>
            <h3>Evidence Graph</h3>
          </div>
        </div>
        <div className="workspace-action-bar" style={{ marginTop: 0 }}>
          <div className="action-description">
            <strong>Ready to Build Evidence Graph</strong>
            <p>
              Constructs the deterministic node graph connecting API Request → Endpoint →
              Exception → Stack Trace → Function → Source File, with historical precedents.
            </p>
          </div>
          <button className="investigate-button" onClick={onBuild}>
            Build Evidence Graph →
          </button>
        </div>
      </section>
    );
  }

  const nodes = graphData.graph?.nodes || [];
  const edges = graphData.graph?.edges || [];

  if (nodes.length === 0) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 3: EVIDENCE GRAPH</p>
            <h3>Evidence Graph</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <h3>Insufficient Graph Data</h3>
          <p>
            The backend returned an empty graph. Ensure the incident has a valid stack
            trace and collected evidence before rebuilding.
          </p>
          <button className="investigate-button" onClick={onRebuild || onBuild}>
            Rebuild Graph
          </button>
        </div>
      </section>
    );
  }

  const nodeMap = {};
  for (const n of nodes) nodeMap[n.id] = n;
  const { chainNodes, otherNodes } = sortNodesForDisplay(nodes);

  return (
    <section className="evidence-section">
      {/* Header row with summary badge */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 3: EVIDENCE GRAPH</p>
          <h3>Evidence Graph · {nodes.length} Nodes · {edges.length} Edges</h3>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span
            className="severity"
            style={{ background: "#1b2518", borderColor: "#2e5229", color: "#86efac", border: "1px solid" }}
          >
            ✓ EVIDENCE-BACKED
          </span>
          <button
            className="view-all"
            onClick={onRebuild || onBuild}
            style={{ fontSize: 10 }}
          >
            Rebuild ↺
          </button>
        </div>
      </div>

      {/* Graph Summary Card */}
      <div className="graph-summary-card">
        <div className="graph-summary-item">
          <span>NODES</span>
          <strong>{nodes.length}</strong>
        </div>
        <div className="graph-summary-item">
          <span>RELATIONSHIPS</span>
          <strong>{edges.length}</strong>
        </div>
        <div className="graph-summary-item">
          <span>EVIDENCE-BACKED</span>
          <strong style={{ color: "#4ade80" }}>YES</strong>
        </div>
        <div className="graph-summary-item">
          <span>SOURCE</span>
          <strong>Backend Evidence Graph</strong>
        </div>
      </div>

      {/* Core RCA Chain — vertical hierarchy */}
      {chainNodes.length > 0 && (
        <div className="graph-chain-section">
          <div className="graph-chain-label">
            <span className="group-indicator telemetry" style={{ display: "inline-block", marginRight: 8 }}></span>
            RCA CAUSAL CHAIN
          </div>
          <div className="graph-chain">
            {chainNodes.map((node, idx) => (
              <div key={node.id} className="graph-chain-item">
                <GraphNode node={node} />
                {idx < chainNodes.length - 1 && (
                  <div className="graph-chain-arrow">↓</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Supporting evidence nodes (past_incident, git_blame, etc.) */}
      {otherNodes.length > 0 && (
        <div className="graph-chain-section" style={{ marginTop: 20 }}>
          <div className="graph-chain-label">
            <span className="group-indicator memory" style={{ display: "inline-block", marginRight: 8 }}></span>
            SUPPORTING EVIDENCE NODES ({otherNodes.length})
          </div>
          <div className="graph-supporting-nodes">
            {otherNodes.map((node) => (
              <GraphNode key={node.id} node={node} />
            ))}
          </div>
        </div>
      )}

      {/* Relationships table */}
      {edges.length > 0 && (
        <div className="graph-edges-section">
          <div className="graph-chain-label">
            <span className="group-indicator github" style={{ display: "inline-block", marginRight: 8 }}></span>
            EVIDENCE RELATIONSHIPS ({edges.length})
          </div>
          <div className="graph-edges-list">
            {edges.map((edge) => (
              <GraphEdge key={edge.id} edge={edge} nodeMap={nodeMap} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
