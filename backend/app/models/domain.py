from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True) # UUID
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    organization = Column(String, nullable=False)
    role = Column(String, nullable=False, default="REVIEWER") # SUPERVISOR, REVIEWER, ADMINISTRATOR
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    sector = Column(String)
    assessment_period = Column(String)

class DatasetUpload(Base):
    __tablename__ = "dataset_uploads"
    id = Column(String, primary_key=True, index=True) # UUID
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False) # csv, json
    dataset_type = Column(String, nullable=False) # alerts, assets, cases, generic
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    status = Column(String, default="validated") # validated, validated_with_warnings, rejected, failed
    records_received = Column(Integer, default=0)
    records_valid = Column(Integer, default=0)
    records_rejected = Column(Integer, default=0)
    warnings_count = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    columns_detected = Column(JSON, default=list)
    quality_report = Column(JSON, default=dict)
    error_details = Column(JSON, default=list)
    entity_ids = Column(JSON, default=list)
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)
    source_hash = Column(String, nullable=True)
    hash_algorithm = Column(String, default="SHA-256")
    hash_created_at = Column(DateTime, default=datetime.datetime.utcnow)
    declared_population = Column(JSON, nullable=True)

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, index=True)
    upload_id = Column(String, ForeignKey("dataset_uploads.id"), nullable=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    timestamp = Column(DateTime, index=True)
    severity = Column(String, index=True)
    category = Column(String)
    asset_id = Column(String, nullable=True)
    acknowledged = Column(Boolean, default=False)
    investigation_started = Column(Boolean, default=False)
    escalated = Column(Boolean, default=False)
    closed_at = Column(DateTime, nullable=True)
    disposition = Column(String, nullable=True)
    investigation_duration_mins = Column(Float, nullable=True)
    closure_duration_mins = Column(Float, nullable=True)
    raw_data = Column(JSON, nullable=True)

class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, index=True)
    upload_id = Column(String, ForeignKey("dataset_uploads.id"), nullable=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=True)
    created_at = Column(DateTime)
    investigator = Column(String, nullable=True)
    investigation_duration = Column(Float, nullable=True) # minutes
    escalation_status = Column(Boolean, default=False)
    closure_time = Column(DateTime, nullable=True)
    closure_reason = Column(String, nullable=True)
    evidence_count = Column(Integer, default=0)
    raw_data = Column(JSON, nullable=True)

