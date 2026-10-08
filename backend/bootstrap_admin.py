"""
SAT-SA Local Administrator Bootstrap Utility.
Enables offline/air-gapped operators to securely provision an Administrator account
without exposing ADMINISTRATOR role on public self-registration endpoints.
"""

import sys
import uuid
import re
import argparse
from app.database import SessionLocal, init_db
from app.models import domain
from app.services.auth import hash_password, UserRole
from app.services.audit import AuditService, EventType, ActorType

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def bootstrap_admin(full_name: str, email: str, password: str, organization: str):
    init_db()
    db = SessionLocal()
    try:
        email_clean = email.strip().lower()
        full_name_clean = full_name.strip()
        org_clean = organization.strip()

        if not full_name_clean:
            print("[ERROR] Full name is required.")
            sys.exit(1)

        if not EMAIL_REGEX.match(email_clean):
            print("[ERROR] A valid email address is required.")
            sys.exit(1)

        if len(password) < 8:
            print("[ERROR] Password must be at least 8 characters.")
            sys.exit(1)

        existing = db.query(domain.User).filter(domain.User.email == email_clean).first()
        if existing:
            if existing.role == UserRole.ADMINISTRATOR:
                print(f"[INFO] Administrator account '{email_clean}' already exists.")
                return existing
            else:
                existing.role = UserRole.ADMINISTRATOR
                existing.password_hash = hash_password(password)
                existing.is_active = True
                db.commit()
                print(f"[SUCCESS] User '{email_clean}' upgraded to ADMINISTRATOR role.")
                return existing

        user_id = f"USR-ADM-{uuid.uuid4().hex[:8].upper()}"
        pwd_hash = hash_password(password)

        new_admin = domain.User(
            id=user_id,
            full_name=full_name_clean,
            email=email_clean,
            password_hash=pwd_hash,
            organization=org_clean,
            role=UserRole.ADMINISTRATOR,
            is_active=True,
        )
        db.add(new_admin)
        db.commit()

        # Audit event
        try:
            audit_svc = AuditService()
            audit_svc.record_event(
                db=db,
                event_type=EventType.USER_REGISTERED,
                actor_type=ActorType.SYSTEM,
                actor_id="CLI_BOOTSTRAP",
                payload={
                    "user_id": user_id,
                    "email": email_clean,
                    "role": UserRole.ADMINISTRATOR,
                    "organization": org_clean,
                    "provisioning_method": "CLI_BOOTSTRAP",
                },
            )
        except Exception:
            pass

        print(f"[SUCCESS] Created Administrator account '{email_clean}' with User ID: {user_id}")
        return new_admin
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision a SAT-SA Administrator Account")
    parser.add_argument("--name", default="System Administrator", help="Admin full name")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password (min 8 chars)")
    parser.add_argument("--org", default="National SOC Operations Centre", help="Organization name")

    args = parser.parse_args()
    bootstrap_admin(
        full_name=args.name,
        email=args.email,
        password=args.password,
        organization=args.org,
    )
