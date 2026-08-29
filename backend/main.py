import json
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
from ingestion import normalize_and_redact_incident
from evidence_collector import collect_evidence
from evidence_graph import build_incident_graph
from rca_engine import analyze_incident_rca
from impact_analysis import analyze_blast_radius
from fix_engine import generate_candidate_fixes
from approval import ApprovalRequest, get_approval_state, process_approval_decision

# Simple regex for email format validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Supported Evidence Graph Node Types
SUPPORTED_NODE_TYPES = {
    "api_request",
    "endpoint",
    "exception",
    "stack_trace",
    "function",
    "source_file",
    "git_blame",
    "commit",
    "diff",
    "deploy",
    "past_incident",
    "test_result",
}


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


class GraphNodeCreate(BaseModel):
    node_type: str = Field(..., min_length=1, description="Supported type of node in the evidence graph")
    label: str = Field(..., min_length=1, description="Human-readable label for this graph node")
    data: Optional[Any] = Field(None, description="Optional JSON-compatible metadata or payload")

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        v_stripped = v.strip().lower()
        if not v_stripped:
            raise ValueError("node_type cannot be empty or whitespace only")
        if v_stripped not in SUPPORTED_NODE_TYPES:
            raise ValueError(f"Unsupported node_type '{v}'. Must be one of: {sorted(SUPPORTED_NODE_TYPES)}")
        return v_stripped

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("label cannot be empty or whitespace only")
        return v_stripped


class GraphEdgeCreate(BaseModel):
    source_node_id: int = Field(..., description="ID of source node in the graph")
    target_node_id: int = Field(..., description="ID of target node in the graph")
    relationship: str = Field(..., min_length=1, description="Description of the relationship")

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("relationship cannot be empty or whitespace only")
        return v_stripped


class IncidentIngestRequest(BaseModel):
    service: str = Field(..., min_length=1, description="Originating service name")
    environment: str = Field(..., min_length=1, description="Deployment environment (e.g. 'production', 'staging')")
    endpoint: str = Field(..., min_length=1, description="Failing HTTP endpoint")
    http_method: str = Field(..., min_length=1, description="HTTP method (GET, POST, etc.)")
    status_code: int = Field(..., description="HTTP status code (e.g. 500)")
    exception_type: str = Field(..., min_length=1, description="Exception class name")
    exception_message: str = Field(..., min_length=1, description="Exception error message")
    stack_trace: str = Field(..., min_length=1, description="Stack trace or traceback log")
    request_id: Optional[str] = Field(None, description="Optional request correlation ID")
    timestamp: Optional[str] = Field(None, description="Optional timestamp of the incident")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata object")

    @field_validator(
        "service",
        "environment",
        "endpoint",
        "http_method",
        "exception_type",
        "exception_message",
        "stack_trace",
    )
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return v_stripped


class CollectEvidenceRequest(BaseModel):
    verdict_id: Optional[int] = Field(None, description="Optional verdict ID to link and persist collected evidence")


class BuildGraphRequest(BaseModel):
    verdict_id: Optional[int] = Field(None, description="Optional verdict ID to link and store the evidence graph")


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
def create_evidence_entry(verdict_id: int, payload: EvidenceCreate):
    """
    Create an evidence record linked to a verdict.
    Returns HTTP 404 if the verdict does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

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
# Evidence Graph Endpoints
# ---------------------------------------------------------------------------

@app.post("/verdicts/{verdict_id}/graph/nodes", status_code=status.HTTP_201_CREATED)
def create_graph_node(verdict_id: int, payload: GraphNodeCreate):
    """
    Create a graph node for an existing verdict.
    Returns HTTP 201 with created node data.
    Returns HTTP 404 if the verdict does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate verdict existence
    cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict with ID {verdict_id} not found"
        )

    data_str = json.dumps(payload.data) if payload.data is not None else None

    try:
        cursor.execute(
            "INSERT INTO evidence_graph_nodes (verdict_id, node_type, label, data) VALUES (?, ?, ?, ?);",
            (verdict_id, payload.node_type, payload.label, data_str)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, verdict_id, node_type, label, data, created_at FROM evidence_graph_nodes WHERE id = ?;",
            (new_id,)
        )
        row = cursor.fetchone()
        node_dict = dict(row)
        if node_dict["data"] is not None:
            try:
                node_dict["data"] = json.loads(node_dict["data"])
            except Exception:
                pass
        return node_dict
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create graph node: {str(exc)}"
        )
    finally:
        conn.close()


