import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import domain
from app.analytics.config import (
    MIN_PEER_BENCHMARK_ENTITIES,
    PEER_DEVIATION_SIGNIFICANT_THRESHOLD,
    PEER_DEVIATION_WATCH_THRESHOLD,
)


def _median(vals: List[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _average(vals: List[float]) -> float:
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _percentile_rank(val: float, cohort: List[float]) -> float:
    if not cohort:
        return 50.0
    n = len(cohort)
    count_less = sum(1 for v in cohort if v < val)
    count_equal = sum(1 for v in cohort if v == val)
    return round(((count_less + 0.5 * count_equal) / n) * 100.0, 1)


class CohortBenchmarker:
    """
    Computes cohort peer benchmarks across entities.
    Produces peer medians, averages, percentiles, and supervisory deviation indicators.
    """

    def __init__(self, min_entities: int = MIN_PEER_BENCHMARK_ENTITIES):
        self.min_entities = min_entities

    def calculate_cohort_benchmarks(
        self,
        entity_records: Dict[str, Dict[str, Any]],
        upload_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculates benchmarks across entities.
        entity_records: Dict[entity_id -> {"alerts": [...], "cases": [...], "assets": [...]}]
        Returns:
            {
                "benchmarks": List[domain.Benchmark],
                "peer_findings": List[domain.Finding],
                "insufficient_sample": bool
            }
        """
        entity_ids = list(entity_records.keys())
        if len(entity_ids) < self.min_entities:
            return {
                "benchmarks": [],
                "peer_findings": [],
                "insufficient_sample": True,
                "message": f"Insufficient peer sample: {len(entity_ids)} entity observed (requires at least {self.min_entities} for peer comparison).",
            }

        # 1. Compute raw metrics for each entity
        raw_entity_metrics: Dict[str, Dict[str, float]] = {}

        for eid, data in entity_records.items():
            alerts = data.get("alerts", [])
            cases = data.get("cases", [])
            assets = data.get("assets", [])

            # Metric: Escalation Rate (%)
            total_alerts = len(alerts)
            escalated_alerts = sum(1 for a in alerts if a.escalated)
            esc_rate = (escalated_alerts / total_alerts * 100.0) if total_alerts > 0 else 0.0

            # Metric: Monitoring Coverage (%)
            total_assets = len(assets)
            monitored_assets = sum(1 for ast in assets if ast.has_telemetry)
            cov_rate = (monitored_assets / total_assets * 100.0) if total_assets > 0 else 100.0

            # Metric: Median Investigation Duration (mins)
            inv_durs = [a.investigation_duration_mins for a in alerts if a.investigation_duration_mins is not None and a.investigation_duration_mins > 0]
            for c in cases:
                if c.investigation_duration is not None and c.investigation_duration > 0:
                    inv_durs.append(c.investigation_duration)
            med_inv = _median(inv_durs) if inv_durs else 30.0

            # Metric: Median Closure Duration (mins)
            close_durs = [a.closure_duration_mins for a in alerts if a.closure_duration_mins is not None and a.closure_duration_mins > 0]
            med_close = _median(close_durs) if close_durs else 45.0

            # Metric: Acknowledgment Rate (%)
            ack_count = sum(1 for a in alerts if a.acknowledged)
            ack_rate = (ack_count / total_alerts * 100.0) if total_alerts > 0 else 100.0

            raw_entity_metrics[eid] = {
                "Escalation Rate": round(esc_rate, 1),
                "Monitoring Coverage": round(cov_rate, 1),
                "Investigation Duration (mins)": round(med_inv, 1),
                "Closure Duration (mins)": round(med_close, 1),
                "Acknowledgment Rate": round(ack_rate, 1),
            }

        # 2. Compute cohort baselines for each metric
        metric_names = [
            "Escalation Rate",
            "Monitoring Coverage",
            "Investigation Duration (mins)",
            "Closure Duration (mins)",
            "Acknowledgment Rate",
        ]

        cohort_values: Dict[str, List[float]] = {m: [] for m in metric_names}
        for eid in entity_ids:
            for m in metric_names:
                cohort_values[m].append(raw_entity_metrics[eid][m])

        cohort_medians = {m: _median(cohort_values[m]) for m in metric_names}
        cohort_averages = {m: _average(cohort_values[m]) for m in metric_names}

        # 3. Create Benchmark objects and identify significant peer deviations
        benchmarks: List[domain.Benchmark] = []
        peer_findings: List[domain.Finding] = []

        for eid in entity_ids:
            for m in metric_names:
                ent_val = raw_entity_metrics[eid][m]
                peer_med = cohort_medians[m]
                peer_avg = cohort_averages[m]
                percentile = _percentile_rank(ent_val, cohort_values[m])

                if peer_med != 0:
                    dev_pct = round(((ent_val - peer_med) / peer_med) * 100.0, 1)
                else:
                    dev_pct = 0.0

                # Determine status
                abs_dev = abs(dev_pct)
                if abs_dev >= PEER_DEVIATION_SIGNIFICANT_THRESHOLD:
                    status_label = "SIGNIFICANT DEVIATION"
                elif abs_dev >= PEER_DEVIATION_WATCH_THRESHOLD:
                    status_label = "WATCH"
                else:
                    status_label = "NORMAL"

                bm = domain.Benchmark(
                    entity_id=eid,
                    metric=m,
                    entity_value=ent_val,
                    peer_median=round(peer_med, 1),
                    peer_average=round(peer_avg, 1),
                    percentile=percentile,
                    deviation_percent=dev_pct,
                    status_label=status_label,
                )
                benchmarks.append(bm)

                # If significant deviation on critical operational metrics, generate peer finding
                if status_label == "SIGNIFICANT DEVIATION" and m in ["Escalation Rate", "Monitoring Coverage"]:
                    if dev_pct < 0:  # Below peer median
                        finding_id = f"PEER-{eid}-{m[:3].upper()}"
                        peer_findings.append(
                            domain.Finding(
                                id=finding_id,
                                entity_id=eid,
                                type=f"Peer Cohort Deviation: {m}",
                                category="peer_deviation",
                                severity="HIGH" if abs_dev > 50 else "MEDIUM",
                                confidence=0.87,
                                description=(
                                    f"Entity {eid} exhibited {m.lower()} of {ent_val}%, which deviates by "
                                    f"{dev_pct}% from the peer median of {peer_med:.1f}%."
                                ),
                                rationale=(
                                    f"Peer comparison indicator: Entity deviates from peer baseline ({peer_med:.1f}%) "
                                    f"and warrants supervisory review to verify operational alignment."
                                ),
                                evidence_ids=[],
                                risk_contribution=15.0,
                                recommended_action=f"Review entity operating procedures regarding {m.lower()} in comparison to sector peers.",
                                status="Requires Review",
                                upload_id=upload_id,
                                analytic_rule=f"PEER_BENCHMARK_{m[:4].upper()}_V1",
                                details={
                                    "metric": m,
                                    "entity_value": ent_val,
                                    "peer_median": round(peer_med, 1),
                                    "peer_average": round(peer_avg, 1),
                                    "deviation_percent": dev_pct,
                                },
                            )
                        )

        return {
            "benchmarks": benchmarks,
            "peer_findings": peer_findings,
            "insufficient_sample": False,
            "cohort_medians": cohort_medians,
        }
