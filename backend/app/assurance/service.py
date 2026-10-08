import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import domain
from app.assurance.coverage import (
    evaluate_population_exposure,
    evaluate_temporal_coverage,
    evaluate_severity_coverage,
    evaluate_asset_coverage,
    evaluate_process_coverage,
)
from app.assurance.contradictions import detect_evidence_contradictions
from app.assurance.dependencies import evaluate_evidence_dependencies
from app.assurance.blind_spots import detect_evidence_blind_spots
from app.assurance.validity import synthesize_assessment_validity
from app.assurance.hashing import verify_upload_integrity


class AssessmentAssuranceService:
    """
    Core service evaluating Assessment Assurance (Module 5).
    Maintains the critical distinction: FINDING CONFIDENCE != ASSESSMENT VALIDITY.
    """

    def evaluate_assurance(
        self,
        db: Session,
        analysis_id: Optional[str] = None,
        upload_id: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> domain.AssessmentAssurance:
        """
        Evaluate and persist the comprehensive assessment assurance profile.
        """
        # 1. Fetch relevant upload & operational records
        upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == upload_id).first() if upload_id else None

        alerts_query = db.query(domain.Alert)
        cases_query = db.query(domain.Case)
        assets_query = db.query(domain.Asset)
        findings_query = db.query(domain.Finding)

        if upload_id:
            alerts_query = alerts_query.filter(domain.Alert.upload_id == upload_id)
            cases_query = cases_query.filter(domain.Case.upload_id == upload_id)
            assets_query = assets_query.filter(domain.Asset.upload_id == upload_id)
            findings_query = findings_query.filter(domain.Finding.upload_id == upload_id)
        elif entity_id:
            alerts_query = alerts_query.filter(domain.Alert.entity_id == entity_id)
            cases_query = cases_query.filter(domain.Case.entity_id == entity_id)
            assets_query = assets_query.filter(domain.Asset.entity_id == entity_id)
            findings_query = findings_query.filter(domain.Finding.entity_id == entity_id)

        alerts = alerts_query.all()
        cases = cases_query.all()
        assets = assets_query.all()
        findings = findings_query.all()

        total_records = len(alerts) + len(cases) + len(assets)

        # 2. Evaluate Population Exposure
        declared_pop = upload.declared_population if upload else None
        pop_exposure = evaluate_population_exposure(
            declared_population=declared_pop,
            observable_counts={"alerts": len(alerts), "cases": len(cases), "assets": len(assets)},
        )

        # 3. Evaluate Multidimensional Coverage
        dt_start = upload.date_range_start if upload else (min([a.timestamp for a in alerts if a.timestamp], default=None))
        dt_end = upload.date_range_end if upload else (max([a.timestamp for a in alerts if a.timestamp], default=None))

        temp_coverage = evaluate_temporal_coverage(dt_start, dt_end)
        sev_coverage = evaluate_severity_coverage(alerts)
        asset_coverage = evaluate_asset_coverage(assets, alerts)
        proc_coverage = evaluate_process_coverage(alerts, cases)

        coverage_details = {
            "temporal": temp_coverage,
            "severity": sev_coverage,
            "asset": asset_coverage,
            "process": proc_coverage,
        }

        # 4. Detect Evidence Contradictions
        contradiction_details = detect_evidence_contradictions(alerts, cases, assets)

        # 5. Evaluate Evidence Dependencies
        dependency_details = evaluate_evidence_dependencies(findings)

        # 6. Detect Blind Spots
        blind_spots = detect_evidence_blind_spots(coverage_details, alerts, assets, cases)

        # 7. Check Source Hash & Integrity
        integrity = verify_upload_integrity(upload)

        # 8. Synthesize Overall Assessment Validity
        validity_profile = synthesize_assessment_validity(
            population_exposure=pop_exposure,
            coverage_details=coverage_details,
            contradiction_details=contradiction_details,
            dependency_details=dependency_details,
            blind_spots=blind_spots,
            total_records=total_records,
        )

        overall_status = validity_profile["overall_status"]
        limitations = validity_profile["limitations"]
        supervisory_interpretation = validity_profile["supervisory_interpretation"]

        # 9. Update Findings with Assessment Validity Status
        for f in findings:
            f.assessment_validity = overall_status
            f.validity_rationale = supervisory_interpretation
        db.commit()

        # 10. Persist AssessmentAssurance Record
        # Clean existing assurance for this analysis_id/upload_id
        if analysis_id:
            db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.analysis_id == analysis_id).delete()
        elif upload_id:
            db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.upload_id == upload_id).delete()

        assurance_id = f"ASSURE-{uuid.uuid4().hex[:8].upper()}"
        assurance_record = domain.AssessmentAssurance(
            id=assurance_id,
            analysis_id=analysis_id,
            upload_id=upload_id,
            entity_id=entity_id or (findings[0].entity_id if findings else None),
            overall_status=overall_status,
            finding_confidence="HIGH" if any(f.confidence >= 0.85 for f in findings) else "MEDIUM",
            population_exposure=pop_exposure,
            coverage_details=coverage_details,
            dependency_details=dependency_details,
            contradiction_details=contradiction_details,
            blind_spots=blind_spots,
            limitations=limitations,
            supervisory_interpretation=supervisory_interpretation,
            source_hash=integrity.get("hash"),
            integrity_status=integrity.get("status", "VERIFIED"),
        )
        db.add(assurance_record)
        db.commit()
        db.refresh(assurance_record)

        # Record ASSURANCE_CREATED audit event
        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            target_entity = entity_id or (findings[0].entity_id if findings else "CSE-001")
            audit_svc.record_event(
                db=db,
                event_type=EventType.ASSURANCE_CREATED,
                actor_type=ActorType.ANALYTICS_ENGINE,
                actor_id="AssessmentAssuranceService",
                entity_id=target_entity,
                analysis_id=analysis_id or upload_id,
                payload={
                    "assurance_id": assurance_id,
                    "overall_status": overall_status,
                    "assessment_validity": overall_status,
                    "coverage_details": coverage_details,
                    "blind_spots_count": len(blind_spots),
                    "integrity_status": integrity.get("status", "VERIFIED"),
                },
            )
        except Exception:
            pass

        return assurance_record
