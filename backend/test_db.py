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
    create_verdict,
    get_all_verdicts,
    get_verdict_by_id,
    VerdictCreate
)


def test_database_and_verdicts_crud():
    print("==================================================")
    print("        VERDICT BACKEND COMPREHENSIVE TESTS       ")
    print("==================================================")
    
    # -------------------------------------------------------------------
    # 1. Database Foundation & Table Verification
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
    # 2. System Status & Existing Endpoints
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
    # 3. Verdicts CRUD Tests
    # -------------------------------------------------------------------
    print("\n[SECTION 3: Verdicts CRUD API]")
    
    # 3a. Create a verdict (POST /verdicts)
    payload_1 = VerdictCreate(title="Login Authentication Failure", status="investigating")
    created_1 = create_verdict(payload_1)
    assert created_1["id"] is not None
    assert created_1["title"] == "Login Authentication Failure"
    assert created_1["status"] == "investigating"
    assert created_1["user_id"] is None
    assert "created_at" in created_1
    verdict_1_id = created_1["id"]
    print(f"[PASS] POST /verdicts (without user_id): ID={verdict_1_id}, title='{created_1['title']}', status='{created_1['status']}'")

    # 3b. Create a second verdict (with user_id)
    # First insert a test user so foreign key is valid
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (name, email) VALUES (?, ?);", ("Alice", "alice@verdict.app"))
    conn.commit()
    cursor.execute("SELECT id FROM users WHERE email = ?;", ("alice@verdict.app",))
    user_id = cursor.fetchone()["id"]
    conn.close()

    payload_2 = VerdictCreate(user_id=user_id, title="Checkout Missing Payment Crash", status="open")
    created_2 = create_verdict(payload_2)
    assert created_2["id"] is not None
    assert created_2["user_id"] == user_id
    assert created_2["title"] == "Checkout Missing Payment Crash"
    assert created_2["status"] == "open"
    verdict_2_id = created_2["id"]
    print(f"[PASS] POST /verdicts (with user_id={user_id}): ID={verdict_2_id}, title='{created_2['title']}'")

    # 3c. Get all verdicts (GET /verdicts)
    all_verdicts = get_all_verdicts()
    assert len(all_verdicts) >= 2
    ids = [v["id"] for v in all_verdicts]
    assert verdict_1_id in ids
    assert verdict_2_id in ids
    print(f"[PASS] GET /verdicts: retrieved {len(all_verdicts)} records successfully")

    # 3d. Get one verdict by ID (GET /verdicts/{verdict_id})
    single_verdict = get_verdict_by_id(verdict_1_id)
    assert single_verdict["id"] == verdict_1_id
    assert single_verdict["title"] == "Login Authentication Failure"
    print(f"[PASS] GET /verdicts/{verdict_1_id}: retrieved record matching ID")

    # 3e. 404 for non-existent verdict
    missing_id = 999999
    try:
        get_verdict_by_id(missing_id)
        assert False, "Expected HTTPException 404 for missing verdict"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert str(missing_id) in exc.detail
        print(f"[PASS] GET /verdicts/{missing_id}: correctly returned HTTP 404 ('{exc.detail}')")

    # 3f. Validation: Missing / Empty Title
    try:
        VerdictCreate(title="", status="open")
        assert False, "Expected ValidationError for empty title"
    except ValidationError:
        print("[PASS] Pydantic validation: empty title rejected")

    # 3g. Validation: Whitespace Title
    try:
        create_verdict(VerdictCreate(title="   ", status="open"))
        assert False, "Expected HTTPException 422 for whitespace title"
    except HTTPException as exc:
        assert exc.status_code == 422
        print(f"[PASS] Endpoint validation: whitespace title rejected with HTTP {exc.status_code}")

    # 3h. Validation: Missing / Empty Status
    try:
        VerdictCreate(title="Valid Title", status="")
        assert False, "Expected ValidationError for empty status"
    except ValidationError:
        print("[PASS] Pydantic validation: empty status rejected")

    # -------------------------------------------------------------------
    # Cleanup Test Records
    # -------------------------------------------------------------------
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM verdicts WHERE id IN (?, ?);", (verdict_1_id, verdict_2_id))
    cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    conn.close()
    print("\n[PASS] Test data cleaned up successfully.")

    print("\n==================================================")
    print("      ALL BACKEND TESTS PASSED SUCCESSFULLY!       ")
    print("==================================================")


if __name__ == "__main__":
    test_database_and_verdicts_crud()
