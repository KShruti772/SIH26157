"""
Assessment Agent (Module 6 — Local Agentic AI).

Formulates an evidence-grounded supervisory hypothesis from deterministic analytics.
Supports both local LLM execution and deterministic fallback mode.
"""

from typing import Dict, Any, List, Optional
from app.agents.schemas import (
    AssessmentContext,
    AssessmentAgentOutput,
    ReasoningStep,
)
from app.agents.permissions import check_agent_permission
from app.agents.guardrails import validate_schema_output
from app.agents.prompts import (
    ASSESSMENT_SYSTEM_PROMPT,
    build_assessment_prompt,
)
from app.agents.llm import LocalLLMClient, LocalLLMError


class AssessmentAgent:
    """
    Supervisory Assessment Agent.
    Transforms raw deterministic findings into structured, evidence-cited supervisory hypotheses.
    """

    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.agent_name = "assessment_agent"
        self.llm_client = llm_client or LocalLLMClient()

    def run(
        self,
        context: AssessmentContext,
        force_fallback: bool = False,
    ) -> AssessmentAgentOutput:
        """
        Execute Assessment Agent reasoning on the bounded context.
        """
        check_agent_permission(self.agent_name, "CREATE_HYPOTHESIS")

        if not force_fallback and self.llm_client.check_availability():
            try:
                prompt = build_assessment_prompt(context)
                raw_json = self.llm_client.generate_json(
                    prompt=prompt,
                    system_prompt=ASSESSMENT_SYSTEM_PROMPT,
                )
                output, _ = validate_schema_output(
                    raw_json, AssessmentAgentOutput, context.valid_evidence_ids
                )
                return output
            except Exception:
                # Fallback on LLM failure or unparseable output
                pass

        return self._deterministic_fallback(context)

    def _deterministic_fallback(self, context: AssessmentContext) -> AssessmentAgentOutput:
        """
        Deterministic, rule-based hypothesis generation guaranteeing zero hallucination.
        """
        finding = context.finding
        f_type = finding.get("type", "Supervisory Finding")
        f_cat = finding.get("category", "execution_gap")
        f_conf_val = finding.get("confidence", 0.85)
        f_conf = "HIGH" if f_conf_val >= 0.8 else ("MEDIUM" if f_conf_val >= 0.5 else "LOW")
        a_validity = finding.get("assessment_validity", "HIGH")
        desc = finding.get("description", "")
        entity_id = context.entity_id

        # Compile supporting evidence citations
        eids = context.valid_evidence_ids[:10]
        reasoning_steps: List[ReasoningStep] = []

        if eids:
            reasoning_steps.append(
                ReasoningStep(
                    statement=f"Observed {len(eids)} telemetry records supporting '{f_type}' for entity {entity_id}.",
                    evidence_ids=eids,
                )
            )
        else:
            reasoning_steps.append(
                ReasoningStep(
                    statement=f"Absence of expected telemetry indicates unobserved operational activity for entity {entity_id}.",
                    evidence_ids=[],
                )
            )

        if context.limitations:
            reasoning_steps.append(
                ReasoningStep(
                    statement=f"Evidence coverage limitation noted: {context.limitations[0]}",
                    evidence_ids=[],
                )
            )

        # Formulate grounded hypothesis
        hypothesis = (
            f"Supervisory evaluation for {entity_id} identifies '{f_type}' ({f_cat.replace('_', ' ')}). "
            f"Observed evidence: {desc} Finding Confidence is {f_conf}, while Assessment Validity is {a_validity} "
            f"reflecting current submission coverage."
        )

        alt_explanations = [
            "The observed pattern may reflect incomplete dataset submission or an external unintegrated ticketing system.",
            "Operational processes may have occurred outside the observable time or severity window.",
        ]

        return AssessmentAgentOutput(
            agent=self.agent_name,
            hypothesis=hypothesis,
            finding_confidence=f_conf,
            assessment_validity=a_validity,
            supporting_evidence=eids,
            limitations=context.limitations,
            reasoning=reasoning_steps,
            alternative_explanations=alt_explanations,
        )