@app.get("/verdicts/{verdict_id}/graph")
def get_verdict_graph(verdict_id: int):
    """
    Retrieve the evidence graph (nodes and edges) for a given verdict.
    Returns HTTP 404 if the verdict does not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate verdict existence
    cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict with ID {verdict_id} not found"
        )

    # Fetch nodes
    cursor.execute(
        "SELECT id, verdict_id, node_type, label, data, created_at FROM evidence_graph_nodes WHERE verdict_id = ? ORDER BY id ASC;",
        (verdict_id,)
    )
    node_rows = cursor.fetchall()
    nodes = []
    for r in node_rows:
        nd = dict(r)
        if nd["data"] is not None:
            try:
                nd["data"] = json.loads(nd["data"])
            except Exception:
                pass
        nodes.append(nd)

    # Fetch edges
    cursor.execute(
        "SELECT id, verdict_id, source_node_id, target_node_id, relationship, created_at FROM evidence_graph_edges WHERE verdict_id = ? ORDER BY id ASC;",
        (verdict_id,)
    )
    edge_rows = cursor.fetchall()
    edges = [dict(r) for r in edge_rows]
    conn.close()

    return {
        "verdict_id": verdict_id,
        "nodes": nodes,
        "edges": edges
    }


@app.post("/verdicts/{verdict_id}/graph/edges", status_code=status.HTTP_201_CREATED)
def create_graph_edge(verdict_id: int, payload: GraphEdgeCreate):
    """
    Create a directed relationship/edge between two existing graph nodes.
    Validates that:
    1. The verdict exists.
    2. Both source and target nodes exist and belong to the same verdict.
    Returns HTTP 404 if any validation fails.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate verdict existence
    cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict with ID {verdict_id} not found"
        )

    # Validate source and target nodes
    cursor.execute(
        "SELECT id, verdict_id FROM evidence_graph_nodes WHERE id IN (?, ?);",
        (payload.source_node_id, payload.target_node_id)
    )
    rows = cursor.fetchall()
    found_nodes = {r["id"]: r["verdict_id"] for r in rows}

    if payload.source_node_id not in found_nodes:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source node with ID {payload.source_node_id} not found"
        )

    if payload.target_node_id not in found_nodes:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target node with ID {payload.target_node_id} not found"
        )

    if found_nodes[payload.source_node_id] != verdict_id:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source node {payload.source_node_id} does not belong to verdict {verdict_id}"
        )

    if found_nodes[payload.target_node_id] != verdict_id:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target node {payload.target_node_id} does not belong to verdict {verdict_id}"
        )

    try:
        cursor.execute(
            "INSERT INTO evidence_graph_edges (verdict_id, source_node_id, target_node_id, relationship) VALUES (?, ?, ?, ?);",
            (verdict_id, payload.source_node_id, payload.target_node_id, payload.relationship)
        )
        conn.commit()
        new_edge_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, verdict_id, source_node_id, target_node_id, relationship, created_at FROM evidence_graph_edges WHERE id = ?;",
            (new_edge_id,)
        )
        row = cursor.fetchone()
        return dict(row)
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create graph edge: {str(exc)}"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Incident Ingestion & Evidence Collection Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ingest", status_code=status.HTTP_201_CREATED)
def ingest_incident(payload: IncidentIngestRequest):
    """
    Ingest a new runtime failure or regression incident.
    Normalizes data, redacts sensitive secrets/tokens, and stores in SQLite.
    """
    # Normalize and redact the incoming payload
    normalized = normalize_and_redact_incident(payload.model_dump())

    conn = get_db_connection()
    cursor = conn.cursor()
    metadata_json = json.dumps(normalized["metadata"]) if normalized["metadata"] is not None else None

    try:
        cursor.execute("""
            INSERT INTO incidents (
                service, environment, endpoint, http_method, status_code,
                exception_type, exception_message, stack_trace, request_id,
                timestamp, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            normalized["service"],
            normalized["environment"],
            normalized["endpoint"],
            normalized["http_method"],
            normalized["status_code"],
            normalized["exception_type"],
            normalized["exception_message"],
            normalized["stack_trace"],
            normalized["request_id"],
            normalized["timestamp"],
            metadata_json
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM incidents WHERE id = ?;", (new_id,))
        row = cursor.fetchone()
        incident_record = dict(row)
        if incident_record.get("metadata") is not None:
            try:
                incident_record["metadata"] = json.loads(incident_record["metadata"])
            except Exception:
                pass

        return {
            "status": "success",
            "incident_id": new_id,
            "incident": incident_record
        }
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to ingest incident: {str(exc)}"
        )
    finally:
        conn.close()


@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: int):
    """
    Retrieve an ingested incident by ID.
    Returns HTTP 404 if not found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident_record = dict(row)
    if incident_record.get("metadata") is not None:
        try:
            incident_record["metadata"] = json.loads(incident_record["metadata"])
        except Exception:
            pass

    return incident_record


@app.post("/api/v1/incidents/{incident_id}/collect-evidence", status_code=status.HTTP_200_OK)
def collect_incident_evidence(incident_id: int, payload: Optional[CollectEvidenceRequest] = None):
    """
    Collect structured evidence for an incident:
    - Incident Memory (searches historical incidents in SQLite)
    - Safe local/mock GitHub evidence (no network requests)
    - Runtime telemetry / stack trace
    Optionally stores evidence in SQLite if verdict_id is provided.
    """
    verdict_id = payload.verdict_id if payload else None

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    incident_row = cursor.fetchone()
    if incident_row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident = dict(incident_row)
    if incident.get("metadata"):
        try:
            incident["metadata"] = json.loads(incident["metadata"])
        except Exception:
            pass

    # 2. Verify verdict if specified
    if verdict_id is not None:
        cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Verdict with ID {verdict_id} not found"
            )

    try:
        evidence_list = collect_evidence(incident, verdict_id=verdict_id, conn=conn)
        return {
            "status": "success",
            "incident_id": incident_id,
            "evidence_count": len(evidence_list),
            "evidence": evidence_list
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to collect evidence: {str(exc)}"
        )
    finally:
        conn.close()


