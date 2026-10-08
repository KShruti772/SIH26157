from typing import Dict, Any, List, Optional
from app.assurance.config import (
    ASSURANCE_STATUS_HIGH,
    ASSURANCE_STATUS_CAUTION,
    ASSURANCE_STATUS_LOW,
    ASSURANCE_STATUS_INDETERMINATE,
    COVERAGE_FULL,
    COVERAGE_PARTIAL,
    COVERAGE_LOW,
    COVERAGE_UNKNOWN,
    INDEPENDENCE_LOW,
    INDEPENDENCE_MODERATE,
    MIN_OBSERVABLE_RECORDS_FOR_ASSURANCE,
)


def synthesize_assessment_validity(
    population_exposure: Dict[str, Any],
    coverage_details: Dict[str, Any],
    contradiction_details: Dict[str, Any],
    dependency_details: Dict[str, Any],
    blind_spots: List[Dict[str, Any]],
    total_records: int,
) -> Dict[str, Any]:
    """
    Synthesize overall Assessment Validity profile and human-in-the-loop supervisory interpretation.
    CRITICAL RULE: Validity is an explainable multi-dimensional assurance profile, NOT an opaque 0-100 score.
    """
    limitations: List[str] = []

    # Check for indeterminate state (insufficient sample)
    if total_records < MIN_OBSERVABLE_RECORDS_FOR_ASSURANCE:
        limitations.append("Observable dataset contains insufficient records to evaluate representative assurance dimensions.")
        return {
            "overall_status": ASSURANCE_STATUS_INDETERMINATE,
            "limitations": limitations,
            "supervisory_interpretation": "Assessment validity is INDETERMINATE due to an insufficient sample of observable records in the submission.",
        }

    pop_status = population_exposure.get("status")
    pop_value = population_exposure.get("value")

    proc_status = coverage_details.get("process", {}).get("status", COVERAGE_UNKNOWN)
    sev_status = coverage_details.get("severity", {}).get("status", COVERAGE_UNKNOWN)
    asset_status = coverage_details.get("asset", {}).get("status", COVERAGE_UNKNOWN)
    temp_status = coverage_details.get("temporal", {}).get("status", COVERAGE_UNKNOWN)

    contradiction_count = contradiction_details.get("count", 0)
    inconsistency_count = contradiction_details.get("inconsistency_count", 0)
    dep_status = dependency_details.get("status")

    # 1. Compile Explainable Limitations
    if pop_status == COVERAGE_LOW and pop_value is not None:
        limitations.append(f"Major population exposure gap: submitted records represent only {pop_value * 100:.0f}% of declared population.")
    elif pop_status == COVERAGE_PARTIAL and pop_value is not None:
        limitations.append(f"Partial population exposure: submitted records cover {pop_value * 100:.0f}% of declared population.")
    elif pop_status == COVERAGE_UNKNOWN:
        limitations.append("Declared population metadata was not supplied; population completeness cannot be verified.")

    if proc_status == COVERAGE_LOW:
        missing_st = coverage_details.get("process", {}).get("stages_missing", [])
        limitations.append(f"Major process visibility gap: missing operational evidence for {', '.join(missing_st)}.")
    elif proc_status == COVERAGE_PARTIAL:
        missing_st = coverage_details.get("process", {}).get("stages_missing", [])
        if missing_st:
            limitations.append(f"Process evidence gap: no evidence observed for {', '.join(missing_st)} stage(s).")

    if sev_status == COVERAGE_LOW or sev_status == COVERAGE_PARTIAL:
        limitations.append("Severity distribution exhibits gaps or high concentration; some threat levels are underrepresented.")

    if asset_status == COVERAGE_LOW or asset_status == COVERAGE_PARTIAL:
        limitations.append("Asset telemetry coverage is incomplete; certain critical infrastructure assets lack telemetry streams.")

    if contradiction_count > 0:
        limitations.append(f"Evidence integrity warning: {contradiction_count} internal contradiction(s) detected between correlated records.")

    if dep_status == INDEPENDENCE_LOW:
        limitations.append("Multiple assessment claims depend upon identical underlying source records (low evidence independence).")

    # 2. Determine Overall Status (HIGH, CAUTION, LOW, INDETERMINATE)
    high_impact_blind_spots = [bs for bs in blind_spots if bs.get("severity_impact") == "HIGH"]

    is_low = (
        (pop_status == COVERAGE_LOW)
        or (proc_status == COVERAGE_LOW)
        or (contradiction_count >= 3)
        or (len(high_impact_blind_spots) >= 3)
    )

    is_caution = (
        is_low
        or (pop_status == COVERAGE_PARTIAL)
        or (proc_status == COVERAGE_PARTIAL)
        or (sev_status in [COVERAGE_PARTIAL, COVERAGE_LOW])
        or (asset_status in [COVERAGE_PARTIAL, COVERAGE_LOW])
        or (contradiction_count > 0)
        or (inconsistency_count > 0)
        or (dep_status == INDEPENDENCE_LOW)
        or (len(blind_spots) > 0)
    )

    if is_low:
        overall_status = ASSURANCE_STATUS_LOW
        supervisory_interpretation = (
            "Assessment validity is LOW. Significant evidence gaps, contradictions, or unobserved process stages "
            "preclude extrapolating findings to broader supervisory conclusions without supplementary verification."
        )
    elif is_caution:
        overall_status = ASSURANCE_STATUS_CAUTION
        supervisory_interpretation = (
            "The observed evidence supports specific analytical findings within the submitted dataset, "
            "but evidence coverage, blind spots, or dependency limitations warrant CAUTION before generalising "
            "to the complete operational environment."
        )
    else:
        overall_status = ASSURANCE_STATUS_HIGH
        supervisory_interpretation = (
            "Assessment validity is HIGH. Submitted evidence exhibits comprehensive process coverage, "
            "balanced severity representation, internal consistency, and independent provenance."
        )

    return {
        "overall_status": overall_status,
        "limitations": limitations,
        "supervisory_interpretation": supervisory_interpretation,
    }
