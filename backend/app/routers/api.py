from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import Response, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import time
import json
import uuid
import asyncio
import re
import logging
import datetime

from app.database import get_db, SessionLocal
from app.models import domain
from app.schemas import api as schemas
from app.services import ingestion, evidence, workspace, reporting, audit as audit_service
from app.services.audit import AuditService, ReplayEngine, EventType, ActorType
from app.analytics.engine import SupervisoryAnalyticsEngine

from app.assurance.service import AssessmentAssuranceService
from app.assurance import hashing
from app.agents.orchestrator import AgentOrchestrator
from app.agents.schemas import (
    HumanReviewPackage,
    HumanDecisionRequest,
    AgentRunResponse,
    AgentAuditLogResponse,
)

from app.services import auth as auth_service
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
    revoke_token,
    security_scheme,
    UserRole,
    ALLOWED_SELF_REGISTER_ROLES,
)

logger = logging.getLogger("satsa.api")

# Central Public and Protected Router definitions
public_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(get_current_user)])

# Unified router for backward-compatibility
router = APIRouter()
router.include_router(public_router)
router.include_router(protected_router)

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024 # 100 MB max for prototype upload
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# =========================================================================
# PUBLIC ENDPOINTS (No Authentication Required)
# =========================================================================

@public_router.get("/health")
def health_check():
    """System liveness/health probe."""
    return {"status": "ok"}


@public_router.post("/auth/register", response_model=schemas.AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: schemas.UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new standard user account.
    Public self-registration is strictly restricted to REVIEWER role.
    SUPERVISOR and ADMINISTRATOR roles must be provisioned through administrative controls.
    """
    email_clean = (req.email or "").strip().lower()
    full_name_clean = (req.full_name or "").strip()
    org_clean = (req.organization or "").strip()
    requested_role = (req.role or UserRole.REVIEWER).strip().upper()

    if not full_name_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full name is required.")

    if not org_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization is required.")

    if not email_clean or not EMAIL_REGEX.match(email_clean):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid email address is required.")

    if requested_role in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Self-registration as '{requested_role}' is not permitted. Only REVIEWER accounts may self-register. Contact an administrator for elevated privileges.",
        )

    if requested_role not in ALLOWED_SELF_REGISTER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{req.role}'. Allowed self-registration role: REVIEWER.",
        )

    if req.password != req.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match.")

    if len(req.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters long.")

    # Check for existing email
    existing = db.query(domain.User).filter(domain.User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email address already exists.")

    user_id = f"USR-{uuid.uuid4().hex[:10].upper()}"
    pwd_hash = hash_password(req.password)

    new_user = domain.User(
        id=user_id,
        full_name=full_name_clean,
        email=email_clean,
        password_hash=pwd_hash,
        organization=org_clean,
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Record USER_REGISTERED audit event
    try:
        audit_svc = AuditService()
        audit_svc.record_event(
            db=db,
            event_type=EventType.USER_REGISTERED,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=user_id,
            payload={
                "user_id": user_id,
                "email": email_clean,
                "full_name": full_name_clean,
                "organization": org_clean,
                "role": UserRole.REVIEWER,
            },
        )
    except Exception as e:
        logger.error(f"Audit log failed for user registration: {e}")

    token = create_access_token(new_user)
    return schemas.AuthTokenResponse(
        token=token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(new_user),
        role=new_user.role,
        name=new_user.full_name,
    )


@public_router.post("/auth/login", response_model=schemas.AuthTokenResponse)
def login_user(req: schemas.UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates a user via email and password, issuing a signed JWT token with unique JTI.
    Returns generic authentication error for any invalid credential.
    """
    email_clean = (req.email or "").strip().lower()
    user = db.query(domain.User).filter(domain.User.email == email_clean).first()

    audit_svc = AuditService()

    if not user or not verify_password(req.password, user.password_hash):
        try:
            audit_svc.record_event(
                db=db,
                event_type=EventType.USER_LOGIN_FAILED,
                actor_type=ActorType.SYSTEM,
                actor_id="AuthService",
                payload={"attempted_email": email_clean, "reason": "INVALID_CREDENTIALS"},
            )
        except Exception as e:
            logger.error(f"Audit log failed for failed login: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact system administrator.",
        )

    try:
        audit_svc.record_event(
            db=db,
            event_type=EventType.USER_LOGIN,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=user.id,
            payload={
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "organization": user.organization,
            },
        )
    except Exception as e:
        logger.error(f"Audit log failed for user login: {e}")

    token = create_access_token(user)
    return schemas.AuthTokenResponse(
        token=token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(user),
        role=user.role,
        name=user.full_name,
    )


# =========================================================================
# PROTECTED AUTHENTICATION & USER ENDPOINTS
# =========================================================================

@protected_router.get("/auth/me", response_model=schemas.UserResponse)
def get_current_user_profile(
    current_user: domain.User = Depends(get_current_user),
):
    """
    Retrieves the currently authenticated user profile from validated, unrevoked JWT session.
    """
    return schemas.UserResponse.model_validate(current_user)


@protected_router.post("/auth/logout")
def logout_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    current_user: domain.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Logs out the authenticated user, persistently revokes the token JTI in the database,
    and records a USER_LOGOUT audit event.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorization token provided for logout.",
        )

    try:
        revoke_token(db=db, token=auth.credentials, reason="USER_LOGOUT")
    except ValueError as ve:
        logger.warning(f"Invalid token supplied during logout for user {current_user.id}: {type(ve).__name__}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token provided for logout.",
        )
    except Exception as e:
        logger.error(f"Token revocation failed during logout for user {current_user.id}: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session token. Logout not completed.",
        )

    try:
        audit_svc = AuditService()
        audit_svc.record_event(
            db=db,
            event_type=EventType.USER_LOGOUT,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=current_user.id,
            payload={"user_id": current_user.id, "email": current_user.email},
        )
    except Exception as e:
        logger.error(f"Audit log failed for user logout: {type(e).__name__}")
    return {"status": "ok", "message": "Successfully logged out and revoked token."}


