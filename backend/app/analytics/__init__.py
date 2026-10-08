"""
Supervisory Analytics Package for SAT-SA.
Provides execution gap detection, negative space analysis, statistical anomaly detection,
peer cohort benchmarking, and multi-factor risk scoring.
"""

from app.analytics.config import (
    PROTOTYPE_CRITICAL_CLOSURE_MINUTES,
    PROTOTYPE_HIGH_CLOSURE_MINUTES,
    MIN_ANOMALY_SAMPLE_SIZE,
    MIN_PEER_BENCHMARK_ENTITIES,
    RISK_WEIGHTS,
)
from app.analytics.execution_gaps import ExecutionGapDetector
from app.analytics.negative_space import NegativeSpaceDetector
from app.analytics.anomalies import AnomalyDetector
from app.analytics.benchmarking import CohortBenchmarker
from app.analytics.risk import RiskScoreCalculator
from app.analytics.engine import SupervisoryAnalyticsEngine

__all__ = [
    "PROTOTYPE_CRITICAL_CLOSURE_MINUTES",
    "PROTOTYPE_HIGH_CLOSURE_MINUTES",
    "MIN_ANOMALY_SAMPLE_SIZE",
    "MIN_PEER_BENCHMARK_ENTITIES",
    "RISK_WEIGHTS",
    "ExecutionGapDetector",
    "NegativeSpaceDetector",
    "AnomalyDetector",
    "CohortBenchmarker",
    "RiskScoreCalculator",
    "SupervisoryAnalyticsEngine",
]
