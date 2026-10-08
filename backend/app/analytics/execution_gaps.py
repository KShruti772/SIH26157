import uuid
from typing import List, Dict, Any, Optional
from app.models import domain
from app.analytics.config import (
    PROTOTYPE_CRITICAL_CLOSURE_MINUTES,
    PROTOTYPE_HIGH_CLOSURE_MINUTES,
    RULE_EG_CRITICAL_FAST_CLOSURE,
    RULE_EG_CRITICAL_UNESCALATED,
    RULE_EG_UNINVESTIGATED_ACK,
)


class ExecutionGapDetector:
    """
    Deterministic detector for operational execution gaps in SOC telemetry.
    Identifies discrepancies between expected operational procedures and recorded actions.
    """

    def __init__(
        self,
        critical_closure_threshold_mins: float = PROTOTYPE_CRITICAL_CLOSURE_MINUTES,
        high_closure_threshold_mins: float = PROTOTYPE_HIGH_CLOSURE_MINUTES,
    ):
        self.critical_closure_threshold_mins = critical_closure_threshold_mins
        self.high_closure_threshold_mins = high_closure_threshold_mins

    def analyze_entity(
        self,
        entity_id: str,
        alerts: List[domain.Alert],
        cases: List[domain.Case],
        upload_id: Optional[str] = None,
    ) -> List[domain.Finding]:
        """
        Run all execution gap analytical rules against the entity's records.
        """
        findings: List[domain.Finding] = []

        # 1. Critical alerts closed under prototype threshold without escalation
        fast_closed_crit = []
        for a in alerts:
            if a.severity == "Critical" and not a.escalated:
                dur = a.closure_duration_mins
                if dur is None and a.closed_at and a.timestamp:
                    dur = (a.closed_at - a.timestamp).total_seconds() / 60.0
                if dur is not None and dur <= self.critical_closure_threshold_mins:
                    fast_closed_crit.append((a, dur))

        if fast_closed_crit:
            avg_dur = sum(d for _, d in fast_closed_crit) / len(fast_closed_crit)
            ev_ids = [a.id for a, _ in fast_closed_crit]
            finding_id = f"EG-{entity_id}-FAST-CRIT"
            findings.append(
                domain.Finding(
                    id=finding_id,
                    entity_id=entity_id,
                    type="Rapid Critical Alert Closure Without Escalation",
                    category="execution_gap",
                    severity="HIGH" if len(fast_closed_crit) < 5 else "CRITICAL",
                    confidence=0.91,
                    description=(
                        f"{len(fast_closed_crit)} Critical severity alert(s) were closed within an average of "
                        f"{avg_dur:.1f} minutes without escalation. Configured prototype threshold is "
                        f"{self.critical_closure_threshold_mins:.0f} minutes."
                    ),
                    rationale=(
                        "Critical alerts are expected to undergo thorough multi-tier assessment or escalation. "
                        "Rapid closure without escalation is an operational indicator requiring supervisory review."
                    ),
                    evidence_ids=ev_ids,
                    risk_contribution=min(25.0, 10.0 + len(fast_closed_crit) * 1.5),
                    recommended_action="Review SOC analyst triage notes, disposition logs, and escalation justification for the flagged critical alerts.",
                    status="Requires Review",
                    upload_id=upload_id,
                    analytic_rule=RULE_EG_CRITICAL_FAST_CLOSURE,
                    details={
                        "rule": RULE_EG_CRITICAL_FAST_CLOSURE,
                        "flagged_count": len(fast_closed_crit),
                        "average_duration_mins": round(avg_dur, 2),
                        "threshold_mins": self.critical_closure_threshold_mins,
                    },
                )
            )

        # 2. Critical alerts investigated but closed without escalation (not already flagged above)
        fast_crit_ids = {a.id for a, _ in fast_closed_crit}
        unescalated_investigated_crit = [
            a for a in alerts
            if a.severity == "Critical"
            and not a.escalated
            and (a.investigation_started or any(c.alert_id == a.id for c in cases))
            and a.id not in fast_crit_ids
        ]

        if unescalated_investigated_crit:
            ev_ids = [a.id for a in unescalated_investigated_crit]
            finding_id = f"EG-{entity_id}-UNESC-CRIT"
            findings.append(
                domain.Finding(
                    id=finding_id,
                    entity_id=entity_id,
                    type="Critical Alerts Closed Without Escalation",
                    category="execution_gap",
                    severity="HIGH",
                    confidence=0.88,
                    description=(
                        f"{len(unescalated_investigated_crit)} Critical severity alert(s) underwent investigation "
                        f"but were closed without recorded escalation to Tier-2 / Tier-3 incident handlers."
                    ),
                    rationale=(
                        "Supervisory baseline expects high-impact or critical security events to involve escalated "
                        "oversight before definitive closure."
                    ),
                    evidence_ids=ev_ids,
                    risk_contribution=min(20.0, 8.0 + len(unescalated_investigated_crit) * 1.2),
                    recommended_action="Verify escalation criteria alignment and audit SOC tier handover procedures for critical events.",
                    status="Requires Review",
                    upload_id=upload_id,
                    analytic_rule=RULE_EG_CRITICAL_UNESCALATED,
                    details={
                        "rule": RULE_EG_CRITICAL_UNESCALATED,
                        "flagged_count": len(unescalated_investigated_crit),
                    },
                )
            )

        # 3. High/Critical alerts acknowledged but lacking investigation records
        case_alert_ids = {c.alert_id for c in cases if c.alert_id}
        uninvestigated_ack = [
            a for a in alerts
            if a.severity in ["High", "Critical"]
            and a.acknowledged
            and not a.investigation_started
            and a.id not in case_alert_ids
        ]

        if uninvestigated_ack:
            ev_ids = [a.id for a in uninvestigated_ack]
            finding_id = f"EG-{entity_id}-UNINV-ACK"
            findings.append(
                domain.Finding(
                    id=finding_id,
                    entity_id=entity_id,
                    type="Acknowledged Priority Alerts Lacking Investigation",
                    category="execution_gap",
                    severity="HIGH",
                    confidence=0.86,
                    description=(
                        f"{len(uninvestigated_ack)} High/Critical alert(s) were acknowledged in the console "
                        f"but have no recorded investigation or case tracking evidence."
                    ),
                    rationale=(
                        "Acknowledging an alert without initiating an investigation creates an operational gap where triage may have stalled."
                    ),
                    evidence_ids=ev_ids,
                    risk_contribution=min(18.0, 6.0 + len(uninvestigated_ack) * 1.0),
                    recommended_action="Audit triage queues to ensure acknowledged high-priority alerts are assigned and investigated.",
                    status="Requires Review",
                    upload_id=upload_id,
                    analytic_rule=RULE_EG_UNINVESTIGATED_ACK,
                    details={
                        "rule": RULE_EG_UNINVESTIGATED_ACK,
                        "flagged_count": len(uninvestigated_ack),
                    },
                )
            )

        return findings
