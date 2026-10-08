"""
Audit logging and provenance tracking for Module 6 — Local Agentic AI.

Records machine-readable execution logs for every agent step to support Module 9 Audit & Replay.
"""

import hashlib
import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import domain
from app.agents.config import (
    LOCAL_LLM_PROVIDER,
    LOCAL_LLM_MODEL,
    PROMPT_VERSION,
)


def compute_object_hash(data: Any) -> str:
    """Compute deterministic SHA-256 hash of any JSON-serializable object."""
    try:
        raw_json = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.sha256(str(data).encode("utf-8")).hexdigest()


class AgentAuditTracker:
    """
    Records immutable agent execution traces to the database.
    """

    @staticmethod
    def record_step(
        db: Session,
        run_id: str,
        agent_id: str,
        finding_id: str,
        input_context_hash: Optional[str],
        action: str,
        output_data: Any,
        status: str = "SUCCESS",
        validation_result: str = "PASSED",
        error_message: Optional[str] = None,
        referenced_evidence_ids: Optional[List[str]] = None,
        model_provider: str = LOCAL_LLM_PROVIDER,
        model_name: str = LOCAL_LLM_MODEL,
        prompt_version: str = PROMPT_VERSION,
    ) -> domain.AgentAuditLog:
        """
        Persist a single agent execution step to the database.
        """
        output_hash = compute_object_hash(output_data) if output_data is not None else None
        ref_ids = referenced_evidence_ids or []

        log_entry = domain.AgentAuditLog(
            run_id=run_id,
            agent_id=agent_id,
            finding_id=finding_id,
            timestamp=datetime.datetime.utcnow(),
            input_context_hash=input_context_hash,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            output_hash=output_hash,
            referenced_evidence_ids=ref_ids,
            action=action,
            status=status,
            validation_result=validation_result,
            error_message=error_message,
        )

        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
