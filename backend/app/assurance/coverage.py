from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models import domain
from app.assurance.config import (
    COVERAGE_FULL,
    COVERAGE_PARTIAL,
    COVERAGE_LOW,
    COVERAGE_AVAILABLE,
    COVERAGE_UNKNOWN,
    POPULATION_EXPOSURE_HIGH_THRESHOLD,
    POPULATION_EXPOSURE_CAUTION_THRESHOLD,
    SEVERITY_IMBALANCE_RATIO_THRESHOLD,
)


def evaluate_population_exposure(
    declared_population: Optional[Dict[str, Any]],
    observable_counts: Dict[str, int],
) -> Dict[str, Any]:
    """
    Evaluate observable population vs claimed/declared population.
    CRITICAL RULE: Never invent a denominator if none was supplied.
    """
    if not declared_population:
        return {
            "status": COVERAGE_UNKNOWN,
            "value": None,
            "claimed_population": None,
            "observable_population": observable_counts.get("alerts", 0),
            "explanation": "Population exposure could not be fully assessed because no declared population was supplied.",
        }

    claimed = (
        declared_population.get("claimed_alert_count")
        or declared_population.get("declared_population")
        or declared_population.get("expected_alerts")
    )

    if not claimed or claimed <= 0:
        return {
            "status": COVERAGE_UNKNOWN,
            "value": None,
            "claimed_population": None,
            "observable_population": observable_counts.get("alerts", 0),
            "explanation": "Population exposure could not be fully assessed because no valid declared population count was supplied.",
        }

    observable = observable_counts.get("alerts", 0)
    ratio = round(min(1.0, observable / claimed), 3)

    if ratio >= POPULATION_EXPOSURE_HIGH_THRESHOLD:
        status = COVERAGE_FULL
    elif ratio >= POPULATION_EXPOSURE_CAUTION_THRESHOLD:
        status = COVERAGE_PARTIAL
    else:
        status = COVERAGE_LOW

    return {
        "status": status,
        "value": ratio,
        "claimed_population": claimed,
        "observable_population": observable,
        "explanation": f"Observable records represent {ratio * 100:.1f}% of declared population ({observable:,} of {claimed:,} claimed records).",
    }


