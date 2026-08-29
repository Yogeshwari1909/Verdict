import asyncio
import json
import sqlite3
import uuid
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from database import init_db, get_db_connection, DB_PATH
from main import (
    health_check,
    db_status,
    checkout,
    create_user,
    get_all_users,
    get_user_by_id,
    create_verdict,
    get_all_verdicts,
    get_verdict_by_id,
    create_evidence_entry,
    get_verdict_evidence,
    create_graph_node,
    get_verdict_graph,
    create_graph_edge,
    ingest_incident,
    get_incident,
    collect_incident_evidence,
    build_incident_evidence_graph,
    analyze_incident,
    get_incident_blast_radius,
    get_incident_candidate_fixes,
    submit_incident_fix_approval,
    get_incident_fix_approval,
    create_incident_github_pr,
    check_incident_regression,
    UserCreate,
    VerdictCreate,
    EvidenceCreate,
    GraphNodeCreate,
    GraphEdgeCreate,
    IncidentIngestRequest,
    CollectEvidenceRequest,
    BuildGraphRequest,
    SUPPORTED_NODE_TYPES,
)
from evidence_collector import (
    collect_evidence,
    collect_github_evidence,
    collect_incident_memory_evidence,
    CollectedEvidence,
)
from evidence_graph import (
    build_incident_graph,
    extract_traceback_frames,
)
from rca_engine import (
    analyze_incident_rca,
    Hypothesis,
    RCAResult,
)
from impact_analysis import (
    analyze_blast_radius,
    BlastRadiusResult,
)
from fix_engine import (
    generate_candidate_fixes,
    CandidateFix,
    FixPlanResult,
)
from approval import (
    ApprovalRequest,
    get_approval_state,
    process_approval_decision,
)
from github_integration import (
    GitHubPRCreateRequest,
    GitHubPRResult,
    create_fix_pull_request,
)
from regression_sentinel import (
    RegressionCheckRequest,
    RegressionCheck,
    SentinelResult,
    run_regression_sentinel,
)


