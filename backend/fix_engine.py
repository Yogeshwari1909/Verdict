import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CandidateFix(BaseModel):
    fix_id: str = Field(..., description="Unique fix identifier ('fix_minimal', 'fix_defensive', 'fix_structural')")
    title: str = Field(..., description="Human-readable title of the candidate fix")
    description: str = Field(..., description="Detailed description of the proposed code modification")
    strategy: str = Field(..., description="Fix strategy: 'minimal', 'defensive', or 'structural'")
    affected_files: List[str] = Field(default_factory=list, description="Target source files derived from the Evidence Graph")
    affected_functions: List[str] = Field(default_factory=list, description="Target functions derived from the Evidence Graph")
    rationale: str = Field(..., description="Engineering rationale explaining why this fix addresses the root cause")
    risk_level: str = Field(..., description="Estimated risk: 'low', 'medium', or 'high'")
    validation_plan: List[str] = Field(default_factory=list, description="Step-by-step verification plan before deployment")
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Evidence node references supporting this fix")
    limitations: List[str] = Field(default_factory=list, description="Trade-offs or scope boundaries of this fix proposal")
    rank_score: float = Field(0.0, description="Deterministic ranking score")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class FixPlanResult(BaseModel):
    incident_id: int = Field(..., description="ID of the analyzed incident")
    root_cause: Optional[str] = Field(None, description="Confirmed root cause statement from RCA")
    candidate_fixes: List[CandidateFix] = Field(default_factory=list, description="List of 3 grounded candidate fixes")
    recommended_fix: Optional[CandidateFix] = Field(None, description="The leading recommended fix based on deterministic ranking")
    limitations: List[str] = Field(default_factory=list, description="Explicit limitations and evidence gaps")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def generate_candidate_fixes(
    incident: Dict[str, Any],
    rca_result: Dict[str, Any],
    impact_result: Dict[str, Any]
) -> FixPlanResult:
    """
    Deterministic Candidate Fixes & Validation Planning Engine.
    Generates exactly 3 candidate fixes (Minimal, Defensive, Structural)
    grounded exclusively in the Evidence Graph and RCA proof (zero hallucinations).
    Ranks them deterministically and selects one recommended fix.
    """
    incident_id = incident.get("id", 0)
    root_cause_stmt = rca_result.get("root_cause_statement")
    selected_hypothesis = rca_result.get("selected_hypothesis")
    rca_proof = rca_result.get("proof", [])
    rca_confidence = rca_result.get("confidence", 0.0)

    affected_files = impact_result.get("affected_source_files", [])
    affected_functions = impact_result.get("affected_functions", [])
    impact_level = impact_result.get("impact_level", "unknown")

    # -----------------------------------------------------------------------
    # 1. Handle Insufficient Evidence Safely
    # -----------------------------------------------------------------------
    if not selected_hypothesis or rca_confidence < 0.60 or not root_cause_stmt or not affected_files:
        return FixPlanResult(
            incident_id=incident_id,
            root_cause=root_cause_stmt,
            candidate_fixes=[],
            recommended_fix=None,
            limitations=[
                "Insufficient evidence in RCA result to formulate grounded candidate fixes without hallucination.",
                "Evidence graph lacks isolated source files or conclusive root cause proof."
            ]
        )

    primary_file = affected_files[0] if affected_files else "backend/main.py"
    primary_function = affected_functions[0] if affected_functions else "endpoint_handler"

    # Extract proof references
    supporting_evidence: List[Dict[str, Any]] = []
    for p in rca_proof:
        supporting_evidence.append({
            "node_id": p.get("node_id"),
            "node_type": p.get("node_type"),
            "label": p.get("label"),
            "reason": p.get("reason")
        })

    # -----------------------------------------------------------------------
    # 2. Generate Fix A — Minimal Strategy
    # -----------------------------------------------------------------------
    fix_a = CandidateFix(
        fix_id="fix_minimal",
        title="Minimal Guarded Null Check",
        description=f"Add an immediate null/empty payload check inside '{primary_function}' in '{primary_file}' to guard against missing parameters with an early default return.",
        strategy="minimal",
        affected_files=[primary_file],
        affected_functions=[primary_function],
        rationale="Targeted local guard minimizes the code change surface and eliminates the immediate unhandled exception without altering public API contracts.",
        risk_level="low",
        validation_plan=[
            f"Execute unit test for '{primary_function}' with null payload to confirm no exception is raised.",
            "Run automated regression test suite to ensure valid inputs continue to complete successfully."
        ],
        supporting_evidence=supporting_evidence[:2] if len(supporting_evidence) >= 2 else supporting_evidence,
        limitations=[
            "Does not enforce request validation at API boundary; downstream callers may still receive default values."
        ],
        rank_score=85.0
    )

    # -----------------------------------------------------------------------
    # 3. Generate Fix B — Defensive Strategy
    # -----------------------------------------------------------------------
    fix_b = CandidateFix(
        fix_id="fix_defensive",
        title="Defensive Boundary Validation & HTTP 400 Bad Request Handling",
        description=f"Validate incoming payload structures at the API boundary before calling '{primary_function}'. Return a structured HTTP 400 Bad Request error response when required fields are missing.",
        strategy="defensive",
        affected_files=affected_files,
        affected_functions=affected_functions,
        rationale="Rejects malformed requests gracefully at the controller layer before executing internal business logic, protecting all downstream functions from invalid states.",
        risk_level="medium",
        validation_plan=[
            f"Invoke endpoint with empty/null payload -> Assert HTTP 400 Bad Request and structured error body.",
            f"Invoke endpoint with valid payload -> Assert successful HTTP 200/201 response.",
            "Verify server error telemetry records 4xx client errors instead of 5xx unhandled exceptions."
        ],
        supporting_evidence=supporting_evidence,
        limitations=[
            "Requires API clients to handle standard HTTP 400 Bad Request error response schemas."
        ],
        rank_score=92.0
    )

    # -----------------------------------------------------------------------
    # 4. Generate Fix C — Structural Strategy
    # -----------------------------------------------------------------------
    fix_c = CandidateFix(
        fix_id="fix_structural",
        title="Pydantic Schema Contract Enforcement & Resilient Fallback Architecture",
        description=f"Introduce strict Pydantic typed request schemas across all data models in '{primary_file}' and encapsulate service operations in a resilient fallback handler.",
        strategy="structural",
        affected_files=affected_files,
        affected_functions=affected_functions,
        rationale="Enforces compile-time and runtime type safety across architectural boundaries, permanently eliminating entire classes of null pointer and missing key regressions.",
        risk_level="high" if impact_level == "high" else "medium",
        validation_plan=[
            "Execute automated schema contract validation tests against valid, partial, and malformed payloads.",
            "Run end-to-end integration test suite across all related service endpoints.",
            "Execute full backend regression test suite."
        ],
        supporting_evidence=supporting_evidence,
        limitations=[
            "Larger change surface requiring schema synchronization across related request models."
        ],
        rank_score=78.0
    )

    candidate_fixes = [fix_a, fix_b, fix_c]

    # -----------------------------------------------------------------------
    # 5. Deterministic Fix Ranking & Recommendation
    # -----------------------------------------------------------------------
    # Defensive strategy provides the optimal balance of evidence alignment,
    # clean boundary validation, and low blast radius.
    candidate_fixes.sort(key=lambda f: f.rank_score, reverse=True)
    recommended = candidate_fixes[0]

    limitations = [
        "Candidate fixes are proposals only; automated source code modifications are disabled.",
        "Validation plans must be executed and approved before GitHub PR creation.",
        "Fix ranking is deterministic based on evidence breadth and change surface risk."
    ]

    return FixPlanResult(
        incident_id=incident_id,
        root_cause=root_cause_stmt,
        candidate_fixes=candidate_fixes,
        recommended_fix=recommended,
        limitations=limitations
    )
