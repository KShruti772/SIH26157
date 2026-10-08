"""
Comprehensive test suite for Module 6 — Local Agentic AI.

Verifies:
1. Structured outputs for Assessment Agent, Challenge Agent, and Investigation Planner.
2. Evidence ID validation and anti-hallucination guardrails.
3. Strict permission checks (no autonomous decisions, no evidence modification).
4. Deterministic fallback mode when Ollama is unavailable.
5. Bounded reasoning steps (MAX_AGENT_STEPS = 3).
6. Separation of Finding Confidence vs Assessment Validity.
7. Blind-spot and missing evidence detection.
8. Machine-readable audit trails and SHA-256 context hashing.
9. Mandatory Human-in-the-Loop termination (HUMAN_REVIEW_REQUIRED).
"""

import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Dict, Any

from app.database import Base
from app.models import domain
from app.agents.schemas import (
    AssessmentContext,
    AssessmentAgentOutput,
    ChallengeAgentOutput,
    InvestigationPlannerOutput,
    HumanReviewPackage,
    EvidenceReference,
)
from app.agents.permissions import (
    check_agent_permission,
    PermissionViolationError,
)
from app.agents.guardrails import (
    validate_and_filter_evidence_ids,
    validate_schema_output,
    GuardrailValidationError,
)
from app.agents.assessment_agent import AssessmentAgent
from app.agents.challenge_agent import ChallengeAgent
from app.agents.investigation_planner import InvestigationPlanner
from app.agents.orchestrator import AgentOrchestrator
from app.agents.llm import LocalLLMClient, LocalLLMError
from app.agents.audit import AgentAuditTracker, compute_object_hash


@pytest.fixture
def agent_db():
    """In-memory SQLite database pre-seeded with test operational data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed Entity
    entity = domain.Entity(id="CSE-TEST-01", name="Power Grid Test Entity", sector="Power", assessment_period="Q3-2026")
    db.add(entity)

    # Seed Upload
    upload = domain.DatasetUpload(
        id="UPL-AGENT-01",
        filename="soc_alerts_sample.csv",
        file_type="csv",
        dataset_type="alerts",
        status="validated",
        records_received=10,
        records_valid=10,
        records_rejected=0,
        source_hash="abcd1234efgh5678",
    )
    db.add(upload)

    # Seed Assets
    asset1 = domain.Asset(id="AST-001", entity_id="CSE-TEST-01", type="SCADA-Server", criticality="Critical", has_telemetry=True)
    asset2 = domain.Asset(id="AST-002", entity_id="CSE-TEST-01", type="RTU-Gateway", criticality="Critical", has_telemetry=False)
    db.add_all([asset1, asset2])

    # Seed Alerts
    alert1 = domain.Alert(
        id="ALT-101",
        entity_id="CSE-TEST-01",
        upload_id="UPL-AGENT-01",
        timestamp=datetime.datetime(2026, 8, 1, 10, 0),
        severity="Critical",
        category="Unauthorized Access",
        asset_id="AST-001",
        acknowledged=True,
        investigation_started=False,
        escalated=False,
    )
    alert2 = domain.Alert(
        id="ALT-102",
        entity_id="CSE-TEST-01",
        upload_id="UPL-AGENT-01",
        timestamp=datetime.datetime(2026, 8, 1, 11, 0),
        severity="High",
        category="Malware",
        asset_id="AST-001",
        acknowledged=True,
        investigation_started=False,
        escalated=False,
    )
    db.add_all([alert1, alert2])

    # Seed Finding
    finding = domain.Finding(
        id="FIND-AGENT-01",
        entity_id="CSE-TEST-01",
        upload_id="UPL-AGENT-01",
        type="Uninvestigated Critical Alerts",
        category="execution_gap",
        severity="Critical",
        confidence=0.92,
        description="2 Critical/High alerts acknowledged but no formal investigation or case record observable.",
        rationale="Critical alerts require mandatory Tier-1 investigation within 15 minutes.",
        evidence_ids=["ALT-101", "ALT-102", "AST-001"],
        risk_contribution=24.5,
        recommended_action="Review Tier-1 triage response procedures and case logging.",
        status="Requires Review",
        assessment_validity="CAUTION",
        validity_rationale="Submitted dataset contains alert logs but lacks case management telemetry.",
    )
    db.add(finding)
    db.commit()

    yield db
    db.close()


class MockLocalLLMClient(LocalLLMClient):
    """Mock LLM client returning valid JSON payloads for testing without live Ollama."""

    def __init__(self, response_payload: Dict[str, Any]):
        super().__init__()
        self.response_payload = response_payload

    def check_availability(self) -> bool:
        return True

    def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        return self.response_payload


def test_assessment_agent_structured_output(agent_db):
    """Verify AssessmentAgent produces valid AssessmentAgentOutput in fallback mode."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    agent = AssessmentAgent()
    res = agent.run(ctx, force_fallback=True)

    assert isinstance(res, AssessmentAgentOutput)
    assert res.agent == "assessment_agent"
    assert "CSE-TEST-01" in res.hypothesis
    assert res.finding_confidence in ("HIGH", "MEDIUM", "LOW")
    assert res.assessment_validity in ("HIGH", "CAUTION", "LOW", "INDETERMINATE")
    assert len(res.supporting_evidence) > 0
    assert len(res.reasoning) > 0



