"""
Deterministic bounded context builder for Module 6 — Local Agentic AI.

Assembles strictly bounded, traceable operational context from deterministic
analytics, evidence graph, and assurance profile.
Does NOT send full database tables to the LLM.
"""

import hashlib
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models import domain
from app.services.evidence import resolve_evidence_records, _serialize_model
from app.assurance.service import AssessmentAssuranceService
from app.agents.schemas import AssessmentContext, EvidenceReference


def compute_context_hash(context_dict: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of context dictionary for machine-readable audit."""
    canonical_json = json.dumps(context_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_assessment_context(finding_id: str, db: Session) -> AssessmentContext:
    """
    Build a bounded, traceable AssessmentContext for a specific Finding.
    """
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        raise ValueError(f"Finding with ID '{finding_id}' not found in database.")

    # 1. Resolve supporting evidence records
    raw_evidence_ids = finding.evidence_ids or []
    resolved = resolve_evidence_records(raw_evidence_ids, db)
    alerts = resolved.get("alerts", [])
    cases = resolved.get("cases", [])
    assets = resolved.get("assets", [])

    # If evidence_ids was empty and category is negative_space, fetch entity assets
    if not alerts and not cases and not assets and finding.category == "negative_space":
        assets = db.query(domain.Asset).filter(domain.Asset.entity_id == finding.entity_id).all()

    # 2. Build structured evidence references
    supporting_refs: List[EvidenceReference] = []
    valid_eids: List[str] = list(raw_evidence_ids)

    for ast in assets:
        if ast.id not in valid_eids:
            valid_eids.append(ast.id)
        supporting_refs.append(
            EvidenceReference(
                evidence_id=ast.id,
                source_type="asset",
                source_record_id=ast.id,
                timestamp=None,
                summary=f"Asset {ast.id} ({ast.type or 'Generic'}) - Criticality: {ast.criticality or 'Unspecified'}, Telemetry: {ast.has_telemetry}",
            )
        )

    for a in alerts:
        if a.id not in valid_eids:
            valid_eids.append(a.id)
        supporting_refs.append(
            EvidenceReference(
                evidence_id=a.id,
                source_type="alert",
                source_record_id=a.id,
                timestamp=a.timestamp.isoformat() if a.timestamp else None,
                summary=f"Alert {a.id} ({a.severity} - {a.category}) acknowledged={a.acknowledged}, investigated={a.investigation_started}, escalated={a.escalated}",
            )
        )

    for c in cases:
        if c.id not in valid_eids:
            valid_eids.append(c.id)
        supporting_refs.append(
            EvidenceReference(
                evidence_id=c.id,
                source_type="case",
                source_record_id=c.id,
                timestamp=c.created_at.isoformat() if c.created_at else None,
                summary=f"Case {c.id} (linked alert: {c.alert_id or 'None'}), investigator={c.investigator or 'Unassigned'}, escalation={c.escalation_status}",
            )
        )

    # 3. Retrieve or evaluate AssessmentAssurance profile
    assurance_rec = db.query(domain.AssessmentAssurance).filter(
        (domain.AssessmentAssurance.entity_id == finding.entity_id) |
        (domain.AssessmentAssurance.upload_id == finding.upload_id)
    ).order_by(domain.AssessmentAssurance.created_at.desc()).first()

    if not assurance_rec:
        assurance_svc = AssessmentAssuranceService()
        assurance_rec = assurance_svc.evaluate_assurance(
            db=db,
            upload_id=finding.upload_id,
            entity_id=finding.entity_id,
        )

    coverage = assurance_rec.coverage_details or {}
    contradictions = assurance_rec.contradiction_details.get("contradictions", []) if isinstance(assurance_rec.contradiction_details, dict) else []
    blind_spots = assurance_rec.blind_spots or []
    dependencies = assurance_rec.dependency_details or {}
    limitations = assurance_rec.limitations or []

    # 4. Assembled Finding details
    finding_dict = {
        "id": finding.id,
        "entity_id": finding.entity_id,
        "type": finding.type,
        "category": finding.category,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "assessment_validity": finding.assessment_validity or assurance_rec.overall_status,
        "description": finding.description,
        "rationale": finding.rationale,
        "analytic_rule": finding.analytic_rule,
        "risk_contribution": finding.risk_contribution,
        "recommended_action": finding.recommended_action,
        "details": finding.details or {},
    }

    analytics_dict = {
        "finding_confidence": finding.confidence,
        "assessment_validity": finding.assessment_validity or assurance_rec.overall_status,
        "rule": finding.analytic_rule,
        "observed_metrics": finding.details or {},
    }

    return AssessmentContext(
        analysis_id=assurance_rec.analysis_id,
        entity_id=finding.entity_id,
        finding=finding_dict,
        supporting_evidence=supporting_refs,
        contradictions=contradictions,
        blind_spots=blind_spots,
        coverage=coverage,
        dependencies=dependencies,
        limitations=limitations,
        analytics=analytics_dict,
        valid_evidence_ids=valid_eids,
    )
