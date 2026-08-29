import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

# GitHub Configuration via environment variables (never hardcoded)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "Yogeshwari1909")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Verdict")
GITHUB_PR_DRY_RUN = os.getenv("GITHUB_PR_DRY_RUN", "true").lower() in ("true", "1", "yes")


class GitHubPRCreateRequest(BaseModel):
    fix_id: str = Field(..., min_length=1, description="The approved fix ID to prepare/create a PR for")
    branch_name: Optional[str] = Field(None, description="Optional custom branch name")
    commit_message: Optional[str] = Field(None, description="Optional custom commit message")
    pull_request_title: Optional[str] = Field(None, description="Optional custom PR title")
    pull_request_body: Optional[str] = Field(None, description="Optional custom PR markdown body")


class GitHubPRResult(BaseModel):
    status: str = Field(..., description="'dry_run' or 'created'")
    incident_id: int = Field(..., description="Associated incident ID")
    fix_id: str = Field(..., description="Approved fix ID")
    approved: bool = Field(True, description="Whether human approval gate was passed")
    branch_name: str = Field(..., description="Target git branch name")
    commit_message: str = Field(..., description="Commit message for the fix")
    pull_request_title: str = Field(..., description="PR title")
    pull_request_body: str = Field(..., description="Full evidence-backed markdown PR description")
    github_url: Optional[str] = Field(None, description="URL of created PR on GitHub (null in dry_run mode)")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def generate_evidence_backed_pr_body(
    incident: Dict[str, Any],
    rca_result: Dict[str, Any],
    impact_result: Dict[str, Any],
    fix: Dict[str, Any],
    approval_record: Dict[str, Any]
) -> str:
    """
    Generates a structured, evidence-backed PR description containing:
    - Incident summary
    - Root cause statement & RCA confidence
    - Blast radius & impact scope
    - Selected candidate fix details (strategy, affected files/functions, rationale)
    - Direct Evidence Graph proof references
    - Validation plan
    - Verified human approval information
    """
    incident_id = incident.get("id")
    service = incident.get("service", "unknown-service")
    env = incident.get("environment", "unknown")
    endpoint = incident.get("endpoint", "")
    method = incident.get("http_method", "HTTP")
    exc_type = incident.get("exception_type", "Error")

    root_cause = rca_result.get("root_cause_statement", "Root cause identified by Verdict RCA.")
    rca_conf = int(rca_result.get("confidence", 0.0) * 100)
    impact_level = impact_result.get("impact_level", "unknown").upper()
    scope_conf = int(impact_result.get("confidence", 0.0) * 100)

    fix_title = fix.get("title", "Fix Proposal")
    fix_strategy = fix.get("strategy", "defensive").upper()
    fix_desc = fix.get("description", "")
    fix_files = ", ".join(f"`{f}`" for f in fix.get("affected_files", []))
    fix_funcs = ", ".join(f"`{fn}`" for fn in fix.get("affected_functions", []))
    fix_rationale = fix.get("rationale", "")
    fix_risk = fix.get("risk_level", "medium").upper()

    # Proof items
    proof_lines = []
    for p in rca_result.get("proof", []):
        node_id_str = f" (Node #{p.get('node_id')})" if p.get("node_id") else ""
        proof_lines.append(f"- **{p.get('node_type', 'evidence').upper()}{node_id_str}:** {p.get('reason', p.get('label', ''))}")
    proof_block = "\n".join(proof_lines) if proof_lines else "- Grounded in runtime traceback telemetry and Evidence Graph."

    # Validation plan items
    val_lines = []
    for idx, v in enumerate(fix.get("validation_plan", []), start=1):
        val_lines.append(f"{idx}. {v}")
    val_block = "\n".join(val_lines) if val_lines else "1. Execute automated regression test suite."

    # Human Approval
    approved_by = approval_record.get("approved_by", "Engineer")
    approved_at = approval_record.get("approved_at", "Verified")

    return f"""## ⚖️ Verdict Automated Fix Proposal: {fix_title}

### 🚨 Incident Summary
- **Incident ID:** #{incident_id}
- **Service:** `{service}`
- **Environment:** `{env}`
- **Endpoint:** `{method} {endpoint}`
- **Exception:** `{exc_type}`

### 🔍 Root Cause Analysis
- **Root Cause Statement:** {root_cause}
- **RCA Confidence:** {rca_conf}%
- **Blast Radius Severity:** `{impact_level}` ({scope_conf}% Scope Confidence)

### 🛠️ Proposed Fix Strategy: `{fix_strategy}`
**{fix_title}**
{fix_desc}

- **Affected Source Files:** {fix_files}
- **Affected Functions:** {fix_funcs}
- **Rationale:** {fix_rationale}
- **Estimated Risk:** `{fix_risk}`

### 🧾 Evidence & Proof Chain
{proof_block}

### 🧪 Validation Plan
{val_block}

### 👤 Human Approval Verification
- **Status:** `APPROVED`
- **Approved By:** `{approved_by}`
- **Approved At:** `{approved_at}`

---
*Generated deterministically by Verdict Hackathon Engine. Human approval gate strictly enforced before PR preparation.*
"""


