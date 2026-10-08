import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import domain
from app.services.normalization import (
    normalize_column_name,
    normalize_severity,
    normalize_boolean,
    normalize_timestamp,
    normalize_null,
    normalize_float,
    normalize_int,
)
from app.services.adapters import detect_dataset_type, map_columns_to_canonical
from app.services.validation import (
    validate_and_normalize_alert_record,
    validate_and_normalize_asset_record,
    validate_and_normalize_case_record,
)
from app.services.ingestion import (
    parse_raw_file,
    process_uploaded_file,
    get_upload_preview_data,
)


@pytest.fixture
def db_session():
    """Create in-memory SQLite session for isolated unit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_normalization_column_names():
    assert normalize_column_name("Alert ID") == "alert_id"
    assert normalize_column_name("alertId") == "alert_id"
    assert normalize_column_name("  Timestamp (UTC)  ") == "timestamp"
    assert normalize_column_name("Entity-Name") == "entity_name"
    assert normalize_column_name("Flow Duration [sec]") == "flow_duration"


def test_normalization_severity():
    assert normalize_severity("CRITICAL") == ("Critical", True)
    assert normalize_severity("crit") == ("Critical", True)
    assert normalize_severity("Sev 1") == ("Critical", True)
    assert normalize_severity("HIGH") == ("High", True)
    assert normalize_severity("medium") == ("Medium", True)
    assert normalize_severity("low") == ("Low", True)
    assert normalize_severity("informational") == ("Low", True)
    assert normalize_severity("unknown_custom_sev") == ("Unknown_Custom_Sev", False)
    assert normalize_severity(None) == ("Unknown", False)


def test_normalization_boolean():
    assert normalize_boolean("true") == (True, True)
    assert normalize_boolean("YES") == (True, True)
    assert normalize_boolean(1) == (True, True)
    assert normalize_boolean("escalate") == (True, True)
    assert normalize_boolean("false") == (False, True)
    assert normalize_boolean("NO") == (False, True)
    assert normalize_boolean(0) == (False, True)
    assert normalize_boolean("invalid_val", default=False) == (False, False)


def test_normalization_timestamp():
    # ISO UTC
    dt, warn, valid = normalize_timestamp("2026-09-01T14:30:00Z")
    assert valid is True
    assert dt == datetime(2026, 9, 1, 14, 30, 0)
    assert warn is None

    # Timezone aware (+05:30)
    dt, warn, valid = normalize_timestamp("2026-09-01T20:00:00+05:30")
    assert valid is True
    assert dt == datetime(2026, 9, 1, 14, 30, 0)
    assert warn is None

    # Timezone naive (assumes UTC with warning)
    dt, warn, valid = normalize_timestamp("2026-09-01 14:30:00")
    assert valid is True
    assert dt == datetime(2026, 9, 1, 14, 30, 0)
    assert warn == "timezone_assumed_utc"

    # Unix timestamp
    dt, warn, valid = normalize_timestamp(1788273000)
    assert valid is True

    # Invalid timestamp
    dt, warn, valid = normalize_timestamp("not-a-date")
    assert valid is False
    assert dt is None


def test_dataset_type_detection():
    assert detect_dataset_type(["alert_id", "timestamp", "severity", "category"]) == "alerts"
    assert detect_dataset_type(["alert_id", "timestamp", "src_ip", "dst_ip", "flow_duration"]) == "alerts"
    assert detect_dataset_type(["asset_id", "hostname", "criticality", "asset_type"]) == "assets"
    assert detect_dataset_type(["case_id", "created_at", "investigator", "closure_reason"]) == "cases"


def test_ingest_valid_csv_alerts(db_session):
    csv_content = b"""alert_id,timestamp,severity,category,asset_id,acknowledged,escalated
AL-101,2026-09-01 10:00:00,Critical,Exfiltration,SRV-01,true,false
AL-102,2026-09-01 10:15:00,High,Malware,SRV-02,yes,yes
AL-103,2026-09-01 10:30:00,Low,PortScan,SRV-03,0,0
"""
    upload = process_uploaded_file(csv_content, "alerts_test.csv", db_session)
    assert upload.status in ("validated", "validated_with_warnings")
    assert upload.records_received == 3
    assert upload.records_valid == 3
    assert upload.records_rejected == 0
    assert upload.dataset_type == "alerts"

    # Check database persistence
    alerts = db_session.query(domain.Alert).filter(domain.Alert.upload_id == upload.id).all()
    assert len(alerts) == 3
    assert alerts[0].id == "AL-101"
    assert alerts[0].severity == "Critical"
    assert alerts[0].acknowledged is True
    assert alerts[0].escalated is False


def test_ingest_valid_assets_csv(db_session):
    csv_content = b"""asset_id,hostname,asset_type,criticality,has_telemetry,entity_id
AST-901,srv-dc-01,Domain Controller,Critical,true,CSE-001
AST-902,srv-db-02,Database,High,1,CSE-001
AST-903,ws-003,Workstation,Low,0,CSE-002
"""
    upload = process_uploaded_file(csv_content, "assets.csv", db_session)
    assert upload.records_received == 3
    assert upload.records_valid == 3
    assert upload.dataset_type == "assets"

    assets = db_session.query(domain.Asset).filter(domain.Asset.upload_id == upload.id).all()
    assert len(assets) == 3
    assert assets[0].id == "AST-901"
    assert assets[0].criticality == "Critical"


def test_ingest_valid_cases_csv(db_session):
    csv_content = b"""case_id,created_at,investigator,investigation_duration,escalation_status,closure_reason
