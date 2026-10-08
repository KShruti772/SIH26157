"""
Service managing the Human Examiner Workspace (Module 7).

Coordinates human decisions, evidence requests, modification tracking,
decision history reconstruction, and audit logging.
Strictly ensures:
- The human examiner is the final decision-maker.
- AI cannot autonomously finalize supervisory assessments.
- Source evidence remains immutable.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.models import domain
from app.agents.audit import AgentAuditTracker, compute_object_hash
from app.services.evidence import calculate_evidence_completeness, resolve_evidence_records


VALID_DECISIONS = {"CONFIRM", "REJECT", "MODIFY", "REQUEST_EVIDENCE", "DEFER"}

VALID_REQUEST_TYPES = {
    "CASE_MANAGEMENT_RECORDS",
    "INVESTIGATION_LOGS",
    "ESCALATION_RECORDS",
    "CLOSURE_DISPOSITION_RECORDS",
    "ASSET_INVENTORY",
    "TELEMETRY_COVERAGE",
    "OTHER",
}

VALID_REJECTION_REASONS = {
    "EVIDENCE_DISPROVES_FINDING",
    "NOT_REPRESENTATIVE",
    "EVIDENCE_LIMITATION_INVALIDATES_CONCLUSION",
    "FALSE_POSITIVE",
    "OTHER",
}


def record_human_decision(
    finding_id: str,
    decision: str,
    notes: Optional[str],
    rationale: Optional[str],
    reviewer: str,
    db: Session,
    rejection_reason: Optional[str] = None,
    modified_assessment: Optional[str] = None,
    modified_fields: Optional[Dict[str, Any]] = None,
    agent_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record a formal human examiner decision on a finding.
    Ensures source evidence immutability and complete audit provenance.
    """
    decision_norm = decision.strip().upper()
    if decision_norm not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision '{decision}'. Must be one of: {sorted(list(VALID_DECISIONS))}")

    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise ValueError(f"Finding with ID '{finding_id}' not found.")

    # Validate mandatory notes/reasons
    if decision_norm == "REJECT" and not rejection_reason and not notes:
        raise ValueError("Rejection reason or explanatory notes are mandatory when rejecting a finding.")
    if decision_norm == "MODIFY" and not modified_assessment and not notes:
        raise ValueError("Modified assessment text or explanatory notes are mandatory when modifying an assessment.")

    now = datetime.datetime.utcnow()

    # Update finding state
    if decision_norm == "CONFIRM":
        finding.decision_status = "CONFIRMED"
        finding.status = "Confirmed by Supervisor"
    elif decision_norm == "REJECT":
        finding.decision_status = "REJECTED"
        finding.status = "Rejected by Supervisor"
    elif decision_norm == "MODIFY":
        finding.decision_status = "MODIFIED"
        finding.status = "Modified by Supervisor"
        if modified_assessment:
            finding.modified_assessment = modified_assessment
    elif decision_norm == "DEFER":
        finding.decision_status = "DEFERRED"
        finding.status = "Deferred"
    elif decision_norm == "REQUEST_EVIDENCE":
        finding.decision_status = "EVIDENCE_REQUESTED"
        finding.status = "Evidence Requested"

    finding.adjudicated_by = reviewer
    finding.adjudicated_at = now

    # Update associated ReviewItem if exists
    review_item = db.query(domain.ReviewItem).filter(domain.ReviewItem.finding_id == finding_id).first()
    if review_item:
        if decision_norm == "CONFIRM":
            review_item.status = "Confirmed"
        elif decision_norm == "REJECT":
            review_item.status = "Dismissed"
        elif decision_norm == "MODIFY":
            review_item.status = "Modified"
        elif decision_norm == "DEFER":
            review_item.status = "Deferred"
        review_item.reviewer = reviewer

    # Create immutable FindingDecision record
    decision_rec = domain.FindingDecision(
        finding_id=finding_id,
        decision=decision_norm,
        actor=reviewer,
        timestamp=now,
        notes=notes,
        rationale=rationale,
        rejection_reason=rejection_reason,
        modified_fields=modified_fields or ({"modified_assessment": modified_assessment} if modified_assessment else None),
        evidence_refs=finding.evidence_ids or [],
        agent_run_id=agent_run_id,
    )
    db.add(decision_rec)

    # If an agent run is associated or exists, mark state completed
    agent_run = None
    if agent_run_id:
        agent_run = db.query(domain.AgentRun).filter(domain.AgentRun.id == agent_run_id).first()
    if not agent_run:
        agent_run = db.query(domain.AgentRun).filter(
            domain.AgentRun.finding_id == finding_id
        ).order_by(domain.AgentRun.created_at.desc()).first()

    if agent_run:
        agent_run.human_decision = decision_norm
        agent_run.human_notes = notes
        agent_run.state = "COMPLETED"
        agent_run.updated_at = now

    # Record machine-readable audit entry
    AgentAuditTracker.record_step(
        db=db,
        run_id=agent_run.id if agent_run else f"MANUAL-{uuid.uuid4().hex[:8]}",
        agent_id="human_examiner",
        finding_id=finding_id,
        input_context_hash=None,
        action=f"HUMAN_DECISION_{decision_norm}",
        output_data={
            "decision": decision_norm,
            "reviewer": reviewer,
            "notes": notes,
            "rejection_reason": rejection_reason,
            "modified_assessment": modified_assessment,
        },
        status="SUCCESS",
        model_provider="human",
        model_name=reviewer,
    )

    db.commit()
    db.refresh(finding)
    db.refresh(decision_rec)

    # Record HUMAN_DECISION_CREATED audit event (Module 9)
    try:
        from app.services.audit import AuditService, EventType, ActorType
        audit_svc = AuditService()
        audit_svc.record_event(
            db=db,
            event_type=EventType.HUMAN_DECISION_CREATED,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=reviewer or "Human Examiner",
            entity_id=finding.entity_id,
            analysis_id=finding.upload_id,
            finding_id=finding.id,
            decision_id=str(decision_rec.id),
            agent_run_id=agent_run.id if agent_run else None,
            payload={
                "decision": decision_norm,
                "notes": notes,
                "rationale": rationale,
                "rejection_reason": rejection_reason,
                "modified_assessment": modified_assessment,
                "finding_id": finding.id,
            },
        )
    except Exception:
        pass

    return {
        "finding_id": finding.id,
        "decision": decision_norm,
        "decision_status": finding.decision_status,
        "status": finding.status,
        "adjudicated_by": finding.adjudicated_by,
        "adjudicated_at": finding.adjudicated_at.isoformat() if finding.adjudicated_at else None,
        "decision_id": decision_rec.id,
    }


