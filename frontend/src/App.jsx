import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import InvestigationWorkspace from "./components/InvestigationWorkspace";
import "./App.css";

function App() {
  const [currentView, setCurrentView] = useState("dashboard");
  const [healthStatus, setHealthStatus] = useState(null);
  const [dbStatus, setDbStatus] = useState(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [systemError, setSystemError] = useState(null);

  const [incidents, setIncidents] = useState([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [isLoadingIncidents, setIsLoadingIncidents] = useState(true);
  const [incidentError, setIncidentError] = useState(null);

  // 1. Fetch system status (Health + DB Status)
  const fetchSystemStatus = useCallback(async () => {
    setIsLoadingStatus(true);
    setSystemError(null);
    try {
      const [health, db] = await Promise.all([
        api.getHealth(),
        api.getDbStatus(),
      ]);
      setHealthStatus(health);
      setDbStatus(db);
    } catch (err) {
      setSystemError(err.message || "Failed to connect to backend");
    } finally {
      setIsLoadingStatus(false);
    }
  }, []);

  // 2. Fetch real incident data from existing backend endpoints
  const loadIncidents = useCallback(async () => {
    setIsLoadingIncidents(true);
    setIncidentError(null);
    try {
      const verdicts = await api.getVerdicts().catch(() => []);
      const incidentIdSet = new Set();

      for (const v of verdicts) {
        if (v.title) {
          const match = v.title.match(/Incident #(\d+)/);
          if (match) {
            incidentIdSet.add(parseInt(match[1], 10));
          }
        }
      }

      // Probe recent IDs 1..5 if no verdicts found
      if (incidentIdSet.size === 0) {
        for (let i = 1; i <= 5; i++) {
          try {
            const inc = await api.getIncident(i);
            if (inc && inc.id) {
              incidentIdSet.add(inc.id);
            }
          } catch {
            // Not found
          }
        }
      }

      // Fetch full details for each discovered incident ID
      const loaded = [];
      for (const incId of incidentIdSet) {
        try {
          const inc = await api.getIncident(incId);
          if (inc && inc.id) {
            loaded.push(inc);
          }
        } catch {
          // Skip if missing
        }
      }

      loaded.sort((a, b) => b.id - a.id);
      setIncidents(loaded);
      if (loaded.length > 0) {
        setSelectedIncidentId((prev) => (prev ? prev : loaded[0].id));
      }
    } catch (err) {
      setIncidentError(err.message || "Failed to load incidents from backend");
    } finally {
      setIsLoadingIncidents(false);
    }
  }, []);

  useEffect(() => {
    fetchSystemStatus();
    loadIncidents();
  }, [fetchSystemStatus, loadIncidents]);

  // Handler to simulate & ingest a real runtime failure for testing
  const handleTriggerSimulatedIncident = async () => {
    try {
      setIsLoadingIncidents(true);
      const checkoutFail = await api.triggerCheckoutFailure();
      const ingestRes = await api.ingestIncident({
        service: "checkout-service",
        environment: "production",
        endpoint: "/checkout",
        http_method: "POST",
        status_code: 500,
        exception_type: checkoutFail.error_type || "PaymentProcessingError",
        exception_message:
          checkoutFail.detail ||
          "Payment payload is null or missing in payment_service.charge",
        stack_trace:
          checkoutFail.traceback ||
          "Traceback: payment_service.charge failed with ValueError",
        metadata: { build: "v2.1.0", checkout_mode: "express" },
      });

      if (ingestRes?.incident_id) {
        await api.buildGraph(ingestRes.incident_id).catch(() => {});
        await loadIncidents();
        setSelectedIncidentId(ingestRes.incident_id);
      }
    } catch (err) {
      setIncidentError(
        "Failed to simulate incident: " + (err.message || "Unknown error")
      );
    } finally {
      setIsLoadingIncidents(false);
    }
  };

  const isConnected =
    !isLoadingStatus &&
    !systemError &&
    healthStatus?.status === "ok" &&
    dbStatus?.status === "ok";

  const isError =
    !isLoadingStatus &&
    (Boolean(systemError) ||
      healthStatus?.status !== "ok" ||
      dbStatus?.status !== "ok");

  let statusTitle = "Backend Connected";
  let statusSubtitle = "FastAPI & SQLite operational";
  let statusClass = "connected";

  if (isLoadingStatus) {
    statusTitle = "Connecting...";
    statusSubtitle = "Checking system health";
    statusClass = "loading";
  } else if (isError) {
    statusTitle = "Backend Error";
    statusSubtitle = systemError || "Service disconnected";
    statusClass = "error";
  }

  // Active incident resolution
  const activeIncident =
    incidents.find((i) => i.id === selectedIncidentId) ||
    incidents[0] ||
    null;

  const isCritical = activeIncident?.status_code >= 500;

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">V</div>
          <div>
            <h1>VERDICT</h1>
            <span>AI Incident Investigator</span>
          </div>
        </div>

        <nav>
          <button
            className={`nav-item ${
              currentView === "dashboard" ? "active" : ""
            }`}
            onClick={() => setCurrentView("dashboard")}
          >
            <span>⌂</span>
            Dashboard
          </button>

          <button
            className="nav-item"
            onClick={() => setCurrentView("dashboard")}
          >
            <span>◉</span>
            Incidents
          </button>

          <button
            className={`nav-item ${
              currentView === "investigation" ? "active" : ""
            }`}
            onClick={() => {
              if (selectedIncidentId || activeIncident?.id) {
                setCurrentView("investigation");
              }
            }}
          >
            <span>⌕</span>
            Investigations
          </button>
        </nav>

        <div className={`system-status ${statusClass}`}>
          <span className={`status-dot ${statusClass}`}></span>
          <div>
            <strong>{statusTitle}</strong>
            <small title={statusSubtitle}>{statusSubtitle}</small>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="main">
        {currentView === "investigation" &&
        (selectedIncidentId || activeIncident?.id) ? (
          <InvestigationWorkspace
            incidentId={selectedIncidentId || activeIncident.id}
            onBack={() => setCurrentView("dashboard")}
            onStartEvidenceCollection={(id) => {
              // Action hook prepared for next pipeline step (Task 5)
              console.log("Starting evidence collection for incident:", id);
            }}
          />
        ) : (
          <>
            <header className="topbar">
              <div>
                <p className="eyebrow">INVESTIGATION CENTER</p>
                <h2>Incident Dashboard</h2>
              </div>

              <div className="topbar-right">
                <span className="live">
                  <span className={`live-dot ${statusClass}`}></span>
                  {isLoadingStatus
                    ? "CONNECTING"
                    : isConnected
                    ? "LIVE"
                    : "OFFLINE"}
                </span>

                <div className="avatar">V</div>
              </div>
            </header>

            {incidentError && (
              <div className="error-banner">
                <span>⚠️ {incidentError}</span>
                <button
                  className="view-all"
                  onClick={loadIncidents}
                  style={{ color: "#fb7185" }}
                >
                  Retry
                </button>
              </div>
            )}

            {/* Stats */}
            <section className="stats">
              <div className="stat-card">
                <span>ACTIVE INCIDENTS</span>
                <strong>
                  {isLoadingIncidents
                    ? "..."
                    : String(incidents.length).padStart(2, "0")}
                </strong>
                <small>Requires investigation</small>
              </div>

              <div className="stat-card">
                <span>INVESTIGATING</span>
                <strong>{activeIncident ? "01" : "00"}</strong>
                <small>Currently selected</small>
              </div>

              <div className="stat-card">
                <span>RESOLVED</span>
                <strong>00</strong>
                <small>This session</small>
              </div>

              <div className="stat-card">
                <span>PRs CREATED</span>
                <strong>00</strong>
                <small>Validated fixes</small>
              </div>
            </section>

            {/* Active investigation */}
            <section className="section-header">
              <div>
                <p className="eyebrow">ACTIVE INVESTIGATION</p>
                <h3>
                  {activeIncident
                    ? `Incident #${activeIncident.id}`
                    : "No Active Incident"}
                </h3>
              </div>

              {activeIncident && (
                <span
                  className={`severity ${
                    isCritical ? "" : "warning-severity"
                  }`}
                >
                  {isCritical ? "CRITICAL" : "WARNING"}
                </span>
              )}
            </section>

            {isLoadingIncidents ? (
              <div className="incident-card empty-card">
                <p>Loading incident telemetry from SQLite backend...</p>
              </div>
            ) : activeIncident ? (
              <section className="incident-card">
                <div className="incident-header">
                  <div>
                    <div className="incident-title">
                      <span
                        className={`error-code ${
                          isCritical ? "" : "warning-400"
                        }`}
                      >
                        {activeIncident.status_code}
                      </span>
                      <div>
                        <h3>{activeIncident.exception_type}</h3>
                        <p>
                          {activeIncident.http_method}{" "}
                          {activeIncident.endpoint}
                        </p>
                      </div>
                    </div>
                  </div>

                  <span className="investigating">INVESTIGATING</span>
                </div>

                <div className="incident-details">
                  <div>
                    <span>EXCEPTION</span>
                    <strong>{activeIncident.exception_type}</strong>
                  </div>

                  <div>
                    <span>SERVICE</span>
                    <strong>{activeIncident.service}</strong>
                  </div>

                  <div>
                    <span>ENVIRONMENT</span>
                    <strong>{activeIncident.environment}</strong>
                  </div>

                  <div>
                    <span>TIMESTAMP</span>
                    <strong>
                      {activeIncident.timestamp
                        ? activeIncident.timestamp.slice(0, 19)
                        : activeIncident.created_at
                        ? activeIncident.created_at.slice(0, 19)
                        : "Recently"}
                    </strong>
                  </div>
                </div>

                <div className="progress-area">
                  <div className="progress-label">
                    <span>Investigation progress</span>
                    <strong>Ready for Analysis</strong>
                  </div>

                  <div className="progress">
                    <div
                      className="progress-fill"
                      style={{ width: "35%" }}
                    ></div>
                  </div>
                </div>

                <button
                  className="investigate-button"
                  onClick={() => {
                    setSelectedIncidentId(activeIncident.id);
                    setCurrentView("investigation");
                  }}
                >
                  Open Investigation →
                </button>
              </section>
            ) : (
              <div className="incident-card empty-card">
                <h3>No Incidents in Database</h3>
                <p>
                  No runtime failures have been ingested yet. Trigger a
                  simulated failure to ingest telemetry into SQLite.
                </p>
                <button
                  className="investigate-button"
                  onClick={handleTriggerSimulatedIncident}
                >
                  + Ingest Test Failure (POST /checkout)
                </button>
              </div>
            )}

            {/* Investigation pipeline */}
            <section className="pipeline-section">
              <div className="section-header">
                <div>
                  <p className="eyebrow">VERDICT PIPELINE</p>
                  <h3>Investigation lifecycle</h3>
                </div>
              </div>

              <div className="pipeline">
                <div className="pipeline-step completed">
                  <div className="step-number">✓</div>
                  <strong>Incident</strong>
                  <span>
                    {activeIncident
                      ? `#${activeIncident.id} Ingested`
                      : "Pending"}
                  </span>
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
                  <strong>Graph & RCA</strong>
                  <span>Pending</span>
                </div>

                <div className="connector"></div>

                <div className="pipeline-step">
                  <div className="step-number">4</div>
                  <strong>Fix Engine</strong>
                  <span>3 Candidates</span>
                </div>

                <div className="connector"></div>

                <div className="pipeline-step">
                  <div className="step-number">5</div>
                  <strong>Approval Gate</strong>
                  <span>Pending</span>
                </div>

                <div className="connector"></div>

                <div className="pipeline-step">
                  <div className="step-number">6</div>
                  <strong>Sentinel & PR</strong>
                  <span>Pending</span>
                </div>
              </div>
            </section>

            {/* Recent incidents */}
            <section className="recent-section">
              <div className="section-header">
                <div>
                  <p className="eyebrow">RECENT ACTIVITY</p>
                  <h3>Recent incidents</h3>
                </div>

                <button
                  className="view-all"
                  onClick={handleTriggerSimulatedIncident}
                >
                  + Trigger New Incident
                </button>
              </div>

              <div className="table">
                <div className="table-row table-head">
                  <span>INCIDENT</span>
                  <span>SERVICE</span>
                  <span>STATUS</span>
                  <span>TIME</span>
                </div>

                {incidents.length === 0 ? (
                  <div className="table-empty">
                    No incidents stored in SQLite. Click "+ Trigger New
                    Incident" to test.
                  </div>
                ) : (
                  incidents.map((inc) => (
                    <div
                      key={inc.id}
                      className={`table-row clickable ${
                        selectedIncidentId === inc.id ? "selected" : ""
                      }`}
                      onClick={() => {
                        setSelectedIncidentId(inc.id);
                        setCurrentView("investigation");
                      }}
                    >
                      <span>
                        <strong>#{inc.id}</strong>
                        <small>
                          {inc.http_method} {inc.endpoint}
                        </small>
                      </span>
                      <span>{inc.service}</span>
                      <span
                        className={`status ${
                          inc.status_code >= 500
                            ? "investigating-status"
                            : "resolved-status"
                        }`}
                      >
                        HTTP {inc.status_code}
                      </span>
                      <span>
                        {inc.created_at
                          ? inc.created_at.slice(11, 16)
                          : inc.timestamp
                          ? inc.timestamp.slice(11, 16)
                          : "Now"}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;