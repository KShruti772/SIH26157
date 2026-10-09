"""
Unit and integration test suite for Module 8 — Reporting & Supervisory Dashboard.
Validates deterministic report compilation, capability evaluation, assurance integration,
evidence limitations, human adjudication separation, JSON/PDF exports, and traceability.
"""

import pytest
import datetime
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import domain
from app.services import reporting, workspace
from app.analytics.engine import SupervisoryAnalyticsEngine
from app.assurance.service import AssessmentAssuranceService

from sqlalchemy.pool import StaticPool

# Setup isolated SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

from app.services.auth import get_current_user

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    def override_get_current_user():
        return domain.User(
            id="USR-TEST-SUP",
            full_name="Lead Supervisory Examiner",
            email="supervisor@ntro.gov",
            role="SUPERVISOR",
            organization="NTRO Supervisory Division",
            is_active=True,
        )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def populated_db(db_session):
    """Populate database with real entity, upload, alerts, findings, assurance, and human decisions."""
    # 1. Entity
    entity = domain.Entity(
        id="CSE-001",
        name="State Power Grid Operations",
        sector="Energy & Power",
        assessment_period="2026-Q3",
    )
    db_session.add(entity)

    # 2. Upload
    upload = domain.DatasetUpload(
        id="UPL-9812",
        filename="soc_alerts_q3.csv",
        file_type="csv",
        dataset_type="alerts",
        records_received=100,
        records_valid=95,
        source_hash="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        entity_ids=["CSE-001"],
    )
    db_session.add(upload)

    # 3. Assets
    asset1 = domain.Asset(id="ast-001", entity_id="CSE-001", type="SCADA_GATEWAY", criticality="CRITICAL", has_telemetry=True)
    asset2 = domain.Asset(id="ast-002", entity_id="CSE-001", type="PLC_CONTROLLER", criticality="HIGH", has_telemetry=False)
    db_session.add_all([asset1, asset2])

    # 4. Alerts
    now = datetime.datetime.utcnow()
    alert1 = domain.Alert(
        id="alt-001",
        entity_id="CSE-001",
        timestamp=now - datetime.timedelta(hours=2),
        severity="CRITICAL",
        category="Initial Access",
        asset_id="ast-001",
        acknowledged=True,
        investigation_started=False,
        escalated=False,
    )
    alert2 = domain.Alert(
        id="alt-002",
        entity_id="CSE-001",
        timestamp=now - datetime.timedelta(hours=1),
        severity="HIGH",
        category="Privilege Escalation",
        asset_id="ast-001",
        acknowledged=True,
        investigation_started=False,
        escalated=False,
    )
    db_session.add_all([alert1, alert2])

    # 5. Finding
    finding = domain.Finding(
        id="NS-CSE-001-ALERTS-NOCASE",
        entity_id="CSE-001",
        type="Absence of Formal Case Records for Priority Alerts",
        category="negative_space",
        severity="HIGH",
        confidence=0.89,
        description="Evidence gap detected: no formal case record was observed for 2 priority alerts.",
        rationale="Operational compliance requires priority detections to possess linked investigation case files.",
        evidence_ids=["alt-001", "alt-002"],
        risk_contribution=25.0,
        recommended_action="Validate whether ticketing system exports were included.",
        status="Requires Review",
        upload_id="UPL-9812",
        analytic_rule="NS_ALERTS_WITHOUT_CASE_V1",
        assessment_validity="LOW",
        validity_rationale="Significant evidence gaps: missing case management records.",
        decision_status="EVIDENCE_REQUESTED",
    )
    db_session.add(finding)

    # 6. Review Item
    review_item = domain.ReviewItem(
        id=1,
        finding_id="NS-CSE-001-ALERTS-NOCASE",
        priority_score=85.0,
        reviewer=None,
        status="Pending",
    )
    db_session.add(review_item)

    # 7. Assessment Assurance
    assurance = domain.AssessmentAssurance(
        id="ASS-CSE-001-01",
        analysis_id="UPL-9812",
        upload_id="UPL-9812",
        entity_id="CSE-001",
        overall_status="LOW",
        finding_confidence="HIGH",
        supervisory_interpretation="Process coverage is LOW due to absent case records.",
        population_exposure={"status": "PARTIAL", "coverage_pct": 50.0},
        coverage_details={
            "temporal": {"status": "HIGH", "observation": "Full window observed."},
            "severity": {"status": "HIGH", "observation": "All severities present."},
            "asset": {"status": "CAUTION", "observation": "Unmonitored assets detected."},
            "process": {
                "status": "LOW",
                "observation": "Detection logs present; investigation/escalation logs missing.",
                "implication": "Broader conclusions cannot be substantiated.",
            },
        },
        dependency_details={"dependency_level": "HIGH"},
        contradiction_details={"items": []},
        blind_spots=["Missing case management records", "No escalation logs"],
        limitations=["Missing case records"],
        integrity_status="VERIFIED",
    )
    db_session.add(assurance)

    # 8. Evidence Request
    req = domain.EvidenceRequest(
        id="REQ-TEST-01",
        finding_id="NS-CSE-001-ALERTS-NOCASE",
        analysis_id="UPL-9812",
        entity_id="CSE-001",
        requested_by="Examiner-402",
        requested_at=now,
        request_type="CASE_MANAGEMENT_RECORDS",
        description="Formal export of ITSM case records.",
        reason="Verify whether downstream investigation occurred outside SIEM.",
        priority="HIGH",
        status="OPEN",
    )
    db_session.add(req)

    # 9. Finding Decision record
    dec = domain.FindingDecision(
        id=1,
        finding_id="NS-CSE-001-ALERTS-NOCASE",
        decision="EVIDENCE_REQUESTED",
        actor="Examiner-402",
        timestamp=now,
        notes="Evidence request REQ-TEST-01 issued.",
        rationale="Need ITSM ticketing logs.",
        evidence_refs=["alt-001", "alt-002"],
    )
    db_session.add(dec)

    db_session.commit()
    return entity


