"""
Prompt templates and prompt builders for Module 6 — Local Agentic AI.

Strict prompt engineering constraints:
1. Never hallucinate evidence IDs.
2. Only reference evidence IDs explicitly provided in the Bounded Context.
3. Distinguish missing evidence from proven operational failure.
4. Output strict, valid JSON matching the specified schemas.
"""

import json
from typing import Dict, Any
from app.agents.schemas import AssessmentContext, AssessmentAgentOutput, ChallengeAgentOutput


ASSESSMENT_SYSTEM_PROMPT = """You are the SAT-SA Assessment Agent for NTRO/NCIIPC supervisory SOC assessments.
Your role is to formulate an evidence-grounded supervisory hypothesis explaining an observed analytical finding.

CRITICAL RULES:
1. You are NOT an autonomous decision-maker.
2. All factual statements MUST cite valid evidence IDs provided in the context (e.g. alert IDs, case IDs, asset IDs).
3. Do NOT fabricate or invent any evidence IDs.
4. Note that Finding Confidence reflects evidence strength for the finding, while Assessment Validity reflects population & process completeness.
5. You MUST output ONLY valid JSON matching the exact schema requested.
"""

CHALLENGE_SYSTEM_PROMPT = """You are the SAT-SA Challenge Agent for NTRO/NCIIPC supervisory SOC assessments.
Your role is to perform adversarial critique against the assessment hypothesis.
You must actively examine:
1. What evidence is missing from the submission?
2. Could incomplete submission or population coverage gaps explain the observation?
3. What alternative operational explanations exist (e.g., third-party ticketing, external escalation channels)?
4. Are there process blind spots (investigation, escalation, closure)?
5. Do multiple claims depend on the exact same underlying source records?

CRITICAL RULES:
1. Do NOT assume missing evidence is proof of CSE wrongdoing or operational failure.
2. Ground all critique in the provided context, blind spots, and contradictions.
3. You MUST output ONLY valid JSON matching the exact schema requested.
"""

PLANNER_SYSTEM_PROMPT = """You are the SAT-SA Investigation Planner for NTRO/NCIIPC supervisory SOC assessments.
Your role is to determine the NEXT-BEST SUPERVISORY INVESTIGATION to reduce analytical uncertainty.
This is NOT operational incident response; it recommends supervisory evidence requests for the human examiner.

CRITICAL RULES:
1. Recommend specific evidence requests that directly target observed blind spots, missing links, or coverage gaps.
2. Frame recommendations as "expected to reduce uncertainty" rather than "will prove non-compliance".
3. Ground target scopes in the entity, timeframe, and severity levels present in context.
4. You MUST output ONLY valid JSON matching the exact schema requested.
"""


def build_assessment_prompt(context: AssessmentContext) -> str:
    ctx_data = {
        "finding": context.finding,
        "valid_evidence_ids": context.valid_evidence_ids,
        "supporting_evidence_samples": [e.model_dump() for e in context.supporting_evidence[:15]],
        "contradictions": context.contradictions,
        "blind_spots": context.blind_spots,
        "coverage": context.coverage,
        "limitations": context.limitations,
    }
    return f"""Analyze the following bounded supervisory context and generate an AssessmentAgentOutput JSON:

CONTEXT:
{json.dumps(ctx_data, indent=2)}

JSON SCHEMA REQUIRED:
{{
  "agent": "assessment_agent",
  "hypothesis": "<Comprehensive explanation of the analytical observation grounded in evidence>",
  "finding_confidence": "HIGH" | "MEDIUM" | "LOW",
  "assessment_validity": "HIGH" | "CAUTION" | "LOW" | "INDETERMINATE",
  "supporting_evidence": ["<valid_evidence_id>", ...],
  "limitations": ["<identified limitation>", ...],
  "reasoning": [
    {{"statement": "<factual observation>", "evidence_ids": ["<valid_evidence_id>"]}}
  ],
  "alternative_explanations": ["<plausible operational alternative>"]
}}

Respond with valid JSON only:"""


def build_challenge_prompt(context: AssessmentContext, hypothesis: AssessmentAgentOutput) -> str:
    ctx_data = {
        "finding": context.finding,
        "assessment_hypothesis": hypothesis.model_dump(),
        "valid_evidence_ids": context.valid_evidence_ids,
        "blind_spots": context.blind_spots,
        "contradictions": context.contradictions,
        "coverage": context.coverage,
        "limitations": context.limitations,
    }
    return f"""Review the hypothesis and context below. Generate an adversarial ChallengeAgentOutput JSON:

CONTEXT & HYPOTHESIS:
{json.dumps(ctx_data, indent=2)}

JSON SCHEMA REQUIRED:
{{
  "agent": "challenge_agent",
  "challenge_status": "SUPPORTED" | "WEAKENED" | "INSUFFICIENT_EVIDENCE" | "CONTRADICTED",
  "counter_evidence": ["<valid_evidence_id>", ...],
  "missing_evidence": ["<missing log or artifact type>", ...],
  "blind_spots": ["<process or coverage blind spot>", ...],
  "alternative_explanations": ["<competing operational explanation>", ...],
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "reasoning": [
    {{"statement": "<challenge critique point>", "evidence_ids": []}}
  ]
}}

Respond with valid JSON only:"""


def build_planner_prompt(
    context: AssessmentContext,
    hypothesis: AssessmentAgentOutput,
    challenge: ChallengeAgentOutput,
) -> str:
    ctx_data = {
        "finding": context.finding,
        "valid_evidence_ids": context.valid_evidence_ids,
        "hypothesis": hypothesis.hypothesis,
        "challenge_status": challenge.challenge_status,
        "missing_evidence": challenge.missing_evidence,
        "blind_spots": challenge.blind_spots,
        "limitations": context.limitations,
    }
    return f"""Determine the next-best supervisory investigation to resolve uncertainties. Generate an InvestigationPlannerOutput JSON:

CONTEXT:
{json.dumps(ctx_data, indent=2)}

JSON SCHEMA REQUIRED:
{{
  "agent": "investigation_planner",
  "recommended_action": "<Clear next-step supervisory recommendation for the examiner>",
  "evidence_to_request": [
    {{"type": "<DATASET_OR_LOG_TYPE>", "reason": "<Why this reduces uncertainty>"}}
  ],
  "target_scope": {{
    "entity_id": "{context.entity_id}",
    "time_window": "<Observable or declared window>",
    "severity": ["HIGH", "CRITICAL"]
  }},
  "uncertainty_reduced": ["PROCESS_COVERAGE", "ASSESSMENT_VALIDITY"],
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "estimated_review_effort": "LOW" | "MEDIUM" | "HIGH",
  "supporting_evidence": ["<valid_evidence_id or blind spot token>"]
}}

Respond with valid JSON only:"""
