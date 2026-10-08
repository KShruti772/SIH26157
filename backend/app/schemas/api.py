from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class EntityBase(BaseModel):
    id: str
    name: str
    sector: str
    assessment_period: str

    class Config:
        from_attributes = True

class QualityReportSchema(BaseModel):
    missing_timestamps: int = 0
    invalid_timestamps: int = 0
    missing_entity_ids: int = 0
    duplicate_ids: int = 0
    unknown_severity: int = 0
    missing_criticality: int = 0
    missing_assets: int = 0
    non_standard_booleans: int = 0

class DatasetUploadBase(BaseModel):
    id: str
    filename: str
    file_type: str
    dataset_type: str
    uploaded_at: datetime
    status: str
    records_received: int
    records_valid: int
    records_rejected: int
    warnings_count: int
    errors_count: int
    columns_detected: List[str] = []
    quality_report: Dict[str, Any] = {}
    error_details: List[str] = []
    entity_ids: List[str] = []
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    source_hash: Optional[str] = None
    hash_algorithm: Optional[str] = "SHA-256"
    hash_created_at: Optional[datetime] = None
    declared_population: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    upload_id: str
    status: str
    filename: str
    file_type: str
    dataset_type: str
    records_received: int
    records_valid: int
    records_rejected: int
    warnings_count: int
    errors_count: int
    columns_detected: List[str]
    quality: Dict[str, Any]
    error_details: List[str] = []
    entities_detected: List[str] = []
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    source_hash: Optional[str] = None

class DataPreviewResponse(BaseModel):
    upload_id: str
    filename: str
    file_type: str
    dataset_type: str
    status: str
    records_received: int
    records_valid: int
    records_rejected: int
    warnings_count: int
    errors_count: int
    columns_detected: List[str]
    quality: Dict[str, Any]
    entities: List[str]
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    total_preview_records: int
    data: List[Dict[str, Any]]

class AnalysisRunRequest(BaseModel):
    upload_id: Optional[str] = None
    entity_ids: Optional[List[str]] = None

class FindingBase(BaseModel):
    id: str
    entity_id: str
    type: str
    category: str
    severity: str
    confidence: float
    description: str
    rationale: str
    evidence_ids: List[str] = []
    risk_contribution: float
    recommended_action: str
    status: str
    upload_id: Optional[str] = None
    analytic_rule: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    assessment_validity: Optional[str] = "HIGH"
    validity_rationale: Optional[str] = None
    decision_status: Optional[str] = "OPEN"
    modified_assessment: Optional[str] = None
    adjudicated_by: Optional[str] = None
    adjudicated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssessmentAssuranceBase(BaseModel):
    id: str
    analysis_id: Optional[str] = None
    upload_id: Optional[str] = None
    entity_id: Optional[str] = None
    overall_status: str
    finding_confidence: str = "HIGH"
    population_exposure: Dict[str, Any] = {}
    coverage_details: Dict[str, Any] = {}
    dependency_details: Dict[str, Any] = {}
    contradiction_details: Dict[str, Any] = {}
    blind_spots: List[Dict[str, Any]] = []
    limitations: List[str] = []
    supervisory_interpretation: Optional[str] = None
    source_hash: Optional[str] = None
    integrity_status: str = "VERIFIED"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RiskScoreBase(BaseModel):
    entity_id: str
    overall_score: float
    execution_gap_risk: float
    negative_space_risk: float
    investigation_risk: float
    escalation_risk: float
    anomaly_risk: float
    peer_deviation_risk: float
    monitoring_coverage_risk: float

    class Config:
        from_attributes = True

class BenchmarkBase(BaseModel):
    id: int
    entity_id: str
    metric: str
    entity_value: float
    peer_median: float
    peer_average: float
    percentile: float
    deviation_percent: float
    status_label: str

    class Config:
        from_attributes = True

