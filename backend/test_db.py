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
    create_evidence,
    get_verdict_evidence,
    create_graph_node,
    get_verdict_graph,
    create_graph_edge,
    ingest_incident,
    get_incident,
    UserCreate,
    VerdictCreate,
    EvidenceCreate,
    GraphNodeCreate,
    GraphEdgeCreate,
    IncidentIngestRequest,
    SUPPORTED_NODE_TYPES,
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

    cursor.execute("PRAGMA table_info(incidents);")
    incident_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in [
        "id", "service", "environment", "endpoint", "http_method",
        "status_code", "exception_type", "exception_message",
        "stack_trace", "request_id", "timestamp", "metadata", "created_at"
    ]:
        assert col in incident_cols, f"Column '{col}' missing from incidents table"
    print(f"[PASS] 'incidents' schema verified: {list(incident_cols.keys())}")

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
    ev_1 = create_evidence(created_v1["id"], ev_payload_1)
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

    # 7a. Test Successful Ingestion with Normalization & Redaction
    raw_incident_payload = IncidentIngestRequest(
        service="   payment-gateway-service   ",
        environment="  production  ",
        endpoint="  checkout/v1  ",
        http_method="  post  ",
        status_code=500,
        exception_type="  PaymentProcessingError  ",
        exception_message="Failed charging customer with api_key=sk_live_secret123456789 and password='mySuperSecretPassword!'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            "  File '/app/payment.py', line 45, in charge\n"
            "    headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitiveSecretToken'}\n"
            "ValueError: Payment failed with client_secret: 'shh_secret_abc987'"
        ),
        request_id="  req_checkout_98765  ",
        metadata={
            "api_key": "sk_live_998877665544",
            "auth_token": "token_abc_123",
            "user_password": "PlaintextPasswordHere",
            "nested_secrets": {
                "private_key": "-----BEGIN RSA PRIVATE KEY-----",
                "normal_field": "Non-sensitive value"
            },
            "custom_header": "Bearer eyJhbGciOiJIUzI1NiJ9.userAuthJwtToken",
            "request_ip": "192.168.1.1"
        }
    )

    ingest_result = ingest_incident(raw_incident_payload)
    assert ingest_result["status"] == "success"
    assert ingest_result["incident_id"] is not None
    created_incident_ids.append(ingest_result["incident_id"])
    inc = ingest_result["incident"]

    # 7b. Verify Normalization
    assert inc["service"] == "payment-gateway-service", f"Expected trimmed service name, got '{inc['service']}'"
    assert inc["environment"] == "production", f"Expected trimmed environment, got '{inc['environment']}'"
    assert inc["endpoint"] == "/checkout/v1", f"Expected normalized endpoint with leading slash, got '{inc['endpoint']}'"
    assert inc["http_method"] == "POST", f"Expected uppercase HTTP method POST, got '{inc['http_method']}'"
    assert inc["status_code"] == 500
    assert inc["exception_type"] == "PaymentProcessingError"
    assert inc["request_id"] == "req_checkout_98765"
    assert inc["timestamp"] is not None
    print(f"[PASS] Incident normalization verified: service='{inc['service']}', method='{inc['http_method']}', endpoint='{inc['endpoint']}'")

    # 7c. Verify Redaction in exception_message & stack_trace
    assert "sk_live_secret123456789" not in inc["exception_message"], "API key leaked in exception message!"
    assert "mySuperSecretPassword!" not in inc["exception_message"], "Password leaked in exception message!"
    assert "[REDACTED]" in inc["exception_message"]
    print(f"[PASS] Redaction in exception_message: '{inc['exception_message']}'")

    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitiveSecretToken" not in inc["stack_trace"], "Bearer token leaked in stack trace!"
    assert "shh_secret_abc987" not in inc["stack_trace"], "Client secret leaked in stack trace!"
    assert "Bearer [REDACTED]" in inc["stack_trace"]
    print(f"[PASS] Redaction in stack_trace: Bearer token and client_secret redacted")

    # 7d. Verify Redaction in metadata
    meta = inc["metadata"]
    assert meta["api_key"] == "[REDACTED]", f"Expected [REDACTED] for api_key, got {meta['api_key']}"
    assert meta["auth_token"] == "[REDACTED]", f"Expected [REDACTED] for auth_token, got {meta['auth_token']}"
    assert meta["user_password"] == "[REDACTED]", f"Expected [REDACTED] for user_password, got {meta['user_password']}"
    assert meta["nested_secrets"]["private_key"] == "[REDACTED]", "Nested private_key not redacted!"
    assert meta["nested_secrets"]["normal_field"] == "Non-sensitive value"
    assert "Bearer [REDACTED]" in meta["custom_header"]
    assert meta["request_ip"] == "192.168.1.1"
    print(f"[PASS] Redaction in metadata: sensitive keys and Bearer headers redacted")

    # 7e. Retrieve Ingested Incident (GET /api/v1/incidents/{incident_id})
    fetched_incident = get_incident(ingest_result["incident_id"])
    assert fetched_incident["id"] == ingest_result["incident_id"]
    assert fetched_incident["service"] == "payment-gateway-service"
    assert fetched_incident["metadata"]["api_key"] == "[REDACTED]"
    print(f"[PASS] GET /api/v1/incidents/{ingest_result['incident_id']}: retrieved incident correctly")

    # 7f. Missing Incident -> HTTP 404
    missing_inc_id = 999999
    try:
        get_incident(missing_inc_id)
        assert False, "Expected 404 for missing incident"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert str(missing_inc_id) in exc.detail
        print(f"[PASS] GET /api/v1/incidents/{missing_inc_id}: correctly returned HTTP 404")

    # 7g. Validation: Missing / Empty Required Fields
    for field_name in ["service", "environment", "endpoint", "http_method", "exception_type", "exception_message", "stack_trace"]:
        invalid_kwargs = {
            "service": "srv", "environment": "prod", "endpoint": "/ep",
            "http_method": "GET", "status_code": 500, "exception_type": "Err",
            "exception_message": "msg", "stack_trace": "tb"
        }
        invalid_kwargs[field_name] = "   "
        try:
            IncidentIngestRequest(**invalid_kwargs)
            assert False, f"Expected ValidationError for whitespace-only {field_name}"
        except ValidationError:
            pass
    print(f"[PASS] Validation: all 7 required string fields reject empty/whitespace-only input")

    # -------------------------------------------------------------------
    # 8. Cleanup Remaining Test Records
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
