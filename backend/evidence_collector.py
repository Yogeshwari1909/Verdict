import json
import re
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from database import get_db_connection


class CollectedEvidence(BaseModel):
    """
    Common evidence model across all collector sources.
    """
    source: str = Field(..., description="Source of evidence ('github', 'incident_memory', 'runtime_telemetry')")
    evidence_type: str = Field(..., description="Type of evidence ('source_reference', 'past_incident', 'stack_trace')")
    title: str = Field(..., description="Human-readable title describing the evidence item")
    content: str = Field(..., description="The main text or serialized content of the evidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual metadata")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def collect_github_evidence(
    repository: str,
    file_path: str,
    commit_sha: Optional[str] = None
) -> CollectedEvidence:
    """
    Safe local/mock GitHub evidence collector.
    Performs NO network requests.
    Returns structured GitHub evidence.
    """
    repo = repository.strip() if repository else "Yogeshwari1909/Verdict"
    fpath = file_path.strip() if file_path else "backend/main.py"
    sha = commit_sha.strip() if commit_sha else None

    content_lines = [
        f"Repository: {repo}",
        f"Target File: {fpath}",
    ]
    if sha:
        content_lines.append(f"Commit SHA: {sha}")
    content_lines.append("Source: Local Git Context (Safe/Offline Collector)")

    metadata = {
        "repository": repo,
        "file_path": fpath,
        "commit_sha": sha,
        "is_mock": True,
        "network_call": False
    }

    title_sha = f"@{sha[:7]}" if sha else ""
    return CollectedEvidence(
        source="github",
        evidence_type="source_reference",
        title=f"GitHub Reference: {repo}/{fpath}{title_sha}",
        content="\n".join(content_lines),
        metadata=metadata
    )


def collect_incident_memory_evidence(
    incident: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> List[CollectedEvidence]:
    """
    Search historical incidents in SQLite that match the current incident
    by service, endpoint, exception_type, or exception_message.
    Excludes the current incident ID.
    """
    current_id = incident.get("id")
    service = incident.get("service")
    endpoint = incident.get("endpoint")
    exc_type = incident.get("exception_type")
    exc_msg = incident.get("exception_message")

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        # Search for past incidents sharing matching attributes
        query = """
            SELECT id, service, environment, endpoint, http_method, status_code,
                   exception_type, exception_message, stack_trace, request_id, timestamp, metadata, created_at
            FROM incidents
            WHERE id != ? AND (
                service = ? OR
                endpoint = ? OR
                exception_type = ? OR
                exception_message LIKE ?
            )
            ORDER BY id DESC
            LIMIT 5;
        """
        # Match pattern for exception message if provided
        msg_pattern = f"%{exc_msg[:30]}%" if exc_msg else "%"
        cursor.execute(query, (current_id or -1, service, endpoint, exc_type, msg_pattern))
        rows = cursor.fetchall()

        evidence_items = []
        for row in rows:
            r_dict = dict(row)
            if r_dict.get("metadata"):
                try:
                    r_dict["metadata"] = json.loads(r_dict["metadata"])
                except Exception:
                    pass

            content = (
                f"Historical Incident #{r_dict['id']}: {r_dict['exception_type']} on {r_dict['http_method']} {r_dict['endpoint']}\n"
                f"Service: {r_dict['service']} ({r_dict['environment']})\n"
                f"Message: {r_dict['exception_message']}\n"
                f"Occurred: {r_dict['timestamp'] or r_dict['created_at']}"
            )

            evidence_items.append(
                CollectedEvidence(
                    source="incident_memory",
                    evidence_type="past_incident",
                    title=f"Past Incident #{r_dict['id']}: {r_dict['exception_type']} on {r_dict['endpoint']}",
                    content=content,
                    metadata={
                        "matched_incident_id": r_dict["id"],
                        "service": r_dict["service"],
                        "endpoint": r_dict["endpoint"],
                        "exception_type": r_dict["exception_type"],
                        "status_code": r_dict["status_code"]
                    }
                )
            )
        return evidence_items
    finally:
        if should_close:
            conn.close()


def collect_evidence(
    incident: Dict[str, Any],
    verdict_id: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Orchestrates evidence collection:
    1. Collects incident-memory evidence from previous matching incidents in SQLite.
    2. Prepares GitHub evidence through the safe local/mock collector (no network requests).
    3. Captures runtime telemetry/stack-trace evidence from the incident itself.
    4. Optionally stores evidence records in the SQLite evidence table if verdict_id is provided.
    5. Returns a normalized list of evidence dictionary objects.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        collected: List[CollectedEvidence] = []

        # 1. Incident Memory Evidence
        memory_evidence = collect_incident_memory_evidence(incident, conn=conn)
        collected.extend(memory_evidence)

        # 2. GitHub Evidence (Safe local/mock)
        meta = incident.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        
        repo = meta.get("repository", "Yogeshwari1909/Verdict")
        file_path = meta.get("file_path")
        if not file_path and incident.get("stack_trace"):
            match = re.search(r"File ['\"]([^'\"]+)['\"]", incident["stack_trace"])
            if match:
                file_path = match.group(1)
        file_path = file_path or "backend/main.py"
        commit_sha = meta.get("commit_sha")

        github_evidence = collect_github_evidence(
            repository=repo,
            file_path=file_path,
            commit_sha=commit_sha
        )
        collected.append(github_evidence)

        # 3. Runtime Telemetry Evidence
        runtime_evidence = CollectedEvidence(
            source="runtime_telemetry",
            evidence_type="stack_trace",
            title=f"Runtime Exception: {incident.get('exception_type')} on {incident.get('endpoint')}",
            content=(
                f"Exception: {incident.get('exception_type')}: {incident.get('exception_message')}\n"
                f"Endpoint: {incident.get('http_method')} {incident.get('endpoint')} -> HTTP {incident.get('status_code')}\n"
                f"Stack Trace:\n{incident.get('stack_trace')}"
            ),
            metadata={
                "incident_id": incident.get("id"),
                "service": incident.get("service"),
                "environment": incident.get("environment"),
                "request_id": incident.get("request_id"),
            }
        )
        collected.append(runtime_evidence)

        # 4. Store in evidence table if verdict_id is provided
        if verdict_id is not None:
            cursor = conn.cursor()
            for ev in collected:
                content_payload = json.dumps({
                    "title": ev.title,
                    "content": ev.content,
                    "metadata": ev.metadata
                })
                cursor.execute(
                    "INSERT INTO evidence (verdict_id, source, evidence_type, content) VALUES (?, ?, ?, ?);",
                    (verdict_id, ev.source, ev.evidence_type, content_payload)
                )
            conn.commit()

        return [ev.to_dict() for ev in collected]
    finally:
        if should_close:
            conn.close()
