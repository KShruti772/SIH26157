import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import domain
from app.analytics.config import (
    PROTOTYPE_CRITICAL_CLOSURE_MINUTES,
    PROTOTYPE_HIGH_CLOSURE_MINUTES,
    MIN_ANOMALY_SAMPLE_SIZE,
    MIN_PEER_BENCHMARK_ENTITIES,
)
from app.analytics.execution_gaps import ExecutionGapDetector
from app.analytics.negative_space import NegativeSpaceDetector
from app.analytics.anomalies import AnomalyDetector
from app.analytics.benchmarking import CohortBenchmarker
from app.analytics.risk import RiskScoreCalculator
from app.analytics.engine import SupervisoryAnalyticsEngine


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# =========================================================================
# 1-5. EXECUTION GAP TESTS
# =========================================================================

def test_execution_gap_critical_investigated_and_escalated():
    """Rule 1: Critical alert investigated and escalated -> NO execution gap finding."""
    detector = ExecutionGapDetector()
    now = datetime.now(timezone.utc)
    alerts = [
        domain.Alert(
            id="AL-01",
            entity_id="CSE-TEST",
            severity="Critical",
            category="Malware",
            timestamp=now - timedelta(minutes=45),
            acknowledged=True,
            investigation_started=True,
            escalated=True,  # Escalated!
            closure_duration_mins=45.0,
            closed_at=now,
        )
    ]
    cases = [
        domain.Case(
            id="CASE-01",
            entity_id="CSE-TEST",
            alert_id="AL-01",
            created_at=now - timedelta(minutes=40),
            investigation_duration=40.0,
            escalation_status=True,
        )
    ]
    findings = detector.analyze_entity("CSE-TEST", alerts, cases)
    assert len(findings) == 0


def test_execution_gap_acknowledged_not_investigated():
    """Rule 2: Critical/High alert acknowledged but not investigated -> Execution gap finding."""
    detector = ExecutionGapDetector()
    now = datetime.now(timezone.utc)
    alerts = [
        domain.Alert(
            id="AL-02",
            entity_id="CSE-TEST",
            severity="Critical",
            category="Exfiltration",
            timestamp=now - timedelta(hours=2),
            acknowledged=True,
            investigation_started=False,  # Triage stalled!
            escalated=False,
            closed_at=None,
        )
    ]
    findings = detector.analyze_entity("CSE-TEST", alerts, [])
    assert len(findings) == 1
    assert findings[0].category == "execution_gap"
    assert "AL-02" in findings[0].evidence_ids


def test_execution_gap_critical_investigated_not_escalated():
    """Rule 3: Critical alert investigated (>15m) but closed without escalation -> Finding."""
    detector = ExecutionGapDetector()
    now = datetime.now(timezone.utc)
    alerts = [
        domain.Alert(
            id="AL-03",
            entity_id="CSE-TEST",
            severity="Critical",
            category="Intrusion",
            timestamp=now - timedelta(minutes=60),
            acknowledged=True,
            investigation_started=True,
            escalated=False,  # Missing required escalation
            closure_duration_mins=60.0,
            closed_at=now,
        )
    ]
    findings = detector.analyze_entity("CSE-TEST", alerts, [])
    assert len(findings) == 1
    assert findings[0].category == "execution_gap"
    assert "AL-03" in findings[0].evidence_ids


def test_execution_gap_rapid_closure():
    """Rule 4: Critical alert closed under prototype threshold (<=15 mins) without escalation -> Fast closure finding."""
    detector = ExecutionGapDetector()
    now = datetime.now(timezone.utc)
    alerts = [
        domain.Alert(
            id="AL-04",
            entity_id="CSE-TEST",
            severity="Critical",
            category="Ransomware",
            timestamp=now - timedelta(minutes=5),
            acknowledged=True,
            investigation_started=True,
            escalated=False,
            closure_duration_mins=5.0,  # Below 15 min threshold
            closed_at=now,
        )
    ]
    findings = detector.analyze_entity("CSE-TEST", alerts, [])
    assert len(findings) == 1
    assert "Rapid Critical Alert Closure" in findings[0].type
    assert findings[0].details["threshold_mins"] == PROTOTYPE_CRITICAL_CLOSURE_MINUTES


