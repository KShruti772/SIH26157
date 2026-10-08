"""
SAT-SA Local Authentication & Security Service.
Provides PBKDF2-HMAC-SHA256 password hashing, deterministic HMAC-SHA256 JWT generation,
token verification, and role-based authorization for offline air-gapped deployments.
"""

import os
import hmac
import hashlib
import base64
import json
import secrets
import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_db
from app.models import domain

# Secret key for offline JWT signing
SECRET_KEY = os.environ.get("SAT_SA_SECRET_KEY", "sat-sa-offline-supervisory-secret-key-2026-ntro")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
PBKDF2_ITERATIONS = 100_000

# Controlled User Roles
class UserRole:
    SUPERVISOR = "SUPERVISOR"
    REVIEWER = "REVIEWER"
    ADMINISTRATOR = "ADMINISTRATOR"

ALLOWED_SELF_REGISTER_ROLES = [UserRole.SUPERVISOR, UserRole.REVIEWER]

security_scheme = HTTPBearer(auto_error=False)


# =========================================================================
# SECURE PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# =========================================================================

def hash_password(password: str) -> str:
    """
    Hashes password using PBKDF2-HMAC-SHA256 with 16-byte random salt and 100,000 iterations.
    Format: pbkdf2_sha256$100000$<salt_hex>$<hash_hex>
    """
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies plain password against stored PBKDF2-HMAC-SHA256 hash using constant-time comparison.
    """
    if not hashed_password or not plain_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_key_hex = parts[3]

        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(computed_key.hex(), expected_key_hex)
    except Exception:
        return False


# =========================================================================
# STATELESS JWT ENCODING & DECODING (HMAC-SHA256)
# =========================================================================

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user: domain.User, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """
    Generates an RFC-7519 compliant JSON Web Token signed with HMAC-SHA256.
    """
    now = datetime.datetime.utcnow()
    expire = now + (expires_delta or datetime.timedelta(hours=JWT_EXPIRATION_HOURS))

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.full_name,
        "role": user.role,
        "org": user.organization,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode("utf-8"))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode("utf-8"))
    
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and cryptographically verifies an HMAC-SHA256 signed JWT.
    Raises ValueError if invalid, expired, or tampered.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token format.")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _base64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("JWT signature verification failed.")

    payload_json = _base64url_decode(payload_b64).decode("utf-8")
    payload = json.loads(payload_json)

    # Check expiration
    exp = payload.get("exp")
    if exp and datetime.datetime.utcnow().timestamp() > exp:
        raise ValueError("JWT token has expired.")

    return payload


# =========================================================================
# FASTAPI AUTHENTICATION & AUTHORIZATION DEPENDENCIES
# =========================================================================

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> domain.User:
    """
    Enforces authentication on protected endpoints.
    Resolves active user from valid JWT Bearer token.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(auth.credentials)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(ve)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    user = db.query(domain.User).filter(domain.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")
    return user


def require_role(allowed_roles: List[str]):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that authenticated user possesses one of the allowed roles.
    """
    allowed_norm = [r.upper() for r in allowed_roles]

    def _role_checker(current_user: domain.User = Depends(get_current_user)) -> domain.User:
        user_role = (current_user.role or "").upper()
        if user_role not in allowed_norm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{user_role}' does not have required permissions ({', '.join(allowed_norm)}).",
            )
        return current_user

    return _role_checker
