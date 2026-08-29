import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator

from database import get_db_connection


class ApprovalRequest(BaseModel):
    fix_id: str = Field(..., min_length=1, description="The specific candidate fix ID being approved or rejected")
    action: str = Field(..., description="Action: 'approve' or 'reject'")
    approved_by: str = Field(..., min_length=1, description="Identifier of the engineer submitting the decision")

    @field_validator("fix_id")
    @classmethod
    def validate_fix_id(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("fix_id cannot be empty or whitespace only")
        return v_stripped

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v_stripped = v.strip().lower()
        if v_stripped not in ["approve", "reject"]:
            raise ValueError(f"Invalid action '{v}'. Must be 'approve' or 'reject'")
        return v_stripped

    @field_validator("approved_by")
    @classmethod
    def validate_approved_by(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("approved_by cannot be empty or whitespace only")
        return v_stripped


class ApprovalRecord(BaseModel):
    approval_id: Optional[int] = Field(None, description="Approval record ID in database")
    incident_id: int = Field(..., description="Incident ID")
    fix_id: Optional[str] = Field(None, description="Fix ID associated with the decision")
    status: str = Field("pending", description="Approval status: 'pending', 'approved', 'rejected'")
    approved_by: Optional[str] = Field(None, description="User who approved or rejected the fix")
    approved_at: Optional[str] = Field(None, description="Timestamp when the decision occurred")
    created_at: Optional[str] = Field(None, description="Creation timestamp")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def get_approval_state(
    incident_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Retrieve the current approval state for an incident.
    If no decision exists yet, returns status='pending'.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id AS approval_id, incident_id, fix_id, status, approved_by, approved_at, created_at FROM fix_approvals WHERE incident_id = ? ORDER BY id DESC LIMIT 1;",
            (incident_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return {
                "approval_id": None,
                "incident_id": incident_id,
                "fix_id": None,
                "status": "pending",
                "approved_by": None,
                "approved_at": None,
                "created_at": None
            }
        return dict(row)
    finally:
        if should_close:
            conn.close()


def process_approval_decision(
    incident_id: int,
    payload: ApprovalRequest,
    valid_fix_ids: List[str],
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Validates and stores the human approval decision for an incident fix.
    Ensures safe state machine rules:
    - Only valid candidate fixes for this incident can be approved/rejected.
    - Transitions from pending -> approved or pending -> rejected are allowed.
    - Conflicting transitions on already decided records raise HTTP 409 Conflict.
    """
    # 1. Validate fix_id belongs to candidate fixes
    if payload.fix_id not in valid_fix_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fix ID '{payload.fix_id}' is invalid. Must be one of the candidate fixes for incident {incident_id}: {valid_fix_ids}"
        )

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()

        # 2. Check current approval state
        cursor.execute(
            "SELECT id, fix_id, status, approved_by, approved_at, created_at FROM fix_approvals WHERE incident_id = ? ORDER BY id DESC LIMIT 1;",
            (incident_id,)
        )
        existing = cursor.fetchone()

        if existing:
            current_status = existing["status"]
            current_fix = existing["fix_id"]

            if current_status == "approved":
                if payload.action == "approve" and current_fix == payload.fix_id:
                    # Idempotent re-approval
                    return {
                        "approval_id": existing["id"],
                        "incident_id": incident_id,
                        "fix_id": existing["fix_id"],
                        "status": existing["status"],
                        "approved_by": existing["approved_by"],
                        "approved_at": existing["approved_at"],
                        "created_at": existing["created_at"]
                    }
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incident {incident_id} is already approved for fix '{current_fix}'. Conflicting state transition not allowed."
                )

            if current_status == "rejected":
                if payload.action == "reject" and current_fix == payload.fix_id:
                    # Idempotent re-rejection
                    return {
                        "approval_id": existing["id"],
                        "incident_id": incident_id,
                        "fix_id": existing["fix_id"],
                        "status": existing["status"],
                        "approved_by": existing["approved_by"],
                        "approved_at": existing["approved_at"],
                        "created_at": existing["created_at"]
                    }
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incident {incident_id} was already rejected for fix '{current_fix}'. Conflicting state transition not allowed."
                )

        # 3. Store new approval decision
        status_value = "approved" if payload.action == "approve" else "rejected"
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO fix_approvals (incident_id, fix_id, status, approved_by, approved_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (incident_id, payload.fix_id, status_value, payload.approved_by, now_iso)
        )
        conn.commit()
        new_id = cursor.lastrowid

        cursor.execute(
            "SELECT id AS approval_id, incident_id, fix_id, status, approved_by, approved_at, created_at FROM fix_approvals WHERE id = ?;",
            (new_id,)
        )
        return dict(cursor.fetchone())
    finally:
        if should_close:
            conn.close()