def test_complete_backend_suite():
    print("==================================================")
    print("        VERDICT BACKEND COMPREHENSIVE TESTS       ")
    print("==================================================")
    
    # -------------------------------------------------------------------
    # 1. Database Foundation & Schema Verification
    # -------------------------------------------------------------------
    print("\n[SECTION 1: Database Foundation & Schema]")
    init_db()
    assert DB_PATH.exists(), f"Database file not found at {DB_PATH}"
    print(f"[PASS] SQLite database file verified at: {DB_PATH}")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row["name"] for row in cursor.fetchall()]
    assert "users" in tables, f"'users' table missing: {tables}"
    assert "verdicts" in tables, f"'verdicts' table missing: {tables}"
    assert "evidence" in tables, f"'evidence' table missing: {tables}"
    assert "evidence_graph_nodes" in tables, f"'evidence_graph_nodes' table missing: {tables}"
    assert "evidence_graph_edges" in tables, f"'evidence_graph_edges' table missing: {tables}"
    assert "incidents" in tables, f"'incidents' table missing: {tables}"
    assert "fix_approvals" in tables, f"'fix_approvals' table missing: {tables}"
    print(f"[PASS] All required tables present: {tables}")

    # Initial safety cleanup respecting foreign keys
    cursor.execute("DELETE FROM fix_approvals;")
    cursor.execute("DELETE FROM evidence_graph_edges;")
    cursor.execute("DELETE FROM evidence_graph_nodes;")
    cursor.execute("DELETE FROM evidence;")
    cursor.execute("DELETE FROM verdicts WHERE title LIKE 'Incident #%' OR title LIKE 'Checkout Missing%';")
    cursor.execute("DELETE FROM users WHERE email LIKE '%@verdict.app';")
    cursor.execute("DELETE FROM incidents WHERE service = 'checkout-service';")
    conn.commit()
    conn.close()

    # -------------------------------------------------------------------
    # 2. System Status & Deliberate Failure Endpoints
    # -------------------------------------------------------------------
    print("\n[SECTION 2: System Status Endpoints]")
    health_res = health_check()
    assert health_res == {"status": "ok", "service": "verdict-backend"}
    print(f"[PASS] GET /health: {health_res}")

    db_res = db_status()
    assert db_res == {"database": "connected", "status": "ok"}
    print(f"[PASS] GET /db-status: {db_res}")

    async def test_checkout():
        scope = {"type": "http", "method": "POST", "headers": [(b"content-type", b"application/json")]}
        async def receive():
            return {"type": "http.request", "body": b'{"items": ["item_1"]}'}
        req = Request(scope, receive)
        res = await checkout(req)
        assert res.status_code == 500
        body = json.loads(res.body.decode())
        assert body["status"] == "error"
        assert "payment_service.charge" in body["traceback"]
        print(f"[PASS] POST /checkout deliberate failure: HTTP {res.status_code} ({body['error_type']})")

    asyncio.run(test_checkout())

    # -------------------------------------------------------------------
    # 3. Users API Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 3: Users API]")
    created_user_ids = []
    created_verdict_ids = []
    created_incident_ids = []

    user_email = f"alice_{uuid.uuid4().hex[:6]}@verdict.app"
    user_payload_1 = UserCreate(name="Alice Developer", email=user_email)
    user_1 = create_user(user_payload_1)
    assert user_1["id"] is not None
    created_user_ids.append(user_1["id"])
    print(f"[PASS] POST /users: created user ID={user_1['id']}")

    # -------------------------------------------------------------------
    # 4. Verdicts CRUD Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 4: Verdicts CRUD API]")
    payload_v1 = VerdictCreate(user_id=user_1["id"], title="Checkout Missing Payment Crash", status="open")
    created_v1 = create_verdict(payload_v1)
    assert created_v1["id"] is not None
    created_verdict_ids.append(created_v1["id"])
    print(f"[PASS] POST /verdicts: ID={created_v1['id']}")

    # -------------------------------------------------------------------
    # 5. Evidence Foundation Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 5: Evidence API]")
    ev_payload_1 = EvidenceCreate(
        source="github_pr_102",
        evidence_type="traceback",
        content="ValueError: payment_service.charge: Payment payload is null or missing"
    )
    ev_1 = create_evidence_entry(created_v1["id"], ev_payload_1)
    assert ev_1["id"] is not None
    print(f"[PASS] POST /verdicts/{created_v1['id']}/evidence: created evidence ID={ev_1['id']}")

    # -------------------------------------------------------------------
    # 6. Evidence Graph Tests (Manual Nodes & Edges)
    # -------------------------------------------------------------------
    print("\n[SECTION 6: Evidence Graph Foundation]")
    node_1 = create_graph_node(created_v1["id"], GraphNodeCreate(node_type="api_request", label="POST /checkout"))
    node_2 = create_graph_node(created_v1["id"], GraphNodeCreate(node_type="endpoint", label="/checkout route"))
    edge_1 = create_graph_edge(created_v1["id"], GraphEdgeCreate(source_node_id=node_1["id"], target_node_id=node_2["id"], relationship="triggers"))
    assert edge_1["id"] is not None
    graph = get_verdict_graph(created_v1["id"])
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    print(f"[PASS] Graph node & edge created and retrieved successfully for verdict {created_v1['id']}")

    # -------------------------------------------------------------------
    # 7. Incident Ingestion & Redaction Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 7: Incident Ingestion & Redaction]")
    past_incident_payload = IncidentIngestRequest(
        service="checkout-service",
        environment="staging",
        endpoint="/checkout",
        http_method="POST",
        status_code=500,
        exception_type="PaymentProcessingError",
        exception_message="Historical failure: Null payment token",
        stack_trace="Traceback:\n  File 'backend/payment.py', line 20, in process_token",
        metadata={"build": "v1.0.0"}
    )
    past_ingest = ingest_incident(past_incident_payload)
    past_inc_id = past_ingest["incident_id"]
    created_incident_ids.append(past_inc_id)

    prod_incident_payload = IncidentIngestRequest(
        service="checkout-service",
        environment="production",
        endpoint="/checkout",
        http_method="post",
        status_code=500,
        exception_type="PaymentProcessingError",
        exception_message="Failed charging with api_key=sk_live_secret12345: Payment payload is null or missing",
        stack_trace=(
            "Traceback (most recent call last):\n"
            "  File 'backend/main.py', line 45, in checkout\n"
            "    charge_res = payment_service.charge(payment_data)\n"
            "  File 'backend/payment_service.py', line 27, in charge\n"
            "    raise ValueError('Payment payload is null with token: Bearer eyJhbGciOiJIUzI1NiJ9.secretToken')"
        ),
        request_id="req_9876",
        metadata={
            "api_key": "sk_live_998877",
            "repository": "Yogeshwari1909/Verdict",
            "commit_sha": "abc123456789"
        }
    )
    prod_ingest = ingest_incident(prod_incident_payload)
    prod_inc_id = prod_ingest["incident_id"]
    created_incident_ids.append(prod_inc_id)
    print(f"[PASS] Ingested incidents: Historical #{past_inc_id} (staging), Current #{prod_inc_id} (production)")

    # -------------------------------------------------------------------
    # 8. Evidence Collector & Graph Construction
    # -------------------------------------------------------------------
    print("\n[SECTION 8: Evidence Collector & Automated Graph Construction]")
    graph_res = build_incident_evidence_graph(prod_inc_id, None)
    assert graph_res["status"] == "success"
    if graph_res["verdict_id"]:
        created_verdict_ids.append(graph_res["verdict_id"])
    print(f"[PASS] Built incident evidence graph with {graph_res['nodes_created']} nodes and {graph_res['edges_created']} edges")

    # -------------------------------------------------------------------
    # 9. RCA Engine & Cross-Examination Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 9: RCA Reasoning & Cross-Examination Engine]")
    rca_res = analyze_incident(prod_inc_id)
    assert rca_res["incident_id"] == prod_inc_id
    assert len(rca_res["hypotheses"]) >= 2
    assert rca_res["selected_hypothesis"] is not None
    assert rca_res["confidence"] >= 0.60
    assert len(rca_res["proof"]) >= 1
    print(f"[PASS] RCA Engine verified: Selected '{rca_res['selected_hypothesis']['title']}' (RCA Confidence: {rca_res['confidence']})")

    # -------------------------------------------------------------------
    # 10. Blast Radius & Scope Assessment Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 10: Blast Radius & Impact Analysis Engine]")
    impact_res = get_incident_blast_radius(prod_inc_id)
    assert impact_res["incident_id"] == prod_inc_id
    assert impact_res["impact_level"] == "high"
    assert impact_res["confidence"] >= 0.75
    assert len(impact_res["evidence_references"]) >= 4
    print(f"[PASS] Blast Radius verified: level='{impact_res['impact_level']}', scope_confidence={impact_res['confidence']}")

    # -------------------------------------------------------------------
    # 11. Candidate Fixes & Validation Planning Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 11: Candidate Fixes & Validation Planning Engine]")
    fix_res = get_incident_candidate_fixes(prod_inc_id)
    assert fix_res["incident_id"] == prod_inc_id
    assert len(fix_res["candidate_fixes"]) == 3
    assert fix_res["recommended_fix"] is not None
    print(f"[PASS] Fix Engine generated 3 candidate fixes. Recommended: '{fix_res['recommended_fix']['title']}'")

    # -------------------------------------------------------------------
    # 12. Human Approval Gate Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 12: Human Approval Gate]")
    init_approval = get_incident_fix_approval(prod_inc_id)
    assert init_approval["status"] == "pending"

    approve_req = ApprovalRequest(
        fix_id="fix_defensive",
        action="approve",
        approved_by="staff_sre@verdict.app"
    )
    approved_res = submit_incident_fix_approval(prod_inc_id, approve_req)
    assert approved_res["status"] == "approved"
    assert approved_res["fix_id"] == "fix_defensive"
    print(f"[PASS] Human approval gate approved 'fix_defensive' for incident #{prod_inc_id}")

    # -------------------------------------------------------------------
    # 13. GitHub PR Integration Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 13: GitHub PR Integration & Safety Gate]")
    unapproved_pr_req = GitHubPRCreateRequest(fix_id="fix_minimal")
    try:
        create_incident_github_pr(past_inc_id, unapproved_pr_req)
        assert False, "Expected 412 Precondition Failed for unapproved incident"
    except HTTPException as exc:
        assert exc.status_code == 412
        print(f"[PASS] Unapproved incident PR blocked safely: HTTP 412 ('{exc.detail}')")

    valid_pr_req = GitHubPRCreateRequest(fix_id="fix_defensive")
    pr_preview = create_incident_github_pr(prod_inc_id, valid_pr_req)
    assert pr_preview["status"] == "dry_run"
    assert pr_preview["github_url"] is None
    print(f"[PASS] Approved fix passed gate in DRY-RUN mode (github_url=null, 0 network requests)")

    # -------------------------------------------------------------------
    # 14. Regression Sentinel Validation Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 14: Regression Sentinel Engine]")

    # 14a. Unapproved incident regression check -> HTTP 412 Precondition Failed
    unapproved_sentinel_req = RegressionCheckRequest(fix_id="fix_minimal")
    try:
        check_incident_regression(past_inc_id, unapproved_sentinel_req)
        assert False, "Expected 412 Precondition Failed for unapproved regression check"
    except HTTPException as exc:
        assert exc.status_code == 412
        print(f"[PASS] Unapproved regression check blocked safely: HTTP 412 ('{exc.detail}')")

    # 14b. Mismatched fix ID regression check -> HTTP 400 Bad Request
    mismatched_sentinel_req = RegressionCheckRequest(fix_id="fix_minimal")
    try:
        check_incident_regression(prod_inc_id, mismatched_sentinel_req)
        assert False, "Expected 400 Bad Request for mismatched fix ID"
    except HTTPException as exc:
        assert exc.status_code == 400
        print(f"[PASS] Mismatched fix ID blocked safely: HTTP 400 ('{exc.detail}')")

    # 14c. Approved fix executes Regression Sentinel checks
    approved_sentinel_req = RegressionCheckRequest(fix_id="fix_defensive")
    sentinel_res = check_incident_regression(prod_inc_id, approved_sentinel_req)
    assert sentinel_res["incident_id"] == prod_inc_id
    assert sentinel_res["fix_id"] == "fix_defensive"
    assert sentinel_res["status"] == "passed"
    assert sentinel_res["safe_to_merge"] is True
    assert len(sentinel_res["regressions_detected"]) == 0
    assert len(sentinel_res["checks"]) >= 4
    print(f"[PASS] POST /api/v1/incidents/{prod_inc_id}/regression-check: status='passed', safe_to_merge=True")

    # 14d. Verify specific check statuses (passed and skipped)
    check_statuses = {c["check_id"]: c["status"] for c in sentinel_res["checks"]}
    assert check_statuses.get("check_db_connectivity") == "passed"
    assert check_statuses.get("check_system_health") == "passed"
    assert check_statuses.get("check_positive_control") == "passed"
    assert check_statuses.get("check_boundary_validation") == "passed"
    assert check_statuses.get("check_production_load_traffic") == "skipped"
    print(f"[PASS] Verified check status breakdown: {check_statuses}")

    # 14e. Verify evidence references in checks
    for c in sentinel_res["checks"]:
        assert c["evidence_reference"] is not None
        assert len(c["expected_result"]) > 0
        assert len(c["actual_result"]) > 0
    print(f"[PASS] All {len(sentinel_res['checks'])} regression checks contain grounded evidence references and expected/actual assertions")

    # 14f. Missing Incident -> HTTP 404
    missing_inc_id = 999999
    try:
        check_incident_regression(missing_inc_id, approved_sentinel_req)
        assert False, "Expected 404 for missing incident on POST /regression-check"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Missing incident on POST /regression-check returned HTTP 404 ('{exc.detail}')")

    # -------------------------------------------------------------------
    # 15. Cleanup All Test Records
    # -------------------------------------------------------------------
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fix_approvals;")
    cursor.execute("DELETE FROM evidence_graph_edges;")
    cursor.execute("DELETE FROM evidence_graph_nodes;")
    cursor.execute("DELETE FROM evidence;")
    if created_incident_ids:
        placeholders = ",".join("?" * len(created_incident_ids))
        cursor.execute(f"DELETE FROM incidents WHERE id IN ({placeholders});", created_incident_ids)
    if created_verdict_ids:
        placeholders = ",".join("?" * len(created_verdict_ids))
        cursor.execute(f"DELETE FROM verdicts WHERE id IN ({placeholders});", created_verdict_ids)
    if created_user_ids:
        placeholders = ",".join("?" * len(created_user_ids))
        cursor.execute(f"DELETE FROM users WHERE id IN ({placeholders});", created_user_ids)
    cursor.execute("DELETE FROM verdicts WHERE title LIKE 'Incident #%';")
    conn.commit()
    conn.close()
    print("\n[PASS] All test data cleaned up successfully.")

    print("\n==================================================")
    print("      ALL BACKEND TESTS PASSED SUCCESSFULLY!       ")
    print("==================================================")


if __name__ == "__main__":
    test_complete_backend_suite()
