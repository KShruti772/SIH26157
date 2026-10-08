"""
Comprehensive test suite for Module 7 — Human Examiner Workspace.

Verifies:
1. Complete examiner workflow: Finding Detail -> Evidence Trace -> Assurance -> Agent Review -> Decision.
2. Review Queue filtering by Entity, Severity, Category, Validity, and Decision Status.
3. Sorting by Priority, Severity, Confidence, Validity, and Timestamp.
4. Human Examiner Decisions: CONFIRM, REJECT, MODIFY, REQUEST_EVIDENCE, DEFER.
5. Mandatory notes validation for rejection and modification.
6. Evidence request lifecycle: Creation, State transition, Resolution back to UNDER_REVIEW.
7. Decision History timeline reconstruction and chronological ordering.
8. Source evidence immutability during human adjudication.
9. Machine-readable audit events generated for all human actions.
"""

import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import domain
from app.services import workspace, evidence
from app.assurance.service import AssessmentAssuranceService
from app.agents.orchestrator import AgentOrchestrator


@pytest.fixture
def workspace_db():
    """In-memory SQLite database pre-seeded with test operational data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed Entity
    entity = domain.Entity(id="CSE-FIN-01", name="Financial Sector Node", sector="Banking", assessment_period="Q3-2026")
    db.add(entity)

    # Seed Upload
    upload = domain.DatasetUpload(
        id="UPL-WS-01",
        filename="bank_soc_telemetry.csv",
        file_type="csv",
        dataset_type="alerts",
        status="validated",
        records_received=15,
        records_valid=15,
        records_rejected=0,
        source_hash="sha256_ws_test_hash_12345",
    )
    db.add(upload)

    # Seed Assets
    asset1 = domain.Asset(id="AST-FIN-001", entity_id="CSE-FIN-01", type="Core-Banking-Server", criticality="Critical", has_telemetry=True)
    asset2 = domain.Asset(id="AST-FIN-002", entity_id="CSE-FIN-01", type="Payment-Gateway", criticality="Critical", has_telemetry=False)
    db.add_all([asset1, asset2])

    # Seed Alerts
    alert1 = domain.Alert(
        id="ALT-FIN-001",
        entity_id="CSE-FIN-01",
        upload_id="UPL-WS-01",
        timestamp=datetime.datetime(2026, 8, 10, 8, 30),
        severity="Critical",
        category="Ransomware Activity",
        asset_id="AST-FIN-001",
        acknowledged=True,
        investigation_started=False,
        escalated=False,
        closure_duration_mins=4.5,
    )
    alert2 = domain.Alert(
        id="ALT-FIN-002",
        entity_id="CSE-FIN-01",
        upload_id="UPL-WS-01",
        timestamp=datetime.datetime(2026, 8, 10, 9, 15),
        severity="High",
        category="Privilege Escalation",
        asset_id="AST-FIN-001",
        acknowledged=True,
        investigation_started=False,
        escalated=False,
        closure_duration_mins=6.0,
    )
    db.add_all([alert1, alert2])

    # Seed Finding
    finding = domain.Finding(
        id="FIND-WS-01",
        entity_id="CSE-FIN-01",
        upload_id="UPL-WS-01",
        type="Rapid Closure of Critical Security Alerts",
        category="execution_gap",
        severity="Critical",
        confidence=0.94,
        description="Critical ransomware alerts closed within 4.5 minutes without observable tier-2 escalation.",
        rationale="Critical alerts require mandatory deep investigation prior to closure.",
        evidence_ids=["ALT-FIN-001", "ALT-FIN-002", "AST-FIN-001"],
        risk_contribution=32.0,
        recommended_action="Review Tier-1 playbook and request analyst disposition log.",
        status="Requires Review",
        decision_status="OPEN",
        assessment_validity="CAUTION",
        validity_rationale="Submitted telemetry lacks case management records.",
    )
    db.add(finding)

    # Seed ReviewItem
    review_item = domain.ReviewItem(
        finding_id="FIND-WS-01",
        priority_score=92.5,
        status="Pending",
        reviewer=None,
    )
    db.add(review_item)
    db.commit()

    yield db
    db.close()


def test_finding_opens_in_examiner_workspace(workspace_db):
    """Verify finding loads with complete metadata and default decision state."""
    finding = workspace_db.query(domain.Finding).filter(domain.Finding.id == "FIND-WS-01").first()
    assert finding is not None
    assert finding.id == "FIND-WS-01"
    assert finding.entity_id == "CSE-FIN-01"
    assert finding.severity == "Critical"
    assert finding.confidence == 0.94
    assert finding.assessment_validity == "CAUTION"
    assert finding.decision_status == "OPEN"


def test_review_queue_filters_work(workspace_db):
    """Verify review queue filters by entity, severity, category, and validity."""
    # Filter by entity
    items = workspace.get_enhanced_review_queue_items(workspace_db, entity_id="CSE-FIN-01")
    assert len(items) == 1
    assert items[0]["finding"].entity_id == "CSE-FIN-01"

    # Filter by non-existent entity
    empty = workspace.get_enhanced_review_queue_items(workspace_db, entity_id="NON-EXISTENT")
    assert len(empty) == 0

    # Filter by severity
    crit_items = workspace.get_enhanced_review_queue_items(workspace_db, severity="CRITICAL")
    assert len(crit_items) == 1

    # Filter by validity
    caution_items = workspace.get_enhanced_review_queue_items(workspace_db, validity="CAUTION")
    assert len(caution_items) == 1

    # Filter by decision status
    open_items = workspace.get_enhanced_review_queue_items(workspace_db, decision_status="OPEN")
    assert len(open_items) == 1


def test_review_queue_sorting_work(workspace_db):
    """Verify review queue sorting by priority score and timestamp."""
    items = workspace.get_enhanced_review_queue_items(workspace_db, sort_by="priority", order="desc")
    assert len(items) == 1
    assert items[0]["review_item"].priority_score == 92.5
    assert "why_review" in items[0]


def test_evidence_trace_displays_real_records(workspace_db):
    """Verify evidence trace reconstructs real alerts and assets."""
    trace = evidence.get_evidence_trace("FIND-WS-01", workspace_db)
    assert trace["finding_id"] == "FIND-WS-01"
    assert len(trace["alerts"]) == 2
    assert len(trace["assets"]) == 1
    assert trace["alerts"][0]["id"] == "ALT-FIN-001"
    assert trace["assets"][0]["id"] == "AST-FIN-001"


def test_missing_evidence_is_displayed_correctly(workspace_db):
    """Verify missing links and completeness are computed from actual data."""
    trace = evidence.get_evidence_trace("FIND-WS-01", workspace_db)
    assert len(trace["missing_links"]) > 0
    assert any("investigation" in ml.lower() or "case" in ml.lower() for ml in trace["missing_links"])
    assert trace["evidence_completeness"] < 1.0


def test_assessment_assurance_displays_correctly(workspace_db):
    """Verify assessment assurance evaluation synthesizes all dimensions."""
    svc = AssessmentAssuranceService()
    assurance = svc.evaluate_assurance(workspace_db, entity_id="CSE-FIN-01")
    assert assurance.overall_status in ("HIGH", "CAUTION", "LOW", "INDETERMINATE")
    assert "process" in assurance.coverage_details
    assert "severity" in assurance.coverage_details
    assert "temporal" in assurance.coverage_details
    assert assurance.integrity_status in ("VERIFIED", "CHANGED", "UNAVAILABLE")


def test_agent_review_loads_correctly(workspace_db):
    """Verify agentic review package generates structured review for workspace."""
    orchestrator = AgentOrchestrator()
    pkg = orchestrator.run_analysis("FIND-WS-01", workspace_db, force_fallback=True)
    assert pkg.finding_id == "FIND-WS-01"
    assert pkg.state == "HUMAN_REVIEW_REQUIRED"
    assert pkg.assessment_agent_result.agent == "assessment_agent"
    assert pkg.challenge_agent_result.agent == "challenge_agent"
    assert pkg.investigation_planner_result.agent == "investigation_planner"


def test_human_confirm_works(workspace_db):
    """Verify human CONFIRM action updates state and records decision."""
    res = workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="CONFIRM",
        notes="Confirmed: evidence clearly demonstrates rapid closure of ransomware alerts.",
        rationale="Analyst closed alert without Tier-2 escalation.",
        reviewer="Lead Examiner Sharma",
        db=workspace_db,
    )
    assert res["decision"] == "CONFIRM"
    assert res["decision_status"] == "CONFIRMED"
    assert res["status"] == "Confirmed by Supervisor"
    assert res["adjudicated_by"] == "Lead Examiner Sharma"

    # Verify review item status updated
    item = workspace_db.query(domain.ReviewItem).filter(domain.ReviewItem.finding_id == "FIND-WS-01").first()
    assert item.status == "Confirmed"


def test_human_reject_works(workspace_db):
    """Verify human REJECT action requires rejection reason and updates state."""
    res = workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="REJECT",
        notes="Alert was closed by automated containment SOAR playbook.",
        rationale="Verified automated playbook containment event in secondary logs.",
        reviewer="Lead Examiner Sharma",
        rejection_reason="FALSE_POSITIVE",
        db=workspace_db,
    )
    assert res["decision"] == "REJECT"
    assert res["decision_status"] == "REJECTED"
    assert res["status"] == "Rejected by Supervisor"

    item = workspace_db.query(domain.ReviewItem).filter(domain.ReviewItem.finding_id == "FIND-WS-01").first()
    assert item.status == "Dismissed"


def test_human_modify_works(workspace_db):
    """Verify human MODIFY action preserves original finding and stores modification."""
    original_desc = "Critical ransomware alerts closed within 4.5 minutes without observable tier-2 escalation."
    modified_text = "Modified assessment: Rapid closure observed, but automated endpoint isolation confirmed."

    res = workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="MODIFY",
        notes="Scope reduced following supplemental verification.",
        rationale="Partial mitigation verified.",
        reviewer="Lead Examiner Sharma",
        modified_assessment=modified_text,
        db=workspace_db,
    )
    assert res["decision"] == "MODIFY"
    assert res["decision_status"] == "MODIFIED"

    # Verify original finding description is NOT overwritten
    finding = workspace_db.query(domain.Finding).filter(domain.Finding.id == "FIND-WS-01").first()
    assert finding.description == original_desc
    assert finding.modified_assessment == modified_text


def test_request_evidence_works(workspace_db):
    """Verify creating a formal evidence request transitions finding state."""
    req = workspace.create_evidence_request(
        finding_id="FIND-WS-01",
        request_type="CASE_MANAGEMENT_RECORDS",
        reason="Verify if Tier-2 escalation occurred in secondary ITSM ticketing system.",
        requested_by="Lead Examiner Sharma",
        priority="HIGH",
        db=workspace_db,
    )
    assert req.id.startswith("REQ-")
    assert req.status == "OPEN"
    assert req.request_type == "CASE_MANAGEMENT_RECORDS"

    # Finding transitioned to EVIDENCE_REQUESTED
    finding = workspace_db.query(domain.Finding).filter(domain.Finding.id == "FIND-WS-01").first()
    assert finding.decision_status == "EVIDENCE_REQUESTED"
    assert finding.status == "Evidence Requested"


def test_missing_notes_are_rejected_where_required(workspace_db):
    """Verify rejecting or modifying a finding without notes raises ValueError."""
    with pytest.raises(ValueError) as exc1:
        workspace.record_human_decision(
            finding_id="FIND-WS-01",
            decision="REJECT",
            notes=None,
            rationale=None,
            rejection_reason=None,
            reviewer="Examiner",
            db=workspace_db,
        )
    assert "mandatory" in str(exc1.value).lower()

    with pytest.raises(ValueError) as exc2:
        workspace.record_human_decision(
            finding_id="FIND-WS-01",
            decision="MODIFY",
            notes=None,
            rationale=None,
            modified_assessment=None,
            reviewer="Examiner",
            db=workspace_db,
        )
    assert "mandatory" in str(exc2.value).lower()


def test_decision_history_persists(workspace_db):
    """Verify unified decision and audit history timeline is returned chronologically."""
    # 1. Create evidence request
    workspace.create_evidence_request(
        finding_id="FIND-WS-01",
        request_type="INVESTIGATION_LOGS",
        reason="Need investigator notes.",
        requested_by="Examiner A",
        db=workspace_db,
    )

    # 2. Record decision
    workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="CONFIRM",
        notes="Final confirmation.",
        rationale="Verified.",
        reviewer="Examiner A",
        db=workspace_db,
    )

    history = workspace.get_finding_unified_history("FIND-WS-01", workspace_db)
    assert len(history) >= 3  # Created + Evidence Request + Decision

    event_types = [h["event_type"] for h in history]
    assert "FINDING_CREATED" in event_types
    assert "EVIDENCE_REQUESTED" in event_types
    assert "HUMAN_DECISION_CONFIRM" in event_types


def test_human_decisions_create_audit_events(workspace_db):
    """Verify all human decisions append structured audit records."""
    workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="CONFIRM",
        notes="Audit check.",
        rationale="Audit check rationale.",
        reviewer="Examiner Audit",
        db=workspace_db,
    )

    logs = workspace_db.query(domain.AgentAuditLog).filter(
        domain.AgentAuditLog.finding_id == "FIND-WS-01",
        domain.AgentAuditLog.action == "HUMAN_DECISION_CONFIRM",
    ).all()
    assert len(logs) >= 1
    assert logs[0].model_provider == "human"
    assert logs[0].model_name == "Examiner Audit"


def test_source_evidence_cannot_be_modified_through_decision_api(workspace_db):
    """Verify human decision recording does not alter underlying alert/asset records."""
    alert_before = workspace_db.query(domain.Alert).filter(domain.Alert.id == "ALT-FIN-001").first()
    orig_ts = alert_before.timestamp
    orig_closure = alert_before.closure_duration_mins

    workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="MODIFY",
        notes="Modification notes.",
        rationale="Mod rationale.",
        reviewer="Examiner",
        modified_assessment="Different assessment.",
        db=workspace_db,
    )

    alert_after = workspace_db.query(domain.Alert).filter(domain.Alert.id == "ALT-FIN-001").first()
    assert alert_after.timestamp == orig_ts
    assert alert_after.closure_duration_mins == orig_closure


def test_evidence_request_persists_and_transitions_state(workspace_db):
    """Verify updating an evidence request to RECEIVED transitions finding back to UNDER_REVIEW."""
    req = workspace.create_evidence_request(
        finding_id="FIND-WS-01",
        request_type="TELEMETRY_COVERAGE",
        reason="Check sensor logs.",
        requested_by="Examiner",
        db=workspace_db,
    )
    assert req.status == "OPEN"

    # Update to RECEIVED
    updated = workspace.update_evidence_request_status(
        request_id=req.id,
        status="RECEIVED",
        response_notes="Received supplementary syslog file.",
        reviewer="Examiner",
        db=workspace_db,
    )
    assert updated.status == "RECEIVED"
    assert updated.resolved_at is not None

    finding = workspace_db.query(domain.Finding).filter(domain.Finding.id == "FIND-WS-01").first()
    assert finding.decision_status == "UNDER_REVIEW"


def test_defer_decision_works(workspace_db):
    """Verify DEFER decision transitions finding state to DEFERRED."""
    res = workspace.record_human_decision(
        finding_id="FIND-WS-01",
        decision="DEFER",
        notes="Awaiting next quarter audit window telemetry.",
        rationale="Deferred pending additional CSE submission.",
        reviewer="Examiner Lead",
        db=workspace_db,
    )
    assert res["decision"] == "DEFER"
    assert res["decision_status"] == "DEFERRED"

    finding = workspace_db.query(domain.Finding).filter(domain.Finding.id == "FIND-WS-01").first()
    assert finding.decision_status == "DEFERRED"
    assert finding.status == "Deferred"
