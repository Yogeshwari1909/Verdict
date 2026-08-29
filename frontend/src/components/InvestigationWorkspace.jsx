import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function InvestigationWorkspace({
  incidentId,
  onBack,
  onStartEvidenceCollection,
}) {
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
          <div className="pipeline-step completed">
            <div className="step-number">✓</div>
            <strong>Incident</strong>
            <span>Captured</span>
          </div>

          <div className="connector completed-line"></div>

          <div className="pipeline-step current">
            <div className="step-number">2</div>
            <strong>Evidence</strong>
            <span>Ready to Collect</span>
          </div>

          <div className="connector"></div>

          <div className="pipeline-step">
            <div className="step-number">3</div>
            <strong>Graph</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

          <div className="pipeline-step">
            <div className="step-number">4</div>
            <strong>RCA</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

          <div className="pipeline-step">
            <div className="step-number">5</div>
            <strong>Impact</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

          <div className="pipeline-step">
            <div className="step-number">6</div>
            <strong>3 Fixes</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

          <div className="pipeline-step">
            <div className="step-number">7</div>
            <strong>Approval</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

          <div className="pipeline-step">
            <div className="step-number">8</div>
            <strong>Sentinel</strong>
            <span>Pending</span>
          </div>

          <div className="connector"></div>

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
            <strong>Ready for Evidence Collection</strong>
            <p>
              Query historical Incident Memory in SQLite and fetch local GitHub
              context to build the Evidence Graph.
            </p>
          </div>

          <button
            className="investigate-button"
            onClick={() => {
              if (onStartEvidenceCollection) {
                onStartEvidenceCollection(incident.id);
              }
            }}
          >
            Collect Evidence →
          </button>
        </div>
      </section>
    </div>
  );
}
