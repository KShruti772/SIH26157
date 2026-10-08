"""
Module 6 — Local Agentic AI package for SAT-SA.

Provides offline, evidence-grounded supervisory AI assistance:
- Assessment Agent (hypothesis formulation)
- Challenge Agent (adversarial critique)
- Investigation Planner (next-best evidence recommendation)
- Agent Orchestrator & Audit Tracker
"""

from app.agents.config import (
    LOCAL_LLM_PROVIDER,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
    MAX_AGENT_STEPS,
    DISCLAIMER_NOTICE,
)
from app.agents.schemas import (
    AssessmentContext,
    AssessmentAgentOutput,
    ChallengeAgentOutput,
    InvestigationPlannerOutput,
    HumanReviewPackage,
    HumanDecisionRequest,
    AgentRunResponse,
    AgentAuditLogResponse,
)
from app.agents.assessment_agent import AssessmentAgent
from app.agents.challenge_agent import ChallengeAgent
from app.agents.investigation_planner import InvestigationPlanner
from app.agents.orchestrator import AgentOrchestrator
from app.agents.llm import LocalLLMClient
from app.agents.audit import AgentAuditTracker

__all__ = [
    "LOCAL_LLM_PROVIDER",
    "LOCAL_LLM_MODEL",
    "OLLAMA_BASE_URL",
    "MAX_AGENT_STEPS",
    "DISCLAIMER_NOTICE",
    "AssessmentContext",
    "AssessmentAgentOutput",
    "ChallengeAgentOutput",
    "InvestigationPlannerOutput",
    "HumanReviewPackage",
    "HumanDecisionRequest",
    "AgentRunResponse",
    "AgentAuditLogResponse",
    "AssessmentAgent",
    "ChallengeAgent",
    "InvestigationPlanner",
    "AgentOrchestrator",
    "LocalLLMClient",
    "AgentAuditTracker",
]