def test_challenge_agent_structured_output(agent_db):
    """Verify ChallengeAgent performs adversarial critique and returns structured output."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    ass_agent = AssessmentAgent()
    hypothesis = ass_agent.run(ctx, force_fallback=True)

    chall_agent = ChallengeAgent()
    challenge = chall_agent.run(ctx, hypothesis, force_fallback=True)

    assert isinstance(challenge, ChallengeAgentOutput)
    assert challenge.agent == "challenge_agent"
    assert challenge.challenge_status in ("SUPPORTED", "WEAKENED", "INSUFFICIENT_EVIDENCE", "CONTRADICTED")
    assert len(challenge.alternative_explanations) > 0
    assert len(challenge.reasoning) > 0


def test_investigation_planner_structured_output(agent_db):
    """Verify InvestigationPlanner returns structured next-best evidence requests."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    ass_agent = AssessmentAgent()
    hyp = ass_agent.run(ctx, force_fallback=True)
    chall_agent = ChallengeAgent()
    chall = chall_agent.run(ctx, hyp, force_fallback=True)

    planner = InvestigationPlanner()
    plan = planner.run(ctx, hyp, chall, force_fallback=True)

    assert isinstance(plan, InvestigationPlannerOutput)
    assert plan.agent == "investigation_planner"
    assert len(plan.evidence_to_request) > 0
    assert plan.priority in ("HIGH", "MEDIUM", "LOW")
    assert "ASSESSMENT_VALIDITY" in plan.uncertainty_reduced or "PROCESS_COVERAGE" in plan.uncertainty_reduced


def test_evidence_id_validation():
    """Verify valid evidence IDs are accepted and preserved."""
    valid_ids = ["ALT-101", "ALT-102", "AST-001"]
    cited = ["ALT-101", "AST-001"]
    sanitized, invalid = validate_and_filter_evidence_ids(cited, valid_ids)

    assert sanitized == ["ALT-101", "AST-001"]
    assert len(invalid) == 0


def test_invalid_evidence_id_rejected():
    """Verify hallucinated or unknown evidence IDs are detected and filtered out."""
    valid_ids = ["ALT-101", "ALT-102"]
    cited = ["ALT-101", "E999999", "FAKE-CASE-99"]
    sanitized, invalid = validate_and_filter_evidence_ids(cited, valid_ids)

    assert sanitized == ["ALT-101"]
    assert "E999999" in invalid
    assert "FAKE-CASE-99" in invalid


def test_unknown_finding_id_rejected(agent_db):
    """Verify attempting agent analysis on a non-existent finding ID raises ValueError."""
    orchestrator = AgentOrchestrator()
    with pytest.raises(ValueError) as exc:
        orchestrator.run_analysis("FIND-NON-EXISTENT", agent_db)
    assert "not found" in str(exc.value)


