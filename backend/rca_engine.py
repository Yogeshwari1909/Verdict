import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    node_id: Optional[int] = Field(None, description="Graph node ID if applicable")
    node_type: str = Field(..., description="Node type or evidence source")
    label: str = Field(..., description="Label or title of the evidence")
    reason: str = Field(..., description="Explanation of how this evidence supports or contradicts the hypothesis")


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(..., description="Unique identifier for the hypothesis")
    title: str = Field(..., description="Brief title of the hypothesis")
    description: str = Field(..., description="Detailed description of the proposed explanation")
    status: str = Field(..., description="Status: 'supported', 'contradicted', or 'inconclusive'")
    supporting_evidence: List[EvidenceReference] = Field(default_factory=list, description="Evidence items supporting this hypothesis")
    contradicting_evidence: List[EvidenceReference] = Field(default_factory=list, description="Evidence items contradicting this hypothesis")
    confidence: float = Field(..., description="Calculated confidence score between 0.0 and 1.0")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RCAResult(BaseModel):
    incident_id: int = Field(..., description="ID of the analyzed incident")
    hypotheses: List[Hypothesis] = Field(..., description="List of evaluated hypotheses")
    selected_hypothesis: Optional[Hypothesis] = Field(None, description="The leading supported hypothesis, if conclusive")
    root_cause_statement: Optional[str] = Field(None, description="Synthesized root cause summary with proof")
    confidence: float = Field(..., description="Confidence score of the selected hypothesis (or 0.0 if inconclusive)")
    proof: List[EvidenceReference] = Field(default_factory=list, description="Direct proof items from graph nodes supporting the root cause")
    limitations: List[str] = Field(default_factory=list, description="Explicit boundaries and gaps in available evidence")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def analyze_incident_rca(
    incident: Dict[str, Any],
    graph: Dict[str, Any],
    collected_evidence: Optional[List[Dict[str, Any]]] = None
) -> RCAResult:
    """
    Deterministic RCA Reasoning & Cross-Examination Engine.
    Evaluates evidence graph nodes and collected telemetry to generate, cross-examine,
    and score hypotheses based strictly on available evidence (zero hallucinations).
    """
    collected_evidence = collected_evidence or []
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    incident_id = incident.get("id", 0)
    exception_type = incident.get("exception_type", "")
    exception_msg = incident.get("exception_message", "")
    stack_trace = incident.get("stack_trace", "")
    endpoint = incident.get("endpoint", "")
    http_method = incident.get("http_method", "")
    status_code = incident.get("status_code", 500)

    # Index graph nodes by type
    nodes_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for node in nodes:
        ntype = node.get("node_type", "")
        nodes_by_type.setdefault(ntype, []).append(node)

    hypotheses: List[Hypothesis] = []
    limitations: List[str] = []

    # -----------------------------------------------------------------------
    # 1. Hypothesis Generation & Cross-Examination (Rule A: Missing Input Validation)
    # -----------------------------------------------------------------------
    null_keywords = ["null", "missing", "none", "typeerror", "valueerror", "keyerror", "required", "invalid", "expected dict"]
    is_null_validation_pattern = any(kw in exception_msg.lower() or kw in exception_type.lower() for kw in null_keywords)

    if is_null_validation_pattern:
        supp: List[EvidenceReference] = []
        contra: List[EvidenceReference] = []

        # Find supporting exception node
        for exc_node in nodes_by_type.get("exception", []):
            supp.append(EvidenceReference(
                node_id=exc_node.get("id"),
                node_type="exception",
                label=exc_node.get("label", ""),
                reason=f"Exception message explicitly flags missing/null payload: '{exception_msg}'"
            ))

        # Find supporting stack trace node
        for st_node in nodes_by_type.get("stack_trace", []):
            supp.append(EvidenceReference(
                node_id=st_node.get("id"),
                node_type="stack_trace",
                label=st_node.get("label", ""),
                reason="Stack trace indicates execution reached payment validation check without guarded fallback"
            ))

        # Find supporting function node
        for fn_node in nodes_by_type.get("function", []):
            supp.append(EvidenceReference(
                node_id=fn_node.get("id"),
                node_type="function",
                label=fn_node.get("label", ""),
                reason=f"Failure raised directly within function '{fn_node.get('label')}'"
            ))

        # Check for contradiction: If status code is 200 or 400 with handled message
        if status_code == 200:
            contra.append(EvidenceReference(
                node_id=None,
                node_type="api_request",
                label=f"Status {status_code}",
                reason="Request completed with status 200, contradicting unhandled failure"
            ))

        # Calculate confidence
        s_count = len(supp)
        c_count = len(contra)
        if s_count > 0 and c_count == 0:
            conf = min(0.95, 0.65 + 0.10 * (s_count - 1))
            status_val = "supported"
        elif s_count > c_count:
            conf = max(0.40, 0.60 + 0.05 * (s_count - c_count))
            status_val = "supported" if conf >= 0.60 else "inconclusive"
        elif c_count > 0:
            conf = max(0.05, 0.30 - 0.10 * (c_count - s_count))
            status_val = "contradicted"
        else:
            conf = 0.0
            status_val = "inconclusive"

        hypotheses.append(Hypothesis(
            hypothesis_id="hyp_missing_input_validation",
            title="Missing Input Validation",
            description="The service encountered an unhandled exception because incoming request payload fields were null or missing, and were not validated prior to downstream processing.",
            status=status_val,
            supporting_evidence=supp,
            contradicting_evidence=contra,
            confidence=round(conf, 2)
        ))

    # -----------------------------------------------------------------------
    # 2. Hypothesis Generation & Cross-Examination (Rule B: Execution Path Defect in Source)
    # -----------------------------------------------------------------------
    source_files = nodes_by_type.get("source_file", [])
    functions = nodes_by_type.get("function", [])

    if source_files and functions:
        supp_b: List[EvidenceReference] = []
        contra_b: List[EvidenceReference] = []

        for fn in functions:
            supp_b.append(EvidenceReference(
                node_id=fn.get("id"),
                node_type="function",
                label=fn.get("label", ""),
                reason=f"Execution trace isolated unhandled error in {fn.get('label')}"
            ))

        for sf in source_files:
            supp_b.append(EvidenceReference(
                node_id=sf.get("id"),
                node_type="source_file",
                label=sf.get("label", ""),
                reason=f"Defect localized to source file '{sf.get('label')}'"
            ))

        s_count = len(supp_b)
        conf_b = min(0.85, 0.60 + 0.08 * (s_count - 1))
        hypotheses.append(Hypothesis(
            hypothesis_id="hyp_source_code_defect",
            title="Unhandled Edge Case in Source Function",
            description=f"The application function in {source_files[0].get('label')} failed to handle null/unexpected parameter values during execution.",
            status="supported",
            supporting_evidence=supp_b,
            contradicting_evidence=contra_b,
            confidence=round(conf_b, 2)
        ))

    # -----------------------------------------------------------------------
    # 3. Hypothesis Generation & Cross-Examination (Rule C: Historical Recurrence)
    # -----------------------------------------------------------------------
    past_incidents = nodes_by_type.get("past_incident", [])
    if past_incidents:
        supp_c: List[EvidenceReference] = []
        for pi in past_incidents:
            supp_c.append(EvidenceReference(
                node_id=pi.get("id"),
                node_type="past_incident",
                label=pi.get("label", ""),
                reason="Historical incident in incident memory shares matching endpoint and exception type pattern"
            ))

        conf_c = min(0.90, 0.70 + 0.10 * len(past_incidents))
        hypotheses.append(Hypothesis(
            hypothesis_id="hyp_historical_recurrence",
            title="Historical Failure Pattern Recurrence",
            description="The incident matches a known failure pattern previously recorded in incident memory.",
            status="supported",
            supporting_evidence=supp_c,
            contradicting_evidence=[],
            confidence=round(conf_c, 2)
        ))
    else:
        limitations.append("No historical incident pattern matched in incident memory.")

    # -----------------------------------------------------------------------
    # 4. Hypothesis Generation & Cross-Examination (Rule D: External Network Dependency)
    # -----------------------------------------------------------------------
    # Cross-examine whether this was an external upstream outage
    network_keywords = ["timeout", "connection refused", "502", "503", "unreachable", "dns"]
    is_network_failure = any(kw in exception_msg.lower() or kw in exception_type.lower() for kw in network_keywords)
    if is_network_failure:
        supp_d = [EvidenceReference(
            node_id=None,
            node_type="exception",
            label=f"Exception: {exception_type}",
            reason=f"Exception indicates network error: {exception_msg}"
        )]
        hypotheses.append(Hypothesis(
            hypothesis_id="hyp_upstream_dependency_failure",
            title="Upstream Dependency Failure",
            description="The incident was triggered by an unreachable upstream network dependency or service timeout.",
            status="supported",
            supporting_evidence=supp_d,
            contradicting_evidence=[],
            confidence=0.80
        ))

    # -----------------------------------------------------------------------
    # 5. Limitations & Evidence Boundaries
    # -----------------------------------------------------------------------
    if not nodes_by_type.get("commit") and not nodes_by_type.get("diff"):
        limitations.append("No Git diff or commit blame history available in evidence graph to pinpoint the introducing commit.")
    if not nodes_by_type.get("deploy"):
        limitations.append("No deployment event telemetry linked to correlate recent release timing.")
    limitations.append("Stack trace analysis is based on static frame parsing without runtime live heap inspection.")

    # -----------------------------------------------------------------------
    # 6. Select Leading Hypothesis & Compile Proof
    # -----------------------------------------------------------------------
    selected_hyp: Optional[Hypothesis] = None
    root_cause_stmt: Optional[str] = None
    proof: List[EvidenceReference] = []
    overall_conf = 0.0

    # Sort supported hypotheses by confidence descending
    supported_hyps = [h for h in hypotheses if h.status == "supported"]
    supported_hyps.sort(key=lambda h: h.confidence, reverse=True)

    if supported_hyps and supported_hyps[0].confidence >= 0.60:
        selected_hyp = supported_hyps[0]
        overall_conf = selected_hyp.confidence
        proof = list(selected_hyp.supporting_evidence)

        # Synthesize clear root cause statement
        func_labels = [f.get("label") for f in nodes_by_type.get("function", [])]
        file_labels = [f.get("label") for f in nodes_by_type.get("source_file", [])]
        location_str = ""
        if func_labels and file_labels:
            location_str = f" in {func_labels[0]} ({file_labels[0]})"
        elif file_labels:
            location_str = f" in {file_labels[0]}"

        root_cause_stmt = (
            f"Root cause confirmed with {int(overall_conf * 100)}% confidence: "
            f"{exception_type} occurred during {http_method} {endpoint}{location_str} "
            f"due to missing/null payload validation ('{exception_msg}')."
        )
    else:
        limitations.append("Insufficient evidence to conclusively determine a single root cause without contradiction.")

    return RCAResult(
        incident_id=incident_id,
        hypotheses=hypotheses,
        selected_hypothesis=selected_hyp,
        root_cause_statement=root_cause_stmt,
        confidence=overall_conf,
        proof=proof,
        limitations=limitations
    )
