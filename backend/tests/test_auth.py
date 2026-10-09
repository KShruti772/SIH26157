"""
SAT-SA Local Authentication, Authorization, & Security Hardening Tests.
Tests cover:
1. Public Registration (default REVIEWER, rejection of SUPERVISOR & ADMINISTRATOR self-registration, validation)
2. Login (valid credentials, wrong password, unknown email, inactive account)
3. Current User /me (authenticated, missing token, invalid/tampered/expired/malformed tokens)
4. Central Route Protection (unauthenticated access to protected data/reporting/audit routes rejected with 401)
5. Database-Backed Logout Invalidation (token revocation, rejection of revoked token across all routes)
6. Endpoint-level RBAC & Permission Matrix (Supervisory & Admin operations restricted)
7. Administrator User Management & Bootstrap Provisioning
8. Secret Key Configuration Fail-Closed Enforcement
9. Audit Logging & Zero Credential/Secret Leakage
"""

import os
import pytest
import datetime
import uuid
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
    get_secret_key,
    require_role,
    UserRole,
)
from app.services.audit import AuditService, EventType
from bootstrap_admin import bootstrap_privileged_user


# =========================================================================
# TEST FIXTURES
# =========================================================================

@pytest.fixture
def auth_db():
    """Isolated in-memory SQLite database for authentication and RBAC tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Pre-seed an active admin user
    admin = domain.User(
        id="USR-ADM-01",
        full_name="Lead Admin Chief",
        email="admin.chief@ntro.gov",
        password_hash=hash_password("AdminPass123!"),
        organization="NTRO HQ Operations",
        role=UserRole.ADMINISTRATOR,
        is_active=True,
    )
    session.add(admin)

    # Pre-seed an active supervisor user
    supervisor = domain.User(
        id="USR-SUP-01",
        full_name="Lead Supervisor Smith",
        email="supervisor.smith@ntro.gov",
        password_hash=hash_password("SuperSecretPass123!"),
        organization="NTRO Cyber Security Division",
        role=UserRole.SUPERVISOR,
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
        role=UserRole.REVIEWER,
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
        role=UserRole.REVIEWER,
        is_active=False,
    )
    session.add(inactive_user)

    # Pre-seed an entity and finding for endpoint testing
    entity = domain.Entity(id="CSE-001", name="State Power Grid", sector="Energy", assessment_period="2026-Q3")
    session.add(entity)

    finding = domain.Finding(
        id="FIND-001",
        entity_id="CSE-001",
        type="Execution Gap",
        category="execution_gap",
        severity="High",
        confidence=0.9,
        description="High severity test finding",
        rationale="Evidence rationale",
        evidence_ids=["AL-001"],
        status="Requires Review",
    )
    session.add(finding)

    # Pre-seed a review queue item
    review_item = domain.ReviewItem(
        id=1,
        finding_id="FIND-001",
        priority_score=90.0,
        status="Pending",
        notes="Initial review notes",
    )
    session.add(review_item)

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
# 1. REGISTRATION TESTS (STRICT ROLE PRIVILEGE ENFORCEMENT)
# =========================================================================

def test_successful_public_registration_defaults_to_reviewer(client, auth_db):
    """Test standard public registration succeeds and grants only REVIEWER role."""
    payload = {
        "full_name": "New Analyst Alpha",
        "email": "analyst.alpha@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "National SOC Coordination",
        "role": "REVIEWER",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert data["role"] == "REVIEWER"
    assert data["name"] == "New Analyst Alpha"
    assert data["user"]["email"] == "analyst.alpha@ntro.gov"

    user = auth_db.query(domain.User).filter(domain.User.email == "analyst.alpha@ntro.gov").first()
    assert user is not None
    assert user.role == "REVIEWER"
    assert user.password_hash != "SecurePassword2026!"
    assert verify_password("SecurePassword2026!", user.password_hash) is True


def test_registration_supervisor_self_registration_rejected(client):
    """Test that attempting to self-register as SUPERVISOR is strictly rejected with HTTP 403."""
    payload = {
        "full_name": "Illegal Supervisor Attempt",
        "email": "supervisor.attempt@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "SUPERVISOR",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 403
    assert "not permitted" in response.json()["detail"].lower()


def test_registration_administrator_self_registration_rejected(client):
    """Test that attempting to self-register as ADMINISTRATOR is strictly rejected with HTTP 403."""
    payload = {
        "full_name": "Illegal Admin Attempt",
        "email": "admin.attempt@ntro.gov",
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "ADMINISTRATOR",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 403
    assert "not permitted" in response.json()["detail"].lower()


def test_registration_duplicate_email(client):
    """Test registering with an existing email returns HTTP 409 Conflict."""
    payload = {
        "full_name": "Duplicate User",
        "email": "supervisor.smith@ntro.gov", # Already exists
        "password": "SecurePassword2026!",
        "confirm_password": "SecurePassword2026!",
        "organization": "NTRO",
        "role": "REVIEWER",
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


def test_registration_invalid_role(client):
    """Test registration rejects unrecognized roles with 400 Bad Request."""
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
    """Test authenticating with valid email and password returns signed JWT with unique JTI."""
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

    token_payload = decode_access_token(data["token"])
    assert token_payload["email"] == "supervisor.smith@ntro.gov"
    assert token_payload["role"] == "SUPERVISOR"
    assert "jti" in token_payload


def test_login_wrong_password(client):
    """Test authenticating with incorrect password returns generic HTTP 401."""
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
# 3. CURRENT USER & TOKEN VALIDATION TESTS
# =========================================================================

def test_get_current_user_profile(client):
    """Test /api/auth/me returns current user profile when authenticated."""
    login_res = client.post("/api/auth/login", json={
        "email": "supervisor.smith@ntro.gov",
        "password": "SuperSecretPass123!",
    })
    token = login_res.json()["token"]

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
    """Test /api/auth/me rejects invalid or tampered JWT tokens with HTTP 401."""
    headers = {"Authorization": "Bearer invalid.token.signature"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


def test_get_current_user_malformed_token_never_produces_500(client):
    """Test malformed JWT payloads consistently return HTTP 401, never HTTP 500."""
    malformed_tokens = [
        "not-even-a-jwt",
        "abc.def",
        "a.b.c.d",
        "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjMifQ.sig",
        "!!!.@@@.###",
    ]
    for bad_token in malformed_tokens:
        headers = {"Authorization": f"Bearer {bad_token}"}
        res = client.get("/api/auth/me", headers=headers)
        assert res.status_code == 401, f"Expected 401 for token '{bad_token}', got {res.status_code}"


# =========================================================================
# 4. CENTRAL ROUTE PROTECTION TESTS
# =========================================================================

def test_unauthenticated_requests_to_protected_endpoints_rejected(client):
    """Verify all protected data, analytics, reporting, and audit endpoints reject unauthenticated requests."""
    protected_endpoints = [
        ("GET", "/api/uploads"),
        ("GET", "/api/dashboard/summary"),
        ("GET", "/api/entities"),
        ("GET", "/api/findings"),
        ("GET", "/api/reports"),
        ("GET", "/api/audit/events"),
        ("POST", "/api/upload"),
        ("POST", "/api/analysis/run"),
    ]
    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path)
        assert res.status_code == 401, f"Endpoint {method} {path} should require authentication, got {res.status_code}"


def test_public_endpoints_accessible_without_authentication(client):
    """Verify public endpoints remain accessible without tokens."""
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}


# =========================================================================
# 5. DATABASE-BACKED LOGOUT & TOKEN REVOCATION TESTS
# =========================================================================

def test_logout_revokes_token_persistently(client, auth_db):
    """Test that logging out persistently revokes the token, causing all subsequent calls to return 401."""
    # 1. Login
    login_res = client.post("/api/auth/login", json={
        "email": "reviewer.jones@ntro.gov",
        "password": "ReviewerPass123!",
    })
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify token works on protected endpoints before logout
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    dash_res = client.get("/api/dashboard/summary", headers=headers)
    assert dash_res.status_code == 200

    # 3. Execute Logout
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "ok"

    # Verify RevokedToken entry exists in database
    token_payload = decode_access_token(token)
    jti = token_payload["jti"]
    revoked_entry = auth_db.query(domain.RevokedToken).filter(domain.RevokedToken.jti == jti).first()
    assert revoked_entry is not None
    assert revoked_entry.user_id == "USR-REV-01"

    # 4. Verify the revoked token is REJECTED on subsequent requests
    me_after_logout = client.get("/api/auth/me", headers=headers)
    assert me_after_logout.status_code == 401
    assert "revoked" in me_after_logout.json()["detail"].lower()

    findings_after_logout = client.get("/api/findings", headers=headers)
    assert findings_after_logout.status_code == 401
    assert "revoked" in findings_after_logout.json()["detail"].lower()


# =========================================================================
# 6. ENDPOINT-LEVEL RBAC & PERMISSION MATRIX TESTS
# =========================================================================

def test_rbac_reviewer_cannot_perform_supervisory_operations(client):
    """Test that a user with REVIEWER role is rejected with 403 Forbidden on supervisory actions."""
    login_res = client.post("/api/auth/login", json={
        "email": "reviewer.jones@ntro.gov",
        "password": "ReviewerPass123!",
    })
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Reviewer attempting finding adjudication decision -> 403
    decision_res = client.post(
        "/api/findings/FIND-001/decision",
        json={"decision": "CONFIRMED", "notes": "Analyst attempted confirmation"},
        headers=headers,
    )
    assert decision_res.status_code == 403
    assert "Access denied" in decision_res.json()["detail"]

    # Reviewer attempting review queue item patch -> 403
    queue_patch_res = client.patch(
        "/api/review-queue/1",
        json={"status": "Under Investigation", "notes": "Unauthorized modification"},
        headers=headers,
    )
    assert queue_patch_res.status_code == 403
    assert "Access denied" in queue_patch_res.json()["detail"]

    # Reviewer attempting evidence request creation -> 403
    ev_req_res = client.post(
        "/api/findings/FIND-001/evidence-requests",
        json={"request_type": "SUPPLEMENTAL_LOGS", "reason": "Need logs"},
        headers=headers,
    )
    assert ev_req_res.status_code == 403
    assert "Access denied" in ev_req_res.json()["detail"]

    # Reviewer attempting report generation -> 403
    report_gen_res = client.post("/api/reports/generate", json={}, headers=headers)
    assert report_gen_res.status_code == 403

    # Reviewer attempting agent analysis trigger -> 403
    agent_res = client.post("/api/agents/analyze/FIND-001", headers=headers)
    assert agent_res.status_code == 403

    # Reviewer attempting audit snapshot -> 403
    snapshot_res = client.post("/api/audit/snapshots/CSE-001", headers=headers)
    assert snapshot_res.status_code == 403


def test_rbac_supervisor_allowed_supervisory_operations(client):
    """Test that a user with SUPERVISOR role can execute supervisory actions."""
    login_res = client.post("/api/auth/login", json={
        "email": "supervisor.smith@ntro.gov",
        "password": "SuperSecretPass123!",
    })
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Supervisor finding adjudication -> allowed (not 403)
    decision_res = client.post(
        "/api/findings/FIND-001/decision",
        json={"decision": "CONFIRM", "notes": "Supervisor verified finding validity"},
        headers=headers,
    )
    assert decision_res.status_code == 200

    # Supervisor review queue item patch -> allowed (200)
    queue_patch_res = client.patch(
        "/api/review-queue/1",
        json={"status": "In Progress", "notes": "Supervisor reviewed"},
        headers=headers,
    )
    assert queue_patch_res.status_code == 200
    assert queue_patch_res.json()["status"] == "In Progress"

    # Supervisor evidence request creation -> allowed (200)
    ev_req_res = client.post(
        "/api/findings/FIND-001/evidence-requests",
        json={"request_type": "SUPPLEMENTAL_LOGS", "reason": "Need investigation records"},
        headers=headers,
    )
    assert ev_req_res.status_code == 200

    # Supervisor report generation -> allowed (not 403)
    report_gen_res = client.post("/api/reports/generate", json={"entity_id": "CSE-001"}, headers=headers)
    assert report_gen_res.status_code == 200


def test_rbac_admin_only_endpoints(client):
    """Test administrator endpoints (/api/admin/users) reject Reviewer and Supervisor but allow Admin."""
    # 1. Reviewer attempt -> 403
    rev_token = client.post("/api/auth/login", json={
        "email": "reviewer.jones@ntro.gov", "password": "ReviewerPass123!"
    }).json()["token"]
    rev_res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {rev_token}"})
    assert rev_res.status_code == 403

    # 2. Supervisor attempt -> 403
    sup_token = client.post("/api/auth/login", json={
        "email": "supervisor.smith@ntro.gov", "password": "SuperSecretPass123!"
    }).json()["token"]
    sup_res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {sup_token}"})
    assert sup_res.status_code == 403

    # 3. Admin attempt -> 200
    adm_token = client.post("/api/auth/login", json={
        "email": "admin.chief@ntro.gov", "password": "AdminPass123!"
    }).json()["token"]
    adm_res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {adm_token}"})
    assert adm_res.status_code == 200
    assert len(adm_res.json()) >= 3


# =========================================================================
# 7. SECRET CONFIGURATION FAIL-CLOSED ENFORCEMENT
# =========================================================================

def test_missing_secret_key_fails_closed():
    """Verify that if SAT_SA_SECRET_KEY is missing/empty, token generation raises RuntimeError."""
    current_key = os.environ.get("SAT_SA_SECRET_KEY")
    try:
        os.environ["SAT_SA_SECRET_KEY"] = ""
        with pytest.raises(RuntimeError) as exc_info:
            get_secret_key()
        assert "FATAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
    finally:
        if current_key:
            os.environ["SAT_SA_SECRET_KEY"] = current_key


# =========================================================================
# 8. AUDIT LOGGING & ZERO CREDENTIAL LEAKAGE TESTS
# =========================================================================

def test_auth_audit_events_do_not_contain_secrets(client, auth_db):
    """Verify auth events never store plain passwords, hashes, or tokens in audit logs."""
    client.post("/api/auth/register", json={
        "full_name": "Audit Test Analyst",
        "email": "audit.test@ntro.gov",
        "password": "TopSecretPassword123!",
        "confirm_password": "TopSecretPassword123!",
        "organization": "Security Audit Cell",
        "role": "REVIEWER",
    })

    client.post("/api/auth/login", json={
        "email": "audit.test@ntro.gov",
        "password": "WrongPasswordAttempt!",
    })

    login_res = client.post("/api/auth/login", json={
        "email": "audit.test@ntro.gov",
        "password": "TopSecretPassword123!",
    })
    token = login_res.json()["token"]

    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    audit_events = auth_db.query(domain.AuditEvent).all()
    assert len(audit_events) >= 3

    for evt in audit_events:
        payload_str = str(evt.payload_json or {})
        assert "TopSecretPassword123!" not in payload_str
        assert "WrongPasswordAttempt!" not in payload_str
        assert "pbkdf2_sha256" not in payload_str
        assert token not in payload_str


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
    reg_res = client.post("/api/auth/register", json={
        "full_name": "API Security Check",
        "email": "api.sec@ntro.gov",
        "password": "SecretPassword123!",
        "confirm_password": "SecretPassword123!",
        "organization": "Security Cell",
        "role": "REVIEWER",
    })
    assert reg_res.status_code == 201
    reg_json_str = str(reg_res.json())
    assert "password_hash" not in reg_json_str
    assert "SecretPassword123!" not in reg_json_str

    login_res = client.post("/api/auth/login", json={
        "email": "api.sec@ntro.gov",
        "password": "SecretPassword123!",
    })
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    login_json_str = str(login_res.json())
    assert "password_hash" not in login_json_str
    assert "SecretPassword123!" not in login_json_str

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_json_str = str(me_res.json())
    assert "password_hash" not in me_json_str
    assert "SecretPassword123!" not in me_json_str


# =========================================================================
# 9. JWT CLAIMS VALIDATION & REVOCATION ROBUSTNESS TESTS
# =========================================================================

def test_jwt_claims_strict_validation(auth_db):
    """Verify that malformed claims (empty sub, empty jti, non-numeric timestamps, future iat) are strictly rejected."""
    user = auth_db.query(domain.User).filter(domain.User.email == "reviewer.jones@ntro.gov").first()
    valid_token = create_access_token(user)

    # 1. Valid token decodes successfully
    payload = decode_access_token(valid_token)
    assert payload["sub"] == user.id
    assert "jti" in payload
    assert isinstance(payload["iat"], (int, float))
    assert isinstance(payload["exp"], (int, float))

    import hmac
    import hashlib
    import json
    from app.services.auth import _base64url_encode, get_secret_key, JWT_ALGORITHM

    secret = get_secret_key()
    header_b64 = _base64url_encode(json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode("utf-8"))

    def _craft_token(custom_payload: dict) -> str:
        payload_b64 = _base64url_encode(json.dumps(custom_payload).encode("utf-8"))
        sig = hmac.new(secret.encode("utf-8"), f"{header_b64}.{payload_b64}".encode("utf-8"), hashlib.sha256).digest()
        return f"{header_b64}.{payload_b64}.{_base64url_encode(sig)}"

    # Missing/empty sub
    with pytest.raises(ValueError) as exc:
        decode_access_token(_craft_token({"sub": "", "jti": "test-jti", "iat": int(datetime.datetime.utcnow().timestamp()), "exp": int(datetime.datetime.utcnow().timestamp()) + 3600}))
    assert "sub" in str(exc.value)

    # Missing/empty jti
    with pytest.raises(ValueError) as exc:
        decode_access_token(_craft_token({"sub": "USR-01", "jti": "   ", "iat": int(datetime.datetime.utcnow().timestamp()), "exp": int(datetime.datetime.utcnow().timestamp()) + 3600}))
    assert "jti" in str(exc.value)

    # Future iat (issued 5 minutes in future)
    future_ts = int(datetime.datetime.utcnow().timestamp()) + 300
    with pytest.raises(ValueError) as exc:
        decode_access_token(_craft_token({"sub": "USR-01", "jti": "test-jti", "iat": future_ts, "exp": future_ts + 3600}))
    assert "future" in str(exc.value)

    # exp <= iat
    now_ts = int(datetime.datetime.utcnow().timestamp())
    with pytest.raises(ValueError) as exc:
        decode_access_token(_craft_token({"sub": "USR-01", "jti": "test-jti", "iat": now_ts, "exp": now_ts - 100}))
    assert "exp" in str(exc.value)


def test_revoke_token_database_failure_simulation(auth_db):
    """Simulate a database commit/revocation failure and verify revoke_token raises RuntimeError and rolls back."""
    from unittest.mock import MagicMock
    from app.services.auth import revoke_token

    user = auth_db.query(domain.User).filter(domain.User.email == "reviewer.jones@ntro.gov").first()
    token = create_access_token(user)

    # Mock DB session where commit raises an operational exception
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.commit.side_effect = Exception("Operational database write failure")

    with pytest.raises(RuntimeError) as exc_info:
        revoke_token(mock_db, token, reason="UNIT_TEST_FAILURE")
    assert "Database error during token revocation" in str(exc_info.value)
    mock_db.rollback.assert_called_once()


def test_logout_database_failure_returns_500_without_leaking_secrets(client, auth_db, monkeypatch):
    """Verify that when database revocation fails during logout, 500 is returned and no tokens/secrets leak."""
    import app.routers.api as api_module

    # Login to get a valid token
    login_res = client.post("/api/auth/login", json={
        "email": "reviewer.jones@ntro.gov",
        "password": "ReviewerPass123!",
    })
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # Mock revoke_token in api router to simulate database failure
    def mock_failing_revoke(db, token, reason):
        raise RuntimeError("Simulated database failure during revocation")

    monkeypatch.setattr(api_module, "revoke_token", mock_failing_revoke)

    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 500
    res_text = res.text
    # Ensure it did NOT return success
    assert "Successfully logged out" not in res_text
    # Ensure no tokens or secret keys leak in response
    assert token not in res_text
    assert os.environ.get("SAT_SA_SECRET_KEY") not in res_text
    assert res.json()["detail"] == "Failed to revoke session token. Logout not completed."


def test_rbac_admin_allowed_supervisory_operations(client):
    """Test that ADMINISTRATOR retains intended access to review-queue and evidence-requests."""
    login_res = client.post("/api/auth/login", json={
        "email": "admin.chief@ntro.gov",
        "password": "AdminPass123!",
    })
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Admin PATCH /review-queue/{id} -> allowed (200)
    queue_patch_res = client.patch(
        "/api/review-queue/1",
        json={"status": "Resolved", "notes": "Administrator verified queue item"},
        headers=headers,
    )
    assert queue_patch_res.status_code == 200
    assert queue_patch_res.json()["status"] == "Resolved"

    # Admin POST /findings/{finding_id}/evidence-requests -> allowed (200)
    ev_req_res = client.post(
        "/api/findings/FIND-001/evidence-requests",
        json={"request_type": "SUPPLEMENTAL_LOGS", "reason": "Admin requested logs"},
        headers=headers,
    )
    assert ev_req_res.status_code == 200
    assert ev_req_res.json()["finding_id"] == "FIND-001"


def test_jwt_extended_negative_validations(auth_db):
    """Comprehensive negative tests for JWT algorithm confusion, invalid claim types, and malformed structures."""
    import hmac
    import hashlib
    import json
    from app.services.auth import _base64url_encode, get_secret_key, JWT_ALGORITHM

    secret = get_secret_key()
    valid_header_b64 = _base64url_encode(json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode("utf-8"))
    now_ts = int(datetime.datetime.utcnow().timestamp())

    def _craft_raw_token(hdr: dict, pld: dict, use_secret: str = secret) -> str:
        h_b64 = _base64url_encode(json.dumps(hdr).encode("utf-8"))
        p_b64 = _base64url_encode(json.dumps(pld).encode("utf-8"))
        sig = hmac.new(use_secret.encode("utf-8"), f"{h_b64}.{p_b64}".encode("utf-8"), hashlib.sha256).digest()
        return f"{h_b64}.{p_b64}.{_base64url_encode(sig)}"

    # 1. Algorithm 'none' attack
    none_token = _craft_raw_token({"alg": "none", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "iat": now_ts, "exp": now_ts + 3600})
    with pytest.raises(ValueError) as exc:
        decode_access_token(none_token)
    assert "algorithm" in str(exc.value).lower()

    # 2. Unsupported algorithm 'RS256'
    rs256_token = _craft_raw_token({"alg": "RS256", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "iat": now_ts, "exp": now_ts + 3600})
    with pytest.raises(ValueError) as exc:
        decode_access_token(rs256_token)
    assert "algorithm" in str(exc.value).lower()

    # 3. Non-numeric iat (boolean)
    bool_iat_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "iat": True, "exp": now_ts + 3600})
    with pytest.raises(ValueError) as exc:
        decode_access_token(bool_iat_token)
    assert "iat" in str(exc.value)

    # 4. Non-numeric exp (string)
    str_exp_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "iat": now_ts, "exp": "2026-12-31"})
    with pytest.raises(ValueError) as exc:
        decode_access_token(str_exp_token)
    assert "exp" in str(exc.value)

    # 5. Non-string sub (integer)
    int_sub_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": 12345, "jti": "jti-1", "iat": now_ts, "exp": now_ts + 3600})
    with pytest.raises(ValueError) as exc:
        decode_access_token(int_sub_token)
    assert "sub" in str(exc.value)

    # 6. Non-string jti (dict)
    dict_jti_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": "USR-01", "jti": {"id": 1}, "iat": now_ts, "exp": now_ts + 3600})
    with pytest.raises(ValueError) as exc:
        decode_access_token(dict_jti_token)
    assert "jti" in str(exc.value)

    # 7. Missing required claim 'iat'
    no_iat_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "exp": now_ts + 3600})
    with pytest.raises(ValueError) as exc:
        decode_access_token(no_iat_token)
    assert "missing required claim: 'iat'" in str(exc.value)

    # 8. Missing required claim 'exp'
    no_exp_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "iat": now_ts})
    with pytest.raises(ValueError) as exc:
        decode_access_token(no_exp_token)
    assert "missing required claim: 'exp'" in str(exc.value)

    # 9. Invalid signature key
    wrong_key_token = _craft_raw_token({"alg": "HS256", "typ": "JWT"}, {"sub": "USR-01", "jti": "jti-1", "iat": now_ts, "exp": now_ts + 3600}, use_secret="wrong-secret-key")
    with pytest.raises(ValueError) as exc:
        decode_access_token(wrong_key_token)
    assert "signature" in str(exc.value).lower()

    # 10. Malformed token formats
    with pytest.raises(ValueError):
        decode_access_token("singleparttoken")
    with pytest.raises(ValueError):
        decode_access_token("part1.part2")
    with pytest.raises(ValueError):
        decode_access_token(None)

