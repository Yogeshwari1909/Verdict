import { useState } from "react";

/* ─────────────────────────────────────────────────────────────
   GitHubPRView.jsx
   Stage 9: GitHub Pull Request Integration (Final Pipeline Stage)
   Interacts with POST /api/v1/incidents/{id}/github/pr.
   Evidence-backed PR generation strictly gated behind:
   1. Human Approval (Stage 7)
   2. Regression Sentinel passing with safe_to_merge=true (Stage 8)
   Operates in safe DRY-RUN mode by default (github_url=null).
   Zero mock data — strictly reflects backend PR result.
   ───────────────────────────────────────────────────────────── */

const STRATEGY_CONFIG = {
  minimal: { color: "#4ade80", bg: "#0f2218", border: "#166534", label: "MINIMAL" },
  defensive: { color: "#38bdf8", bg: "#0c1f2e", border: "#1e4060", label: "DEFENSIVE" },
  structural: { color: "#c084fc", bg: "#1a0e2e", border: "#4c1d95", label: "STRUCTURAL" },
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

export default function GitHubPRView({
  incidentId,
  service,
  environment,
  fixesData,
  approvalData,
  sentinelData,
  prData,
  preparing,
  error,
  onPreparePr,
}) {
  const isApproved = approvalData?.status === "approved";
  const approvedFixId = approvalData?.fix_id;
  const isSentinelPassed =
    sentinelData !== null &&
    sentinelData.status === "passed" &&
    sentinelData.safe_to_merge === true;

  const isGateUnlocked = isApproved && isSentinelPassed;

  // Find candidate fix matching the approved fix
  const candidateFixes = fixesData?.candidate_fixes || [];
  const approvedFix =
    candidateFixes.find((f) => f.fix_id === approvedFixId) ||
    (fixesData?.recommended_fix?.fix_id === approvedFixId
      ? fixesData.recommended_fix
      : null);

  // ── 1. LOCKED / SAFETY GATE NOT MET STATE ──────────────────────────────────
  if (!isGateUnlocked) {
    let lockReason = "Human approval and successful regression validation are required before PR preparation.";
    if (!isApproved && approvalData?.status === "rejected") {
      lockReason = "Fix was rejected by human reviewer in Stage 7. PR creation is blocked.";
    } else if (!isApproved) {
      lockReason = "Awaiting human authorization in Stage 7 (Human Approval Gate).";
    } else if (!sentinelData) {
      lockReason = "Regression Sentinel (Stage 8) has not been executed. Validation required.";
    } else if (!isSentinelPassed) {
      lockReason = "Regression Sentinel detected regressions or fix was marked unsafe to merge.";
    }

    return (
      <section className="evidence-section pr-locked">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 9: GITHUB PULL REQUEST</p>
            <h3>GitHub PR</h3>
            <p className="fixes-header-subhead">
              Prepare an evidence-backed pull request for the approved remediation.
            </p>
          </div>
          {incidentId && (
            <span className="fixes-incident-context-badge">
              Incident #{incidentId} {service ? `· ${service}` : ""}
            </span>
          )}
        </div>

        {/* Safety Gate Status Checklist Card */}
        <div className="pr-gate-status-card">
          <div className="pr-gate-header">
            <span className="pr-gate-lock-icon">🔒</span>
            <div>
              <strong>GITHUB PR STAGE LOCKED</strong>
              <p>{lockReason}</p>
            </div>
          </div>

          <div className="pr-gate-checkpoints-grid">
            <div className="pr-gate-checkpoint">
              <span className="pr-checkpoint-label">STAGE 7: HUMAN APPROVAL</span>
              {isApproved ? (
                <strong className="pr-status-tag approved">
                  ✓ APPROVED ({approvedFixId})
                </strong>
              ) : approvalData?.status === "rejected" ? (
                <strong className="pr-status-tag rejected">
                  ✕ REJECTED
                </strong>
              ) : (
                <strong className="pr-status-tag pending">
                  ● PENDING DECISION
                </strong>
              )}
            </div>

            <div className="pr-gate-checkpoint">
              <span className="pr-checkpoint-label">STAGE 8: REGRESSION SENTINEL</span>
              {isSentinelPassed ? (
                <strong className="pr-status-tag approved">
                  ✓ SAFE TO MERGE
                </strong>
              ) : sentinelData?.status === "failed" || sentinelData?.safe_to_merge === false ? (
                <strong className="pr-status-tag rejected">
                  ✕ BLOCKED (UNSAFE)
                </strong>
              ) : (
                <strong className="pr-status-tag pending">
                  ● NOT YET VALIDATED
                </strong>
              )}
            </div>
          </div>
        </div>

        <div className="incident-card empty-card" style={{ marginTop: 16 }}>
          <p>
            The GitHub PR stage is strictly protected. Verdict requires verified human authorization and passing automated regression assertions before generating branch proposals or PR payloads.
          </p>
        </div>
      </section>
    );
  }

  // ── 2. UNLOCKED: Ready to Prepare PR (Before In-flight/Response) ─────────────
  const isPrReady = !prData && !preparing;

  return (
    <section className="evidence-section">
      {/* ── HEADER ── */}
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 9: GITHUB PULL REQUEST (FINAL STAGE)</p>
          <h3>
            GitHub PR
            {prData?.status === "dry_run" && (
              <span style={{ color: "#38bdf8", fontSize: 14, marginLeft: 10 }}>
                ✓ Preview Ready (Dry-Run)
              </span>
            )}
            {prData?.status === "created" && prData?.github_url && (
              <span style={{ color: "#4ade80", fontSize: 14, marginLeft: 10 }}>
                ✓ PR Created
              </span>
            )}
          </h3>
          <p className="fixes-header-subhead">
            Prepare an evidence-backed pull request for the approved remediation.
          </p>
        </div>
        <div className="fixes-header-right">
          {incidentId && (
            <span className="fixes-incident-context-badge">
              Incident #{incidentId} {service ? `· ${service}` : ""} {environment ? `(${environment})` : ""}
            </span>
          )}
          {prData && onPreparePr && (
            <button
              className="view-all"
              onClick={() => onPreparePr(approvedFixId)}
              style={{ fontSize: 10, marginLeft: 8 }}
            >
              Re-generate ↺
            </button>
          )}
        </div>
      </div>

      {/* ── ERROR BANNER ── */}
      {error && (
        <div className="error-banner" style={{ marginBottom: 16 }}>
          <span>⚠️ {error}</span>
          {onPreparePr && (
            <button
              className="view-all"
              onClick={() => onPreparePr(approvedFixId)}
              style={{ color: "#fb7185" }}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* ── SAFETY GATE VERIFIED NOTICE ── */}
      <div className="fixes-safety-notice" style={{ borderLeftColor: "#4ade80" }}>
        <span className="fixes-safety-icon">🛡✓</span>
        <div>
          <strong>SAFETY GATES VERIFIED — PULL REQUEST AUTHORIZED</strong>
          <p>
            Fix <code>{approvedFixId}</code> was approved by <strong>{approvalData.approved_by}</strong> and passed all Regression Sentinel safety checks (<code>safe_to_merge=true</code>).
          </p>
        </div>
      </div>

      {/* ── PR PREPARATION SUMMARY CARDS (APPROVED FIX & SENTINEL SUMMARY) ── */}
      <div className="pr-summary-grid">
        {/* Approved Fix Summary */}
        <div className="pr-summary-card">
          <span className="pr-summary-eyebrow">AUTHORIZED REMEDIATION</span>
          <div className="pr-summary-title-row">
            <h4>{approvedFix?.title || approvedFixId}</h4>
            {approvedFix && (
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
            )}
          </div>
          <code className="approval-fix-id-code">{approvedFixId}</code>
          <p className="fix-description" style={{ marginTop: 8 }}>
            {approvedFix?.description}
          </p>
          <div className="pr-meta-list">
            <div>
              <span className="pr-meta-label">RISK:</span>
              <strong style={{ color: getRiskConfig(approvedFix?.risk_level).color }}>
                {(approvedFix?.risk_level || "medium").toUpperCase()}
              </strong>
            </div>
            <div>
              <span className="pr-meta-label">RANK SCORE:</span>
              <strong>{approvedFix?.rank_score || "N/A"}</strong>
            </div>
            <div>
              <span className="pr-meta-label">APPROVED BY:</span>
              <strong>{approvalData.approved_by}</strong>
            </div>
          </div>
        </div>

        {/* Regression Sentinel Summary */}
        <div className="pr-summary-card">
          <span className="pr-summary-eyebrow">VALIDATION SENTINEL AUDIT</span>
          <div className="pr-summary-title-row">
            <h4>Regression Sentinel Validation</h4>
            <span className="sentinel-merge-badge safe">
              ✓ SAFE TO MERGE
            </span>
          </div>
          <p className="fix-description" style={{ marginTop: 8 }}>
            {sentinelData?.validation_summary}
          </p>
          <div className="pr-meta-list">
            <div>
              <span className="pr-meta-label">CHECKS PASSED:</span>
              <strong>
                {sentinelData?.checks?.filter((c) => c.status === "passed").length || 0} / {sentinelData?.checks?.length || 0}
              </strong>
            </div>
            <div>
              <span className="pr-meta-label">REGRESSIONS:</span>
              <strong style={{ color: "#4ade80" }}>
                {sentinelData?.regressions_detected?.length || 0} DETECTED
              </strong>
            </div>
            <div>
              <span className="pr-meta-label">SANDBOX MODE:</span>
              <strong>LOCAL VALIDATION</strong>
            </div>
          </div>
        </div>
      </div>

      {/* ── ACTION BUTTON: PREPARE PR (When not yet prepared) ── */}
      {isPrReady && (
        <div className="workspace-action-bar" style={{ marginTop: 20 }}>
          <div className="action-description">
            <strong>Ready to Generate Evidence-Backed Pull Request</strong>
            <p>
              Generate structured git branch name, commit message, and evidence-grounded pull request description containing RCA root cause, proof chain, validation logs, and approval metadata.
            </p>
          </div>
          <button
            className="investigate-button"
            onClick={() => onPreparePr(approvedFixId)}
            disabled={preparing}
          >
            {preparing ? "Preparing GitHub PR..." : "Prepare GitHub PR →"}
          </button>
        </div>
      )}

      {/* ── IN-FLIGHT LOADING STATE ── */}
      {preparing && !prData && (
        <div className="incident-card empty-card" style={{ marginTop: 20 }}>
          <p>Synthesizing evidence-backed PR payload from RCA, graph proof, and validation contracts...</p>
        </div>
      )}

      {/* ── PR RESULT DISPLAY (DRY-RUN PREVIEW OR REAL PR) ── */}
      {prData && (
        <div className="pr-result-section">
          {/* Dry-Run Notice or Live PR Link */}
          {prData.status === "dry_run" ? (
            <div className="pr-dryrun-banner">
              <div className="pr-dryrun-icon">🛡</div>
              <div>
                <strong>SAFE DRY-RUN MODE: PR PREVIEW READY</strong>
                <p>
                  No external GitHub branch or PR was created. Verdict is operating in safe dry-run mode (0 network requests, github_url=null). Source code is not modified and no merge was executed.
                </p>
              </div>
            </div>
          ) : (
            <div className="pr-live-banner">
              <div className="pr-dryrun-icon">✓</div>
              <div>
                <strong>GITHUB PULL REQUEST CREATED</strong>
                <p>
                  Pull request created successfully. Review and merge via GitHub repository.
                </p>
                {prData.github_url && (
                  <a
                    href={prData.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="pr-github-link-btn"
                  >
                    Open Pull Request on GitHub ↗
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Git Branch & Commit Details */}
          <div className="pr-git-details-card">
            <div className="pr-git-row">
              <span className="pr-git-label">TARGET BRANCH</span>
              <code className="pr-git-code">{prData.branch_name}</code>
            </div>
            <div className="pr-git-row">
              <span className="pr-git-label">COMMIT MESSAGE</span>
              <code className="pr-git-code">{prData.commit_message}</code>
            </div>
            <div className="pr-git-row">
              <span className="pr-git-label">PULL REQUEST TITLE</span>
              <strong className="pr-title-text">{prData.pull_request_title}</strong>
            </div>
          </div>

          {/* Full Markdown PR Body Preview */}
          <div className="pr-body-preview-container">
            <div className="pr-body-preview-header">
              <span>EVIDENCE-BACKED PR DESCRIPTION PREVIEW</span>
              <span className="pr-markdown-tag">MARKDOWN</span>
            </div>
            <div className="pr-body-preview-content">
              <pre className="pr-markdown-pre">
                <code>{prData.pull_request_body}</code>
              </pre>
            </div>
          </div>

          {/* Pipeline Completion Summary */}
          <div className="fixes-next-stage-callout" style={{ marginTop: 20 }}>
            <div className="fixes-next-stage-header">
              <div className="fixes-next-stage-badge" style={{ color: "#4ade80", background: "#0f2218", borderColor: "#166534" }}>
                Stage 9: ✓ GITHUB PR COMPLETE
              </div>
              <div className="fixes-next-stage-arrow">→</div>
              <div className="fixes-next-stage-badge" style={{ color: "#c4b5fd", background: "#1f1730", borderColor: "#5b3d9c" }}>
                PIPELINE COMPLETE (9/9 STAGES)
              </div>
            </div>
            <p className="fixes-next-stage-desc">
              Investigation lifecycle successfully finished. Incident #{incidentId} was captured, multi-source evidence was collected, Evidence Graph constructed, root cause cross-examined, impact quantified, candidate fixes formulated, human approval authorized, regression assertions validated, and evidence-backed PR prepared.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