def test_execution_gap_evidence_traceability():
    """Rule 5: Generated finding preserves exact evidence IDs and rule identifier."""
    detector = ExecutionGapDetector()
    alerts = [
        domain.Alert(
            id=f"AL-CRIT-{i}",
            entity_id="CSE-TRACE",
            severity="Critical",
            category="Exfiltration",
            acknowledged=True,
            investigation_started=True,
            escalated=False,
            closure_duration_mins=6.0,
        )
        for i in range(3)
    ]
    findings = detector.analyze_entity("CSE-TRACE", alerts, [], upload_id="UP-100")
    assert len(findings) == 1
    f = findings[0]
    assert f.upload_id == "UP-100"
    assert f.evidence_ids == ["AL-CRIT-0", "AL-CRIT-1", "AL-CRIT-2"]
    assert f.analytic_rule is not None


# =========================================================================
# 6-9. NEGATIVE SPACE TESTS
# =========================================================================

def test_negative_space_critical_asset_no_telemetry():
    """Rule 6: Critical asset with no telemetry -> Negative space finding with non-accusatory language."""
    detector = NegativeSpaceDetector()
    assets = [
        domain.Asset(id="AST-01", entity_id="CSE-NS", criticality="Critical", has_telemetry=False),
        domain.Asset(id="AST-02", entity_id="CSE-NS", criticality="Medium", has_telemetry=True),
    ]
    findings = detector.analyze_entity("CSE-NS", assets, [], [])
    assert len(findings) == 1
    assert findings[0].category == "negative_space"
    assert "Required evidence was not observed" in findings[0].description
    assert "AST-01" in findings[0].evidence_ids


def test_negative_space_valid_telemetry_no_finding():
    """Rule 7: Assets with active telemetry -> NO negative space finding."""
    detector = NegativeSpaceDetector()
    assets = [
        domain.Asset(id="AST-01", entity_id="CSE-NS", criticality="Critical", has_telemetry=True),
        domain.Asset(id="AST-02", entity_id="CSE-NS", criticality="High", has_telemetry=True),
    ]
    findings = detector.analyze_entity("CSE-NS", assets, [], [])
    assert len(findings) == 0


def test_negative_space_missing_case_records():
    """Rule 8: Priority alerts with no case or investigation record -> Evidence gap finding."""
    detector = NegativeSpaceDetector()
    alerts = [
        domain.Alert(id="AL-PRIO-01", entity_id="CSE-NS", severity="Critical", investigation_started=False),
        domain.Alert(id="AL-PRIO-02", entity_id="CSE-NS", severity="High", investigation_started=False),
    ]
    findings = detector.analyze_entity("CSE-NS", [], alerts, [])
    assert len(findings) == 1
    assert findings[0].category == "negative_space"
    assert "Evidence gap detected" in findings[0].description


# =========================================================================
# 10-12. ANOMALY DETECTION TESTS
# =========================================================================

def test_anomaly_normal_durations_no_outliers():
    """Rule 10: Homogeneous normal investigation durations -> NO anomaly finding."""
    detector = AnomalyDetector(min_sample_size=5)
    alerts = [
        domain.Alert(id=f"AL-N-{i}", entity_id="CSE-ANOM", investigation_duration_mins=40.0 + (i * 2))
        for i in range(10)
    ]
    findings = detector.analyze_entity("CSE-ANOM", alerts, [])
    assert len(findings) == 0


def test_anomaly_extreme_duration_outlier():
    """Rule 11: Sample with extreme fast outlier -> Statistical anomaly finding with baseline explanation."""
    detector = AnomalyDetector(min_sample_size=5)
    # 8 normal alerts (~45m) and 2 outlier alerts (2m)
    alerts = [
        domain.Alert(id=f"AL-NORM-{i}", entity_id="CSE-ANOM", investigation_duration_mins=45.0 + i)
        for i in range(8)
    ]
    alerts.append(domain.Alert(id="AL-OUTLIER-1", entity_id="CSE-ANOM", investigation_duration_mins=2.0))
    alerts.append(domain.Alert(id="AL-OUTLIER-2", entity_id="CSE-ANOM", investigation_duration_mins=2.5))

    findings = detector.analyze_entity("CSE-ANOM", alerts, [])
    assert len(findings) >= 1
    anom = [f for f in findings if f.category == "anomaly"][0]
    assert "Statistical Outlier" in anom.description or "Statistical outlier" in anom.description
    assert anom.details["baseline_median"] > 40.0
    assert "AL-OUTLIER-1" in anom.evidence_ids


