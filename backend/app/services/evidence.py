import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.models import domain


def _serialize_model(obj: Any) -> Dict[str, Any]:
    """Helper to convert SQLAlchemy model instance into clean dictionary."""
    if obj is None:
        return {}
    res = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, (datetime.datetime, datetime.date)):
            res[col.name] = val.isoformat()
        else:
            res[col.name] = val
    return res


def resolve_evidence_records(evidence_ids: List[str], db: Session) -> Dict[str, List[Any]]:
    """
    Resolve a list of evidence IDs to their corresponding database models across
    Alert, Case, and Asset tables. Also resolves direct child/parent linkages.
    """
    if not evidence_ids:
        return {"alerts": [], "cases": [], "assets": []}

    alerts = db.query(domain.Alert).filter(domain.Alert.id.in_(evidence_ids)).all()
    cases = db.query(domain.Case).filter(domain.Case.id.in_(evidence_ids)).all()
    assets = db.query(domain.Asset).filter(domain.Asset.id.in_(evidence_ids)).all()

    # Discover linked cases for alerts if not explicitly in evidence_ids
    alert_ids = [a.id for a in alerts]
    if alert_ids:
        linked_cases = db.query(domain.Case).filter(domain.Case.alert_id.in_(alert_ids)).all()
        existing_case_ids = {c.id for c in cases}
        for lc in linked_cases:
            if lc.id not in existing_case_ids:
                cases.append(lc)
                existing_case_ids.add(lc.id)

    # Discover linked assets for alerts if not explicitly in evidence_ids
    asset_ids_from_alerts = [a.asset_id for a in alerts if a.asset_id]
    if asset_ids_from_alerts:
        linked_assets = db.query(domain.Asset).filter(domain.Asset.id.in_(asset_ids_from_alerts)).all()
        existing_asset_ids = {ast.id for ast in assets}
        for la in linked_assets:
            if la.id not in existing_asset_ids:
                assets.append(la)
                existing_asset_ids.add(la.id)

    return {
        "alerts": alerts,
        "cases": cases,
        "assets": assets,
    }


def calculate_evidence_completeness(
    category: str,
    alerts: List[domain.Alert],
    cases: List[domain.Case],
    assets: List[domain.Asset],
) -> float:
    """
    Deterministically calculate an evidence completeness score (0.0 to 1.0)
    evaluating whether expected operational trace records and timestamps are present.
    """
    if category == "negative_space":
        # For negative space, the absence is the subject; if assets exist or zero telemetry is shown,
        # completeness reflects the confidence of verifying absence.
        if assets:
            telemetry_count = sum(1 for a in assets if a.has_telemetry)
            return round(max(0.5, 1.0 - (len(assets) - telemetry_count) / (len(assets) * 2)), 2)
        return 0.70

    total_checks = 0
    passed_checks = 0

    for alert in alerts:
        total_checks += 4
        # Check 1: Alert has valid timestamp
        if alert.timestamp is not None:
            passed_checks += 1
        # Check 2: Asset reference is cataloged
        if alert.asset_id and any(ast.id == alert.asset_id for ast in assets):
            passed_checks += 1
        elif not alert.asset_id:
            # Asset id missing from alert
            pass
        # Check 3: Investigation record or indicator
        if alert.investigation_started or any(c.alert_id == alert.id for c in cases):
            passed_checks += 1
        # Check 4: Closure info available
        if alert.closed_at or alert.closure_duration_mins is not None:
            passed_checks += 1

    for case in cases:
        total_checks += 3
        if case.created_at is not None:
            passed_checks += 1
        if case.investigation_duration is not None or case.investigator:
            passed_checks += 1
        if case.closure_time is not None or case.closure_reason:
            passed_checks += 1

    if total_checks == 0:
        return 0.50

    return round(passed_checks / total_checks, 2)


