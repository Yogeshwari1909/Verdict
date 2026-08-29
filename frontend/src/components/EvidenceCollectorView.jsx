export default function EvidenceCollectorView({
  evidence = [],
  loading = false,
  error = null,
  onRetry,
}) {
  if (loading) {
    return (
      <section className="evidence-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">STAGE 2: EVIDENCE COLLECTOR</p>
            <h3>Collecting Multi-Source Evidence...</h3>
          </div>
        </div>
        <div className="incident-card empty-card">
          <span className="live-dot loading" style={{ margin: "0 auto 12px" }}></span>
          <p>Querying Incident Memory in SQLite and gathering safe Git context...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="evidence-section">
        <div className="error-banner">
          <span>⚠️ {error}</span>
          {onRetry && (
            <button
              className="view-all"
              onClick={onRetry}
              style={{ color: "#fb7185" }}
            >
              Retry Collection
            </button>
          )}
        </div>
      </section>
    );
  }

  if (!evidence || evidence.length === 0) {
    return null;
  }

  // Group evidence items by source
  const runtimeTelemetry = evidence.filter(
    (e) => e.source === "runtime_telemetry"
  );
  const incidentMemory = evidence.filter(
    (e) => e.source === "incident_memory"
  );
  const githubContext = evidence.filter((e) => e.source === "github");

  return (
    <section className="evidence-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">STAGE 2: EVIDENCE COLLECTOR</p>
          <h3>Collected Evidence Artifacts ({evidence.length})</h3>
        </div>
        <span className="severity" style={{ background: "#1b2518", borderColor: "#2e5229", color: "#86efac" }}>
          ✓ {evidence.length} PROOF ARTIFACTS
        </span>
      </div>

      <div className="evidence-groups-container">
        {/* 1. Runtime Telemetry */}
        {runtimeTelemetry.length > 0 && (
          <div className="evidence-group">
            <div className="evidence-group-header">
              <span className="group-indicator telemetry"></span>
              <h4>Runtime Telemetry ({runtimeTelemetry.length})</h4>
            </div>
            <div className="evidence-cards-list">
              {runtimeTelemetry.map((item, idx) => (
                <div key={`telemetry-${idx}`} className="evidence-card">
                  <div className="evidence-card-header">
                    <strong>{item.title}</strong>
                    <span className="evidence-type-badge">{item.evidence_type}</span>
                  </div>
                  <pre className="evidence-content">
                    <code>{item.content}</code>
                  </pre>
                  {item.metadata && Object.keys(item.metadata).length > 0 && (
                    <div className="evidence-meta-tags">
                      {item.metadata.service && (
                        <span className="meta-tag">Service: {item.metadata.service}</span>
                      )}
                      {item.metadata.environment && (
                        <span className="meta-tag">Env: {item.metadata.environment}</span>
                      )}
                      {item.metadata.request_id && (
                        <span className="meta-tag">Req ID: {item.metadata.request_id}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 2. Incident Memory */}
        {incidentMemory.length > 0 && (
          <div className="evidence-group">
            <div className="evidence-group-header">
              <span className="group-indicator memory"></span>
              <h4>Incident Memory & Historical Precedents ({incidentMemory.length})</h4>
            </div>
            <div className="evidence-cards-list">
              {incidentMemory.map((item, idx) => (
                <div key={`memory-${idx}`} className="evidence-card">
                  <div className="evidence-card-header">
                    <strong>{item.title}</strong>
                    <span className="evidence-type-badge memory-badge">
                      {item.evidence_type}
                    </span>
                  </div>
                  <pre className="evidence-content">
                    <code>{item.content}</code>
                  </pre>
                  {item.metadata && Object.keys(item.metadata).length > 0 && (
                    <div className="evidence-meta-tags">
                      {item.metadata.matched_incident_id && (
                        <span className="meta-tag">
                          Matched Incident #{item.metadata.matched_incident_id}
                        </span>
                      )}
                      {item.metadata.exception_type && (
                        <span className="meta-tag">
                          Pattern: {item.metadata.exception_type}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 3. GitHub Context */}
        {githubContext.length > 0 && (
          <div className="evidence-group">
            <div className="evidence-group-header">
              <span className="group-indicator github"></span>
              <h4>GitHub Context & Source Repository ({githubContext.length})</h4>
            </div>
            <div className="evidence-cards-list">
              {githubContext.map((item, idx) => (
                <div key={`github-${idx}`} className="evidence-card">
                  <div className="evidence-card-header">
                    <strong>{item.title}</strong>
                    <span className="evidence-type-badge github-badge">
                      {item.evidence_type}
                    </span>
                  </div>
                  <pre className="evidence-content">
                    <code>{item.content}</code>
                  </pre>
                  {item.metadata && Object.keys(item.metadata).length > 0 && (
                    <div className="evidence-meta-tags">
                      {item.metadata.repository && (
                        <span className="meta-tag">Repo: {item.metadata.repository}</span>
                      )}
                      {item.metadata.file_path && (
                        <span className="meta-tag">File: {item.metadata.file_path}</span>
                      )}
                      {item.metadata.commit_sha && (
                        <span className="meta-tag">Commit: {item.metadata.commit_sha}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
