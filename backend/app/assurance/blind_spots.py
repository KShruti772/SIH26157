from typing import List, Dict, Any, Optional
from app.models import domain
from app.assurance.config import (
    SEVERITY_IMBALANCE_RATIO_THRESHOLD,
    COVERAGE_PARTIAL,
    COVERAGE_LOW,
)


def detect_evidence_blind_spots(
    coverage_details: Dict[str, Any],
    alerts: List[domain.Alert],
    assets: List[domain.Asset],
    cases: List[domain.Case],
) -> List[Dict[str, Any]]:
    """
    Detect structured operational evidence blind spots across temporal, severity, asset, and process dimensions.
    Uses cautious supervisory language distinguishing observed data gaps from operational failure.
    """
    blind_spots: List[Dict[str, Any]] = []

    # 1. Severity Blind Spots
    sev_cov = coverage_details.get("severity", {})
    percentages = sev_cov.get("percentages", {})
    distribution = sev_cov.get("distribution", {})

    if distribution.get("Critical", 0) == 0:
        blind_spots.append({
            "dimension": "severity",
            "type": "SEVERITY_TIER_ABSENT",
            "severity_impact": "HIGH",
            "description": "Evidence blind spot detected: Zero Critical severity alert records were observed in the submitted telemetry.",
            "supervisory_implication": "Supervisory evaluation of critical incident escalation cannot be substantiated from this dataset alone.",
        })

    for sev, pct in percentages.items():
        if pct >= (SEVERITY_IMBALANCE_RATIO_THRESHOLD * 100.0) and len(alerts) > 10:
            blind_spots.append({
                "dimension": "severity",
                "type": "SEVERITY_CONCENTRATION",
                "severity_impact": "MEDIUM",
                "description": f"Evidence blind spot detected: {pct:.1f}% of submitted alerts belong exclusively to the '{sev}' tier.",
                "supervisory_implication": "Dataset exhibits high severity concentration; other threat levels are underrepresented.",
            })

    # 2. Asset Blind Spots
    asset_cov = coverage_details.get("asset", {})
    critical_total = asset_cov.get("critical_assets", 0)
    monitored_total = asset_cov.get("monitored_assets", 0)
    total_assets = asset_cov.get("total_assets", 0)

    if total_assets > 0 and monitored_total < total_assets:
        unmonitored = total_assets - monitored_total
        blind_spots.append({
            "dimension": "asset",
            "type": "UNMONITORED_ASSETS_OBSERVED",
            "severity_impact": "HIGH" if critical_total > 0 else "MEDIUM",
            "description": f"Evidence blind spot detected: {unmonitored} asset(s) in the catalog lack observable active telemetry streams.",
            "supervisory_implication": "Supervisory visibility into unmonitored infrastructure segments is constrained.",
        })

    # 3. Process-Stage Blind Spots
    proc_cov = coverage_details.get("process", {})
    missing_stages = proc_cov.get("stages_missing", [])

    for st in missing_stages:
        blind_spots.append({
            "dimension": "process",
            "type": f"PROCESS_STAGE_{st.upper()}_ABSENT",
            "severity_impact": "HIGH" if st in ["Investigation", "Escalation"] else "MEDIUM",
            "description": f"Evidence blind spot detected: No {st.lower()} evidence was observable in the submitted dataset.",
            "supervisory_implication": f"Operational efficacy of the {st} stage cannot be independently substantiated without supplementary records.",
        })

    # 4. Temporal Blind Spots
    temp_cov = coverage_details.get("temporal", {})
    span_days = temp_cov.get("span_days", 0)
    if span_days > 0 and span_days < 7 and len(alerts) > 0:
        blind_spots.append({
            "dimension": "temporal",
            "type": "NARROW_TIME_WINDOW",
            "severity_impact": "MEDIUM",
            "description": f"Evidence blind spot detected: Observable telemetry spans only {span_days} days.",
            "supervisory_implication": "Short observation windows may not capture cyclical operational patterns or sustained incident handling.",
        })

    return blind_spots
