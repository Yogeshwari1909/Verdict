import { useState } from "react";

/* ─────────────────────────────────────────────────────────────
   HumanApprovalView.jsx
   Stage 7: Human Approval Gate
   Interacts with GET/POST /api/v1/incidents/{id}/approval.
   Proposals only — Human authorization required before PR creation.
   Zero mock data — strictly reflects backend persisted approval state.
   ───────────────────────────────────────────────────────────── */

const STRATEGY_CONFIG = {
  minimal: {
    color: "#4ade80",
    bg: "#0f2218",
    border: "#166534",
    label: "MINIMAL",
  },
  defensive: {
    color: "#38bdf8",
    bg: "#0c1f2e",
    border: "#1e4060",
    label: "DEFENSIVE",
  },
  structural: {
    color: "#c084fc",
    bg: "#1a0e2e",
    border: "#4c1d95",
    label: "STRUCTURAL",
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
    }
  );
}

function getRiskConfig(risk) {
  return RISK_CONFIG[(risk || "").toLowerCase()] || RISK_CONFIG.medium;
}

export default function HumanApprovalView({
  incidentId,
  service,
  environment,
  fixesData,
  approvalData,
  loading,
  submitting,
  error,
  fixesComplete,
  onSubmitApproval,
  onRefresh,
}) {
  const candidateFixes = fixesData?.candidate_fixes || [];
  const recommendedFix = fixesData?.recommended_fix;

  // Selected candidate fix for review/decision
  const [selectedFixId, setSelectedFixId] = useState(null);
  const [reviewerInput, setReviewerInput] = useState("");
  const [validationError, setValidationError] = useState(null);

  // ── GUARD: Candidate fixes must be generated first ─────────────────────────
  if (!fixesComplete) {
    return (
      <section className="evidence-section approval-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 7: HUMAN APPROVAL GATE</p>
            <h3>Human Approval</h3>
            <p className="fixes-header-subhead">
              Review and authorize the evidence-backed remediation before validation and PR creation.
            </p>
          </div>
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>Candidate Fixes Required</h3>
          <p>
            Generate 3 Candidate Fixes (Stage 6) before reviewing Human Approval.
            Human authorization requires evaluated candidate strategies and validation plans.
          </p>
        </div>
      </section>
    );
  }

  // ── LOADING STATE ──────────────────────────────────────────────────────────
  if (loading && !approvalData) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 7: HUMAN APPROVAL GATE</p>
            <h3>Human Approval</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <p>Loading approval status from backend...</p>
        </div>
      </section>
    );
  }

  const approvalStatus = approvalData?.status || "pending";
  const isApproved = approvalStatus === "approved";
  const isRejected = approvalStatus === "rejected";
  const isDecided = isApproved || isRejected;

  // Determine active fix: if decided, show the approved/rejected fix; else user selection
  const decidedFixId = approvalData?.fix_id;
  const currentSelectedFixId = isDecided
    ? decidedFixId
    : selectedFixId || recommendedFix?.fix_id || candidateFixes[0]?.fix_id;

  const activeFix =
    candidateFixes.find((f) => f.fix_id === currentSelectedFixId) ||
    (recommendedFix?.fix_id === currentSelectedFixId ? recommendedFix : null) ||
    candidateFixes[0];

  const handleAction = (action) => {
    setValidationError(null);

    const reviewer = reviewerInput.trim();
    if (!reviewer) {
      setValidationError("Reviewer / Engineer identity is required to authorize this decision.");
      return;
    }

    if (!currentSelectedFixId) {
      setValidationError("Please select a candidate fix to approve or reject.");
      return;
    }

    onSubmitApproval({
      fix_id: currentSelectedFixId,
      action: action,
      approved_by: reviewer,
    });
  };

  return (
    <section className="evidence-section">
      {/* ── 1. HEADER ── */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 7: HUMAN APPROVAL GATE</p>
          <h3>
            Human Approval
            {isApproved && (
              <span style={{ color: "#4ade80", fontSize: 14, marginLeft: 10 }}>
                ✓ Authorized
              </span>
            )}
            {isRejected && (
              <span style={{ color: "#fb7185", fontSize: 14, marginLeft: 10 }}>
                ✕ Rejected
              </span>
            )}
            {!isDecided && (
              <span style={{ color: "#fbbf24", fontSize: 14, marginLeft: 10 }}>
                ● Awaiting Decision
              </span>
            )}
          </h3>
          <p className="fixes-header-subhead">
            Review and authorize the evidence-backed remediation before validation and PR creation.
          </p>
        </div>
        <div className="fixes-header-right">
          {incidentId && (
            <span className="fixes-incident-context-badge">
              Incident #{incidentId} {service ? `· ${service}` : ""} {environment ? `(${environment})` : ""}
            </span>
          )}
          {onRefresh && (
            <button
              className="view-all"
              onClick={onRefresh}
              style={{ fontSize: 10, marginLeft: 8 }}
            >
              Refresh ↺
            </button>
          )}
        </div>
      </div>

      {/* ── ERROR BANNER ── */}
      {error && (
        <div className="error-banner" style={{ marginBottom: 16 }}>
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* ── 2. SAFETY WARNING / HUMAN-IN-THE-LOOP REQUIREMENT ── */}
      <div
        className="fixes-safety-notice"
        style={{
          borderLeftColor: isApproved
            ? "#4ade80"
            : isRejected
            ? "#fb7185"
            : "#fbbf24",
        }}
      >
        <span className="fixes-safety-icon">
          {isApproved ? "🛡✓" : isRejected ? "🛡✕" : "⚠️"}
        </span>
        <div>
          <strong>
            {isApproved
              ? "Human Authorization Recorded — Regression Sentinel Unlocked"
              : isRejected
              ? "Human Rejection Recorded — Pipeline Halted"
              : "HUMAN DECISION REQUIRED — SAFETY CHECKPOINT"}
          </strong>
          <p>
            {isApproved
              ? `Fix '${approvalData.fix_id}' was explicitly authorized by ${approvalData.approved_by}. Validation in Regression Sentinel is now permitted.`
              : isRejected
              ? `Fix '${approvalData.fix_id}' was rejected by ${approvalData.approved_by}. Source code modifications and PR creation remain blocked.`
              : "Verdict will not modify source code, run regression tests, or create a GitHub PR without explicit human authorization. Select a candidate fix and record your engineering decision."}
          </p>
        </div>
      </div>

      {/* ── 3. APPROVAL STATUS CARD ── */}
      <div className="approval-status-card">
        <div className="approval-status-header">
          <span className="approval-section-title">APPROVAL STATUS</span>
          {isApproved && (
            <span className="approval-badge approved">
              ✓ APPROVED
            </span>
          )}
          {isRejected && (
            <span className="approval-badge rejected">
              ✕ REJECTED
            </span>
          )}
          {!isDecided && (
            <span className="approval-badge pending">
              ● PENDING HUMAN REVIEW
            </span>
          )}
        </div>

        {isDecided ? (
          <div className="approval-details-grid">
            <div>
              <span className="approval-detail-label">DECISION STATUS</span>
              <strong style={{ color: isApproved ? "#4ade80" : "#fb7185" }}>
                {approvalStatus.toUpperCase()}
              </strong>
            </div>
            <div>
              <span className="approval-detail-label">TARGET FIX ID</span>
              <code>{approvalData.fix_id}</code>
            </div>
            <div>
              <span className="approval-detail-label">REVIEWER / ENGINEER</span>
              <strong>{approvalData.approved_by || "Unknown"}</strong>
            </div>
            <div>
              <span className="approval-detail-label">DECISION TIMESTAMP</span>
              <strong>
                {approvalData.approved_at
                  ? approvalData.approved_at.slice(0, 19)
                  : approvalData.created_at
                  ? approvalData.created_at.slice(0, 19)
                  : "Recorded"}
              </strong>
            </div>
          </div>
        ) : (
          <div className="approval-pending-msg">
            <p>
              Awaiting engineer decision. Review the candidate fixes below, enter your reviewer email/handle, and click <strong>Approve Fix</strong> or <strong>Reject Fix</strong>.
            </p>
          </div>
        )}
      </div>

      {/* ── 4. CANDIDATE FIX SELECTION TABS ── */}
      <div className="fixes-block">
        <div className="fixes-block-header">
          <span className="group-indicator memory" />
          SELECT FIX FOR AUTHORIZATION · {candidateFixes.length} CANDIDATES
        </div>

        <div className="approval-fix-selector">
          {candidateFixes.map((fix) => {
            const strCfg = getStrategyConfig(fix.strategy);
            const isSelected = fix.fix_id === currentSelectedFixId;
            const isRec = recommendedFix && fix.fix_id === recommendedFix.fix_id;

            return (
              <button
                key={fix.fix_id}
                type="button"
                className={`approval-fix-tab ${isSelected ? "selected" : ""}`}
                style={{
                  borderColor: isSelected
                    ? "#8b5cf6"
                    : isRec
                    ? "#7c3aed"
                    : "#232836",
                }}
                onClick={() => {
                  if (!isDecided) {
                    setSelectedFixId(fix.fix_id);
                  }
                }}
                disabled={isDecided}
              >
                <div className="approval-tab-top">
                  <span
                    className="fix-strategy-badge"
                    style={{
                      color: strCfg.color,
                      background: strCfg.bg,
                      borderColor: strCfg.border,
                    }}
                  >
                    {strCfg.label}
                  </span>
                  {isRec && (
                    <span className="approval-rec-tag">★ RECOMMENDED</span>
                  )}
                </div>
                <strong className="approval-tab-title">{fix.title}</strong>
                <span className="approval-tab-meta">
                  Risk: {fix.risk_level.toUpperCase()} · Score: {fix.rank_score}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 5. REVIEW SUMMARY CARD ── */}
      {activeFix && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator telemetry" />
            REVIEW SUMMARY · {activeFix.title} ({activeFix.fix_id})
          </div>

          <div className="approval-review-card">
            <div className="approval-review-header">
              <div>
                <span className="fixes-inspector-sub">PROPOSED REMEDIATION</span>
                <h4>{activeFix.title}</h4>
                <code className="approval-fix-id-code">{activeFix.fix_id}</code>
              </div>
              <div className="fix-card-badges">
                <span
                  className="fix-strategy-badge"
                  style={{
                    color: getStrategyConfig(activeFix.strategy).color,
                    background: getStrategyConfig(activeFix.strategy).bg,
                    borderColor: getStrategyConfig(activeFix.strategy).border,
                  }}
                >
                  {getStrategyConfig(activeFix.strategy).label}
                </span>
                <span
                  className="fix-risk-badge"
                  style={{
                    color: getRiskConfig(activeFix.risk_level).color,
                    background: getRiskConfig(activeFix.risk_level).bg,
                    borderColor: getRiskConfig(activeFix.risk_level).border,
                  }}
                >
                  {getRiskConfig(activeFix.risk_level).label}
                </span>
                <span className="fix-rank-badge">
                  Rank Score: <strong>{activeFix.rank_score}</strong>
                </span>
              </div>
            </div>

            <p className="fix-description" style={{ marginTop: 10 }}>
              {activeFix.description}
            </p>

            <div className="fix-section" style={{ marginTop: 10 }}>
              <div className="fix-section-label">RATIONALE</div>
              <p className="fix-section-text">{activeFix.rationale}</p>
            </div>

            {/* Affected files & functions */}
            <div className="fix-affected-block" style={{ marginTop: 12 }}>
              {activeFix.affected_files?.length > 0 && (
                <div className="fix-affected-section">
                  <div className="fix-affected-label">AFFECTED FILES</div>
                  <div className="fix-code-tags">
                    {activeFix.affected_files.map((f, i) => (
                      <code key={i} className="fix-affected-code">
                        📄 {f}
                      </code>
                    ))}
                  </div>
                </div>
              )}
              {activeFix.affected_functions?.length > 0 && (
                <div className="fix-affected-section">
                  <div className="fix-affected-label">AFFECTED FUNCTIONS</div>
                  <div className="fix-code-tags">
                    {activeFix.affected_functions.map((fn, i) => (
                      <code key={i} className="fix-affected-code">
                        ƒ {fn}
                      </code>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Validation Plan Checklist */}
            {activeFix.validation_plan?.length > 0 && (
              <div className="fix-section" style={{ marginTop: 14 }}>
                <div className="fix-section-label">
                  VALIDATION PLAN TO BE EXECUTED IN REGRESSION SENTINEL ({activeFix.validation_plan.length} STEPS)
                </div>
                <ol className="fix-validation-list">
                  {activeFix.validation_plan.map((step, idx) => (
                    <li key={idx} className="fix-validation-item">
                      <span className="fix-validation-num">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <span className="fix-validation-text">{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── 6. REVIEWER INPUT & DECISION ACTIONS ── */}
      <div className="approval-action-card">
        {isDecided ? (
          <div className="approval-decided-banner">
            <strong>Decision already recorded for this incident.</strong>
            <p>
              Status: <strong>{approvalStatus.toUpperCase()}</strong> by{" "}
              <strong>{approvalData.approved_by}</strong> on{" "}
              {approvalData.approved_at || approvalData.created_at || "recently"}. Conflicting modifications are blocked by safety policy.
            </p>
          </div>
        ) : (
          <>
            <div className="approval-reviewer-input-group">
              <label htmlFor="reviewer-input">
                REVIEWER / AUTHORIZING ENGINEER <span style={{ color: "#fb7185" }}>*</span>
              </label>
              <input
                id="reviewer-input"
                type="text"
                className="approval-reviewer-input"
                placeholder="engineer@company.com"
                value={reviewerInput}
                onChange={(e) => {
                  setReviewerInput(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                disabled={submitting}
              />
              <span className="approval-reviewer-help">
                Explicit engineer identification is required to satisfy Verdict audit trail & compliance requirements.
              </span>
            </div>

            {validationError && (
              <div className="approval-validation-error">
                ⚠️ {validationError}
              </div>
            )}

            <div className="approval-actions-row">
              <button
                type="button"
                className="btn-reject"
                onClick={() => handleAction("reject")}
                disabled={submitting}
              >
                {submitting ? "Submitting..." : "✕ Reject Fix"}
              </button>

              <button
                type="button"
                className="btn-approve"
                onClick={() => handleAction("approve")}
                disabled={submitting}
              >
                {submitting
                  ? "Submitting Decision..."
                  : `✓ Authorize & Approve '${activeFix?.fix_id || "Fix"}' →`}
              </button>
            </div>
          </>
        )}
      </div>

      {/* ── 7. NEXT PIPELINE STAGE CALLOUT ── */}
      <div className="fixes-next-stage-callout" style={{ marginTop: 20 }}>
        <div className="fixes-next-stage-header">
          <div
            className="fixes-next-stage-badge"
            style={{
              color: isApproved ? "#4ade80" : isRejected ? "#fb7185" : "#fbbf24",
              background: isApproved ? "#0f2218" : isRejected ? "#250d13" : "#1f1708",
              borderColor: isApproved ? "#166534" : isRejected ? "#7f1d1d" : "#78350f",
            }}
          >
            Stage 7: {isApproved ? "✓ APPROVED" : isRejected ? "✕ REJECTED" : "● PENDING APPROVAL"}
          </div>
          <div className="fixes-next-stage-arrow">→</div>
          <div
            className={`fixes-next-stage-badge ${isApproved ? "next" : ""}`}
            style={{
              opacity: isApproved ? 1 : 0.5,
            }}
          >
            Stage 8: {isApproved ? "NEXT STEP → REGRESSION SENTINEL" : "REGRESSION SENTINEL (LOCKED)"}
          </div>
        </div>
        <p className="fixes-next-stage-desc">
          {isApproved
            ? "Human approval successfully granted. Regression Sentinel validation is now authorized to run positive controls and boundary checks."
            : isRejected
            ? "Fix rejected. The pipeline is halted. Regression Sentinel and GitHub PR creation are safely blocked."
            : "Awaiting human authorization. Regression Sentinel (Stage 8) remains strictly locked until an engineer approves a candidate fix."}
        </p>
      </div>
    </section>
  );
}