def test_agent_cannot_modify_source_evidence():
    """Verify agent permissions strictly forbid modifying or deleting evidence."""
    with pytest.raises(PermissionViolationError):
        check_agent_permission("assessment_agent", "MODIFY_SOURCE_EVIDENCE")

    with pytest.raises(PermissionViolationError):
        check_agent_permission("challenge_agent", "DELETE_SOURCE_EVIDENCE")


def test_agent_cannot_finalize_assessment():
    """Verify agent cannot autonomously finalize supervisory assessments."""
    with pytest.raises(PermissionViolationError):
        check_agent_permission("assessment_agent", "FINALIZE_ASSESSMENT")

    with pytest.raises(PermissionViolationError):
        check_agent_permission("investigation_planner", "AUTONOMOUS_INCIDENT_CLOSURE")


def test_max_agent_steps_enforced(agent_db):
    """Verify orchestrator terminates cleanly in bounded 3 steps."""
    orchestrator = AgentOrchestrator()
    pkg = orchestrator.run_analysis("FIND-AGENT-01", agent_db, force_fallback=True)

    assert pkg.audit_summary["steps_completed"] == 3
    assert pkg.audit_summary["max_steps"] == 3
    assert pkg.state == "HUMAN_REVIEW_REQUIRED"


def test_ollama_unavailable_fallback_works(agent_db):
    """Verify offline fallback runs seamlessly when Ollama server is unreachable."""
    # Client pointing to non-existent port
    offline_client = LocalLLMClient(base_url="http://127.0.0.1:59999")
    assert not offline_client.check_availability()

    orchestrator = AgentOrchestrator(llm_client=offline_client)
    pkg = orchestrator.run_analysis("FIND-AGENT-01", agent_db, force_fallback=False)

    assert isinstance(pkg, HumanReviewPackage)
    assert pkg.audit_summary["mode"] == "DETERMINISTIC_FALLBACK"


def test_deterministic_fallback_full_package(agent_db):
    """Verify complete HumanReviewPackage produced in deterministic fallback mode."""
    orchestrator = AgentOrchestrator()
    pkg = orchestrator.run_analysis("FIND-AGENT-01", agent_db, force_fallback=True)

    assert pkg.finding_id == "FIND-AGENT-01"
    assert pkg.entity_id == "CSE-TEST-01"
    assert pkg.assessment_agent_result.agent == "assessment_agent"
    assert pkg.challenge_agent_result.agent == "challenge_agent"
    assert pkg.investigation_planner_result.agent == "investigation_planner"
    assert pkg.human_decision is None
    assert pkg.state == "HUMAN_REVIEW_REQUIRED"


def test_finding_confidence_separate_from_validity(agent_db):
    """Verify finding confidence and assessment validity remain strictly distinct."""
    orchestrator = AgentOrchestrator()
    pkg = orchestrator.run_analysis("FIND-AGENT-01", agent_db, force_fallback=True)

    assert pkg.finding_confidence in ("HIGH", "MEDIUM", "LOW")
    assert pkg.assessment_validity in ("HIGH", "CAUTION", "LOW", "INDETERMINATE")
    assert pkg.finding_confidence != pkg.assessment_validity



def test_challenge_agent_detects_blind_spot(agent_db):
    """Verify challenge agent flags process and telemetry blind spots."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    chall_agent = ChallengeAgent()
    hyp = AssessmentAgent().run(ctx, force_fallback=True)
    res = chall_agent.run(ctx, hyp, force_fallback=True)

    assert "CASE_MANAGEMENT_RECORDS" in res.missing_evidence
    assert res.challenge_status in ("INSUFFICIENT_EVIDENCE", "WEAKENED")


def test_challenge_agent_identifies_missing_evidence(agent_db):
    """Verify challenge agent lists missing lifecycle stages."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    chall_agent = ChallengeAgent()
    hyp = AssessmentAgent().run(ctx, force_fallback=True)
    res = chall_agent.run(ctx, hyp, force_fallback=True)

    assert len(res.missing_evidence) > 0
    assert any("CASE" in m or "ESCALATION" in m for m in res.missing_evidence)


