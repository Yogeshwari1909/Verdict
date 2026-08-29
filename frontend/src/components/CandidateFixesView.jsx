import { useState } from "react";

/* ─────────────────────────────────────────────────────────────
   CandidateFixesView.jsx
   Stage 6: Candidate Fixes & Validation Planning
   Renders the deterministic output of POST /api/v1/incidents/{id}/fixes.
   Proposals only — no source code is modified.
   Zero mock data — every value originates from the backend.
   ───────────────────────────────────────────────────────────── */

const STRATEGY_CONFIG = {
  minimal: {
    color: "#4ade80",
    bg: "#0f2218",
    border: "#166534",
    label: "MINIMAL",
    tagline: "Smallest change surface (Targeted local guard)",
  },
  defensive: {
    color: "#38bdf8",
    bg: "#0c1f2e",
    border: "#1e4060",
    label: "DEFENSIVE",
    tagline: "Boundary validation & request protection",
  },
  structural: {
    color: "#c084fc",
    bg: "#1a0e2e",
    border: "#4c1d95",
    label: "STRUCTURAL",
    tagline: "Architectural schema contract enforcement",
  },
};

const RISK_CONFIG = {
  low: { color: "#4ade80", bg: "#0f2218", border: "#166534", label: "LOW RISK" },
  medium: { color: "#fbbf24", bg: "#1f1708", border: "#78350f", label: "MEDIUM RISK" },
  high: { color: "#fb7185", bg: "#250d13", border: "#7f1d1d", label: "HIGH RISK" },
};

function getStrategyConfig(strategy) {
  return (
    STRATEGY_CONFIG[(strategy || "").toLowerCase()] || {
      color: "#9ca3af",
      bg: "#111318",
      border: "#232836",
      label: (strategy || "UNKNOWN").toUpperCase(),
      tagline: "",
    }
  );
}

function getRiskConfig(risk) {
  return RISK_CONFIG[(risk || "").toLowerCase()] || RISK_CONFIG.medium;
}

function StrategyBadge({ strategy }) {
  const cfg = getStrategyConfig(strategy);
  return (
    <span
      className="fix-strategy-badge"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}
    >
      {cfg.label}
    </span>
  );
}

function RiskBadge({ risk }) {
  const cfg = getRiskConfig(risk);
  return (
    <span
      className="fix-risk-badge"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}
    >
      {cfg.label}
    </span>
  );
}

function RankScoreBadge({ score }) {
  const formatted =
    typeof score === "number"
      ? Number.isInteger(score)
        ? score
        : score.toFixed(1)
      : score;
  return (
    <span className="fix-rank-badge">
      Rank Score: <strong>{formatted}</strong>
    </span>
  );
}

function EvidenceItem({ evRef }) {
  return (
    <div className="fix-evidence-item">
      <div className="fix-evidence-meta">
        {evRef.node_id != null && (
          <span className="fix-evidence-id">Node #{evRef.node_id}</span>
        )}
        <span className="fix-evidence-type">{evRef.node_type}</span>
        <span className="fix-evidence-label">{evRef.label}</span>
      </div>
      {evRef.reason && <p className="fix-evidence-reason">{evRef.reason}</p>}
    </div>
  );
}

