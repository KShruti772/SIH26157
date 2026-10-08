"""
SAT-SA Assessment Assurance Configuration & Heuristic Baselines.

IMPORTANT DISCLAIMER:
Assessment assurance is a proposed analytical methodology and prototype implementation.
Thresholds and decision rules defined herein are PROTOTYPE ANALYTICAL RULES designed to assist
human-in-the-loop supervisory examiners in evaluating evidence representativeness, completeness,
and integrity. They are NOT established statutory standards of NCIIPC / NTRO and require validation
against expert supervisory review.
"""

# Overall Assessment Validity Statuses
ASSURANCE_STATUS_HIGH = "HIGH"
ASSURANCE_STATUS_CAUTION = "CAUTION"
ASSURANCE_STATUS_LOW = "LOW"
ASSURANCE_STATUS_INDETERMINATE = "INDETERMINATE"

# Evidence Independence Levels
INDEPENDENCE_HIGH = "HIGH_INDEPENDENCE"
INDEPENDENCE_MODERATE = "MODERATE_INDEPENDENCE"
INDEPENDENCE_LOW = "LOW_INDEPENDENCE"
INDEPENDENCE_UNKNOWN = "UNKNOWN"

# Coverage Statuses
COVERAGE_FULL = "FULL"
COVERAGE_PARTIAL = "PARTIAL"
COVERAGE_LOW = "LOW"
COVERAGE_AVAILABLE = "AVAILABLE"
COVERAGE_UNKNOWN = "UNKNOWN"

# Integrity Verification Statuses
INTEGRITY_VERIFIED = "VERIFIED"
INTEGRITY_CHANGED = "CHANGED"
INTEGRITY_UNAVAILABLE = "UNAVAILABLE"

# Prototype Analytical Thresholds
# Note: Prototype analytical rule — requires validation against expert supervisory review.
POPULATION_EXPOSURE_HIGH_THRESHOLD = 0.90     # >= 90% observable vs claimed
POPULATION_EXPOSURE_CAUTION_THRESHOLD = 0.60  # >= 60% and < 90% observable vs claimed
SEVERITY_IMBALANCE_RATIO_THRESHOLD = 0.90     # Single severity concentration > 90% indicates potential blind spot
SHARED_EVIDENCE_DEPENDENCY_THRESHOLD = 0.50   # > 50% shared source IDs indicates linked dependency
MIN_OBSERVABLE_RECORDS_FOR_ASSURANCE = 3      # Sample below 3 is INDETERMINATE
