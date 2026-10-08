from typing import List, Dict, Any, Optional
from app.models import domain
from app.analytics.config import (
    RULE_NS_CRITICAL_ASSET_NO_TELEMETRY,
    RULE_NS_ALERTS_WITHOUT_CASE,
    RULE_NS_INVESTIGATION_MISSING_ESCALATION,
)


class NegativeSpaceDetector:
    """
    Detector for supervisory negative-space indicators (absence of expected operational evidence).
    Uses neutral supervisory language that clearly distinguishes observed data absence
    from confirmed operational failure.
    """

    def analyze_entity(
        self,
        entity_id: str,
        assets: List[domain.Asset],
        alerts: List[domain.Alert],
        cases: List[domain.Case],
        upload_id: Optional[str] = None,
    ) -> List[domain.Finding]:
        """
        Analyze entity data for absent operational evidence.
        """
        findings: List[domain.Finding] = []

        # 1. Critical assets with absent telemetry / logging evidence
        critical_assets = [ast for ast in assets if ast.criticality in ["Critical", "High"]]
        dormant_critical_assets = [ast for ast in critical_assets if not ast.has_telemetry]

        if dormant_critical_assets:
            ast_ids = [ast.id for ast in dormant_critical_assets]
            finding_id = f"NS-{entity_id}-CRIT-ASSET"
            findings.append(
                domain.Finding(
                    id=finding_id,
                    entity_id=entity_id,
                    type="Missing Telemetry on Critical Assets",
                    category="negative_space",
                    severity="CRITICAL" if any(a.criticality == "Critical" for a in dormant_critical_assets) else "HIGH",
                    confidence=0.92,
                    description=(
                        f"Required evidence was not observed in the submitted dataset: "
                        f"{len(dormant_critical_assets)} critical/high asset(s) have no active telemetry log indicators."
                    ),
                    rationale=(
                        "Continuous telemetry is expected for designated critical infrastructure assets. "
                        "Absence of telemetry logs in the submitted dataset warrants supervisory clarification."
                    ),
                    evidence_ids=ast_ids,
                    risk_contribution=min(30.0, 12.0 + len(dormant_critical_assets) * 3.0),
                    recommended_action=(
                        "Request sensor deployment logs, SIEM agent heartbeats, and asset inventory reconciliations "
                        "for the unmonitored assets."
                    ),
                    status="Requires Review",
                    upload_id=upload_id,
                    analytic_rule=RULE_NS_CRITICAL_ASSET_NO_TELEMETRY,
                    details={
                        "rule": RULE_NS_CRITICAL_ASSET_NO_TELEMETRY,
                        "total_critical_assets": len(critical_assets),
                        "missing_telemetry_count": len(dormant_critical_assets),
                        "asset_ids": ast_ids[:10],
                    },
                )
            )

        # 2. Critical/High alerts with absent formal case/investigation records
        case_alert_ids = {c.alert_id for c in cases if c.alert_id}
        alerts_without_cases = [
            a for a in alerts
            if a.severity in ["Critical", "High"]
            and a.id not in case_alert_ids
            and not a.investigation_started
        ]

        if alerts_without_cases:
            alert_ids = [a.id for a in alerts_without_cases]
            finding_id = f"NS-{entity_id}-ALERTS-NOCASE"
            findings.append(
                domain.Finding(
                    id=finding_id,
                    entity_id=entity_id,
                    type="Absence of Formal Case Records for Priority Alerts",
                    category="negative_space",
                    severity="HIGH",
                    confidence=0.89,
                    description=(
                        f"Evidence gap detected: no formal investigation or case record was observed "
                        f"for {len(alerts_without_cases)} High/Critical alert(s) in the submitted telemetry."
                    ),
                    rationale=(
                        "Operational compliance requires priority detections to possess linked investigation case files. "
                        "This observed absence indicates potential telemetry ingestion gaps or unformalized triage."
                    ),
                    evidence_ids=alert_ids[:20],
                    risk_contribution=min(22.0, 8.0 + len(alerts_without_cases) * 1.5),
                    recommended_action="Validate whether ticketing or SOAR system exports were fully included in the CSE data submission.",
                    status="Requires Review",
                    upload_id=upload_id,
                    analytic_rule=RULE_NS_ALERTS_WITHOUT_CASE,
                    details={
                        "rule": RULE_NS_ALERTS_WITHOUT_CASE,
                        "flagged_count": len(alerts_without_cases),
                        "total_priority_alerts": sum(1 for a in alerts if a.severity in ["Critical", "High"]),
                    },
                )
            )

        return findings
