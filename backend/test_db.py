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
    UserCreate,
    VerdictCreate,
    EvidenceCreate,
    GraphNodeCreate,
    GraphEdgeCreate,
    IncidentIngestRequest,
    CollectEvidenceRequest,
    SUPPORTED_NODE_TYPES,
)
from evidence_collector import (
    collect_evidence,
    collect_github_evidence,
    collect_incident_memory_evidence,
    CollectedEvidence,
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
    # 6. Evidence Graph Tests
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
    # 7. Incident Ingestion & Redaction/Normalization Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 7: Incident Ingestion & Redaction/Normalization]")
    # First create a historical incident (Incident #1)
    past_incident_payload = IncidentIngestRequest(
        service="checkout-service",
        environment="staging",
        endpoint="/checkout",
        http_method="POST",
        status_code=500,
        exception_type="PaymentProcessingError",
        exception_message="Historical failure: Null payment token",
        stack_trace="Traceback: line 20 in charge()",
        metadata={"build": "v1.0.0"}
    )
    past_ingest = ingest_incident(past_incident_payload)
    created_incident_ids.append(past_ingest["incident_id"])
    print(f"[PASS] Ingested historical incident ID={past_ingest['incident_id']}")

    # Now create current incident (Incident #2) with sensitive data to verify redaction
    current_incident_payload = IncidentIngestRequest(
        service="  checkout-service  ",
        environment=" production ",
        endpoint=" checkout ",
        http_method=" post ",
        status_code=500,
        exception_type="PaymentProcessingError",
        exception_message="Failed charging with api_key=sk_live_secret12345",
        stack_trace="Traceback:\n  File 'backend/main.py', line 45\n    headers={'Authorization': 'Bearer eyJhbGciOiJIUzI1NiJ9.secretToken'}",
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
    print(f"[PASS] Ingested current incident ID={curr_inc_id}")

    # -------------------------------------------------------------------
    # 8. Evidence Collector Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 8: Evidence Collector Foundation]")

    # 8a. Safe Mock GitHub Collector (No Network Calls)
    gh_evidence = collect_github_evidence("Yogeshwari1909/Verdict", "backend/main.py", "abc1234")
    assert gh_evidence.source == "github"
    assert gh_evidence.evidence_type == "source_reference"
    assert "abc1234" in gh_evidence.title
    assert gh_evidence.metadata["network_call"] is False
    assert gh_evidence.metadata["is_mock"] is True
    print(f"[PASS] GitHub Collector (Offline/Safe): {gh_evidence.title}")

    # 8b. Incident Memory Collector finding matching historical incident
    curr_inc_record = curr_ingest["incident"]
    conn = get_db_connection()
    memory_matches = collect_incident_memory_evidence(curr_inc_record, conn=conn)
    conn.close()
    assert len(memory_matches) >= 1, "Expected to find past matching incident in Incident Memory"
    matched_id = memory_matches[0].metadata["matched_incident_id"]
    assert matched_id == past_ingest["incident_id"], f"Expected to match incident {past_ingest['incident_id']}, got {matched_id}"
    print(f"[PASS] Incident Memory Collector: found historical incident #{matched_id} for service '{curr_inc_record['service']}'")

    # 8c. Safe handling when no historical incident matches
    unique_incident = {
        "id": 99999,
        "service": "unique_unknown_service_xyz",
        "endpoint": "/non_existent",
        "exception_type": "UnknownCustomError",
        "exception_message": "completely unique message 12345"
    }
    conn = get_db_connection()
    empty_matches = collect_incident_memory_evidence(unique_incident, conn=conn)
    conn.close()
    assert len(empty_matches) == 0
    print(f"[PASS] Incident Memory Collector: safely handled 0 matches without errors")

    # 8d. Test collect_evidence orchestration function
    orchestrated_evidence = collect_evidence(curr_inc_record, verdict_id=None)
    assert len(orchestrated_evidence) >= 2  # Includes memory match + GitHub + runtime telemetry
    sources = [e["source"] for e in orchestrated_evidence]
    assert "github" in sources
    assert "incident_memory" in sources
    assert "runtime_telemetry" in sources
    print(f"[PASS] collect_evidence orchestration returned {len(orchestrated_evidence)} structured evidence items")

    # 8e. Test POST /api/v1/incidents/{incident_id}/collect-evidence endpoint (without verdict_id)
    endpoint_res = collect_incident_evidence(curr_inc_id, None)
    assert endpoint_res["status"] == "success"
    assert endpoint_res["incident_id"] == curr_inc_id
    assert endpoint_res["evidence_count"] >= 3
    print(f"[PASS] POST /api/v1/incidents/{curr_inc_id}/collect-evidence returned {endpoint_res['evidence_count']} evidence items")

    # 8f. Test POST /api/v1/incidents/{incident_id}/collect-evidence with verdict_id to persist in evidence table
    persist_res = collect_incident_evidence(curr_inc_id, CollectEvidenceRequest(verdict_id=created_v1["id"]))
    assert persist_res["status"] == "success"
    
    # Verify records stored in evidence table
    verdict_evidence = get_verdict_evidence(created_v1["id"])
    assert len(verdict_evidence) >= 3
    print(f"[PASS] Persisted collected evidence in SQLite 'evidence' table for verdict {created_v1['id']} (count={len(verdict_evidence)})")

    # 8g. Test missing incident returns HTTP 404
    missing_inc_id = 999999
    try:
        collect_incident_evidence(missing_inc_id, None)
        assert False, "Expected 404 for missing incident"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Missing incident returned HTTP 404 ('{exc.detail}')")

    # -------------------------------------------------------------------
    # 9. Cleanup All Test Records
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
