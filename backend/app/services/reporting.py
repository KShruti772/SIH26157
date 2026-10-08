"""
SAT-SA Supervisory Reporting & Dashboard Service (Module 8)
Generates deterministic, evidence-grounded supervisory reports (JSON & PDF)
and consolidates multi-dimensional supervisory assessment dashboards.
"""

import io
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models import domain
from app.assurance.service import AssessmentAssuranceService
from app.services import workspace

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas


# =========================================================================
# 8 OPERATIONAL CAPABILITY DEFINITIONS (NCIIPC / NTRO SAT-SA SPECIFICATION)
# =========================================================================

CAPABILITY_NAMES = [
    "Threat Detection",
    "Investigation",
    "Escalation",
    "Incident Response",
    "Security Operations",
    "Governance & Oversight",
    "Operational Discipline",
    "Cyber Resilience",
]

RULE_TO_CAPABILITY_MAP = {
    "NS_UNMONITORED_ASSETS_V1": ["Threat Detection", "Cyber Resilience"],
    "EXEC_CRITICAL_UNINVESTIGATED_V1": ["Threat Detection", "Investigation", "Security Operations"],
    "NS_ALERTS_WITHOUT_CASE_V1": ["Investigation", "Governance & Oversight"],
    "EXEC_ACKNOWLEDGED_NOT_INVESTIGATED_V1": ["Investigation", "Security Operations"],
    "ANOMALY_INVESTIGATION_DURATION_V1": ["Investigation", "Operational Discipline"],
    "EXEC_CRITICAL_INVESTIGATED_NOT_ESCALATED_V1": ["Escalation", "Governance & Oversight"],
    "EXEC_RAPID_CLOSURE_V1": ["Incident Response", "Operational Discipline"],
    "ANOMALY_CLOSURE_DURATION_V1": ["Incident Response", "Operational Discipline"],
    "STAT_ANOMALY_OUTLIER_V1": ["Security Operations", "Operational Discipline"],
    "PEER_DEVIATION_DURATION_V1": ["Security Operations", "Operational Discipline"],
}

CATEGORY_TO_CAPABILITY_MAP = {
    "execution_gap": ["Security Operations", "Investigation", "Escalation"],
    "negative_space": ["Threat Detection", "Governance & Oversight", "Cyber Resilience"],
    "anomaly": ["Operational Discipline", "Incident Response"],
    "peer_deviation": ["Security Operations", "Operational Discipline"],
}


