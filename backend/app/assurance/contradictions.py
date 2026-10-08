from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models import domain


def detect_evidence_contradictions(
    alerts: List[domain.Alert],
    cases: List[domain.Case],
    assets: List[domain.Asset],
) -> Dict[str, Any]:
    """
    Deterministically detects internal contradictions and inconsistencies within submitted records.
    Explicitly distinguishes:
      - MISSING: An expected field or record is not supplied (NOT a contradiction).
      - INCONSISTENT: State transitions or associated metadata have discrepancies.
      - CONTRADICTORY: Direct mutually exclusive statements between correlated records.
    """
    contradictions: List[Dict[str, Any]] = []
    inconsistencies: List[Dict[str, Any]] = []

    case_by_alert = {c.alert_id: c for c in cases if c.alert_id}
    asset_by_id = {ast.id: ast for ast in assets if ast.id}

    # 1. Alert vs Case Escalation Contradiction
    for alert in alerts:
        linked_case = case_by_alert.get(alert.id)
        if linked_case is not None:
            # If Alert says escalated = True but linked Case explicitly says escalation_status = False (or vice-versa)
            if alert.escalated is True and linked_case.escalation_status is False:
                contradictions.append({
                    "type": "CONTRADICTION",
                    "entity_id": alert.entity_id,
                    "record_ids": [alert.id, linked_case.id],
                    "fields_involved": ["alert.escalated", "case.escalation_status"],
                    "observed_values": {"alert.escalated": True, "case.escalation_status": False},
                    "explanation": f"Alert {alert.id} is flagged as escalated, but linked Case {linked_case.id} records escalation_status=False.",
                })
            elif alert.escalated is False and linked_case.escalation_status is True:
                contradictions.append({
                    "type": "CONTRADICTION",
                    "entity_id": alert.entity_id,
                    "record_ids": [alert.id, linked_case.id],
                    "fields_involved": ["alert.escalated", "case.escalation_status"],
                    "observed_values": {"alert.escalated": False, "case.escalation_status": True},
                    "explanation": f"Alert {alert.id} is recorded as unescalated, but linked Case {linked_case.id} records escalation_status=True.",
                })

        # 2. Inconsistent Triage State: Acknowledged False but Investigation True
        if alert.acknowledged is False and alert.investigation_started is True:
            inconsistencies.append({
                "type": "INCONSISTENCY",
                "entity_id": alert.entity_id,
                "record_ids": [alert.id],
                "fields_involved": ["alert.acknowledged", "alert.investigation_started"],
                "observed_values": {"acknowledged": False, "investigation_started": True},
                "explanation": f"Alert {alert.id} indicates investigation started without prior recorded acknowledgment.",
            })

    # 3. Case Chronological Contradiction (created_at > closure_time)
    for c in cases:
        if c.created_at and c.closure_time and c.created_at > c.closure_time:
            contradictions.append({
                "type": "CONTRADICTION",
                "entity_id": c.entity_id,
                "record_ids": [c.id],
                "fields_involved": ["case.created_at", "case.closure_time"],
                "observed_values": {
                    "created_at": c.created_at.isoformat(),
                    "closure_time": c.closure_time.isoformat(),
                },
                "explanation": f"Case {c.id} created timestamp ({c.created_at}) occurs after recorded closure timestamp ({c.closure_time}).",
            })

        # 4. Case Inconsistency: Closure reason/duration present without closure timestamp
        if c.closure_reason and c.closure_time is None and c.investigation_duration and c.investigation_duration > 0:
            inconsistencies.append({
                "type": "INCONSISTENCY",
                "entity_id": c.entity_id,
                "record_ids": [c.id],
                "fields_involved": ["case.closure_reason", "case.closure_time"],
                "observed_values": {"closure_reason": c.closure_reason, "closure_time": None},
                "explanation": f"Case {c.id} specifies closure disposition '{c.closure_reason}' but lacks a definitive closure timestamp.",
            })

    total_issues = len(contradictions) + len(inconsistencies)
    status = "PRESENT" if contradictions else ("INCONSISTENCIES_ONLY" if inconsistencies else "NONE")

    return {
        "count": len(contradictions),
        "inconsistency_count": len(inconsistencies),
        "total_issues": total_issues,
        "status": status,
        "contradictions": contradictions,
        "inconsistencies": inconsistencies,
        "explanation": (
            f"Detected {len(contradictions)} direct contradiction(s) and {len(inconsistencies)} state transition inconsistency(ies)."
            if total_issues > 0 else "No internal evidence contradictions observed in submitted records."
        ),
    }