class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True, index=True)
    upload_id = Column(String, ForeignKey("dataset_uploads.id"), nullable=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    type = Column(String, nullable=True)
    criticality = Column(String, nullable=True)
    has_telemetry = Column(Boolean, default=True)
    raw_data = Column(JSON, nullable=True)

class Finding(Base):
    __tablename__ = "findings"
    id = Column(String, primary_key=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    type = Column(String, index=True)
    category = Column(String) # execution_gap, negative_space, anomaly, peer_deviation
    severity = Column(String)
    confidence = Column(Float) # Finding confidence (evidence strength for this finding)
    description = Column(Text)
    rationale = Column(Text)
    evidence_ids = Column(JSON) # List of alert/case/asset IDs
    risk_contribution = Column(Float)
    recommended_action = Column(Text)
    status = Column(String, index=True, default="Requires Review")
    upload_id = Column(String, ForeignKey("dataset_uploads.id"), nullable=True, index=True)
    analytic_rule = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    assessment_validity = Column(String, default="HIGH", index=True) # HIGH, CAUTION, LOW, INDETERMINATE
    validity_rationale = Column(Text, nullable=True)
    decision_status = Column(String, default="OPEN", index=True) # OPEN, UNDER_REVIEW, EVIDENCE_REQUESTED, MODIFIED, CONFIRMED, REJECTED, DEFERRED
    modified_assessment = Column(Text, nullable=True)
    adjudicated_by = Column(String, nullable=True)
    adjudicated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ReviewItem(Base):
    __tablename__ = "review_items"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    finding_id = Column(String, ForeignKey("findings.id"))
    priority_score = Column(Float)
    reviewer = Column(String, nullable=True)
    status = Column(String, default="Pending")
    notes = Column(Text, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    user = Column(String)
    action = Column(String)
    object = Column(String)
    previous_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)

class RiskScore(Base):
    __tablename__ = "risk_scores"
    entity_id = Column(String, ForeignKey("entities.id"), primary_key=True)
    overall_score = Column(Float)
    execution_gap_risk = Column(Float)
    negative_space_risk = Column(Float)
    investigation_risk = Column(Float)
    escalation_risk = Column(Float)
    anomaly_risk = Column(Float)
    peer_deviation_risk = Column(Float)
    monitoring_coverage_risk = Column(Float)

class Benchmark(Base):
    __tablename__ = "benchmarks"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entity_id = Column(String, ForeignKey("entities.id"))
    metric = Column(String)
    entity_value = Column(Float)
    peer_median = Column(Float)
    peer_average = Column(Float)
    percentile = Column(Float)
    deviation_percent = Column(Float)
    status_label = Column(String) # NORMAL, WATCH, SIGNIFICANT DEVIATION

class AssessmentAssurance(Base):
    __tablename__ = "assessment_assurances"
    id = Column(String, primary_key=True, index=True) # UUID
    analysis_id = Column(String, nullable=True, index=True)
    upload_id = Column(String, ForeignKey("dataset_uploads.id"), nullable=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=True, index=True)
    overall_status = Column(String, index=True) # HIGH, CAUTION, LOW, INDETERMINATE
    finding_confidence = Column(String, default="HIGH")
    population_exposure = Column(JSON, default=dict)
    coverage_details = Column(JSON, default=dict)
    dependency_details = Column(JSON, default=dict)
    contradiction_details = Column(JSON, default=dict)
    blind_spots = Column(JSON, default=list)
    limitations = Column(JSON, default=list)
    supervisory_interpretation = Column(Text, nullable=True)
    source_hash = Column(String, nullable=True)
    integrity_status = Column(String, default="VERIFIED") # VERIFIED, CHANGED, UNAVAILABLE
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    @property
    def assessment_validity(self):
        return self.overall_status or "HIGH"

    @property
    def validity_rationale(self):
        return self.supervisory_interpretation or ""

    @property
    def temporal_coverage(self):
        if isinstance(self.coverage_details, dict):
            return self.coverage_details.get("temporal", {}).get("status", "HIGH")
        return "HIGH"

    @property
    def severity_coverage(self):
        if isinstance(self.coverage_details, dict):
            return self.coverage_details.get("severity", {}).get("status", "HIGH")
        return "HIGH"

    @property
    def asset_coverage(self):
        if isinstance(self.coverage_details, dict):
            return self.coverage_details.get("asset", {}).get("status", "HIGH")
        return "HIGH"

    @property
    def process_coverage(self):
        if isinstance(self.coverage_details, dict):
            return self.coverage_details.get("process", {}).get("status", "HIGH")
        return "HIGH"

    @property
    def evidence_dependency(self):
        if isinstance(self.dependency_details, dict):
            return self.dependency_details.get("dependency_level", "LOW")
        return "LOW"

    @property
    def contradictions_detected(self):
        if isinstance(self.contradiction_details, dict):
            return len(self.contradiction_details.get("items", [])) > 0
        return False

    @property
    def source_integrity(self):
        return self.integrity_status or "VERIFIED"

    @property
    def dimension_details(self):
        dims = {}
        if isinstance(self.coverage_details, dict):
            dims.update(self.coverage_details)
        return dims


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(String, primary_key=True, index=True) # UUID e.g. ARUN-XXXX
    finding_id = Column(String, ForeignKey("findings.id"), index=True)
    analysis_id = Column(String, nullable=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    state = Column(String, default="HUMAN_REVIEW_REQUIRED", index=True) # CREATED, CONTEXT_BUILT, ASSESSED, CHALLENGED, INVESTIGATION_RECOMMENDED, HUMAN_REVIEW_REQUIRED, COMPLETED
    mode = Column(String, default="DETERMINISTIC_FALLBACK") # LOCAL_LLM, DETERMINISTIC_FALLBACK
    assessment_result = Column(JSON, default=dict)
    challenge_result = Column(JSON, default=dict)
    planner_result = Column(JSON, default=dict)
    human_decision = Column(String, nullable=True) # CONFIRMED, REJECTED, MODIFIED, REQUEST_EVIDENCE
    human_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class AgentAuditLog(Base):
    __tablename__ = "agent_audit_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String, ForeignKey("agent_runs.id"), index=True)
    agent_id = Column(String, index=True) # assessment_agent, challenge_agent, investigation_planner, orchestrator
    finding_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    input_context_hash = Column(String, nullable=True)
    model_provider = Column(String, default="ollama")
    model_name = Column(String, default="local-model")
    prompt_version = Column(String, default="v1.0")
    output_hash = Column(String, nullable=True)
    referenced_evidence_ids = Column(JSON, default=list)
    action = Column(String)
    status = Column(String, default="SUCCESS") # SUCCESS, FALLBACK, VALIDATION_FAILED, ERROR
    validation_result = Column(String, default="PASSED") # PASSED, REPAIRED, REJECTED
    error_message = Column(Text, nullable=True)

class EvidenceRequest(Base):
    __tablename__ = "evidence_requests"
    id = Column(String, primary_key=True, index=True) # UUID e.g. REQ-XXXX
    finding_id = Column(String, ForeignKey("findings.id"), index=True)
    analysis_id = Column(String, nullable=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    requested_by = Column(String, default="Human Examiner")
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    request_type = Column(String, index=True) # CASE_MANAGEMENT_RECORDS, INVESTIGATION_LOGS, ESCALATION_RECORDS, CLOSURE_DISPOSITION_RECORDS, ASSET_INVENTORY, TELEMETRY_COVERAGE, OTHER
    description = Column(Text, nullable=True)
    reason = Column(Text, nullable=False)
    priority = Column(String, default="HIGH") # HIGH, MEDIUM, LOW
    status = Column(String, default="OPEN", index=True) # OPEN, RECEIVED, RESOLVED, CANCELLED
    response_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

class FindingDecision(Base):
    __tablename__ = "finding_decisions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    finding_id = Column(String, ForeignKey("findings.id"), index=True)
    decision = Column(String, index=True) # CONFIRMED, REJECTED, MODIFIED, EVIDENCE_REQUESTED, DEFERRED
    actor = Column(String, default="Human Examiner")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    notes = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)
    rejection_reason = Column(String, nullable=True)
    modified_fields = Column(JSON, nullable=True)
    evidence_refs = Column(JSON, default=list)
    agent_run_id = Column(String, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(String, unique=True, index=True, nullable=False)
    entity_id = Column(String, ForeignKey("entities.id"), index=True, nullable=True)
    event_type = Column(String, index=True, nullable=False)
    actor_type = Column(String, index=True, nullable=False)
    actor_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    analysis_id = Column(String, index=True, nullable=True)
    finding_id = Column(String, ForeignKey("findings.id"), index=True, nullable=True)
    agent_run_id = Column(String, nullable=True, index=True)
    decision_id = Column(String, nullable=True)
    evidence_request_id = Column(String, nullable=True, index=True)
    report_id = Column(String, nullable=True, index=True)
    event_version = Column(String, default="1.0")
    payload_json = Column(JSON, default=dict)
    previous_event_hash = Column(String, nullable=True)
    event_hash = Column(String, nullable=False, index=True)
    source_snapshot_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AssessmentSnapshot(Base):
    __tablename__ = "assessment_snapshots"
    id = Column(String, primary_key=True, index=True) # SNP-UUID...
    analysis_id = Column(String, index=True, nullable=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True, nullable=False)
    snapshot_timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    snapshot_hash = Column(String, nullable=False, index=True)
    data_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)