@app.post("/api/v1/incidents/{incident_id}/build-graph", status_code=status.HTTP_200_OK)
def build_incident_evidence_graph(incident_id: int, payload: Optional[BuildGraphRequest] = None):
    """
    Builds the Evidence Graph for an ingested incident connecting:
    API Request -> Endpoint -> Exception -> Stack Trace -> Function -> Source File
    as well as collected evidence (historical incidents, local GitHub context).
    Persists nodes and edges in SQLite with complete duplicate prevention.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    incident_row = cursor.fetchone()
    if incident_row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident = dict(incident_row)
    if incident.get("metadata"):
        try:
            incident["metadata"] = json.loads(incident["metadata"])
        except Exception:
            pass

    verdict_id = payload.verdict_id if payload else None

    # 2. If no verdict_id provided, find or create one for this incident
    if verdict_id is None:
        verdict_title = f"Incident #{incident_id}: {incident.get('exception_type')} on {incident.get('endpoint')}"
        cursor.execute("SELECT id FROM verdicts WHERE title = ?;", (verdict_title,))
        existing_v = cursor.fetchone()
        if existing_v:
            verdict_id = existing_v["id"]
        else:
            cursor.execute(
                "INSERT INTO verdicts (title, status) VALUES (?, ?);",
                (verdict_title, "investigating")
            )
            conn.commit()
            verdict_id = cursor.lastrowid
    else:
        cursor.execute("SELECT id FROM verdicts WHERE id = ?;", (verdict_id,))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Verdict with ID {verdict_id} not found"
            )

    try:
        # Collect evidence
        collected_evidence = collect_evidence(incident, verdict_id=verdict_id, conn=conn)

        # Build graph with safe duplicate prevention
        graph_result = build_incident_graph(
            incident=incident,
            collected_evidence=collected_evidence,
            verdict_id=verdict_id,
            conn=conn
        )
        return graph_result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to build evidence graph: {str(exc)}"
        )
    finally:
        conn.close()


@app.post("/api/v1/incidents/{incident_id}/analyze", status_code=status.HTTP_200_OK)
def analyze_incident(incident_id: int):
    """
    Executes the deterministic RCA Reasoning & Cross-Examination engine.
    Cross-examines evidence from the incident and its Evidence Graph to evaluate
    and score hypotheses based strictly on proof.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    incident_row = cursor.fetchone()
    if incident_row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident = dict(incident_row)
    if incident.get("metadata"):
        try:
            incident["metadata"] = json.loads(incident["metadata"])
        except Exception:
            pass

    try:
        # Find or create associated verdict
        verdict_title = f"Incident #{incident_id}: {incident.get('exception_type')} on {incident.get('endpoint')}"
        cursor.execute("SELECT id FROM verdicts WHERE title = ?;", (verdict_title,))
        existing_v = cursor.fetchone()
        if existing_v:
            verdict_id = existing_v["id"]
        else:
            cursor.execute(
                "INSERT INTO verdicts (title, status) VALUES (?, ?);",
                (verdict_title, "investigating")
            )
            conn.commit()
            verdict_id = cursor.lastrowid

        # Collect evidence & graph
        collected_evidence = collect_evidence(incident, verdict_id=verdict_id, conn=conn)

        # Build or retrieve graph
        graph_result = build_incident_graph(
            incident=incident,
            collected_evidence=collected_evidence,
            verdict_id=verdict_id,
            conn=conn
        )
        graph = graph_result.get("graph", {"nodes": [], "edges": []})

        # Run deterministic RCA engine
        rca_result = analyze_incident_rca(
            incident=incident,
            graph=graph,
            collected_evidence=collected_evidence
        )
        return rca_result.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to analyze incident: {str(exc)}"
        )
    finally:
        conn.close()


