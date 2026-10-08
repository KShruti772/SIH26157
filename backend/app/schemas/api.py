from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class EntityBase(BaseModel):
    id: str
    name: str
    sector: str
    assessment_period: str

    class Config:
        from_attributes = True

class FindingBase(BaseModel):
    id: str
    entity_id: str
    type: str
    category: str
    severity: str
    confidence: float
    description: str
    rationale: str
    evidence_ids: List[str]
    risk_contribution: float
    recommended_action: str
    status: str

    class Config:
        from_attributes = True

class RiskScoreBase(BaseModel):
    entity_id: str
    overall_score: float
    execution_gap_risk: float
    negative_space_risk: float
    investigation_risk: float
    escalation_risk: float
    anomaly_risk: float
    peer_deviation_risk: float
    monitoring_coverage_risk: float

    class Config:
        from_attributes = True

class BenchmarkBase(BaseModel):
    id: int
    entity_id: str
    metric: str
    entity_value: float
    peer_median: float
    peer_average: float
    percentile: float
    deviation_percent: float
    status_label: str

    class Config:
        from_attributes = True

class ReviewItemBase(BaseModel):
    id: int
    finding_id: str
    priority_score: float
    reviewer: Optional[str] = None
    status: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class AuditLogBase(BaseModel):
    id: int
    timestamp: datetime
    user: str
    action: str
    object: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None

    class Config:
        from_attributes = True
