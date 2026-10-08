import random
from datetime import datetime, timedelta
from app.database import engine, Base, SessionLocal
from app.models import domain

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    
    # 1. Create 10 CSEs
    entities = []
    for i in range(1, 11):
        e = domain.Entity(
            id=f"CSE-{i:03d}",
            name=f"Critical Sector Entity {i}",
            sector=random.choice(["Energy", "Finance", "Telecom", "Transport", "Govt"]),
            assessment_period="2026-Q3"
        )
        entities.append(e)
        db.add(e)
    db.commit()

    # Create dummy alerts and cases
    now = datetime.utcnow()
    alerts = []
    cases = []
    assets = []
    
    # Generate standard data
    for entity in entities:
        # Create some assets
        for j in range(5):
            a = domain.Asset(
                id=f"AST-{entity.id}-{j}",
                entity_id=entity.id,
                type=random.choice(["Server", "Endpoint", "Network", "Cloud"]),
                criticality=random.choice(["High", "Critical", "Medium"]),
                has_telemetry=True
            )
            assets.append(a)
            db.add(a)
            
        # Create alerts
        for k in range(50):
            alert = domain.Alert(
                id=f"AL-{entity.id}-{k}",
                entity_id=entity.id,
                timestamp=now - timedelta(days=random.randint(1, 30)),
                severity=random.choice(["Low", "Medium", "High", "Critical"]),
                category=random.choice(["Malware", "Intrusion", "DDoS", "Exfiltration"]),
                asset_id=assets[0].id,
                acknowledged=True,
                investigation_started=True,
                escalated=False,
                closed_at=now,
                disposition="False Positive",
                investigation_duration_mins=random.uniform(10, 120),
                closure_duration_mins=random.uniform(15, 130)
            )
            alerts.append(alert)
            db.add(alert)
            
    # Inject Scenarios
    
    # CSE-003: Critical alerts closed without escalation
    for k in range(10):
        alert = domain.Alert(
            id=f"AL-CSE-003-CRIT-{k}",
            entity_id="CSE-003",
            timestamp=now - timedelta(days=random.randint(1, 10)),
            severity="Critical",
            category="Exfiltration",
            asset_id="AST-CSE-003-0",
            acknowledged=True,
            investigation_started=True,
            escalated=False, # The issue!
            closed_at=now,
            disposition="Resolved",
            investigation_duration_mins=5.0,
            closure_duration_mins=6.0
        )
        db.add(alert)
        
    f1 = domain.Finding(
        id="EG-0042",
        entity_id="CSE-003",
        type="Critical alerts closed without escalation",
        category="execution_gap",
        severity="HIGH",
        confidence=0.91,
        description="Multiple critical severity alerts were closed very quickly without being escalated to higher tiers.",
        rationale="Critical alerts should normally be escalated. The entity shows a significant deviation from peer behaviour.",
        evidence_ids=["AL-CSE-003-CRIT-0", "AL-CSE-003-CRIT-1"],
        risk_contribution=18.0,
        recommended_action="Review critical alerts and escalation decisions."
    )
    db.add(f1)
    
    r1 = domain.RiskScore(
        entity_id="CSE-003",
        overall_score=72,
        execution_gap_risk=21,
        negative_space_risk=15,
        investigation_risk=12,
        escalation_risk=10,
        anomaly_risk=6,
        peer_deviation_risk=5,
        monitoring_coverage_risk=3
    )
    db.add(r1)
    
    rev1 = domain.ReviewItem(
        finding_id="EG-0042",
        priority_score=94.0,
        status="Pending"
    )
    db.add(rev1)

    # CSE-005: Critical assets have missing telemetry
    f2 = domain.Finding(
        id="NS-0015",
        entity_id="CSE-005",
        type="Missing Telemetry on Critical Assets",
        category="negative_space",
        severity="CRITICAL",
        confidence=0.95,
        description="Critical assets found with no corresponding log telemetry.",
        rationale="Critical assets must be monitored continuously.",
        evidence_ids=[],
        risk_contribution=25.0,
        recommended_action="Validate logging configuration on critical assets."
    )
    db.add(f2)
    db.add(domain.ReviewItem(finding_id="NS-0015", priority_score=88.0))
    db.add(domain.RiskScore(
        entity_id="CSE-005", overall_score=85, execution_gap_risk=10, negative_space_risk=40,
        investigation_risk=10, escalation_risk=5, anomaly_risk=10, peer_deviation_risk=5, monitoring_coverage_risk=5
    ))

    # Add random risk scores for the rest
    for i in range(1, 11):
        eid = f"CSE-{i:03d}"
        if eid not in ["CSE-003", "CSE-005"]:
            db.add(domain.RiskScore(
                entity_id=eid, overall_score=random.randint(10, 45), execution_gap_risk=5, negative_space_risk=5,
                investigation_risk=5, escalation_risk=5, anomaly_risk=random.randint(1,5), peer_deviation_risk=0, monitoring_coverage_risk=random.randint(1,5)
            ))

    db.commit()
    db.close()
    print("Database seeded with synthetic data.")

if __name__ == "__main__":
    seed()
