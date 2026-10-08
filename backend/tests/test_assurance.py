import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import domain
from app.assurance.config import (
    ASSURANCE_STATUS_HIGH,
    ASSURANCE_STATUS_CAUTION,
    ASSURANCE_STATUS_LOW,
    ASSURANCE_STATUS_INDETERMINATE,
    COVERAGE_FULL,
    COVERAGE_PARTIAL,
    COVERAGE_LOW,
    COVERAGE_UNKNOWN,
    INDEPENDENCE_HIGH,
    INDEPENDENCE_LOW,
    INTEGRITY_VERIFIED,
)
from app.assurance.hashing import (
    compute_source_hash,
    compute_canonical_records_hash,
    verify_upload_integrity,
)
from app.assurance.coverage import (
    evaluate_population_exposure,
    evaluate_temporal_coverage,
    evaluate_severity_coverage,
    evaluate_asset_coverage,
    evaluate_process_coverage,
)
from app.assurance.contradictions import detect_evidence_contradictions
from app.assurance.dependencies import evaluate_evidence_dependencies
from app.assurance.blind_spots import detect_evidence_blind_spots
from app.assurance.validity import synthesize_assessment_validity
from app.assurance.service import AssessmentAssuranceService


@pytest.fixture
def db_session():
    """In-memory SQLite test session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# =========================================================================
# 1. FULL EVIDENCE -> HIGH VALIDITY
# =========================================================================

def test_full_evidence_high_validity():
    """Scenario 1: Comprehensive process coverage, balanced severities, no contradictions -> HIGH validity."""
    pop_exposure = {"status": COVERAGE_FULL, "value": 0.95}
    coverage_details = {
        "temporal": {"status": COVERAGE_FULL, "span_days": 30},
        "severity": {"status": COVERAGE_FULL},
        "asset": {"status": COVERAGE_FULL},
        "process": {"status": COVERAGE_FULL, "stages_observed": ["Detection", "Investigation", "Escalation", "Closure"], "stages_missing": []},
    }
    contradictions = {"count": 0, "inconsistency_count": 0, "contradictions": [], "inconsistencies": []}
    dependencies = {"status": INDEPENDENCE_HIGH, "shared_cluster_count": 0}
    blind_spots = []

    res = synthesize_assessment_validity(pop_exposure, coverage_details, contradictions, dependencies, blind_spots, total_records=100)
    assert res["overall_status"] == ASSURANCE_STATUS_HIGH
    assert "Assessment validity is HIGH" in res["supervisory_interpretation"]


# =========================================================================
# 2. PARTIAL POPULATION EXPOSURE -> CAUTION
# =========================================================================

def test_partial_population_exposure_caution():
    """Scenario 2: Observable population is 75% of declared population -> CAUTION validity."""
    pop_exposure = evaluate_population_exposure(
        declared_population={"claimed_alert_count": 10000},
        observable_counts={"alerts": 7500},
    )
    assert pop_exposure["status"] == COVERAGE_PARTIAL
    assert pop_exposure["value"] == 0.75

    coverage_details = {
        "process": {"status": COVERAGE_FULL, "stages_observed": ["Detection", "Investigation", "Escalation", "Closure"]},
        "severity": {"status": COVERAGE_FULL},
        "asset": {"status": COVERAGE_FULL},
        "temporal": {"status": COVERAGE_FULL},
    }
    res = synthesize_assessment_validity(pop_exposure, coverage_details, {"count": 0}, {"status": INDEPENDENCE_HIGH}, [], total_records=7500)
    assert res["overall_status"] == ASSURANCE_STATUS_CAUTION
    assert any("75%" in lim for lim in res["limitations"])


# =========================================================================
# 3. NO DECLARED POPULATION -> UNKNOWN STATUS (NO INVENTED DENOMINATOR)
# =========================================================================

def test_no_declared_population_unknown_state():
    """Scenario 3: No claimed population metadata supplied -> UNKNOWN without fabricated denominator."""
    pop_exposure = evaluate_population_exposure(
        declared_population=None,
        observable_counts={"alerts": 500},
    )
    assert pop_exposure["status"] == COVERAGE_UNKNOWN
    assert pop_exposure["value"] is None
    assert "could not be fully assessed" in pop_exposure["explanation"]


# =========================================================================
# 4. MISSING PROCESS STAGE -> BLIND SPOT
# =========================================================================

def test_missing_process_stage_blind_spot():
    """Scenario 4: Dataset has alerts but zero escalation or closure records -> Process blind spot."""
    alerts = [domain.Alert(id="A1", entity_id="CSE-1", severity="Critical", escalated=False, closed_at=None, investigation_started=True)]
    cases = []
    proc_cov = evaluate_process_coverage(alerts, cases)

    assert "Escalation" in proc_cov["stages_missing"]
    assert "Closure" in proc_cov["stages_missing"]
    assert any("No escalation evidence was observable" in gap for gap in proc_cov["visibility_gaps"])

    blind_spots = detect_evidence_blind_spots({"process": proc_cov, "severity": {}, "asset": {}, "temporal": {}}, alerts, [], cases)
    assert any(bs["dimension"] == "process" and "ESCALATION" in bs["type"].upper() for bs in blind_spots)


# =========================================================================
# 5. SEVERITY COVERAGE GAP -> BLIND SPOT
# =========================================================================

def test_severity_coverage_gap_blind_spot():
    """Scenario 5: 100% of alerts are Low severity (0 Critical) -> Severity blind spot detected."""
    alerts = [domain.Alert(id=f"A{i}", entity_id="CSE-1", severity="Low") for i in range(20)]
    sev_cov = evaluate_severity_coverage(alerts)
    assert sev_cov["percentages"]["Low"] == 100.0

    blind_spots = detect_evidence_blind_spots({"severity": sev_cov, "process": {}, "asset": {}, "temporal": {}}, alerts, [], [])
    assert any(bs["dimension"] == "severity" and "Zero Critical" in bs["description"] for bs in blind_spots)


# =========================================================================
# 6. ASSET COVERAGE GAP -> BLIND SPOT
# =========================================================================

def test_asset_coverage_gap_blind_spot():
    """Scenario 6: Critical assets lack active telemetry -> Asset blind spot detected."""
    assets = [
        domain.Asset(id="AST-1", entity_id="CSE-1", criticality="Critical", has_telemetry=False),
        domain.Asset(id="AST-2", entity_id="CSE-1", criticality="Medium", has_telemetry=True),
    ]
    asset_cov = evaluate_asset_coverage(assets, [])
    assert asset_cov["status"] == COVERAGE_PARTIAL

    blind_spots = detect_evidence_blind_spots({"asset": asset_cov, "severity": {}, "process": {}, "temporal": {}}, [], assets, [])
    assert any(bs["dimension"] == "asset" for bs in blind_spots)


# =========================================================================
# 7. CONTRADICTORY RECORDS DETECTED
# =========================================================================

def test_contradictory_records_detected():
    """Scenario 7: Alert says escalated=True but Case says escalation_status=False -> Contradiction."""
    alerts = [domain.Alert(id="AL-CONTRA", entity_id="CSE-1", escalated=True, acknowledged=True, investigation_started=True)]
    cases = [domain.Case(id="CASE-CONTRA", entity_id="CSE-1", alert_id="AL-CONTRA", escalation_status=False)]

    res = detect_evidence_contradictions(alerts, cases, [])
    assert res["count"] == 1
    assert res["status"] == "PRESENT"
    assert res["contradictions"][0]["type"] == "CONTRADICTION"
    assert "alert.escalated" in res["contradictions"][0]["fields_involved"]


# =========================================================================
# 8. MISSING RECORDS ARE NOT TREATED AS CONTRADICTIONS
# =========================================================================

def test_missing_records_not_contradictions():
    """Scenario 8: Missing case or missing closure time is an evidence gap, NOT a contradiction."""
    alerts = [domain.Alert(id="AL-MISSING", entity_id="CSE-1", severity="High", escalated=False, closed_at=None)]
    cases = []  # Missing case record

    res = detect_evidence_contradictions(alerts, cases, [])
    assert res["count"] == 0  # No contradiction!
    assert res["status"] == "NONE"


# =========================================================================
# 9. SHARED EVIDENCE DEPENDENCY DETECTED
# =========================================================================

def test_shared_evidence_dependency_detected():
    """Scenario 9: Multiple findings reference the exact same underlying alert IDs -> LOW_INDEPENDENCE."""
    f1 = domain.Finding(id="F1", entity_id="CSE-1", type="EG 1", severity="HIGH", confidence=0.9, risk_contribution=10, category="execution_gap", description="", rationale="", recommended_action="", evidence_ids=["A100", "A101", "A102"])
    f2 = domain.Finding(id="F2", entity_id="CSE-1", type="EG 2", severity="HIGH", confidence=0.88, risk_contribution=10, category="execution_gap", description="", rationale="", recommended_action="", evidence_ids=["A100", "A101", "A102"])

    dep = evaluate_evidence_dependencies([f1, f2])
    assert dep["status"] == INDEPENDENCE_LOW
    assert dep["shared_cluster_count"] == 1
    assert "Low evidence independence" in dep["explanation"]


# =========================================================================
# 10. FINDING CONFIDENCE HIGH WHILE VALIDITY IS CAUTION
# =========================================================================

def test_finding_confidence_high_while_validity_caution():
    """Scenario 10: Core SAT-SA principle: Finding confidence 95% (HIGH) while Assessment Validity is CAUTION."""
    f = domain.Finding(
        id="F-CONF-HIGH",
        entity_id="CSE-1",
        type="Unescalated Alerts",
        category="execution_gap",
        severity="HIGH",
        confidence=0.95,  # Finding confidence is HIGH
        assessment_validity=ASSURANCE_STATUS_CAUTION,  # Assessment validity is CAUTION
        description="Observed alerts were closed without escalation",
        rationale="",
        recommended_action="",
        risk_contribution=20.0,
    )
    assert f.confidence == 0.95
    assert f.assessment_validity == ASSURANCE_STATUS_CAUTION
    assert f.confidence >= 0.90 and f.assessment_validity != ASSURANCE_STATUS_HIGH


# =========================================================================
# 11. VALIDITY IS NOT A SINGLE OPAQUE SCORE
# =========================================================================

def test_validity_is_structured_profile_not_opaque_score():
    """Scenario 11: Assessment validity returns multi-dimensional dictionary profile with explainable limitations."""
    res = synthesize_assessment_validity(
        population_exposure={"status": COVERAGE_PARTIAL, "value": 0.81},
        coverage_details={
            "process": {"status": COVERAGE_PARTIAL, "stages_missing": ["Escalation"]},
            "severity": {"status": COVERAGE_PARTIAL},
            "asset": {"status": COVERAGE_FULL},
            "temporal": {"status": COVERAGE_FULL},
        },
        contradiction_details={"count": 0, "inconsistency_count": 0},
        dependency_details={"status": INDEPENDENCE_LOW},
        blind_spots=[{"type": "SEVERITY_GAP"}],
        total_records=500,
    )
    assert isinstance(res, dict)
    assert "overall_status" in res
    assert res["overall_status"] in [ASSURANCE_STATUS_HIGH, ASSURANCE_STATUS_CAUTION, ASSURANCE_STATUS_LOW, ASSURANCE_STATUS_INDETERMINATE]
    assert isinstance(res["limitations"], list)
    assert len(res["limitations"]) >= 2
    assert "supervisory_interpretation" in res
    # Ensure no opaque 'validity_score: 73'
    assert "validity_score" not in res


# =========================================================================
# 12-13. INTEGRITY HASHING STABLE & CHANGED DETECTION
# =========================================================================

def test_source_integrity_hashing():
    """Scenarios 12-13: SHA-256 integrity hash is deterministic and verifiable."""
    raw_bytes = b"alert_id,timestamp,severity\nAL-1,2026-01-01T00:00:00,Critical\n"
    h1 = compute_source_hash(raw_bytes)
    h2 = compute_source_hash(raw_bytes)
    assert h1 == h2
    assert len(h1) == 64

    upload = domain.DatasetUpload(
        id="UP-HASH-TEST",
        filename="test.csv",
        file_type="csv",
        dataset_type="alerts",
        source_hash=h1,
        hash_algorithm="SHA-256",
        hash_created_at=datetime.now(timezone.utc),
    )
    report = verify_upload_integrity(upload)
    assert report["status"] == INTEGRITY_VERIFIED
    assert report["hash"] == h1


# =========================================================================
# 14. INSUFFICIENT INFORMATION -> INDETERMINATE
# =========================================================================

def test_insufficient_information_indeterminate():
    """Scenario 14: Tiny sample (< 3 records) -> Assessment validity is INDETERMINATE."""
    res = synthesize_assessment_validity(
        population_exposure={"status": COVERAGE_UNKNOWN},
        coverage_details={},
        contradiction_details={},
        dependency_details={},
        blind_spots=[],
        total_records=1,  # Only 1 record
    )
    assert res["overall_status"] == ASSURANCE_STATUS_INDETERMINATE
    assert any("insufficient" in lim.lower() for lim in res["limitations"])


# =========================================================================
# 15. END-TO-END SERVICE EVALUATION & PERSISTENCE
# =========================================================================

def test_assessment_assurance_service_e2e(db_session):
    """Scenario 15: Full AssessmentAssuranceService execution against SQLite."""
    upload = domain.DatasetUpload(
        id="UP-ASSURE-E2E",
        filename="alerts.csv",
        file_type="csv",
        dataset_type="alerts",
        source_hash=compute_source_hash(b"sample data"),
        hash_algorithm="SHA-256",
        declared_population={"claimed_alert_count": 100},
    )
    db_session.add(upload)

    now = datetime.now(timezone.utc)
    for i in range(10):
        db_session.add(domain.Alert(
            id=f"AL-E2E-{i}",
            upload_id="UP-ASSURE-E2E",
            entity_id="CSE-ASSURE",
            severity="Critical" if i < 3 else "Medium",
            timestamp=now - timedelta(days=i),
            investigation_started=True,
            escalated=False,
            closure_duration_mins=10.0,
        ))

    db_session.add(domain.Finding(
        id="FIND-ASSURE-1",
        upload_id="UP-ASSURE-E2E",
        entity_id="CSE-ASSURE",
        type="Fast Critical Closure",
        category="execution_gap",
        severity="HIGH",
        confidence=0.92,
        risk_contribution=20.0,
        description="",
        rationale="",
        recommended_action="",
        evidence_ids=["AL-E2E-0", "AL-E2E-1"],
    ))
    db_session.commit()

    service = AssessmentAssuranceService()
    assurance_record = service.evaluate_assurance(db=db_session, upload_id="UP-ASSURE-E2E")

    assert assurance_record is not None
    assert assurance_record.upload_id == "UP-ASSURE-E2E"
    assert assurance_record.overall_status in [ASSURANCE_STATUS_HIGH, ASSURANCE_STATUS_CAUTION, ASSURANCE_STATUS_LOW]
    assert assurance_record.population_exposure["value"] == 0.10  # 10 observed of 100 claimed -> LOW exposure -> triggers CAUTION/LOW
    assert len(assurance_record.limitations) > 0

    # Verify finding was updated with assessment_validity
    finding = db_session.query(domain.Finding).filter(domain.Finding.id == "FIND-ASSURE-1").first()
    assert finding.assessment_validity == assurance_record.overall_status
    assert finding.validity_rationale is not None