def test_anomaly_insufficient_sample_no_false_positives():
    """Rule 12: Insufficient sample size (< 5) -> Does not generate false anomalies."""
    detector = AnomalyDetector(min_sample_size=5)
    alerts = [
        domain.Alert(id="AL-1", entity_id="CSE-TINY", investigation_duration_mins=2.0),
        domain.Alert(id="AL-2", entity_id="CSE-TINY", investigation_duration_mins=50.0),
    ]
    findings = detector.analyze_entity("CSE-TINY", alerts, [])
    assert len(findings) == 0


# =========================================================================
# 13-14. PEER BENCHMARKING TESTS
# =========================================================================

def test_peer_benchmarking_multiple_entities():
    """Rule 13: Multiple entities -> Correct cohort median, average, percentile, and deviation."""
    benchmarker = CohortBenchmarker(min_entities=2)
    entity_records = {
        "CSE-001": {
            "alerts": [domain.Alert(id="A1", entity_id="CSE-001", escalated=True) for _ in range(10)],
            "cases": [],
            "assets": [domain.Asset(id="AST1", entity_id="CSE-001", has_telemetry=True)],
        },
        "CSE-002": {
            "alerts": [domain.Alert(id="A2", entity_id="CSE-002", escalated=True) for _ in range(8)] +
                      [domain.Alert(id="A3", entity_id="CSE-002", escalated=False) for _ in range(2)],
            "cases": [],
            "assets": [domain.Asset(id="AST2", entity_id="CSE-002", has_telemetry=True)],
        },
        "CSE-003": {
            "alerts": [domain.Alert(id="A4", entity_id="CSE-003", escalated=False) for _ in range(10)],  # 0% escalation
            "cases": [],
            "assets": [domain.Asset(id="AST3", entity_id="CSE-003", has_telemetry=True)],
        },
    }

    result = benchmarker.calculate_cohort_benchmarks(entity_records)
    assert not result["insufficient_sample"]
    assert len(result["benchmarks"]) > 0

    # CSE-003 Escalation Rate should be 0%, peer median should be 80.0%
    b_cse3 = [b for b in result["benchmarks"] if b.entity_id == "CSE-003" and b.metric == "Escalation Rate"][0]
    assert b_cse3.entity_value == 0.0
    assert b_cse3.peer_median == 80.0
    assert b_cse3.status_label == "SIGNIFICANT DEVIATION"


def test_peer_benchmarking_single_entity():
    """Rule 14: Single entity cohort -> Reports insufficient peer sample."""
    benchmarker = CohortBenchmarker(min_entities=2)
    entity_records = {
        "CSE-SINGLE": {
            "alerts": [domain.Alert(id="A1", entity_id="CSE-SINGLE", escalated=True)],
            "cases": [],
            "assets": [],
        }
    }
    result = benchmarker.calculate_cohort_benchmarks(entity_records)
    assert result["insufficient_sample"] is True
    assert len(result["benchmarks"]) == 0


# =========================================================================
# 18-19. RISK SCORING TESTS
# =========================================================================

def test_risk_score_calculation_bounds_and_dimensions():
    """Rules 18-19: Findings affect correct risk dimension; overall score remains bounded 0-100."""
    calculator = RiskScoreCalculator()
    findings = [
        domain.Finding(
            id="EG-01",
            entity_id="CSE-RISK",
            category="execution_gap",
            severity="HIGH",
            risk_contribution=20.0,
            confidence=0.9,
            type="Test EG",
            description="",
            rationale="",
            recommended_action="",
        ),
        domain.Finding(
            id="NS-01",
            entity_id="CSE-RISK",
            category="negative_space",
            severity="CRITICAL",
            risk_contribution=30.0,
            confidence=0.95,
            type="Test NS",
            description="",
            rationale="",
            recommended_action="",
        ),
    ]
    assets = [
        domain.Asset(id="AST-1", entity_id="CSE-RISK", has_telemetry=False),
        domain.Asset(id="AST-2", entity_id="CSE-RISK", has_telemetry=True),
    ]
    alerts = [
        domain.Alert(id="AL-1", entity_id="CSE-RISK", severity="Critical", escalated=False, investigation_started=False),
    ]

    risk = calculator.calculate_entity_risk("CSE-RISK", findings, [], assets, alerts)
    assert 0.0 <= risk.overall_score <= 100.0
    assert risk.execution_gap_risk > 0.0
    assert risk.negative_space_risk > 0.0
    assert risk.investigation_risk > 0.0
    assert risk.escalation_risk > 0.0
    assert risk.monitoring_coverage_risk == 50.0  # 1 of 2 assets missing telemetry
