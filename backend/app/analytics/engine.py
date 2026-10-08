import logging
from typing import Dict, List, Any, Optional, Callable
from sqlalchemy.orm import Session

from app.models import domain
from app.analytics.execution_gaps import ExecutionGapDetector
from app.analytics.negative_space import NegativeSpaceDetector
from app.analytics.anomalies import AnomalyDetector
from app.analytics.benchmarking import CohortBenchmarker
from app.analytics.risk import RiskScoreCalculator
from app.assurance.service import AssessmentAssuranceService

logger = logging.getLogger("satsa.analytics")


class SupervisoryAnalyticsEngine:
    """
    Core Supervisory Analytics Engine.
    Executes deterministic detection, evidence correlation, anomaly identification,
    cohort benchmarking, multi-factor risk scoring, and assessment assurance profiling.
    """

    def __init__(self):
        self.execution_gap_detector = ExecutionGapDetector()
        self.negative_space_detector = NegativeSpaceDetector()
        self.anomaly_detector = AnomalyDetector()
        self.benchmarker = CohortBenchmarker()
        self.risk_calculator = RiskScoreCalculator()
        self.assurance_service = AssessmentAssuranceService()

    def run(
        self,
        db: Session,
        analysis_id: Optional[str] = None,
        upload_id: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full supervisory analytics pipeline.
        """
        def report(stage: str, desc: str, pct: int):
            if progress_callback:
                progress_callback(stage, desc, pct)

        report("loading_data", "Querying ingested records and entity profiles", 10)

        # 1. Identify entities to analyze
        if not entity_ids:
            if upload_id:
                # Find entities present in this upload
                up = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == upload_id).first()
                if up and up.entity_ids:
                    entity_ids = list(up.entity_ids)
                else:
                    # Look up by foreign key on alerts/cases/assets
                    e_alerts = [r[0] for r in db.query(domain.Alert.entity_id).filter(domain.Alert.upload_id == upload_id).distinct()]
                    e_cases = [r[0] for r in db.query(domain.Case.entity_id).filter(domain.Case.upload_id == upload_id).distinct()]
                    e_assets = [r[0] for r in db.query(domain.Asset.entity_id).filter(domain.Asset.upload_id == upload_id).distinct()]
                    entity_ids = list(set(e_alerts + e_cases + e_assets))
            
            # If still empty or no upload_id provided, analyze all entities in database
            if not entity_ids:
                entity_ids = [e.id for e in db.query(domain.Entity).all()]

        # Ensure entities exist in entities table
        for eid in entity_ids:
            existing = db.query(domain.Entity).filter(domain.Entity.id == eid).first()
            if not existing:
                db.add(domain.Entity(id=eid, name=f"Critical Sector Entity {eid}", sector="Critical Infrastructure", assessment_period="2026-Q3"))
        db.commit()

        # Record ANALYSIS_STARTED audit event
        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            primary_entity = entity_ids[0] if entity_ids else "CSE-001"
            audit_svc.record_event(
                db=db,
                event_type=EventType.ANALYSIS_STARTED,
                actor_type=ActorType.ANALYTICS_ENGINE,
                actor_id="SupervisoryAnalyticsEngine",
                entity_id=primary_entity,
                analysis_id=analysis_id or upload_id,
                payload={
                    "analysis_id": analysis_id or upload_id,
                    "entities_count": len(entity_ids),
                    "entities": entity_ids,
                },
            )
        except Exception:
            pass

        # Group records by entity
        entity_data: Dict[str, Dict[str, Any]] = {}
        for eid in entity_ids:
            alerts = db.query(domain.Alert).filter(domain.Alert.entity_id == eid).all()
            cases = db.query(domain.Case).filter(domain.Case.entity_id == eid).all()
            assets = db.query(domain.Asset).filter(domain.Asset.entity_id == eid).all()
            entity_data[eid] = {
                "alerts": alerts,
                "cases": cases,
                "assets": assets,
            }

        report("reconstructing_evidence", "Building operational evidence relationships", 25)

        all_findings: List[domain.Finding] = []

        # 2. Execution Gap Detection
        report("detecting_execution_gaps", "Running deterministic execution gap detectors", 40)
        for eid, data in entity_data.items():
            eg_findings = self.execution_gap_detector.analyze_entity(
                entity_id=eid,
                alerts=data["alerts"],
                cases=data["cases"],
                upload_id=upload_id,
            )
            all_findings.extend(eg_findings)

        # 3. Negative Space Detection
        report("detecting_negative_space", "Evaluating evidence absence and missing telemetry", 55)
        for eid, data in entity_data.items():
            ns_findings = self.negative_space_detector.analyze_entity(
                entity_id=eid,
                assets=data["assets"],
                alerts=data["alerts"],
                cases=data["cases"],
                upload_id=upload_id,
            )
            all_findings.extend(ns_findings)

        # 4. Statistical Anomaly Detection
        report("detecting_anomalies", "Calculating statistical duration and operational anomalies", 70)
        for eid, data in entity_data.items():
            anom_findings = self.anomaly_detector.analyze_entity(
                entity_id=eid,
                alerts=data["alerts"],
                cases=data["cases"],
                upload_id=upload_id,
            )
            all_findings.extend(anom_findings)

        # 5. Cohort Peer Benchmarking
        report("calculating_benchmarks", "Computing peer cohort medians and percentile ranks", 80)
        benchmark_results = self.benchmarker.calculate_cohort_benchmarks(
            entity_records=entity_data,
            upload_id=upload_id,
        )
        benchmarks = benchmark_results["benchmarks"]
        all_findings.extend(benchmark_results["peer_findings"])

        # 6. Entity Risk Scoring
        report("calculating_risk", "Synthesizing multi-factor supervisory risk scores", 90)
        risk_scores: List[domain.RiskScore] = []
        for eid, data in entity_data.items():
            rs = self.risk_calculator.calculate_entity_risk(
                entity_id=eid,
                findings=all_findings,
                benchmarks=benchmarks,
                assets=data["assets"],
                alerts=data["alerts"],
            )
            risk_scores.append(rs)

        # 7. Persist to SQLite Database
        report("persisting_findings", "Saving findings, risk scores, benchmarks, and review items", 95)
        
        # Clear existing findings for entities being re-analyzed to prevent stale duplicates
        for eid in entity_ids:
            # Delete review items for old findings of this entity
            old_finding_ids = [f.id for f in db.query(domain.Finding.id).filter(domain.Finding.entity_id == eid).all()]
            if old_finding_ids:
                db.query(domain.ReviewItem).filter(domain.ReviewItem.finding_id.in_(old_finding_ids)).delete(synchronize_session=False)
            db.query(domain.Finding).filter(domain.Finding.entity_id == eid).delete(synchronize_session=False)
            db.query(domain.Benchmark).filter(domain.Benchmark.entity_id == eid).delete(synchronize_session=False)
            db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == eid).delete(synchronize_session=False)

        # Insert new findings
        for f in all_findings:
            db.add(f)
            # Create review item for each finding
            priority = 50.0
            if f.severity == "CRITICAL":
                priority = 90.0 + (f.confidence * 8.0)
            elif f.severity == "HIGH":
                priority = 75.0 + (f.confidence * 10.0)
            elif f.severity == "MEDIUM":
                priority = 55.0 + (f.confidence * 10.0)
            else:
                priority = 35.0

            db.add(domain.ReviewItem(
                finding_id=f.id,
                priority_score=round(priority, 1),
                status="Pending",
                notes=f"Auto-queued by Supervisory Analytics Engine ({f.category})"
            ))

        # Insert benchmarks
        for b in benchmarks:
            db.add(b)

        # Insert risk scores
        for r in risk_scores:
            db.add(r)

        db.commit()

        # Record FINDING_CREATED audit events for each finding
        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            for f in all_findings:
                audit_svc.record_event(
                    db=db,
                    event_type=EventType.FINDING_CREATED,
                    actor_type=ActorType.ANALYTICS_ENGINE,
                    actor_id="SupervisoryAnalyticsEngine",
                    entity_id=f.entity_id,
                    analysis_id=analysis_id or upload_id or f.upload_id,
                    finding_id=f.id,
                    payload={
                        "finding_id": f.id,
                        "type": f.type,
                        "category": f.category,
                        "severity": f.severity,
                        "confidence": f.confidence,
                        "analytic_rule": f.analytic_rule,
                        "evidence_ids": f.evidence_ids or [],
                        "risk_contribution": f.risk_contribution,
                    },
                )
        except Exception:
            pass

        # 8. Evaluate Assessment Assurance (Module 5)
        report("evaluating_assurance", "Evaluating assessment assurance, evidence coverage & integrity", 98)
        assurance_rec = self.assurance_service.evaluate_assurance(
            db=db,
            analysis_id=analysis_id,
            upload_id=upload_id,
            entity_id=entity_ids[0] if len(entity_ids) == 1 else None,
        )

        # Record ANALYSIS_COMPLETED audit event
        try:
            from app.services.audit import AuditService, EventType, ActorType
            audit_svc = AuditService()
            primary_entity = entity_ids[0] if entity_ids else "CSE-001"
            audit_svc.record_event(
                db=db,
                event_type=EventType.ANALYSIS_COMPLETED,
                actor_type=ActorType.ANALYTICS_ENGINE,
                actor_id="SupervisoryAnalyticsEngine",
                entity_id=primary_entity,
                analysis_id=analysis_id or upload_id,
                payload={
                    "analysis_id": analysis_id or upload_id,
                    "entities_analyzed": len(entity_ids),
                    "findings_count": len(all_findings),
                    "assessment_validity": assurance_rec.overall_status,
                    "categories": {
                        "execution_gaps": sum(1 for f in all_findings if f.category == "execution_gap"),
                        "negative_space": sum(1 for f in all_findings if f.category == "negative_space"),
                        "anomalies": sum(1 for f in all_findings if f.category == "anomaly"),
                        "peer_deviations": sum(1 for f in all_findings if f.category == "peer_deviation"),
                    },
                },
            )
        except Exception:
            pass

        report("completed", "Supervisory analytics pipeline completed successfully", 100)

        return {
            "entities_analyzed": len(entity_ids),
            "findings_count": len(all_findings),
            "benchmarks_count": len(benchmarks),
            "risk_scores_count": len(risk_scores),
            "assessment_validity": assurance_rec.overall_status,
            "assurance_id": assurance_rec.id,
            "categories": {
                "execution_gaps": sum(1 for f in all_findings if f.category == "execution_gap"),
                "negative_space": sum(1 for f in all_findings if f.category == "negative_space"),
                "anomalies": sum(1 for f in all_findings if f.category == "anomaly"),
                "peer_deviations": sum(1 for f in all_findings if f.category == "peer_deviation"),
            },
        }