# =========================================================================
# UNIT & INTEGRATION TESTS
# =========================================================================

def test_dashboard_summary_api(client, populated_db, db_session):
    """1. Test GET /api/dashboard/summary returns consolidated metrics."""
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["entities_count"] >= 1
    assert data["findings_count"] >= 1
    assert "capabilities_overview" in data
    assert len(data["capabilities_overview"]) == 8
    assert "supervisory_attention" in data
    assert len(data["supervisory_attention"]) >= 1
    assert data["supervisory_attention"][0]["finding_id"] == "NS-CSE-001-ALERTS-NOCASE"


def test_entity_assessment_api(client, populated_db):
    """2. Test GET /api/entities/{id}/assessment returns detailed entity supervisory assessment."""
    res = client.get("/api/entities/CSE-001/assessment")
    assert res.status_code == 200
    data = res.json()
    assert data["entity"]["id"] == "CSE-001"
    assert len(data["capabilities"]) == 8
    assert data["human_adjudication"]["evidence_requested"] == 1
    assert len(data["evidence_requests"]) == 1


def test_capability_assessment_all_eight_dimensions(populated_db, db_session):
    """3. Test capability assessment covers all 8 PS operational dimensions with evidence states."""
    findings = db_session.query(domain.Finding).all()
    assurance = db_session.query(domain.AssessmentAssurance).first()
    alerts = db_session.query(domain.Alert).all()
    cases = db_session.query(domain.Case).all()
    assets = db_session.query(domain.Asset).all()

    caps = reporting.evaluate_capabilities(findings, assurance, alerts, cases, assets)
    assert len(caps) == 8
    cap_names = [c["name"] for c in caps]
    expected_names = [
        "Threat Detection", "Investigation", "Escalation", "Incident Response",
        "Security Operations", "Governance & Oversight", "Operational Discipline", "Cyber Resilience"
    ]
    assert cap_names == expected_names
    
    # Investigation should reflect concern due to missing case finding
    inv_cap = next(c for c in caps if c["name"] == "Investigation")
    assert inv_cap["status"] in ("OBSERVED CONCERN", "INSUFFICIENT EVIDENCE")
    assert "NS-CSE-001-ALERTS-NOCASE" in inv_cap["finding_ids"]


def test_findings_summary_and_categories(populated_db, db_session):
    """4. Test finding summary grouping and category counts."""
    findings = db_session.query(domain.Finding).all()
    adj = reporting.summarize_human_adjudication(findings)
    assert adj["total_findings"] == 1
    assert adj["evidence_requested"] == 1
    assert adj["confirmed"] == 0


def test_assurance_summary_dimensions(populated_db, db_session):
    """5. Test assessment assurance matrix and dimension reporting."""
    assurance = db_session.query(domain.AssessmentAssurance).first()
    assert assurance.assessment_validity == "LOW"
    assert assurance.process_coverage == "LOW"
    assert len(assurance.blind_spots) == 2


