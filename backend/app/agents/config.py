"""
Configuration and settings for Module 6 — Local Agentic AI.

IMPORTANT:
- Operates strictly offline / air-gapped using local Ollama or local LLM provider.
- All prioritization formulas and thresholds are prototype analytical heuristics.
- Prototype analytical rule — requires validation against expert supervisory review.
"""

import os
from typing import Dict, Any

# Local Model Provider Configuration
LOCAL_LLM_PROVIDER: str = os.getenv("LOCAL_LLM_PROVIDER", "ollama")
LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "llama3")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Agent Execution Modes
# "LOCAL_LLM": uses local open-weight model via Ollama endpoint
# "DETERMINISTIC_FALLBACK": uses deterministic evidence grounding and rule templates
AGENT_MODE_ENV: str = os.getenv("AGENT_MODE", "LOCAL_LLM")

# Execution Bounds & Guardrails
MAX_AGENT_STEPS: int = int(os.getenv("MAX_AGENT_STEPS", "3"))
MAX_REPLAN_ATTEMPTS: int = int(os.getenv("MAX_REPLAN_ATTEMPTS", "2"))
LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "15.0"))

# Prototype Investigation Prioritization Weights
# Formula: Priority = (Relevance * Uncertainty_Reduction * Finding_Importance) / Review_Effort
PRIORITY_WEIGHTS: Dict[str, float] = {
    "relevance": 1.0,
    "uncertainty_reduction": 1.2,
    "finding_importance": 1.5,
    "review_effort_penalty": 0.8,
}

EFFORT_SCORES: Dict[str, float] = {
    "LOW": 1.0,
    "MEDIUM": 1.5,
    "HIGH": 2.5,
}

IMPORTANCE_SCORES: Dict[str, float] = {
    "CRITICAL": 3.0,
    "HIGH": 2.0,
    "MEDIUM": 1.0,
    "LOW": 0.5,
}

PROMPT_VERSION: str = "v1.0-offline"

DISCLAIMER_NOTICE: str = (
    "The agentic supervisory layer provides evidence-grounded analytical recommendations "
    "and uncertainty reduction suggestions. It does NOT replace human supervisory judgment "
    "or autonomously finalize supervisory findings."
)