@app.post("/api/v1/incidents/{incident_id}/impact", status_code=status.HTTP_200_OK)
def get_incident_blast_radius(incident_id: int):
    """
    Executes the deterministic Blast-Radius and Scope Assessment engine.
    Extracts affected services, endpoints, functions, and files from the Evidence Graph
    to determine the impact level and scope confidence without hallucination.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    incident_row = cursor.fetchone()
    if incident_row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident = dict(incident_row)
    if incident.get("metadata"):
        try:
            incident["metadata"] = json.loads(incident["metadata"])
        except Exception:
            pass

    try:
        # Find or create associated verdict
        verdict_title = f"Incident #{incident_id}: {incident.get('exception_type')} on {incident.get('endpoint')}"
        cursor.execute("SELECT id FROM verdicts WHERE title = ?;", (verdict_title,))
        existing_v = cursor.fetchone()
        if existing_v:
            verdict_id = existing_v["id"]
        else:
            cursor.execute(
                "INSERT INTO verdicts (title, status) VALUES (?, ?);",
                (verdict_title, "investigating")
            )
            conn.commit()
            verdict_id = cursor.lastrowid

        # Collect evidence & graph
        collected_evidence = collect_evidence(incident, verdict_id=verdict_id, conn=conn)

        # Build or retrieve graph
        graph_result = build_incident_graph(
            incident=incident,
            collected_evidence=collected_evidence,
            verdict_id=verdict_id,
            conn=conn
        )
        graph = graph_result.get("graph", {"nodes": [], "edges": []})

        # Run deterministic Blast Radius analysis
        impact_result = analyze_blast_radius(
            incident=incident,
            graph=graph
        )
        return impact_result.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to analyze incident blast radius: {str(exc)}"
        )
    finally:
        conn.close()


@app.post("/api/v1/incidents/{incident_id}/fixes", status_code=status.HTTP_200_OK)
def get_incident_candidate_fixes(incident_id: int):
    """
    Generates exactly 3 grounded Candidate Fixes (Minimal, Defensive, Structural)
    with validation plans, risk ranking, and a recommended fix proposal.
    Proposals only: does not modify code or open PRs.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    incident_row = cursor.fetchone()
    if incident_row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident = dict(incident_row)
    if incident.get("metadata"):
        try:
            incident["metadata"] = json.loads(incident["metadata"])
        except Exception:
            pass

    try:
        # Find or create associated verdict
        verdict_title = f"Incident #{incident_id}: {incident.get('exception_type')} on {incident.get('endpoint')}"
        cursor.execute("SELECT id FROM verdicts WHERE title = ?;", (verdict_title,))
        existing_v = cursor.fetchone()
        if existing_v:
            verdict_id = existing_v["id"]
        else:
            cursor.execute(
                "INSERT INTO verdicts (title, status) VALUES (?, ?);",
                (verdict_title, "investigating")
            )
            conn.commit()
            verdict_id = cursor.lastrowid

        # Collect evidence & graph
        collected_evidence = collect_evidence(incident, verdict_id=verdict_id, conn=conn)

        # Build or retrieve graph
        graph_result = build_incident_graph(
            incident=incident,
            collected_evidence=collected_evidence,
            verdict_id=verdict_id,
            conn=conn
        )
        graph = graph_result.get("graph", {"nodes": [], "edges": []})

        # Run RCA & Impact analysis
        rca_result = analyze_incident_rca(
            incident=incident,
            graph=graph,
            collected_evidence=collected_evidence
        )
        impact_result = analyze_blast_radius(
            incident=incident,
            graph=graph
        )

        # Generate candidate fixes
        fix_plan = generate_candidate_fixes(
            incident=incident,
            rca_result=rca_result.to_dict(),
            impact_result=impact_result.to_dict()
        )
        return fix_plan.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate candidate fixes: {str(exc)}"
        )
    finally:
        conn.close()


