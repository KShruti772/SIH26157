"""
Agent Orchestrator (Module 6 — Local Agentic AI).

Coordinates the sequential, bounded execution:
  BUILD CONTEXT -> ASSESSMENT AGENT -> CHALLENGE AGENT -> INVESTIGATION PLANNER -> HUMAN REVIEW REQUIRED

Enforces:
1. Deterministic bounded iterations (MAX_AGENT_STEPS = 3).
2. Strict Human-in-the-Loop requirement (State stops at HUMAN_REVIEW_REQUIRED).
3. Seamless fallback between LOCAL_LLM and DETERMINISTIC_FALLBACK.
4. Full audit logging of all execution steps.
"""

import uuid
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import domain
from app.agents.config import (
    MAX_AGENT_STEPS,
    MAX_REPLAN_ATTEMPTS,
    DISCLAIMER_NOTICE,
    LOCAL_LLM_PROVIDER,
    LOCAL_LLM_MODEL,
)
from app.agents.schemas import (
    AssessmentContext,
    HumanReviewPackage,
    AssessmentAgentOutput,
    ChallengeAgentOutput,
    InvestigationPlannerOutput,
)
from app.agents.evidence_context import build_assessment_context, compute_context_hash
from app.agents.assessment_agent import AssessmentAgent
from app.agents.challenge_agent import ChallengeAgent
from app.agents.investigation_planner import InvestigationPlanner
from app.agents.llm import LocalLLMClient
from app.agents.audit import AgentAuditTracker
from app.agents.permissions import check_agent_permission


