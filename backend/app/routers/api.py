from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import time
import json
import uuid
import asyncio

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

import re
from app.services import auth as auth_service
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
    UserRole,
    ALLOWED_SELF_REGISTER_ROLES,
)

router = APIRouter()

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024 # 100 MB max for prototype upload
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/auth/register", response_model=schemas.AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: schemas.UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new user account (SUPERVISOR or REVIEWER).
    ADMINISTRATOR self-registration is strictly disallowed.
    """
    email_clean = (req.email or "").strip().lower()
    full_name_clean = (req.full_name or "").strip()
    org_clean = (req.organization or "").strip()
    role_clean = (req.role or "").strip().upper()

    if not full_name_clean:
        raise HTTPException(status_code=400, detail="Full name is required.")

    if not org_clean:
        raise HTTPException(status_code=400, detail="Organization is required.")

    if not email_clean or not EMAIL_REGEX.match(email_clean):
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    if role_clean == UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=403,
            detail="Administrator accounts cannot be self-registered. Contact system administration.",
        )

    if role_clean not in ALLOWED_SELF_REGISTER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{req.role}'. Allowed self-registration roles: {', '.join(ALLOWED_SELF_REGISTER_ROLES)}",
        )

    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    # Check for existing email
    existing = db.query(domain.User).filter(domain.User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email address already exists.")

    user_id = f"USR-{uuid.uuid4().hex[:10].upper()}"
    pwd_hash = hash_password(req.password)

    new_user = domain.User(
        id=user_id,
        full_name=full_name_clean,
        email=email_clean,
        password_hash=pwd_hash,
        organization=org_clean,
        role=role_clean,
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
                "role": role_clean,
            },
        )
    except Exception:
        pass

    token = create_access_token(new_user)
    return schemas.AuthTokenResponse(
        token=token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(new_user),
        role=new_user.role,
        name=new_user.full_name,
    )


@router.post("/auth/login", response_model=schemas.AuthTokenResponse)
def login_user(req: schemas.UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates a user via email and password, issuing a signed JWT token.
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
        except Exception:
            pass
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
    except Exception:
        pass

    token = create_access_token(user)
    return schemas.AuthTokenResponse(
        token=token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(user),
        role=user.role,
        name=user.full_name,
    )


@router.get("/auth/me", response_model=schemas.UserResponse)
def get_current_user_profile(
    current_user: domain.User = Depends(get_current_user),
):
    """
    Retrieves the currently authenticated user profile from validated JWT session.
    """
    return schemas.UserResponse.model_validate(current_user)


@router.post("/auth/logout")
def logout_user(
    current_user: domain.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Logs out the authenticated user and records USER_LOGOUT audit event.
    """
    try:
        audit_svc = AuditService()
        audit_svc.record_event(
            db=db,
            event_type=EventType.USER_LOGOUT,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=current_user.id,
            payload={"user_id": current_user.id, "email": current_user.email},
        )
    except Exception:
        pass
    return {"status": "ok", "message": "Successfully logged out."}

# In-memory storage for active analysis tracking
analysis_store = {}

@router.post("/upload", response_model=schemas.UploadResponse)
async def upload_data(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Real ingestion endpoint:
    - Reads and validates file payload
    - Safe CSV/JSON parsing
    - Schema detection & field mapping
    - Normalization & data quality profiling
    - Cryptographic source integrity hashing (SHA-256)
    - Database insertion into SQLite
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    fn = file.filename.lower()
    allowed_exts = (".csv", ".tsv", ".txt", ".json", ".jsonl")
    if not any(fn.endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported extensions are: {', '.join(allowed_exts)}"
        )

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB"
        )

    try:
        upload_record = ingestion.process_uploaded_file(content, file.filename, db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion processing error: {str(e)}"
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
        columns_detected=upload_record.columns_detected or [],
        quality=upload_record.quality_report or {},
        error_details=upload_record.error_details or [],
        entities_detected=upload_record.entity_ids or [],
        date_range_start=upload_record.date_range_start.isoformat() if upload_record.date_range_start else None,
        date_range_end=upload_record.date_range_end.isoformat() if upload_record.date_range_end else None,
        source_hash=upload_record.source_hash,
    )

@router.get("/uploads", response_model=List[schemas.DatasetUploadBase])
def get_uploads(db: Session = Depends(get_db)):
    """List all historical dataset submissions."""
    return db.query(domain.DatasetUpload).order_by(domain.DatasetUpload.uploaded_at.desc()).all()

