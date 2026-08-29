import re
import sqlite3
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from database import init_db, get_db_connection

# Simple regex for email format validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables on startup
    init_db()
    yield


app = FastAPI(title="Verdict Backend", version="1.0.0", lifespan=lifespan)

# Enable CORS for Next.js frontend (default port 3000) or other clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Required non-empty user name")
    email: str = Field(..., min_length=1, description="Required valid email address")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Name cannot be empty or whitespace only")
        return v_stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v_stripped = v.strip()
        if not EMAIL_REGEX.match(v_stripped):
            raise ValueError(f"'{v}' is not a valid email address")
        return v_stripped.lower()


class VerdictCreate(BaseModel):
    user_id: Optional[int] = Field(None, description="Optional user ID associated with this verdict")
    title: str = Field(..., min_length=1, description="Required title for the verdict")
    status: str = Field(..., min_length=1, description="Required status (e.g. 'open', 'investigating', 'resolved')")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Title cannot be empty or whitespace only")
        return v_stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Status cannot be empty or whitespace only")
        return v_stripped


class EvidenceCreate(BaseModel):
    source: str = Field(..., min_length=1, description="Source of evidence (e.g. 'github_pr', 'log', 'sentry')")
    evidence_type: str = Field(..., min_length=1, description="Type of evidence (e.g. 'traceback', 'diff', 'metrics')")
    content: str = Field(..., min_length=1, description="The content of the evidence")

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Source cannot be empty or whitespace only")
        return v_stripped

    @field_validator("evidence_type")
    @classmethod
    def validate_evidence_type(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Evidence type cannot be empty or whitespace only")
        return v_stripped

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Content cannot be empty or whitespace only")
        return v_stripped


# ---------------------------------------------------------------------------
# Mock Payment Service
# ---------------------------------------------------------------------------

class PaymentService:
    def charge(self, payment_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Simulate payment processing.
        Raises ValueError if payment data is missing, null, or lacks an amount.
        """
        if payment_data is None:
            raise ValueError("payment_service.charge: Payment payload is null or missing")
        
        if not isinstance(payment_data, dict):
            raise TypeError(f"payment_service.charge: Expected dict for payment_data, got {type(payment_data).__name__}")

        amount = payment_data.get("amount")
        if amount is None or amount <= 0:
            raise ValueError(f"payment_service.charge: Invalid or missing payment amount: {amount}")

        return {
            "status": "charged",
            "amount": amount,
            "transaction_id": "txn_mock_verdict_12345"
        }


payment_service = PaymentService()


# ---------------------------------------------------------------------------
# Health & Status Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Health check route."""
    return {
        "status": "ok",
        "service": "verdict-backend"
    }


@app.get("/db-status")
def db_status():
    """Database connectivity status check."""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        return {
            "database": "connected",
            "status": "ok"
        }
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "database": "error",
                "status": "failed",
                "detail": str(exc)
            }
        )


# ---------------------------------------------------------------------------
# Users Endpoints
# ---------------------------------------------------------------------------

@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate):
    """
    Create a new user in SQLite.
    Returns HTTP 201 with created user data.
    Returns HTTP 409 if the email already exists.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email) VALUES (?, ?);",
            (payload.name, payload.email)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?;",
            (new_id,)
        )
        row = cursor.fetchone()
        return dict(row)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        error_msg = str(exc)
        if "UNIQUE constraint failed: users.email" in error_msg or "UNIQUE" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{payload.email}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database integrity error: {error_msg}"
        )
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create user: {str(exc)}"
        )
    finally:
        conn.close()


@app.get("/users")
def get_all_users():
    """
    Retrieve all users ordered by newest first.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, created_at FROM users ORDER BY id DESC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/users/{user_id}")
def get_user_by_id(user_id: int):
    """
    Retrieve a single user by ID.
    Returns HTTP 404 if the user does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?;",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return dict(row)


# ---------------------------------------------------------------------------
# Verdicts CRUD Endpoints
# ---------------------------------------------------------------------------

@app.post("/verdicts", status_code=status.HTTP_201_CREATED)
def create_verdict(payload: VerdictCreate):
    """
    Create a new verdict record in SQLite using parameterized queries.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO verdicts (user_id, title, status) VALUES (?, ?, ?);",
            (payload.user_id, payload.title, payload.status)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, user_id, title, status, created_at FROM verdicts WHERE id = ?;",
            (new_id,)
        )
        row = cursor.fetchone()
        return dict(row)
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create verdict: {str(exc)}"
        )
    finally:
        conn.close()


@app.get("/verdicts")
def get_all_verdicts():
    """
    Retrieve all verdict records ordered by newest first.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, title, status, created_at FROM verdicts ORDER BY id DESC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/verdicts/{verdict_id}")
def get_verdict_by_id(verdict_id: int):
    """
    Retrieve a single verdict record by ID using parameterized query.
    Returns HTTP 404 if the record does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, title, status, created_at FROM verdicts WHERE id = ?;",
        (verdict_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict with id {verdict_id} not found"
        )
    return dict(row)


# ---------------------------------------------------------------------------
# Evidence Endpoints
# ---------------------------------------------------------------------------

@app.post("/verdicts/{verdict_id}/evidence", status_code=status.HTTP_201_CREATED)
def create_evidence(verdict_id: int, payload: EvidenceCreate):
    """
    Create an evidence record linked to a verdict.
    Returns HTTP 404 if the verdict does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify that the verdict exists
    cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict with ID {verdict_id} not found"
        )

    try:
        cursor.execute(
            "INSERT INTO evidence (verdict_id, source, evidence_type, content) VALUES (?, ?, ?, ?);",
            (verdict_id, payload.source, payload.evidence_type, payload.content)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, verdict_id, source, evidence_type, content, created_at FROM evidence WHERE id = ?;",
            (new_id,)
        )
        row = cursor.fetchone()
        return dict(row)
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create evidence: {str(exc)}"
        )
    finally:
        conn.close()


@app.get("/verdicts/{verdict_id}/evidence")
def get_verdict_evidence(verdict_id: int):
    """
    Retrieve all evidence records for a given verdict.
    Returns HTTP 404 if the verdict does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify that the verdict exists
    cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict with ID {verdict_id} not found"
        )

    cursor.execute(
        "SELECT id, verdict_id, source, evidence_type, content, created_at FROM evidence WHERE verdict_id = ? ORDER BY id ASC;",
        (verdict_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Deliberate Failure Checkout Endpoint (Regression / Demo)
# ---------------------------------------------------------------------------

@app.post("/checkout")
async def checkout(request: Request):
    """
    Deliberate failure checkout endpoint for regression/failure demonstrations.
    Intentionally returns HTTP 500 when payment data is missing/null,
    including a detailed payment_service.charge traceback.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    payment_data = body.get("payment") if isinstance(body, dict) else None

    try:
        # Deliberately invoke payment_service.charge
        charge_result = payment_service.charge(payment_data)
        return {
            "status": "success",
            "order_status": "completed",
            "payment": charge_result
        }
    except Exception as exc:
        # Capture formatted traceback from payment_service.charge failure
        tb_str = traceback.format_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Payment processing failed in checkout",
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "traceback": tb_str
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