def create_evidence_request(
    finding_id: str,
    request_type: str,
    reason: str,
    requested_by: str,
    db: Session,
    description: Optional[str] = None,
    priority: str = "HIGH",
) -> domain.EvidenceRequest:
    """
    Create and persist a formal supervisory evidence request.
    """
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise ValueError(f"Finding with ID '{finding_id}' not found.")

    if not reason or not reason.strip():
        raise ValueError("A clear supervisory rationale is required when requesting additional evidence.")

    req_type_norm = request_type.strip().upper().replace(" ", "_")

    req_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.datetime.utcnow()

    req_obj = domain.EvidenceRequest(
        id=req_id,
        finding_id=finding_id,
        analysis_id=finding.upload_id,
        entity_id=finding.entity_id,
        requested_by=requested_by or "Human Examiner",
        requested_at=now,
        request_type=req_type_norm,
        description=description,
        reason=reason,
        priority=priority.upper() if priority else "HIGH",
        status="OPEN",
    )
    db.add(req_obj)

    # Transition finding to EVIDENCE_REQUESTED
    finding.decision_status = "EVIDENCE_REQUESTED"
    finding.status = "Evidence Requested"

    # Record decision history entry
    decision_rec = domain.FindingDecision(
        finding_id=finding_id,
        decision="EVIDENCE_REQUESTED",
        actor=requested_by or "Human Examiner",
        timestamp=now,
        notes=f"Evidence Request {req_id}: {req_type_norm} — {reason}",
        rationale=reason,
        modified_fields={"request_id": req_id, "request_type": req_type_norm},
        evidence_refs=finding.evidence_ids or [],
    )
    db.add(decision_rec)

    # Record audit log
    AgentAuditTracker.record_step(
        db=db,
        run_id=req_id,
        agent_id="human_examiner",
        finding_id=finding_id,
        input_context_hash=None,
        action="CREATE_EVIDENCE_REQUEST",
        output_data={"request_id": req_id, "type": req_type_norm, "reason": reason},
        status="SUCCESS",
        model_provider="human",
        model_name=requested_by or "Human Examiner",
    )

    db.commit()
    db.refresh(req_obj)

    # Record EVIDENCE_REQUEST_CREATED audit event (Module 9)
    try:
        from app.services.audit import AuditService, EventType, ActorType
        audit_svc = AuditService()
        audit_svc.record_event(
            db=db,
            event_type=EventType.EVIDENCE_REQUEST_CREATED,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=requested_by or "Human Examiner",
            entity_id=finding.entity_id,
            analysis_id=finding.upload_id,
            finding_id=finding_id,
            evidence_request_id=req_id,
            payload={
                "request_id": req_id,
                "request_type": req_type_norm,
                "reason": reason,
                "priority": priority.upper() if priority else "HIGH",
                "finding_id": finding_id,
            },
        )
    except Exception:
        pass

    return req_obj


