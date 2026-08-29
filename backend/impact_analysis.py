import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BlastRadiusResult(BaseModel):
    incident_id: int = Field(..., description="ID of the analyzed incident")
    affected_service: str = Field(..., description="Service directly affected by the incident")
    affected_environment: str = Field(..., description="Environment where the incident occurred")
    affected_endpoints: List[str] = Field(default_factory=list, description="Endpoints identified in the evidence graph")
    affected_functions: List[str] = Field(default_factory=list, description="Function names identified in the evidence graph")
    affected_source_files: List[str] = Field(default_factory=list, description="Source files identified in the evidence graph")
    related_past_incidents: List[int] = Field(default_factory=list, description="IDs of historical incidents matched in the graph")
    impact_level: str = Field(..., description="Blast radius severity level: 'low', 'medium', 'high', 'unknown'")
    confidence: float = Field(..., description="Confidence in the scope assessment (0.0 to 1.0)")
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list, description="Evidence node references used to determine the blast radius")
    limitations: List[str] = Field(default_factory=list, description="Explicit boundaries and gaps in available scope evidence")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def analyze_blast_radius(
    incident: Dict[str, Any],
    graph: Dict[str, Any]
) -> BlastRadiusResult:
    """
    Deterministic Blast-Radius and Scope Assessment Engine.
    Extracts affected entities strictly from the Evidence Graph and computes
    impact level and scope confidence using evidence-backed rules (zero hallucinations).
    """
    incident_id = incident.get("id", 0)
    raw_service = incident.get("service", "").strip()
    raw_env = incident.get("environment", "").strip()
    status_code = incident.get("status_code", 0)

    nodes = graph.get("nodes", [])

    # Index graph nodes by type
    nodes_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for node in nodes:
        ntype = node.get("node_type", "")
        nodes_by_type.setdefault(ntype, []).append(node)

    # -----------------------------------------------------------------------
    # 1. Extract Affected Entities from Evidence Graph (No Hallucinations)
    # -----------------------------------------------------------------------
    affected_endpoints: List[str] = []
    affected_functions: List[str] = []
    affected_source_files: List[str] = []
    related_past_incidents: List[int] = []
    evidence_references: List[Dict[str, Any]] = []

    # Endpoints
    for ep_node in nodes_by_type.get("endpoint", []):
        ep_data = ep_node.get("data") or {}
        if isinstance(ep_data, str):
            try:
                ep_data = json.loads(ep_data)
            except Exception:
                ep_data = {}
        ep_val = ep_data.get("endpoint") or ep_node.get("label", "").replace("Endpoint: ", "").strip()
        if ep_val and ep_val not in affected_endpoints:
            affected_endpoints.append(ep_val)
        evidence_references.append({
            "node_id": ep_node.get("id"),
            "node_type": "endpoint",
            "label": ep_node.get("label", ""),
            "contribution": f"Identified affected endpoint route: {ep_val}"
        })

    # Functions
    for fn_node in nodes_by_type.get("function", []):
        fn_data = fn_node.get("data") or {}
        if isinstance(fn_data, str):
            try:
                fn_data = json.loads(fn_data)
            except Exception:
                fn_data = {}
        fn_val = fn_data.get("function_name") or fn_node.get("label", "").replace("Function: ", "").strip()
        if fn_val and fn_val not in affected_functions:
            affected_functions.append(fn_val)
        evidence_references.append({
            "node_id": fn_node.get("id"),
            "node_type": "function",
            "label": fn_node.get("label", ""),
            "contribution": f"Identified execution failure location: {fn_val}"
        })

    # Source Files
    for sf_node in nodes_by_type.get("source_file", []):
        sf_data = sf_node.get("data") or {}
        if isinstance(sf_data, str):
            try:
                sf_data = json.loads(sf_data)
            except Exception:
                sf_data = {}
        sf_val = sf_data.get("file_path") or sf_node.get("label", "").replace("File: ", "").strip()
        if sf_val and sf_val not in affected_source_files:
            affected_source_files.append(sf_val)
        evidence_references.append({
            "node_id": sf_node.get("id"),
            "node_type": "source_file",
            "label": sf_node.get("label", ""),
            "contribution": f"Localized source file: {sf_val}"
        })

    # Historical Incidents
    for pi_node in nodes_by_type.get("past_incident", []):
        pi_data = pi_node.get("data") or {}
        if isinstance(pi_data, str):
            try:
                pi_data = json.loads(pi_data)
            except Exception:
                pi_data = {}
        matched_id = pi_data.get("matched_incident_id")
        if matched_id and matched_id not in related_past_incidents:
            related_past_incidents.append(matched_id)
        evidence_references.append({
            "node_id": pi_node.get("id"),
            "node_type": "past_incident",
            "label": pi_node.get("label", ""),
            "contribution": f"Correlated with historical incident #{matched_id}"
        })

    # Fallback for service/environment if not explicitly in incident record
    service = raw_service or "unknown-service"
    environment = raw_env or "unknown"

    # -----------------------------------------------------------------------
    # 2. Limitations (Explicit boundaries)
    # -----------------------------------------------------------------------
    limitations: List[str] = [
        "No downstream multi-service distributed tracing available in evidence graph.",
        "No live user traffic volume or error-rate metrics attached to quantify affected user count.",
        "No deployment event telemetry linked to determine active release blast radius.",
        "Scope analysis is bounded by static frame graph and single-service telemetry."
    ]

    # -----------------------------------------------------------------------
    # 3. Determine Scope Assessment Confidence & Impact Level
    # -----------------------------------------------------------------------
    # If the graph has 0 nodes or essential data is missing, mark UNKNOWN
    if not nodes or (not affected_endpoints and not affected_source_files):
        return BlastRadiusResult(
            incident_id=incident_id,
            affected_service=service,
            affected_environment=environment,
            affected_endpoints=affected_endpoints,
            affected_functions=affected_functions,
            affected_source_files=affected_source_files,
            related_past_incidents=related_past_incidents,
            impact_level="unknown",
            confidence=0.0,
            evidence_references=[],
            limitations=limitations + ["Insufficient graph entities to evaluate blast radius scope."]
        )

    # Scope assessment confidence calculation
    scope_conf = 0.0
    if raw_service and raw_env:
        scope_conf += 0.25
    if affected_endpoints:
        scope_conf += 0.25
    if affected_functions or affected_source_files:
        scope_conf += 0.30
    if nodes_by_type.get("exception") and nodes_by_type.get("stack_trace"):
        scope_conf += 0.10

    scope_conf = min(0.90, round(scope_conf, 2))

    # Determine impact_level
    is_prod = environment.lower() in ["production", "prod"]
    is_5xx = (status_code >= 500)
    critical_keywords = ["checkout", "pay", "order", "billing", "auth", "login"]
    is_critical_endpoint = any(kw in ep.lower() for ep in affected_endpoints for kw in critical_keywords)
    has_multiple_entities = (len(affected_functions) >= 2 or len(affected_source_files) >= 2 or len(affected_endpoints) >= 2)

    if is_prod and is_5xx:
        if is_critical_endpoint or has_multiple_entities:
            impact_level = "high"
        else:
            impact_level = "medium"
    elif is_prod and not is_5xx:
        impact_level = "medium"
    elif not is_prod:
        # Non-production environment (staging, dev, test)
        impact_level = "low"
    else:
        impact_level = "unknown"

    return BlastRadiusResult(
        incident_id=incident_id,
        affected_service=service,
        affected_environment=environment,
        affected_endpoints=affected_endpoints,
        affected_functions=affected_functions,
        affected_source_files=affected_source_files,
        related_past_incidents=related_past_incidents,
        impact_level=impact_level,
        confidence=scope_conf,
        evidence_references=evidence_references,
        limitations=limitations
    )
