"""
Unit & Integration Tests for bootstrap_admin.py CLI and privileged user provisioning.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import domain
from app.services.auth import verify_password, UserRole
from bootstrap_admin import bootstrap_privileged_user


@pytest.fixture
def bootstrap_db():
    """Isolated in-memory SQLite database for bootstrap testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


def test_bootstrap_new_administrator_success(bootstrap_db):
    """Test creating a new administrator account succeeds and hashes password."""
    user = bootstrap_privileged_user(
        full_name="New Security Lead",
        email="lead.admin@ntro.gov",
        password="SecureAdminPassword2026!",
        organization="NTRO Operations",
        role=UserRole.ADMINISTRATOR,
        db_session=bootstrap_db,
    )
    assert user is not None
    assert user.id.startswith("USR-ADM-")
    assert user.email == "lead.admin@ntro.gov"
    assert user.role == UserRole.ADMINISTRATOR
    assert user.is_active is True
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert "SecureAdminPassword2026!" not in user.password_hash
    assert verify_password("SecureAdminPassword2026!", user.password_hash) is True


def test_bootstrap_new_supervisor_success(bootstrap_db):
    """Test creating a new supervisor account succeeds and hashes password."""
    user = bootstrap_privileged_user(
        full_name="Field Supervisor",
        email="field.sup@ntro.gov",
        password="SecureSupervisorPass2026!",
        organization="NTRO Assessment Cell",
        role=UserRole.SUPERVISOR,
        db_session=bootstrap_db,
    )
    assert user is not None
    assert user.id.startswith("USR-SUP-")
    assert user.role == UserRole.SUPERVISOR
    assert verify_password("SecureSupervisorPass2026!", user.password_hash) is True


def test_bootstrap_promotion_without_confirmation_raises_error(bootstrap_db):
    """Test attempting to promote/overwrite an existing user without confirm_promote is rejected."""
    # 1. Create reviewer user
    bootstrap_privileged_user(
        full_name="Standard Reviewer",
        email="operator.one@ntro.gov",
        password="InitialPassword123!",
        role=UserRole.SUPERVISOR,
        db_session=bootstrap_db,
    )

    # 2. Attempt to promote/reset without confirm_promote in non-interactive environment
    with pytest.raises(PermissionError) as exc_info:
        bootstrap_privileged_user(
            full_name="Standard Reviewer",
            email="operator.one@ntro.gov",
            password="NewAdminPassword123!",
            role=UserRole.ADMINISTRATOR,
            confirm_promote=False,
            db_session=bootstrap_db,
        )
    assert "Explicit confirmation (--confirm-promote) is required" in str(exc_info.value)

    # User remains SUPERVISOR with initial password
    user = bootstrap_db.query(domain.User).filter(domain.User.email == "operator.one@ntro.gov").first()
    assert user.role == UserRole.SUPERVISOR
    assert verify_password("InitialPassword123!", user.password_hash) is True


def test_bootstrap_promotion_with_confirmation_succeeds(bootstrap_db):
    """Test promoting an existing account with confirm_promote=True updates role and password."""
    # 1. Create initial user
    bootstrap_privileged_user(
        full_name="Promotable Examiner",
        email="promotable@ntro.gov",
        password="InitialPassword123!",
        role=UserRole.SUPERVISOR,
        db_session=bootstrap_db,
    )

    # 2. Promote with confirm_promote=True
    updated = bootstrap_privileged_user(
        full_name="Promotable Examiner",
        email="promotable@ntro.gov",
        password="PromotedAdminPassword123!",
        role=UserRole.ADMINISTRATOR,
        confirm_promote=True,
        db_session=bootstrap_db,
    )
    assert updated.role == UserRole.ADMINISTRATOR
    assert verify_password("PromotedAdminPassword123!", updated.password_hash) is True

    # 3. Verify audit event was recorded with previous and new role without credentials
    events = bootstrap_db.query(domain.AuditEvent).filter(domain.AuditEvent.event_type == "USER_ROLE_CHANGED").all()
    assert len(events) >= 1
    payload_str = str(events[0].payload_json)
    assert "PromotedAdminPassword123!" not in payload_str
    assert "pbkdf2_sha256" not in payload_str
    assert events[0].payload_json.get("previous_role") == UserRole.SUPERVISOR
    assert events[0].payload_json.get("new_role") == UserRole.ADMINISTRATOR