def test_alternative_explanations_produced(agent_db):
    """Verify plausible operational alternative explanations are generated."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    chall_agent = ChallengeAgent()
    hyp = AssessmentAgent().run(ctx, force_fallback=True)
    res = chall_agent.run(ctx, hyp, force_fallback=True)

    assert len(res.alternative_explanations) > 0
    assert any("submission" in a.lower() or "ticketing" in a.lower() for a in res.alternative_explanations)


def test_investigation_planner_recommends_relevant_evidence(agent_db):
    """Verify planner recommends requesting case management logs."""
    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    hyp = AssessmentAgent().run(ctx, force_fallback=True)
    chall = ChallengeAgent().run(ctx, hyp, force_fallback=True)

    planner = InvestigationPlanner()
    plan = planner.run(ctx, hyp, chall, force_fallback=True)

    req_types = [item.type for item in plan.evidence_to_request]
    assert "CASE_MANAGEMENT_EXPORT" in req_types or "ESCALATION_TICKET_SAMPLE" in req_types


def test_agent_audit_trail_created(agent_db):
    """Verify persistent machine-readable audit logs are recorded for all agent actions."""
    orchestrator = AgentOrchestrator()
    pkg = orchestrator.run_analysis("FIND-AGENT-01", agent_db, force_fallback=True)

    logs = agent_db.query(domain.AgentAuditLog).filter(domain.AgentAuditLog.run_id == pkg.run_id).all()
    assert len(logs) >= 3  # context + assessment + challenge + planner

    actions = [l.action for l in logs]
    assert "BUILD_ASSESSMENT_CONTEXT" in actions
    assert "CREATE_HYPOTHESIS" in actions
    assert "CREATE_CHALLENGE" in actions
    assert "RECOMMEND_INVESTIGATION" in actions


def test_human_decision_adjudication(agent_db):
    """Verify human examiner can confirm, request evidence, or reject finding."""
    orchestrator = AgentOrchestrator()
    pkg = orchestrator.run_analysis("FIND-AGENT-01", agent_db, force_fallback=True)

    # Human confirms finding
    updated_run = orchestrator.apply_human_decision(
        run_id=pkg.run_id,
        decision="CONFIRM",
        notes="Reviewed supporting alert telemetry and validated observation.",
        reviewer="Supervisor Lead",
        db=agent_db,
    )

    assert updated_run.state == "COMPLETED"
    assert updated_run.human_decision == "CONFIRM"

    # Finding status updated
    finding = agent_db.query(domain.Finding).filter(domain.Finding.id == "FIND-AGENT-01").first()
    assert finding.status == "Confirmed by Supervisor"


def test_mock_llm_client_integration(agent_db):
    """Verify custom local LLM client structured output is validated through guardrails."""
    mock_payload = {
        "agent": "assessment_agent",
        "hypothesis": "Local LLM hypothesis citing ALT-101 and ALT-102.",
        "finding_confidence": "HIGH",
        "assessment_validity": "CAUTION",
        "supporting_evidence": ["ALT-101", "ALT-102"],
        "limitations": ["Case telemetry not submitted"],
        "reasoning": [
            {"statement": "Alerts ALT-101 and ALT-102 uninvestigated.", "evidence_ids": ["ALT-101", "ALT-102"]}
        ],
        "alternative_explanations": ["External ticketing"],
    }
    mock_client = MockLocalLLMClient(mock_payload)
    agent = AssessmentAgent(llm_client=mock_client)

    from app.agents.evidence_context import build_assessment_context
    ctx = build_assessment_context("FIND-AGENT-01", agent_db)
    res = agent.run(ctx, force_fallback=False)

    assert res.hypothesis == "Local LLM hypothesis citing ALT-101 and ALT-102."
    assert res.supporting_evidence == ["ALT-101", "ALT-102"]