def identify_missing_links(
    finding: domain.Finding,
    alerts: List[domain.Alert],
    cases: List[domain.Case],
    assets: List[domain.Asset],
) -> List[str]:
    """
    Identify specific missing links or unobserved records in the operational chain.
    """
    missing = []
    
    if finding.category == "negative_space":
        if not alerts and not cases:
            missing.append(f"No alert or incident case records observed for entity {finding.entity_id} in assessment window.")
        unmonitored_assets = [ast.id for ast in assets if not ast.has_telemetry]
        if unmonitored_assets:
            missing.append(f"Telemetry log stream missing for {len(unmonitored_assets)} critical asset(s): {', '.join(unmonitored_assets[:5])}")
        return missing

    case_alert_ids = {c.alert_id for c in cases if c.alert_id}
    asset_ids = {ast.id for ast in assets}

    for alert in alerts:
        if alert.id not in case_alert_ids and not alert.investigation_started:
            missing.append(f"Formal investigation or case record absent for alert {alert.id} ({alert.severity}).")
        
        if alert.asset_id and alert.asset_id not in asset_ids:
            missing.append(f"Referenced asset {alert.asset_id} is not documented in entity asset inventory.")
        
        if alert.severity == "Critical" and not alert.escalated:
            missing.append(f"Escalation event record missing for Critical alert {alert.id}.")

        if alert.closed_at is None and alert.closure_duration_mins is None:
            missing.append(f"Alert closure timestamp not recorded for {alert.id}.")

    return missing


def get_evidence_trace(finding_id: str, db: Session) -> Dict[str, Any]:
    """
    Generate the full operational evidence trace for a supervisory finding.
    Reconstructs the chain: CSE -> Asset -> Alert -> Case -> Investigation -> Escalation.
    """
    finding = db.query(domain.Finding).filter(domain.Finding.id == finding_id).first()
    if not finding:
        return {
            "finding_id": finding_id,
            "finding": None,
            "trace": [],
            "missing_links": ["Finding record not found"],
            "evidence_completeness": 0.0,
            "alerts": [],
            "cases": [],
            "assets": [],
        }

    evidence_ids = finding.evidence_ids or []
    resolved = resolve_evidence_records(evidence_ids, db)
    alerts = resolved["alerts"]
    cases = resolved["cases"]
    assets = resolved["assets"]

    # If evidence_ids was empty, look for entity-associated assets if negative space
    if not alerts and not cases and not assets and finding.category == "negative_space":
        assets = db.query(domain.Asset).filter(domain.Asset.entity_id == finding.entity_id).all()

    completeness = calculate_evidence_completeness(finding.category, alerts, cases, assets)
    missing_links = identify_missing_links(finding, alerts, cases, assets)

    # Build sequential trace entries with real data
    trace = []
    for ast in assets:
        trace.append({
            "type": "asset",
            "id": ast.id,
            "entity_id": ast.entity_id,
            "timestamp": None,
            "data": _serialize_model(ast),
            "summary": f"Asset {ast.id} ({ast.type or 'Unknown'}) - Criticality: {ast.criticality or 'Unspecified'}, Telemetry: {ast.has_telemetry}",
        })

    for alert in alerts:
        trace.append({
            "type": "alert",
            "id": alert.id,
            "entity_id": alert.entity_id,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
            "data": _serialize_model(alert),
            "summary": f"Alert {alert.id} ({alert.severity} - {alert.category}) generated at {alert.timestamp or 'Unknown'}",
        })

    for case in cases:
        trace.append({
            "type": "case",
            "id": case.id,
            "entity_id": case.entity_id,
            "timestamp": case.created_at.isoformat() if case.created_at else None,
            "data": _serialize_model(case),
            "summary": f"Case {case.id} created at {case.created_at or 'Unknown'}, Investigator: {case.investigator or 'Unassigned'}",
        })

    return {
        "finding_id": finding.id,
        "finding": _serialize_model(finding),
        "trace": trace,
        "missing_links": missing_links,
        "evidence_completeness": completeness,
        "alerts": [_serialize_model(a) for a in alerts],
        "cases": [_serialize_model(c) for c in cases],
        "assets": [_serialize_model(ast) for ast in assets],
    }