class ReviewItemBase(BaseModel):
    id: int
    finding_id: str
    priority_score: float
    reviewer: Optional[str] = None
    status: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class AuditLogBase(BaseModel):
    id: int
    timestamp: datetime
    user: str
    action: str
    object: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None

    class Config:
        from_attributes = True

class AgentRunBase(BaseModel):
    id: str
    finding_id: str
    analysis_id: Optional[str] = None
    entity_id: str
    state: str
    mode: str
    assessment_result: Dict[str, Any] = {}
    challenge_result: Dict[str, Any] = {}
    planner_result: Dict[str, Any] = {}
    human_decision: Optional[str] = None
    human_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AgentAuditLogItem(BaseModel):
    id: int
    run_id: str
    agent_id: str
    finding_id: str
    timestamp: datetime
    input_context_hash: Optional[str] = None
    model_provider: str
    model_name: str
    prompt_version: str
    output_hash: Optional[str] = None
    referenced_evidence_ids: List[str] = []
    action: str
    status: str
    validation_result: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class EvidenceRequestCreate(BaseModel):
    request_type: str
    reason: str
    description: Optional[str] = None
    priority: Optional[str] = "HIGH"
    requested_by: Optional[str] = "Human Examiner"

class EvidenceRequestUpdate(BaseModel):
    status: str # RECEIVED, RESOLVED, CANCELLED
    response_notes: Optional[str] = None

class EvidenceRequestBase(BaseModel):
    id: str
    finding_id: str
    analysis_id: Optional[str] = None
    entity_id: str
    requested_by: str
    requested_at: datetime
    request_type: str
    description: Optional[str] = None
    reason: str
    priority: str
    status: str
    response_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FindingDecisionCreate(BaseModel):
    decision: str # CONFIRM, REJECT, MODIFY, REQUEST_EVIDENCE, DEFER
    notes: Optional[str] = None
    rationale: Optional[str] = None
    reviewer: Optional[str] = "Human Examiner"
    rejection_reason: Optional[str] = None
    modified_assessment: Optional[str] = None
    modified_fields: Optional[Dict[str, Any]] = None
    agent_run_id: Optional[str] = None

class FindingDecisionBase(BaseModel):
    id: int
    finding_id: str
    decision: str
    actor: str
    timestamp: datetime
    notes: Optional[str] = None
    rationale: Optional[str] = None
    rejection_reason: Optional[str] = None
    modified_fields: Optional[Dict[str, Any]] = None
    evidence_refs: List[str] = []
    agent_run_id: Optional[str] = None

    class Config:
        from_attributes = True

