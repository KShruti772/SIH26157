"""
SAT-SA Cryptographic Audit & Replay Engine Tests (Module 9).
Tests cover:
1. event creation
2. deterministic hashing
3. event chaining
4. valid chain verification
5. tampering detection
6. replay reconstruction
7. replay state equality
8. human decision audit event
9. agent action audit events
10. evidence provenance
11. historical immutability
12. broken chain detection
13. empty analysis handling
14. multiple events ordering
15. snapshot creation
16. snapshot hash stability
"""

import pytest
import datetime
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import domain
from app.services.audit import (
    AuditService,
    ReplayEngine,
    EventType,
    ActorType,
    compute_event_hash,
    serialize_canonical_json,
    compute_sha256,
)
from app.services import workspace, reporting


@pytest.fixture
def audit_db():
    """Isolated in-memory SQLite database for audit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed an entity
    entity = domain.Entity(
        id="CSE-TEST-01",
        name="Grid Operations Alpha",
        sector="Energy & Power",
        assessment_period="Q3 2026",
    )
    session.add(entity)

    # Seed an upload
    upload = domain.DatasetUpload(
        id="UPL-AUDIT-01",
        filename="soc_alerts_q3.csv",
        file_type="csv",
        dataset_type="alerts",
        source_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        records_received=10,
        records_valid=10,
        records_rejected=0,
        status="validated",
        entity_ids=["CSE-TEST-01"],
    )
    session.add(upload)
    session.commit()

    yield session
    session.close()


# 1. EVENT CREATION
def test_event_creation(audit_db):
    """Test creating an audit event persists all required fields and assigns a valid SHA-256 hash."""
    svc = AuditService()
    event = svc.record_event(
        db=audit_db,
        event_type=EventType.DATA_INGESTED,
        actor_type=ActorType.SYSTEM,
        actor_id="IngestionService",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"filename": "soc_alerts_q3.csv", "records_valid": 10},
    )

    assert event.id is not None
    assert event.event_id.startswith("EVT-")
    assert event.event_type == EventType.DATA_INGESTED
    assert event.actor_type == ActorType.SYSTEM
    assert event.entity_id == "CSE-TEST-01"
    assert event.analysis_id == "UPL-AUDIT-01"
    assert len(event.event_hash) == 64
    assert event.previous_event_hash is None


# 2. DETERMINISTIC HASHING
def test_deterministic_hashing():
    """Verify that identical event content produces identical SHA-256 hashes regardless of dictionary key ordering."""
    ts = datetime.datetime(2026, 10, 8, 12, 0, 0)
    
    hash1 = compute_event_hash(
        event_type=EventType.ANALYSIS_STARTED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="SupervisoryAnalyticsEngine",
        timestamp=ts,
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"b_key": "val2", "a_key": "val1"},
        previous_event_hash="0000000000000000000000000000000000000000000000000000000000000000",
    )

    hash2 = compute_event_hash(
        event_type=EventType.ANALYSIS_STARTED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="SupervisoryAnalyticsEngine",
        timestamp=ts,
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"a_key": "val1", "b_key": "val2"},
        previous_event_hash="0000000000000000000000000000000000000000000000000000000000000000",
    )

    assert hash1 == hash2
    assert len(hash1) == 64


# 3. EVENT CHAINING
def test_event_chaining(audit_db):
    """Verify sequential events link previous_event_hash to the preceding event's event_hash."""
    svc = AuditService()
    
    # Event 1
    e1 = svc.record_event(
        db=audit_db,
        event_type=EventType.DATA_INGESTED,
        actor_type=ActorType.SYSTEM,
        actor_id="IngestionService",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"step": 1},
    )

    # Event 2
    e2 = svc.record_event(
        db=audit_db,
        event_type=EventType.ANALYSIS_STARTED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="AnalyticsEngine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"step": 2},
    )

    # Event 3
    e3 = svc.record_event(
        db=audit_db,
        event_type=EventType.FINDING_CREATED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="AnalyticsEngine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        finding_id="FIND-001",
        payload={"type": "Uninvestigated Critical Alert"},
    )

    assert e1.previous_event_hash is None
    assert e2.previous_event_hash == e1.event_hash
    assert e3.previous_event_hash == e2.event_hash


