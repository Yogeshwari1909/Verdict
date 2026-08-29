/* ─────────────────────────────────────────────────────────────
   CandidateFixesView.jsx
   Stage 6: Candidate Fixes & Validation Planning
   Renders the deterministic output of POST /api/v1/incidents/{id}/fixes.
   Proposals only — no source code is modified.
   Zero mock data — every value originates from the backend.
   ───────────────────────────────────────────────────────────── */

const STRATEGY_CONFIG = {
  minimal:    { color: "#4ade80",  bg: "#0f2218", border: "#166534", label: "MINIMAL",    tagline: "Smallest change surface" },
  defensive:  { color: "#38bdf8",  bg: "#0c1f2e", border: "#1e4060", label: "DEFENSIVE",  tagline: "Boundary validation & protection" },
  structural: { color: "#c084fc",  bg: "#1a0e2e", border: "#4c1d95", label: "STRUCTURAL", tagline: "Architectural enforcement" },
};

const RISK_CONFIG = {
  low:    { color: "#4ade80", bg: "#0f2218", border: "#166534", label: "LOW RISK"    },
  medium: { color: "#fbbf24", bg: "#1f1708", border: "#78350f", label: "MEDIUM RISK" },
  high:   { color: "#fb7185", bg: "#250d13", border: "#7f1d1d", label: "HIGH RISK"   },
};

function getStrategyConfig(strategy) {
  return STRATEGY_CONFIG[(strategy || "").toLowerCase()] || { color: "#9ca3af", bg: "#111318", border: "#232836", label: (strategy || "UNKNOWN").toUpperCase(), tagline: "" };
}

function getRiskConfig(risk) {
  return RISK_CONFIG[(risk || "").toLowerCase()] || RISK_CONFIG.medium;
}

function StrategyBadge({ strategy }) {
  const cfg = getStrategyConfig(strategy);
  return (
    <span className="fix-strategy-badge" style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}>
      {cfg.label}
    </span>
  );
}

function RiskBadge({ risk }) {
  const cfg = getRiskConfig(risk);
  return (
    <span className="fix-risk-badge" style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}>
      {cfg.label}
    </span>
  );
}