def update_evidence_request_status(
    request_id: str,
    status: str,
    response_notes: Optional[str],
    reviewer: str,
    db: Session,
) -> domain.EvidenceRequest:
    """
    Update status of an evidence request (e.g. RECEIVED, RESOLVED, CANCELLED).
    """
    status_norm = status.strip().upper()
    req_obj = db.query(domain.EvidenceRequest).filter(domain.EvidenceRequest.id == request_id).first()
    if not req_obj:
        raise ValueError(f"Evidence Request with ID '{request_id}' not found.")

    now = datetime.datetime.utcnow()
    req_obj.status = status_norm
    if response_notes:
        req_obj.response_notes = response_notes
    if status_norm in ("RECEIVED", "RESOLVED", "CANCELLED"):
        req_obj.resolved_at = now

    # When received or resolved, transition finding back to UNDER_REVIEW
    finding = db.query(domain.Finding).filter(domain.Finding.id == req_obj.finding_id).first()
    if finding and status_norm in ("RECEIVED", "RESOLVED"):
        finding.decision_status = "UNDER_REVIEW"
        finding.status = "Under Supervisory Review"

    db.commit()
    db.refresh(req_obj)

    # Record EVIDENCE_REQUEST_UPDATED audit event (Module 9)
    try:
        from app.services.audit import AuditService, EventType, ActorType
        audit_svc = AuditService()
        audit_svc.record_event(
            db=db,
            event_type=EventType.EVIDENCE_REQUEST_UPDATED,
            actor_type=ActorType.HUMAN_EXAMINER,
            actor_id=reviewer or "Human Examiner",
            entity_id=req_obj.entity_id,
            analysis_id=req_obj.analysis_id,
            finding_id=req_obj.finding_id,
            evidence_request_id=req_obj.id,
            payload={
                "request_id": req_obj.id,
                "status": status_norm,
                "response_notes": response_notes,
            },
        )
    except Exception:
        pass

    # Record audit log
    AgentAuditTracker.record_step(
        db=db,
        run_id=request_id,
        agent_id="human_examiner",
        finding_id=req_obj.finding_id,
        input_context_hash=None,
        action=f"EVIDENCE_REQUEST_{status_norm}",
        output_data={"request_id": request_id, "status": status_norm, "notes": response_notes},
        status="SUCCESS",
        model_provider="human",
        model_name=reviewer or "Human Examiner",
    )

    db.commit()
    db.refresh(req_obj)
    return req_obj


