import asyncio
import json
import sqlite3
from pathlib import Path
from starlette.requests import Request

from database import init_db, get_db_connection, DB_PATH
from main import health_check, db_status, checkout


def test_database_creation():
    print("--- Running Database Foundation Tests ---")
    
    # 1. Initialize database
    init_db()
    assert DB_PATH.exists(), f"Database file not found at {DB_PATH}"
    print(f"[PASS] Database file exists at: {DB_PATH}")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 2. Verify tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row["name"] for row in cursor.fetchall()]
    assert "users" in tables, f"'users' table missing from tables: {tables}"
    assert "verdicts" in tables, f"'verdicts' table missing from tables: {tables}"
    print(f"[PASS] Tables created successfully: {tables}")

    # 3. Verify users table schema
    cursor.execute("PRAGMA table_info(users);")
    user_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in ["id", "name", "email", "created_at"]:
        assert col in user_cols, f"Column '{col}' missing from users table"
    print(f"[PASS] 'users' table schema verified: {list(user_cols.keys())}")

    # 4. Verify verdicts table schema
    cursor.execute("PRAGMA table_info(verdicts);")
    verdict_cols = {row["name"]: row["type"] for row in cursor.fetchall()}
    for col in ["id", "user_id", "title", "status", "created_at"]:
        assert col in verdict_cols, f"Column '{col}' missing from verdicts table"
    print(f"[PASS] 'verdicts' table schema verified: {list(verdict_cols.keys())}")

    # 5. Verify row_factory access by column name
    cursor.execute("INSERT OR IGNORE INTO users (name, email) VALUES (?, ?);", ("Test User", "test@verdict.app"))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE email = ?;", ("test@verdict.app",))
    row = cursor.fetchone()
    assert row is not None, "Failed to retrieve inserted test user"
    assert row["name"] == "Test User", f"Expected 'Test User', got {row['name']}"
    assert row["email"] == "test@verdict.app", f"Expected 'test@verdict.app', got {row['email']}"
    print(f"[PASS] Row factory test passed: id={row['id']}, name='{row['name']}', email='{row['email']}'")

    # 6. Verify foreign key relationship
    user_id = row["id"]
    cursor.execute("INSERT INTO verdicts (user_id, title, status) VALUES (?, ?, ?);", (user_id, "Checkout Regression", "open"))
    conn.commit()

    cursor.execute("SELECT * FROM verdicts WHERE user_id = ?;", (user_id,))
    v_row = cursor.fetchone()
    assert v_row is not None, "Failed to retrieve inserted verdict"
    assert v_row["title"] == "Checkout Regression"
    assert v_row["status"] == "open"
    print(f"[PASS] Verdict record created with foreign key user_id={v_row['user_id']}: title='{v_row['title']}'")

    # Clean up test rows
    cursor.execute("DELETE FROM verdicts WHERE id = ?;", (v_row["id"],))
    cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    conn.close()

    print("\n--- Running Endpoint Tests ---")
    
    # 7. Test /health endpoint
    health_res = health_check()
    assert health_res == {"status": "ok", "service": "verdict-backend"}
    print(f"[PASS] GET /health endpoint: {health_res}")

    # 8. Test /db-status endpoint
    db_res = db_status()
    assert db_res == {"database": "connected", "status": "ok"}
    print(f"[PASS] GET /db-status endpoint: {db_res}")

    # 9. Test /checkout failure endpoint
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
        print(f"[PASS] POST /checkout intentional failure: status={res.status_code}, error_type={body['error_type']}")

    asyncio.run(test_checkout())

    print("\nAll database and endpoint tests passed successfully!")


if __name__ == "__main__":
    test_database_creation()