CASE-501,2026-09-01 11:00:00,analyst_alice,45.5,true,Escalated to Tier 2
CASE-502,2026-09-01 11:30:00,analyst_bob,12.0,false,False Positive
"""
    upload = process_uploaded_file(csv_content, "cases.csv", db_session)
    assert upload.records_received == 2
    assert upload.records_valid == 2
    assert upload.dataset_type == "cases"

    cases = db_session.query(domain.Case).filter(domain.Case.upload_id == upload.id).all()
    assert len(cases) == 2
    assert cases[0].id == "CASE-501"
    assert cases[0].escalation_status is True


def test_ingest_valid_json_alerts(db_session):
    json_content = b"""[
        {"alert_id": "JAL-1", "timestamp": "2026-09-01T12:00:00Z", "severity": "CRITICAL", "category": "Ransomware"},
        {"alert_id": "JAL-2", "timestamp": "2026-09-01T12:05:00Z", "severity": "HIGH", "category": "Phishing"}
    ]"""
    upload = process_uploaded_file(json_content, "alerts.json", db_session)
    assert upload.records_received == 2
    assert upload.records_valid == 2
    assert upload.records_rejected == 0


def test_ingest_missing_required_timestamp(db_session):
    csv_content = b"""alert_id,severity,category
AL-201,High,Exfiltration
"""
    upload = process_uploaded_file(csv_content, "missing_ts.csv", db_session)
    assert upload.records_received == 1
    assert upload.records_valid == 0
    assert upload.records_rejected == 1
    assert upload.quality_report["missing_timestamps"] == 1


def test_ingest_invalid_timestamp(db_session):
    csv_content = b"""alert_id,timestamp,severity
AL-301,invalid-date-string,High
"""
    upload = process_uploaded_file(csv_content, "invalid_ts.csv", db_session)
    assert upload.records_rejected == 1
    assert upload.quality_report["invalid_timestamps"] == 1


def test_duplicate_detection(db_session):
    csv_content = b"""alert_id,timestamp,severity
AL-401,2026-09-01 10:00:00,High
AL-401,2026-09-01 10:05:00,Critical
AL-402,2026-09-01 10:10:00,Low
"""
    upload = process_uploaded_file(csv_content, "dups.csv", db_session, duplicate_policy="keep_first")
    assert upload.records_received == 3
    assert upload.records_valid == 2
    assert upload.records_rejected == 1
    assert upload.quality_report["duplicate_ids"] == 1


def test_mixed_severity_and_booleans(db_session):
    csv_content = b"""alert_id,timestamp,severity,acknowledged,escalated
MIX-1,2026-09-01 10:00:00,crit,yes,no
MIX-2,2026-09-01 10:05:00,Sev 2,1,0
MIX-3,2026-09-01 10:10:00,informational,true,false
MIX-4,2026-09-01 10:15:00,CustomSeverity99,T,F
"""
    upload = process_uploaded_file(csv_content, "mixed.csv", db_session)
    assert upload.records_valid == 4
    alerts = db_session.query(domain.Alert).filter(domain.Alert.upload_id == upload.id).all()
    assert alerts[0].severity == "Critical"
    assert alerts[1].severity == "High"
    assert alerts[2].severity == "Low"
    assert alerts[3].severity == "Customseverity99"
    assert upload.quality_report["unknown_severity"] == 1


def test_malformed_ragged_csv(db_session):
    csv_content = b"""alert_id,timestamp,severity
RAG-1,2026-09-01 10:00:00,High,extra_ignored_value
RAG-2,2026-09-01 10:05:00
RAG-3,2026-09-01 10:10:00,Medium
"""
    upload = process_uploaded_file(csv_content, "ragged.csv", db_session)
    assert upload.records_valid >= 2


def test_unknown_columns_preserved_in_raw_data(db_session):
    csv_content = b"""alert_id,timestamp,severity,custom_geo_location,firewall_rule_id
AL-501,2026-09-01 10:00:00,Medium,Asia-South,FW-9988
"""
    upload = process_uploaded_file(csv_content, "custom_cols.csv", db_session)
    assert upload.records_valid == 1
    alert = db_session.query(domain.Alert).filter(domain.Alert.id == "AL-501").first()
    assert alert is not None
    assert alert.raw_data is not None
    assert alert.raw_data.get("custom_geo_location") == "Asia-South"
    assert alert.raw_data.get("firewall_rule_id") == "FW-9988"


def test_empty_file_rejected(db_session):
    upload = process_uploaded_file(b"", "empty.csv", db_session)
    assert upload.status == "rejected"
    assert upload.records_received == 0


def test_preview_data_retrieval(db_session):
    csv_content = b"""alert_id,timestamp,severity,category,entity_id
PREV-01,2026-09-01 10:00:00,Critical,Intrusion,CSE-002
PREV-02,2026-09-01 10:05:00,Low,Scan,CSE-002
"""
    upload = process_uploaded_file(csv_content, "preview_test.csv", db_session)
    preview = get_upload_preview_data(upload.id, db_session)
    assert preview is not None
    assert preview["upload_id"] == upload.id
    assert preview["total_preview_records"] == 2
    assert preview["data"][0]["id"] == "PREV-01"
    assert preview["data"][0]["entity_id"] == "CSE-002"
    assert "CSE-002" in preview["entities"]