def evaluate_temporal_coverage(
    date_start: Optional[datetime],
    date_end: Optional[datetime],
    declared_window: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate temporal span of observable data against declared assessment window.
    """
    if not date_start or not date_end:
        return {
            "status": COVERAGE_UNKNOWN,
            "observable_start": None,
            "observable_end": None,
            "span_days": 0,
            "explanation": "Temporal coverage unknown: no valid timestamp range detected in submitted records.",
        }

    span_seconds = (date_end - date_start).total_seconds()
    span_days = round(span_seconds / 86400.0, 1)

    if declared_window and "start" in declared_window and "end" in declared_window:
        dec_start = declared_window["start"]
        dec_end = declared_window["end"]
        if isinstance(dec_start, str):
            dec_start = datetime.fromisoformat(dec_start)
        if isinstance(dec_end, str):
            dec_end = datetime.fromisoformat(dec_end)
        dec_span = max(1.0, (dec_end - dec_start).total_seconds() / 86400.0)
        ratio = round(min(1.0, span_days / dec_span), 2)
        status = COVERAGE_FULL if ratio >= 0.9 else (COVERAGE_PARTIAL if ratio >= 0.5 else COVERAGE_LOW)
        explanation = f"Observable temporal span covers {span_days} days ({ratio * 100:.0f}% of declared {dec_span:.0f}-day assessment window)."
    else:
        status = COVERAGE_AVAILABLE
        explanation = f"Observable telemetry spans {span_days} days ({date_start.strftime('%Y-%m-%d')} to {date_end.strftime('%Y-%m-%d')})."

    return {
        "status": status,
        "observable_start": date_start.isoformat(),
        "observable_end": date_end.isoformat(),
        "span_days": span_days,
        "explanation": explanation,
    }


def evaluate_severity_coverage(alerts: List[domain.Alert]) -> Dict[str, Any]:
    """
    Evaluate observable coverage across severity tiers.
    """
    if not alerts:
        return {
            "status": COVERAGE_UNKNOWN,
            "distribution": {},
            "total_alerts": 0,
            "explanation": "No alert telemetry available to evaluate severity coverage.",
        }

    total = len(alerts)
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Unknown": 0}
    for a in alerts:
        sev = a.severity or "Unknown"
        counts[sev] = counts.get(sev, 0) + 1

    pcts = {k: round((v / total) * 100.0, 1) for k, v in counts.items() if v > 0}
    
    # Check for representation of priority severities
    has_crit = counts.get("Critical", 0) > 0
    has_high = counts.get("High", 0) > 0
    max_pct = max(pcts.values()) if pcts else 0

    if max_pct >= (SEVERITY_IMBALANCE_RATIO_THRESHOLD * 100.0):
        status = COVERAGE_PARTIAL
        explanation = f"Severe severity imbalance: {max_pct:.1f}% of observable evidence is concentrated in a single severity category."
    elif has_crit and has_high:
        status = COVERAGE_FULL
        explanation = f"Multi-tier severity coverage represented across {len(pcts)} severity tiers ({counts['Critical']} Critical, {counts['High']} High)."
    elif has_crit or has_high:
        status = COVERAGE_PARTIAL
        explanation = "Partial severity coverage: High/Critical detections observed, but some tiers have minimal representation."
    else:
        status = COVERAGE_LOW
        explanation = "Low priority severity coverage: No High or Critical detections observed in dataset."

    return {
        "status": status,
        "distribution": counts,
        "percentages": pcts,
        "total_alerts": total,
        "explanation": explanation,
    }


def evaluate_asset_coverage(
    assets: List[domain.Asset],
    alerts: List[domain.Alert],
) -> Dict[str, Any]:
    """
    Evaluate observable asset coverage and telemetry visibility.
    """
    total_assets = len(assets)
    if total_assets == 0:
        return {
            "status": COVERAGE_UNKNOWN,
            "total_assets": 0,
            "critical_assets": 0,
            "monitored_assets": 0,
            "explanation": "No asset inventory records available in submitted dataset.",
        }

    critical_assets = [a for a in assets if a.criticality in ["Critical", "High"]]
    monitored_assets = [a for a in assets if a.has_telemetry]
    alert_asset_ids = {a.asset_id for a in alerts if a.asset_id}
    active_in_alerts = [a for a in assets if a.id in alert_asset_ids]

    cov_ratio = round(len(monitored_assets) / total_assets, 2)
    crit_monitored = [a for a in critical_assets if a.has_telemetry]
    crit_ratio = round(len(crit_monitored) / max(1, len(critical_assets)), 2) if critical_assets else 1.0

    if cov_ratio >= 0.9 and crit_ratio >= 0.9:
        status = COVERAGE_FULL
        explanation = f"Strong asset coverage: {len(monitored_assets)} of {total_assets} assets ({cov_ratio * 100:.0f}%) have active telemetry streams."
    elif cov_ratio > 0.0:
        status = COVERAGE_PARTIAL
        explanation = f"Partial asset coverage: {len(monitored_assets)} of {total_assets} assets monitored; {len(critical_assets) - len(crit_monitored)} critical asset(s) lack telemetry."
    else:
        status = COVERAGE_LOW
        explanation = f"Low asset coverage: 0% of cataloged assets have active telemetry."

    return {
        "status": status,
        "total_assets": total_assets,
        "critical_assets": len(critical_assets),
        "monitored_assets": len(monitored_assets),
        "assets_with_alerts": len(active_in_alerts),
        "coverage_ratio": cov_ratio,
        "critical_coverage_ratio": crit_ratio,
        "explanation": explanation,
    }


def evaluate_process_coverage(
    alerts: List[domain.Alert],
    cases: List[domain.Case],
) -> Dict[str, Any]:
    """
    Evaluate evidence presence across operational stages: Detection -> Investigation -> Escalation -> Closure.
    Uses cautious non-accusatory supervisory language.
    """
    stages_observed = []
    visibility_gaps = []

    # 1. Detection Stage
    if alerts:
        stages_observed.append("Detection")
    else:
        visibility_gaps.append("No detection alert telemetry was observable in the submitted dataset.")

    # 2. Investigation Stage
    has_investigation = any(a.investigation_started for a in alerts) or any(c.investigation_duration is not None for c in cases) or len(cases) > 0
    if has_investigation:
        stages_observed.append("Investigation")
    else:
        visibility_gaps.append("No formal investigation or case records were observable in the submitted dataset.")

    # 3. Escalation Stage
    has_escalation = any(a.escalated for a in alerts) or any(c.escalation_status for c in cases)
    if has_escalation:
        stages_observed.append("Escalation")
    else:
        visibility_gaps.append("No escalation evidence was observable in the submitted dataset.")

    # 4. Closure Stage
    has_closure = any(a.closed_at is not None or a.closure_duration_mins is not None for a in alerts) or any(c.closure_time is not None for c in cases)
    if has_closure:
        stages_observed.append("Closure")
    else:
        visibility_gaps.append("No alert or case closure disposition evidence was observable in the submitted dataset.")

    obs_count = len(stages_observed)
    if obs_count == 4:
        status = COVERAGE_FULL
        explanation = "Full end-to-end process coverage observable across Detection, Investigation, Escalation, and Closure."
    elif obs_count >= 2:
        status = COVERAGE_PARTIAL
        explanation = f"Partial process coverage: Evidence observable for {', '.join(stages_observed)}; gaps detected in remaining stages."
    elif obs_count == 1:
        status = COVERAGE_LOW
        explanation = f"Low process coverage: Evidence only observable for {stages_observed[0]} stage."
    else:
        status = COVERAGE_UNKNOWN
        explanation = "Process coverage could not be evaluated due to lack of observable operational records."

    return {
        "status": status,
        "stages_observed": stages_observed,
        "stages_missing": [s for s in ["Detection", "Investigation", "Escalation", "Closure"] if s not in stages_observed],
        "visibility_gaps": visibility_gaps,
        "explanation": explanation,
    }
