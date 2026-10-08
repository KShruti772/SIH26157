"""
Challenge Agent (Module 6 — Local Agentic AI).

Performs adversarial critique and counter-evidence analysis against the assessment hypothesis.
Supports both local LLM execution and deterministic fallback mode.
"""

from typing import Dict, Any, List, Optional
from app.agents.schemas import (
    AssessmentContext,
    AssessmentAgentOutput,
    ChallengeAgentOutput,
    ReasoningStep,
)
from app.agents.permissions import check_agent_permission
from app.agents.guardrails import validate_schema_output
from app.agents.prompts import (
    CHALLENGE_SYSTEM_PROMPT,
    build_challenge_prompt,
)
from app.agents.llm import LocalLLMClient


class ChallengeAgent:
    """
    Supervisory Challenge Agent.
    Critiques findings, detects counter-evidence, identifies blind spots and alternative operational explanations.
    """

    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.agent_name = "challenge_agent"
        self.llm_client = llm_client or LocalLLMClient()

    def run(
        self,
        context: AssessmentContext,
        hypothesis: AssessmentAgentOutput,
        force_fallback: bool = False,
    ) -> ChallengeAgentOutput:
        """
        Execute Challenge Agent critique on the context and hypothesis.
        """
        check_agent_permission(self.agent_name, "CREATE_CHALLENGE")

        if not force_fallback and self.llm_client.check_availability():
            try:
                prompt = build_challenge_prompt(context, hypothesis)
                raw_json = self.llm_client.generate_json(
                    prompt=prompt,
                    system_prompt=CHALLENGE_SYSTEM_PROMPT,
                )
                output, _ = validate_schema_output(
                    raw_json, ChallengeAgentOutput, context.valid_evidence_ids
                )
                return output
            except Exception:
                # Fallback to deterministic rules
                pass

        return self._deterministic_fallback(context, hypothesis)

    def _deterministic_fallback(
        self,
        context: AssessmentContext,
        hypothesis: AssessmentAgentOutput,
    ) -> ChallengeAgentOutput:
        """
        Deterministic, rule-based challenge generation.
        """
        contradictions = context.contradictions
        blind_spots = context.blind_spots
        coverage = context.coverage
        proc_cov = coverage.get("process", {})
        proc_status = proc_cov.get("status", "UNKNOWN")

        # 1. Determine Challenge Status
        if len(contradictions) > 0:
            challenge_status = "CONTRADICTED"
            severity = "HIGH"
        elif proc_status in ("LOW", "NONE", "PARTIAL") or len(blind_spots) > 0:
            challenge_status = "INSUFFICIENT_EVIDENCE" if proc_status in ("LOW", "NONE") else "WEAKENED"
            severity = "MEDIUM"
        else:
            challenge_status = "SUPPORTED"
            severity = "LOW"

        # 2. Extract Missing Evidence & Blind Spots
        missing_evidence: List[str] = []
        bs_tokens: List[str] = []

        if proc_status in ("LOW", "PARTIAL", "NONE"):
            missing_evidence.append("CASE_MANAGEMENT_RECORDS")
            missing_evidence.append("ESCALATION_WORKFLOW_LOGS")

        for bs in blind_spots:
            b_type = bs.get("type") or bs.get("blind_spot_type", "GENERIC_GAP")
            bs_tokens.append(f"BLINDSPOT_{b_type.upper()}")

        # 3. Formulate Counter-Evidence and Alternative Explanations
        counter_evidence: List[str] = []
        for c in contradictions:
            rec_id = c.get("record_id")
            if rec_id and rec_id in context.valid_evidence_ids:
                counter_evidence.append(rec_id)

        alt_explanations = [
            "The absence of observable investigation or case files may indicate submission truncation rather than a failure of SOC operations.",
            "Case management and escalations may be tracked in an unintegrated IT Service Management (ITSM) ticketing platform.",
            "Alert closures may occur automatically via predefined SOAR playbooks without creating formal manual case files.",
        ]

        reasoning_steps = [
            ReasoningStep(
                statement=f"Adversarial critique status: {challenge_status}. Process coverage in submitted dataset is {proc_status}.",
                evidence_ids=[],
            )
        ]

        if bs_tokens:
            reasoning_steps.append(
                ReasoningStep(
                    statement=f"Identified {len(bs_tokens)} operational visibility blind spot(s) in submitted evidence.",
                    evidence_ids=[],
                )
            )

        if counter_evidence:
            reasoning_steps.append(
                ReasoningStep(
                    statement=f"Detected {len(counter_evidence)} contradictory record(s) requiring examiner reconciliation.",
                    evidence_ids=counter_evidence,
                )
            )

        return ChallengeAgentOutput(
            agent=self.agent_name,
            challenge_status=challenge_status,
            counter_evidence=counter_evidence,
            missing_evidence=missing_evidence,
            blind_spots=bs_tokens,
            alternative_explanations=alt_explanations,
            severity=severity,
            reasoning=reasoning_steps,
        )