def get_finding_unified_history(finding_id: str, db: Session) -> List[Dict[str, Any]]:
    """
    Reconstruct unified, chronological audit and decision history for a finding.
    Connects to the cryptographic AuditEvent ledger while maintaining full backwards compatibility.
    """
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise ValueError(f"Finding with ID '{finding_id}' not found.")

    # Check if dedicated AuditEvent records exist for this finding
    audit_evts = db.query(domain.AuditEvent).filter(
        domain.AuditEvent.finding_id == finding_id
    ).order_by(domain.AuditEvent.id.asc()).all()

    if audit_evts:
        timeline: List[Dict[str, Any]] = []
        has_created = False
        for evt in audit_evts:
            if evt.event_type == "FINDING_CREATED":
                has_created = True
            payload = evt.payload_json or {}
            summary = payload.get("notes") or payload.get("reason") or payload.get("hypothesis") or payload.get("type") or f"{evt.event_type} by {evt.actor_id}"
            action = f"{evt.event_type.replace('_', ' ').title()}"
            hist_evt_type = evt.event_type

            if evt.event_type == "FINDING_CREATED":
                action = f"Rule Trigger: {payload.get('analytic_rule') or finding.type}"
                summary = finding.description
                hist_evt_type = "FINDING_CREATED"
            elif evt.event_type == "HUMAN_DECISION_CREATED":
                action = f"Examiner Action: {payload.get('decision')}"
                hist_evt_type = f"HUMAN_DECISION_{payload.get('decision', 'APPLIED')}"
            elif evt.event_type == "EVIDENCE_REQUEST_CREATED":
                action = f"Requested Evidence: {payload.get('request_type')}"
                hist_evt_type = "EVIDENCE_REQUESTED"

            timeline.append({
                "event_id": evt.event_id,
                "timestamp": evt.timestamp,
                "event_type": hist_evt_type,
                "audit_event_type": evt.event_type,
                "actor": evt.actor_id or evt.actor_type,
                "actor_type": evt.actor_type,
                "action": action,
                "status": payload.get("decision") or payload.get("status") or "SUCCESS",
                "summary": summary,
                "details": payload,
                "event_hash": evt.event_hash,
                "previous_event_hash": evt.previous_event_hash,
            })

        if not has_created:
            timeline.insert(0, {
                "event_id": f"EVT-CREATE-{finding.id}",
                "timestamp": finding.created_at or datetime.datetime.utcnow(),
                "event_type": "FINDING_CREATED",
                "actor": "Deterministic Analytics Engine",
                "actor_type": "ANALYTICS_ENGINE",
                "action": f"Rule Trigger: {finding.analytic_rule or finding.type}",
                "status": "INITIAL_DETECTION",
                "summary": finding.description or "Finding created by analytics engine.",
                "details": {
                    "severity": finding.severity,
                    "confidence": finding.confidence,
                    "category": finding.category,
                    "evidence_count": len(finding.evidence_ids or []),
                },
                "event_hash": None,
                "previous_event_hash": None,
            })

        timeline.sort(key=lambda x: x["timestamp"] if isinstance(x["timestamp"], datetime.datetime) else datetime.datetime.min)
        return timeline

    # Fallback to legacy reconstruct if no AuditEvent records exist yet
    timeline = []

    # 1. Finding Created Event
    timeline.append({
        "event_id": f"EVT-CREATE-{finding.id}",
        "timestamp": finding.created_at or datetime.datetime.utcnow(),
        "event_type": "FINDING_CREATED",
        "actor": "Deterministic Analytics Engine",
        "action": f"Rule Trigger: {finding.analytic_rule or finding.type}",
        "status": "INITIAL_DETECTION",
        "summary": finding.description,
        "details": {
            "severity": finding.severity,
            "confidence": finding.confidence,
            "category": finding.category,
            "evidence_count": len(finding.evidence_ids or []),
        },
    })

    # 2. Assurance Evaluation
    assurance = db.query(domain.AssessmentAssurance).filter(
        (domain.AssessmentAssurance.entity_id == finding.entity_id) |
        (domain.AssessmentAssurance.upload_id == finding.upload_id)
    ).order_by(domain.AssessmentAssurance.created_at.asc()).first()

    if assurance:
        timeline.append({
            "event_id": f"EVT-ASSURE-{assurance.id}",
            "timestamp": assurance.created_at or finding.created_at,
            "event_type": "ASSURANCE_EVALUATED",
            "actor": "Assessment Assurance Engine",
            "action": f"Assurance Profile Synthesized: {assurance.overall_status}",
            "status": assurance.overall_status,
            "summary": assurance.supervisory_interpretation or "Assurance dimensions evaluated.",
            "details": {
                "overall_status": assurance.overall_status,
                "integrity_status": assurance.integrity_status,
                "blind_spots_count": len(assurance.blind_spots or []),
            },
        })

    # 3. Agent Runs & Steps
    agent_runs = db.query(domain.AgentRun).filter(domain.AgentRun.finding_id == finding_id).order_by(domain.AgentRun.created_at.asc()).all()
    for ar in agent_runs:
        timeline.append({
            "event_id": f"EVT-AGENT-{ar.id}",
            "timestamp": ar.created_at,
            "event_type": "AGENT_ANALYSIS",
            "actor": f"Local Agentic AI ({ar.mode})",
            "action": f"Supervisory Reasoning Pipeline ({ar.state})",
            "status": ar.state,
            "summary": ar.assessment_result.get("hypothesis") if isinstance(ar.assessment_result, dict) else "Agent reasoning completed.",
            "details": {
                "run_id": ar.id,
                "mode": ar.mode,
                "challenge_status": ar.challenge_result.get("challenge_status") if isinstance(ar.challenge_result, dict) else None,
                "recommended_action": ar.planner_result.get("recommended_action") if isinstance(ar.planner_result, dict) else None,
            },
        })

    # 4. Evidence Requests
    requests = db.query(domain.EvidenceRequest).filter(domain.EvidenceRequest.finding_id == finding_id).order_by(domain.EvidenceRequest.requested_at.asc()).all()
    for req in requests:
        timeline.append({
            "event_id": f"EVT-REQ-{req.id}",
            "timestamp": req.requested_at,
            "event_type": "EVIDENCE_REQUESTED",
            "actor": req.requested_by,
            "action": f"Requested Evidence: {req.request_type}",
            "status": req.status,
            "summary": req.reason,
            "details": {
                "request_id": req.id,
                "priority": req.priority,
                "response_notes": req.response_notes,
                "resolved_at": req.resolved_at.isoformat() if req.resolved_at else None,
            },
        })

    # 5. Human Decisions
    decisions = db.query(domain.FindingDecision).filter(domain.FindingDecision.finding_id == finding_id).order_by(domain.FindingDecision.timestamp.asc()).all()
    for dec in decisions:
        timeline.append({
            "event_id": f"EVT-DEC-{dec.id}",
            "timestamp": dec.timestamp,
            "event_type": f"HUMAN_DECISION_{dec.decision}",
            "actor": dec.actor,
            "action": f"Examiner Action: {dec.decision}",
            "status": dec.decision,
            "summary": dec.notes or dec.rationale or f"Decision {dec.decision} applied.",
            "details": {
                "rejection_reason": dec.rejection_reason,
                "modified_fields": dec.modified_fields,
            },
        })

    # Sort strictly by timestamp ascending
    timeline.sort(key=lambda x: x["timestamp"] if isinstance(x["timestamp"], datetime.datetime) else datetime.datetime.min)
    return timeline


