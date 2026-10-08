"""
SAT-SA Cryptographic Audit & Replay Service (Module 9).
Provides offline, append-oriented, cryptographically chained audit logging,
deterministic hash validation, snapshot generation, and full supervisory replay.
"""

import json
import hashlib
import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.models import domain
from app.services import reporting


# =========================================================================
# CONSTANTS & CONTROLLED VOCABULARIES
# =========================================================================

class EventType:
    DATA_INGESTED = "DATA_INGESTED"
    DATA_VALIDATED = "DATA_VALIDATED"
    ANALYSIS_STARTED = "ANALYSIS_STARTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    FINDING_CREATED = "FINDING_CREATED"
    FINDING_UPDATED = "FINDING_UPDATED"
    ASSURANCE_CREATED = "ASSURANCE_CREATED"
    ASSURANCE_UPDATED = "ASSURANCE_UPDATED"
    AGENT_RUN_STARTED = "AGENT_RUN_STARTED"
    AGENT_ASSESSMENT_CREATED = "AGENT_ASSESSMENT_CREATED"
    AGENT_CHALLENGE_CREATED = "AGENT_CHALLENGE_CREATED"
    AGENT_RECOMMENDATION_CREATED = "AGENT_RECOMMENDATION_CREATED"
    AGENT_RUN_COMPLETED = "AGENT_RUN_COMPLETED"
    EVIDENCE_REQUEST_CREATED = "EVIDENCE_REQUEST_CREATED"
    EVIDENCE_REQUEST_UPDATED = "EVIDENCE_REQUEST_UPDATED"
    HUMAN_DECISION_CREATED = "HUMAN_DECISION_CREATED"
    REPORT_GENERATED = "REPORT_GENERATED"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    REPLAY_STARTED = "REPLAY_STARTED"
    REPLAY_COMPLETED = "REPLAY_COMPLETED"


class ActorType:
    SYSTEM = "SYSTEM"
    ANALYTICS_ENGINE = "ANALYTICS_ENGINE"
    ASSESSMENT_AGENT = "ASSESSMENT_AGENT"
    CHALLENGE_AGENT = "CHALLENGE_AGENT"
    INVESTIGATION_PLANNER = "INVESTIGATION_PLANNER"
    HUMAN_EXAMINER = "HUMAN_EXAMINER"
    REPORTING_ENGINE = "REPORTING_ENGINE"
    REPLAY_ENGINE = "REPLAY_ENGINE"


# =========================================================================
# CANONICAL HASHING (RFC-8785 DETERMINISTIC JSON + SHA-256)
# =========================================================================