# 4. VALID CHAIN VERIFICATION
def test_valid_chain_verification(audit_db):
    """Verify verify_chain returns valid=True when all links and signatures match."""
    svc = AuditService()
    for i in range(5):
        svc.record_event(
            db=audit_db,
            event_type=EventType.FINDING_CREATED,
            actor_type=ActorType.ANALYTICS_ENGINE,
            actor_id="Engine",
            entity_id="CSE-TEST-01",
            analysis_id="UPL-AUDIT-01",
            finding_id=f"FIND-{i}",
            payload={"index": i},
        )

    events = svc.get_analysis_events(audit_db, analysis_id="UPL-AUDIT-01")
    assert len(events) == 5

    res = svc.verify_chain(events)
    assert res["valid"] is True
    assert res["total_events"] == 5
    assert res["broken_at_index"] is None
    assert res["error"] is None


# 5. TAMPERING DETECTION (PAYLOAD MODIFIED)
def test_tampering_detection(audit_db):
    """Verify that tampering with an event's payload causes hash recomputation failure and reports the broken event."""
    svc = AuditService()
    e1 = svc.record_event(
        db=audit_db,
        event_type=EventType.ANALYSIS_STARTED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="Engine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"status": "INITIAL"},
    )
    e2 = svc.record_event(
        db=audit_db,
        event_type=EventType.FINDING_CREATED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="Engine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        finding_id="FIND-001",
        payload={"severity": "HIGH"},
    )

    events = svc.get_analysis_events(audit_db, analysis_id="UPL-AUDIT-01")
    
    # Tamper with event 2 payload directly in memory
    events[1].payload_json = {"severity": "CRITICAL_TAMPERED"}

    res = svc.verify_chain(events)
    assert res["valid"] is False
    assert res["broken_at_index"] == 1
    assert res["broken_event_id"] == e2.event_id
    assert "Tampered event payload" in res["error"]


# 6. REPLAY RECONSTRUCTION
def test_replay_reconstruction(audit_db):
    """Verify ReplayEngine rebuilds the assessment state step-by-step from raw audit events."""
    svc = AuditService()
    engine = ReplayEngine(audit_service=svc)

    # 1. Ingestion
    svc.record_event(
        db=audit_db,
        event_type=EventType.DATA_INGESTED,
        actor_type=ActorType.SYSTEM,
        actor_id="Ingestion",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"filename": "alerts.csv", "records_valid": 5},
    )

    # 2. Finding created
    svc.record_event(
        db=audit_db,
        event_type=EventType.FINDING_CREATED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="Analytics",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        finding_id="FIND-REPLAY-1",
        payload={
            "finding_id": "FIND-REPLAY-1",
            "type": "Uninvestigated Critical Alert",
            "category": "Execution Gap",
            "severity": "CRITICAL",
            "confidence": 0.95,
            "assessment_validity": "HIGH",
            "analytic_rule": "RULE_CRIT_NO_CASE",
        },
    )

    # 3. Assurance evaluated
    svc.record_event(
        db=audit_db,
        event_type=EventType.ASSURANCE_CREATED,
        actor_type=ActorType.SYSTEM,
        actor_id="AssuranceEngine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        payload={"overall_status": "HIGH", "coverage_details": {"completeness": "HIGH"}},
    )

    # Also persist corresponding database finding to check state match
    finding = domain.Finding(
        id="FIND-REPLAY-1",
        upload_id="UPL-AUDIT-01",
        entity_id="CSE-TEST-01",
        type="Uninvestigated Critical Alert",
        category="Execution Gap",
        severity="CRITICAL",
        confidence=0.95,
        assessment_validity="HIGH",
        decision_status="OPEN",
    )
    audit_db.add(finding)
    assurance = domain.AssessmentAssurance(
        id="ASR-01",
        analysis_id="UPL-AUDIT-01",
        entity_id="CSE-TEST-01",
        overall_status="HIGH",
    )
    audit_db.add(assurance)
    audit_db.commit()

    replay_res = engine.replay_analysis(db=audit_db, analysis_id="UPL-AUDIT-01", entity_id="CSE-TEST-01")

    assert replay_res["replay_valid"] is True
    assert replay_res["chain_integrity"] == "VERIFIED"
    assert replay_res["state_match"] is True
    assert replay_res["events_processed"] == 3
    assert len(replay_res["reconstructed_state"]["findings"]) == 1
    assert replay_res["reconstructed_state"]["findings"][0]["id"] == "FIND-REPLAY-1"
    assert replay_res["reconstructed_state"]["findings"][0]["severity"] == "CRITICAL"


