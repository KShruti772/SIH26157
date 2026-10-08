import random
from datetime import datetime, timedelta
from app.database import engine, Base, SessionLocal
from app.models import domain
from app.analytics.engine import SupervisoryAnalyticsEngine

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    
    # 1. Create 10 Critical Sector Entities (CSEs)
    entities = []
    sectors = ["Energy", "Finance", "Telecom", "Transport", "Govt", "Defense", "Healthcare", "IT", "Power", "Banking"]
    for i in range(1, 11):
        e = domain.Entity(
            id=f"CSE-{i:03d}",
            name=f"Critical Sector Entity {i}",
            sector=sectors[i - 1],
            assessment_period="2026-Q3"
        )
        entities.append(e)
        db.add(e)
    db.commit()

    now = datetime.utcnow()
    
    # 2. Seed Assets for all entities
    for entity in entities:
        is_cse_005 = (entity.id == "CSE-005")
        for j in range(6):
            crit = "Critical" if j < 2 else ("High" if j < 4 else "Medium")
            # CSE-005 has dormant critical assets with missing telemetry
            has_telem = False if (is_cse_005 and crit in ["Critical", "High"]) else True
            a = domain.Asset(
                id=f"AST-{entity.id}-{j}",
                entity_id=entity.id,
                type="Server" if j % 2 == 0 else "Endpoint",
                criticality=crit,
                has_telemetry=has_telem,
            )
            db.add(a)

    # 3. Seed Alerts and Cases for all entities
    for entity in entities:
        is_cse_003 = (entity.id == "CSE-003")
        is_cse_005 = (entity.id == "CSE-005")

        for k in range(35):
            alert_id = f"AL-{entity.id}-{k:03d}"
            sev = random.choice(["Low", "Medium", "High", "Critical"]) if not is_cse_003 else ("Critical" if k < 15 else "Low")
            
            # Normal peers escalate critical alerts ~85% of the time
            is_crit = (sev == "Critical")
            if is_cse_003 and is_crit:
                # CSE-003 operational gap: closed rapidly without escalation
                escalated = False
                inv_dur = 4.5
                close_dur = 5.5
                inv_started = True
                ack = True
            else:
                escalated = True if is_crit else (random.random() > 0.6)
                inv_dur = random.uniform(25, 65)
                close_dur = inv_dur + random.uniform(10, 40)
                inv_started = True
                ack = True

            gen_time = now - timedelta(days=random.randint(1, 28), hours=random.randint(0, 23))
            close_time = gen_time + timedelta(minutes=close_dur)

            alert = domain.Alert(
                id=alert_id,
                entity_id=entity.id,
                timestamp=gen_time,
                severity=sev,
                category=random.choice(["Exfiltration", "Intrusion", "Malware", "Privilege Escalation"]),
                asset_id=f"AST-{entity.id}-0",
                acknowledged=ack,
                investigation_started=inv_started,
                escalated=escalated,
                closed_at=close_time,
                disposition="Resolved" if escalated else "False Positive",
                investigation_duration_mins=inv_dur,
                closure_duration_mins=close_dur,
            )
            db.add(alert)

            # Add linked Case for investigated alerts
            if inv_started and random.random() > 0.3:
                case = domain.Case(
                    id=f"CASE-{entity.id}-{k:03d}",
                    entity_id=entity.id,
                    alert_id=alert_id,
                    created_at=gen_time + timedelta(minutes=2),
                    investigator=f"Analyst-{random.randint(1, 8)}",
                    investigation_duration=inv_dur,
                    escalation_status=escalated,
                    closure_time=close_time,
                    closure_reason="Disposition reached",
                    evidence_count=random.randint(1, 4),
                )
                db.add(case)

    db.commit()
    print("Realistic operational records staged in database.")

    # 4. Run real Supervisory Analytics Engine over staged records
    print("Executing Supervisory Analytics Engine over staged operational records...")
    engine_inst = SupervisoryAnalyticsEngine()
    summary = engine_inst.run(db=db)
    print(f"Supervisory Analytics Engine complete! Generated {summary['findings_count']} findings across {summary['entities_analyzed']} entities.")

    # Also add aliased finding entries for EG-0042 and NS-0015 for backward compatibility with legacy direct links
    existing_eg = db.query(domain.Finding).filter(domain.Finding.id == "EG-CSE-003-FAST-CRIT").first()
    if existing_eg:
        db.add(domain.Finding(
            id="EG-0042",
            entity_id="CSE-003",
            type="Critical alerts closed without escalation",
            category="execution_gap",
            severity=existing_eg.severity,
            confidence=existing_eg.confidence,
            description=existing_eg.description,
            rationale=existing_eg.rationale,
            evidence_ids=existing_eg.evidence_ids,
            risk_contribution=existing_eg.risk_contribution,
            recommended_action=existing_eg.recommended_action,
            status="Requires Review",
            analytic_rule=existing_eg.analytic_rule,
            details=existing_eg.details,
            assessment_validity=existing_eg.assessment_validity or "CAUTION",
            validity_rationale=existing_eg.validity_rationale or "Evidence supports specific finding, but complete operational population remains unverified.",
        ))
        db.add(domain.ReviewItem(finding_id="EG-0042", priority_score=94.0, status="Pending", notes="Demo baseline review item"))

    existing_ns = db.query(domain.Finding).filter(domain.Finding.id == "NS-CSE-005-CRIT-ASSET").first()
    if existing_ns:
        db.add(domain.Finding(
            id="NS-0015",
            entity_id="CSE-005",
            type="Missing Telemetry on Critical Assets",
            category="negative_space",
            severity=existing_ns.severity,
            confidence=existing_ns.confidence,
            description=existing_ns.description,
            rationale=existing_ns.rationale,
            evidence_ids=existing_ns.evidence_ids,
            risk_contribution=existing_ns.risk_contribution,
            recommended_action=existing_ns.recommended_action,
            status="Requires Review",
            analytic_rule=existing_ns.analytic_rule,
            details=existing_ns.details,
            assessment_validity=existing_ns.assessment_validity or "CAUTION",
            validity_rationale=existing_ns.validity_rationale or "Evidence supports specific finding, but complete operational population remains unverified.",
        ))
        db.add(domain.ReviewItem(finding_id="NS-0015", priority_score=88.0, status="Pending", notes="Demo baseline review item"))

    db.commit()
    db.close()
    print("Database seeding and analytical discovery completed.")

if __name__ == "__main__":
    seed()