def test_bootstrap_validation_checks(bootstrap_db):
    """Test validation checks for invalid email, role, and short passwords."""
    # Invalid role
    with pytest.raises(ValueError) as exc1:
        bootstrap_privileged_user(
            full_name="Test User",
            email="test@ntro.gov",
            password="ValidPass123!",
            role="INVALID_ROLE",
            db_session=bootstrap_db,
        )
    assert "Invalid privileged role" in str(exc1.value)

    # Invalid email
    with pytest.raises(ValueError) as exc2:
        bootstrap_privileged_user(
            full_name="Test User",
            email="not-an-email",
            password="ValidPass123!",
            role=UserRole.ADMINISTRATOR,
            db_session=bootstrap_db,
        )
    assert "valid email" in str(exc2.value)

    # Short password (< 8 chars)
    with pytest.raises(ValueError) as exc3:
        bootstrap_privileged_user(
            full_name="Test User",
            email="shortpass@ntro.gov",
            password="short",
            role=UserRole.ADMINISTRATOR,
            db_session=bootstrap_db,
        )
    assert "at least 8 characters" in str(exc3.value)


def test_bootstrap_interactive_password_prompt_success(bootstrap_db, monkeypatch):
    """Test interactive hidden password prompt using getpass.getpass."""
    import sys
    import getpass

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "InteractiveSecretPass123!")

    user = bootstrap_privileged_user(
        full_name="Interactive Examiner",
        email="interactive@ntro.gov",
        password=None,
        role=UserRole.ADMINISTRATOR,
        db_session=bootstrap_db,
    )
    assert user is not None
    assert verify_password("InteractiveSecretPass123!", user.password_hash) is True


def test_bootstrap_interactive_password_mismatch_raises_error(bootstrap_db, monkeypatch):
    """Test interactive prompt raises error if confirmation password does not match."""
    import sys
    import getpass

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    prompts = iter(["FirstSecret123!", "SecondSecret123!"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(prompts))

    with pytest.raises(ValueError) as exc:
        bootstrap_privileged_user(
            full_name="Mismatch Examiner",
            email="mismatch@ntro.gov",
            password=None,
            role=UserRole.ADMINISTRATOR,
            db_session=bootstrap_db,
        )
    assert "Passwords do not match" in str(exc.value)


def test_bootstrap_interactive_promotion_confirmation(bootstrap_db, monkeypatch):
    """Test interactive confirmation prompt [y/N] for promoting existing accounts."""
    import sys
    import builtins

    # 1. Create initial user
    bootstrap_privileged_user(
        full_name="Existing Operator",
        email="operator.existing@ntro.gov",
        password="InitialPassword123!",
        role=UserRole.SUPERVISOR,
        db_session=bootstrap_db,
    )

    # 2. Simulate operator declining interactive confirmation
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "n")

    cancelled = bootstrap_privileged_user(
        full_name="Existing Operator",
        email="operator.existing@ntro.gov",
        password="AttemptedNewPassword123!",
        role=UserRole.ADMINISTRATOR,
        confirm_promote=False,
        db_session=bootstrap_db,
    )
    assert cancelled is None

    # User remains SUPERVISOR
    user = bootstrap_db.query(domain.User).filter(domain.User.email == "operator.existing@ntro.gov").first()
    assert user.role == UserRole.SUPERVISOR

    # 3. Simulate operator agreeing to interactive confirmation
    monkeypatch.setattr(builtins, "input", lambda prompt="": "y")

    confirmed = bootstrap_privileged_user(
        full_name="Existing Operator",
        email="operator.existing@ntro.gov",
        password="ConfirmedNewPassword123!",
        role=UserRole.ADMINISTRATOR,
        confirm_promote=False,
        db_session=bootstrap_db,
    )
    assert confirmed is not None
    assert confirmed.role == UserRole.ADMINISTRATOR
    assert verify_password("ConfirmedNewPassword123!", confirmed.password_hash) is True

