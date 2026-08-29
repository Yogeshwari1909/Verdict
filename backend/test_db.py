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
    UserCreate,
    VerdictCreate,
    EvidenceCreate,
    GraphNodeCreate,
    GraphEdgeCreate,
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
    print(f"[PASS] Required tables present: {tables}")

    cursor.execute("PRAGMA table_info(evidence_graph_nodes);")
    node_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in ["id", "verdict_id", "node_type", "label", "data", "created_at"]:
        assert col in node_cols, f"Column '{col}' missing from evidence_graph_nodes table"
    print(f"[PASS] 'evidence_graph_nodes' schema verified: {list(node_cols.keys())}")

    cursor.execute("PRAGMA table_info(evidence_graph_edges);")
    edge_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in ["id", "verdict_id", "source_node_id", "target_node_id", "relationship", "created_at"]:
        assert col in edge_cols, f"Column '{col}' missing from evidence_graph_edges table"
    print(f"[PASS] 'evidence_graph_edges' schema verified: {list(edge_cols.keys())}")

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

    user_payload_1 = UserCreate(name="Alice Developer", email="alice@verdict.app")
    user_1 = create_user(user_payload_1)
    assert user_1["id"] is not None
    created_user_ids.append(user_1["id"])
    print(f"[PASS] POST /users: created user ID={user_1['id']}")

    user_payload_2 = UserCreate(name="Bob Tester", email="bob@verdict.app")
    user_2 = create_user(user_payload_2)
    assert user_2["id"] is not None
    created_user_ids.append(user_2["id"])
    print(f"[PASS] POST /users: created second user ID={user_2['id']}")

    try:
        create_user(UserCreate(name="Duplicate Alice", email="alice@verdict.app"))
        assert False, "Expected 409 on duplicate email"
    except HTTPException as exc:
        assert exc.status_code == 409
        print(f"[PASS] Duplicate email rejected with HTTP 409")

    all_users = get_all_users()
    assert len(all_users) >= 2
    print(f"[PASS] GET /users: retrieved {len(all_users)} users")

    # -------------------------------------------------------------------
    # 4. Verdicts CRUD Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 4: Verdicts CRUD API]")
    
    payload_v1 = VerdictCreate(title="Login Authentication Failure", status="investigating")
    created_v1 = create_verdict(payload_v1)
    assert created_v1["id"] is not None
    created_verdict_ids.append(created_v1["id"])
    print(f"[PASS] POST /verdicts: ID={created_v1['id']}")

    payload_v2 = VerdictCreate(user_id=user_1["id"], title="Checkout Missing Payment Crash", status="open")
    created_v2 = create_verdict(payload_v2)
    assert created_v2["id"] is not None
    created_verdict_ids.append(created_v2["id"])
    print(f"[PASS] POST /verdicts: ID={created_v2['id']}")

    # -------------------------------------------------------------------
    # 5. Evidence Foundation Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 5: Evidence API]")
    ev_payload_1 = EvidenceCreate(
        source="github_pr_102",
        evidence_type="traceback",
        content="ValueError: payment_service.charge: Payment payload is null or missing"
    )
    ev_1 = create_evidence(created_v2["id"], ev_payload_1)
    assert ev_1["id"] is not None
    print(f"[PASS] POST /verdicts/{created_v2['id']}/evidence: created evidence ID={ev_1['id']}")

    ev_list = get_verdict_evidence(created_v2["id"])
    assert len(ev_list) >= 1
    print(f"[PASS] GET /verdicts/{created_v2['id']}/evidence: retrieved {len(ev_list)} items")

    # -------------------------------------------------------------------
    # 6. Evidence Graph Tests (Nodes, Edges, Relationships, Validation)
    # -------------------------------------------------------------------
    print("\n[SECTION 6: Evidence Graph Foundation]")

    # 6a. Verify all 12 supported node_types can be created
    print(f"Supported Node Types ({len(SUPPORTED_NODE_TYPES)}): {sorted(SUPPORTED_NODE_TYPES)}")
    created_nodes = {}
    
    # Create nodes demonstrating the presentation RCA sequence
    flow_steps = [
        ("api_request", "POST /checkout Request", {"payload": {"items": ["item_1"]}}),
        ("endpoint", "checkout endpoint", {"route": "/checkout", "handler": "main.checkout"}),
        ("exception", "ValueError: Payment payload is null", {"type": "ValueError"}),
        ("stack_trace", "Traceback in charge()", {"frame": "payment_service.py:27"}),
        ("function", "PaymentService.charge", {"signature": "charge(payment_data)"}),
        ("source_file", "backend/main.py", {"path": "backend/main.py"}),
        ("git_blame", "Blame commit abc1234", {"author": "dev@verdict.app", "line": 27}),
        ("commit", "feat: refactor payment payload", {"commit_hash": "abc1234"}),
        ("diff", "- payment_data.get('amount') + charge(data)", {"additions": 1, "deletions": 1}),
        ("deploy", "Deploy #42 to Production", {"env": "production", "status": "deployed"}),
        ("past_incident", "Incident #12: Null payment crash", {"incident_id": "INC-12"}),
        ("test_result", "Test failure in checkout_test", {"passed": False, "test": "test_checkout"}),
    ]

    for node_type, label, data in flow_steps:
        node_payload = GraphNodeCreate(node_type=node_type, label=label, data=data)
        node = create_graph_node(created_v2["id"], node_payload)
        assert node["id"] is not None
        assert node["node_type"] == node_type
        assert node["label"] == label
        assert node["data"] == data
        created_nodes[node_type] = node["id"]

    print(f"[PASS] Successfully created all {len(created_nodes)} evidence graph node types for verdict {created_v2['id']}")

    # 6b. Create Edges connecting nodes in the RCA chain
    edge_definitions = [
        (created_nodes["api_request"], created_nodes["endpoint"], "triggers"),
        (created_nodes["endpoint"], created_nodes["function"], "invokes"),
        (created_nodes["function"], created_nodes["exception"], "raises"),
        (created_nodes["exception"], created_nodes["stack_trace"], "generates"),
        (created_nodes["stack_trace"], created_nodes["source_file"], "points_to"),
        (created_nodes["source_file"], created_nodes["git_blame"], "inspected_by"),
        (created_nodes["git_blame"], created_nodes["commit"], "identified_in"),
        (created_nodes["commit"], created_nodes["diff"], "contains"),
        (created_nodes["commit"], created_nodes["deploy"], "deployed_in"),
        (created_nodes["exception"], created_nodes["past_incident"], "matches_pattern"),
        (created_nodes["diff"], created_nodes["test_result"], "validated_by"),
    ]

    created_edge_ids = []
    for src, tgt, rel in edge_definitions:
        edge_payload = GraphEdgeCreate(source_node_id=src, target_node_id=tgt, relationship=rel)
        edge = create_graph_edge(created_v2["id"], edge_payload)
        assert edge["id"] is not None
        assert edge["source_node_id"] == src
        assert edge["target_node_id"] == tgt
        assert edge["relationship"] == rel
        created_edge_ids.append(edge["id"])

    print(f"[PASS] Successfully created {len(created_edge_ids)} graph edges forming RCA chain")

    # 6c. Retrieve Graph (GET /verdicts/{verdict_id}/graph)
    graph = get_verdict_graph(created_v2["id"])
    assert graph["verdict_id"] == created_v2["id"]
    assert len(graph["nodes"]) == len(flow_steps)
    assert len(graph["edges"]) == len(edge_definitions)
    print(f"[PASS] GET /verdicts/{created_v2['id']}/graph: retrieved graph with {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")

    # 6d. Rejection of invalid verdict ID (404)
    missing_vid = 999999
    try:
        create_graph_node(missing_vid, GraphNodeCreate(node_type="endpoint", label="test"))
        assert False, "Expected 404 for invalid verdict on node creation"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Node creation on missing verdict returned HTTP 404")

    try:
        get_verdict_graph(missing_vid)
        assert False, "Expected 404 for invalid verdict on graph retrieval"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Graph retrieval on missing verdict returned HTTP 404")

    try:
        create_graph_edge(missing_vid, GraphEdgeCreate(source_node_id=1, target_node_id=2, relationship="rel"))
        assert False, "Expected 404 for invalid verdict on edge creation"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Edge creation on missing verdict returned HTTP 404")

    # 6e. Rejection of invalid node IDs (404)
    try:
        create_graph_edge(created_v2["id"], GraphEdgeCreate(source_node_id=999999, target_node_id=created_nodes["endpoint"], relationship="test"))
        assert False, "Expected 404 for non-existent source node"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Edge with invalid source node returned HTTP 404 ('{exc.detail}')")

    try:
        create_graph_edge(created_v2["id"], GraphEdgeCreate(source_node_id=created_nodes["api_request"], target_node_id=999999, relationship="test"))
        assert False, "Expected 404 for non-existent target node"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Edge with invalid target node returned HTTP 404 ('{exc.detail}')")

    # 6f. Rejection of nodes belonging to another verdict (404)
    # Create a node on verdict 1 (created_v1)
    other_node = create_graph_node(created_v1["id"], GraphNodeCreate(node_type="endpoint", label="v1 endpoint"))
    try:
        # Try to connect a node from created_v1 with a node from created_v2
        create_graph_edge(created_v2["id"], GraphEdgeCreate(source_node_id=other_node["id"], target_node_id=created_nodes["endpoint"], relationship="cross_connect"))
        assert False, "Expected 404 when connecting nodes belonging to different verdicts"
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f"[PASS] Edge between nodes of different verdicts rejected with HTTP 404 ('{exc.detail}')")

    # 6g. Validation of empty fields & unsupported node_type
    try:
        GraphNodeCreate(node_type="unsupported_type", label="Test")
        assert False, "Expected ValidationError for unsupported node_type"
    except ValidationError:
        print("[PASS] Validation: rejected unsupported node_type")

    try:
        GraphNodeCreate(node_type="", label="Test")
        assert False, "Expected ValidationError for empty node_type"
    except ValidationError:
        print("[PASS] Validation: rejected empty node_type")

    try:
        GraphNodeCreate(node_type="endpoint", label="   ")
        assert False, "Expected ValidationError for whitespace label"
    except ValidationError:
        print("[PASS] Validation: rejected whitespace label")

    try:
        GraphEdgeCreate(source_node_id=1, target_node_id=2, relationship="   ")
        assert False, "Expected ValidationError for whitespace relationship"
    except ValidationError:
        print("[PASS] Validation: rejected whitespace relationship")

    # 6h. Foreign Key Cascade Behavior Test
    # Deleting created_v2 should automatically cascade delete all its nodes and edges
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM verdicts WHERE id = ?;", (created_v2["id"],))
    conn.commit()

    cursor.execute("SELECT id FROM evidence_graph_nodes WHERE verdict_id = ?;", (created_v2["id"],))
    remaining_nodes = cursor.fetchall()
    assert len(remaining_nodes) == 0, f"Expected 0 nodes after verdict cascade delete, found {len(remaining_nodes)}"

    cursor.execute("SELECT id FROM evidence_graph_edges WHERE verdict_id = ?;", (created_v2["id"],))
    remaining_edges = cursor.fetchall()
    assert len(remaining_edges) == 0, f"Expected 0 edges after verdict cascade delete, found {len(remaining_edges)}"
    print(f"[PASS] Foreign key cascade: deleting verdict {created_v2['id']} automatically removed all its nodes and edges")

    conn.close()

    # -------------------------------------------------------------------
    # 7. Cleanup Remaining Test Records
    # -------------------------------------------------------------------
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM verdicts WHERE id = ?;", (created_v1["id"],))
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
