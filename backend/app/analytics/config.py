"""
SAT-SA Supervisory Analytics Configuration & Thresholds.

IMPORTANT DISCLAIMER:
The thresholds and weights defined in this module are PROTOTYPE ANALYTICAL THRESHOLDS
configured for supervisory audit heuristics and anomaly detection. They are NOT official
statutory or regulatory thresholds of NCIIPC / NTRO, but serve as configurable analytical baselines
for human-in-the-loop examiner triage and prioritization.
"""

# Execution Gap Detection Thresholds (in minutes)
PROTOTYPE_CRITICAL_CLOSURE_MINUTES = 15.0
PROTOTYPE_HIGH_CLOSURE_MINUTES = 30.0

# Anomaly Detection Parameters
MIN_ANOMALY_SAMPLE_SIZE = 5
ANOMALY_IQR_MULTIPLIER = 1.5

# Cohort Peer Benchmarking
MIN_PEER_BENCHMARK_ENTITIES = 2
PEER_DEVIATION_SIGNIFICANT_THRESHOLD = 25.0  # Percentage deviation from median
PEER_DEVIATION_WATCH_THRESHOLD = 10.0

# Documented 7-Factor Risk Weighting Model (Normalized to 1.0)
RISK_WEIGHTS = {
    "execution_gap": 0.25,
    "negative_space": 0.20,
    "investigation": 0.15,
    "escalation": 0.15,
    "anomaly": 0.10,
    "peer_deviation": 0.10,
    "monitoring_coverage": 0.05,
}

# Analytic Rule Identifiers for Provenance and Audit
RULE_EG_CRITICAL_FAST_CLOSURE = "EG_CRITICAL_FAST_CLOSURE_V1"
RULE_EG_CRITICAL_UNESCALATED = "EG_CRITICAL_UNESCALATED_V1"
RULE_EG_UNINVESTIGATED_ACK = "EG_UNINVESTIGATED_ACK_ALERT_V1"

RULE_NS_CRITICAL_ASSET_NO_TELEMETRY = "NS_CRITICAL_ASSET_NO_TELEMETRY_V1"
RULE_NS_ALERTS_WITHOUT_CASE = "NS_ALERTS_WITHOUT_CASE_V1"
RULE_NS_INVESTIGATION_MISSING_ESCALATION = "NS_INVESTIGATION_MISSING_ESCALATION_V1"

RULE_ANOMALY_INVESTIGATION_DURATION = "ANOMALY_INVESTIGATION_DURATION_V1"
RULE_ANOMALY_CLOSURE_DURATION = "ANOMALY_CLOSURE_DURATION_V1"
RULE_ANOMALY_ESCALATION_RATE = "ANOMALY_ESCALATION_RATE_V1"