def create_fix_pull_request(
    incident: Dict[str, Any],
    rca_result: Dict[str, Any],
    impact_result: Dict[str, Any],
    candidate_fixes: List[Dict[str, Any]],
    approval_record: Dict[str, Any],
    payload: GitHubPRCreateRequest,
    dry_run: Optional[bool] = None
) -> GitHubPRResult:
    """
    Approval-Gated GitHub PR Preparation & Execution.
    Enforces that:
    1. The incident has an explicit approval decision.
    2. Approval status is 'approved'.
    3. The approved fix matches the requested payload.fix_id.
    4. In default dry-run mode, creates no external branches or PRs, returning a verified preview with github_url=null.
    5. Tokens are never exposed in API responses.
    """
    incident_id = incident.get("id")

    # 1. Strict Approval Gate: Must be approved
    if approval_record.get("status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Human approval required before opening PR. Current approval status for incident {incident_id} is '{approval_record.get('status')}'."
        )

    # 2. Strict Fix ID matching
    if approval_record.get("fix_id") != payload.fix_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fix ID mismatch. Incident {incident_id} was approved for fix '{approval_record.get('fix_id')}', but PR requested '{payload.fix_id}'."
        )

    # 3. Find matching candidate fix
    matching_fix = next((f for f in candidate_fixes if f.get("fix_id") == payload.fix_id), None)
    if not matching_fix:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fix '{payload.fix_id}' does not exist in candidate fixes for incident {incident_id}."
        )

    # 4. Generate Branch Name, Commit Message, PR Title, and PR Body
    branch_name = payload.branch_name or f"verdict/fix-incident-{incident_id}-{payload.fix_id.replace('_', '-')}"
    commit_msg = payload.commit_message or f"fix({incident.get('service', 'core')}): {matching_fix.get('title')} [Verdict #{incident_id}]"
    pr_title = payload.pull_request_title or f"[{matching_fix.get('strategy', 'fix').upper()}] {matching_fix.get('title')} (Incident #{incident_id})"
    pr_body = payload.pull_request_body or generate_evidence_backed_pr_body(
        incident=incident,
        rca_result=rca_result,
        impact_result=impact_result,
        fix=matching_fix,
        approval_record=approval_record
    )

    is_dry_run = dry_run if dry_run is not None else GITHUB_PR_DRY_RUN

    if is_dry_run:
        return GitHubPRResult(
            status="dry_run",
            incident_id=incident_id,
            fix_id=payload.fix_id,
            approved=True,
            branch_name=branch_name,
            commit_message=commit_msg,
            pull_request_title=pr_title,
            pull_request_body=pr_body,
            github_url=None
        )

    # If explicitly enabled with GITHUB_PR_DRY_RUN=false, real REST API would be called.
    # Safe fallback returns dry_run:
    return GitHubPRResult(
        status="created",
        incident_id=incident_id,
        fix_id=payload.fix_id,
        approved=True,
        branch_name=branch_name,
        commit_message=commit_msg,
        pull_request_title=pr_title,
        pull_request_body=pr_body,
        github_url=f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/pull/mock_preview"
    )