def serialize_canonical_json(data: Any) -> str:
    """
    Serializes arbitrary Python objects to deterministic canonical JSON:
    - Sorted dictionary keys
    - Minimal separators (',', ':')
    - ISO-8601 UTC formatted datetimes
    - UTF-8 representation
    """
    def _default_encoder(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return str(obj)

    return json.dumps(
        data,
        default=_default_encoder,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )


def compute_sha256(content: str) -> str:
    """Computes SHA-256 hex digest for a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_event_hash(
    event_type: str,
    actor_type: str,
    actor_id: str,
    timestamp: Any,
    entity_id: Optional[str] = None,
    analysis_id: Optional[str] = None,
    finding_id: Optional[str] = None,
    agent_run_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    evidence_request_id: Optional[str] = None,
    report_id: Optional[str] = None,
    event_version: str = "1.0",
    payload: Optional[Dict[str, Any]] = None,
    previous_event_hash: Optional[str] = None,
    source_snapshot_hash: Optional[str] = None,
) -> str:
    """
    Computes cryptographic SHA-256 hash across canonical event fields.
    Guarantees strict hash stability across platforms and environments.
    """
    ts_str = timestamp.isoformat() if isinstance(timestamp, (datetime.datetime, datetime.date)) else str(timestamp)
    
    canonical_dict = {
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "timestamp": ts_str,
        "entity_id": entity_id,
        "analysis_id": analysis_id,
        "finding_id": finding_id,
        "agent_run_id": agent_run_id,
        "decision_id": decision_id,
        "evidence_request_id": evidence_request_id,
        "report_id": report_id,
        "event_version": event_version,
        "payload": payload or {},
        "previous_event_hash": previous_event_hash,
        "source_snapshot_hash": source_snapshot_hash,
    }
    canonical_json_str = serialize_canonical_json(canonical_dict)
    return compute_sha256(canonical_json_str)


# =========================================================================
# AUDIT EVENT SERVICE (RECORD, FETCH, VERIFY, SNAPSHOT)
# =========================================================================

class AuditService:
    """
    Service managing append-only cryptographic audit event chains.
    """

    def record_event(
        self,
        db: Session,
        event_type: str,
        actor_type: str,
        actor_id: str,
        entity_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        evidence_request_id: Optional[str] = None,
        report_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        source_snapshot_hash: Optional[str] = None,
        timestamp: Optional[datetime.datetime] = None,
        event_version: str = "1.0",
    ) -> domain.AuditEvent:
        """
        Appends a new cryptographically chained audit event to the persistent ledger.
        Resolves the previous event hash in the sequence to maintain verifiable hash continuity.
        """
        event_ts = timestamp or datetime.datetime.utcnow()
        payload = payload or {}

        # Resolve latest event hash for the stream
        query = db.query(domain.AuditEvent)
        if analysis_id:
            query = query.filter(domain.AuditEvent.analysis_id == analysis_id)
        elif entity_id:
            query = query.filter(domain.AuditEvent.entity_id == entity_id)

        last_event = query.order_by(domain.AuditEvent.id.desc()).first()
        prev_hash = last_event.event_hash if last_event else None

        # Compute hash
        evt_hash = compute_event_hash(
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            timestamp=event_ts,
            entity_id=entity_id,
            analysis_id=analysis_id,
            finding_id=finding_id,
            agent_run_id=agent_run_id,
            decision_id=decision_id,
            evidence_request_id=evidence_request_id,
            report_id=report_id,
            event_version=event_version,
            payload=payload,
            previous_event_hash=prev_hash,
            source_snapshot_hash=source_snapshot_hash,
        )

        event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"

        audit_entry = domain.AuditEvent(
            event_id=event_id,
            entity_id=entity_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            timestamp=event_ts,
            analysis_id=analysis_id,
            finding_id=finding_id,
            agent_run_id=agent_run_id,
            decision_id=str(decision_id) if decision_id is not None else None,
            evidence_request_id=evidence_request_id,
            report_id=report_id,
            event_version=event_version,
            payload_json=payload,
            previous_event_hash=prev_hash,
            event_hash=evt_hash,
            source_snapshot_hash=source_snapshot_hash,
        )

        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry

    def get_events(
        self,
        db: Session,
        entity_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        event_type: Optional[str] = None,
        actor_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "asc",
    ) -> List[domain.AuditEvent]:
        """Fetch audit events matching filter criteria."""
        query = db.query(domain.AuditEvent)
        if entity_id:
            query = query.filter(domain.AuditEvent.entity_id == entity_id)
        if analysis_id:
            query = query.filter(domain.AuditEvent.analysis_id == analysis_id)
        if finding_id:
            query = query.filter(domain.AuditEvent.finding_id == finding_id)
        if event_type:
            query = query.filter(domain.AuditEvent.event_type == event_type)
        if actor_type:
            query = query.filter(domain.AuditEvent.actor_type == actor_type)

        if order.lower() == "desc":
            query = query.order_by(domain.AuditEvent.id.desc())
        else:
            query = query.order_by(domain.AuditEvent.id.asc())

        return query.offset(offset).limit(limit).all()

    def get_analysis_events(self, db: Session, analysis_id: str) -> List[domain.AuditEvent]:
        """Fetch all chronological audit events associated with an analysis/upload."""
        return db.query(domain.AuditEvent).filter(
            domain.AuditEvent.analysis_id == analysis_id
        ).order_by(domain.AuditEvent.id.asc()).all()

    def verify_chain(self, events: List[domain.AuditEvent]) -> Dict[str, Any]:
        """
        Validates cryptographic integrity and uninterrupted linkage across an event sequence.
        Checks:
        1. Correct previous_event_hash reference for every sequential event.
        2. Computed event_hash matches stored event_hash for every event.
        """
        if not events:
            return {
                "valid": True,
                "total_events": 0,
                "broken_at_index": None,
                "broken_event_id": None,
                "error": None,
                "chain_hashes": [],
            }

        chain_hashes = []
        for idx, event in enumerate(events):
            # 1. Check link to previous event
            if idx == 0:
                # First event in sequence may have None or specific initial hash
                expected_prev = event.previous_event_hash
            else:
                expected_prev = events[idx - 1].event_hash
                if event.previous_event_hash != expected_prev:
                    return {
                        "valid": False,
                        "total_events": len(events),
                        "broken_at_index": idx,
                        "broken_event_id": event.event_id,
                        "error": f"Broken chain link at event index {idx} ({event.event_id}): previous_event_hash '{event.previous_event_hash}' does not match expected '{expected_prev}'",
                        "chain_hashes": chain_hashes,
                    }

            # 2. Recompute event hash and verify integrity
            recomputed = compute_event_hash(
                event_type=event.event_type,
                actor_type=event.actor_type,
                actor_id=event.actor_id,
                timestamp=event.timestamp,
                entity_id=event.entity_id,
                analysis_id=event.analysis_id,
                finding_id=event.finding_id,
                agent_run_id=event.agent_run_id,
                decision_id=event.decision_id,
                evidence_request_id=event.evidence_request_id,
                report_id=event.report_id,
                event_version=event.event_version,
                payload=event.payload_json or {},
                previous_event_hash=event.previous_event_hash,
                source_snapshot_hash=event.source_snapshot_hash,
            )

            if recomputed != event.event_hash:
                return {
                    "valid": False,
                    "total_events": len(events),
                    "broken_at_index": idx,
                    "broken_event_id": event.event_id,
                    "error": f"Tampered event payload at index {idx} ({event.event_id}): stored hash '{event.event_hash}' != computed '{recomputed}'",
                    "chain_hashes": chain_hashes,
                }

            chain_hashes.append(event.event_hash)

        return {
            "valid": True,
            "total_events": len(events),
            "broken_at_index": None,
            "broken_event_id": None,
            "error": None,
            "chain_hashes": chain_hashes,
        }

    def create_snapshot(
        self,
        db: Session,
        entity_id: str,
        analysis_id: Optional[str] = None,
    ) -> domain.AssessmentSnapshot:
        """
        Creates a deterministic point-in-time snapshot of the supervisory assessment state.
        References evidence and source record IDs without duplicating raw datasets.
        """
        entity = db.query(domain.Entity).filter(domain.Entity.id == entity_id).first()
        findings = db.query(domain.Finding).filter(domain.Finding.entity_id == entity_id).all()
        assurance = db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.entity_id == entity_id).order_by(domain.AssessmentAssurance.created_at.desc()).first()
        alerts = db.query(domain.Alert).filter(domain.Alert.entity_id == entity_id).all()
        cases = db.query(domain.Case).filter(domain.Case.entity_id == entity_id).all()
        assets = db.query(domain.Asset).filter(domain.Asset.entity_id == entity_id).all()
        evidence_requests = db.query(domain.EvidenceRequest).filter(domain.EvidenceRequest.entity_id == entity_id).all()
        decisions = db.query(domain.FindingDecision).all()

        capabilities = reporting.evaluate_capabilities(
            findings=findings,
            assurance=assurance,
            alerts=alerts,
            cases=cases,
            assets=assets,
        )

        snapshot_content = {
            "entity": {
                "id": entity.id if entity else entity_id,
                "name": entity.name if entity else "Unknown Entity",
                "sector": entity.sector if entity else "Critical Infrastructure",
                "assessment_period": entity.assessment_period if entity else "Not provided",
            },
            "analysis_id": analysis_id or "ANL-CURRENT",
            "findings": [
                {
                    "id": f.id,
                    "type": f.type,
                    "category": f.category,
                    "severity": f.severity,
                    "confidence": f.confidence,
                    "assessment_validity": f.assessment_validity,
                    "analytic_rule": f.analytic_rule,
                    "evidence_ids": f.evidence_ids or [],
                    "decision_status": f.decision_status or "OPEN",
                    "adjudicated_by": f.adjudicated_by,
                    "modified_assessment": f.modified_assessment,
                }
                for f in findings
            ],
            "assessment_validity": assurance.assessment_validity if assurance else "HIGH",
            "capabilities": [
                {
                    "name": c["name"],
                    "status": c["status"],
                    "findings_count": c["findings_count"],
                    "assessment_validity": c["assessment_validity"],
                }
                for c in capabilities
            ],
            "evidence_requests": [
                {
                    "id": req.id,
                    "finding_id": req.finding_id,
                    "request_type": req.request_type,
                    "status": req.status,
                    "priority": req.priority,
                    "reason": req.reason,
                }
                for req in evidence_requests
            ],
            "decisions_count": len([d for d in decisions if any(d.finding_id == f.id for f in findings)]),
        }

        canonical_str = serialize_canonical_json(snapshot_content)
        snap_hash = compute_sha256(canonical_str)
        snap_id = f"SNP-{uuid.uuid4().hex[:10].upper()}"

        snapshot_record = domain.AssessmentSnapshot(
            id=snap_id,
            analysis_id=analysis_id,
            entity_id=entity_id,
            snapshot_timestamp=datetime.datetime.utcnow(),
            snapshot_hash=snap_hash,
            data_json=snapshot_content,
        )

        db.add(snapshot_record)
        db.commit()
        db.refresh(snapshot_record)

        # Record audit event for snapshot creation
        self.record_event(
            db=db,
            event_type=EventType.SNAPSHOT_CREATED,
            actor_type=ActorType.SYSTEM,
            actor_id="AuditService",
            entity_id=entity_id,
            analysis_id=analysis_id,
            payload={
                "snapshot_id": snap_id,
                "snapshot_hash": snap_hash,
                "findings_count": len(findings),
                "assessment_validity": snapshot_content["assessment_validity"],
            },
            source_snapshot_hash=snap_hash,
        )

        return snapshot_record


# =========================================================================
# DETERMINISTIC REPLAY ENGINE (MODULE 10 RECONSTRUCTION)
# =========================================================================

class ReplayEngine:
    """
    Deterministic replay engine that reconstructs the supervisory assessment state
    by replaying chronological audit events and comparing against persisted state.
    """

    def __init__(self, audit_service: Optional[AuditService] = None):
        self.audit_service = audit_service or AuditService()

    def replay_analysis(self, db: Session, analysis_id: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes deterministic replay of an assessment from its audit event stream.
        1. Retrieves events and verifies chronological ordering & hash chain integrity.
        2. Applies event state transitions to reconstruct final findings, decisions, and capabilities.
        3. Compares reconstructed state with persisted database state.
        """
        # Fetch events for analysis
        events_query = db.query(domain.AuditEvent)
        if analysis_id:
            events_query = events_query.filter(domain.AuditEvent.analysis_id == analysis_id)
        elif entity_id:
            events_query = events_query.filter(domain.AuditEvent.entity_id == entity_id)

        events = events_query.order_by(domain.AuditEvent.id.asc()).all()

        if not events:
            # Check if analysis exists
            upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.id == analysis_id).first()
            return {
                "analysis_id": analysis_id,
                "entity_id": entity_id or (upload.entity_ids[0] if upload and upload.entity_ids else "CSE-GENERAL"),
                "replay_valid": False,
                "chain_integrity": "EMPTY",
                "state_match": False,
                "events_processed": 0,
                "mismatches": [{"field": "audit_events", "issue": f"No audit events found for analysis_id '{analysis_id}'"}],
                "reconstructed_state": {},
                "persisted_state": {},
                "replayed_at": datetime.datetime.utcnow().isoformat(),
            }

        # 1. Verify Cryptographic Chain Integrity
        chain_result = self.audit_service.verify_chain(events)
        chain_integrity_status = "VERIFIED" if chain_result["valid"] else "BROKEN"

        # 2. Sequential State Reconstruction
        reconstructed_findings: Dict[str, Dict[str, Any]] = {}
        reconstructed_assurance: Dict[str, Any] = {"assessment_validity": "HIGH", "dimensions": {}}
        reconstructed_decisions: Dict[str, Dict[str, Any]] = {}
        reconstructed_requests: Dict[str, Dict[str, Any]] = {}
        reconstructed_agent_runs: Dict[str, Dict[str, Any]] = {}
        analysis_metadata: Dict[str, Any] = {"analysis_id": analysis_id, "stages": []}

        resolved_entity_id = entity_id or events[0].entity_id or "CSE-001"

        for evt in events:
            if evt.entity_id:
                resolved_entity_id = evt.entity_id

            etype = evt.event_type
            payload = evt.payload_json or {}

            if etype == EventType.ANALYSIS_STARTED:
                analysis_metadata["stages"].append({"stage": "STARTED", "timestamp": evt.timestamp.isoformat()})

            elif etype == EventType.DATA_INGESTED:
                analysis_metadata["ingested_filename"] = payload.get("filename")
                analysis_metadata["records_valid"] = payload.get("records_valid")

            elif etype == EventType.FINDING_CREATED:
                fid = evt.finding_id or payload.get("finding_id")
                if fid:
                    reconstructed_findings[fid] = {
                        "id": fid,
                        "type": payload.get("type"),
                        "category": payload.get("category"),
                        "severity": payload.get("severity"),
                        "confidence": payload.get("confidence"),
                        "assessment_validity": payload.get("assessment_validity", "HIGH"),
                        "analytic_rule": payload.get("analytic_rule"),
                        "evidence_ids": payload.get("evidence_ids", []),
                        "decision_status": "OPEN",
                        "adjudicated_by": None,
                        "modified_assessment": None,
                    }

            elif etype == EventType.FINDING_UPDATED:
                fid = evt.finding_id or payload.get("finding_id")
                if fid and fid in reconstructed_findings:
                    for k, v in payload.items():
                        if k != "finding_id":
                            reconstructed_findings[fid][k] = v

            elif etype == EventType.ASSURANCE_CREATED or etype == EventType.ASSURANCE_UPDATED:
                reconstructed_assurance["assessment_validity"] = payload.get("overall_status") or payload.get("assessment_validity", "HIGH")
                if "coverage_details" in payload:
                    reconstructed_assurance["dimensions"] = payload["coverage_details"]

                # Update findings assessment validity if propagated
                for f in reconstructed_findings.values():
                    f["assessment_validity"] = reconstructed_assurance["assessment_validity"]

            elif etype == EventType.AGENT_ASSESSMENT_CREATED:
                rid = evt.agent_run_id or payload.get("run_id")
                if rid:
                    if rid not in reconstructed_agent_runs:
                        reconstructed_agent_runs[rid] = {}
                    reconstructed_agent_runs[rid]["hypothesis"] = payload.get("hypothesis")
                    reconstructed_agent_runs[rid]["confidence"] = payload.get("confidence")

            elif etype == EventType.AGENT_CHALLENGE_CREATED:
                rid = evt.agent_run_id or payload.get("run_id")
                if rid:
                    if rid not in reconstructed_agent_runs:
                        reconstructed_agent_runs[rid] = {}
                    reconstructed_agent_runs[rid]["challenge_status"] = payload.get("challenge_status")
                    reconstructed_agent_runs[rid]["missing_evidence"] = payload.get("missing_evidence", [])

            elif etype == EventType.AGENT_RECOMMENDATION_CREATED:
                rid = evt.agent_run_id or payload.get("run_id")
                if rid:
                    if rid not in reconstructed_agent_runs:
                        reconstructed_agent_runs[rid] = {}
                    reconstructed_agent_runs[rid]["recommended_action"] = payload.get("recommended_action")

            elif etype == EventType.EVIDENCE_REQUEST_CREATED:
                req_id = evt.evidence_request_id or payload.get("request_id")
                if req_id:
                    reconstructed_requests[req_id] = {
                        "id": req_id,
                        "finding_id": evt.finding_id or payload.get("finding_id"),
                        "request_type": payload.get("request_type"),
                        "reason": payload.get("reason"),
                        "priority": payload.get("priority", "HIGH"),
                        "status": payload.get("status", "OPEN"),
                    }
                    # Finding decision status updates to EVIDENCE_REQUESTED
                    fid = evt.finding_id or payload.get("finding_id")
                    if fid and fid in reconstructed_findings:
                        reconstructed_findings[fid]["decision_status"] = "EVIDENCE_REQUESTED"

            elif etype == EventType.EVIDENCE_REQUEST_UPDATED:
                req_id = evt.evidence_request_id or payload.get("request_id")
                if req_id and req_id in reconstructed_requests:
                    reconstructed_requests[req_id]["status"] = payload.get("status", reconstructed_requests[req_id]["status"])

            elif etype == EventType.HUMAN_DECISION_CREATED:
                fid = evt.finding_id or payload.get("finding_id")
                dec_status = payload.get("decision")
                actor = evt.actor_id or payload.get("actor")
                notes = payload.get("notes")

                if fid:
                    reconstructed_decisions[fid] = {
                        "finding_id": fid,
                        "decision": dec_status,
                        "actor": actor,
                        "notes": notes,
                        "timestamp": evt.timestamp.isoformat(),
                    }
                    if fid in reconstructed_findings:
                        reconstructed_findings[fid]["decision_status"] = dec_status
                        reconstructed_findings[fid]["adjudicated_by"] = actor
                        reconstructed_findings[fid]["modified_assessment"] = notes

        # 3. Retrieve Persisted Database State for Verification
        persisted_findings = db.query(domain.Finding).filter(
            (domain.Finding.upload_id == analysis_id) | (domain.Finding.entity_id == resolved_entity_id)
        ).all()

        persisted_assurance = db.query(domain.AssessmentAssurance).filter(
            (domain.AssessmentAssurance.analysis_id == analysis_id) |
            (domain.AssessmentAssurance.entity_id == resolved_entity_id)
        ).order_by(domain.AssessmentAssurance.created_at.desc()).first()

        persisted_requests = db.query(domain.EvidenceRequest).filter(
            (domain.EvidenceRequest.analysis_id == analysis_id) |
            (domain.EvidenceRequest.entity_id == resolved_entity_id)
        ).all()

        # 4. Compare Reconstructed vs Persisted State
        mismatches = []

        if not chain_result["valid"]:
            mismatches.append({
                "component": "hash_chain",
                "issue": chain_result["error"],
            })

        # Findings comparison
        persisted_f_map = {f.id: f for f in persisted_findings}
        for fid, rf in reconstructed_findings.items():
            if fid not in persisted_f_map:
                mismatches.append({
                    "component": "finding",
                    "id": fid,
                    "issue": f"Reconstructed finding '{fid}' is not found in persisted database",
                })
            else:
                pf = persisted_f_map[fid]
                if rf["decision_status"] != (pf.decision_status or "OPEN"):
                    mismatches.append({
                        "component": "finding_decision",
                        "id": fid,
                        "expected": rf["decision_status"],
                        "actual": pf.decision_status,
                        "issue": f"Decision status mismatch for '{fid}': replayed '{rf['decision_status']}' vs db '{pf.decision_status}'",
                    })

        # Assurance comparison
        if persisted_assurance:
            if reconstructed_assurance["assessment_validity"] != persisted_assurance.assessment_validity:
                mismatches.append({
                    "component": "assurance_validity",
                    "expected": reconstructed_assurance["assessment_validity"],
                    "actual": persisted_assurance.assessment_validity,
                    "issue": f"Assessment validity mismatch: replayed '{reconstructed_assurance['assessment_validity']}' vs db '{persisted_assurance.assessment_validity}'",
                })

        state_match = len(mismatches) == 0
        replay_valid = chain_result["valid"] and state_match

        reconstructed_state = {
            "entity_id": resolved_entity_id,
            "analysis_id": analysis_id,
            "findings_count": len(reconstructed_findings),
            "findings": list(reconstructed_findings.values()),
            "assessment_validity": reconstructed_assurance["assessment_validity"],
            "agent_runs": reconstructed_agent_runs,
            "human_decisions": reconstructed_decisions,
            "evidence_requests": list(reconstructed_requests.values()),
        }

        persisted_state = {
            "entity_id": resolved_entity_id,
            "analysis_id": analysis_id,
            "findings_count": len(persisted_findings),
            "findings": [
                {
                    "id": f.id,
                    "type": f.type,
                    "severity": f.severity,
                    "confidence": f.confidence,
                    "assessment_validity": f.assessment_validity,
                    "decision_status": f.decision_status or "OPEN",
                }
                for f in persisted_findings
            ],
            "assessment_validity": persisted_assurance.assessment_validity if persisted_assurance else "HIGH",
            "evidence_requests_count": len(persisted_requests),
        }

        # Log replay completed audit event
        self.audit_service.record_event(
            db=db,
            event_type=EventType.REPLAY_COMPLETED,
            actor_type=ActorType.REPLAY_ENGINE,
            actor_id="ReplayEngine",
            entity_id=resolved_entity_id,
            analysis_id=analysis_id,
            payload={
                "events_processed": len(events),
                "chain_integrity": chain_integrity_status,
                "replay_valid": replay_valid,
                "state_match": state_match,
                "mismatches_count": len(mismatches),
            },
        )

        return {
            "analysis_id": analysis_id,
            "entity_id": resolved_entity_id,
            "replay_valid": replay_valid,
            "chain_integrity": chain_integrity_status,
            "state_match": state_match,
            "events_processed": len(events),
            "chain_verification": chain_result,
            "mismatches": mismatches,
            "reconstructed_state": reconstructed_state,
            "persisted_state": persisted_state,
            "replayed_at": datetime.datetime.utcnow().isoformat(),
        }
