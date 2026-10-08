import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import domain
from app.services.evidence import (
    resolve_evidence_records,
    calculate_evidence_completeness,
    identify_missing_links,
    get_evidence_trace,
)
from app.analytics.engine import SupervisoryAnalyticsEngine


@pytest.fixture
def db_session():
    """In-memory SQLite test database fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_evidence_id_resolution(db_session):
    """Rule 15: Finding evidence IDs resolve correctly to authentic database records."""
    ast = domain.Asset(id="AST-100", entity_id="CSE-EV", type="Server", criticality="Critical", has_telemetry=True)
    alt = domain.Alert(id="AL-100", entity_id="CSE-EV", asset_id="AST-100", severity="Critical", timestamp=datetime.now(timezone.utc))
    cse = domain.Case(id="CASE-100", entity_id="CSE-EV", alert_id="AL-100", created_at=datetime.now(timezone.utc))

    db_session.add_all([ast, alt, cse])
    db_session.commit()

    resolved = resolve_evidence_records(["AL-100"], db_session)
    assert len(resolved["alerts"]) == 1
    assert resolved["alerts"][0].id == "AL-100"
    # Auto-resolved linked case and asset
    assert len(resolved["cases"]) == 1
    assert resolved["cases"][0].id == "CASE-100"
    assert len(resolved["assets"]) == 1
    assert resolved["assets"][0].id == "AST-100"


def test_missing_evidence_reported(db_session):
    """Rule 16: Missing links and incomplete chains are explicitly identified."""
    alt = domain.Alert(
        id="AL-ORPHAN",
        entity_id="CSE-EV",
        asset_id="AST-UNREGISTERED",
        severity="Critical",
        investigation_started=False,
        escalated=False,
        closed_at=None,
        closure_duration_mins=None,
    )
    db_session.add(alt)

    f = domain.Finding(
        id="FIND-01",
        entity_id="CSE-EV",
        category="execution_gap",
        evidence_ids=["AL-ORPHAN"],
        type="Uninvestigated Alert",
        severity="HIGH",
        confidence=0.9,
        description="",
        rationale="",
        recommended_action="",
    )
    db_session.add(f)
    db_session.commit()

    trace = get_evidence_trace("FIND-01", db_session)
    assert trace["finding_id"] == "FIND-01"
    assert len(trace["missing_links"]) > 0
    # Checks for missing case/investigation, missing asset cataloging, missing escalation
    assert any("absent" in ml or "missing" in ml or "not documented" in ml for ml in trace["missing_links"])
    assert trace["evidence_completeness"] < 1.0


def test_no_fabricated_timeline_events(db_session):
    """Rule 17: Trace does not invent timestamps or events when fields are null."""
    now = datetime.now(timezone.utc)
    alt = domain.Alert(
        id="AL-REAL",
        entity_id="CSE-EV",
        timestamp=now,
        severity="High",
        closed_at=None,
        closure_duration_mins=None,
    )
    db_session.add(alt)

    f = domain.Finding(
        id="FIND-02",
        entity_id="CSE-EV",
        category="execution_gap",
        evidence_ids=["AL-REAL"],
        type="Test Finding",
        severity="MEDIUM",
        confidence=0.85,
        description="",
        rationale="",
        recommended_action="",
    )
    db_session.add(f)
    db_session.commit()

    trace = get_evidence_trace("FIND-02", db_session)
    alert_data = trace["alerts"][0]
    assert alert_data["closed_at"] is None
    assert alert_data["closure_duration_mins"] is None


def test_supervisory_analytics_engine_end_to_end(db_session):
    """Integration: Full engine execution discovers findings, computes benchmarks and risk scores."""
    # Seed 2 entities with operational records
    e1 = domain.Entity(id="CSE-E2E-1", name="Entity 1", sector="Energy", assessment_period="2026-Q3")
    e2 = domain.Entity(id="CSE-E2E-2", name="Entity 2", sector="Energy", assessment_period="2026-Q3")
    db_session.add_all([e1, e2])

    now = datetime.now(timezone.utc)
    # E1: Has fast closure critical alerts (Execution Gap)
    for i in range(5):
        db_session.add(domain.Alert(
            id=f"AL-E1-{i}",
            entity_id="CSE-E2E-1",
            severity="Critical",
            category="Exfiltration",
            timestamp=now - timedelta(minutes=5),
            acknowledged=True,
            investigation_started=True,
            escalated=False,
            closure_duration_mins=5.0,
            closed_at=now,
        ))

    # E2: Normal alerts with proper escalation
    for i in range(5):
        db_session.add(domain.Alert(
            id=f"AL-E2-{i}",
            entity_id="CSE-E2E-2",
            severity="Critical",
            category="Exfiltration",
            timestamp=now - timedelta(minutes=50),
            acknowledged=True,
            investigation_started=True,
            escalated=True,
            closure_duration_mins=50.0,
            closed_at=now,
        ))

    db_session.commit()

    engine = SupervisoryAnalyticsEngine()
    summary = engine.run(db=db_session)

    assert summary["entities_analyzed"] == 2
    assert summary["findings_count"] >= 1
    assert summary["categories"]["execution_gaps"] >= 1

    # Verify findings persisted in SQLite
    findings = db_session.query(domain.Finding).filter(domain.Finding.entity_id == "CSE-E2E-1").all()
    assert len(findings) >= 1
    assert findings[0].category == "execution_gap"

    # Verify risk score persisted
    risk1 = db_session.query(domain.RiskScore).filter(domain.RiskScore.entity_id == "CSE-E2E-1").first()
    assert risk1 is not None
    assert risk1.execution_gap_risk > 0.0

    # Verify review items queued
    review_items = db_session.query(domain.ReviewItem).all()
    assert len(review_items) >= 1
