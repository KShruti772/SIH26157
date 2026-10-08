"""
Assessment Assurance Package for SAT-SA (Module 5).
Evaluates multidimensional evidence coverage, population exposure, evidence dependency,
contradiction detection, blind spots, integrity hashing, and assessment validity profiling.
"""

from app.assurance.config import (
    ASSURANCE_STATUS_HIGH,
    ASSURANCE_STATUS_CAUTION,
    ASSURANCE_STATUS_LOW,
    ASSURANCE_STATUS_INDETERMINATE,
    INDEPENDENCE_HIGH,
    INDEPENDENCE_MODERATE,
    INDEPENDENCE_LOW,
    INDEPENDENCE_UNKNOWN,
    COVERAGE_FULL,
    COVERAGE_PARTIAL,
    COVERAGE_LOW,
    COVERAGE_AVAILABLE,
    COVERAGE_UNKNOWN,
    INTEGRITY_VERIFIED,
    INTEGRITY_CHANGED,
    INTEGRITY_UNAVAILABLE,
)
from app.assurance.hashing import (
    compute_source_hash,
    compute_canonical_records_hash,
    verify_upload_integrity,
)
from app.assurance.coverage import (
    evaluate_population_exposure,
    evaluate_temporal_coverage,
    evaluate_severity_coverage,
    evaluate_asset_coverage,
    evaluate_process_coverage,
)
from app.assurance.contradictions import detect_evidence_contradictions
from app.assurance.dependencies import evaluate_evidence_dependencies
from app.assurance.blind_spots import detect_evidence_blind_spots
from app.assurance.validity import synthesize_assessment_validity
from app.assurance.service import AssessmentAssuranceService

__all__ = [
    "ASSURANCE_STATUS_HIGH",
    "ASSURANCE_STATUS_CAUTION",
    "ASSURANCE_STATUS_LOW",
    "ASSURANCE_STATUS_INDETERMINATE",
    "INDEPENDENCE_HIGH",
    "INDEPENDENCE_MODERATE",
    "INDEPENDENCE_LOW",
    "INDEPENDENCE_UNKNOWN",
    "COVERAGE_FULL",
    "COVERAGE_PARTIAL",
    "COVERAGE_LOW",
    "COVERAGE_AVAILABLE",
    "COVERAGE_UNKNOWN",
    "INTEGRITY_VERIFIED",
    "INTEGRITY_CHANGED",
    "INTEGRITY_UNAVAILABLE",
    "compute_source_hash",
    "compute_canonical_records_hash",
    "verify_upload_integrity",
    "evaluate_population_exposure",
    "evaluate_temporal_coverage",
    "evaluate_severity_coverage",
    "evaluate_asset_coverage",
    "evaluate_process_coverage",
    "detect_evidence_contradictions",
    "evaluate_evidence_dependencies",
    "detect_evidence_blind_spots",
    "synthesize_assessment_validity",
    "AssessmentAssuranceService",
]