# 7. REPLAY STATE EQUALITY (MISMATCH DETECTION)
def test_replay_state_equality_detects_drift(audit_db):
    """Verify ReplayEngine detects when database state drifts from what is recorded in the audit ledger."""
    svc = AuditService()
    engine = ReplayEngine(audit_service=svc)

    svc.record_event(
        db=audit_db,
        event_type=EventType.FINDING_CREATED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="Analytics",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        finding_id="FIND-DRIFT-1",
        payload={
            "finding_id": "FIND-DRIFT-1",
            "type": "Uninvestigated Critical Alert",
            "category": "Execution Gap",
            "severity": "CRITICAL",
            "confidence": 0.95,
            "decision_status": "OPEN",
        },
    )

    # Persist in DB with a different status (e.g. manually altered without audit event)
    finding = domain.Finding(
        id="FIND-DRIFT-1",
        upload_id="UPL-AUDIT-01",
        entity_id="CSE-TEST-01",
        type="Uninvestigated Critical Alert",
        category="Execution Gap",
        severity="CRITICAL",
        confidence=0.95,
        decision_status="CONFIRMED",  # Drifted from OPEN
    )
    audit_db.add(finding)
    audit_db.commit()

    replay_res = engine.replay_analysis(db=audit_db, analysis_id="UPL-AUDIT-01", entity_id="CSE-TEST-01")

    assert replay_res["chain_integrity"] == "VERIFIED"
    assert replay_res["state_match"] is False
    assert replay_res["replay_valid"] is False
    assert len(replay_res["mismatches"]) > 0
    assert replay_res["mismatches"][0]["component"] == "finding_decision"


# 8. HUMAN DECISION AUDIT EVENT
def test_human_decision_audit_event(audit_db):
    """Verify human decision recording creates a HUMAN_DECISION_CREATED audit event with hash continuity."""
    svc = AuditService()

    finding = domain.Finding(
        id="FIND-DEC-01",
        upload_id="UPL-AUDIT-01",
        entity_id="CSE-TEST-01",
        type="Uninvestigated Critical Alert",
        category="Execution Gap",
        severity="CRITICAL",
        confidence=0.95,
        decision_status="OPEN",
    )
    audit_db.add(finding)
    audit_db.commit()

    # Record human decision via workspace
    decision_out = workspace.record_human_decision(
        finding_id="FIND-DEC-01",
        decision="CONFIRM",
        notes="Confirmed by examiner after reviewing firewall logs.",
        rationale="Clear critical threat trace.",
        reviewer="Supervisory Examiner Smith",
        db=audit_db,
    )

    assert "Confirmed" in decision_out["status"]

    events = svc.get_events(db=audit_db, finding_id="FIND-DEC-01", event_type=EventType.HUMAN_DECISION_CREATED)
    assert len(events) >= 1
    evt = events[0]
    assert evt.actor_type == ActorType.HUMAN_EXAMINER
    assert evt.actor_id == "Supervisory Examiner Smith"
    assert evt.payload_json["decision"] == "CONFIRM"
    assert evt.payload_json["notes"] == "Confirmed by examiner after reviewing firewall logs."


# 9. AGENT ACTION AUDIT EVENTS
def test_agent_action_audit_events(audit_db):
    """Verify Local Agentic AI lifecycle generates structured AGENT_* audit events."""
    svc = AuditService()
    
    # 1. Agent Run Started
    e1 = svc.record_event(
        db=audit_db,
        event_type=EventType.AGENT_RUN_STARTED,
        actor_type=ActorType.SYSTEM,
        actor_id="AgentOrchestrator",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        agent_run_id="RUN-001",
        finding_id="FIND-001",
        payload={"mode": "full"},
    )

    # 2. Assessment Agent
    e2 = svc.record_event(
        db=audit_db,
        event_type=EventType.AGENT_ASSESSMENT_CREATED,
        actor_type=ActorType.ASSESSMENT_AGENT,
        actor_id="AssessmentAgent",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        agent_run_id="RUN-001",
        finding_id="FIND-001",
        payload={"hypothesis": "Execution gap detected on uninvestigated alert.", "confidence": 0.9},
    )

    # 3. Challenge Agent
    e3 = svc.record_event(
        db=audit_db,
        event_type=EventType.AGENT_CHALLENGE_CREATED,
        actor_type=ActorType.CHALLENGE_AGENT,
        actor_id="ChallengeAgent",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        agent_run_id="RUN-001",
        finding_id="FIND-001",
        payload={"challenge_status": "CONTESTED", "alternative_hypothesis": "Missing telemetry"},
    )

    # 4. Investigation Planner
    e4 = svc.record_event(
        db=audit_db,
        event_type=EventType.AGENT_RECOMMENDATION_CREATED,
        actor_type=ActorType.INVESTIGATION_PLANNER,
        actor_id="InvestigationPlanner",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        agent_run_id="RUN-001",
        finding_id="FIND-001",
        payload={"recommended_action": "REQUEST_EVIDENCE"},
    )

    # 5. Agent Run Completed
    e5 = svc.record_event(
        db=audit_db,
        event_type=EventType.AGENT_RUN_COMPLETED,
        actor_type=ActorType.SYSTEM,
        actor_id="AgentOrchestrator",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        agent_run_id="RUN-001",
        finding_id="FIND-001",
        payload={"final_state": "COMPLETED"},
    )

    events = [e1, e2, e3, e4, e5]
    verification = svc.verify_chain(events)
    assert verification["valid"] is True
    assert verification["total_events"] == 5