def test_evidence_limitations_segregation(populated_db, db_session):
    """6. Test evidence limitations are properly segregated into missing, partial, unknown, contradictory."""
    assurance = db_session.query(domain.AssessmentAssurance).first()
    findings = db_session.query(domain.Finding).all()
    lims = reporting.summarize_evidence_limitations(assurance, findings, has_alerts=True, has_cases=False, has_assets=True)
    
    assert "missing" in lims
    assert "partial" in lims
    assert "unknown" in lims
    assert "contradictory" in lims
    assert any("Case Management" in m["item"] for m in lims["missing"])


def test_human_adjudication_summary(populated_db, db_session):
    """7. Test human adjudication distinct counts."""
    findings = db_session.query(domain.Finding).all()
    adj = reporting.summarize_human_adjudication(findings)
    assert adj["total_findings"] == 1
    assert adj["evidence_requested"] == 1


def test_evidence_request_summary(populated_db, db_session):
    """8. Test evidence request listing and status tracking."""
    reqs = db_session.query(domain.EvidenceRequest).all()
    assert len(reqs) == 1
    assert reqs[0].request_type == "CASE_MANAGEMENT_RECORDS"
    assert reqs[0].status == "OPEN"


def test_report_json_generation_structure(client, populated_db, db_session):
    """9. Test report JSON generation includes all structured sections."""
    res = client.get("/api/reports/CSE-001")
    assert res.status_code == 200
    report = res.json()
    assert "report_metadata" in report
    assert "entity_summary" in report
    assert "assessment_summary" in report
    assert "capability_assessment" in report
    assert "findings" in report
    assert "assurance" in report
    assert "evidence_limitations" in report
    assert "human_adjudication" in report
    assert "evidence_requests" in report
    assert "traceability" in report


def test_report_contains_real_finding_and_evidence_ids(client, populated_db):
    """10 & 11. Test report contains real persisted finding IDs and evidence references."""
    res = client.get("/api/reports/CSE-001")
    report = res.json()
    f_list = report["findings"]
    assert len(f_list) == 1
    f = f_list[0]
    assert f["finding_id"] == "NS-CSE-001-ALERTS-NOCASE"
    assert "alt-001" in f["evidence_references"]
    assert "alt-002" in f["evidence_references"]


def test_report_contains_human_decisions_and_distinguishes_ai(client, populated_db):
    """12 & 13. Test report preserves human decision and distinguishes AI advisory inputs."""
    res = client.get("/api/reports/CSE-001")
    report = res.json()
    f = report["findings"][0]
    assert f["human_decision"]["status"] == "EVIDENCE_REQUESTED"
    assert f["human_decision"]["actor"] == "Examiner-402"
    assert "advisory_notice" in report["assessment_summary"]


def test_report_does_not_fabricate_findings_for_clean_entity(client, db_session):
    """14. Test clean entity with no findings produces empty findings list without fabricated items."""
    clean_ent = domain.Entity(id="CSE-CLEAN", name="Clean Entity", sector="Finance", assessment_period="2026-Q3")
    db_session.add(clean_ent)
    db_session.commit()

    res = client.get("/api/reports/CSE-CLEAN")
    assert res.status_code == 200
    report = res.json()
    assert len(report["findings"]) == 0
    assert report["entity_summary"]["total_findings"] == 0


def test_report_handles_missing_assessment_period(client, db_session):
    """15. Test missing assessment period gracefully displays 'Not provided'."""
    ent = domain.Entity(id="CSE-NO-PERIOD", name="No Period Entity", sector="Healthcare", assessment_period=None)
    db_session.add(ent)
    db_session.commit()

    res = client.get("/api/reports/CSE-NO-PERIOD")
    report = res.json()
    assert report["entity_summary"]["assessment_period"] == "Not provided"


def test_report_handles_low_assessment_validity(client, populated_db):
    """16 & 17. Test report preserves LOW assessment validity and explains evidence gaps."""
    res = client.get("/api/reports/CSE-001")
    report = res.json()
    assert report["assurance"]["assessment_validity"] == "LOW"
    assert "process" in report["assurance"]["dimension_details"] or "process_coverage" in report["assurance"]["dimension_details"]
    assert report["assurance"]["process_coverage"] == "LOW"


