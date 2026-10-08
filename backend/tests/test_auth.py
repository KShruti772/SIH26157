"""
SAT-SA Local Authentication & RBAC Tests.
Tests cover:
1. Registration (success, duplicate email, invalid email, password mismatch, invalid role, admin rejection, weak password)
2. Login (valid credentials, wrong password, unknown email, inactive account)
3. Current User /me (authenticated user, missing token, invalid/tampered token)
4. Authorization & RBAC (supervisor access, reviewer access, unauthorized role)
5. Audit logging & credential privacy (no passwords, hashes, or tokens stored in audit trail)
"""

import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import domain
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    require_role,
    UserRole,
)
from app.services.audit import AuditService, EventType


# =========================================================================
# TEST FIXTURES
# =========================================================================

@pytest.fixture
def auth_db():
    """Isolated in-memory SQLite database for authentication tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Pre-seed an active supervisor user
    supervisor = domain.User(
        id="USR-SUP-01",
        full_name="Lead Supervisor Smith",
        email="supervisor.smith@ntro.gov",
        password_hash=hash_password("SuperSecretPass123!"),
        organization="NTRO Cyber Security Division",
        role="SUPERVISOR",
        is_active=True,
    )
    session.add(supervisor)

    # Pre-seed an active reviewer user
    reviewer = domain.User(
        id="USR-REV-01",
        full_name="Analyst Reviewer Jones",
        email="reviewer.jones@ntro.gov",
        password_hash=hash_password("ReviewerPass123!"),
        organization="NCIIPC Assessment Cell",
        role="REVIEWER",
        is_active=True,
    )
    session.add(reviewer)

    # Pre-seed an inactive user
    inactive_user = domain.User(
        id="USR-INACTIVE-01",
        full_name="Deactivated Examiner",
        email="inactive.user@ntro.gov",
        password_hash=hash_password("InactivePass123!"),
        organization="External Auditing",
        role="REVIEWER",
        is_active=False,
    )
    session.add(inactive_user)

    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(auth_db):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield auth_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =========================================================================
# 1. REGISTRATION TESTS
# =========================================================================

def test_successful_registration(client, auth_db):
    """Test standard user self-registration for allowed roles."""
    payload = {
        "full_name": "New Examiner Alpha",
        "email": "examiner.alpha@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "National SOC Coordination",
        "role": "SUPERVISOR",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert data["role"] == "SUPERVISOR"
    assert data["name"] == "New Examiner Alpha"
    assert data["user"]["email"] == "examiner.alpha@ntro.gov"

    # Verify user exists in database and password is encrypted
    user = auth_db.query(domain.User).filter(domain.User.email == "examiner.alpha@ntro.gov").first()
    assert user is not None
    assert user.password_hash != "SecurePassword2026!"
    assert verify_password("SecurePassword2026!", user.password_hash) is True


def test_registration_duplicate_email(client):
    """Test registering with an existing email returns HTTP 409 Conflict."""
    payload = {
        "full_name": "Duplicate User",
        "email": "supervisor.smith@ntro.gov", # Already exists
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "SUPERVISOR",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_registration_invalid_email(client):
    """Test registration rejects malformed email addresses."""
    payload = {
        "full_name": "Bad Email User",
        "email": "not-an-email",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "REVIEWER",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "valid email" in response.json()["detail"].lower()


def test_registration_password_mismatch(client):
    """Test registration rejects when password and confirm_password differ."""
    payload = {
        "full_name": "Mismatch User",
        "email": "mismatch@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "DifferentPassword2026!",
        "organization": "NTRO",
        "role": "REVIEWER",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "passwords do not match" in response.json()["detail"].lower()


def test_registration_weak_password(client):
    """Test registration enforces minimum password length (>= 8 chars)."""
    payload = {
        "full_name": "Short Password User",
        "email": "short@ntro.gov",
        "password": "short",
        "confirm_password": "short",
        "organization": "NTRO",
        "role": "REVIEWER",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "at least 8 characters" in response.json()["detail"]


def test_registration_administrator_rejected(client):
    """Test that ADMINISTRATOR role cannot be self-registered."""
    payload = {
        "full_name": "Illegal Admin",
        "email": "admin.attempt@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "ADMINISTRATOR",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 403
    assert "cannot be self-registered" in response.json()["detail"]


def test_registration_invalid_role(client):
    """Test registration rejects unrecognized roles."""
    payload = {
        "full_name": "Invalid Role User",
        "email": "invalid.role@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "ROOT_SUPERUSER",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "invalid role" in response.json()["detail"].lower()


# =========================================================================
# 2. LOGIN TESTS
# =========================================================================

def test_login_valid_credentials(client):
    """Test authenticating with valid email and password returns signed JWT."""
    payload = {
        "email": "supervisor.smith@ntro.gov",
        "password": "SuperSecretPass123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["role"] == "SUPERVISOR"
    assert data["name"] == "Lead Supervisor Smith"
    assert data["user"]["email"] == "supervisor.smith@ntro.gov"

    # Verify JWT decode
    token_payload = decode_access_token(data["token"])
    assert token_payload["email"] == "supervisor.smith@ntro.gov"
    assert token_payload["role"] == "SUPERVISOR"


def test_login_wrong_password(client):
    """Test authenticating with incorrect password returns HTTP 401 with generic error."""
    payload = {
        "email": "supervisor.smith@ntro.gov",
        "password": "WrongPassword!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_unknown_email(client):
    """Test authenticating with non-existent email returns generic HTTP 401."""
    payload = {
        "email": "nonexistent@ntro.gov",
        "password": "SomePassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_inactive_account(client):
    """Test authenticating with a deactivated account returns HTTP 403 Forbidden."""
    payload = {
        "email": "inactive.user@ntro.gov",
        "password": "InactivePass123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


# =========================================================================
# 3. CURRENT USER /ME TESTS
# =========================================================================

def test_get_current_user_profile(client):
    """Test /api/auth/me returns current user profile when authenticated."""
    # 1. Login
    login_res = client.post("/api/auth/login", json={
        "email": "supervisor.smith@ntro.gov",
        "password": "SuperSecretPass123!",
    })
    token = login_res.json()["token"]

    # 2. Call /api/auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert user_data["id"] == "USR-SUP-01"
    assert user_data["email"] == "supervisor.smith@ntro.gov"
    assert user_data["role"] == "SUPERVISOR"
    assert user_data["is_active"] is True


def test_get_current_user_missing_token(client):
    """Test /api/auth/me rejects requests without Authorization header."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_get_current_user_invalid_token(client):
    """Test /api/auth/me rejects invalid or tampered JWT tokens."""
    headers = {"Authorization": "Bearer invalid.token.signature"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


# =========================================================================
# 4. LOGOUT TEST
# =========================================================================

def test_logout_endpoint(client):
    """Test /api/auth/logout succeeds with authenticated session."""
    login_res = client.post("/api/auth/login", json={
        "email": "reviewer.jones@ntro.gov",
        "password": "ReviewerPass123!",
    })
    token = login_res.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "ok"


# =========================================================================
# 5. AUDIT LOGGING & CREDENTIAL PRIVACY TESTS
# =========================================================================

def test_auth_audit_events_do_not_contain_secrets(client, auth_db):
    """Verify auth events are chained and NEVER store plain passwords, hashes, or tokens in audit logs."""
    # Register a user
    client.post("/api/auth/register", json={
        "full_name": "Audit Test User",
        "email": "audit.test@ntro.gov",
        "password": "TopSecretPassword123!",
        "confirm_password": "TopSecretPassword123!",
        "organization": "Security Audit Cell",
        "role": "REVIEWER",
    })

    # Failed login attempt
    client.post("/api/auth/login", json={
        "email": "audit.test@ntro.gov",
        "password": "WrongPasswordAttempt!",
    })

    # Successful login attempt
    login_res = client.post("/api/auth/login", json={
        "email": "audit.test@ntro.gov",
        "password": "TopSecretPassword123!",
    })
    token = login_res.json()["token"]

    # Logout
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    # Inspect all audit events in the database
    audit_events = auth_db.query(domain.AuditEvent).all()
    assert len(audit_events) >= 3

    for evt in audit_events:
        payload = evt.payload_json or {}
        payload_str = str(payload)

        # Strictly assert NO secrets leaked
        assert "TopSecretPassword123!" not in payload_str
        assert "WrongPasswordAttempt!" not in payload_str
        assert "pbkdf2_sha256" not in payload_str
        assert token not in payload_str


# =========================================================================
# 6. RBAC AUTHORIZATION TESTS
# =========================================================================

def test_rbac_supervisor_access_allowed(auth_db):
    """Test require_role allows SUPERVISOR for supervisory operations."""
    supervisor = auth_db.query(domain.User).filter(domain.User.email == "supervisor.smith@ntro.gov").first()
    checker = require_role(["SUPERVISOR"])
    res = checker(current_user=supervisor)
    assert res.id == supervisor.id
    assert res.role == "SUPERVISOR"


def test_rbac_reviewer_access_allowed(auth_db):
    """Test require_role allows REVIEWER for reviewer operations."""
    reviewer = auth_db.query(domain.User).filter(domain.User.email == "reviewer.jones@ntro.gov").first()
    checker = require_role(["REVIEWER", "SUPERVISOR"])
    res = checker(current_user=reviewer)
    assert res.id == reviewer.id
    assert res.role == "REVIEWER"


def test_rbac_unauthorized_role_rejected(auth_db):
    """Test require_role raises HTTP 403 Forbidden for unauthorized roles."""
    from fastapi import HTTPException
    reviewer = auth_db.query(domain.User).filter(domain.User.email == "reviewer.jones@ntro.gov").first()
    checker = require_role(["SUPERVISOR", "ADMINISTRATOR"])
    
    with pytest.raises(HTTPException) as exc_info:
        checker(current_user=reviewer)
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail


# =========================================================================
# 7. SECURITY ISOLATION & HASH STORAGE TESTS
# =========================================================================

def test_password_is_hashed_and_not_plaintext(auth_db):
    """Verify password in database is salted PBKDF2-HMAC-SHA256 and never plaintext."""
    user = auth_db.query(domain.User).filter(domain.User.email == "supervisor.smith@ntro.gov").first()
    assert user.password_hash is not None
    assert user.password_hash.startswith("pbkdf2_sha256$100000$")
    assert "SuperSecretPass123!" not in user.password_hash
    assert verify_password("SuperSecretPass123!", user.password_hash) is True
    assert verify_password("WrongPass", user.password_hash) is False


def test_password_and_hash_never_returned_by_api(client):
    """Verify registration, login, and /me responses NEVER expose password or password_hash."""
    # 1. Register
    reg_res = client.post("/api/auth/register", json={
        "full_name": "API Security Check",
        "email": "api.sec@ntro.gov",
        "password": "SecretPassword123!",
        "confirm_password": "SecretPassword123!",
        "organization": "Security Cell",
        "role": "SUPERVISOR",
    })
    assert reg_res.status_code == 201
    reg_json_str = str(reg_res.json())
    assert "password_hash" not in reg_json_str
    assert "SecretPassword123!" not in reg_json_str

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": "api.sec@ntro.gov",
        "password": "SecretPassword123!",
    })
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    login_json_str = str(login_res.json())
    assert "password_hash" not in login_json_str
    assert "SecretPassword123!" not in login_json_str

    # 3. /me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_json_str = str(me_res.json())
    assert "password_hash" not in me_json_str
    assert "SecretPassword123!" not in me_json_str