function ValidationChecklist({ steps }) {
  if (!steps || steps.length === 0) return null;
  return (
    <ol className="fix-validation-list">
      {steps.map((step, idx) => (
        <li key={idx} className="fix-validation-item">
          <span className="fix-validation-num">
            {String(idx + 1).padStart(2, "0")}
          </span>
          <span className="fix-validation-text">{step}</span>
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
          <div className="fix-code-tags">
            {files.map((f, i) => (
              <code key={i} className="fix-affected-code">
                📄 {f}
              </code>
            ))}
          </div>
        </div>
      )}
      {hasFunctions && (
        <div className="fix-affected-section">
          <div className="fix-affected-label">AFFECTED FUNCTIONS</div>
          <div className="fix-code-tags">
            {functions.map((fn, i) => (
              <code key={i} className="fix-affected-code">
                ƒ {fn}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function FixCard({
  fix,
  isRecommended,
  isSelected,
  onSelect,
  showAllDetails = true,
}) {
  const strCfg = getStrategyConfig(fix.strategy);

  return (
    <div
      className={
        "fix-card" +
        (isRecommended ? " fix-card-recommended" : "") +
        (isSelected ? " fix-card-selected" : "")
      }
      style={{
        borderColor: isSelected
          ? "#8b5cf6"
          : isRecommended
          ? "#7c3aed"
          : strCfg.border,
      }}
      onClick={onSelect}
    >
      {/* Recommended banner */}
      {isRecommended && (
        <div className="fix-recommended-banner">
          ★ RECOMMENDED FIX
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
          <RankScoreBadge score={fix.rank_score} />
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
      <AffectedEntities
        files={fix.affected_files}
        functions={fix.affected_functions}
      />

      {/* Validation plan (Numbered 01, 02, 03) */}
      {showAllDetails && fix.validation_plan && fix.validation_plan.length > 0 && (
        <div className="fix-section">
          <div className="fix-section-label">
            VALIDATION PLAN · {fix.validation_plan.length} STEPS
          </div>
          <ValidationChecklist steps={fix.validation_plan} />
          <div className="fix-validation-notice">
            Proposal only — validation plan must pass in Regression Sentinel before PR merge.
          </div>
        </div>
      )}

      {/* Supporting evidence */}
      {showAllDetails &&
        fix.supporting_evidence &&
        fix.supporting_evidence.length > 0 && (
          <div className="fix-section">
            <div className="fix-section-label">
              SUPPORTING EVIDENCE · {fix.supporting_evidence.length} REFERENCE
              {fix.supporting_evidence.length !== 1 ? "S" : ""}
            </div>
            <div className="fix-evidence-list">
              {fix.supporting_evidence.map((evRef, idx) => (
                <EvidenceItem key={idx} evRef={evRef} />
              ))}
            </div>
          </div>
        )}

      {/* Limitations / Trade-offs */}
      {showAllDetails && fix.limitations && fix.limitations.length > 0 && (
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
  incidentId,
  service,
  rcaData,
  fixesData,
  loading,
  generating,
  error,
  impactComplete,
  onGenerate,
  onRetry,
}) {
  const [selectedFixId, setSelectedFixId] = useState(null);

  // ── GUARD: impact analysis must be done first ─────────────────────────────
  if (!impactComplete) {
    return (
      <section className="evidence-section fixes-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>Candidate Fixes</h3>
            <p className="fixes-header-subhead">
              Three evidence-backed remediation strategies ranked by risk, value and validation coverage.
            </p>
          </div>
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>Impact Analysis Required</h3>
          <p>
            Complete Blast Radius / Impact Analysis (Stage 5) before generating
            candidate fixes. Fix proposals are grounded in the impact scope and
            RCA evidence — they cannot safely be generated without them.
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
            <h3>Candidate Fixes</h3>
            <p className="fixes-header-subhead">
              Three evidence-backed remediation strategies ranked by risk, value and validation coverage.
            </p>
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
            <h3>Candidate Fixes</h3>
            <p className="fixes-header-subhead">
              Three evidence-backed remediation strategies ranked by risk, value and validation coverage.
            </p>
          </div>
          {incidentId && (
            <span className="fixes-incident-context-badge">
              Incident #{incidentId} {service ? `· ${service}` : ""}
            </span>
          )}
        </div>

        {/* Safety notice */}
        <div className="fixes-safety-notice">
          <span className="fixes-safety-icon">🛡</span>
          <div>
            <strong>Candidate Fixes Are Proposals Only — No Source Code Is Automatically Modified</strong>
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
              RCA proof and blast-radius scope.
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
            <p className="fixes-header-subhead">
              Three evidence-backed remediation strategies ranked by risk, value and validation coverage.
            </p>
          </div>
        </div>
        <div className="incident-card empty-card">
          <p>Running deterministic candidate fix & validation planning engine...</p>
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

  const hasNoFixes = candidate_fixes.length === 0 && !recommended_fix;

  if (hasNoFixes) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
            <h3>Candidate Fixes</h3>
            <p className="fixes-header-subhead">
              Three evidence-backed remediation strategies ranked by risk, value and validation coverage.
            </p>
          </div>
        </div>
        <div className="incident-card empty-card">
          <h3>Insufficient Evidence for Fix Generation</h3>
          <p>
            The backend was unable to formulate grounded candidate fixes without
            hallucination due to insufficient RCA evidence or missing source file scope.
          </p>
          {limitations.map((lim, i) => (
            <p key={i} style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
              ◦ {lim}
            </p>
          ))}
          <button
            className="investigate-button"
            style={{ marginTop: 14 }}
            onClick={onRetry || onGenerate}
          >
            Retry
          </button>
        </div>
      </section>
    );
  }

  // Active selected fix resolution
  const effectiveSelectedFixId =
    selectedFixId || recommended_fix?.fix_id || candidate_fixes[0]?.fix_id;

  const activeFix =
    candidate_fixes.find((f) => f.fix_id === effectiveSelectedFixId) ||
    recommended_fix ||
    candidate_fixes[0];

  // Calculate or extract confidence score
  const rcaConfidence =
    rcaData?.confidence != null
      ? rcaData.confidence
      : null;

  return (
    <section className="evidence-section">
      {/* ── 1. SECTION HEADER ── */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 6: CANDIDATE FIXES</p>
          <h3>
            Candidate Fixes
            <span style={{ color: "#4ade80", fontSize: 14, marginLeft: 10 }}>
              ✓ {candidate_fixes.length} Strategies Ranked
            </span>
          </h3>
          <p className="fixes-header-subhead">
            Three evidence-backed remediation strategies ranked by risk, value and validation coverage.
          </p>
        </div>
        <div className="fixes-header-right">
          {incidentId && (
            <span className="fixes-incident-context-badge">
              Incident #{incidentId} {service ? `· ${service}` : ""}
            </span>
          )}
          <button
            className="view-all"
            onClick={onGenerate || onRetry}
            style={{ fontSize: 10, marginLeft: 8 }}
          >
            Regenerate ↺
          </button>
        </div>
      </div>

      {/* ── 2. ROOT CAUSE SUMMARY ── */}
      {root_cause && (
        <div className="fixes-root-cause-ref">
          <div className="fixes-root-cause-header">
            <div className="fixes-root-cause-label">ROOT CAUSE</div>
            {rcaConfidence != null && (
              <span className="fixes-rca-conf-badge">
                RCA Confidence: {Math.round(rcaConfidence * 100)}%
              </span>
            )}
          </div>
          <p className="fixes-root-cause-text">{root_cause}</p>
        </div>
      )}

      {/* ── 3. SAFETY NOTICE & LIMITATIONS BANNER ── */}
      <div className="fixes-safety-notice">
        <span className="fixes-safety-icon">🛡</span>
        <div>
          <strong>Candidate Fixes Are Proposals Only — No Source Code Is Automatically Modified</strong>
          <p>
            Candidate fixes are evidence-grounded proposals. Human approval and
            Regression Sentinel validation are strictly required before any code modification
            or GitHub PR creation.
          </p>
        </div>
      </div>

      {/* ── 4. RECOMMENDED FIX HIGHLIGHT ── */}
      {recommended_fix && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator telemetry" />
            RECOMMENDED FIX · BACKEND DETERMINISTIC SELECTION
          </div>
          <FixCard
            fix={recommended_fix}
            isRecommended={true}
            isSelected={effectiveSelectedFixId === recommended_fix.fix_id}
            onSelect={() => setSelectedFixId(recommended_fix.fix_id)}
            showAllDetails={true}
          />
        </div>
      )}

      {/* ── 5. THREE CANDIDATE FIXES (MINIMAL, DEFENSIVE, STRUCTURAL) ── */}
      <div className="fixes-block">
        <div className="fixes-block-header">
          <span className="group-indicator memory" />
          ALL CANDIDATE FIXES · {candidate_fixes.length} STRATEGIES (RANKED)
        </div>
        <div className="fixes-grid">
          {candidate_fixes.map((fix) => (
            <FixCard
              key={fix.fix_id}
              fix={fix}
              isRecommended={
                recommended_fix && fix.fix_id === recommended_fix.fix_id
              }
              isSelected={effectiveSelectedFixId === fix.fix_id}
              onSelect={() => setSelectedFixId(fix.fix_id)}
              showAllDetails={true}
            />
          ))}
        </div>
      </div>

      {/* ── 6. SELECTED FIX FOCUSED VALIDATION & EVIDENCE INSPECTOR (if inspecting) ── */}
      {activeFix && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator github" />
            INSPECTION FOCUS · {activeFix.title} ({getStrategyConfig(activeFix.strategy).label})
          </div>

          <div className="fixes-inspector-card">
            <div className="fixes-inspector-header">
              <div>
                <span className="fixes-inspector-sub">SELECTED CANDIDATE</span>
                <h4>{activeFix.title}</h4>
              </div>
              <div className="fix-card-badges">
                <StrategyBadge strategy={activeFix.strategy} />
                <RiskBadge risk={activeFix.risk_level} />
                <RankScoreBadge score={activeFix.rank_score} />
              </div>
            </div>

            {/* Validation Plan section */}
            <div className="fix-section" style={{ marginTop: 12 }}>
              <div className="fix-section-label">
                VALIDATION PLAN · {activeFix.validation_plan?.length || 0} NUMBERED STEPS
              </div>
              <ValidationChecklist steps={activeFix.validation_plan} />
            </div>

            {/* Supporting Evidence */}
            {activeFix.supporting_evidence && activeFix.supporting_evidence.length > 0 && (
              <div className="fix-section" style={{ marginTop: 14 }}>
                <div className="fix-section-label">
                  SUPPORTING EVIDENCE · {activeFix.supporting_evidence.length} GRAPH NODE REFERENCES
                </div>
                <div className="fix-evidence-list">
                  {activeFix.supporting_evidence.map((evRef, idx) => (
                    <EvidenceItem key={idx} evRef={evRef} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── 7. FIX ENGINE LIMITATIONS / BOUNDARIES ── */}
      {limitations.length > 0 && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator" style={{ background: "#fbbf24" }} />
            FIX ENGINE LIMITATIONS & SAFETY BOUNDARIES · {limitations.length} NOTES
          </div>
          <div className="fixes-limitations-list">
            {limitations.map((lim, idx) => (
              <div
                key={idx}
                className="fix-limitation-item"
                style={{ marginBottom: 6 }}
              >
                <span className="fix-limitation-icon">◦</span>
                <span>{lim}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 8. NEXT PIPELINE STAGE CALLOUT ── */}
      <div className="fixes-next-stage-callout">
        <div className="fixes-next-stage-header">
          <div className="fixes-next-stage-badge">
            Stage 6: ✓ 3 FIXES COMPLETE
          </div>
          <div className="fixes-next-stage-arrow">→</div>
          <div className="fixes-next-stage-badge next">
            Stage 7: NEXT STEP → HUMAN APPROVAL
          </div>
        </div>
        <p className="fixes-next-stage-desc">
          Candidate fixes have been generated and validated against the Evidence Graph.
          Per Verdict safety principles, <strong>Human Approval is required</strong> before proceeding to Regression Sentinel and GitHub PR creation.
        </p>
      </div>
    </section>
  );
}

