"""
Access control and permission guardrails for Module 6 — Local Agentic AI.

Enforces strict separation of agent capabilities:
- No agent may modify raw source evidence or delete records.
- No agent may autonomously finalize supervisory findings or make final judgments.
- The human examiner is the sole authority permitted to adjudicate findings.
"""

from typing import Set, Dict, List


AGENT_PERMISSIONS: Dict[str, Set[str]] = {
    "assessment_agent": {
        "READ_FINDING",
        "READ_EVIDENCE",
        "READ_ANALYTICS",
        "READ_ASSURANCE",
        "CREATE_HYPOTHESIS",
    },
    "challenge_agent": {
        "READ_FINDING",
        "READ_EVIDENCE",
        "READ_ASSURANCE",
        "SEARCH_EVIDENCE",
        "IDENTIFY_CONTRADICTIONS",
        "GENERATE_ALTERNATIVES",
        "CREATE_CHALLENGE",
    },
    "investigation_planner": {
        "READ_FINDING",
        "READ_CHALLENGE",
        "READ_EVIDENCE_GAPS",
        "READ_COVERAGE",
        "RECOMMEND_INVESTIGATION",
    },
    "human_examiner": {
        "CONFIRM_FINDING",
        "CONFIRMED_FINDING",
        "REJECT_FINDING",
        "REJECTED_FINDING",
        "MODIFY_FINDING",
        "MODIFIED_FINDING",
        "REQUEST_EVIDENCE",
        "REQUEST_EVIDENCE_FINDING",
        "ACCEPT_RECOMMENDATION",
        "REJECT_RECOMMENDATION",
    },
}

FORBIDDEN_AGENT_ACTIONS: Set[str] = {
    "MODIFY_SOURCE_EVIDENCE",
    "DELETE_SOURCE_EVIDENCE",
    "MODIFY_FINDING_RECORD",
    "FINALIZE_ASSESSMENT",
    "CHANGE_RISK_SCORE",
    "EXECUTE_OPERATIONAL_ACTION",
    "AUTONOMOUS_INCIDENT_CLOSURE",
}


class PermissionViolationError(PermissionError):
    """Raised when an agent attempts an unauthorized or forbidden action."""
    pass


def check_agent_permission(agent_name: str, action: str) -> bool:
    """
    Validate whether a given agent is permitted to perform a specified action.
    Raises PermissionViolationError if forbidden or unauthorized.
    """
    if action in FORBIDDEN_AGENT_ACTIONS:
        raise PermissionViolationError(
            f"Action '{action}' is strictly forbidden for AI agents in SAT-SA air-gapped supervisory system."
        )

    allowed = AGENT_PERMISSIONS.get(agent_name, set())
    if action not in allowed:
        raise PermissionViolationError(
            f"Agent '{agent_name}' does not possess permission for action '{action}'. "
            f"Allowed permissions: {sorted(list(allowed))}"
        )
    return True
