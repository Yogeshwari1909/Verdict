import { useState } from "react";

/* ─────────────────────────────────────────────────────────────
   RegressionSentinelView.jsx
   Stage 8: Regression Sentinel Validation Engine
   Interacts with POST /api/v1/incidents/{id}/regression-check.
   Verifies that the human-approved fix passes all automated
   regression and boundary validation checks before PR creation.
   Zero mock data — strictly reflects backend sentinel execution.
   ───────────────────────────────────────────────────────────── */

const CHECK_STATUS_CONFIG = {
  passed: {
    color: "#4ade80",
    bg: "#0f2218",
    border: "#166534",
    label: "PASSED",
    icon: "✓",
  },
  failed: {
    color: "#fb7185",
    bg: "#250d13",
    border: "#7f1d1d",
    label: "FAILED",
    icon: "✕",
  },
  skipped: {
    color: "#38bdf8",
    bg: "#0c1f2e",
    border: "#1e4060",
    label: "SKIPPED",
    icon: "○",
  },
  inconclusive: {
    color: "#fbbf24",
    bg: "#1f1708",
    border: "#78350f",
    label: "INCONCLUSIVE",
    icon: "⚠",
  },
};

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

function getCheckStatusConfig(status) {
  return (
    CHECK_STATUS_CONFIG[(status || "").toLowerCase()] ||
    CHECK_STATUS_CONFIG.inconclusive
  );
}

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