def test_pdf_generation_succeeds_and_returns_valid_bytes(client, populated_db, db_session):
    """18 & 19. Test PDF download returns valid binary PDF with application/pdf header."""
    res = client.get("/api/reports/CSE-001/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000
    # PDF magic bytes
    assert res.content.startswith(b"%PDF")


def test_report_api_json_export_download(client, populated_db):
    """20. Test JSON report download endpoint returns valid JSON with attachment header."""
    res = client.get("/api/reports/CSE-001/json")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json"
    data = res.json()
    assert data["report_metadata"]["entity_id"] == "CSE-001"


def test_reports_list_endpoint(client, populated_db):
    """21. Test GET /api/reports returns available report summaries."""
    res = client.get("/api/reports")
    assert res.status_code == 200
    reports = res.json()
    assert len(reports) >= 1
    assert any(r["entity_id"] == "CSE-001" for r in reports)


# =========================================================================
# CAPABILITY STATUS DERIVATION TEST MATRIX (SCENARIOS A – G)
# =========================================================================

def test_scenario_a_relevant_finding_with_sufficient_evidence_produces_observed_concern():
    """Scenario A: Relevant finding + sufficient evidence -> OBSERVED CONCERN."""
    now = datetime.datetime.utcnow()
    alerts = [
        domain.Alert(id="alt-1", entity_id="E1", timestamp=now, severity="CRITICAL", acknowledged=True, investigation_started=True)
    ]
    assets = [domain.Asset(id="ast-1", entity_id="E1", criticality="CRITICAL", has_telemetry=False)]
    cases = []
    findings = [
        domain.Finding(
            id="F-NS-UNMONITORED",
            entity_id="E1",
            analytic_rule="NS_UNMONITORED_ASSETS_V1",
            type="Unmonitored Critical Asset",
            category="negative_space",
            severity="CRITICAL",
            confidence=0.95,
            evidence_ids=["ast-1"],
        )
    ]

    caps = reporting.evaluate_capabilities(findings=findings, assurance=None, alerts=alerts, cases=cases, assets=assets)
    cap_map = {c["name"]: c for c in caps}

    assert cap_map["Threat Detection"]["status"] == "OBSERVED CONCERN"
    assert cap_map["Cyber Resilience"]["status"] == "OBSERVED CONCERN"
    assert "F-NS-UNMONITORED" in cap_map["Cyber Resilience"]["finding_ids"]


def test_scenario_b_no_finding_with_sufficient_evidence_produces_no_observed_concern():
    """Scenario B: No finding + sufficient relevant evidence -> NO OBSERVED CONCERN."""
    now = datetime.datetime.utcnow()
    alerts = [
        domain.Alert(id="alt-1", entity_id="E1", timestamp=now, severity="LOW", acknowledged=True, investigation_started=True, escalated=False, closed_at=now, disposition="TRUE_POSITIVE")
    ]
    assets = [domain.Asset(id="ast-1", entity_id="E1", criticality="HIGH", has_telemetry=True)]
    cases = [
        domain.Case(id="case-1", entity_id="E1", alert_id="alt-1", created_at=now, closure_time=now, escalation_status=False, closure_reason="RESOLVED")
    ]
    findings = [] # No findings flagged

    caps = reporting.evaluate_capabilities(findings=findings, assurance=None, alerts=alerts, cases=cases, assets=assets)
    cap_map = {c["name"]: c for c in caps}

    assert cap_map["Threat Detection"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Investigation"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Escalation"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Incident Response"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Security Operations"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Governance & Oversight"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Operational Discipline"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Cyber Resilience"]["status"] == "NO OBSERVED CONCERN"
    assert "No observed concern in the submitted" in cap_map["Threat Detection"]["observation"]


def test_scenario_c_no_finding_with_insufficient_evidence_produces_insufficient_evidence():
    """Scenario C: No finding + insufficient evidence -> INSUFFICIENT EVIDENCE."""
    alerts = []
    assets = []
    cases = []
    findings = []

    caps = reporting.evaluate_capabilities(findings=findings, assurance=None, alerts=alerts, cases=cases, assets=assets)
    for cap in caps:
        assert cap["status"] == "INSUFFICIENT EVIDENCE"
        assert "Insufficient evidence" in cap["observation"]


def test_scenario_d_capability_not_represented_in_scope_produces_not_assessed():
    """Scenario D: Capability excluded or not in assessment scope -> NOT ASSESSED."""
    now = datetime.datetime.utcnow()
    alerts = [domain.Alert(id="alt-1", entity_id="E1", timestamp=now)]
    assets = [domain.Asset(id="ast-1", entity_id="E1")]
    cases = [domain.Case(id="case-1", entity_id="E1", created_at=now, closure_time=now, escalation_status=True)]
    findings = []

    # Scope only includes Threat Detection and Security Operations
    evaluated_scope = ["Threat Detection", "Security Operations"]
    caps = reporting.evaluate_capabilities(
        findings=findings,
        assurance=None,
        alerts=alerts,
        cases=cases,
        assets=assets,
        assessed_capabilities=evaluated_scope,
    )
    cap_map = {c["name"]: c for c in caps}

    assert cap_map["Threat Detection"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Security Operations"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Escalation"]["status"] == "NOT ASSESSED"
    assert cap_map["Cyber Resilience"]["status"] == "NOT ASSESSED"
    assert cap_map["Incident Response"]["status"] == "NOT ASSESSED"


def test_scenario_e_missing_case_management_data_does_not_falsely_produce_no_observed_concern():
    """Scenario E: Missing case-management data -> downstream capabilities must not become NO OBSERVED CONCERN."""
    now = datetime.datetime.utcnow()
    # Alerts and Assets provided, but 0 Cases submitted
    alerts = [domain.Alert(id="alt-1", entity_id="E1", timestamp=now, severity="MEDIUM")]
    assets = [domain.Asset(id="ast-1", entity_id="E1", has_telemetry=True)]
    cases = [] # Missing case management system records
    findings = [] # No findings directly flagged

    caps = reporting.evaluate_capabilities(findings=findings, assurance=None, alerts=alerts, cases=cases, assets=assets)
    cap_map = {c["name"]: c for c in caps}

    # Threat Detection and Cyber Resilience have sufficient telemetry
    assert cap_map["Threat Detection"]["status"] == "NO OBSERVED CONCERN"
    assert cap_map["Cyber Resilience"]["status"] == "NO OBSERVED CONCERN"

    # Downstream process capabilities MUST NOT be NO OBSERVED CONCERN without case evidence
    assert cap_map["Investigation"]["status"] == "INSUFFICIENT EVIDENCE"
    assert cap_map["Escalation"]["status"] == "INSUFFICIENT EVIDENCE"
    assert cap_map["Governance & Oversight"]["status"] == "INSUFFICIENT EVIDENCE"


def test_scenario_f_missing_escalation_records_produces_insufficient_evidence():
    """Scenario F: Missing escalation records -> Escalation must not automatically become NO OBSERVED CONCERN."""
    now = datetime.datetime.utcnow()
    alerts = [domain.Alert(id="alt-1", entity_id="E1", timestamp=now, severity="HIGH")]
    assets = [domain.Asset(id="ast-1", entity_id="E1", has_telemetry=True)]
    # Case is present but lacks escalation telemetry
    cases = [domain.Case(id="c-1", entity_id="E1", alert_id="alt-1", created_at=now, escalation_status=None, closure_time=now)]
    findings = []

    caps = reporting.evaluate_capabilities(findings=findings, assurance=None, alerts=alerts, cases=cases, assets=assets)
    cap_map = {c["name"]: c for c in caps}

    assert cap_map["Escalation"]["status"] == "INSUFFICIENT EVIDENCE"
    assert "no escalation workflow records" in cap_map["Escalation"]["observation"]


def test_scenario_g_missing_incident_response_evidence_produces_insufficient_evidence():
    """Scenario G: Missing incident-response evidence -> Incident Response must not automatically become NO OBSERVED CONCERN."""
    now = datetime.datetime.utcnow()
    alerts = [domain.Alert(id="alt-1", entity_id="E1", timestamp=now, severity="HIGH")]
    assets = [domain.Asset(id="ast-1", entity_id="E1", has_telemetry=True)]
    # Case is open with no closure timestamps or resolution disposition
    cases = [domain.Case(id="c-1", entity_id="E1", alert_id="alt-1", created_at=now, closure_time=None, closure_reason=None, escalation_status=True)]
    findings = []

    caps = reporting.evaluate_capabilities(findings=findings, assurance=None, alerts=alerts, cases=cases, assets=assets)
    cap_map = {c["name"]: c for c in caps}

    assert cap_map["Incident Response"]["status"] == "INSUFFICIENT EVIDENCE"
    assert "no closure, containment, or resolution records" in cap_map["Incident Response"]["observation"]


def test_classification_wording_is_neutral_prototype(client, populated_db):
    """Test generated report metadata classification uses neutral prototype designation."""
    res = client.get("/api/reports/CSE-001")
    assert res.status_code == 200
    report = res.json()
    assert report["report_metadata"]["classification"] == "SAT-SA — Supervisory Assessment Prototype"
    assert "OFFICIAL-SUPERVISORY (NTRO / NCIIPC)" not in report["report_metadata"]["classification"]

