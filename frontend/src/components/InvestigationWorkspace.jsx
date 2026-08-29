import { useEffect, useState } from "react";
import { api } from "../api/client";
import EvidenceCollectorView from "./EvidenceCollectorView";
import EvidenceGraphView from "./EvidenceGraphView";
import RCAAnalysisView from "./RCAAnalysisView";
import BlastRadiusView from "./BlastRadiusView";
import CandidateFixesView from "./CandidateFixesView";

export default function InvestigationWorkspace({
  incidentId,
  onBack,
}) {
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Evidence Collector State
  const [evidence, setEvidence] = useState([]);
  const [collectingEvidence, setCollectingEvidence] = useState(false);
  const [evidenceError, setEvidenceError] = useState(null);

  // Evidence Graph State
  const [graphData, setGraphData] = useState(null);
  const [buildingGraph, setBuildingGraph] = useState(false);
  const [graphError, setGraphError] = useState(null);

  // RCA / Cross-Examination State
  const [rcaData, setRcaData] = useState(null);
  const [analyzingRca, setAnalyzingRca] = useState(false);
  const [rcaError, setRcaError] = useState(null);

  // Blast Radius / Impact State
  const [impactData, setImpactData] = useState(null);
  const [analyzingImpact, setAnalyzingImpact] = useState(false);
  const [impactError, setImpactError] = useState(null);

  // Candidate Fixes State
  const [fixesData, setFixesData] = useState(null);
  const [generatingFixes, setGeneratingFixes] = useState(false);
  const [fixesError, setFixesError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchIncidentDetails() {
      if (!incidentId) return;
      setLoading(true);
      setError(null);
      try {
        const data = await api.getIncident(incidentId);
        if (isMounted) {
          setIncident(data);
        }
      } catch (err) {
        if (isMounted) {
          setError(
            err.status === 404
              ? `Incident #${incidentId} not found in database.`
              : err.message || "Failed to load incident investigation details."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchIncidentDetails();
    return () => {
      isMounted = false;
    };
  }, [incidentId]);

  // Handler for collecting multi-source evidence from SQLite & safe GitHub context
  const handleCollectEvidence = async () => {
    if (!incidentId || collectingEvidence) return;
    setCollectingEvidence(true);
    setEvidenceError(null);
    try {
      const res = await api.collectEvidence(incidentId);
      if (res && res.evidence) {
        setEvidence(res.evidence);
      }
    } catch (err) {
      setEvidenceError(
        err.message || "Failed to collect multi-source evidence for this incident."
      );
    } finally {
      setCollectingEvidence(false);
    }
  };

  // Handler for building (or rebuilding) the Evidence Graph from backend
  const handleBuildGraph = async () => {
    if (!incidentId || buildingGraph) return;
    setBuildingGraph(true);
    setGraphError(null);
    try {
      const res = await api.buildGraph(incidentId);
      if (res && res.graph) {
        setGraphData(res);
      } else {
        setGraphError("Backend returned an unexpected graph response.");
      }
    } catch (err) {
      setGraphError(
        err.message || "Failed to build the Evidence Graph for this incident."
      );
    } finally {
      setBuildingGraph(false);
    }
  };

  // Handler for running (or re-running) the RCA Cross-Examination Engine
  const handleAnalyzeRca = async () => {
    if (!incidentId || analyzingRca) return;
    setAnalyzingRca(true);
    setRcaError(null);
    try {
      const res = await api.analyzeRca(incidentId);
      if (res && (res.hypotheses !== undefined || res.confidence !== undefined)) {
        setRcaData(res);
      } else {
        setRcaError("Backend returned an unexpected RCA response.");
      }
    } catch (err) {
      setRcaError(
        err.message || "Failed to run RCA analysis for this incident."
      );
    } finally {
      setAnalyzingRca(false);
    }
  };

  // Handler for running (or re-running) the Blast Radius / Impact Analysis
  const handleAnalyzeImpact = async () => {
    if (!incidentId || analyzingImpact) return;
    setAnalyzingImpact(true);
    setImpactError(null);
    try {
      const res = await api.getImpact(incidentId);
      if (res && res.impact_level !== undefined) {
        setImpactData(res);
      } else {
        setImpactError("Backend returned an unexpected impact response.");
      }
    } catch (err) {
      setImpactError(
        err.message || "Failed to analyze blast radius for this incident."
      );
    } finally {
      setAnalyzingImpact(false);
    }
  };

  // Handler for generating (or re-generating) the 3 Candidate Fixes
  const handleGenerateFixes = async () => {
    if (!incidentId || generatingFixes) return;
    setGeneratingFixes(true);
    setFixesError(null);
    try {
      const res = await api.getCandidateFixes(incidentId);
      if (res && res.candidate_fixes !== undefined) {
        setFixesData(res);
      } else {
        setFixesError("Backend returned an unexpected fixes response.");
      }
    } catch (err) {
      setFixesError(
        err.message || "Failed to generate candidate fixes for this incident."
      );
    } finally {
      setGeneratingFixes(false);
    }
  };

  if (loading) {
    return (
      <div className="workspace-container">
        <button className="back-button" onClick={onBack}>
          ← Back to Dashboard
        </button>
        <div className="incident-card empty-card">
          <p>Loading investigation workspace for Incident #{incidentId}...</p>
        </div>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="workspace-container">
        <button className="back-button" onClick={onBack}>
          ← Back to Dashboard
        </button>
        <div className="incident-card empty-card">
          <h3>Incident Not Found</h3>
          <p>{error || `Incident #${incidentId} does not exist.`}</p>
          <button className="investigate-button" onClick={onBack}>
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const isCritical = incident.status_code >= 500;
  const isEvidenceCollected = evidence.length > 0;
  const isGraphBuilt = graphData !== null && (graphData.graph?.nodes?.length ?? 0) > 0;
  const isRcaComplete = rcaData !== null && (rcaData.confidence > 0 || rcaData.hypotheses?.length > 0);
  const rcaPct = rcaData ? Math.round((rcaData.confidence || 0) * 100) : 0;
  const isImpactComplete = impactData !== null && impactData.impact_level !== undefined;
  const impactLevel = impactData ? (impactData.impact_level || "unknown").toUpperCase() : "";
  const impactPct = impactData ? Math.round((impactData.confidence || 0) * 100) : 0;
  const isFixesComplete = fixesData !== null && (fixesData.candidate_fixes?.length > 0 || fixesData.recommended_fix !== null);
  const fixCount = fixesData?.candidate_fixes?.length ?? 0;

  return (
    <div className="workspace-container">
      {/* Top navigation row */}
      <div className="workspace-nav-row">
        <button className="back-button" onClick={onBack}>
          ← Back to Incident Dashboard
        </button>
        <div className="workspace-tag">
          <span className="live-dot"></span>
          <span>INVESTIGATION WORKSPACE</span>
        </div>
      </div>

      {/* Header */}
      <header className="workspace-header">
        <div>
          <p className="eyebrow">ROOT CAUSE INVESTIGATION</p>
          <h2>
            Incident #{incident.id} · {incident.service}
          </h2>
          <p className="workspace-subhead">
            {incident.http_method} {incident.endpoint} &nbsp;•&nbsp;{" "}
            <span className="env-tag">{incident.environment}</span>
          </p>
        </div>

        <div className="workspace-header-actions">
          <span
            className={`severity ${isCritical ? "" : "warning-severity"}`}
          >
            {isCritical ? "CRITICAL (5xx)" : "WARNING (4xx)"}
          </span>
        </div>
      </header>

      {/* 9-Stage Verdict Investigation Pipeline */}
      <section className="pipeline-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">VERDICT PIPELINE</p>
            <h3>Investigation Lifecycle Progress</h3>
          </div>
        </div>

        <div className="pipeline workspace-pipeline">
          {/* Stage 1: Incident */}
          <div className="pipeline-step completed">
            <div className="step-number">✓</div>
            <strong>Incident</strong>
            <span>Captured</span>
          </div>

          <div
            className={`connector ${
              isEvidenceCollected ? "completed-line" : ""
            }`}
          ></div>

          {/* Stage 2: Evidence */}
          <div
            className={`pipeline-step ${
              isEvidenceCollected
                ? "completed"
                : collectingEvidence
                ? "current"
                : "current"
            }`}
          >
            <div className="step-number">
              {isEvidenceCollected ? "✓" : "2"}
            </div>
            <strong>Evidence</strong>
            <span>
              {isEvidenceCollected
                ? `${evidence.length} Collected`
                : collectingEvidence
                ? "Collecting..."
                : "Ready"}
            </span>
          </div>

          <div className="connector"></div>

          {/* Stage 3: Graph */}
          <div
            className={`pipeline-step ${
              isGraphBuilt
                ? "completed"
                : buildingGraph
                ? "current"
                : isEvidenceCollected
                ? "current"
                : ""
            }`}
          >
            <div className="step-number">
              {isGraphBuilt ? "✓" : buildingGraph ? "…" : "3"}
            </div>
            <strong>Graph</strong>
            <span>
              {isGraphBuilt
                ? `${graphData.nodes_created ?? graphData.graph?.nodes?.length} Nodes · ${graphData.edges_created ?? graphData.graph?.edges?.length} Edges`
                : buildingGraph
                ? "Building..."
                : isEvidenceCollected
                ? "Next Step"
                : "Pending"}
            </span>
          </div>

          <div className={`connector ${isGraphBuilt ? "completed-line" : ""}`}></div>

          {/* Stage 4: RCA */}
          <div
            className={`pipeline-step ${
              isRcaComplete
                ? "completed"
                : analyzingRca
                ? "current"
                : isGraphBuilt
                ? "current"
                : ""
            }`}
          >
            <div className="step-number">
              {isRcaComplete ? "✓" : analyzingRca ? "…" : "4"}
            </div>
            <strong>RCA</strong>
            <span>
              {isRcaComplete
                ? `${rcaPct}% Confidence`
                : analyzingRca
                ? "Cross-Examining..."
                : isGraphBuilt
                ? "Next Step"
                : "Pending"}
            </span>
          </div>

          <div className={`connector ${isRcaComplete ? "completed-line" : ""}`}></div>

          {/* Stage 5: Impact */}
          <div
            className={`pipeline-step ${
              isImpactComplete
                ? "completed"
                : analyzingImpact
                ? "current"
                : isRcaComplete
                ? "current"
                : ""
            }`}
          >
            <div className="step-number">
              {isImpactComplete ? "✓" : analyzingImpact ? "…" : "5"}
            </div>
            <strong>Impact</strong>
            <span>
              {isImpactComplete
                ? `${impactLevel} · ${impactPct}%`
                : analyzingImpact
                ? "Analyzing..."
                : isRcaComplete
                ? "Next Step"
                : "Pending"}
            </span>
          </div>

          <div className={`connector ${isImpactComplete ? "completed-line" : ""}`}></div>

          {/* Stage 6: 3 Fixes */}
          <div
            className={`pipeline-step ${
              isFixesComplete
                ? "completed"
                : generatingFixes
                ? "current"
                : isImpactComplete
                ? "current"
                : ""
            }`}
          >
            <div className="step-number">
              {isFixesComplete ? "✓" : generatingFixes ? "…" : "6"}
            </div>
            <strong>3 Fixes</strong>
            <span>
              {isFixesComplete
                ? `${fixCount} Fix${fixCount !== 1 ? "es" : ""}`
                : generatingFixes
                ? "Generating..."
                : isImpactComplete
                ? "Next Step"
                : "Pending"}
            </span>
          </div>

          <div className={`connector ${isFixesComplete ? "completed-line" : ""}`}></div>

          {/* Stage 7: Approval */}
          <div className={`pipeline-step ${isFixesComplete ? "current" : ""}`}>
            <div className="step-number">7</div>
            <strong>Approval</strong>
            <span>{isFixesComplete ? "Next Step" : "Pending"}</span>
          </div>

          <div className="connector"></div>

          {/* Stage 8: Sentinel */}
          <div className="pipeline-step">
            <div className="step-number">8</div>
            <strong>Sentinel</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

          {/* Stage 9: GitHub PR */}
          <div className="pipeline-step">
            <div className="step-number">9</div>
            <strong>GitHub PR</strong>
            <span>Pending</span>
          </div>
        </div>
      </section>

      {/* Incident Summary Card */}
      <section className="incident-card">
        <div className="incident-header">
          <div className="incident-title">
            <span
              className={`error-code ${isCritical ? "" : "warning-400"}`}
            >
              {incident.status_code}
            </span>
            <div>
              <h3>{incident.exception_type}</h3>
              <p>{incident.exception_message}</p>
            </div>
          </div>

          <span className="investigating">STAGE 1: CAPTURED</span>
        </div>

        <div className="incident-details">
          <div>
            <span>SERVICE</span>
            <strong>{incident.service}</strong>
          </div>

          <div>
            <span>ENVIRONMENT</span>
            <strong>{incident.environment}</strong>
          </div>

          <div>
            <span>REQUEST ID</span>
            <strong>{incident.request_id || "N/A"}</strong>
          </div>

          <div>
            <span>TIMESTAMP</span>
            <strong>
              {incident.timestamp
                ? incident.timestamp.slice(0, 19)
                : incident.created_at
                ? incident.created_at.slice(0, 19)
                : "Recently"}
            </strong>
          </div>
        </div>

        {/* Traceback Code Preview */}
        {incident.stack_trace && (
          <div className="traceback-container">
            <div className="traceback-header">
              <span>STACK TRACE TELEMETRY (NORMALIZED & REDACTED)</span>
            </div>
            <pre className="traceback-code">
              <code>{incident.stack_trace}</code>
            </pre>
          </div>
        )}

        {/* Primary Action Button to Advance */}
        <div className="workspace-action-bar">
          <div className="action-description">
            <strong>
              {isEvidenceCollected
                ? `Stage 2 Complete (${evidence.length} Artifacts Collected)`
                : "Ready for Evidence Collection"}
            </strong>
            <p>
              {isEvidenceCollected
                ? "Historical incident memory and GitHub repository context collected. Ready to construct Evidence Graph."
                : "Query historical Incident Memory in SQLite and fetch safe local GitHub context."}
            </p>
          </div>

          <button
            className="investigate-button"
            onClick={handleCollectEvidence}
            disabled={collectingEvidence || isEvidenceCollected}
          >
            {collectingEvidence
              ? "Collecting Evidence..."
              : isEvidenceCollected
              ? `Evidence Collected ✓ (${evidence.length})`
              : "Collect Evidence →"}
          </button>
        </div>
      </section>

      {/* Render Evidence Collector Artifacts View */}
      <EvidenceCollectorView
        evidence={evidence}
        loading={collectingEvidence}
        error={evidenceError}
        onRetry={handleCollectEvidence}
      />

      {/* Render Evidence Graph View — only once evidence is collected */}
      {isEvidenceCollected && (
        <EvidenceGraphView
          graphData={graphData}
          loading={buildingGraph}
          error={graphError}
          onBuild={handleBuildGraph}
          onRebuild={handleBuildGraph}
        />
      )}

      {/* Render RCA / Cross-Examination View — only once graph is built */}
      <RCAAnalysisView
        rcaData={rcaData}
        loading={false}
        analyzing={analyzingRca}
        error={rcaError}
        graphBuilt={isGraphBuilt}
        onRunRca={handleAnalyzeRca}
        onRetry={handleAnalyzeRca}
      />

      {/* Render Blast Radius / Impact View — always rendered; handles own lock state */}
      <BlastRadiusView
        impactData={impactData}
        loading={false}
        analyzing={analyzingImpact}
        error={impactError}
        rcaComplete={isRcaComplete}
        onAnalyze={handleAnalyzeImpact}
        onRetry={handleAnalyzeImpact}
      />

      {/* Render Candidate Fixes View — always rendered; handles own lock state */}
      <CandidateFixesView
        fixesData={fixesData}
        loading={false}
        generating={generatingFixes}
        error={fixesError}
        impactComplete={isImpactComplete}
        onGenerate={handleGenerateFixes}
        onRetry={handleGenerateFixes}
      />
    </div>
  );
}
