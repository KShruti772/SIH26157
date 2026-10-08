import math
from typing import List, Dict, Any, Optional
from app.models import domain
from app.analytics.config import (
    MIN_ANOMALY_SAMPLE_SIZE,
    ANOMALY_IQR_MULTIPLIER,
    RULE_ANOMALY_INVESTIGATION_DURATION,
    RULE_ANOMALY_CLOSURE_DURATION,
)


def _compute_iqr_stats(values: List[float]) -> Optional[Dict[str, float]]:
    """Compute statistical percentiles, median, and IQR bounds."""
    if len(values) < MIN_ANOMALY_SAMPLE_SIZE:
        return None

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    q1 = percentile(0.25)
    median = percentile(0.50)
    q3 = percentile(0.75)
    iqr = q3 - q1
    mean = sum(sorted_vals) / n

    lower_bound = max(0.0, q1 - ANOMALY_IQR_MULTIPLIER * iqr)
    upper_bound = q3 + ANOMALY_IQR_MULTIPLIER * iqr

    return {
        "n": n,
        "mean": mean,
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
    }


class AnomalyDetector:
    """
    Statistical anomaly detector for operational durations and rates.
    Uses IQR and robust median deviation with strict sample size enforcement.
    """

    def __init__(self, min_sample_size: int = MIN_ANOMALY_SAMPLE_SIZE):
        self.min_sample_size = min_sample_size

    def analyze_entity(
        self,
        entity_id: str,
        alerts: List[domain.Alert],
        cases: List[domain.Case],
        upload_id: Optional[str] = None,
    ) -> List[domain.Finding]:
        """
        Analyze entity operational records for statistical anomalies.
        """
        findings: List[domain.Finding] = []

        # 1. Statistical anomaly on investigation duration
        inv_durations = []
        alert_map = {}
        for a in alerts:
            dur = a.investigation_duration_mins
            if dur is not None and dur > 0:
                inv_durations.append(dur)
                alert_map[a.id] = dur

        for c in cases:
            dur = c.investigation_duration
            if dur is not None and dur > 0:
                inv_durations.append(dur)
                alert_map[c.id] = dur

        inv_stats = _compute_iqr_stats(inv_durations)
        if inv_stats is not None and inv_stats["iqr"] > 0:
            # Look for extreme fast closure anomalies (investigation duration < lower_bound and < 5 mins)
            fast_outliers = [aid for aid, dur in alert_map.items() if dur < inv_stats["lower_bound"] and dur <= 5.0]
            if fast_outliers:
                obs_avg = sum(alert_map[aid] for aid in fast_outliers) / len(fast_outliers)
                deviation = ((obs_avg - inv_stats["median"]) / inv_stats["median"]) * 100.0 if inv_stats["median"] > 0 else 0.0
                finding_id = f"ANOM-{entity_id}-INV-DUR"
                findings.append(
                    domain.Finding(
                        id=finding_id,
                        entity_id=entity_id,
                        type="Statistical Anomaly: Atypically Short Investigation Duration",
                        category="anomaly",
                        severity="MEDIUM" if len(fast_outliers) < 5 else "HIGH",
                        confidence=0.85,
                        description=(
                            f"Statistical outlier detected: {len(fast_outliers)} investigation(s) completed in "
                            f"an average of {obs_avg:.1f} minutes, significantly below the entity baseline median "
                            f"of {inv_stats['median']:.1f} minutes (IQR lower bound: {inv_stats['lower_bound']:.1f} mins)."
                        ),
                        rationale=(
                            f"Metric: Investigation Duration | Baseline Median: {inv_stats['median']:.1f}m | "
                            f"Observed: {obs_avg:.1f}m | Deviation: {deviation:.1f}%. "
                            "Unusually fast closures may signify superficial triage or automated mass-closing."
                        ),
                        evidence_ids=fast_outliers[:15],
                        risk_contribution=min(18.0, 6.0 + len(fast_outliers) * 1.2),
                        recommended_action="Review analyst investigation logs and triage thoroughness for the outlier cases.",
                        status="Requires Review",
                        upload_id=upload_id,
                        analytic_rule=RULE_ANOMALY_INVESTIGATION_DURATION,
                        details={
                            "metric": "investigation_duration_mins",
                            "sample_size": inv_stats["n"],
                            "baseline_median": round(inv_stats["median"], 2),
                            "baseline_mean": round(inv_stats["mean"], 2),
                            "iqr_lower": round(inv_stats["lower_bound"], 2),
                            "iqr_upper": round(inv_stats["upper_bound"], 2),
                            "observed_avg": round(obs_avg, 2),
                            "deviation_percent": round(deviation, 2),
                            "outlier_count": len(fast_outliers),
                        },
                    )
                )

        # 2. Statistical anomaly on closure duration
        close_durations = []
        close_map = {}
        for a in alerts:
            dur = a.closure_duration_mins
            if dur is not None and dur > 0:
                close_durations.append(dur)
                close_map[a.id] = dur

        close_stats = _compute_iqr_stats(close_durations)
        if close_stats is not None and close_stats["iqr"] > 0:
            prolonged_outliers = [aid for aid, dur in close_map.items() if dur > close_stats["upper_bound"] and dur > 120.0]
            if prolonged_outliers:
                obs_avg = sum(close_map[aid] for aid in prolonged_outliers) / len(prolonged_outliers)
                deviation = ((obs_avg - close_stats["median"]) / close_stats["median"]) * 100.0 if close_stats["median"] > 0 else 0.0
                finding_id = f"ANOM-{entity_id}-CLOSE-DUR"
                findings.append(
                    domain.Finding(
                        id=finding_id,
                        entity_id=entity_id,
                        type="Statistical Anomaly: Prolonged Alert Closure Duration",
                        category="anomaly",
                        severity="LOW" if len(prolonged_outliers) < 5 else "MEDIUM",
                        confidence=0.82,
                        description=(
                            f"Statistical outlier detected: {len(prolonged_outliers)} alert(s) exhibited prolonged closure "
                            f"duration averaging {obs_avg:.1f} minutes, exceeding the upper IQR threshold of "
                            f"{close_stats['upper_bound']:.1f} minutes (median: {close_stats['median']:.1f} mins)."
                        ),
                        rationale=(
                            f"Metric: Closure Duration | Baseline Median: {close_stats['median']:.1f}m | "
                            f"Observed: {obs_avg:.1f}m | Deviation: +{deviation:.1f}%. "
                            "May indicate triage bottlenecks or orphaned alerts."
                        ),
                        evidence_ids=prolonged_outliers[:15],
                        risk_contribution=min(14.0, 4.0 + len(prolonged_outliers) * 1.0),
                        recommended_action="Inspect queue backlog and verify analyst assignment procedures for prolonged alerts.",
                        status="Requires Review",
                        upload_id=upload_id,
                        analytic_rule=RULE_ANOMALY_CLOSURE_DURATION,
                        details={
                            "metric": "closure_duration_mins",
                            "sample_size": close_stats["n"],
                            "baseline_median": round(close_stats["median"], 2),
                            "baseline_mean": round(close_stats["mean"], 2),
                            "iqr_lower": round(close_stats["lower_bound"], 2),
                            "iqr_upper": round(close_stats["upper_bound"], 2),
                            "observed_avg": round(obs_avg, 2),
                            "deviation_percent": round(deviation, 2),
                            "outlier_count": len(prolonged_outliers),
                        },
                    )
                )

        return findings
