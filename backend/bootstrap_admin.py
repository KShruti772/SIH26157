"""
SAT-SA Local Privileged User Bootstrap Utility.
Enables offline/air-gapped operators to securely provision or promote Administrator
and Supervisor accounts without exposing elevated privileges on public self-registration endpoints.
"""

import sys
import uuid
import re
import getpass
import argparse
from typing import Optional
from app.database import SessionLocal, init_db
from app.models import domain
from app.services.auth import hash_password, UserRole
from app.services.audit import AuditService, EventType, ActorType

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def bootstrap_privileged_user(
    full_name: str,
    email: str,
    password: Optional[str] = None,
    organization: str = "National SOC Operations Centre",
    role: str = UserRole.ADMINISTRATOR,
    confirm_promote: bool = False,
    db_session=None,
) -> Optional[domain.User]:
    """
    Safely provisions a new privileged user or promotes an existing user.
    Requires confirm_promote=True when modifying an existing account in non-interactive environments.
    Never prints or logs passwords or password hashes.
    """
    if db_session is None:
        init_db()
        db = SessionLocal()
        close_session = True
    else:
        db = db_session
        close_session = False

    try:
        email_clean = (email or "").strip().lower()
        full_name_clean = (full_name or "").strip()
        org_clean = (organization or "").strip()
        target_role = (role or "").strip().upper()

        if target_role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
            raise ValueError(f"Invalid privileged role '{role}'. Allowed: SUPERVISOR, ADMINISTRATOR")

        if not full_name_clean:
            raise ValueError("Full name is required.")

        if not EMAIL_REGEX.match(email_clean):
            raise ValueError("A valid email address is required.")

        # If password not provided programmatically, prompt interactively
        if not password:
            if not sys.stdin.isatty():
                raise ValueError("Password is required in non-interactive mode. Supply password or run in interactive terminal.")

            pwd1 = getpass.getpass("Enter password (min 8 chars): ")
            pwd2 = getpass.getpass("Confirm password: ")
            if pwd1 != pwd2:
                raise ValueError("Passwords do not match.")
            password = pwd1

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        existing = db.query(domain.User).filter(domain.User.email == email_clean).first()
        if existing:
            if not confirm_promote:
                # If interactive terminal, ask for explicit confirmation
                if sys.stdin.isatty():
                    resp = input(
                        f"User '{email_clean}' already exists with role '{existing.role}'. "
                        f"Promote/update to '{target_role}' and reset password? [y/N]: "
                    ).strip().lower()
                    if resp not in ["y", "yes"]:
                        print("[INFO] Promotion cancelled by operator. No changes made.")
                        return None
                else:
                    raise PermissionError(
                        f"Account '{email_clean}' already exists (role: {existing.role}). "
                        "Explicit confirmation (--confirm-promote) is required to promote or update existing accounts."
                    )

            previous_role = existing.role
            existing.role = target_role
            existing.password_hash = hash_password(password)
            existing.is_active = True
            if full_name_clean:
                existing.full_name = full_name_clean
            if org_clean:
                existing.organization = org_clean
            db.commit()

            # Record audit event without credentials
            try:
                audit_svc = AuditService()
                audit_svc.record_event(
                    db=db,
                    event_type=EventType.USER_ROLE_CHANGED,
                    actor_type=ActorType.SYSTEM,
                    actor_id="CLI_BOOTSTRAP",
                    payload={
                        "user_id": existing.id,
                        "email": email_clean,
                        "previous_role": previous_role,
                        "new_role": target_role,
                        "action": "CLI_ACCOUNT_UPDATE",
                    },
                )
            except Exception as e:
                print(f"[WARN] Audit recording encountered an issue: {type(e).__name__}")

            print(f"[SUCCESS] User '{email_clean}' successfully updated to role '{target_role}'.")
            return existing

        prefix = "ADM" if target_role == UserRole.ADMINISTRATOR else "SUP"
        user_id = f"USR-{prefix}-{uuid.uuid4().hex[:8].upper()}"
        pwd_hash = hash_password(password)

        new_user = domain.User(
            id=user_id,
            full_name=full_name_clean,
            email=email_clean,
            password_hash=pwd_hash,
            organization=org_clean,
            role=target_role,
            is_active=True,
        )
        db.add(new_user)
        db.commit()

        # Audit event without credentials
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
                    "role": target_role,
                    "organization": org_clean,
                    "provisioning_method": "CLI_BOOTSTRAP",
                },
            )
        except Exception as e:
            print(f"[WARN] Audit recording encountered an issue: {type(e).__name__}")

        print(f"[SUCCESS] Created privileged account '{email_clean}' ({target_role}) with User ID: {user_id}")
        return new_user
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Provision or promote a SAT-SA Supervisor or Administrator account. "
                    "Passwords are submitted through secure hidden interactive prompts."
    )
    parser.add_argument("--name", default="Privileged Examiner", help="Full name of the user")
    parser.add_argument("--email", required=True, help="Email address")
    parser.add_argument("--org", default="National SOC Operations Centre", help="Organization name")
    parser.add_argument("--role", default="ADMINISTRATOR", choices=["SUPERVISOR", "ADMINISTRATOR"], help="Role to assign")
    parser.add_argument("--confirm-promote", action="store_true", help="Explicitly confirm updating/promoting an existing account")

    args = parser.parse_args()
    try:
        bootstrap_privileged_user(
            full_name=args.name,
            email=args.email,
            organization=args.org,
            role=args.role,
            confirm_promote=args.confirm_promote,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
