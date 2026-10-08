"""
Investigation Planner (Module 6 — Local Agentic AI).

Calculates and recommends the next-best supervisory evidence request to reduce analytical uncertainty.
Supports both local LLM execution and deterministic fallback mode.
"""

from typing import Dict, Any, List, Optional
from app.agents.schemas import (
    AssessmentContext,
    AssessmentAgentOutput,
    ChallengeAgentOutput,
    InvestigationPlannerOutput,
    InvestigationRequestItem,
)
from app.agents.permissions import check_agent_permission
from app.agents.guardrails import validate_schema_output
from app.agents.prompts import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_prompt,
)
from app.agents.llm import LocalLLMClient
from app.agents.config import PRIORITY_WEIGHTS, EFFORT_SCORES, IMPORTANCE_SCORES


class InvestigationPlanner:
    """
    Supervisory Investigation Planner.
    Identifies optimal next evidence requests to eliminate blind spots and reduce assessment uncertainty.
    """

    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.agent_name = "investigation_planner"
        self.llm_client = llm_client or LocalLLMClient()

    def run(
        self,
        context: AssessmentContext,
        hypothesis: AssessmentAgentOutput,
        challenge: ChallengeAgentOutput,
        force_fallback: bool = False,
    ) -> InvestigationPlannerOutput:
        """
        Execute Investigation Planner logic to formulate next-best evidence recommendations.
        """
        check_agent_permission(self.agent_name, "RECOMMEND_INVESTIGATION")

        if not force_fallback and self.llm_client.check_availability():
            try:
                prompt = build_planner_prompt(context, hypothesis, challenge)
                raw_json = self.llm_client.generate_json(
                    prompt=prompt,
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                )
                output, _ = validate_schema_output(
                    raw_json, InvestigationPlannerOutput, context.valid_evidence_ids
                )
                return output
            except Exception:
                # Fallback to deterministic heuristic logic
                pass

        return self._deterministic_fallback(context, hypothesis, challenge)

    def _deterministic_fallback(
        self,
        context: AssessmentContext,
        hypothesis: AssessmentAgentOutput,
        challenge: ChallengeAgentOutput,
    ) -> InvestigationPlannerOutput:
        """
        Deterministic heuristic formula for Next-Best Investigation prioritization.
        """
        finding = context.finding
        f_cat = finding.get("category", "execution_gap")
        f_sev = finding.get("severity", "MEDIUM")
        entity_id = context.entity_id

        # Determine evidence items to request based on category and blind spots
        evidence_requests: List[InvestigationRequestItem] = []
        uncertainty_reduced: List[str] = ["ASSESSMENT_VALIDITY"]

        if f_cat == "negative_space":
            evidence_requests.append(
                InvestigationRequestItem(
                    type="ASSET_TELEMETRY_LOG_SAMPLE",
                    reason="Verify whether unmonitored critical assets are forwarding syslog/EDR logs to an unsubmitted secondary SIEM.",
                )
            )
            evidence_requests.append(
                InvestigationRequestItem(
                    type="ASSET_MANAGEMENT_BASELINE",
                    reason="Confirm operational decommissioning or active status of critical assets missing observable telemetry.",
                )
            )
            uncertainty_reduced.append("ASSET_COVERAGE")
            action_desc = f"Request SIEM agent logs and asset baseline for unmonitored critical assets in entity {entity_id}."
        elif "CASE_MANAGEMENT_RECORDS" in challenge.missing_evidence or f_cat == "execution_gap":
            evidence_requests.append(
                InvestigationRequestItem(
                    type="CASE_MANAGEMENT_EXPORT",
                    reason="Directly tests whether unlinked alerts reflect an operational investigation failure or an incomplete dataset export.",
                )
            )
            evidence_requests.append(
                InvestigationRequestItem(
                    type="ESCALATION_TICKET_SAMPLE",
                    reason="Verify whether High/Critical alerts were escalated to Tier-2 / CERT channels outside the alert pipeline.",
                )
            )
            uncertainty_reduced.append("PROCESS_COVERAGE")
            action_desc = f"Request case-management and ticketing export for entity {entity_id} covering the assessment timeframe."
        else:
            evidence_requests.append(
                InvestigationRequestItem(
                    type="SUPPLEMENTAL_ALERT_METRICS",
                    reason="Reconcile observed statistical anomalies against baseline operational shift logs.",
                )
            )
            action_desc = f"Request supplemental shift logs and disposition notes for entity {entity_id}."

        # Compute priority score
        imp_score = IMPORTANCE_SCORES.get(f_sev.upper(), 1.0)
        effort_score = EFFORT_SCORES.get("MEDIUM", 1.5)
        unc_score = 1.5 if len(uncertainty_reduced) > 1 else 1.0

        heuristic_score = (imp_score * unc_score * PRIORITY_WEIGHTS["finding_importance"]) / effort_score
        priority_label = "HIGH" if heuristic_score >= 2.0 else ("MEDIUM" if heuristic_score >= 1.0 else "LOW")

        target_scope = {
            "entity_id": entity_id,
            "time_window": "Observable submission window",
            "severity": [f_sev] if f_sev in ("HIGH", "CRITICAL") else ["HIGH", "CRITICAL"],
        }

        return InvestigationPlannerOutput(
            agent=self.agent_name,
            recommended_action=action_desc,
            evidence_to_request=evidence_requests,
            target_scope=target_scope,
            uncertainty_reduced=uncertainty_reduced,
            priority=priority_label,
            estimated_review_effort="MEDIUM",
            supporting_evidence=challenge.blind_spots[:3] if challenge.blind_spots else context.valid_evidence_ids[:3],
        )