# =========================================================================
# USER ADMINISTRATION (ADMINISTRATOR ONLY)
# =========================================================================

class RoleUpdateRequest(BaseModel):
    role: str

class UserStatusUpdateRequest(BaseModel):
    is_active: bool

@protected_router.get("/admin/users", response_model=List[schemas.UserResponse])
def list_users(
    admin: domain.User = Depends(require_role([UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """Administrator-only: list all registered users."""
    users = db.query(domain.User).order_by(domain.User.created_at.asc()).all()
    return [schemas.UserResponse.model_validate(u) for u in users]


@protected_router.patch("/admin/users/{user_id}/role", response_model=schemas.UserResponse)
def update_user_role(
    user_id: str,
    req: RoleUpdateRequest,
    admin: domain.User = Depends(require_role([UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """Administrator-only: update user role (REVIEWER, SUPERVISOR, ADMINISTRATOR)."""
    target_role = (req.role or "").strip().upper()
    if target_role not in [UserRole.REVIEWER, UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=400, detail=f"Invalid role '{req.role}'.")

    user = db.query(domain.User).filter(domain.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.role = target_role
    db.commit()
    db.refresh(user)
    return schemas.UserResponse.model_validate(user)


@protected_router.patch("/admin/users/{user_id}/status", response_model=schemas.UserResponse)
def update_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    admin: domain.User = Depends(require_role([UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """Administrator-only: activate or deactivate a user account."""
    user = db.query(domain.User).filter(domain.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.is_active = req.is_active
    db.commit()
    db.refresh(user)
    return schemas.UserResponse.model_validate(user)


# =========================================================================
# MODULE 1 & 2 — INGESTION & DATASET MANAGEMENT
# =========================================================================

# In-memory storage for active analysis tracking
analysis_store = {}

@protected_router.post("/upload", response_model=schemas.UploadResponse)
async def upload_data(
    file: UploadFile = File(...),
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Real ingestion endpoint (Supervisor/Admin only):
    - Reads and validates file payload
    - Safe CSV/JSON parsing
    - Schema detection & field mapping
    - Normalization & data quality profiling
    - Cryptographic SHA-256 source hashing
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    filename = file.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ['csv', 'json', 'tsv']:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}. Expected CSV, TSV, or JSON.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed size (100 MB)")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is completely empty.")

    try:
        upload_record = ingestion.process_dataset_submission(
            file_bytes=content,
            filename=filename,
            db=db,
        )
        return schemas.UploadResponse(
            upload_id=upload_record.id,
            status=upload_record.status,
            filename=upload_record.filename,
            file_type=upload_record.file_type,
            dataset_type=upload_record.dataset_type,
            records_received=upload_record.records_received,
            records_valid=upload_record.records_valid,
            records_rejected=upload_record.records_rejected,
            warnings_count=upload_record.warnings_count,
            errors_count=upload_record.errors_count,
            quality_report=upload_record.quality_report or {},
            error_details=upload_record.error_details or [],
            date_range_start=upload_record.date_range_start,
            date_range_end=upload_record.date_range_end,
            source_hash=upload_record.source_hash,
            hash_algorithm=upload_record.hash_algorithm,
            hash_created_at=upload_record.hash_created_at,
            declared_population=upload_record.declared_population or {},
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Data Validation Error: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Processing Error: {str(e)}")


@protected_router.get("/uploads", response_model=List[schemas.DatasetUploadBase])
def get_uploads(db: Session = Depends(get_db)):
    """Retrieve history of uploaded submissions."""
    return db.query(domain.DatasetUpload).order_by(domain.DatasetUpload.uploaded_at.desc()).all()


@protected_router.get("/upload/{id}/preview", response_model=schemas.DataPreviewResponse)
def preview_dataset(id: str, db: Session = Depends(get_db)):
    """
    Returns data quality profile, column mapping, detected entities, sample records,
    and cryptographic integrity provenance for an uploaded dataset.
    """
    upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == id).first()
    if not upload:
        raise HTTPException(status_code=404, detail=f"Upload ID {id} not found")

    sample_alerts = db.query(domain.Alert).filter(domain.Alert.upload_id == id).limit(5).all()
    sample_records = [
        {
            "id": a.id,
            "entity_id": a.entity_id,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "severity": a.severity,
            "category": a.category,
            "acknowledged": a.acknowledged,
            "investigation_started": a.investigation_started,
            "escalated": a.escalated,
            "disposition": a.disposition,
        }
        for a in sample_alerts
    ]

    return schemas.DataPreviewResponse(
        upload_id=upload.id,
        filename=upload.filename,
        file_type=upload.file_type,
        dataset_type=upload.dataset_type,
        status=upload.status,
        records_received=upload.records_received,
        records_valid=upload.records_valid,
        records_rejected=upload.records_rejected,
        warnings_count=upload.warnings_count,
        errors_count=upload.errors_count,
        columns_detected=upload.columns_detected or [],
        quality_report=upload.quality_report or {},
        error_details=upload.error_details or [],
        entity_ids=upload.entity_ids or [],
        date_range_start=upload.date_range_start,
        date_range_end=upload.date_range_end,
        sample_records=sample_records,
        source_hash=upload.source_hash,
        hash_algorithm=upload.hash_algorithm or "SHA-256",
        hash_created_at=upload.hash_created_at,
        declared_population=upload.declared_population or {},
    )


# =========================================================================
# MODULE 4 — SUPERVISORY ANALYTICS ENGINE API ENDPOINTS
# =========================================================================

class AnalysisRunRequest(BaseModel):
    entity_id: Optional[str] = None
    upload_id: Optional[str] = None

@protected_router.post("/analysis/run")
def trigger_analysis(
    req: Optional[AnalysisRunRequest] = None,
    background_tasks: BackgroundTasks = None,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Executes the analytical discovery engine over real operational records (Supervisor/Admin only).
    """
    analysis_id = f"ANL-{uuid.uuid4().hex[:8].upper()}"
    entity_id = req.entity_id if req else None
    upload_id = req.upload_id if req else None

    engine_inst = SupervisoryAnalyticsEngine()
    summary = engine_inst.run(db=db, entity_id=entity_id, upload_id=upload_id)

    analysis_store[analysis_id] = {
        "status": "completed",
        "progress": 100,
        "summary": summary,
        "entity_id": entity_id,
        "upload_id": upload_id,
        "executed_by": current_user.email,
    }

    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "findings_count": summary.get("findings_count", 0),
        "entities_analyzed": summary.get("entities_analyzed", 0),
        "execution_gaps": summary.get("execution_gaps", 0),
        "negative_spaces": summary.get("negative_spaces", 0),
        "statistical_anomalies": summary.get("statistical_anomalies", 0),
    }


@protected_router.get("/analysis/{id}/status")
def get_analysis_status(id: str):
    """Check progress or retrieve summary of an analytics run."""
    if id in analysis_store:
        return analysis_store[id]
    return {"analysis_id": id, "status": "completed", "progress": 100}


# =========================================================================
# CORE SUPERVISORY DATA & REVIEW QUEUE
# =========================================================================

@protected_router.get("/dashboard")
@protected_router.get("/dashboard/summary", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Aggregates high-level supervisory metrics across all assessed critical entities."""
    return reporting.get_dashboard_summary_data(db)


@protected_router.get("/entities", response_model=List[schemas.EntityBase])
def get_entities(db: Session = Depends(get_db)):
    """List all registered critical sector entities."""
    return db.query(domain.Entity).all()


@protected_router.get("/entities/{id}")
def get_entity_profile(id: str, db: Session = Depends(get_db)):
    """Retrieve single entity profile along with linked assets and active finding count."""
    entity = db.query(domain.Entity).filter(domain.Entity.id == id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {id} not found")

    assets = db.query(domain.Asset).filter(domain.Asset.entity_id == id).all()
    finding_count = db.query(domain.Finding).filter(domain.Finding.entity_id == id).count()
    risk = db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == id).first()

    return {
        "id": entity.id,
        "name": entity.name,
        "sector": entity.sector,
        "assessment_period": entity.assessment_period,
        "assets_count": len(assets),
        "findings_count": finding_count,
        "supervisory_score": risk.score if risk else 0.0,
    }


@protected_router.get("/entities/{id}/assessment", response_model=schemas.EntityAssessmentResponse)
def get_entity_assessment(id: str, db: Session = Depends(get_db)):
    """Returns complete supervisory assessment packet for an entity."""
    try:
        res = reporting.get_entity_assessment_data(db, id)
        return res
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Entity {id} not found")


@protected_router.get("/findings", response_model=List[schemas.FindingBase])
def get_findings(
    entity_id: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all supervisory findings with optional filtering."""
    query = db.query(domain.Finding)
    if entity_id:
        query = query.filter(domain.Finding.entity_id == entity_id)
    if category:
        query = query.filter(domain.Finding.category == category)
    if severity:
        query = query.filter(domain.Finding.severity == severity)
    return query.all()


@protected_router.get("/findings/{id}")
def get_finding_detail(id: str, db: Session = Depends(get_db)):
    """Retrieve full finding detail including linked operational evidence and assurance rationale."""
    finding = db.query(domain.Finding).filter(domain.Finding.id == id).first()
    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding '{id}' not found")

    review_item = db.query(domain.ReviewItem).filter(domain.ReviewItem.finding_id == id).first()

    return {
        "id": finding.id,
        "entity_id": finding.entity_id,
        "type": finding.type,
        "category": finding.category,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "description": finding.description,
        "rationale": finding.rationale,
        "evidence_ids": finding.evidence_ids or [],
        "risk_contribution": finding.risk_contribution or 0.0,
        "recommended_action": finding.recommended_action,
        "status": finding.status,
        "decision_status": finding.decision_status or "OPEN",
        "analytic_rule": finding.analytic_rule,
        "details": finding.details or {},
        "assessment_validity": finding.assessment_validity or "HIGH",
        "validity_rationale": finding.validity_rationale,
        "priority_score": review_item.priority_score if review_item else 0.0,
    }


@protected_router.get("/execution-gaps")
def get_execution_gaps(db: Session = Depends(get_db)):
    """Shortcut endpoint for execution-gap findings."""
    return db.query(domain.Finding).filter(domain.Finding.category == "execution_gap").all()


@protected_router.get("/negative-space")
def get_negative_space(db: Session = Depends(get_db)):
    """Shortcut endpoint for negative-space findings."""
    return db.query(domain.Finding).filter(domain.Finding.category == "negative_space").all()


@protected_router.get("/anomalies")
def get_anomalies(db: Session = Depends(get_db)):
    """Shortcut endpoint for anomaly findings."""
    return db.query(domain.Finding).filter(domain.Finding.category == "statistical_anomaly").all()


@protected_router.get("/benchmarks")
def get_benchmarks(sector: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve cohort peer benchmarks."""
    query = db.query(domain.Benchmark)
    if sector:
        query = query.filter(domain.Benchmark.sector == sector)
    return query.all()


@protected_router.get("/risk/{entity_id}", response_model=schemas.RiskScoreBase)
def get_risk_score(entity_id: str, db: Session = Depends(get_db)):
    """Fetch transparent 0-100 supervisory score and driver breakdown."""
    risk = db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == entity_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail=f"Risk profile not found for entity {entity_id}")
    return risk


@protected_router.get("/review-queue")
def get_review_queue(
    status: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    sector: Optional[str] = None,
    sort_by: Optional[str] = "priority_score",
    order: Optional[str] = "desc",
    db: Session = Depends(get_db),
):
    """Retrieve prioritized supervisory review queue with multi-dimensional filtering and sorting."""
    return workspace.get_review_queue_items(
        db=db,
        status=status,
        category=category,
        severity=severity,
        sector=sector,
        sort_by=sort_by,
        order=order,
    )


class ReviewItemUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

@protected_router.patch("/review-queue/{id}", response_model=schemas.ReviewItemBase)
def update_review_item(
    id: int,
    req: ReviewItemUpdate,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """Update review queue item status or analyst notes (Supervisor/Admin only)."""
    item = db.query(domain.ReviewItem).filter(domain.ReviewItem.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if req.status:
        item.status = req.status
    if req.notes is not None:
        item.notes = req.notes
    db.commit()
    return item


@protected_router.get("/evidence/{finding_id}")
def get_finding_evidence(finding_id: str, db: Session = Depends(get_db)):
    """Retrieve full granular operational evidence trace for a finding."""
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return evidence.assemble_evidence_trace(finding=finding, db=db)


# =========================================================================
# MODULE 7 — HUMAN EXAMINER WORKSPACE API ENDPOINTS
# =========================================================================

@protected_router.post("/findings/{finding_id}/decision")
def submit_finding_human_decision(
    finding_id: str,
    req: schemas.FindingDecisionCreate,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Human examiner formal adjudication endpoint (Supervisor/Admin only):
    - CONFIRM, REJECT, MODIFY, REQUEST_EVIDENCE, DEFER
    - Preserves source evidence immutability
    - Records decision audit trail
    """
    try:
        res = workspace.record_human_decision(
            finding_id=finding_id,
            decision=req.decision,
            notes=req.notes,
            rationale=req.rationale,
            reviewer=req.reviewer or current_user.full_name or "Human Examiner",
            db=db,
            rejection_reason=req.rejection_reason,
            modified_assessment=req.modified_assessment,
            modified_fields=req.modified_fields,
            agent_run_id=req.agent_run_id,
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record human decision: {str(e)}")


@protected_router.post("/findings/{finding_id}/evidence-requests", response_model=schemas.EvidenceRequestBase)
def create_finding_evidence_request(
    finding_id: str,
    req: schemas.EvidenceRequestCreate,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Formal supervisory evidence request creation:
    - Transitions finding state to EVIDENCE_REQUESTED
    - Logs audit trail entry
    """
    try:
        ev_req = workspace.create_evidence_request(
            finding_id=finding_id,
            request_type=req.request_type,
            reason=req.reason,
            requested_by=req.requested_by or current_user.full_name or "Human Examiner",
            db=db,
            description=req.description,
            priority=req.priority or "HIGH",
        )
        return ev_req
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create evidence request: {str(e)}")


@protected_router.get("/findings/{finding_id}/evidence-requests", response_model=List[schemas.EvidenceRequestBase])
def get_finding_evidence_requests(
    finding_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all evidence requests created for a finding."""
    return db.query(domain.EvidenceRequest).filter(
        domain.EvidenceRequest.finding_id == finding_id
    ).order_by(domain.EvidenceRequest.requested_at.desc()).all()


@protected_router.patch("/evidence-requests/{request_id}", response_model=schemas.EvidenceRequestBase)
def update_evidence_request(
    request_id: str,
    req: schemas.EvidenceRequestUpdate,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """Update status of an existing evidence request (RECEIVED, RESOLVED, CANCELLED) (Supervisor/Admin only)."""
    try:
        updated = workspace.update_evidence_request_status(
            request_id=request_id,
            status=req.status,
            resolution_notes=req.resolution_notes,
            resolved_by=req.resolved_by or current_user.full_name or "Supervisor Examiner",
            db=db,
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update evidence request: {str(e)}")


@protected_router.get("/findings/{finding_id}/history", response_model=List[schemas.FindingTimelineItem])
def get_finding_history(
    finding_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve full chronological audit and decision lifecycle history for a finding.
    Combines human examiner adjudications, evidence requests, and agent runs into a unified timeline.
    """
    try:
        history = workspace.get_finding_unified_history(finding_id=finding_id, db=db)
        return history
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assemble finding history: {str(e)}")


# =========================================================================
# MODULE 8 — REPORTING & DASHBOARD API ENDPOINTS
# =========================================================================

class ReportGenerateRequest(BaseModel):
    analysis_id: Optional[str] = None
    entity_id: Optional[str] = None

@protected_router.get("/reports")
def get_reports(db: Session = Depends(get_db)):
    """List available entities and submission analyses available for report compilation."""
    entities = db.query(domain.Entity).all()
    results = []
    for ent in entities:
        f_count = db.query(domain.Finding).filter(domain.Finding.entity_id == ent.id).count()
        ass = db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.entity_id == ent.id).first()
        results.append({
            "id": f"RPT-{ent.id}",
            "entity_id": ent.id,
            "entity_name": ent.name,
            "sector": ent.sector,
            "findings_count": f_count,
            "assessment_validity": ass.assessment_validity if ass else "HIGH",
            "date": ent.assessment_period or (datetime.datetime.utcnow().strftime("%Y-%m-%d")),
            "title": f"Supervisory Assessment — {ent.name}",
        })
    return results

@protected_router.post("/reports/generate")
def generate_report(
    req: Optional[ReportGenerateRequest] = None,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """Compile a complete, evidence-grounded supervisory report (Supervisor/Admin only)."""
    analysis_id = req.analysis_id if req else None
    entity_id = req.entity_id if req else None
    try:
        report_data = reporting.generate_supervisory_report_data(
            db=db,
            analysis_id=analysis_id,
            entity_id=entity_id,
        )
        return report_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation error: {str(e)}")

@protected_router.get("/reports/{analysis_id}", response_model=schemas.SupervisoryReport)
def get_report_by_analysis(analysis_id: str, db: Session = Depends(get_db)):
    """Fetch full structured supervisory assessment report by analysis ID or entity ID."""
    try:
        is_entity = db.query(domain.Entity).filter(domain.Entity.id == analysis_id).first()
        if is_entity:
            return reporting.generate_supervisory_report_data(db=db, entity_id=analysis_id)
        return reporting.generate_supervisory_report_data(db=db, analysis_id=analysis_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@protected_router.get("/reports/entity/{entity_id}", response_model=schemas.SupervisoryReport)
def get_report_by_entity(entity_id: str, db: Session = Depends(get_db)):
    """Fetch full structured supervisory assessment report for a specific entity."""
    try:
        return reporting.generate_supervisory_report_data(db=db, entity_id=entity_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate entity report: {str(e)}")

@protected_router.get("/reports/{analysis_id}/json")
def download_report_json(analysis_id: str, db: Session = Depends(get_db)):
    """Export machine-readable supervisory assessment report JSON."""
    try:
        is_entity = db.query(domain.Entity).filter(domain.Entity.id == analysis_id).first()
        if is_entity:
            report_data = reporting.generate_supervisory_report_data(db=db, entity_id=analysis_id)
        else:
            report_data = reporting.generate_supervisory_report_data(db=db, analysis_id=analysis_id)

        json_str = json.dumps(report_data, indent=2, default=str)
        filename = f"SAT_SA_Report_{analysis_id}.json"
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export report JSON: {str(e)}")

@protected_router.get("/reports/{analysis_id}/pdf")
def download_report_pdf(analysis_id: str, db: Session = Depends(get_db)):
    """Generate and export professional printable supervisory assessment PDF."""
    try:
        is_entity = db.query(domain.Entity).filter(domain.Entity.id == analysis_id).first()
        if is_entity:
            report_data = reporting.generate_supervisory_report_data(db=db, entity_id=analysis_id)
        else:
            report_data = reporting.generate_supervisory_report_data(db=db, analysis_id=analysis_id)

        pdf_bytes = reporting.generate_pdf_report(report_data)
        filename = f"SAT_SA_Report_{analysis_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export report PDF: {str(e)}")

@protected_router.get("/reports/entity/{entity_id}/pdf")
def download_entity_report_pdf(entity_id: str, db: Session = Depends(get_db)):
    """Generate and export professional printable supervisory assessment PDF for entity."""
    try:
        report_data = reporting.generate_supervisory_report_data(db=db, entity_id=entity_id)
        pdf_bytes = reporting.generate_pdf_report(report_data)
        filename = f"SAT_SA_Report_{entity_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export entity report PDF: {str(e)}")


@protected_router.get("/audit")
def get_audit(db: Session = Depends(get_db)):
    """Legacy audit log endpoint."""
    return db.query(domain.AuditLog).order_by(domain.AuditLog.timestamp.desc()).limit(100).all()


# =========================================================================
# MODULE 5 — ASSESSMENT ASSURANCE API ENDPOINTS
# =========================================================================

@protected_router.get("/assurance/{analysis_id}", response_model=schemas.AssessmentAssuranceBase)
def get_assurance(analysis_id: str, db: Session = Depends(get_db)):
    """
    Retrieve comprehensive assessment assurance profile for a specific analysis session,
    upload ID, or finding ID.
    """
    rec = db.query(domain.AssessmentAssurance).filter(
        (domain.AssessmentAssurance.analysis_id == analysis_id) |
        (domain.AssessmentAssurance.upload_id == analysis_id) |
        (domain.AssessmentAssurance.id == analysis_id)
    ).first()

    if not rec:
        finding = db.query(domain.Finding).filter(domain.Finding.id == analysis_id).first()
        if finding:
            rec = db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.entity_id == finding.entity_id).first()

    if not rec:
        svc = AssessmentAssuranceService()
        rec = svc.evaluate_assurance(db=db, analysis_id=analysis_id)

    return rec

@protected_router.get("/assurance/entity/{entity_id}", response_model=schemas.AssessmentAssuranceBase)
def get_entity_assurance(entity_id: str, db: Session = Depends(get_db)):
    """Retrieve latest assessment assurance profile for an entity."""
    rec = db.query(domain.AssessmentAssurance).filter(
        domain.AssessmentAssurance.entity_id == entity_id
    ).order_by(domain.AssessmentAssurance.created_at.desc()).first()

    if not rec:
        svc = AssessmentAssuranceService()
        rec = svc.evaluate_assurance(db=db, entity_id=entity_id)

    return rec

@protected_router.get("/assurance/{analysis_id}/blind-spots")
def get_assurance_blind_spots(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieve structured evidence blind spots."""
    rec = get_assurance(analysis_id, db)
    return {"analysis_id": analysis_id, "blind_spots": rec.blind_spots or []}

@protected_router.get("/assurance/{analysis_id}/contradictions")
def get_assurance_contradictions(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieve evidence contradiction and inconsistency records."""
    rec = get_assurance(analysis_id, db)
    return {"analysis_id": analysis_id, "contradictions": rec.contradiction_details or {}}

@protected_router.get("/uploads/{upload_id}/integrity")
def get_upload_integrity(upload_id: str, db: Session = Depends(get_db)):
    """Verify cryptographic source hash integrity for an uploaded dataset submission."""
    upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload record not found")
    return hashing.verify_upload_integrity(upload)


# =========================================================================
# MODULE 6 — LOCAL AGENTIC AI API ENDPOINTS
# =========================================================================

@protected_router.post("/agents/analyze/{finding_id}", response_model=HumanReviewPackage)
def trigger_agent_analysis(
    finding_id: str,
    force_fallback: bool = False,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Execute 3-Agent supervisory reasoning pipeline (Supervisor/Admin only).
    """
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")

    try:
        orchestrator = AgentOrchestrator()
        review_package = orchestrator.run_analysis(
            finding_id=finding_id,
            db=db,
            force_fallback=force_fallback,
        )
        return review_package
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow execution error: {str(e)}")


@protected_router.get("/agents/{run_id}", response_model=AgentRunResponse)
def get_agent_run(run_id: str, db: Session = Depends(get_db)):
    """Retrieve agent run status and stored step results."""
    agent_run = db.query(domain.AgentRun).filter(domain.AgentRun.id == run_id).first()
    if not agent_run:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found")
    return AgentRunResponse(
        run_id=agent_run.id,
        finding_id=agent_run.finding_id,
        entity_id=agent_run.entity_id or "",
        state=agent_run.state,
        mode=agent_run.mode,
        assessment_result=agent_run.assessment_result or {},
        challenge_result=agent_run.challenge_result or {},
        planner_result=agent_run.planner_result or {},
        human_decision=agent_run.human_decision,
        human_notes=agent_run.human_notes,
        created_at=agent_run.created_at,
        updated_at=agent_run.updated_at,
    )


@protected_router.get("/agents/{run_id}/result", response_model=HumanReviewPackage)
def get_agent_result(run_id: str, db: Session = Depends(get_db)):
    """Retrieve the full structured HumanReviewPackage for a completed agent run."""
    agent_run = db.query(domain.AgentRun).filter(domain.AgentRun.id == run_id).first()
    if not agent_run:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found")
    return AgentOrchestrator.to_human_review_package(agent_run)


@protected_router.get("/agents/{run_id}/audit", response_model=List[AgentAuditLogResponse])
def get_agent_audit_trail(run_id: str, db: Session = Depends(get_db)):
    """Retrieve machine-readable audit logs for all steps in an agent run."""
    logs = db.query(domain.AgentAuditLog).filter(domain.AgentAuditLog.run_id == run_id).order_by(domain.AgentAuditLog.timestamp.asc()).all()
    return logs


@protected_router.get("/agents/finding/{finding_id}/latest", response_model=Optional[HumanReviewPackage])
def get_latest_finding_agent_review(finding_id: str, db: Session = Depends(get_db)):
    """Retrieve the most recent agent review package for a finding, if one exists."""
    agent_run = db.query(domain.AgentRun).filter(
        domain.AgentRun.finding_id == finding_id
    ).order_by(domain.AgentRun.created_at.desc()).first()

    if not agent_run:
        return None
    return AgentOrchestrator.to_human_review_package(agent_run)


@protected_router.post("/agents/{run_id}/decision", response_model=AgentRunResponse)
def submit_human_decision(
    run_id: str,
    req: HumanDecisionRequest,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Human supervisor submits final decision on agent proposal (Supervisor/Admin only).
    """
    orchestrator = AgentOrchestrator()
    try:
        updated_run = orchestrator.apply_human_decision(
            run_id=run_id,
            decision=req.decision,
            notes=req.notes,
            reviewer=req.reviewer or current_user.full_name or "Human Examiner",
            db=db,
        )
        return AgentRunResponse(
            run_id=updated_run.id,
            finding_id=updated_run.finding_id,
            entity_id=updated_run.entity_id or "",
            state=updated_run.state,
            mode=updated_run.mode,
            assessment_result=updated_run.assessment_result or {},
            challenge_result=updated_run.challenge_result or {},
            planner_result=updated_run.planner_result or {},
            human_decision=updated_run.human_decision,
            human_notes=updated_run.human_notes,
            created_at=updated_run.created_at,
            updated_at=updated_run.updated_at,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# MODULE 9 — AUDIT & REPLAY ENDPOINTS
# =========================================================================

@protected_router.get("/audit/events", response_model=List[schemas.AuditEventResponse])
def get_audit_events(
    entity_id: Optional[str] = None,
    analysis_id: Optional[str] = None,
    finding_id: Optional[str] = None,
    event_type: Optional[str] = None,
    actor_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    order: str = "asc",
    db: Session = Depends(get_db),
):
    """
    Retrieve cryptographically chained audit events filtered by entity, analysis, finding, or actor.
    """
    svc = AuditService()
    events = svc.get_events(
        db=db,
        entity_id=entity_id,
        analysis_id=analysis_id,
        finding_id=finding_id,
        event_type=event_type,
        actor_type=actor_type,
        limit=limit,
        offset=offset,
        order=order,
    )
    return events


@protected_router.get("/audit/analysis/{analysis_id}", response_model=List[schemas.AuditEventResponse])
def get_analysis_audit_events(analysis_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the full chronological audit event trail for an assessment/analysis run.
    """
    svc = AuditService()
    events = svc.get_analysis_events(db=db, analysis_id=analysis_id)
    return events


@protected_router.get("/audit/integrity/{analysis_id}", response_model=schemas.AuditIntegrityResponse)
def verify_audit_integrity(analysis_id: str, db: Session = Depends(get_db)):
    """
    Verifies cryptographic hash-chain integrity for all events in an analysis stream.
    Validates previous-hash links and recomputed SHA-256 signatures.
    """
    svc = AuditService()
    events = svc.get_analysis_events(db=db, analysis_id=analysis_id)
    verification = svc.verify_chain(events)
    entity_id = events[0].entity_id if events else None
    return schemas.AuditIntegrityResponse(
        analysis_id=analysis_id,
        entity_id=entity_id,
        valid=verification["valid"],
        total_events=verification["total_events"],
        broken_at_index=verification["broken_at_index"],
        broken_event_id=verification["broken_event_id"],
        error=verification["error"],
        chain_hashes=verification["chain_hashes"],
    )


@protected_router.post("/audit/replay/{analysis_id}", response_model=schemas.AuditReplayResponse)
def replay_analysis(
    analysis_id: str,
    entity_id: Optional[str] = None,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Executes offline deterministic replay of the supervisory assessment state (Supervisor/Admin only).
    """
    engine = ReplayEngine()
    result = engine.replay_analysis(db=db, analysis_id=analysis_id, entity_id=entity_id)
    return schemas.AuditReplayResponse(**result)


@protected_router.get("/audit/finding/{finding_id}", response_model=List[schemas.AuditEventResponse])
def get_finding_audit_events(finding_id: str, db: Session = Depends(get_db)):
    """
    Retrieve all audit events directly or indirectly tied to a specific finding.
    """
    svc = AuditService()
    events = svc.get_events(db=db, finding_id=finding_id, order="asc")
    return events


@protected_router.post("/audit/snapshots/{entity_id}", response_model=schemas.AssessmentSnapshotResponse)
def create_assessment_snapshot(
    entity_id: str,
    analysis_id: Optional[str] = None,
    current_user: domain.User = Depends(require_role([UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])),
    db: Session = Depends(get_db),
):
    """
    Generates a cryptographically signed, immutable snapshot of the entity's current assessment state (Supervisor/Admin only).
    """
    svc = AuditService()
    snapshot = svc.create_snapshot(db=db, entity_id=entity_id, analysis_id=analysis_id)
    return snapshot