function EvidenceItem({ evRef }) {
  return (
    <div className="fix-evidence-item">
      <div className="fix-evidence-meta">
        {evRef.node_id != null && <span className="fix-evidence-id">#{evRef.node_id}</span>}
        <span className="fix-evidence-type">{evRef.node_type}</span>
        <span className="fix-evidence-label">{evRef.label}</span>
      </div>
      <p className="fix-evidence-reason">{evRef.reason}</p>
    </div>
  );
}

function ValidationChecklist({ steps }) {
  if (!steps || steps.length === 0) return null;
  return (
    <ol className="fix-validation-list">
      {steps.map((step, idx) => (
        <li key={idx} className="fix-validation-item">
          <span className="fix-validation-num">{idx + 1}</span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
}

function AffectedEntities({ files, functions }) {
  const hasFiles = files && files.length > 0;
  const hasFunctions = functions && functions.length > 0;
  if (!hasFiles && !hasFunctions) return null;
  return (
    <div className="fix-affected-block">
      {hasFiles && (
        <div className="fix-affected-section">
          <div className="fix-affected-label">AFFECTED FILES</div>
          {files.map((f, i) => (
            <code key={i} className="fix-affected-code">{f}</code>
          ))}
        </div>
      )}
      {hasFunctions && (
        <div className="fix-affected-section">
          <div className="fix-affected-label">AFFECTED FUNCTIONS</div>
          {functions.map((fn, i) => (
            <code key={i} className="fix-affected-code">{fn}</code>
          ))}
        </div>
      )}
    </div>
  );
}

function FixCard({ fix, isRecommended }) {
  const strCfg = getStrategyConfig(fix.strategy);
  const riskCfg = getRiskConfig(fix.risk_level);

  return (
    <div
      className={"fix-card" + (isRecommended ? " fix-card-recommended" : "")}
      style={{ borderColor: isRecommended ? "#8b5cf6" : strCfg.border }}
    >
      {/* Recommended banner */}
      {isRecommended && (
        <div className="fix-recommended-banner">
          ✓ BACKEND RECOMMENDATION
        </div>
      )}

      {/* Header row */}
      <div className="fix-card-header">
        <div className="fix-card-title-block">
          <div className="fix-card-title">{fix.title}</div>
          <div className="fix-card-id">{fix.fix_id}</div>
        </div>
        <div className="fix-card-badges">
          <StrategyBadge strategy={fix.strategy} />
          <RiskBadge risk={fix.risk_level} />
          <span className="fix-rank-badge">
            Rank: {typeof fix.rank_score === "number" ? fix.rank_score.toFixed(1) : fix.rank_score}
          </span>
        </div>
      </div>

      {/* Strategy tagline */}
      {strCfg.tagline && (
        <div className="fix-strategy-tagline" style={{ color: strCfg.color }}>
          {strCfg.tagline}
        </div>
      )}

      {/* Description */}
      <p className="fix-description">{fix.description}</p>

      {/* Rationale */}
      <div className="fix-section">
        <div className="fix-section-label">RATIONALE</div>
        <p className="fix-section-text">{fix.rationale}</p>
      </div>

      {/* Affected files + functions */}
      <AffectedEntities files={fix.affected_files} functions={fix.affected_functions} />

      {/* Validation plan */}
      {fix.validation_plan && fix.validation_plan.length > 0 && (
        <div className="fix-section">
          <div className="fix-section-label">VALIDATION PLAN</div>
          <ValidationChecklist steps={fix.validation_plan} />
          <div className="fix-validation-notice">
            Proposal only — validation must pass before PR creation.
          </div>
        </div>
      )}

      {/* Supporting evidence */}
      {fix.supporting_evidence && fix.supporting_evidence.length > 0 && (
        <div className="fix-section">
          <div className="fix-section-label">
            EVIDENCE SUPPORT · {fix.supporting_evidence.length} REFERENCE{fix.supporting_evidence.length !== 1 ? "S" : ""}
          </div>
          <div className="fix-evidence-list">
            {fix.supporting_evidence.map((evRef, idx) => (
              <EvidenceItem key={idx} evRef={evRef} />
            ))}
          </div>
        </div>
      )}

      {/* Limitations */}
      {fix.limitations && fix.limitations.length > 0 && (
        <div className="fix-section">
          <div className="fix-section-label">TRADE-OFFS / LIMITATIONS</div>
          {fix.limitations.map((lim, idx) => (
            <div key={idx} className="fix-limitation-item">
              <span className="fix-limitation-icon">◦</span>
              <span>{lim}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function CandidateFixesView({
  fixesData,
  loading,
  generating,
  error,
  impactComplete,
  onGenerate,
  onRetry,
}) {
  // ── GUARD: impact analysis must be done first ─────────────────────────────
  if (!impactComplete) {
    return (
      <section className="evidence-section fixes-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>3 Candidate Fixes</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>Impact Analysis Required</h3>
          <p>
            Complete Blast Radius / Impact Analysis (Stage 5) before generating
            candidate fixes. Fix proposals are grounded in the impact scope and
            RCA evidence — they cannot be generated without them.
          </p>
        </div>
      </section>
    );
  }

  // ── ERROR ─────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>3 Candidate Fixes</h3>
          </div>
        </div>
        <div className="error-banner">
          <span>⚠️ {error}</span>
          {onRetry && (
            <button className="view-all" onClick={onRetry} style={{ color: "#fb7185" }}>
              Retry
            </button>
          )}
        </div>
      </section>
    );
  }

  // ── PRE-GENERATION: impact done, fixes not yet requested ─────────────────
  if (!fixesData && !generating && !loading) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>3 Candidate Fixes</h3>
          </div>
        </div>

        {/* Safety notice */}
        <div className="fixes-safety-notice">
          <span className="fixes-safety-icon">🛡</span>
          <div>
            <strong>Proposals Only — No Code Has Been Modified</strong>
            <p>
              Candidate fixes are evidence-grounded proposals. No source code has
              been edited, no commits created, and no PRs opened. Human approval
              and Regression Sentinel validation are required before any GitHub PR.
            </p>
          </div>
        </div>

        <div className="workspace-action-bar" style={{ marginTop: 0 }}>
          <div className="action-description">
            <strong>Ready to Generate Candidate Fixes</strong>
            <p>
              The backend will generate exactly 3 evidence-grounded fix proposals
              (Minimal · Defensive · Structural) ranked deterministically from the
              RCA and blast-radius analysis.
            </p>
          </div>
          <button className="investigate-button" onClick={onGenerate}>
            Generate Candidate Fixes →
          </button>
        </div>
      </section>
    );
  }

  // ── GENERATING / LOADING ──────────────────────────────────────────────────
  if (generating || (loading && !fixesData)) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>Generating Candidate Fixes...</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <p>Running evidence-grounded fix generation engine...</p>
        </div>
      </section>
    );
  }

  // ── SUCCESS: render full result ───────────────────────────────────────────
  if (!fixesData) return null;

  const {
    root_cause,
    candidate_fixes = [],
    recommended_fix,
    limitations = [],
  } = fixesData;

  const hasNoFixes = candidate_fixes.length === 0;

  if (hasNoFixes) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>3 Candidate Fixes</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <h3>Insufficient Evidence for Fix Generation</h3>
          <p>
            The backend was unable to generate grounded candidate fixes due to
            insufficient RCA evidence or missing source file scope.
          </p>
          {limitations.map((lim, i) => (
            <p key={i} style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>◦ {lim}</p>
          ))}
          <button className="investigate-button" style={{ marginTop: 14 }} onClick={onRetry || onGenerate}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="evidence-section">
      {/* ── Header ── */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
          <h3>
            3 Candidate Fixes Generated ✓
          </h3>
        </div>
        <button className="view-all" onClick={onGenerate || onRetry} style={{ fontSize: 10 }}>
          Regenerate ↺
        </button>
      </div>

      {/* ── Safety Notice ── */}
      <div className="fixes-safety-notice">
        <span className="fixes-safety-icon">🛡</span>
        <div>
          <strong>Candidate fixes are proposals only. No source code has been modified.</strong>
          <p>
            Human approval and Regression Sentinel validation are required before any
            code change or GitHub PR is created.
          </p>
        </div>
      </div>

      {/* ── Root Cause Reference ── */}
      {root_cause && (
        <div className="fixes-root-cause-ref">
          <div className="fixes-root-cause-label">FIXING ROOT CAUSE</div>
          <p className="fixes-root-cause-text">{root_cause}</p>
        </div>
      )}

      {/* ── RECOMMENDED FIX (most prominent) ── */}
      {recommended_fix && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator telemetry" />
            RECOMMENDED FIX · BACKEND SELECTION
          </div>
          <FixCard fix={recommended_fix} isRecommended={true} />
        </div>
      )}

      {/* ── ALL 3 CANDIDATE FIXES ── */}
      <div className="fixes-block">
        <div className="fixes-block-header">
          <span className="group-indicator memory" />
          ALL CANDIDATE FIXES · {candidate_fixes.length} PROPOSALS (RANKED)
        </div>
        <div className="fixes-grid">
          {candidate_fixes.map((fix) => (
            <FixCard
              key={fix.fix_id}
              fix={fix}
              isRecommended={recommended_fix && fix.fix_id === recommended_fix.fix_id}
            />
          ))}
        </div>
      </div>

      {/* ── Global limitations ── */}
      {limitations.length > 0 && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator" style={{ background: "#fbbf24" }} />
            FIX ENGINE BOUNDARIES · {limitations.length} NOTE{limitations.length !== 1 ? "S" : ""}
          </div>
          <div className="fixes-limitations-list">
            {limitations.map((lim, idx) => (
              <div key={idx} className="fix-limitation-item" style={{ marginBottom: 6 }}>
                <span className="fix-limitation-icon">◦</span>
                <span>{lim}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
