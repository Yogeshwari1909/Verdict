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
        exception_message="Failed charging with api_key=sk_live_secret12345",
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
    # 8. Evidence Collector Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 8: Evidence Collector Foundation]")
    collected = collect_evidence(curr_ingest["incident"], verdict_id=None)
    assert len(collected) >= 3
    sources = [e["source"] for e in collected]
    assert "incident_memory" in sources
    assert "github" in sources
    assert "runtime_telemetry" in sources
    print(f"[PASS] Evidence Collector returned {len(collected)} structured items")

    # -------------------------------------------------------------------
    # 9. Automated Evidence Graph Construction Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 9: Automated Incident Evidence Graph Construction]")

    # 9a. Test Traceback Frame Extraction without hallucination
    sample_trace = (
        "Traceback (most recent call last):\n"
        "  File 'backend/main.py', line 45, in checkout\n"
        "  File 'backend/payment_service.py', line 27, in charge\n"
    )
    extracted_frames = extract_traceback_frames(sample_trace)
    assert len(extracted_frames) == 2
    assert extracted_frames[0]["file_path"] == "backend/main.py"
    assert extracted_frames[0]["function_name"] == "checkout"
    assert extracted_frames[1]["file_path"] == "backend/payment_service.py"
    assert extracted_frames[1]["function_name"] == "charge"
    print(f"[PASS] extract_traceback_frames parsed {len(extracted_frames)} frames accurately without hallucination")

    # 9b. Build Graph via Endpoint (POST /api/v1/incidents/{incident_id}/build-graph)
    graph_res = build_incident_evidence_graph(curr_inc_id, None)
    assert graph_res["status"] == "success"
    assert graph_res["incident_id"] == curr_inc_id
    assert graph_res["verdict_id"] is not None
    created_verdict_ids.append(graph_res["verdict_id"])
    nodes = graph_res["graph"]["nodes"]
    edges = graph_res["graph"]["edges"]
    assert len(nodes) >= 6
    assert len(edges) >= 5
    print(f"[PASS] POST /api/v1/incidents/{curr_inc_id}/build-graph created {len(nodes)} nodes and {len(edges)} edges")

    # 9c. Verify Expected Node Types
    node_types = {n["node_type"] for n in nodes}
    expected_types = {"api_request", "endpoint", "exception", "stack_trace", "function", "source_file", "past_incident"}
    for exp in expected_types:
        assert exp in node_types, f"Expected node type '{exp}' missing from graph: {node_types}"
    print(f"[PASS] All expected node types verified in graph: {sorted(node_types)}")

    # 9d. Verify Expected Relationships
    relationships = {e["relationship"] for e in edges}
    for rel in ["routes_to", "raises", "generates", "occurs_in", "located_in", "matches_pattern"]:
        assert rel in relationships, f"Expected relationship '{rel}' missing from graph edges: {relationships}"
    print(f"[PASS] All expected incident chain relationships verified: {sorted(relationships)}")

    # 9e. Verify Sanitized Data & No Secrets in Graph
    for node in nodes:
        node_str = json.dumps(node)
        assert "sk_live_secret12345" not in node_str, f"Leaked secret in node: {node}"
        assert "eyJhbGciOiJIUzI1NiJ9.secretToken" not in node_str, f"Leaked token in node: {node}"
    print("[PASS] Graph data verified clean: no sensitive tokens or secrets present")

    # 9f. Test Duplicate Prevention Strategy (Idempotency)
    # Calling build-graph again for the same incident/verdict must not duplicate nodes/edges
    graph_res_2 = build_incident_evidence_graph(curr_inc_id, BuildGraphRequest(verdict_id=graph_res["verdict_id"]))
    nodes_2 = graph_res_2["graph"]["nodes"]
    edges_2 = graph_res_2["graph"]["edges"]
    assert len(nodes_2) == len(nodes), f"Duplicate prevention failed! Expected {len(nodes)} nodes, got {len(nodes_2)}"
    assert len(edges_2) == len(edges), f"Duplicate prevention failed! Expected {len(edges)} edges, got {len(edges_2)}"
    print(f"[PASS] Duplicate-prevention verified: repeated graph building produced identical {len(nodes_2)} nodes and {len(edges_2)} edges")

    # 9g. Missing Incident -> 404
    missing_inc_id = 999999
    try:
        build_incident_evidence_graph(missing_inc_id, None)
        assert False, "Expected 404 for missing incident on build-graph"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Missing incident returned HTTP 404 ('{exc.detail}')")

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
