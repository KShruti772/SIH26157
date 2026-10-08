from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import time
import uuid
import asyncio

from app.database import get_db
from app.models import domain
from app.schemas import api as schemas

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.post("/auth/login")
def login(req: LoginRequest):
    if req.username and req.password:
        return {"token": "demo-token", "role": "Supervisor", "name": "Admin User"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# Mock storage for upload and analysis states
upload_store = {}
analysis_store = {}

@router.post("/upload")
def upload_data(file: UploadFile = File(...)):
    # Simulate processing
    upload_id = str(uuid.uuid4())
    upload_store[upload_id] = {
        "status": "completed",
        "filename": file.filename,
        "records": 10500,
        "entities_detected": 10
    }
    return {"upload_id": upload_id, "status": "completed", "details": upload_store[upload_id]}

@router.get("/upload/{id}/preview")
def preview_data(id: str, db: Session = Depends(get_db)):
    # Return some mock or database alerts
    alerts = db.query(domain.Alert).limit(50).all()
    return {"data": alerts}

async def run_analysis_task(analysis_id: str, db: Session):
    # Simulate step by step analysis
    stages = [
        "Data validation", "Data normalization", "Entity profiling",
        "Alert analysis", "Case analysis", "Execution gap analysis",
        "Negative-space analysis", "Anomaly detection", "Peer benchmarking",
        "Risk calculation", "Review prioritization"
    ]
    for i, stage in enumerate(stages):
        await asyncio.sleep(1) # simulate work
        analysis_store[analysis_id] = {
            "status": "processing",
            "progress": int(((i + 1) / len(stages)) * 100),
            "current_stage": stage
        }
    analysis_store[analysis_id]["status"] = "completed"

@router.post("/analysis/run")
def run_analysis(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    analysis_id = str(uuid.uuid4())
    analysis_store[analysis_id] = {"status": "started", "progress": 0, "current_stage": "Initializing"}
    background_tasks.add_task(run_analysis_task, analysis_id, db)
    return {"analysis_id": analysis_id}

@router.get("/analysis/{id}/status")
def get_analysis_status(id: str):
    if id not in analysis_store:
        raise HTTPException(status_code=404, detail="Not found")
    return analysis_store[id]

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    entities_count = db.query(domain.Entity).count()
    findings_count = db.query(domain.Finding).count()
    high_risk_entities = db.query(domain.RiskScore).filter(domain.RiskScore.overall_score >= 51).count()
    reviews_pending = db.query(domain.ReviewItem).filter(domain.ReviewItem.status == "Pending").count()
    
    return {
        "entities_analyzed": entities_count,
        "findings_generated": findings_count,
        "high_risk_entities": high_risk_entities,
        "priority_reviews": reviews_pending
    }

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

@router.get("/findings", response_model=List[schemas.FindingBase])
def get_findings(category: str = None, db: Session = Depends(get_db)):
    q = db.query(domain.Finding)
    if category:
        q = q.filter(domain.Finding.category == category)
    return q.all()

@router.get("/findings/{id}")
def get_finding(id: str, db: Session = Depends(get_db)):
    finding = db.query(domain.Finding).filter(domain.Finding.id == id).first()
    if not finding:
        raise HTTPException(status_code=404)
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
def get_benchmarks(db: Session = Depends(get_db)):
    return db.query(domain.Benchmark).all()

@router.get("/risk/{entity_id}", response_model=schemas.RiskScoreBase)
def get_risk(entity_id: str, db: Session = Depends(get_db)):
    risk = db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == entity_id).first()
    if not risk:
        raise HTTPException(status_code=404)
    return risk

@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db)):
    items = db.query(domain.ReviewItem).all()
    res = []
    for item in items:
        finding = db.query(domain.Finding).filter(domain.Finding.id == item.finding_id).first()
        res.append({"review_item": item, "finding": finding})
    return res

class ReviewUpdate(BaseModel):
    status: str
    reviewer: str = None

@router.patch("/review-queue/{id}")
def update_review(id: int, req: ReviewUpdate, db: Session = Depends(get_db)):
    item = db.query(domain.ReviewItem).filter(domain.ReviewItem.id == id).first()
    if not item:
        raise HTTPException(status_code=404)
    item.status = req.status
    if req.reviewer:
        item.reviewer = req.reviewer
    db.commit()
    return item

@router.get("/evidence/{finding_id}")
def get_evidence(finding_id: str, db: Session = Depends(get_db)):
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404)
    evidence_ids = finding.evidence_ids or []
    # return alerts and cases based on evidence ids
    alerts = db.query(domain.Alert).filter(domain.Alert.id.in_(evidence_ids)).all()
    cases = db.query(domain.Case).filter(domain.Case.id.in_(evidence_ids)).all()
    return {"finding": finding, "alerts": alerts, "cases": cases}

@router.post("/reports/generate")
def generate_report():
    report_id = str(uuid.uuid4())
    return {"report_id": report_id, "status": "generated"}

@router.get("/reports")
def get_reports():
    return [{"id": "rpt-1", "date": "2026-10-08", "name": "Supervisory Report 1"}]

@router.get("/audit")
def get_audit(db: Session = Depends(get_db)):
    return db.query(domain.AuditLog).order_by(domain.AuditLog.timestamp.desc()).limit(100).all()