class FindingTimelineItem(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: str
    actor: str
    action: str
    status: Optional[str] = None
    summary: str
    details: Dict[str, Any] = {}

class ReviewQueueEnhancedItem(BaseModel):
    review_item: ReviewItemBase
    finding: FindingBase
    evidence_completeness: float
    agent_review_status: str # NOT_STARTED, COMPLETED, REQUIRED
    decision_status: str # OPEN, UNDER_REVIEW, EVIDENCE_REQUESTED, MODIFIED, CONFIRMED, REJECTED, DEFERRED
    why_review: str

# =========================================================================
# MODULE 8 — REPORTING & SUPERVISORY DASHBOARD SCHEMAS
# =========================================================================

class CapabilityAssessmentItem(BaseModel):
    name: str # Threat Detection, Investigation, Escalation, Incident Response, Security Operations, Governance & Oversight, Operational Discipline, Cyber Resilience
    status: str # OBSERVED CONCERN, NO OBSERVED CONCERN, INSUFFICIENT EVIDENCE, NOT ASSESSED
    findings_count: int
    finding_ids: List[str] = []
    evidence_coverage: str
    assessment_validity: str # HIGH, CAUTION, LOW, INDETERMINATE
    human_adjudication_state: str
    evidence_limitations: List[str] = []
    observation: str
    implication: str

class EvidenceLimitationsSummary(BaseModel):
    missing: List[Dict[str, Any]] = []
    partial: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []
    contradictory: List[Dict[str, Any]] = []

class HumanAdjudicationSummary(BaseModel):
    total_findings: int
    confirmed: int
    modified: int
    rejected: int
    evidence_requested: int
    deferred: int
    open_under_review: int

class ReportMetadata(BaseModel):
    report_id: str
    report_version: str
    generated_at: datetime
    analysis_id: Optional[str] = None
    entity_id: str
    classification: str = "SAT-SA — Supervisory Assessment Prototype"

class SupervisoryReport(BaseModel):
    report_metadata: Dict[str, Any]
    entity_summary: Dict[str, Any]
    assessment_summary: Dict[str, Any]
    capability_assessment: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    assurance: Dict[str, Any]
    evidence_limitations: Dict[str, Any]
    human_adjudication: Dict[str, Any]
    evidence_requests: List[Dict[str, Any]]
    traceability: Dict[str, Any]

class DashboardSummary(BaseModel):
    entities_count: int
    findings_count: int
    high_risk_entities: int
    priority_reviews: int
    total_uploads: int
    total_alerts: int
    entities: List[Dict[str, Any]] = []
    supervisory_attention: List[Dict[str, Any]] = []
    findings_by_category: Dict[str, int] = {}
    human_adjudication: Dict[str, int] = {}
    evidence_requests: Dict[str, int] = {}
    capabilities_overview: List[Dict[str, Any]] = []
    assessment_validity_distribution: Dict[str, int] = {}

class EntityAssessmentResponse(BaseModel):
    entity: EntityBase
    assessment_id: Optional[str] = None
    source_submission: Optional[Dict[str, Any]] = None
    record_counts: Dict[str, int] = {}
    supervisory_attention: List[Dict[str, Any]] = []
    capabilities: List[CapabilityAssessmentItem] = []
    findings_summary: Dict[str, Any] = {}
    assurance: Optional[Dict[str, Any]] = None
    evidence_limitations: EvidenceLimitationsSummary
    human_adjudication: HumanAdjudicationSummary
    evidence_requests: List[EvidenceRequestBase] = []
    risk: Optional[RiskScoreBase] = None


# =========================================================================
# MODULE 9 — AUDIT & REPLAY SCHEMAS
# =========================================================================

class AuditEventResponse(BaseModel):
    id: int
    event_id: str
    entity_id: Optional[str] = None
    event_type: str
    actor_type: str
    actor_id: str
    timestamp: datetime
    analysis_id: Optional[str] = None
    finding_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    decision_id: Optional[str] = None
    evidence_request_id: Optional[str] = None
    report_id: Optional[str] = None
    event_version: str = "1.0"
    payload_json: Dict[str, Any] = {}
    previous_event_hash: Optional[str] = None
    event_hash: str
    source_snapshot_hash: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditIntegrityResponse(BaseModel):
    analysis_id: Optional[str] = None
    entity_id: Optional[str] = None
    valid: bool
    total_events: int
    broken_at_index: Optional[int] = None
    broken_event_id: Optional[str] = None
    error: Optional[str] = None
    chain_hashes: List[str] = []


class AuditReplayResponse(BaseModel):
    analysis_id: str
    entity_id: str
    replay_valid: bool
    chain_integrity: str
    state_match: bool
    events_processed: int
    chain_verification: Optional[Dict[str, Any]] = None
    mismatches: List[Dict[str, Any]] = []
    reconstructed_state: Dict[str, Any] = {}
    persisted_state: Dict[str, Any] = {}
    replayed_at: str


class AssessmentSnapshotResponse(BaseModel):
    id: str
    analysis_id: Optional[str] = None
    entity_id: str
    snapshot_timestamp: datetime
    snapshot_hash: str
    data_json: Dict[str, Any] = {}
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =========================================================================
# AUTHENTICATION & USER SCHEMAS
# =========================================================================

class UserRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    confirm_password: str
    organization: str
    role: str = "SUPERVISOR" # Allowed self-registration: SUPERVISOR, REVIEWER


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    organization: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuthTokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserResponse
    role: str
    name: str



