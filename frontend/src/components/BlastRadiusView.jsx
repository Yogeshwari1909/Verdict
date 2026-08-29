/* ─────────────────────────────────────────────────────────────
   BlastRadiusView.jsx
   Stage 5: Blast Radius / Impact Analysis
   Renders the deterministic output of POST /api/v1/incidents/{id}/impact.
   Zero mock data — every value originates from the backend.
   ───────────────────────────────────────────────────────────── */

const LEVEL_CONFIG = {
  high:    { color: "#fb7185", bg: "#250d13", border: "#7f1d1d", label: "HIGH",    icon: "🔴" },
  medium:  { color: "#fbbf24", bg: "#1f1708", border: "#78350f", label: "MEDIUM",  icon: "🟡" },
  low:     { color: "#4ade80", bg: "#0f2218", border: "#166534", label: "LOW",     icon: "🟢" },
  unknown: { color: "#9ca3af", bg: "#111318", border: "#232836", label: "UNKNOWN", icon: "⚫" },
};

function getLevelConfig(level) {
  return LEVEL_CONFIG[(level || "").toLowerCase()] || LEVEL_CONFIG.unknown;
}

function ScopeList({ heading, items, icon }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="blast-scope-block">
      <div className="blast-scope-heading">
        <span className="blast-scope-icon">{icon}</span>
        {heading}
        <span className="blast-scope-count">{items.length}</span>
      </div>
      <ul className="blast-scope-list">
        {items.map((item, idx) => (
          <li key={idx} className="blast-scope-item">
            <span className="blast-scope-item-dot">▸</span>
            <code className="blast-scope-code">{String(item)}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceRefRow({ ref: evRef }) {
  return (
    <div className="blast-evidence-row">
      <div className="blast-evidence-meta">
        {evRef.node_id != null && (
          <span className="blast-evidence-id">#{evRef.node_id}</span>
        )}
        <span className="blast-evidence-type">{evRef.node_type}</span>
        <span className="blast-evidence-label">{evRef.label}</span>
      </div>
      <p className="blast-evidence-contrib">{evRef.contribution}</p>
    </div>
  );
}

export default function BlastRadiusView({
  impactData,
  loading,
  analyzing,
  error,
  rcaComplete,
  onAnalyze,
  onRetry,
}) {
  // ── GUARD: RCA must be done first ────────────────────────────────────────
  if (!rcaComplete) {
    return (
      <section className="evidence-section blast-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 5: BLAST RADIUS / IMPACT</p>
            <h3>Blast Radius Analysis</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>RCA Required</h3>
          <p>
            Complete the Root Cause Analysis (Stage 4) before running blast-radius
            assessment. Impact scope is derived from RCA evidence — it cannot be
            determined without a completed causal chain.
          </p>
        </div>
      </section>
    );
  }

  // ── LOADING ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 5: BLAST RADIUS / IMPACT</p>
            <h3>Loading Impact Analysis...</h3>
          </div>
        </div>
        <div className="incident-card empty-card"><p>Retrieving prior impact result...</p></div>
      </section>
    );
  }

  // ── ERROR ─────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 5: BLAST RADIUS / IMPACT</p>
            <h3>Blast Radius Analysis</h3>
          </div>
        </div>
        <div className="error-banner">
          <span>⚠️ {error}</span>
          {onRetry && (
            <button className="view-all" onClick={onRetry} style={{ color: "#fb7185" }}>
              Retry Analysis
            </button>
          )}
        </div>
      </section>
    );
  }

  // ── PRE-ANALYSIS: RCA done, impact not yet run ────────────────────────────
  if (!impactData && !analyzing) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 5: BLAST RADIUS / IMPACT</p>
            <h3>Blast Radius Analysis</h3>
          </div>
        </div>
        <div className="workspace-action-bar" style={{ marginTop: 0 }}>
          <div className="action-description">
            <strong>Ready for Blast Radius Assessment</strong>
            <p>
              Determines which services, endpoints, functions, and source files
              are within the failure blast radius. Scope is derived strictly from
              the Evidence Graph — no guesses or inferred dependencies.
            </p>
          </div>
          <button className="investigate-button" onClick={onAnalyze}>
            Analyze Blast Radius →
          </button>
        </div>
      </section>
    );
  }

  // ── ANALYZING ─────────────────────────────────────────────────────────────
  if (analyzing && !impactData) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 5: BLAST RADIUS / IMPACT</p>
            <h3>Analyzing Impact...</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <p>Assessing blast radius from Evidence Graph scope...</p>
        </div>
      </section>
    );
  }

  // ── SUCCESS: render full impact result ───────────────────────────────────
  const {
    affected_service,
    affected_environment,
    affected_endpoints = [],
    affected_functions = [],
    affected_source_files = [],
    related_past_incidents = [],
    impact_level,
    confidence,
    evidence_references = [],
    limitations = [],
  } = impactData;

  const lvlCfg = getLevelConfig(impact_level);
  const pct = Math.round((confidence || 0) * 100);
  const isUnknown = (impact_level || "").toLowerCase() === "unknown" || pct === 0;

  return (
    <section className="evidence-section">
      {/* ── Header ── */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 5: BLAST RADIUS / IMPACT</p>
          <h3>
            Blast Radius Analysis
            {!isUnknown && (
              <span style={{ color: lvlCfg.color, fontSize: 14, marginLeft: 12 }}>
                {lvlCfg.icon} {lvlCfg.label} · {pct}%
              </span>
            )}
          </h3>
        </div>
        <button className="view-all" onClick={onAnalyze || onRetry} style={{ fontSize: 10 }}>
          Re-analyze ↺
        </button>
      </div>

      {/* ── 1. BLAST RADIUS VERDICT CARD ── */}
      <div
        className="blast-verdict-card"
        style={{ borderColor: isUnknown ? "#232836" : lvlCfg.border }}
      >
        <div className="blast-verdict-eyebrow">BLAST RADIUS</div>

        {isUnknown ? (
          <div className="blast-unknown-msg">
            <span style={{ fontSize: 22 }}>⚠</span>
            <p>Insufficient evidence to determine reliable blast radius.</p>
          </div>
        ) : (
          <div className="blast-verdict-body">
            {/* Impact Level Badge */}
            <div
              className="blast-level-badge"
              style={{
                color: lvlCfg.color,
                background: lvlCfg.bg,
                borderColor: lvlCfg.border,
              }}
            >
              {lvlCfg.icon} {lvlCfg.label}
            </div>

            {/* Confidence */}
            <div className="blast-conf-block">
              <div className="blast-conf-label">SCOPE CONFIDENCE</div>
              <div className="blast-conf-pct" style={{ color: lvlCfg.color }}>{pct}%</div>
              <div className="blast-conf-sub">Evidence-backed</div>
              <div className="blast-conf-bar-wrap">
                <div
                  className="blast-conf-bar-fill"
                  style={{ width: pct + "%", background: lvlCfg.color }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── 2. AFFECTED SCOPE SUMMARY ── */}
      <div className="blast-block">
        <div className="blast-block-header">
          <span className="group-indicator telemetry" />
          AFFECTED SCOPE
        </div>

        {/* Service + Environment inline */}
        <div className="blast-service-row">
          <div className="blast-service-item">
            <span className="blast-service-label">AFFECTED SERVICE</span>
            <strong className="blast-service-value">{affected_service}</strong>
          </div>
          <div className="blast-service-item">
            <span className="blast-service-label">ENVIRONMENT</span>
            <strong
              className="blast-service-value"
              style={{
                color: affected_environment?.toLowerCase().includes("prod")
                  ? "#fb7185"
                  : "#fbbf24",
              }}
            >
              {affected_environment}
            </strong>
          </div>
        </div>

        {/* Scope lists — only render sections with data */}
        <ScopeList
          heading="Affected Endpoints"
          items={affected_endpoints}
          icon="⌁"
        />
        <ScopeList
          heading="Affected Functions"
          items={affected_functions}
          icon="ƒ"
        />
        <ScopeList
          heading="Affected Source Files"
          items={affected_source_files}
          icon="📄"
        />
        <ScopeList
          heading="Related Past Incidents"
          items={related_past_incidents.map((id) => "Incident #" + id)}
          icon="⏳"
        />

        {/* If no scope items at all */}
        {affected_endpoints.length === 0 &&
          affected_functions.length === 0 &&
          affected_source_files.length === 0 &&
          related_past_incidents.length === 0 && (
            <div className="blast-empty-scope">
              No specific scope entities were identified in the Evidence Graph.
            </div>
          )}
      </div>

      {/* ── 3. EVIDENCE REFERENCES ── */}
      {evidence_references.length > 0 && (
        <div className="blast-block">
          <div className="blast-block-header">
            <span className="group-indicator github" />
            EVIDENCE REFERENCES · {evidence_references.length} GRAPH NODE{evidence_references.length !== 1 ? "S" : ""}
          </div>
          <div className="blast-evidence-list">
            {evidence_references.map((evRef, idx) => (
              <EvidenceRefRow key={idx} ref={evRef} />
            ))}
          </div>
        </div>
      )}

      {/* ── 4. LIMITATIONS ── */}
      {limitations.length > 0 && (
        <div className="blast-block">
          <div className="blast-block-header">
            <span className="group-indicator" style={{ background: "#fbbf24" }} />
            SCOPE BOUNDARIES · {limitations.length} LIMITATION{limitations.length !== 1 ? "S" : ""}
          </div>
          <div className="blast-limitations-list">
            {limitations.map((lim, idx) => (
              <div key={idx} className="blast-limitation-item">
                <span className="blast-limitation-icon">◦</span>
                <span>{lim}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