# 10. EVIDENCE PROVENANCE
def test_evidence_provenance(audit_db):
    """Verify evidence requests append EVIDENCE_REQUEST_CREATED and maintain references to findings and entities."""
    finding = domain.Finding(
        id="FIND-PROV-01",
        upload_id="UPL-AUDIT-01",
        entity_id="CSE-TEST-01",
        type="Uninvestigated Critical Alert",
        category="Execution Gap",
        severity="HIGH",
        confidence=0.85,
        decision_status="OPEN",
    )
    audit_db.add(finding)
    audit_db.commit()

    req = workspace.create_evidence_request(
        finding_id="FIND-PROV-01",
        request_type="TIER2_ESCALATION_TICKET",
        reason="Check if Tier-2 escalation occurred out-of-band.",
        requested_by="Examiner Lead",
        db=audit_db,
    )

    svc = AuditService()
    events = svc.get_events(db=audit_db, finding_id="FIND-PROV-01", event_type=EventType.EVIDENCE_REQUEST_CREATED)
    assert len(events) == 1
    assert events[0].evidence_request_id == req.id
    assert events[0].payload_json["request_type"] == "TIER2_ESCALATION_TICKET"
    assert events[0].actor_id == "Examiner Lead"


# 11. HISTORICAL IMMUTABILITY
def test_historical_immutability(audit_db):
    """Verify that updates to findings create new FINDING_UPDATED events without altering old FINDING_CREATED events."""
    svc = AuditService()

    # Create initial event
    e_created = svc.record_event(
        db=audit_db,
        event_type=EventType.FINDING_CREATED,
        actor_type=ActorType.ANALYTICS_ENGINE,
        actor_id="Engine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        finding_id="FIND-IMMUT-01",
        payload={"severity": "MEDIUM", "confidence": 0.70},
    )

    # Later update event
    e_updated = svc.record_event(
        db=audit_db,
        event_type=EventType.FINDING_UPDATED,
        actor_type=ActorType.HUMAN_EXAMINER,
        actor_id="Examiner",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
        finding_id="FIND-IMMUT-01",
        payload={"severity": "HIGH", "confidence": 0.90, "reason": "Corroborated by external report"},
    )

    # Re-fetch initial event from DB
    e_created_refreshed = audit_db.query(domain.AuditEvent).filter(domain.AuditEvent.id == e_created.id).first()
    assert e_created_refreshed.payload_json["severity"] == "MEDIUM"
    assert e_created_refreshed.event_hash == e_created.event_hash

    # Verify chain
    res = svc.verify_chain([e_created, e_updated])
    assert res["valid"] is True


# 12. BROKEN CHAIN DETECTION
def test_broken_chain_detection(audit_db):
    """Verify broken previous_event_hash linkage is accurately detected and isolated."""
    svc = AuditService()
    e1 = svc.record_event(
        db=audit_db,
        event_type=EventType.ANALYSIS_STARTED,
        actor_type=ActorType.SYSTEM,
        actor_id="Engine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
    )
    e2 = svc.record_event(
        db=audit_db,
        event_type=EventType.ANALYSIS_COMPLETED,
        actor_type=ActorType.SYSTEM,
        actor_id="Engine",
        entity_id="CSE-TEST-01",
        analysis_id="UPL-AUDIT-01",
    )

    # Break link manually on second event
    e2_copy = domain.AuditEvent(
        id=e2.id,
        event_id=e2.event_id,
        entity_id=e2.entity_id,
        analysis_id=e2.analysis_id,
        event_type=e2.event_type,
        actor_type=e2.actor_type,
        actor_id=e2.actor_id,
        timestamp=e2.timestamp,
        payload_json=e2.payload_json,
        previous_event_hash="BAD_HASH_FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        event_hash=e2.event_hash,
    )

    res = svc.verify_chain([e1, e2_copy])
    assert res["valid"] is False
    assert res["broken_at_index"] == 1
    assert "Broken chain link" in res["error"]