function CheckStatusBadge({ status }) {
  const cfg = getCheckStatusConfig(status);
  return (
    <span
      className="sentinel-check-badge"
      style={{
        color: cfg.color,
        background: cfg.bg,
        borderColor: cfg.border,
      }}
    >
      <span style={{ marginRight: 4 }}>{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}

function ValidationTypeBadge({ type }) {
  const formatted = (type || "").replace(/_/g, " ").toUpperCase();
  return (
    <span className="sentinel-type-badge">
      {formatted}
    </span>
  );
}

function CheckCard({ check }) {
  const cfg = getCheckStatusConfig(check.status);

  return (
    <div
      className="sentinel-check-card"
      style={{
        borderLeftColor: cfg.color,
      }}
    >
      <div className="sentinel-check-header">
        <div>
          <div className="sentinel-check-title-row">
            <strong className="sentinel-check-name">{check.name}</strong>
            <ValidationTypeBadge type={check.validation_type} />
          </div>
          <span className="sentinel-check-id">{check.check_id}</span>
        </div>
        <CheckStatusBadge status={check.status} />
      </div>

      <p className="sentinel-check-desc">{check.description}</p>

      <div className="sentinel-check-results-grid">
        <div className="sentinel-result-box">
          <span className="sentinel-result-label">EXPECTED BEHAVIOR</span>
          <p className="sentinel-result-text expected">{check.expected_result}</p>
        </div>
        <div className="sentinel-result-box">
          <span className="sentinel-result-label">ACTUAL OBSERVED RESULT</span>
          <p
            className={`sentinel-result-text actual ${
              check.status === "passed"
                ? "passed"
                : check.status === "failed"
                ? "failed"
                : "skipped"
            }`}
          >
            {check.actual_result}
          </p>
        </div>
      </div>

      {check.evidence_reference && (
        <div className="sentinel-check-evidence">
          <span className="sentinel-evidence-label">EVIDENCE TRACE / REQUIREMENT:</span>
          <span className="sentinel-evidence-val">{check.evidence_reference}</span>
        </div>
      )}
    </div>
  );
}

export default function RegressionSentinelView({
  incidentId,
  service,
  environment,
  fixesData,
  approvalData,
  sentinelData,
  running,
  error,
  fixesComplete,
  onRunSentinel,
}) {
  const isApproved = approvalData?.status === "approved";
  const approvedFixId = approvalData?.fix_id;

  // Find the candidate fix matching the approved fix ID
  const candidateFixes = fixesData?.candidate_fixes || [];
  const approvedFix =
    candidateFixes.find((f) => f.fix_id === approvedFixId) ||
    (fixesData?.recommended_fix?.fix_id === approvedFixId
      ? fixesData.recommended_fix
      : null);

  // ── GUARD 1: Fixes must be generated first ──────────────────────────────────
  if (!fixesComplete) {
    return (
      <section className="evidence-section sentinel-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 8: REGRESSION SENTINEL</p>
            <h3>Regression Sentinel</h3>
            <p className="fixes-header-subhead">
              Validate the approved fix against regression and safety checks before GitHub PR creation.
            </p>
          </div>
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>Candidate Fixes Required</h3>
          <p>
            Candidate Fixes (Stage 6) must be formulated and approved before running Regression Sentinel.
          </p>
        </div>
      </section>
    );
  }

  // ── GUARD 2: Human Approval Required (Strict Safety Gate) ───────────────────
  if (!isApproved) {
    return (
      <section className="evidence-section sentinel-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 8: REGRESSION SENTINEL</p>
            <h3>Regression Sentinel</h3>
            <p className="fixes-header-subhead">
              Validate the approved fix against regression and safety checks before GitHub PR creation.
            </p>
          </div>
          {incidentId && (
            <span className="fixes-incident-context-badge">
              Incident #{incidentId} {service ? `· ${service}` : ""}
            </span>
          )}
        </div>
        <div className="incident-card empty-card">
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
          <h3>Human Approval Required</h3>
          <p>
            Regression Sentinel is locked. An authorizing engineer must explicitly approve a candidate fix in Stage 7 (Human Approval Gate) before automated regression checks can be executed.
          </p>
          <div
            style={{
              display: "inline-block",
              background: "#191524",
              border: "1px solid #3b2a59",
              borderRadius: 6,
              padding: "6px 14px",
              fontSize: 11,
              color: "#c4b5fd",
              marginTop: 10,
            }}
          >
            Current Stage 7 Status:{" "}
            <strong style={{ textTransform: "uppercase" }}>
              {approvalData?.status || "PENDING"}
            </strong>
          </div>
        </div>
      </section>
    );
  }

  // ── PRE-RUN STATE: Approved, ready to execute Sentinel ──────────────────────
  if (!sentinelData && !running) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 8: REGRESSION SENTINEL</p>
            <h3>Regression Sentinel</h3>
            <p className="fixes-header-subhead">
              Validate the approved fix against regression and safety checks before GitHub PR creation.
            </p>
          </div>
          <div className="fixes-header-right">
            <span className="sentinel-approved-badge">
              ✓ Fix '{approvedFixId}' Authorized
            </span>
          </div>
        </div>

        {error && (
          <div className="error-banner" style={{ marginBottom: 16 }}>
            <span>⚠️ {error}</span>
            {onRunSentinel && (
              <button
                className="view-all"
                onClick={() => onRunSentinel(approvedFixId)}
                style={{ color: "#fb7185" }}
              >
                Retry Sentinel
              </button>
            )}
          </div>
        )}

        {/* Safety Gate Banner */}
        <div className="fixes-safety-notice" style={{ borderLeftColor: "#38bdf8" }}>
          <span className="fixes-safety-icon">🛡</span>
          <div>
            <strong>REGRESSION GATE — SAFETY CHECKPOINT</strong>
            <p>
              The authorized fix must pass automated baseline, positive control, and boundary checks before a GitHub PR can be prepared. No automatic merge or deployment will occur.
            </p>
          </div>
        </div>

        {/* Approved Fix Summary Card */}
        <div className="sentinel-approved-fix-card">
          <div className="sentinel-approved-fix-header">
            <div>
              <span className="sentinel-approved-sub">TARGET APPROVED FIX</span>
              <h4>{approvedFix?.title || approvedFixId}</h4>
              <code className="approval-fix-id-code">{approvedFixId}</code>
            </div>
            {approvedFix && (
              <div className="fix-card-badges">
                <span
                  className="fix-strategy-badge"
                  style={{
                    color: getStrategyConfig(approvedFix.strategy).color,
                    background: getStrategyConfig(approvedFix.strategy).bg,
                    borderColor: getStrategyConfig(approvedFix.strategy).border,
                  }}
                >
                  {getStrategyConfig(approvedFix.strategy).label}
                </span>
                <span
                  className="fix-risk-badge"
                  style={{
                    color: getRiskConfig(approvedFix.risk_level).color,
                    background: getRiskConfig(approvedFix.risk_level).bg,
                    borderColor: getRiskConfig(approvedFix.risk_level).border,
                  }}
                >
                  {getRiskConfig(approvedFix.risk_level).label}
                </span>
                <span className="fix-rank-badge">
                  Score: <strong>{approvedFix.rank_score}</strong>
                </span>
              </div>
            )}
          </div>

          <p className="fix-description" style={{ marginTop: 8 }}>
            {approvedFix?.description}
          </p>

          <div className="sentinel-approved-meta-row">
            <span>
              Authorized By: <strong>{approvalData.approved_by}</strong>
            </span>
            <span>
              Decision Timestamp: <strong>{approvalData.approved_at?.slice(0, 19) || "Recorded"}</strong>
            </span>
          </div>
        </div>

        <div className="workspace-action-bar" style={{ marginTop: 16 }}>
          <div className="action-description">
            <strong>Ready to Validate Approved Fix</strong>
            <p>
              Execute automated smoke tests, database connectivity baselines, positive controls, and boundary validation schemas against '{approvedFixId}'.
            </p>
          </div>
          <button
            className="investigate-button"
            onClick={() => onRunSentinel(approvedFixId)}
          >
            Run Regression Sentinel →
          </button>
        </div>
      </section>
    );
  }

  // ── RUNNING STATE ──────────────────────────────────────────────────────────
  if (running && !sentinelData) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 8: REGRESSION SENTINEL</p>
            <h3>Running Regression Sentinel...</h3>
            <p className="fixes-header-subhead">
              Executing automated regression checks, smoke tests, and boundary assertions against '{approvedFixId}'...
            </p>
          </div>
        </div>
        <div className="incident-card empty-card">
          <p>Running regression verification engine against backend contracts...</p>
        </div>
      </section>
    );
  }

  // ── RESULTS STATE: Render Executed Checks & Sentinel Verdict ───────────────
  if (!sentinelData) return null;

  const {
    status: overallStatus = "inconclusive",
    safe_to_merge = false,
    checks = [],
    regressions_detected = [],
    validation_summary = "",
    limitations = [],
  } = sentinelData;

  const isPassed = overallStatus === "passed" && safe_to_merge === true;
  const isFailed = overallStatus === "failed" || !safe_to_merge;
  const passedChecksCount = checks.filter((c) => c.status === "passed").length;
  const skippedChecksCount = checks.filter((c) => c.status === "skipped").length;
  const failedChecksCount = checks.filter((c) => c.status === "failed").length;

  return (
    <section className="evidence-section">
      {/* ── 1. HEADER ── */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 8: REGRESSION SENTINEL</p>
          <h3>
            Regression Sentinel
            {isPassed && (
              <span style={{ color: "#4ade80", fontSize: 14, marginLeft: 10 }}>
                ✓ Passed (0 Regressions)
              </span>
            )}
            {isFailed && overallStatus === "failed" && (
              <span style={{ color: "#fb7185", fontSize: 14, marginLeft: 10 }}>
                ✕ Failed ({regressions_detected.length} Regressions)
              </span>
            )}
            {overallStatus === "inconclusive" && (
              <span style={{ color: "#fbbf24", fontSize: 14, marginLeft: 10 }}>
                ⚠ Inconclusive
              </span>
            )}
          </h3>
          <p className="fixes-header-subhead">
            Validate the approved fix against regression and safety checks before GitHub PR creation.
          </p>
        </div>
        <div className="fixes-header-right">
          <span className="sentinel-approved-badge">
            Target: {approvedFixId}
          </span>
          <button
            className="view-all"
            onClick={() => onRunSentinel && onRunSentinel(approvedFixId)}
            style={{ fontSize: 10, marginLeft: 8 }}
          >
            Re-run ↺
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner" style={{ marginBottom: 16 }}>
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* ── 2. OVERALL SENTINEL RESULT VERDICT CARD ── */}
      <div
        className={`sentinel-verdict-card ${
          isPassed ? "passed" : isFailed ? "failed" : "inconclusive"
        }`}
      >
        <div className="sentinel-verdict-header">
          <div>
            <span className="sentinel-verdict-eyebrow">SENTINEL VERDICT</span>
            <div className="sentinel-verdict-title-row">
              <h3>
                {isPassed
                  ? "✓ REGRESSION CHECK PASSED"
                  : overallStatus === "failed"
                  ? "✕ REGRESSION CHECK FAILED"
                  : "⚠ VALIDATION INCONCLUSIVE"}
              </h3>
              {safe_to_merge ? (
                <span className="sentinel-merge-badge safe">
                  ✓ SAFE TO MERGE
                </span>
              ) : (
                <span className="sentinel-merge-badge blocked">
                  ⛔ BLOCKED — NOT SAFE TO MERGE
                </span>
              )}
            </div>
          </div>
          <div className="sentinel-stats-pill">
            <span><strong>{passedChecksCount}</strong> Passed</span>
            <span><strong>{skippedChecksCount}</strong> Skipped</span>
            {failedChecksCount > 0 && (
              <span style={{ color: "#fb7185" }}><strong>{failedChecksCount}</strong> Failed</span>
            )}
          </div>
        </div>

        {/* Validation Summary */}
        <p className="sentinel-summary-text">{validation_summary}</p>

        {/* Detected Regressions */}
        {regressions_detected.length > 0 && (
          <div className="sentinel-regressions-box">
            <span className="sentinel-regressions-label">
              DETECTED REGRESSIONS ({regressions_detected.length}):
            </span>
            <ul className="sentinel-regressions-list">
              {regressions_detected.map((r, i) => (
                <li key={i}>
                  <strong>[{r.severity?.toUpperCase() || "ERROR"}]</strong> Check '{r.check_id}': {r.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ── 3. DETAILED EXECUTED CHECKS ── */}
      <div className="fixes-block">
        <div className="fixes-block-header">
          <span className="group-indicator memory" />
          EXECUTED REGRESSION CHECKS · {checks.length} SUITE ASSERTIONS
        </div>

        <div className="sentinel-checks-list">
          {checks.map((check) => (
            <CheckCard key={check.check_id} check={check} />
          ))}
        </div>
      </div>

      {/* ── 4. LIMITATIONS & TEST BOUNDARIES ── */}
      {limitations.length > 0 && (
        <div className="fixes-block">
          <div className="fixes-block-header">
            <span className="group-indicator" style={{ background: "#fbbf24" }} />
            SENTINEL TEST ENVIRONMENT BOUNDARIES · {limitations.length} NOTES
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

      {/* ── 5. NEXT PIPELINE STAGE CALLOUT ── */}
      <div className="fixes-next-stage-callout" style={{ marginTop: 20 }}>
        <div className="fixes-next-stage-header">
          <div
            className="fixes-next-stage-badge"
            style={{
              color: isPassed ? "#4ade80" : isFailed ? "#fb7185" : "#fbbf24",
              background: isPassed ? "#0f2218" : isFailed ? "#250d13" : "#1f1708",
              borderColor: isPassed ? "#166534" : isFailed ? "#7f1d1d" : "#78350f",
            }}
          >
            Stage 8: {isPassed ? "✓ SENTINEL PASSED" : isFailed ? "✕ SENTINEL FAILED" : "⚠ INCONCLUSIVE"}
          </div>
          <div className="fixes-next-stage-arrow">→</div>
          <div
            className={`fixes-next-stage-badge ${isPassed ? "next" : ""}`}
            style={{
              opacity: isPassed ? 1 : 0.5,
            }}
          >
            Stage 9: {isPassed ? "NEXT STEP → GITHUB PR" : "GITHUB PR (BLOCKED)"}
          </div>
        </div>
        <p className="fixes-next-stage-desc">
          {isPassed
            ? "All regression and boundary assertions passed successfully with 0 regressions detected. Fix is SAFE TO MERGE and ready for GitHub Pull Request generation."
            : isFailed
            ? "Regression Sentinel failed or flagged regressions. GitHub PR creation is blocked until regressions are remediated and approved."
            : "Validation is inconclusive. Complete additional verification before proceeding."}
        </p>
      </div>
    </section>
  );
}
