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
    UserCreate,
    VerdictCreate,
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
    print(f"[PASS] Required tables present: {tables}")

    cursor.execute("PRAGMA table_info(users);")
    user_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in ["id", "name", "email", "created_at"]:
        assert col in user_cols, f"Column '{col}' missing from users table"
    print(f"[PASS] 'users' schema verified: {list(user_cols.keys())}")

    cursor.execute("PRAGMA table_info(verdicts);")
    verdict_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in ["id", "user_id", "title", "status", "created_at"]:
        assert col in verdict_cols, f"Column '{col}' missing from verdicts table"
    print(f"[PASS] 'verdicts' schema verified: {list(verdict_cols.keys())}")

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

    # Deliberate failure endpoint test
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
    
    # Track IDs for cleanup
    created_user_ids = []
    created_verdict_ids = []

    # 3a. Create a user (POST /users)
    user_payload_1 = UserCreate(name="Alice Developer", email="alice@verdict.app")
    user_1 = create_user(user_payload_1)
    assert user_1["id"] is not None
    assert user_1["name"] == "Alice Developer"
    assert user_1["email"] == "alice@verdict.app"
    assert "created_at" in user_1
    created_user_ids.append(user_1["id"])
    print(f"[PASS] POST /users: created user ID={user_1['id']}, name='{user_1['name']}', email='{user_1['email']}'")

    # 3b. Create a second user (POST /users)
    user_payload_2 = UserCreate(name="Bob Tester", email="bob@verdict.app")
    user_2 = create_user(user_payload_2)
    assert user_2["id"] is not None
    assert user_2["name"] == "Bob Tester"
    assert user_2["email"] == "bob@verdict.app"
    created_user_ids.append(user_2["id"])
    print(f"[PASS] POST /users: created second user ID={user_2['id']}")

    # 3c. Duplicate Email -> HTTP 409 Conflict
    try:
        create_user(UserCreate(name="Duplicate Alice", email="alice@verdict.app"))
        assert False, "Expected HTTPException 409 on duplicate email"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "already exists" in exc.detail
        print(f"[PASS] POST /users duplicate email: correctly returned HTTP 409 ('{exc.detail}')")

    # 3d. Get all users (GET /users)
    all_users = get_all_users()
    assert len(all_users) >= 2
    user_ids = [u["id"] for u in all_users]
    assert user_1["id"] in user_ids
    assert user_2["id"] in user_ids
    # Verify newest users first (descending ID)
    user_indices = [user_ids.index(user_2["id"]), user_ids.index(user_1["id"])]
    assert user_indices[0] < user_indices[1], "Users should be ordered newest first (descending ID)"
    print(f"[PASS] GET /users: retrieved {len(all_users)} users ordered newest first")

    # 3e. Get one user by ID (GET /users/{user_id})
    fetched_user = get_user_by_id(user_1["id"])
    assert fetched_user["id"] == user_1["id"]
    assert fetched_user["name"] == "Alice Developer"
    assert fetched_user["email"] == "alice@verdict.app"
    print(f"[PASS] GET /users/{user_1['id']}: retrieved user matching ID")

    # 3f. Missing user -> HTTP 404
    missing_user_id = 999999
    try:
        get_user_by_id(missing_user_id)
        assert False, "Expected HTTPException 404 for missing user"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert str(missing_user_id) in exc.detail
        print(f"[PASS] GET /users/{missing_user_id}: correctly returned HTTP 404 ('{exc.detail}')")

    # 3g. Validation: Invalid/Empty Name
    try:
        UserCreate(name="   ", email="valid@verdict.app")
        assert False, "Expected ValidationError for whitespace-only name"
    except ValidationError:
        print("[PASS] Validation: rejected empty/whitespace name")

    try:
        UserCreate(name="", email="valid@verdict.app")
        assert False, "Expected ValidationError for empty string name"
    except ValidationError:
        print("[PASS] Validation: rejected empty string name")

    # 3h. Validation: Invalid Email
    for invalid_email in ["not-an-email", "missing-at-domain.com", "user@", "@domain.com", ""]:
        try:
            UserCreate(name="Valid Name", email=invalid_email)
            assert False, f"Expected ValidationError for invalid email '{invalid_email}'"
        except ValidationError:
            pass
    print("[PASS] Validation: rejected all invalid email formats")

    # -------------------------------------------------------------------
    # 4. Verdicts CRUD Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 4: Verdicts CRUD API]")
    
    # 4a. Create a verdict (POST /verdicts)
    payload_v1 = VerdictCreate(title="Login Authentication Failure", status="investigating")
    created_v1 = create_verdict(payload_v1)
    assert created_v1["id"] is not None
    assert created_v1["title"] == "Login Authentication Failure"
    assert created_v1["status"] == "investigating"
    assert created_v1["user_id"] is None
    assert "created_at" in created_v1
    created_verdict_ids.append(created_v1["id"])
    print(f"[PASS] POST /verdicts (without user_id): ID={created_v1['id']}, title='{created_v1['title']}'")

    # 4b. Create a verdict with valid user_id
    payload_v2 = VerdictCreate(user_id=user_1["id"], title="Checkout Missing Payment Crash", status="open")
    created_v2 = create_verdict(payload_v2)
    assert created_v2["id"] is not None
    assert created_v2["user_id"] == user_1["id"]
    assert created_v2["title"] == "Checkout Missing Payment Crash"
    created_verdict_ids.append(created_v2["id"])
    print(f"[PASS] POST /verdicts (with user_id={user_1['id']}): ID={created_v2['id']}, title='{created_v2['title']}'")

    # 4c. Get all verdicts (GET /verdicts)
    all_verdicts = get_all_verdicts()
    assert len(all_verdicts) >= 2
    v_ids = [v["id"] for v in all_verdicts]
    assert created_v1["id"] in v_ids
    assert created_v2["id"] in v_ids
    print(f"[PASS] GET /verdicts: retrieved {len(all_verdicts)} records successfully")

    # 4d. Get one verdict by ID (GET /verdicts/{verdict_id})
    single_verdict = get_verdict_by_id(created_v1["id"])
    assert single_verdict["id"] == created_v1["id"]
    assert single_verdict["title"] == "Login Authentication Failure"
    print(f"[PASS] GET /verdicts/{created_v1['id']}: retrieved record matching ID")

    # 4e. 404 for non-existent verdict
    missing_v_id = 999999
    try:
        get_verdict_by_id(missing_v_id)
        assert False, "Expected HTTPException 404 for missing verdict"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert str(missing_v_id) in exc.detail
        print(f"[PASS] GET /verdicts/{missing_v_id}: correctly returned HTTP 404 ('{exc.detail}')")

    # 4f. Validation: Empty / Whitespace Verdict Fields
    try:
        VerdictCreate(title="   ", status="open")
        assert False, "Expected ValidationError for whitespace title"
    except ValidationError:
        print("[PASS] Verdict validation: whitespace title rejected")

    try:
        VerdictCreate(title="Valid Title", status="   ")
        assert False, "Expected ValidationError for whitespace status"
    except ValidationError:
        print("[PASS] Verdict validation: whitespace status rejected")

    # -------------------------------------------------------------------
    # 5. Cleanup Test Records
    # -------------------------------------------------------------------
    conn = get_db_connection()
    cursor = conn.cursor()
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
