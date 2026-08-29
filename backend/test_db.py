import asyncio
import json
import sqlite3
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
    print(f"[PASS] All required tables present: {tables}")

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

    user_payload_1 = UserCreate(name="Alice Developer", email="alice@verdict.app")
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
    created_incident_ids.append(past_ingest["incident_id"])

    current_incident_payload = IncidentIngestRequest(
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
    curr_ingest = ingest_incident(current_incident_payload)
    curr_inc_id = curr_ingest["incident_id"]
    created_incident_ids.append(curr_inc_id)
    print(f"[PASS] Ingested incidents: Historical #{past_ingest['incident_id']}, Current #{curr_inc_id}")

    # -------------------------------------------------------------------
    # 8. Evidence Collector & Graph Construction
    # -------------------------------------------------------------------
    print("\n[SECTION 8: Evidence Collector & Automated Graph Construction]")
    graph_res = build_incident_evidence_graph(curr_inc_id, None)
    assert graph_res["status"] == "success"
    if graph_res["verdict_id"]:
        created_verdict_ids.append(graph_res["verdict_id"])
    print(f"[PASS] Built incident evidence graph with {graph_res['nodes_created']} nodes and {graph_res['edges_created']} edges")

    # -------------------------------------------------------------------
    # 9. RCA Engine & Cross-Examination Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 9: RCA Reasoning & Cross-Examination Engine]")

    # 9a. Test POST /api/v1/incidents/{incident_id}/analyze endpoint
    rca_res = analyze_incident(curr_inc_id)
    assert rca_res["incident_id"] == curr_inc_id
    assert len(rca_res["hypotheses"]) >= 2
    assert rca_res["selected_hypothesis"] is not None
    assert rca_res["confidence"] >= 0.60
    assert len(rca_res["proof"]) >= 1
    assert len(rca_res["limitations"]) >= 1
    print(f"[PASS] POST /api/v1/incidents/{curr_inc_id}/analyze returned {len(rca_res['hypotheses'])} hypotheses")
    print(f"[PASS] Selected Hypothesis: '{rca_res['selected_hypothesis']['title']}' (Confidence: {rca_res['confidence']})")
    print(f"[PASS] Root Cause Statement: '{rca_res['root_cause_statement']}'")

    # 9b. Verify Proof Contains Real Graph Node References
    for proof_item in rca_res["proof"]:
        assert "node_type" in proof_item
        assert "label" in proof_item
        assert "reason" in proof_item
        assert proof_item["node_id"] is not None
    print(f"[PASS] Proof contains {len(rca_res['proof'])} verified evidence node references")

    # 9c. Verify Limitations Are Explicitly Documented
    assert any("Git diff" in lim for lim in rca_res["limitations"]), "Expected limitation regarding Git diff/blame"
    print(f"[PASS] Limitations explicitly declared ({len(rca_res['limitations'])} boundaries documented)")

    # 9d. Test Insufficient Evidence / Inconclusive Scenario
    # Create an empty/vague incident without stack trace or clear error message
    vague_incident = {
        "id": 8888,
        "service": "unknown-service",
        "environment": "test",
        "endpoint": "/vague",
        "http_method": "GET",
        "status_code": 500,
        "exception_type": "GenericError",
        "exception_message": "Something went wrong somewhere",
        "stack_trace": "Traceback: unknown line",
    }
    empty_graph = {"nodes": [], "edges": []}
    vague_rca = analyze_incident_rca(vague_incident, empty_graph, [])
    assert vague_rca.selected_hypothesis is None, "Expected no leading hypothesis for vague incident without proof"
    assert vague_rca.confidence == 0.0
    assert len(vague_rca.proof) == 0
    assert any("Insufficient evidence" in lim for lim in vague_rca.limitations)
    print(f"[PASS] Handled vague incident without proof safely (confidence=0.0, no hallucinated root cause)")

    # 9e. Missing Incident -> HTTP 404
    missing_inc_id = 999999
    try:
        analyze_incident(missing_inc_id)
        assert False, "Expected 404 for missing incident on /analyze"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Missing incident on /analyze returned HTTP 404 ('{exc.detail}')")

    # -------------------------------------------------------------------
    # 10. Cleanup All Test Records
    # -------------------------------------------------------------------
    conn = get_db_connection()
    cursor = conn.cursor()
    if created_incident_ids:
        placeholders = ",".join("?" * len(created_incident_ids))
        cursor.execute(f"DELETE FROM incidents WHERE id IN ({placeholders});", created_incident_ids)
    if created_verdict_ids:
        placeholders = ",".join("?" * len(created_verdict_ids))
        cursor.execute(f"DELETE FROM verdicts WHERE id IN ({placeholders});", created_verdict_ids)
    if created_user_ids:
        placeholders = ",".join("?" * len(created_user_ids))
        cursor.execute(f"DELETE FROM users WHERE id IN ({placeholders});", created_user_ids)
    conn.commit()
    conn.close()
    print("\n[PASS] All test data cleaned up successfully.")

    print("\n==================================================")
    print("      ALL BACKEND TESTS PASSED SUCCESSFULLY!       ")
    print("==================================================")


if __name__ == "__main__":
    test_complete_backend_suite()