class AgentOrchestrator:
    """
    Main orchestrator for SAT-SA supervisory agent workflows.
    """

    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.llm_client = llm_client or LocalLLMClient()
        self.assessment_agent = AssessmentAgent(self.llm_client)
        self.challenge_agent = ChallengeAgent(self.llm_client)
        self.investigation_planner = InvestigationPlanner(self.llm_client)

    def run_analysis(
        self,
        finding_id: str,
        db: Session,
        force_fallback: bool = False,
    ) -> HumanReviewPackage:
        """
        Execute the complete 3-agent supervisory analysis pipeline for a finding.
        Always terminates at state 'HUMAN_REVIEW_REQUIRED'.
        """
        run_id = f"ARUN-{uuid.uuid4().hex[:8].upper()}"

        # 1. State: CREATED -> BUILD CONTEXT
        context: AssessmentContext = build_assessment_context(finding_id, db)
        context_hash = compute_context_hash(context.model_dump())

        # Determine execution mode
        is_llm_avail = not force_fallback and self.llm_client.check_availability()
        mode = "LOCAL_LLM" if is_llm_avail else "DETERMINISTIC_FALLBACK"

        # Create AgentRun persistence record
        agent_run = domain.AgentRun(
            id=run_id,
            finding_id=finding_id,
            analysis_id=context.analysis_id,
            entity_id=context.entity_id,
            state="CONTEXT_BUILT",
            mode=mode,
            assessment_result={},
            challenge_result={},
            planner_result={},
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        )
        db.add(agent_run)
        db.commit()

        # Audit Context Creation
        AgentAuditTracker.record_step(
            db=db,
            run_id=run_id,
            agent_id="orchestrator",
            finding_id=finding_id,
            input_context_hash=context_hash,
            action="BUILD_ASSESSMENT_CONTEXT",
            output_data={"valid_evidence_count": len(context.valid_evidence_ids)},
            status="SUCCESS",
            model_provider=LOCAL_LLM_PROVIDER if mode == "LOCAL_LLM" else "deterministic",
            model_name=LOCAL_LLM_MODEL if mode == "LOCAL_LLM" else "rules_engine",
        )

        # Record AGENT_RUN_STARTED audit event (Module 9)
        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            audit_svc.record_event(
                db=db,
                event_type=EventType.AGENT_RUN_STARTED,
                actor_type=ActorType.SYSTEM,
                actor_id="AgentOrchestrator",
                entity_id=context.entity_id,
                analysis_id=context.analysis_id,
                finding_id=finding_id,
                agent_run_id=run_id,
                payload={"mode": mode, "context_hash": context_hash},
            )
        except Exception:
            pass

        # 2. Step 1: ASSESSMENT AGENT
        agent_run.state = "ASSESSED"
        db.commit()

        assessment_out: AssessmentAgentOutput = self.assessment_agent.run(
            context=context, force_fallback=(mode == "DETERMINISTIC_FALLBACK")
        )
        agent_run.assessment_result = assessment_out.model_dump()
        db.commit()

        AgentAuditTracker.record_step(
            db=db,
            run_id=run_id,
            agent_id="assessment_agent",
            finding_id=finding_id,
            input_context_hash=context_hash,
            action="CREATE_HYPOTHESIS",
            output_data=assessment_out.model_dump(),
            referenced_evidence_ids=assessment_out.supporting_evidence,
            status="SUCCESS" if mode == "LOCAL_LLM" else "FALLBACK",
            model_provider=LOCAL_LLM_PROVIDER if mode == "LOCAL_LLM" else "deterministic",
            model_name=LOCAL_LLM_MODEL if mode == "LOCAL_LLM" else "rules_engine",
        )

        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            audit_svc.record_event(
                db=db,
                event_type=EventType.AGENT_ASSESSMENT_CREATED,
                actor_type=ActorType.ASSESSMENT_AGENT,
                actor_id="AssessmentAgent",
                entity_id=context.entity_id,
                analysis_id=context.analysis_id,
                finding_id=finding_id,
                agent_run_id=run_id,
                payload={
                    "hypothesis": assessment_out.hypothesis,
                    "confidence": assessment_out.finding_confidence,
                    "assessment_validity": assessment_out.assessment_validity,
                    "supporting_evidence": assessment_out.supporting_evidence,
                },
            )
        except Exception:
            pass

        # 3. Step 2: CHALLENGE AGENT
        agent_run.state = "CHALLENGED"
        db.commit()

        challenge_out: ChallengeAgentOutput = self.challenge_agent.run(
            context=context,
            hypothesis=assessment_out,
            force_fallback=(mode == "DETERMINISTIC_FALLBACK"),
        )
        agent_run.challenge_result = challenge_out.model_dump()
        db.commit()

        AgentAuditTracker.record_step(
            db=db,
            run_id=run_id,
            agent_id="challenge_agent",
            finding_id=finding_id,
            input_context_hash=context_hash,
            action="CREATE_CHALLENGE",
            output_data=challenge_out.model_dump(),
            referenced_evidence_ids=challenge_out.counter_evidence,
            status="SUCCESS" if mode == "LOCAL_LLM" else "FALLBACK",
            model_provider=LOCAL_LLM_PROVIDER if mode == "LOCAL_LLM" else "deterministic",
            model_name=LOCAL_LLM_MODEL if mode == "LOCAL_LLM" else "rules_engine",
        )

        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            audit_svc.record_event(
                db=db,
                event_type=EventType.AGENT_CHALLENGE_CREATED,
                actor_type=ActorType.CHALLENGE_AGENT,
                actor_id="ChallengeAgent",
                entity_id=context.entity_id,
                analysis_id=context.analysis_id,
                finding_id=finding_id,
                agent_run_id=run_id,
                payload={
                    "challenge_status": challenge_out.challenge_status,
                    "missing_evidence": challenge_out.missing_evidence,
                    "alternative_explanations": challenge_out.alternative_explanations,
                },
            )
        except Exception:
            pass

        # 4. Step 3: INVESTIGATION PLANNER
        agent_run.state = "INVESTIGATION_RECOMMENDED"
        db.commit()

        planner_out: InvestigationPlannerOutput = self.investigation_planner.run(
            context=context,
            hypothesis=assessment_out,
            challenge=challenge_out,
            force_fallback=(mode == "DETERMINISTIC_FALLBACK"),
        )
        agent_run.planner_result = planner_out.model_dump()
        db.commit()

        AgentAuditTracker.record_step(
            db=db,
            run_id=run_id,
            agent_id="investigation_planner",
            finding_id=finding_id,
            input_context_hash=context_hash,
            action="RECOMMEND_INVESTIGATION",
            output_data=planner_out.model_dump(),
            referenced_evidence_ids=planner_out.supporting_evidence,
            status="SUCCESS" if mode == "LOCAL_LLM" else "FALLBACK",
            model_provider=LOCAL_LLM_PROVIDER if mode == "LOCAL_LLM" else "deterministic",
            model_name=LOCAL_LLM_MODEL if mode == "LOCAL_LLM" else "rules_engine",
        )

        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            audit_svc.record_event(
                db=db,
                event_type=EventType.AGENT_RECOMMENDATION_CREATED,
                actor_type=ActorType.INVESTIGATION_PLANNER,
                actor_id="InvestigationPlanner",
                entity_id=context.entity_id,
                analysis_id=context.analysis_id,
                finding_id=finding_id,
                agent_run_id=run_id,
                payload={
                    "recommended_action": planner_out.recommended_action,
                    "additional_evidence_requests": planner_out.additional_evidence_requests,
                },
            )

            # Record AGENT_RUN_COMPLETED
            audit_svc.record_event(
                db=db,
                event_type=EventType.AGENT_RUN_COMPLETED,
                actor_type=ActorType.SYSTEM,
                actor_id="AgentOrchestrator",
                entity_id=context.entity_id,
                analysis_id=context.analysis_id,
                finding_id=finding_id,
                agent_run_id=run_id,
                payload={
                    "run_id": run_id,
                    "final_state": "HUMAN_REVIEW_REQUIRED",
                    "steps_completed": 3,
                },
            )
        except Exception:
            pass

        # 5. Final State: HUMAN_REVIEW_REQUIRED (Agents cannot finalize assessment)
        agent_run.state = "HUMAN_REVIEW_REQUIRED"
        agent_run.updated_at = datetime.datetime.utcnow()
        db.commit()

        # Finding confidence vs assessment validity
        f_conf_str = assessment_out.finding_confidence
        a_val_str = assessment_out.assessment_validity

        return HumanReviewPackage(
            run_id=run_id,
            finding_id=finding_id,
            entity_id=context.entity_id,
            state="HUMAN_REVIEW_REQUIRED",
            finding_confidence=f_conf_str,
            assessment_validity=a_val_str,
            assessment_agent_result=assessment_out,
            challenge_agent_result=challenge_out,
            investigation_planner_result=planner_out,
            human_decision=None,
            human_notes=None,
            audit_summary={
                "run_id": run_id,
                "mode": mode,
                "context_hash": context_hash,
                "steps_completed": 3,
                "max_steps": MAX_AGENT_STEPS,
            },
            disclaimer=DISCLAIMER_NOTICE,
        )

    def apply_human_decision(
        self,
        run_id: str,
        decision: str,
        notes: Optional[str],
        reviewer: str,
        db: Session,
    ) -> domain.AgentRun:
        """
        Record final human examiner adjudication on an agent supervisory review.
        """
        action_name = f"{decision.upper()}_FINDING"
        check_agent_permission("human_examiner", action_name)

        agent_run = db.query(domain.AgentRun).filter(domain.AgentRun.id == run_id).first()
        if not agent_run:
            raise ValueError(f"AgentRun with ID '{run_id}' not found.")

        agent_run.human_decision = decision.upper()
        agent_run.human_notes = notes
        agent_run.state = "COMPLETED"
        agent_run.updated_at = datetime.datetime.utcnow()

        # Update finding status if relevant
        finding = db.query(domain.Finding).filter(domain.Finding.id == agent_run.finding_id).first()
        if finding:
            d_upper = decision.upper()
            if d_upper in ("CONFIRM", "CONFIRMED"):
                finding.status = "Confirmed by Supervisor"
            elif d_upper in ("REJECT", "REJECTED"):
                finding.status = "Rejected by Supervisor"
            elif d_upper in ("REQUEST_EVIDENCE", "REQUEST EVIDENCE"):
                finding.status = "Evidence Requested"
            elif d_upper in ("MODIFY", "MODIFIED"):
                finding.status = "Modified by Supervisor"


        # Record human audit log
        AgentAuditTracker.record_step(
            db=db,
            run_id=run_id,
            agent_id="human_examiner",
            finding_id=agent_run.finding_id,
            input_context_hash=None,
            action=action_name,
            output_data={"decision": decision, "notes": notes, "reviewer": reviewer},
            status="SUCCESS",
            model_provider="human",
            model_name=reviewer,
        )

        db.commit()
        db.refresh(agent_run)
        return agent_run

    @staticmethod
    def to_human_review_package(agent_run: domain.AgentRun) -> HumanReviewPackage:
        """Convert a persisted AgentRun into a full HumanReviewPackage."""
        ass_res = agent_run.assessment_result or {}
        chall_res = agent_run.challenge_result or {}
        plan_res = agent_run.planner_result or {}

        assessment_out = AssessmentAgentOutput.model_validate(ass_res) if ass_res else AssessmentAgentOutput(
            hypothesis="Assessment data not available",
            finding_confidence="MEDIUM",
            assessment_validity="CAUTION",
        )
        challenge_out = ChallengeAgentOutput.model_validate(chall_res) if chall_res else ChallengeAgentOutput(
            challenge_status="SUPPORTED",
        )
        planner_out = InvestigationPlannerOutput.model_validate(plan_res) if plan_res else InvestigationPlannerOutput(
            recommended_action="No recommended action recorded",
        )

        return HumanReviewPackage(
            run_id=agent_run.id,
            finding_id=agent_run.finding_id,
            entity_id=agent_run.entity_id or "",
            state=agent_run.state,
            finding_confidence=assessment_out.finding_confidence,
            assessment_validity=assessment_out.assessment_validity,
            assessment_agent_result=assessment_out,
            challenge_agent_result=challenge_out,
            investigation_planner_result=planner_out,
            human_decision=agent_run.human_decision,
            human_notes=agent_run.human_notes,
            audit_summary={
                "run_id": agent_run.id,
                "mode": agent_run.mode,
                "steps_completed": 3,
                "max_steps": MAX_AGENT_STEPS,
            },
            disclaimer=DISCLAIMER_NOTICE,
        )

