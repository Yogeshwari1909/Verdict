/* ─────────────────────────────────────────────────────────────
   RCAAnalysisView.jsx
   Stage 4: RCA / Cross-Examination Engine
   Renders the deterministic output of POST /api/v1/incidents/{id}/analyze.
   Zero mock data — every value originates from the backend.
   ───────────────────────────────────────────────────────────── */

const STATUS_CONFIG = {
  supported:    { color: "#4ade80", bg: "#0f2218", border: "#166534", label: "SUPPORTED" },
  contradicted: { color: "#fb7185", bg: "#250d13", border: "#7f1d1d", label: "CONTRADICTED" },
  inconclusive: { color: "#fbbf24", bg: "#1f1708", border: "#78350f", label: "INCONCLUSIVE" },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.inconclusive;
  return (
    <span
      className="rca-status-badge"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}
    >
      {cfg.label}
    </span>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 80 ? "#4ade80" : pct >= 60 ? "#fbbf24" : "#fb7185";
  return (
    <div className="rca-conf-bar-wrap">
      <div
        className="rca-conf-bar-fill"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

function EvidenceRefItem({ evRef, accent }) {
  return (
    <div className="rca-evidence-item" style={{ borderLeftColor: accent || "#8b5cf6" }}>
      <div className="rca-evidence-header">
        {evRef.node_id != null && (
          <span className="rca-evidence-id">#{evRef.node_id}</span>
        )}
        <span className="rca-evidence-type">{evRef.node_type}</span>
        <span className="rca-evidence-label">{evRef.label}</span>
      </div>
      <p className="rca-evidence-reason">{evRef.reason}</p>
    </div>
  );
}

function HypothesisCard({ hyp, isSelected }) {
  const cfg = STATUS_CONFIG[hyp.status] || STATUS_CONFIG.inconclusive;
  const pct = Math.round((hyp.confidence || 0) * 100);
  return (
    <div
      className={"rca-hypothesis-card" + (isSelected ? " rca-hypothesis-selected" : "")}
      style={{ borderColor: isSelected ? "#8b5cf6" : cfg.border }}
    >
      {isSelected && <span className="rca-selected-flag">★ SELECTED</span>}
      <div className="rca-hypothesis-header">
        <div>
          <div className="rca-hypothesis-title">{hyp.title}</div>
          <div className="rca-hypothesis-id">{hyp.hypothesis_id}</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
          <StatusBadge status={hyp.status} />
          <span className="rca-conf-value" style={{ color: cfg.color }}>{pct}%</span>
        </div>
      </div>
      <ConfidenceBar value={hyp.confidence} />
      <p className="rca-hypothesis-desc">{hyp.description}</p>
      <div className="rca-hypothesis-evidence-counts">
        <span style={{ color: "#4ade80" }}>
          ✓ {hyp.supporting_evidence ? hyp.supporting_evidence.length : 0} supporting
        </span>
        <span style={{ color: "#fb7185" }}>
          ✕ {hyp.contradicting_evidence ? hyp.contradicting_evidence.length : 0} contradicting
        </span>
      </div>
    </div>
  );
}

export default function RCAAnalysisView({
  rcaData,
  loading,
  analyzing,
  error,
  graphBuilt,
  onRunRca,
  onRetry,
}) {
  if (!graphBuilt) {
    return (
      <section className="evidence-section rca-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 4: RCA / CROSS-EXAMINATION</p>
            <h3>Root Cause Analysis</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>Evidence Graph Required</h3>
          <p>
            Build the Evidence Graph (Stage 3) before running the Cross-Examination Engine.
            RCA derives conclusions from graph nodes and relationships — it cannot operate without them.
          </p>
        </div>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 4: RCA / CROSS-EXAMINATION</p>
            <h3>Loading RCA...</h3>
          </div>
        </div>
        <div className="incident-card empty-card"><p>Retrieving prior RCA result...</p></div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 4: RCA / CROSS-EXAMINATION</p>
            <h3>Root Cause Analysis</h3>
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

  if (!rcaData && !analyzing) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 4: RCA / CROSS-EXAMINATION</p>
            <h3>Root Cause Analysis</h3>
          </div>
        </div>

        <div className="rca-explainer">
          <p className="rca-explainer-text">
            Verdict does not simply generate an answer. It compares hypotheses against
            evidence and records why evidence supports or rejects each hypothesis.
            The Cross-Examination Engine evaluates every candidate root cause against
            the Evidence Graph before issuing a verdict.
          </p>
          <div className="rca-methodology-flow">
            {["Evidence Graph","Competing Hypotheses","Cross-Examination",
              "Supporting / Contradicting Evidence","Evidence-Derived Confidence","Root Cause Verdict"
            ].map((step, idx, arr) => (
              <span key={step} className="rca-flow-step">
                <span className="rca-flow-label">{step}</span>
                {idx < arr.length - 1 && <span className="rca-flow-arrow">↓</span>}
              </span>
            ))}
          </div>
        </div>

        <div className="workspace-action-bar" style={{ marginTop: 0 }}>
          <div className="action-description">
            <strong>Ready for Cross-Examination</strong>
            <p>
              Runs the deterministic hypothesis engine against the Evidence Graph.
              No LLM hallucination — all conclusions are evidence-backed.
            </p>
          </div>
          <button className="investigate-button" onClick={onRunRca}>
            Run RCA Analysis →
          </button>
        </div>
      </section>
    );
  }

  if (analyzing && !rcaData) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 4: RCA / CROSS-EXAMINATION</p>
            <h3>Cross-Examining Evidence...</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <p>Running hypothesis cross-examination against the Evidence Graph...</p>
        </div>
      </section>
    );
  }

  const hypotheses = rcaData.hypotheses || [];
  const selectedHyp = rcaData.selected_hypothesis || null;
  const root_cause_statement = rcaData.root_cause_statement || null;
  const confidence = rcaData.confidence || 0;
  const proof = rcaData.proof || [];
  const limitations = rcaData.limitations || [];

  const pct = Math.round(confidence * 100);
  const isInconclusive = !selectedHyp || pct === 0;
  const confColor = pct >= 80 ? "#4ade80" : pct >= 60 ? "#fbbf24" : "#fb7185";

  return (
    <section className="evidence-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 4: RCA / CROSS-EXAMINATION</p>
          <h3>
            Root Cause Analysis
            {!isInconclusive && (
              <span style={{ color: "#4ade80", fontSize: 14, marginLeft: 12 }}>
                ✓ {pct}% Confidence
              </span>
            )}
          </h3>
        </div>
        <button className="view-all" onClick={onRunRca || onRetry} style={{ fontSize: 10 }}>
          Re-analyze ↺
        </button>
      </div>

      {/* 1. ROOT CAUSE VERDICT */}
      <div className={"rca-verdict-card" + (isInconclusive ? " rca-verdict-inconclusive" : "")}>
        <div className="rca-verdict-eyebrow">ROOT CAUSE VERDICT</div>
        {isInconclusive ? (
          <div className="rca-inconclusive-msg">
            <span style={{ fontSize: 22 }}>⚠</span>
            <p>Insufficient evidence for a defensible root-cause verdict. RCA inconclusive — insufficient evidence.</p>
          </div>
        ) : (
          <>
            <p className="rca-root-cause-statement">{root_cause_statement}</p>
            <div className="rca-conf-block">
              <div>
                <div className="rca-conf-label">RCA CONFIDENCE</div>
                <div className="rca-conf-pct" style={{ color: confColor }}>{pct}%</div>
                <div className="rca-conf-sub">Evidence-backed</div>
              </div>
              <div className="rca-conf-bar-container">
                <ConfidenceBar value={confidence} />
                <div style={{ fontSize: 9, color: "#6b7280", marginTop: 4 }}>Source: Backend Evidence Graph</div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* 2. SELECTED HYPOTHESIS */}
      {selectedHyp && (
        <div className="rca-block">
          <div className="rca-block-header">
            <span className="group-indicator telemetry" />
            SELECTED HYPOTHESIS
          </div>
          <div className="rca-hypothesis-card rca-hypothesis-selected" style={{ borderColor: "#8b5cf6" }}>
            <span className="rca-selected-flag">★ LEADING HYPOTHESIS</span>
            <div className="rca-hypothesis-header">
              <div>
                <div className="rca-hypothesis-title">{selectedHyp.title}</div>
                <div className="rca-hypothesis-id">{selectedHyp.hypothesis_id}</div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                <StatusBadge status={selectedHyp.status} />
                <span className="rca-conf-value" style={{ color: "#4ade80" }}>
                  {Math.round((selectedHyp.confidence || 0) * 100)}%
                </span>
              </div>
            </div>
            <ConfidenceBar value={selectedHyp.confidence} />
            <p className="rca-hypothesis-desc">{selectedHyp.description}</p>
          </div>
        </div>
      )}

      {/* 3. CROSS-EXAMINATION: ALL HYPOTHESES */}
      {hypotheses.length > 0 && (
        <div className="rca-block">
          <div className="rca-block-header">
            <span className="group-indicator memory" />
            CROSS-EXAMINATION ENGINE · {hypotheses.length} HYPOTHESES EVALUATED
          </div>
          <div className="rca-hypotheses-grid">
            {hypotheses.map((hyp) => (
              <HypothesisCard
                key={hyp.hypothesis_id}
                hyp={hyp}
                isSelected={selectedHyp && hyp.hypothesis_id === selectedHyp.hypothesis_id}
              />
            ))}
          </div>
        </div>
      )}

      {/* 4. SUPPORTING EVIDENCE */}
      {selectedHyp && (
        <div className="rca-block">
          <div className="rca-block-header">
            <span className="group-indicator github" />
            SUPPORTING EVIDENCE · {selectedHyp.supporting_evidence ? selectedHyp.supporting_evidence.length : 0} REFERENCES
          </div>
          {selectedHyp.supporting_evidence && selectedHyp.supporting_evidence.length > 0 ? (
            <div className="rca-evidence-list">
              {selectedHyp.supporting_evidence.map((evRef, idx) => (
                <EvidenceRefItem key={"supp-" + idx} evRef={evRef} accent="#4ade80" />
              ))}
            </div>
          ) : (
            <div className="incident-card empty-card" style={{ padding: "14px 18px" }}>
              <p>No supporting evidence references in the current Evidence Graph.</p>
            </div>
          )}
        </div>
      )}

      {/* 5. CONTRADICTING EVIDENCE */}
      {selectedHyp && (
        <div className="rca-block">
          <div className="rca-block-header">
            <span className="group-indicator" style={{ background: "#fb7185" }} />
            CONTRADICTING EVIDENCE · {selectedHyp.contradicting_evidence ? selectedHyp.contradicting_evidence.length : 0} REFERENCES
          </div>
          {selectedHyp.contradicting_evidence && selectedHyp.contradicting_evidence.length > 0 ? (
            <div className="rca-evidence-list">
              {selectedHyp.contradicting_evidence.map((evRef, idx) => (
                <EvidenceRefItem key={"contra-" + idx} evRef={evRef} accent="#fb7185" />
              ))}
            </div>
          ) : (
            <div className="rca-no-contra">
              No contradicting evidence found in the current Evidence Graph.
            </div>
          )}
        </div>
      )}

      {/* 6. PROOF */}
      {proof.length > 0 && (
        <div className="rca-block">
          <div className="rca-block-header">
            <span className="group-indicator telemetry" />
            PROOF · ROOT CAUSE GROUNDED IN {proof.length} GRAPH NODE{proof.length !== 1 ? "S" : ""}
          </div>
          <div className="rca-evidence-list">
            {proof.map((p, idx) => (
              <EvidenceRefItem key={"proof-" + idx} evRef={p} accent="#38bdf8" />
            ))}
          </div>
        </div>
      )}

      {/* 7. LIMITATIONS */}
      {limitations.length > 0 && (
        <div className="rca-block">
          <div className="rca-block-header">
            <span className="group-indicator" style={{ background: "#fbbf24" }} />
            EVIDENCE BOUNDARIES · {limitations.length} LIMITATION{limitations.length !== 1 ? "S" : ""}
          </div>
          <div className="rca-limitations-list">
            {limitations.map((lim, idx) => (
              <div key={idx} className="rca-limitation-item">
                <span className="rca-limitation-icon">◦</span>
                <span>{lim}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
