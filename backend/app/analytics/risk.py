from typing import List, Dict, Any, Optional
from app.models import domain
from app.analytics.config import RISK_WEIGHTS


class RiskScoreCalculator:
    """
    Deterministic 7-factor supervisory prioritization risk score calculator.

    DISCLAIMER:
    This score is an internal prototype supervisory prioritization metric
    designed to highlight entities requiring human examiner triage.
    It is NOT an official or statutory cyber risk rating.
    """

    def calculate_entity_risk(
        self,
        entity_id: str,
        findings: List[domain.Finding],
        benchmarks: List[domain.Benchmark],
        assets: List[domain.Asset],
        alerts: List[domain.Alert],
    ) -> domain.RiskScore:
        """
        Calculate multi-factor risk score for an entity based on generated findings,
        benchmark deviations, and operational telemetry.
        """
        entity_findings = [f for f in findings if f.entity_id == entity_id]

        # 1. Execution Gap Risk (0-100)
        eg_findings = [f for f in entity_findings if f.category == "execution_gap"]
        eg_risk = min(100.0, sum(f.risk_contribution for f in eg_findings) * 1.8)

        # 2. Negative Space Risk (0-100)
        ns_findings = [f for f in entity_findings if f.category == "negative_space"]
        ns_risk = min(100.0, sum(f.risk_contribution for f in ns_findings) * 1.5)

        # 3. Investigation Risk (0-100)
        total_alerts = len(alerts)
        uninvestigated_count = sum(1 for a in alerts if not a.investigation_started)
        inv_risk = min(100.0, (uninvestigated_count / max(1, total_alerts)) * 100.0) if total_alerts > 0 else 10.0

        # 4. Escalation Risk (0-100)
        critical_alerts = [a for a in alerts if a.severity == "Critical"]
        if critical_alerts:
            unescalated_crit = sum(1 for a in critical_alerts if not a.escalated)
            esc_risk = min(100.0, (unescalated_crit / len(critical_alerts)) * 100.0)
        else:
            esc_risk = 10.0

        # 5. Anomaly Risk (0-100)
        anom_findings = [f for f in entity_findings if f.category == "anomaly"]
        anom_risk = min(100.0, sum(f.risk_contribution for f in anom_findings) * 2.0)

        # 6. Peer Deviation Risk (0-100)
        entity_bms = [b for b in benchmarks if b.entity_id == entity_id]
        sig_devs = sum(1 for b in entity_bms if b.status_label == "SIGNIFICANT DEVIATION")
        peer_risk = min(100.0, sig_devs * 30.0)

        # 7. Monitoring Coverage Risk (0-100)
        if assets:
            unmonitored_assets = sum(1 for ast in assets if not ast.has_telemetry)
            mon_risk = min(100.0, (unmonitored_assets / len(assets)) * 100.0)
        else:
            mon_risk = 10.0

        # Overall Weighted Score (0-100)
        overall = (
            eg_risk * RISK_WEIGHTS["execution_gap"]
            + ns_risk * RISK_WEIGHTS["negative_space"]
            + inv_risk * RISK_WEIGHTS["investigation"]
            + esc_risk * RISK_WEIGHTS["escalation"]
            + anom_risk * RISK_WEIGHTS["anomaly"]
            + peer_risk * RISK_WEIGHTS["peer_deviation"]
            + mon_risk * RISK_WEIGHTS["monitoring_coverage"]
        )
        overall_score = round(min(100.0, max(0.0, overall)), 1)

        return domain.RiskScore(
            entity_id=entity_id,
            overall_score=overall_score,
            execution_gap_risk=round(eg_risk, 1),
            negative_space_risk=round(ns_risk, 1),
            investigation_risk=round(inv_risk, 1),
            escalation_risk=round(esc_risk, 1),
            anomaly_risk=round(anom_risk, 1),
            peer_deviation_risk=round(peer_risk, 1),
            monitoring_coverage_risk=round(mon_risk, 1),
        )