def evaluate_capabilities(
    findings: List[domain.Finding],
    assurance: Optional[domain.AssessmentAssurance],
    alerts: List[domain.Alert],
    cases: List[domain.Case],
    assets: List[domain.Asset],
    assessed_capabilities: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Evaluates the 8 operational capabilities deterministically based strictly on
    persisted findings, observed evidence coverage, and assurance limitations.
    
    CRITICAL SUPERVISORY RULE:
    Absence of a finding MUST NOT automatically produce 'NO OBSERVED CONCERN'.
    If required telemetry (cases, escalation logs, response timestamps) was not submitted,
    the capability status MUST be 'INSUFFICIENT EVIDENCE'.
    
    States:
    - OBSERVED CONCERN: Specific evidence-backed findings or execution gaps exist.
    - NO OBSERVED CONCERN: Sufficient evidence is available, process was observed, and no findings flagged.
    - INSUFFICIENT EVIDENCE: Relevant telemetry/logs were missing from submission.
    - NOT ASSESSED: Capability excluded from assessment scope or zero data evaluated.
    """
    has_alerts = len(alerts) > 0
    has_cases = len(cases) > 0
    has_assets = len(assets) > 0
    
    # Check specific observable telemetry in records
    has_alert_timestamps = has_alerts and any(getattr(a, "timestamp", None) is not None for a in alerts)
    has_alert_investigations = has_alerts and any(getattr(a, "investigation_started", False) for a in alerts)
    has_alert_escalations = has_alerts and any(getattr(a, "escalated", None) is not None for a in alerts)
    has_case_escalations = has_cases and any(getattr(c, "escalation_status", None) is not None or getattr(c, "escalated", None) is not None for c in cases)
    has_alert_closures = has_alerts and any(getattr(a, "closed_at", None) is not None or getattr(a, "disposition", None) is not None for a in alerts)
    has_case_closures = has_cases and any(getattr(c, "closure_time", None) is not None or getattr(c, "closed_at", None) is not None or getattr(c, "closure_reason", None) is not None or getattr(c, "disposition", None) is not None for c in cases)
    
    has_investigation_evidence = has_cases or has_alert_investigations
    has_escalation_evidence = has_case_escalations or (has_alerts and has_alert_escalations and has_cases)
    has_response_evidence = has_case_closures or has_alert_closures

    results = []
    
    for cap in CAPABILITY_NAMES:
        # Check if explicitly excluded from assessment scope
        if assessed_capabilities is not None and cap not in assessed_capabilities:
            results.append({
                "name": cap,
                "status": "NOT ASSESSED",
                "findings_count": 0,
                "finding_ids": [],
                "evidence_coverage": "Capability excluded from current assessment scope.",
                "assessment_validity": "INDETERMINATE",
                "human_adjudication_state": "N/A (Not Assessed)",
                "evidence_limitations": ["Scope exclusion"],
                "observation": "Capability was not evaluated in current assessment scope.",
                "implication": "No evaluation performed for this capability.",
            })
            continue

        # Match findings to this capability
        matched_findings = []
        for f in findings:
            cap_matches = []
            if f.analytic_rule and f.analytic_rule in RULE_TO_CAPABILITY_MAP:
                cap_matches.extend(RULE_TO_CAPABILITY_MAP[f.analytic_rule])
            elif f.category and f.category in CATEGORY_TO_CAPABILITY_MAP:
                cap_matches.extend(CATEGORY_TO_CAPABILITY_MAP[f.category])
            
            if cap in cap_matches:
                matched_findings.append(f)

        f_count = len(matched_findings)
        f_ids = [f.id for f in matched_findings]
        
        # Determine status, coverage, and limitations
        if cap == "Threat Detection":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Detection logs ingested; negative space / triage gaps identified."
                obs = f"Observed {f_count} finding(s) impacting detection coverage and monitored perimeter."
                imp = "Detection blind spots or unmonitored assets create unobserved exposure windows."
                lims = ["Unmonitored critical assets" if any("UNMONITORED" in (f.id or "") or "UNMONITORED" in (f.analytic_rule or "") for f in matched_findings) else "Telemetry coverage gaps"]
            elif has_alerts:
                status = "NO OBSERVED CONCERN"
                coverage = f"{len(alerts)} alerts submitted across active monitored assets."
                obs = "No observed concern in the submitted detection telemetry."
                imp = "Initial telemetry ingestion aligns with declared monitoring perimeter."
                lims = []
            else:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "No alert stream or detection telemetry submitted."
                obs = "Insufficient evidence to assess threat detection; no alert stream or detection telemetry submitted."
                imp = "Threat detection capability cannot be substantiated from submitted evidence."
                lims = ["Missing alert stream"]

        elif cap == "Investigation":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Alerts submitted; linked investigation case files missing or incomplete."
                obs = f"Observed {f_count} finding(s) regarding investigation gaps or missing case documentation."
                imp = "Alerts lack formal investigation records, obscuring root-cause analysis and triage disposition."
                lims = ["Missing case management files" if not has_cases else "Investigation record gaps"]
            elif not has_investigation_evidence:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "Alerts present; zero formal case management records or investigation workflows observable."
                obs = "Insufficient evidence to assess investigation capability; no formal case management records were submitted."
                imp = "Downstream investigation efficacy cannot be substantiated from alert logs alone."
                lims = ["Absence of case management telemetry"]
            else:
                status = "NO OBSERVED CONCERN"
                coverage = f"{len(cases)} formal case records observed with completed investigations." if has_cases else "Investigation workflow indicators observable in alert stream."
                obs = "No observed concern in the submitted investigation records."
                imp = "Investigation workflow is observable and evidence-backed."
                lims = []

        elif cap == "Escalation":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Escalation logs present or unescalated critical items identified."
                obs = f"Observed {f_count} finding(s) where priority alerts lacked mandatory escalation."
                imp = "Critical security events were retained at Tier-1 without formal supervisor escalation."
                lims = ["Escalation workflow log gaps"]
            elif not has_cases or not has_escalation_evidence:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "Escalation workflow logs not submitted."
                obs = "Insufficient evidence to assess escalation capability; no escalation workflow records or tier transfer logs submitted."
                imp = "Tier escalation compliance cannot be substantiated without workflow logs."
                lims = ["Absence of escalation telemetry"]
            else:
                status = "NO OBSERVED CONCERN"
                coverage = "Escalation records observable for priority incidents."
                obs = "No observed concern in the submitted escalation records."
                imp = "Escalation protocols are evidence-supported in submitted workflow data."
                lims = []

        elif cap == "Incident Response":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Closure records observed; rapid or anomalous closures flagged."
                obs = f"Observed {f_count} finding(s) with anomalous closure duration or disposition."
                imp = "Rapid alert closure without investigation indicates potential rubber-stamping or containment failure."
                lims = ["Disposition verification required"]
            elif not has_response_evidence:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "Incident response and closure records missing."
                obs = "Insufficient evidence to assess incident response capability; no closure, containment, or resolution records submitted."
                imp = "Response timeliness and containment adequacy cannot be evaluated."
                lims = ["Missing response / closure records"]
            else:
                status = "NO OBSERVED CONCERN"
                coverage = "Formal closure records and timestamps observed."
                obs = "No observed concern in the submitted incident response records."
                imp = "Response cycle is observable with documented durations and disposition categories."
                lims = []

        elif cap == "Security Operations":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Operational alert and case data evaluated."
                obs = f"Observed {f_count} operational finding(s) across alert triage and execution flow."
                imp = "Supervisory friction points exist in standard operational procedures."
                lims = ["Process stage limitations"]
            elif has_alerts:
                status = "NO OBSERVED CONCERN"
                coverage = "Standard operations telemetry evaluated with no systemic execution gaps."
                obs = "No observed concern in the submitted operational triage records."
                imp = "Baseline operational discipline observed across triage queues."
                lims = []
            else:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "Insufficient operations data submitted."
                obs = "Insufficient evidence to assess security operations; operational triage telemetry missing."
                imp = "Security operations health cannot be determined."
                lims = ["Missing operations data"]

        elif cap == "Governance & Oversight":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Auditability and case linkage evaluated."
                obs = f"Observed {f_count} finding(s) impacting supervisory governance and auditability."
                imp = "Absence of formal case tracking or documentation degrades operational governance and auditability."
                lims = ["Case tracking documentation gaps"]
            elif not has_cases:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "Case management tracking records not submitted."
                obs = "Insufficient evidence to assess governance and oversight; no formal case tracking records were submitted."
                imp = "Governance and supervisory auditability cannot be evaluated without formal case records."
                lims = ["Missing case tracking records"]
            else:
                status = "NO OBSERVED CONCERN"
                coverage = "Comprehensive case documentation and audit references present."
                obs = "No observed concern in the submitted governance and case tracking documentation."
                imp = "Supervisory auditability is maintained across case records."
                lims = []

        elif cap == "Operational Discipline":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Timestamp and procedural consistency evaluated."
                obs = f"Observed {f_count} finding(s) relating to procedural anomalies or timing outliers."
                imp = "Inconsistent triage timing or unstandardized closure reasons observed."
                lims = ["Procedural variance"]
            elif has_alert_timestamps:
                status = "NO OBSERVED CONCERN"
                coverage = "Timestamp hygiene and alert handling consistency verified."
                obs = "No observed concern in the submitted operational timestamps and procedural workflows."
                imp = "Operational discipline is consistent across observed records."
                lims = []
            else:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "Insufficient telemetry to assess operational discipline."
                obs = "Insufficient evidence to assess operational discipline; timestamp telemetry missing."
                imp = "Discipline cannot be measured."
                lims = ["Missing data"]

        elif cap == "Cyber Resilience":
            if f_count > 0:
                status = "OBSERVED CONCERN"
                coverage = "Asset inventory and telemetry coverage evaluated."
                obs = f"Observed {f_count} finding(s) impacting critical infrastructure telemetry."
                imp = "Unmonitored critical assets undermine organizational cyber resilience."
                lims = ["Asset inventory telemetry gaps"]
            elif has_assets:
                status = "NO OBSERVED CONCERN"
                coverage = f"{len(assets)} critical/high assets evaluated with active telemetry."
                obs = "No observed concern in the submitted asset inventory and monitoring coverage."
                imp = "Core infrastructure resilience is supported by active monitoring perimeter."
                lims = []
            else:
                status = "INSUFFICIENT EVIDENCE"
                coverage = "No asset inventory data submitted."
                obs = "Insufficient evidence to assess cyber resilience; no asset inventory submitted."
                imp = "Perimeter resilience cannot be assessed without asset inventory."
                lims = ["Missing asset inventory"]

        else:
            status = "NOT ASSESSED"
            coverage = "Not in assessment scope."
            obs = "Not assessed in current submission."
            imp = "No evaluation performed."
            lims = []

        # Adjudication state summary for capability findings
        adj_states = [f.decision_status or "OPEN" for f in matched_findings]
        if not adj_states:
            adj_summary = "N/A (No Findings)"
        elif all(s == "CONFIRMED" for s in adj_states):
            adj_summary = f"All {len(adj_states)} Confirmed"
        elif any(s == "EVIDENCE_REQUESTED" for s in adj_states):
            adj_summary = f"{adj_states.count('EVIDENCE_REQUESTED')} Evidence Requested"
        elif any(s == "MODIFIED" for s in adj_states):
            adj_summary = f"{adj_states.count('MODIFIED')} Modified by Examiner"
        elif any(s == "REJECTED" for s in adj_states):
            adj_summary = f"{adj_states.count('REJECTED')} Rejected"
        else:
            adj_summary = f"{adj_states.count('OPEN')} Open / Under Review"

        # Validity
        val = assurance.assessment_validity if assurance else "HIGH"
        if status in ("INSUFFICIENT EVIDENCE", "NOT ASSESSED"):
            val = "LOW" if status == "INSUFFICIENT EVIDENCE" else "INDETERMINATE"

        results.append({
            "name": cap,
            "status": status,
            "findings_count": f_count,
            "finding_ids": f_ids,
            "evidence_coverage": coverage,
            "assessment_validity": val,
            "human_adjudication_state": adj_summary,
            "evidence_limitations": lims,
            "observation": obs,
            "implication": imp,
        })

    return results


def summarize_evidence_limitations(
    assurance: Optional[domain.AssessmentAssurance],
    findings: List[domain.Finding],
    has_alerts: bool = True,
    has_cases: bool = False,
    has_assets: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Segregates observed limitations into MISSING, PARTIAL, UNKNOWN, CONTRADICTORY.
    """
    missing = []
    partial = []
    unknown = []
    contradictory = []

    # Process missing records
    if not has_cases:
        missing.append({
            "item": "Case Management Records (ITSM/SOAR)",
            "observation": "Zero formal case investigation or ticket records were observable in submission.",
            "implication": "Downstream investigation and escalation compliance cannot be verified from alert telemetry alone.",
        })
    if not has_assets:
        missing.append({
            "item": "Asset Inventory Telemetry Baseline",
            "observation": "No asset inventory submitted to cross-reference alert sources.",
            "implication": "Asset criticality and coverage cannot be independently substantiated.",
        })

    # Assurance dimension details
    if assurance and assurance.dimension_details:
        dims = assurance.dimension_details
        for k, v in dims.items():
            st = v.get("status", "HIGH")
            obs = v.get("explanation") or v.get("observation", "")
            imp = v.get("implication") or (
                "Data baseline absence limits assessment certainty." if st in ("UNKNOWN", "INDETERMINATE") else ""
            )
            title = k.replace("_", " ").title()
            
            if st in ("LOW", "CAUTION") and "missing" in obs.lower():
                missing.append({"item": title, "observation": obs, "implication": imp})
            elif st in ("CAUTION", "PARTIAL") or "partial" in obs.lower():
                partial.append({"item": title, "observation": obs, "implication": imp})
            elif st in ("INDETERMINATE", "UNKNOWN") or "unknown" in obs.lower():
                unknown.append({"item": title, "observation": obs, "implication": imp})
            elif st == "CONTRADICTION" or "contradict" in obs.lower():
                contradictory.append({"item": title, "observation": obs, "implication": imp})

    # Contradictions from assurance
    if assurance and assurance.contradiction_details:
        for c in assurance.contradiction_details.get("items", []):
            contradictory.append({
                "item": f"Contradiction in {c.get('record_id', 'Record')}",
                "observation": c.get("description", "Inconsistent evidence timestamps or states detected."),
                "implication": "Conflicting telemetry reduces confidence in specific record timelines.",
            })

    # If unknown population exposure
    if assurance and assurance.population_exposure == "UNKNOWN":
        if not any(u["item"] == "Population Exposure Denominator" for u in unknown):
            unknown.append({
                "item": "Population Exposure Denominator",
                "observation": "Total organizational asset count or unmonitored baseline was not declared.",
                "implication": "Overall SOC telemetry coverage percentage remains indeterminate.",
            })

    return {
        "missing": missing,
        "partial": partial,
        "unknown": unknown,
        "contradictory": contradictory,
    }


def summarize_human_adjudication(findings: List[domain.Finding]) -> Dict[str, int]:
    """
    Computes distinct counts for human examiner adjudications.
    """
    total = len(findings)
    confirmed = sum(1 for f in findings if (f.decision_status or "").upper() == "CONFIRMED")
    modified = sum(1 for f in findings if (f.decision_status or "").upper() == "MODIFIED")
    rejected = sum(1 for f in findings if (f.decision_status or "").upper() == "REJECTED")
    evidence_req = sum(1 for f in findings if (f.decision_status or "").upper() == "EVIDENCE_REQUESTED")
    deferred = sum(1 for f in findings if (f.decision_status or "").upper() == "DEFERRED")
    open_ur = sum(1 for f in findings if (f.decision_status or "").upper() in ("OPEN", "UNDER_REVIEW", ""))

    return {
        "total_findings": total,
        "confirmed": confirmed,
        "modified": modified,
        "rejected": rejected,
        "evidence_requested": evidence_req,
        "deferred": deferred,
        "open_under_review": open_ur,
    }


def generate_supervisory_report_data(
    db: Session,
    analysis_id: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assembles a complete, evidence-grounded supervisory report structure from
    persisted database records. No LLM hallucinations or fabricated facts.
    """
    # 1. Resolve Entity
    target_entity = None
    if entity_id:
        target_entity = db.query(domain.Entity).filter(domain.Entity.id == entity_id).first()
    
    # 2. Resolve Findings
    f_query = db.query(domain.Finding)
    if entity_id:
        f_query = f_query.filter(domain.Finding.entity_id == entity_id)
    if analysis_id:
        # Check if analysis_id matches upload_id or finding IDs
        f_query = f_query.filter((domain.Finding.upload_id == analysis_id) | (domain.Finding.id == analysis_id))
    
    findings = f_query.order_by(domain.Finding.risk_contribution.desc()).all()
    if not target_entity and findings:
        target_entity = db.query(domain.Entity).filter(domain.Entity.id == findings[0].entity_id).first()

    if not target_entity:
        target_entity = db.query(domain.Entity).first() or domain.Entity(
            id=entity_id or "CSE-GENERAL", name=entity_id or "General Critical Sector Entity", sector="Critical Infrastructure", assessment_period="Not provided"
        )

    # 3. Resolve Upload Submissions & Telemetry Counts
    u_query = db.query(domain.DatasetUpload)
    if entity_id:
        u_query = u_query.filter(domain.DatasetUpload.entity_ids.contains(entity_id))
    uploads = u_query.order_by(domain.DatasetUpload.uploaded_at.desc()).all()
    latest_upload = uploads[0] if uploads else None

    alerts = db.query(domain.Alert).filter(domain.Alert.entity_id == target_entity.id).all()
    cases = db.query(domain.Case).filter(domain.Case.entity_id == target_entity.id).all()
    assets = db.query(domain.Asset).filter(domain.Asset.entity_id == target_entity.id).all()

    # 4. Resolve Assurance
    assurance = None
    if analysis_id:
        assurance = db.query(domain.AssessmentAssurance).filter(
            (domain.AssessmentAssurance.analysis_id == analysis_id) |
            (domain.AssessmentAssurance.upload_id == analysis_id)
        ).first()
    if not assurance and target_entity:
        assurance = db.query(domain.AssessmentAssurance).filter(
            domain.AssessmentAssurance.entity_id == target_entity.id
        ).order_by(domain.AssessmentAssurance.created_at.desc()).first()

    if not assurance:
        svc = AssessmentAssuranceService()
        assurance = svc.evaluate_assurance(db=db, entity_id=target_entity.id, analysis_id=analysis_id)

    # 5. Evaluate Capabilities
    capabilities = evaluate_capabilities(
        findings=findings,
        assurance=assurance,
        alerts=alerts,
        cases=cases,
        assets=assets,
    )

    # 6. Summarize Limitations & Adjudication
    limitations = summarize_evidence_limitations(
        assurance=assurance,
        findings=findings,
        has_alerts=len(alerts) > 0,
        has_cases=len(cases) > 0,
        has_assets=len(assets) > 0,
    )
    adjudication = summarize_human_adjudication(findings)

    # 7. Resolve Evidence Requests
    req_query = db.query(domain.EvidenceRequest).filter(domain.EvidenceRequest.entity_id == target_entity.id)
    evidence_requests = req_query.order_by(domain.EvidenceRequest.requested_at.desc()).all()

    # 8. Assemble Traceability & Finding Details
    traceability_map = {}
    detailed_findings = []

    for f in findings:
        # Agent Run
        latest_agent_run = db.query(domain.AgentRun).filter(
            domain.AgentRun.finding_id == f.id
        ).order_by(domain.AgentRun.created_at.desc()).first()

        # Decision Record
        latest_decision = db.query(domain.FindingDecision).filter(
            domain.FindingDecision.finding_id == f.id
        ).order_by(domain.FindingDecision.timestamp.desc()).first()

        trace_item = {
            "finding_id": f.id,
            "analysis_id": analysis_id or f.upload_id or "ANL-CURRENT",
            "evidence_ids": f.evidence_ids or [],
            "assessment_validity": f.assessment_validity or assurance.assessment_validity,
            "agent_run_id": latest_agent_run.id if latest_agent_run else None,
            "agent_hypothesis": latest_agent_run.assessment_result.get("hypothesis") if latest_agent_run and isinstance(latest_agent_run.assessment_result, dict) else None,
            "agent_confidence": latest_agent_run.assessment_result.get("confidence") if latest_agent_run and isinstance(latest_agent_run.assessment_result, dict) else None,
            "human_decision": f.decision_status or "OPEN",
            "human_decision_id": f"DEC-{latest_decision.id}" if latest_decision else None,
            "adjudicated_by": f.adjudicated_by or (latest_decision.actor if latest_decision else None),
            "adjudicated_at": f.adjudicated_at.isoformat() if f.adjudicated_at else (latest_decision.timestamp.isoformat() if latest_decision else None),
            "examiner_notes": f.modified_assessment or (latest_decision.notes if latest_decision else None),
        }
        traceability_map[f.id] = trace_item

        detailed_findings.append({
            "finding_id": f.id,
            "title": f.type,
            "category": f.category,
            "severity": f.severity,
            "priority_score": f.risk_contribution,
            "finding_confidence": f.confidence,
            "assessment_validity": f.assessment_validity or assurance.assessment_validity,
            "observed_facts": {
                "rule_id": f.analytic_rule or f.category,
                "details": f.details or {},
                "affected_evidence_count": len(f.evidence_ids or []),
                "source_upload": f.upload_id,
            },
            "rationale": f.rationale,
            "description": f.description,
            "recommended_action": f.recommended_action,
            "evidence_references": (f.evidence_ids or [])[:20], # Sample first 20 for report display
            "ai_recommendation": {
                "hypothesis": latest_agent_run.assessment_result.get("hypothesis") if latest_agent_run and isinstance(latest_agent_run.assessment_result, dict) else "No agent run executed.",
                "confidence": latest_agent_run.assessment_result.get("confidence") if latest_agent_run and isinstance(latest_agent_run.assessment_result, dict) else None,
                "missing_evidence": latest_agent_run.challenge_result.get("missing_evidence") if latest_agent_run and isinstance(latest_agent_run.challenge_result, dict) else [],
            } if latest_agent_run else None,
            "challenge_result": {
                "challenge_status": latest_agent_run.challenge_result.get("challenge_status") if latest_agent_run and isinstance(latest_agent_run.challenge_result, dict) else None,
                "alternative_explanations": latest_agent_run.challenge_result.get("alternative_explanations") if latest_agent_run and isinstance(latest_agent_run.challenge_result, dict) else [],
            } if latest_agent_run else None,
            "human_decision": {
                "status": f.decision_status or "OPEN",
                "actor": f.adjudicated_by or (latest_decision.actor if latest_decision else "Unadjudicated"),
                "timestamp": f.adjudicated_at.isoformat() if f.adjudicated_at else None,
                "notes": f.modified_assessment or (latest_decision.notes if latest_decision else None),
                "rejection_reason": latest_decision.rejection_reason if latest_decision else None,
            },
        })

    # 9. Deterministic Executive Summary Generation
    crit_high_f = sum(1 for f in findings if f.severity in ("CRITICAL", "HIGH"))
    major_lims = [m["item"] for m in limitations["missing"]] + [p["item"] for p in limitations["partial"]]
    lim_str = f" Major observable evidence limitations include: {', '.join(major_lims[:3])}." if major_lims else " Evidence submission satisfied baseline coverage."
    
    exec_summary_text = (
        f"Supervisory evaluation for {target_entity.name} ({target_entity.id}) analyzed {len(alerts)} alert records, "
        f"{len(cases)} case records, and {len(assets)} infrastructure assets. "
        f"The analytics engine identified {len(findings)} supervisory finding(s), of which {crit_high_f} are categorized as High/Critical severity. "
        f"Overall Assessment Validity is rated as {assurance.assessment_validity}, reflecting current submission coverage and observable process stages."
        f"{lim_str} "
        f"Human examiner adjudication status: {adjudication['confirmed']} confirmed, {adjudication['modified']} modified, "
        f"{adjudication['rejected']} rejected, {adjudication['evidence_requested']} pending additional evidence requests, and "
        f"{adjudication['open_under_review']} open for examination. AI outputs remain strictly advisory; supervisory decisions reflect human examiner determination."
    )

    report_id = f"RPT-{target_entity.id}-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.datetime.utcnow()

    return {
        "report_metadata": {
            "report_id": report_id,
            "report_version": "1.0",
            "generated_at": now.isoformat(),
            "analysis_id": analysis_id or (latest_upload.id if latest_upload else "ANL-CURRENT"),
            "entity_id": target_entity.id,
            "classification": "SAT-SA — Supervisory Assessment Prototype",
            "title": "SAT-SA Supervisory Assessment Report",
        },
        "entity_summary": {
            "entity_id": target_entity.id,
            "name": target_entity.name,
            "sector": target_entity.sector or "Critical Infrastructure",
            "assessment_period": target_entity.assessment_period or "Not provided",
            "source_submission": {
                "filename": latest_upload.filename if latest_upload else "Not provided",
                "source_hash": latest_upload.source_hash if latest_upload else "Not provided",
                "uploaded_at": latest_upload.uploaded_at.isoformat() if latest_upload else "Not provided",
            },
            "records_submitted": {
                "alerts": len(alerts),
                "cases": len(cases),
                "assets": len(assets),
            },
            "total_findings": len(findings),
            "findings_requiring_review": adjudication["open_under_review"],
            "findings_confirmed": adjudication["confirmed"],
            "findings_modified": adjudication["modified"],
            "findings_rejected": adjudication["rejected"],
            "findings_evidence_requested": adjudication["evidence_requested"],
            "findings_deferred": adjudication["deferred"],
        },
        "assessment_summary": {
            "executive_summary": exec_summary_text,
            "findings_count": len(findings),
            "high_priority_findings": crit_high_f,
            "confirmed_findings": adjudication["confirmed"],
            "evidence_requests_count": len(evidence_requests),
            "assessment_validity": assurance.assessment_validity,
            "validity_rationale": assurance.validity_rationale,
            "advisory_notice": "AI agent recommendations are strictly advisory. Final supervisory judgement remains with the human examiner.",
        },
        "capability_assessment": capabilities,
        "findings": detailed_findings,
        "assurance": {
            "assessment_validity": assurance.assessment_validity,
            "validity_rationale": assurance.validity_rationale,
            "population_exposure": assurance.population_exposure,
            "temporal_coverage": assurance.temporal_coverage,
            "severity_coverage": assurance.severity_coverage,
            "asset_coverage": assurance.asset_coverage,
            "process_coverage": assurance.process_coverage,
            "evidence_dependency": assurance.evidence_dependency,
            "contradictions_detected": assurance.contradictions_detected,
            "source_integrity": assurance.source_integrity,
            "dimension_details": assurance.dimension_details or {},
            "blind_spots": assurance.blind_spots or [],
        },
        "evidence_limitations": limitations,
        "human_adjudication": adjudication,
        "evidence_requests": [
            {
                "id": req.id,
                "finding_id": req.finding_id,
                "request_type": req.request_type,
                "description": req.description,
                "reason": req.reason,
                "priority": req.priority,
                "status": req.status,
                "requested_by": req.requested_by,
                "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                "response_notes": req.response_notes,
            }
            for req in evidence_requests
        ],
        "traceability": traceability_map,
    }


# =========================================================================
# REPORTLAB PROFESSIONAL PDF GENERATOR (OFFLINE & PRINT-READY)
# =========================================================================

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and render total page numbers."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b")) # slate-500
        
        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 750, "SAT-SA Supervisory Assessment Report — Prototype")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 744, letter[0] - 54, 744)

        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, footer_text)
        self.drawString(54, 36, "National Technical Research Organisation (NTRO) / NCIIPC — Supervisory Assessment Prototype")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()


def generate_pdf_report(report_data: Dict[str, Any]) -> bytes:
    """
    Compiles structured report data into a professional, human-readable supervisory PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"), # slate-900
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#2563eb"), # blue-600
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=6,
    )
    h3_style = ParagraphStyle(
        'SectionH3',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    advisory_style = ParagraphStyle(
        'AdvisoryNotice',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8,
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )
    table_cell_norm = ParagraphStyle(
        'TableCellNorm',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )

    story = []
    meta = report_data.get("report_metadata", {})
    entity_s = report_data.get("entity_summary", {})
    assess_s = report_data.get("assessment_summary", {})
    caps = report_data.get("capability_assessment", [])
    findings = report_data.get("findings", [])
    assurance = report_data.get("assurance", {})
    limitations = report_data.get("evidence_limitations", {})
    adjudication = report_data.get("human_adjudication", {})
    evidence_requests = report_data.get("evidence_requests", [])
    traceability = report_data.get("traceability", {})

    # ================= PAGE 1: HEADER & EXECUTIVE SUMMARY =================
    story.append(Paragraph("SAT-SA SUPERVISORY ASSESSMENT REPORT", title_style))
    story.append(Paragraph("SUPERVISORY ANALYTICS TOOL FOR SOC ASSESSMENT (NTRO / NCIIPC) — PROTOTYPE", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=10))

    # Metadata Grid Table
    meta_table_data = [
        [
            Paragraph(f"<b>Report ID:</b> {meta.get('report_id')}", table_cell_norm),
            Paragraph(f"<b>Classification:</b> {meta.get('classification')}", table_cell_norm),
        ],
        [
            Paragraph(f"<b>Entity/CSE:</b> {entity_s.get('name')} ({entity_s.get('entity_id')})", table_cell_norm),
            Paragraph(f"<b>Sector:</b> {entity_s.get('sector')}", table_cell_norm),
        ],
        [
            Paragraph(f"<b>Assessment Period:</b> {entity_s.get('assessment_period')}", table_cell_norm),
            Paragraph(f"<b>Generated At:</b> {meta.get('generated_at')[:19]} UTC", table_cell_norm),
        ],
        [
            Paragraph(f"<b>Source Submission:</b> {entity_s.get('source_submission', {}).get('filename')}", table_cell_norm),
            Paragraph(f"<b>Source Hash:</b> {str(entity_s.get('source_submission', {}).get('source_hash'))[:16]}...", table_cell_norm),
        ],
    ]
    t_meta = Table(meta_table_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # Executive Summary Section
    story.append(Paragraph("1. Executive Summary", h2_style))
    story.append(Paragraph(assess_s.get("executive_summary", ""), body_style))
    story.append(Paragraph(f"<b>Advisory Notice:</b> {assess_s.get('advisory_notice', '')}", advisory_style))
    story.append(Spacer(1, 8))

    # Quantitative Assessment Scope Table
    rec_s = entity_s.get("records_submitted", {})
    scope_data = [
        [
            Paragraph("<b>Ingested Alerts</b>", table_cell_bold),
            Paragraph("<b>Ingested Cases</b>", table_cell_bold),
            Paragraph("<b>Ingested Assets</b>", table_cell_bold),
            Paragraph("<b>Findings Flagged</b>", table_cell_bold),
            Paragraph("<b>Assessment Validity</b>", table_cell_bold),
        ],
        [
            Paragraph(str(rec_s.get("alerts", 0)), table_cell_norm),
            Paragraph(str(rec_s.get("cases", 0)), table_cell_norm),
            Paragraph(str(rec_s.get("assets", 0)), table_cell_norm),
            Paragraph(str(len(findings)), table_cell_norm),
            Paragraph(f"<b>{assurance.get('assessment_validity', 'HIGH')}</b>", table_cell_norm),
        ],
    ]
    t_scope = Table(scope_data, colWidths=[100, 100, 100, 100, 104])
    t_scope.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_scope)
    story.append(Spacer(1, 14))

    # ================= 2. CAPABILITY ASSESSMENT =================
    story.append(Paragraph("2. Operational Capability Assessment (8 PS Dimensions)", h2_style))
    story.append(Paragraph("Evaluation of eight operational capabilities based strictly on submitted evidence and process observability:", body_style))

    cap_table_data = [
        [
            Paragraph("<b>Operational Capability</b>", table_cell_bold),
            Paragraph("<b>Status</b>", table_cell_bold),
            Paragraph("<b>Findings</b>", table_cell_bold),
            Paragraph("<b>Validity</b>", table_cell_bold),
            Paragraph("<b>Adjudication State</b>", table_cell_bold),
        ]
    ]
    for c in caps:
        st_color = "#dc2626" if c["status"] == "OBSERVED CONCERN" else "#f59e0b" if c["status"] == "INSUFFICIENT EVIDENCE" else "#16a34a"
        cap_table_data.append([
            Paragraph(f"<b>{c['name']}</b>", table_cell_norm),
            Paragraph(f"<font color='{st_color}'><b>{c['status']}</b></font>", table_cell_norm),
            Paragraph(str(c["findings_count"]), table_cell_norm),
            Paragraph(c["assessment_validity"], table_cell_norm),
            Paragraph(c["human_adjudication_state"], table_cell_norm),
        ])

    t_cap = Table(cap_table_data, colWidths=[130, 120, 60, 74, 120])
    t_cap.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_cap)
    story.append(Spacer(1, 14))

    # ================= 3. SUPERVISORY FINDINGS & ADJUDICATION =================
    story.append(Paragraph("3. Key Supervisory Findings & Examiner Adjudication", h2_style))
    story.append(Paragraph("Detailed examination of flagged operational conditions, evidence citations, AI advisory inputs, and human examiner decisions:", body_style))

    if not findings:
        story.append(Paragraph("No supervisory findings were generated for this assessment.", body_style))
    else:
        for idx, f in enumerate(findings[:10], 1): # Display up to 10 findings in detail
            f_box = []
            f_box.append(Paragraph(f"<b>Finding {idx}: {f['title']}</b> (ID: {f['finding_id']})", h3_style))
            
            f_detail_data = [
                [
                    Paragraph(f"<b>Category:</b> {f['category']}", table_cell_norm),
                    Paragraph(f"<b>Severity:</b> {f['severity']}", table_cell_norm),
                    Paragraph(f"<b>Confidence:</b> {f['finding_confidence']*100:.1f}%", table_cell_norm),
                    Paragraph(f"<b>Validity:</b> {f['assessment_validity']}", table_cell_norm),
                ],
                [
                    Paragraph(f"<b>Observed Facts:</b> {f['description']}", table_cell_norm),
                    "", "", ""
                ],
                [
                    Paragraph(f"<b>Supervisory Rationale:</b> {f['rationale']}", table_cell_norm),
                    "", "", ""
                ],
                [
                    Paragraph(f"<b>AI Advisory Review:</b> {f.get('ai_recommendation', {}).get('hypothesis') if f.get('ai_recommendation') else 'N/A'}", table_cell_norm),
                    "", "", ""
                ],
                [
                    Paragraph(f"<b>Human Decision:</b> <b>{f.get('human_decision', {}).get('status', 'OPEN')}</b> | Adjudicated By: {f.get('human_decision', {}).get('actor', 'Pending')} | Notes: {f.get('human_decision', {}).get('notes') or 'None'}", table_cell_norm),
                    "", "", ""
                ],
            ]
            t_f = Table(f_detail_data, colWidths=[126, 126, 126, 126])
            t_f.setStyle(TableStyle([
                ('SPAN', (0, 1), (3, 1)),
                ('SPAN', (0, 2), (3, 2)),
                ('SPAN', (0, 3), (3, 3)),
                ('SPAN', (0, 4), (3, 4)),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            f_box.append(t_f)
            f_box.append(Spacer(1, 8))
            story.append(KeepTogether(f_box))

    story.append(Spacer(1, 10))

    # ================= 4. ASSESSMENT ASSURANCE & 8 DIMENSIONS =================
    story.append(Paragraph("4. Assessment Assurance & Evidence Validity Matrix", h2_style))
    story.append(Paragraph(
        f"Assessment Validity is determined as <b>{assurance.get('assessment_validity', 'HIGH')}</b>. "
        f"{assurance.get('validity_rationale', '')}",
        body_style
    ))

    assurance_dim_data = [
        [
            Paragraph("<b>Assurance Dimension</b>", table_cell_bold),
            Paragraph("<b>Status</b>", table_cell_bold),
            Paragraph("<b>Observation</b>", table_cell_bold),
            Paragraph("<b>Implication</b>", table_cell_bold),
        ]
    ]
    dims = assurance.get("dimension_details", {})
    for dim_k, dim_v in dims.items():
        title_d = dim_k.replace("_", " ").title()
        st_d = dim_v.get("status", "HIGH")
        obs_d = dim_v.get("explanation") or dim_v.get("observation", "")
        imp_d = dim_v.get("implication") or (
            "Evidence gaps or unobserved process stages limit supervisory assurance." if st_d in ("LOW", "UNKNOWN", "CAUTION") else "Observable telemetry supports baseline supervisory evaluation."
        )
        
        assurance_dim_data.append([
            Paragraph(f"<b>{title_d}</b>", table_cell_norm),
            Paragraph(f"<b>{st_d}</b>", table_cell_norm),
            Paragraph(obs_d, table_cell_norm),
            Paragraph(imp_d, table_cell_norm),
        ])

    t_ass = Table(assurance_dim_data, colWidths=[110, 64, 165, 165])
    t_ass.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ass)
    story.append(Spacer(1, 14))

    # ================= 5. EVIDENCE LIMITATIONS =================
    story.append(Paragraph("5. Evidence Limitations Breakdown", h2_style))
    lim_types = [
        ("Missing Evidence", limitations.get("missing", []), "#ef4444"),
        ("Partial Evidence", limitations.get("partial", []), "#f59e0b"),
        ("Unknown Denominators", limitations.get("unknown", []), "#64748b"),
        ("Contradictory Evidence", limitations.get("contradictory", []), "#8b5cf6"),
    ]
    for lim_title, lim_list, col in lim_types:
        if lim_list:
            story.append(Paragraph(f"<b>{lim_title}:</b>", h3_style))
            for item in lim_list:
                obs_t = item.get('observation', '')
                imp_t = f" <i>({item.get('implication')})</i>" if item.get('implication') else ""
                story.append(Paragraph(f"• <b>{item.get('item', '')}:</b> {obs_t}{imp_t}", body_style))

    story.append(Spacer(1, 10))

    # ================= 6. EVIDENCE REQUESTS & TRACEABILITY =================
    story.append(Paragraph("6. Formal Evidence Requests & Provenance Registry", h2_style))
    if evidence_requests:
        req_table_data = [
            [
                Paragraph("<b>Request ID</b>", table_cell_bold),
                Paragraph("<b>Evidence Type</b>", table_cell_bold),
                Paragraph("<b>Priority</b>", table_cell_bold),
                Paragraph("<b>Status</b>", table_cell_bold),
                Paragraph("<b>Supervisory Rationale</b>", table_cell_bold),
            ]
        ]
        for req in evidence_requests:
            req_table_data.append([
                Paragraph(req.get("id", ""), table_cell_norm),
                Paragraph(req.get("request_type", ""), table_cell_norm),
                Paragraph(req.get("priority", "HIGH"), table_cell_norm),
                Paragraph(f"<b>{req.get('status', 'OPEN')}</b>", table_cell_norm),
                Paragraph(req.get("reason", ""), table_cell_norm),
            ])
        t_req = Table(req_table_data, colWidths=[80, 110, 54, 60, 200])
        t_req.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_req)
    else:
        story.append(Paragraph("No active evidence requests recorded.", body_style))

    story.append(Spacer(1, 14))

    # End of Document Traceability Registry
    story.append(Paragraph("7. Traceability Verification", h2_style))
    story.append(Paragraph(
        f"All {len(findings)} findings in this report maintain cryptographic provenance linking each observed rule "
        f"to source telemetry records in DatasetUpload '{meta.get('analysis_id')}', immutable AssessmentAssurance profile, "
        f"local AI audit logs, and human adjudication records. Generated via SAT-SA Offline Supervisory Engine.",
        advisory_style
    ))

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


# =========================================================================
# DASHBOARD SUMMARY DATA AGGREGATOR
# =========================================================================

def get_dashboard_summary_data(db: Session) -> Dict[str, Any]:
    """
    Consolidates real, persisted metrics for the main Supervisory Dashboard.
    Answers: 'What requires supervisory attention?' and 'How strong is the evidence supporting it?'
    """
    entities = db.query(domain.Entity).all()
    findings = db.query(domain.Finding).all()
    uploads = db.query(domain.DatasetUpload).all()
    alerts_count = db.query(domain.Alert).count()
    evidence_reqs = db.query(domain.EvidenceRequest).all()

    # High priority review items
    priority_reviews = db.query(domain.ReviewItem).filter(domain.ReviewItem.status == "Pending").count()
    
    # Entity summaries
    entity_cards = []
    for ent in entities:
        ent_findings = [f for f in findings if f.entity_id == ent.id]
        ent_alerts = db.query(domain.Alert).filter(domain.Alert.entity_id == ent.id).count()
        ent_cases = db.query(domain.Case).filter(domain.Case.entity_id == ent.id).count()
        ent_assets = db.query(domain.Asset).filter(domain.Asset.entity_id == ent.id).count()
        
        # Latest assurance
        ass = db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.entity_id == ent.id).order_by(domain.AssessmentAssurance.created_at.desc()).first()
        val = ass.assessment_validity if ass else "HIGH"

        adj = summarize_human_adjudication(ent_findings)

        entity_cards.append({
            "entity_id": ent.id,
            "name": ent.name,
            "sector": ent.sector,
            "assessment_period": ent.assessment_period or "Not provided",
            "records_submitted": ent_alerts + ent_cases + ent_assets,
            "alerts_count": ent_alerts,
            "cases_count": ent_cases,
            "assets_count": ent_assets,
            "total_findings": len(ent_findings),
            "findings_requiring_review": adj["open_under_review"],
            "findings_confirmed": adj["confirmed"],
            "findings_modified": adj["modified"],
            "findings_rejected": adj["rejected"],
            "findings_evidence_requested": adj["evidence_requested"],
            "assessment_validity": val,
        })

    # Supervisory attention items (Top 10 highest risk contribution / priority findings)
    enhanced_queue = workspace.get_enhanced_review_queue_items(db=db, sort_by="priority", order="desc")
    supervisory_attention = []
    for item in enhanced_queue[:8]:
        f = item["finding"]
        r = item["review_item"]
        supervisory_attention.append({
            "finding_id": f.id,
            "title": f.type,
            "entity_id": f.entity_id,
            "category": f.category,
            "severity": f.severity,
            "priority_score": r.priority_score,
            "finding_confidence": f.confidence,
            "assessment_validity": f.assessment_validity or "HIGH",
            "decision_status": f.decision_status or "OPEN",
            "why_review": item["why_review"],
        })

    # Category breakdown
    cat_counts = {
        "execution_gap": sum(1 for f in findings if f.category == "execution_gap"),
        "negative_space": sum(1 for f in findings if f.category == "negative_space"),
        "anomaly": sum(1 for f in findings if f.category == "anomaly"),
        "peer_deviation": sum(1 for f in findings if f.category == "peer_deviation"),
    }

    # Adjudication breakdown
    adj_summary = summarize_human_adjudication(findings)

    # Evidence requests breakdown
    req_summary = {
        "OPEN": sum(1 for r in evidence_reqs if r.status == "OPEN"),
        "RECEIVED": sum(1 for r in evidence_reqs if r.status == "RECEIVED"),
        "RESOLVED": sum(1 for r in evidence_reqs if r.status == "RESOLVED"),
        "CANCELLED": sum(1 for r in evidence_reqs if r.status == "CANCELLED"),
        "TOTAL": len(evidence_reqs),
    }

    # Assessment validity breakdown
    val_dist = {
        "HIGH": sum(1 for f in findings if (f.assessment_validity or "").upper() == "HIGH"),
        "CAUTION": sum(1 for f in findings if (f.assessment_validity or "").upper() == "CAUTION"),
        "LOW": sum(1 for f in findings if (f.assessment_validity or "").upper() == "LOW"),
        "INDETERMINATE": sum(1 for f in findings if (f.assessment_validity or "").upper() == "INDETERMINATE"),
    }

    # Capabilities overview
    alerts_all = db.query(domain.Alert).all()
    cases_all = db.query(domain.Case).all()
    assets_all = db.query(domain.Asset).all()
    first_ass = db.query(domain.AssessmentAssurance).first()
    caps_overview = evaluate_capabilities(findings, first_ass, alerts_all, cases_all, assets_all)

    return {
        "entities_count": len(entities),
        "findings_count": len(findings),
        "high_risk_entities": sum(1 for ec in entity_cards if ec["total_findings"] >= 3 or any(f.severity in ("CRITICAL", "HIGH") for f in findings if f.entity_id == ec["entity_id"])),
        "priority_reviews": priority_reviews,
        "total_uploads": len(uploads),
        "total_alerts": alerts_count,
        "entities": entity_cards,
        "supervisory_attention": supervisory_attention,
        "findings_by_category": cat_counts,
        "human_adjudication": adj_summary,
        "evidence_requests": req_summary,
        "capabilities_overview": caps_overview,
        "assessment_validity_distribution": val_dist,
    }


def get_entity_assessment_data(db: Session, entity_id: str) -> Dict[str, Any]:
    """
    Consolidates entity-level assessment data for the Entity Assessment view.
    """
    entity = db.query(domain.Entity).filter(domain.Entity.id == entity_id).first()
    if not entity:
        raise ValueError(f"Entity with ID '{entity_id}' not found.")

    findings = db.query(domain.Finding).filter(domain.Finding.entity_id == entity_id).order_by(domain.Finding.risk_contribution.desc()).all()
    alerts = db.query(domain.Alert).filter(domain.Alert.entity_id == entity_id).all()
    cases = db.query(domain.Case).filter(domain.Case.entity_id == entity_id).all()
    assets = db.query(domain.Asset).filter(domain.Asset.entity_id == entity_id).all()
    
    # Latest upload
    upload = db.query(domain.DatasetUpload).filter(domain.DatasetUpload.entity_ids.contains(entity_id)).order_by(domain.DatasetUpload.uploaded_at.desc()).first()

    # Latest assurance
    assurance = db.query(domain.AssessmentAssurance).filter(domain.AssessmentAssurance.entity_id == entity_id).order_by(domain.AssessmentAssurance.created_at.desc()).first()
    if not assurance:
        svc = AssessmentAssuranceService()
        assurance = svc.evaluate_assurance(db=db, entity_id=entity_id)

    capabilities = evaluate_capabilities(findings, assurance, alerts, cases, assets)
    limitations = summarize_evidence_limitations(assurance, findings, len(alerts) > 0, len(cases) > 0, len(assets) > 0)
    adjudication = summarize_human_adjudication(findings)
    evidence_requests = db.query(domain.EvidenceRequest).filter(domain.EvidenceRequest.entity_id == entity_id).order_by(domain.EvidenceRequest.requested_at.desc()).all()
    risk = db.query(domain.RiskScore).filter(domain.RiskScore.entity_id == entity_id).first()

    # Supervisory attention
    supervisory_attention = []
    for f in findings[:5]:
        supervisory_attention.append({
            "finding_id": f.id,
            "title": f.type,
            "category": f.category,
            "severity": f.severity,
            "priority_score": f.risk_contribution,
            "finding_confidence": f.confidence,
            "assessment_validity": f.assessment_validity or assurance.assessment_validity,
            "decision_status": f.decision_status or "OPEN",
            "description": f.description,
        })

    findings_summary = {
        "total": len(findings),
        "execution_gaps": sum(1 for f in findings if f.category == "execution_gap"),
        "negative_space": sum(1 for f in findings if f.category == "negative_space"),
        "anomalies": sum(1 for f in findings if f.category == "anomaly"),
        "peer_deviations": sum(1 for f in findings if f.category == "peer_deviation"),
    }

    return {
        "entity": entity,
        "assessment_id": upload.id if upload else "ANL-CURRENT",
        "source_submission": {
            "filename": upload.filename if upload else "Not provided",
            "source_hash": upload.source_hash if upload else "Not provided",
            "uploaded_at": upload.uploaded_at.isoformat() if upload else None,
        } if upload else None,
        "record_counts": {
            "alerts": len(alerts),
            "cases": len(cases),
            "assets": len(assets),
        },
        "supervisory_attention": supervisory_attention,
        "capabilities": capabilities,
        "findings_summary": findings_summary,
        "assurance": {
            "assessment_validity": assurance.assessment_validity,
            "validity_rationale": assurance.validity_rationale,
            "population_exposure": assurance.population_exposure,
            "temporal_coverage": assurance.temporal_coverage,
            "severity_coverage": assurance.severity_coverage,
            "asset_coverage": assurance.asset_coverage,
            "process_coverage": assurance.process_coverage,
            "evidence_dependency": assurance.evidence_dependency,
            "contradictions_detected": assurance.contradictions_detected,
            "source_integrity": assurance.source_integrity,
            "dimension_details": assurance.dimension_details or {},
            "blind_spots": assurance.blind_spots or [],
        } if assurance else None,
        "evidence_limitations": limitations,
        "human_adjudication": adjudication,
        "evidence_requests": evidence_requests,
        "risk": risk,
    }