# 13. EMPTY ANALYSIS HANDLING
def test_empty_analysis_handling(audit_db):
    """Verify verify_chain and replay_analysis gracefully handle empty/non-existent streams."""
    svc = AuditService()
    engine = ReplayEngine(audit_service=svc)

    res_verify = svc.verify_chain([])
    assert res_verify["valid"] is True
    assert res_verify["total_events"] == 0

    res_replay = engine.replay_analysis(audit_db, analysis_id="NON_EXISTENT_ANALYSIS")
    assert res_replay["replay_valid"] is False
    assert res_replay["chain_integrity"] == "EMPTY"
    assert res_replay["events_processed"] == 0


# 14. MULTIPLE EVENTS ORDERING
def test_multiple_events_ordering(audit_db):
    """Verify events maintain strict monotonic sequence order and can be fetched in ASC or DESC order."""
    svc = AuditService()
    for i in range(10):
        svc.record_event(
            db=audit_db,
            event_type=EventType.DATA_VALIDATED,
            actor_type=ActorType.SYSTEM,
            actor_id="Validator",
            entity_id="CSE-TEST-01",
            analysis_id="UPL-ORDER-01",
            payload={"seq": i},
        )

    asc_events = svc.get_events(audit_db, analysis_id="UPL-ORDER-01", order="asc")
    desc_events = svc.get_events(audit_db, analysis_id="UPL-ORDER-01", order="desc")

    assert len(asc_events) == 10
    assert len(desc_events) == 10
    assert [e.payload_json["seq"] for e in asc_events] == list(range(10))
    assert [e.payload_json["seq"] for e in desc_events] == list(range(9, -1, -1))


# 15. SNAPSHOT CREATION
def test_snapshot_creation(audit_db):
    """Verify create_snapshot captures entity, findings, capabilities, assurance, and records a SNAPSHOT_CREATED event."""
    svc = AuditService()

    finding = domain.Finding(
        id="FIND-SNAP-01",
        upload_id="UPL-AUDIT-01",
        entity_id="CSE-TEST-01",
        type="Uninvestigated Critical Alert",
        category="Execution Gap",
        severity="HIGH",
        confidence=0.9,
        assessment_validity="HIGH",
    )
    audit_db.add(finding)
    audit_db.commit()

    snap = svc.create_snapshot(db=audit_db, entity_id="CSE-TEST-01", analysis_id="UPL-AUDIT-01")

    assert snap.id.startswith("SNP-")
    assert snap.entity_id == "CSE-TEST-01"
    assert len(snap.snapshot_hash) == 64
    assert snap.data_json["entity"]["id"] == "CSE-TEST-01"
    assert len(snap.data_json["findings"]) == 1

    # Check SNAPSHOT_CREATED audit event was recorded
    events = svc.get_events(db=audit_db, entity_id="CSE-TEST-01", event_type=EventType.SNAPSHOT_CREATED)
    assert len(events) >= 1
    assert events[-1].source_snapshot_hash == snap.snapshot_hash


# 16. SNAPSHOT HASH STABILITY
def test_snapshot_hash_stability():
    """Verify that canonical JSON serialization produces deterministic hashes for complex snapshot payloads."""
    snapshot_payload = {
        "analysis_id": "ANL-TEST",
        "capabilities": [
            {"assessment_validity": "HIGH", "findings_count": 2, "name": "Threat Detection", "status": "OBSERVED CONCERN"},
            {"assessment_validity": "HIGH", "findings_count": 0, "name": "Governance & Oversight", "status": "NO OBSERVED CONCERN"},
        ],
        "entity": {"id": "CSE-001", "name": "Power Grid", "sector": "Energy"},
        "findings": [
            {"confidence": 0.95, "id": "F-1", "severity": "CRITICAL", "type": "Execution Gap"},
        ],
    }

    str1 = serialize_canonical_json(snapshot_payload)
    hash1 = compute_sha256(str1)

    # Alter key insertion order
    snapshot_payload_reordered = {
        "findings": [
            {"type": "Execution Gap", "id": "F-1", "severity": "CRITICAL", "confidence": 0.95},
        ],
        "entity": {"sector": "Energy", "name": "Power Grid", "id": "CSE-001"},
        "capabilities": [
            {"status": "OBSERVED CONCERN", "name": "Threat Detection", "findings_count": 2, "assessment_validity": "HIGH"},
            {"status": "NO OBSERVED CONCERN", "name": "Governance & Oversight", "findings_count": 0, "assessment_validity": "HIGH"},
        ],
        "analysis_id": "ANL-TEST",
    }

    str2 = serialize_canonical_json(snapshot_payload_reordered)
    hash2 = compute_sha256(str2)

    assert hash1 == hash2
    assert len(hash1) == 64