@router.get("/upload/{id}/preview", response_model=schemas.DataPreviewResponse)
def preview_data(id: str, db: Session = Depends(get_db)):
    """Fetch real records belonging specifically to the requested upload."""
    preview = ingestion.get_upload_preview_data(id, db, limit=50)
    if not preview:
        raise HTTPException(status_code=404, detail=f"Upload '{id}' not found")
    return schemas.DataPreviewResponse(**preview)

def run_analysis_task(analysis_id: str, upload_id: Optional[str] = None, entity_ids: Optional[List[str]] = None):
    """
    Executes real supervisory analytics engine across ingested datasets.
    """
    db = SessionLocal()
    try:
        def cb(stage: str, desc: str, pct: int):
            analysis_store[analysis_id] = {
                "status": "processing" if pct < 100 else "completed",
                "progress": pct,
                "current_stage": stage,
                "description": desc,
                "upload_id": upload_id,
            }

        engine = SupervisoryAnalyticsEngine()
        summary = engine.run(
            db=db,
            analysis_id=analysis_id,
            upload_id=upload_id,
            entity_ids=entity_ids,
            progress_callback=cb,
        )
        if analysis_id in analysis_store:
            analysis_store[analysis_id]["summary"] = summary
            analysis_store[analysis_id]["status"] = "completed"
            analysis_store[analysis_id]["progress"] = 100
    except Exception as e:
        analysis_store[analysis_id] = {
            "status": "failed",
            "progress": 100,
            "current_stage": "failed",
            "description": f"Analysis execution failed: {str(e)}",
            "error": str(e),
        }
    finally:
        db.close()

