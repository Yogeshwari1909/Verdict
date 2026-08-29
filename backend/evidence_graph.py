import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from database import get_db_connection

# Regex to safely extract traceback frames without hallucination
FRAME_REGEX = re.compile(
    r"File\s+['\"](?P<file>[^'\"]+)['\"],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>[^\n\r]+))?",
    re.IGNORECASE
)


def extract_traceback_frames(stack_trace: str) -> List[Dict[str, Any]]:
    """
    Extract source files, lines, and function names reliably from a stack trace.
    Does not hallucinate frames or functions.
    """
    if not stack_trace or not isinstance(stack_trace, str):
        return []

    frames = []
    for match in FRAME_REGEX.finditer(stack_trace):
        file_path = match.group("file").strip()
        line_num = int(match.group("line"))
        func_name = match.group("func").strip() if match.group("func") else None
        # Exclude generic '<module>' as a function name
        if func_name == "<module>":
            func_name = None

        frames.append({
            "file_path": file_path,
            "line_number": line_num,
            "function_name": func_name
        })
    return frames


def build_incident_graph(
    incident: Dict[str, Any],
    collected_evidence: Optional[List[Dict[str, Any]]] = None,
    verdict_id: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Deterministic function to construct the Evidence Graph connecting:
    API Request -> Endpoint -> Exception -> Stack Trace -> Function -> Source File
    along with collected evidence (e.g. past incidents).

    Implements a safe duplicate-prevention strategy by clearing any existing
    graph nodes/edges for the verdict prior to generation.
    """
    collected_evidence = collected_evidence or []
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()

        # -------------------------------------------------------------------
        # 1. Duplicate Prevention Strategy
        # -------------------------------------------------------------------
        # If a verdict_id is provided, atomically clear any previously built
        # graph nodes/edges for this verdict to ensure complete idempotency.
        if verdict_id is not None:
            cursor.execute("DELETE FROM evidence_graph_edges WHERE verdict_id = ?;", (verdict_id,))
            cursor.execute("DELETE FROM evidence_graph_nodes WHERE verdict_id = ?;", (verdict_id,))

        created_nodes: List[Dict[str, Any]] = []
        created_edges: List[Dict[str, Any]] = []
        node_lookup: Dict[str, int] = {}  # key -> node_id

        def insert_node(node_type: str, label: str, data: Optional[Dict[str, Any]] = None, key: Optional[str] = None) -> int:
            data_str = json.dumps(data) if data is not None else None
            cursor.execute(
                "INSERT INTO evidence_graph_nodes (verdict_id, node_type, label, data) VALUES (?, ?, ?, ?);",
                (verdict_id, node_type, label, data_str)
            )
            node_id = cursor.lastrowid
            node_obj = {
                "id": node_id,
                "verdict_id": verdict_id,
                "node_type": node_type,
                "label": label,
                "data": data,
            }
            created_nodes.append(node_obj)
            if key:
                node_lookup[key] = node_id
            return node_id

        def insert_edge(src_id: int, tgt_id: int, relationship: str) -> int:
            cursor.execute(
                "INSERT INTO evidence_graph_edges (verdict_id, source_node_id, target_node_id, relationship) VALUES (?, ?, ?, ?);",
                (verdict_id, src_id, tgt_id, relationship)
            )
            edge_id = cursor.lastrowid
            edge_obj = {
                "id": edge_id,
                "verdict_id": verdict_id,
                "source_node_id": src_id,
                "target_node_id": tgt_id,
                "relationship": relationship,
            }
            created_edges.append(edge_obj)
            return edge_id

        # -------------------------------------------------------------------
        # 2. Build Incident Chain Nodes
        # -------------------------------------------------------------------
        # 2a. API Request Node
        api_data = {
            "http_method": incident.get("http_method"),
            "request_id": incident.get("request_id"),
            "status_code": incident.get("status_code"),
            "service": incident.get("service"),
            "environment": incident.get("environment"),
        }
        api_node_id = insert_node(
            node_type="api_request",
            label=f"{incident.get('http_method', 'HTTP')} {incident.get('endpoint', '/')}",
            data=api_data,
            key="api_request"
        )

        # 2b. Endpoint Node
        ep_data = {
            "endpoint": incident.get("endpoint"),
            "service": incident.get("service"),
        }
        endpoint_node_id = insert_node(
            node_type="endpoint",
            label=f"Endpoint: {incident.get('endpoint')}",
            data=ep_data,
            key="endpoint"
        )
        insert_edge(api_node_id, endpoint_node_id, "routes_to")

        # 2c. Exception Node
        exc_data = {
            "exception_type": incident.get("exception_type"),
            "exception_message": incident.get("exception_message"),
        }
        exc_node_id = insert_node(
            node_type="exception",
            label=f"Exception: {incident.get('exception_type')}",
            data=exc_data,
            key="exception"
        )
        insert_edge(endpoint_node_id, exc_node_id, "raises")

        # 2d. Stack Trace Node
        st_data = {
            "stack_trace": incident.get("stack_trace"),
        }
        st_node_id = insert_node(
            node_type="stack_trace",
            label=f"Stack Trace ({incident.get('exception_type')})",
            data=st_data,
            key="stack_trace"
        )
        insert_edge(exc_node_id, st_node_id, "generates")

        # 2e. Parse Traceback Frames (Safely without hallucination)
        frames = extract_traceback_frames(incident.get("stack_trace", ""))
        last_func_node_id = None
        last_file_node_id = None

        for idx, frame in enumerate(frames):
            file_p = frame["file_path"]
            func_n = frame["function_name"]
            line_n = frame["line_number"]

            # Source file node
            file_key = f"file:{file_p}"
            if file_key not in node_lookup:
                f_node_id = insert_node(
                    node_type="source_file",
                    label=f"File: {file_p}",
                    data={"file_path": file_p, "line_number": line_n},
                    key=file_key
                )
            else:
                f_node_id = node_lookup[file_key]
            last_file_node_id = f_node_id

            # Function node (if present)
            if func_n:
                func_key = f"func:{file_p}:{func_n}"
                if func_key not in node_lookup:
                    fn_node_id = insert_node(
                        node_type="function",
                        label=f"Function: {func_n}",
                        data={"function_name": func_n, "file_path": file_p, "line_number": line_n},
                        key=func_key
                    )
                else:
                    fn_node_id = node_lookup[func_key]
                last_func_node_id = fn_node_id

                # Connect stack_trace -> function -> source_file
                insert_edge(st_node_id, fn_node_id, "occurs_in")
                insert_edge(fn_node_id, f_node_id, "located_in")
            else:
                # Direct stack_trace -> source_file
                insert_edge(st_node_id, f_node_id, "points_to")

        # -------------------------------------------------------------------
        # 3. Integrate Collected Evidence
        # -------------------------------------------------------------------
        for ev in collected_evidence:
            ev_type = ev.get("evidence_type")
            ev_source = ev.get("source")
            ev_title = ev.get("title", "")
            ev_meta = ev.get("metadata") or {}

            if ev_type == "past_incident" or ev_source == "incident_memory":
                # Create past_incident graph node
                pi_node_id = insert_node(
                    node_type="past_incident",
                    label=ev_title,
                    data=ev_meta
                )
                insert_edge(exc_node_id, pi_node_id, "matches_pattern")

            elif ev_source == "github" and "file_path" in ev_meta:
                gh_file = ev_meta["file_path"]
                file_key = f"file:{gh_file}"
                if file_key not in node_lookup:
                    gh_file_node_id = insert_node(
                        node_type="source_file",
                        label=f"File: {gh_file}",
                        data=ev_meta,
                        key=file_key
                    )
                    if last_func_node_id:
                        insert_edge(last_func_node_id, gh_file_node_id, "references")

        conn.commit()

        return {
            "status": "success",
            "incident_id": incident.get("id"),
            "verdict_id": verdict_id,
            "nodes_created": len(created_nodes),
            "edges_created": len(created_edges),
            "graph": {
                "nodes": created_nodes,
                "edges": created_edges
            }
        }
    finally:
        if should_close:
            conn.close()