@app.post("/api/v1/incidents/{incident_id}/approval", status_code=status.HTTP_200_OK)
def submit_incident_fix_approval(incident_id: int, payload: ApprovalRequest):
    """
    Submits a human approval or rejection decision for a candidate fix.
    Validates fix_id against the incident's candidate fixes and enforces safe state machine rules.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT * FROM incidents WHERE id = ?;", (incident_id,))
    incident_row = cursor.fetchone()
    if incident_row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    incident = dict(incident_row)
    if incident.get("metadata"):
        try:
            incident["metadata"] = json.loads(incident["metadata"])
        except Exception:
            pass

    try:
        # Obtain candidate fixes for this incident to validate fix_id
        verdict_title = f"Incident #{incident_id}: {incident.get('exception_type')} on {incident.get('endpoint')}"
        cursor.execute("SELECT id FROM verdicts WHERE title = ?;", (verdict_title,))
        v_row = cursor.fetchone()
        verdict_id = v_row["id"] if v_row else None

        collected_evidence = collect_evidence(incident, verdict_id=verdict_id, conn=conn)
        graph_result = build_incident_graph(incident, collected_evidence=collected_evidence, verdict_id=verdict_id, conn=conn)
        graph = graph_result.get("graph", {"nodes": [], "edges": []})

        rca_result = analyze_incident_rca(incident, graph=graph, collected_evidence=collected_evidence)
        impact_result = analyze_blast_radius(incident, graph=graph)
        fix_plan = generate_candidate_fixes(incident, rca_result=rca_result.to_dict(), impact_result=impact_result.to_dict())

        valid_fix_ids = [f.fix_id for f in fix_plan.candidate_fixes]

        # Process approval decision
        decision = process_approval_decision(
            incident_id=incident_id,
            payload=payload,
            valid_fix_ids=valid_fix_ids,
            conn=conn
        )
        return decision
    finally:
        conn.close()


@app.get("/api/v1/incidents/{incident_id}/approval", status_code=status.HTTP_200_OK)
def get_incident_fix_approval(incident_id: int):
    """
    Retrieves the current approval state for an incident.
    Returns status='pending' if no decision has been submitted.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify incident exists
    cursor.execute("SELECT id FROM incidents WHERE id = ?;", (incident_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    try:
        state = get_approval_state(incident_id, conn=conn)
        return state
    finally:
        conn.close()


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
