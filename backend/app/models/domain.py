from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    sector = Column(String)
    assessment_period = Column(String)

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    timestamp = Column(DateTime, index=True)
    severity = Column(String, index=True)
    category = Column(String)
    asset_id = Column(String)
    acknowledged = Column(Boolean, default=False)
    investigation_started = Column(Boolean, default=False)
    escalated = Column(Boolean, default=False)
    closed_at = Column(DateTime, nullable=True)
    disposition = Column(String, nullable=True)
    investigation_duration_mins = Column(Float, nullable=True)
    closure_duration_mins = Column(Float, nullable=True)

class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=True)
    created_at = Column(DateTime)
    investigator = Column(String)
    investigation_duration = Column(Float) # minutes
    escalation_status = Column(Boolean, default=False)
    closure_time = Column(DateTime, nullable=True)
    closure_reason = Column(String)
    evidence_count = Column(Integer, default=0)

class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    type = Column(String)
    criticality = Column(String)
    has_telemetry = Column(Boolean, default=True)

class Finding(Base):
    __tablename__ = "findings"
    id = Column(String, primary_key=True, index=True)
    entity_id = Column(String, ForeignKey("entities.id"), index=True)
    type = Column(String, index=True)
    category = Column(String) # execution_gap, negative_space, anomaly
    severity = Column(String)
    confidence = Column(Float)
    description = Column(Text)
    rationale = Column(Text)
    evidence_ids = Column(JSON) # List of alert/case/asset IDs
    risk_contribution = Column(Float)
    recommended_action = Column(Text)
    status = Column(String, index=True, default="Requires Review")

class ReviewItem(Base):
    __tablename__ = "review_items"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    finding_id = Column(String, ForeignKey("findings.id"))
    priority_score = Column(Float)
    reviewer = Column(String, nullable=True)
    status = Column(String, default="Pending")
    notes = Column(Text, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    user = Column(String)
    action = Column(String)
    object = Column(String)
    previous_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)

class RiskScore(Base):
    __tablename__ = "risk_scores"
    entity_id = Column(String, ForeignKey("entities.id"), primary_key=True)
    overall_score = Column(Float)
    execution_gap_risk = Column(Float)
    negative_space_risk = Column(Float)
    investigation_risk = Column(Float)
    escalation_risk = Column(Float)
    anomaly_risk = Column(Float)
    peer_deviation_risk = Column(Float)
    monitoring_coverage_risk = Column(Float)

class Benchmark(Base):
    __tablename__ = "benchmarks"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entity_id = Column(String, ForeignKey("entities.id"))
    metric = Column(String)
    entity_value = Column(Float)
    peer_median = Column(Float)
    peer_average = Column(Float)
    percentile = Column(Float)
    deviation_percent = Column(Float)
    status_label = Column(String) # NORMAL, WATCH, SIGNIFICANT DEVIATION