@router.post("/analysis/run")
def run_analysis(
    req: Optional[schemas.AnalysisRunRequest] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    analysis_id = str(uuid.uuid4())
    upload_id = req.upload_id if req else None
    entity_ids = req.entity_ids if req else None

    analysis_store[analysis_id] = {
        "status": "started",
        "progress": 0,
        "current_stage": "loading_data",
        "description": "Preparing supervisory assessment pipeline",
        "upload_id": upload_id,
    }
    if background_tasks:
        background_tasks.add_task(run_analysis_task, analysis_id, upload_id, entity_ids)
    else:
        run_analysis_task(analysis_id, upload_id, entity_ids)
    return {"analysis_id": analysis_id, "status": "started"}

@router.get("/analysis/{id}/status")
def get_analysis_status(id: str):
    if id not in analysis_store:
        raise HTTPException(status_code=404, detail="Analysis session not found")
    return analysis_store[id]

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Consolidated Supervisory Assessment Dashboard summary."""
    data = reporting.get_dashboard_summary_data(db)
    # Maintain top-level fields for backwards compatibility
    data["entities_analyzed"] = data["entities_count"]
    data["findings_generated"] = data["findings_count"]
    return data

@router.get("/dashboard/summary", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Full structured supervisory assessment dashboard response."""
    return reporting.get_dashboard_summary_data(db)

@router.get("/entities", response_model=List[schemas.EntityBase])
def get_entities(db: Session = Depends(get_db)):
    return db.query(domain.Entity).all()

@router.get("/entities/{id}")
def get_entity(id: str, db: Session = Depends(get_db)):
    entity = db.query(domain.Entity).filter(domain.Entity.id == id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    risk = db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == id).first()
    return {"entity": entity, "risk": risk}

@router.get("/entities/{id}/assessment", response_model=schemas.EntityAssessmentResponse)
def get_entity_assessment(id: str, db: Session = Depends(get_db)):
    """Comprehensive entity-level supervisory capability and assurance assessment."""
    try:
        return reporting.get_entity_assessment_data(db, entity_id=id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate entity assessment: {str(e)}")


@router.get("/findings", response_model=List[schemas.FindingBase])
def get_findings(
    category: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity: Optional[str] = None,
    severity: Optional[str] = None,
    upload_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(domain.Finding)
    if category:
        q = q.filter(domain.Finding.category == category)
    target_entity = entity_id or entity
    if target_entity:
        q = q.filter(domain.Finding.entity_id == target_entity)
    if severity:
        q = q.filter(domain.Finding.severity == severity.upper())
    if upload_id:
        q = q.filter(domain.Finding.upload_id == upload_id)
    return q.order_by(domain.Finding.risk_contribution.desc()).all()

@router.get("/findings/{id}")
def get_finding(id: str, db: Session = Depends(get_db)):
    finding = db.query(domain.Finding).filter(domain.Finding.id == id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding

@router.get("/execution-gaps")
def get_execution_gaps(db: Session = Depends(get_db)):
    return db.query(domain.Finding).filter(domain.Finding.category == "execution_gap").all()

@router.get("/negative-space")
def get_negative_space(db: Session = Depends(get_db)):
    return db.query(domain.Finding).filter(domain.Finding.category == "negative_space").all()

@router.get("/anomalies")
def get_anomalies(db: Session = Depends(get_db)):
    return db.query(domain.Finding).filter(domain.Finding.category == "anomaly").all()

@router.get("/benchmarks")
def get_benchmarks(entity_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(domain.Benchmark)
    if entity_id:
        q = q.filter(domain.Benchmark.entity_id == entity_id)
    return q.all()

@router.get("/risk/{entity_id}", response_model=schemas.RiskScoreBase)
def get_risk(entity_id: str, db: Session = Depends(get_db)):
    risk = db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == entity_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk record not found")
    return risk

@router.get("/review-queue")
def get_review_queue(
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    validity: Optional[str] = None,
    decision_status: Optional[str] = None,
    agent_status: Optional[str] = None,
    sort_by: str = "priority",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    """
    Enhanced Priority Manual Review Queue with rich multi-parameter filtering,
    sorting, evidence completeness, validity classification, and 'why review' rationale.
    """
    return workspace.get_enhanced_review_queue_items(
        db=db,
        entity_id=entity_id,
        severity=severity,
        category=category,
        validity=validity,
        decision_status=decision_status,
        agent_status=agent_status,
        sort_by=sort_by,
        order=order,
    )

class ReviewUpdate(BaseModel):
    status: str
    reviewer: Optional[str] = None

@router.patch("/review-queue/{id}")
def update_review(id: int, req: ReviewUpdate, db: Session = Depends(get_db)):
    item = db.query(domain.ReviewItem).filter(domain.ReviewItem.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.status = req.status
    if req.reviewer:
        item.reviewer = req.reviewer
    db.commit()
    return item

@router.get("/evidence/{finding_id}")
def get_evidence(finding_id: str, db: Session = Depends(get_db)):
    trace_data = evidence.get_evidence_trace(finding_id, db)
    if not trace_data or not trace_data.get("finding"):
        raise HTTPException(status_code=404, detail="Finding not found")
    return trace_data

# =========================================================================
# MODULE 7 — HUMAN EXAMINER WORKSPACE API ENDPOINTS
# =========================================================================

@router.post("/findings/{finding_id}/decision")
def submit_finding_human_decision(
    finding_id: str,
    req: schemas.FindingDecisionCreate,
    db: Session = Depends(get_db),
):
    """
    Human examiner formal adjudication endpoint:
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
            reviewer=req.reviewer or "Human Examiner",
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


@router.post("/findings/{finding_id}/evidence-requests", response_model=schemas.EvidenceRequestBase)
def create_finding_evidence_request(
    finding_id: str,
    req: schemas.EvidenceRequestCreate,
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
            requested_by=req.requested_by or "Human Examiner",
            db=db,
            description=req.description,
            priority=req.priority or "HIGH",
        )
        return ev_req
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create evidence request: {str(e)}")


@router.get("/findings/{finding_id}/evidence-requests", response_model=List[schemas.EvidenceRequestBase])
def get_finding_evidence_requests(
    finding_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all evidence requests created for a finding."""
    return db.query(domain.EvidenceRequest).filter(
        domain.EvidenceRequest.finding_id == finding_id
    ).order_by(domain.EvidenceRequest.requested_at.desc()).all()


@router.patch("/evidence-requests/{request_id}", response_model=schemas.EvidenceRequestBase)
def update_evidence_request(
    request_id: str,
    req: schemas.EvidenceRequestUpdate,
    db: Session = Depends(get_db),
):
    """Update status of an existing evidence request (RECEIVED, RESOLVED, CANCELLED)."""
    try:
        updated = workspace.update_evidence_request_status(
            request_id=request_id,
            status=req.status,
            response_notes=req.response_notes,
            reviewer="Human Examiner",
            db=db,
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update evidence request: {str(e)}")


@router.get("/findings/{finding_id}/history", response_model=List[schemas.FindingTimelineItem])
def get_finding_history(
    finding_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve unified chronological audit and decision timeline for a finding:
    Detection -> Assurance -> Agent Reasoning -> Evidence Requests -> Human Decisions.
    """
    try:
        history = workspace.get_finding_unified_history(finding_id=finding_id, db=db)
        return history
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assemble finding history: {str(e)}")


class ReportGenerateRequest(BaseModel):
    analysis_id: Optional[str] = None
    entity_id: Optional[str] = None

@router.get("/reports")
def get_reports(db: Session = Depends(get_db)):
    """List available entities and submission analyses available for report compilation."""
    entities = db.query(domain.Entity).all()
    uploads = db.query(domain.DatasetUpload).order_by(domain.DatasetUpload.uploaded_at.desc()).all()
    
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

@router.post("/reports/generate")
def generate_report(
    req: Optional[ReportGenerateRequest] = None,
    db: Session = Depends(get_db),
):
    """Compile a complete, evidence-grounded supervisory report."""
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

@router.get("/reports/{analysis_id}", response_model=schemas.SupervisoryReport)
def get_report_by_analysis(analysis_id: str, db: Session = Depends(get_db)):
    """Fetch full structured supervisory assessment report by analysis ID or entity ID."""
    try:
        # Check if analysis_id is entity_id
        is_entity = db.query(domain.Entity).filter(domain.Entity.id == analysis_id).first()
        if is_entity:
            return reporting.generate_supervisory_report_data(db=db, entity_id=analysis_id)
        return reporting.generate_supervisory_report_data(db=db, analysis_id=analysis_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.get("/reports/entity/{entity_id}", response_model=schemas.SupervisoryReport)
def get_report_by_entity(entity_id: str, db: Session = Depends(get_db)):
    """Fetch full structured supervisory assessment report for a specific entity."""
    try:
        return reporting.generate_supervisory_report_data(db=db, entity_id=entity_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate entity report: {str(e)}")

@router.get("/reports/{analysis_id}/json")
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

@router.get("/reports/{analysis_id}/pdf")
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

@router.get("/reports/entity/{entity_id}/pdf")
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


@router.get("/audit")
def get_audit(db: Session = Depends(get_db)):
    return db.query(domain.AuditLog).order_by(domain.AuditLog.timestamp.desc()).limit(100).all()

# =========================================================================
# MODULE 5 — ASSESSMENT ASSURANCE API ENDPOINTS
# =========================================================================

@router.get("/assurance/{analysis_id}", response_model=schemas.AssessmentAssuranceBase)
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
        # Check if analysis_id is a finding ID
        finding = db.query(domain.Finding).filter(domain.Finding.id == analysis_id).first()
        if finding:
            rec = db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.entity_id == finding.entity_id).first()

    if not rec:
        # Evaluate dynamically for entity/upload if not yet persisted
        svc = AssessmentAssuranceService()
        rec = svc.evaluate_assurance(db=db, analysis_id=analysis_id)

    return rec

@router.get("/assurance/entity/{entity_id}", response_model=schemas.AssessmentAssuranceBase)
def get_entity_assurance(entity_id: str, db: Session = Depends(get_db)):
    """Retrieve latest assessment assurance profile for an entity."""
    rec = db.query(domain.AssessmentAssurance).filter(
        domain.AssessmentAssurance.entity_id == entity_id
    ).order_by(domain.AssessmentAssurance.created_at.desc()).first()

    if not rec:
        svc = AssessmentAssuranceService()
        rec = svc.evaluate_assurance(db=db, entity_id=entity_id)

    return rec

@router.get("/assurance/{analysis_id}/blind-spots")
def get_assurance_blind_spots(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieve structured evidence blind spots."""
    rec = get_assurance(analysis_id, db)
    return {"analysis_id": analysis_id, "blind_spots": rec.blind_spots or []}

@router.get("/assurance/{analysis_id}/contradictions")
def get_assurance_contradictions(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieve evidence contradiction and inconsistency records."""
    rec = get_assurance(analysis_id, db)
    return {"analysis_id": analysis_id, "contradictions": rec.contradiction_details or {}}

@router.get("/uploads/{upload_id}/integrity")
def get_upload_integrity(upload_id: str, db: Session = Depends(get_db)):
    """Verify cryptographic source hash integrity for an uploaded dataset submission."""
    upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload record not found")
    return hashing.verify_upload_integrity(upload)


# =========================================================================
# MODULE 6 — LOCAL AGENTIC AI (SUPERVISORY REASONING) API ENDPOINTS
# =========================================================================

@router.post("/agents/analyze/{finding_id}", response_model=HumanReviewPackage)
def trigger_agent_analysis(
    finding_id: str,
    force_fallback: bool = False,
    db: Session = Depends(get_db),
):
    """
    Execute 3-Agent supervisory reasoning pipeline (Assessment -> Challenge -> Investigation Planner)
    for a specific finding. Generates and returns the consolidated HumanReviewPackage.
    State stops at 'HUMAN_REVIEW_REQUIRED'.
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


@router.get("/agents/{run_id}", response_model=AgentRunResponse)
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


@router.get("/agents/{run_id}/result", response_model=HumanReviewPackage)
def get_agent_result(run_id: str, db: Session = Depends(get_db)):
    """Retrieve the full structured HumanReviewPackage for a completed agent run."""
    agent_run = db.query(domain.AgentRun).filter(domain.AgentRun.id == run_id).first()
    if not agent_run:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found")
    return AgentOrchestrator.to_human_review_package(agent_run)


@router.get("/agents/{run_id}/audit", response_model=List[AgentAuditLogResponse])
def get_agent_audit_trail(run_id: str, db: Session = Depends(get_db)):
    """Retrieve machine-readable audit logs for all steps in an agent run."""
    logs = db.query(domain.AgentAuditLog).filter(domain.AgentAuditLog.run_id == run_id).order_by(domain.AgentAuditLog.timestamp.asc()).all()
    return logs


@router.get("/agents/finding/{finding_id}/latest", response_model=Optional[HumanReviewPackage])
def get_latest_finding_agent_review(finding_id: str, db: Session = Depends(get_db)):
    """Retrieve the most recent agent review package for a finding, if one exists."""
    agent_run = db.query(domain.AgentRun).filter(
        domain.AgentRun.finding_id == finding_id
    ).order_by(domain.AgentRun.created_at.desc()).first()

    if not agent_run:
        return None
    return AgentOrchestrator.to_human_review_package(agent_run)


@router.post("/agents/{run_id}/decision", response_model=AgentRunResponse)
def submit_human_decision(
    run_id: str,
    req: HumanDecisionRequest,
    db: Session = Depends(get_db),
):
    """
    Human examiner submits final supervisory decision (CONFIRMED, REJECTED, MODIFY, REQUEST_EVIDENCE).
    Updates state to COMPLETED and logs human adjudication audit record.
    """
    orchestrator = AgentOrchestrator()
    try:
        updated_run = orchestrator.apply_human_decision(
            run_id=run_id,
            decision=req.decision,
            notes=req.notes,
            reviewer=req.reviewer or "Human Examiner",
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

@router.get("/audit/events", response_model=List[schemas.AuditEventResponse])
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


@router.get("/audit/analysis/{analysis_id}", response_model=List[schemas.AuditEventResponse])
def get_analysis_audit_events(analysis_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the full chronological audit event trail for an assessment/analysis run.
    """
    svc = AuditService()
    events = svc.get_analysis_events(db=db, analysis_id=analysis_id)
    return events


@router.get("/audit/integrity/{analysis_id}", response_model=schemas.AuditIntegrityResponse)
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


@router.post("/audit/replay/{analysis_id}", response_model=schemas.AuditReplayResponse)
def replay_analysis(
    analysis_id: str,
    entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Executes offline deterministic replay of the supervisory assessment state.
    Reconstructs findings, assurance, decisions, and capabilities from the audit stream
    and validates state equality against persisted records.
    """
    engine = ReplayEngine()
    result = engine.replay_analysis(db=db, analysis_id=analysis_id, entity_id=entity_id)
    return schemas.AuditReplayResponse(**result)


@router.get("/audit/finding/{finding_id}", response_model=List[schemas.AuditEventResponse])
def get_finding_audit_events(finding_id: str, db: Session = Depends(get_db)):
    """
    Retrieve all audit events directly or indirectly tied to a specific finding.
    """
    svc = AuditService()
    events = svc.get_events(db=db, finding_id=finding_id, order="asc")
    return events


@router.post("/audit/snapshots/{entity_id}", response_model=schemas.AssessmentSnapshotResponse)
def create_assessment_snapshot(
    entity_id: str,
    analysis_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Generates a cryptographically signed, immutable snapshot of the entity's current assessment state.
    """
    svc = AuditService()
    snapshot = svc.create_snapshot(db=db, entity_id=entity_id, analysis_id=analysis_id)
    return snapshot