from sqlalchemy import desc, asc, func

def get_enhanced_review_queue_items(
    db: Session,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    validity: Optional[str] = None,
    decision_status: Optional[str] = None,
    agent_status: Optional[str] = None,
    sort_by: str = "priority",
    order: str = "desc",
) -> List[Dict[str, Any]]:
    """
    Retrieve review queue items with rich filtering, sorting, and supervisory 'why review' explanations.
    """
    query = db.query(domain.ReviewItem, domain.Finding).join(
        domain.Finding, domain.ReviewItem.finding_id == domain.Finding.id
    )

    if entity_id:
        query = query.filter(domain.Finding.entity_id == entity_id)
    if severity:
        query = query.filter(func.upper(domain.Finding.severity) == severity.upper())
    if category:
        query = query.filter(domain.Finding.category == category)
    if validity:
        query = query.filter(func.upper(domain.Finding.assessment_validity) == validity.upper())
    if decision_status:
        query = query.filter(func.upper(domain.Finding.decision_status) == decision_status.upper())


    # Sorting
    if sort_by == "priority":
        query = query.order_by(desc(domain.ReviewItem.priority_score) if order == "desc" else asc(domain.ReviewItem.priority_score))
    elif sort_by == "severity":
        query = query.order_by(desc(domain.Finding.severity) if order == "desc" else asc(domain.Finding.severity))
    elif sort_by == "confidence":
        query = query.order_by(desc(domain.Finding.confidence) if order == "desc" else asc(domain.Finding.confidence))
    elif sort_by == "validity":
        query = query.order_by(desc(domain.Finding.assessment_validity) if order == "desc" else asc(domain.Finding.assessment_validity))
    elif sort_by == "created_at":
        query = query.order_by(desc(domain.Finding.created_at) if order == "desc" else asc(domain.Finding.created_at))
    else:
        query = query.order_by(desc(domain.ReviewItem.priority_score))

    rows = query.all()
    results = []

    for review_item, finding in rows:
        # Check Agent Run status
        latest_agent_run = db.query(domain.AgentRun).filter(
            domain.AgentRun.finding_id == finding.id
        ).order_by(domain.AgentRun.created_at.desc()).first()

        agent_state = "NOT_STARTED"
        if latest_agent_run:
            agent_state = "COMPLETED" if latest_agent_run.state == "COMPLETED" else "REQUIRED"

        if agent_status and agent_state != agent_status.upper():
            continue

        # Resolve completeness
        resolved = resolve_evidence_records(finding.evidence_ids or [], db)
        completeness = calculate_evidence_completeness(
            finding.category, resolved.get("alerts", []), resolved.get("cases", []), resolved.get("assets", [])
        )

        # Synthesize Why Review reason
        f_sev = finding.severity or "Medium"
        f_val = finding.assessment_validity or "HIGH"
        if f_sev in ("CRITICAL", "HIGH") and f_val in ("CAUTION", "LOW"):
            why = f"High priority ({f_sev}) finding with {f_val} validity requires human examination of missing process logs."
        elif f_sev in ("CRITICAL", "HIGH"):
            why = f"{f_sev} severity finding requiring Tier-1 examiner validation and supervisor sign-off."
        else:
            why = f"Observed operational pattern for {finding.entity_id} requires routine review."

        results.append({
            "review_item": review_item,
            "finding": finding,
            "evidence_completeness": completeness,
            "agent_review_status": agent_state,
            "decision_status": finding.decision_status or "OPEN",
            "why_review": why,
        })

    return results
