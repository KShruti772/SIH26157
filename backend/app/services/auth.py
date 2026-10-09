"""
SAT-SA Local Authentication & Security Service.
Provides PBKDF2-HMAC-SHA256 password hashing, deterministic HMAC-SHA256 JWT generation,
token verification, token revocation tracking, and role-based authorization for offline air-gapped deployments.
"""

import os
import hmac
import hashlib
import base64
import json
import secrets
import datetime
import uuid
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_db
from app.models import domain

logger = logging.getLogger("satsa.auth")

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
PBKDF2_ITERATIONS = 100_000


def get_secret_key() -> str:
    """
    Retrieves the SAT-SA secret key from the environment.
    Fails closed with a clear error if SAT_SA_SECRET_KEY is missing or empty.
    """
    key = os.environ.get("SAT_SA_SECRET_KEY")
    if not key or not key.strip():
        raise RuntimeError(
            "FATAL SECURITY CONFIGURATION ERROR: SAT_SA_SECRET_KEY environment variable is not configured. "
            "The application cannot sign or verify authentication tokens. "
            "Set SAT_SA_SECRET_KEY before starting SAT-SA."
        )
    return key.strip()


# Controlled User Roles
class UserRole:
    SUPERVISOR = "SUPERVISOR"
    REVIEWER = "REVIEWER"
    ADMINISTRATOR = "ADMINISTRATOR"


# Public self-registration is strictly restricted to REVIEWER role
ALLOWED_SELF_REGISTER_ROLES = [UserRole.REVIEWER]

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
# STATELESS JWT ENCODING & DECODING (HMAC-SHA256 WITH REVOCATION JTI)
# =========================================================================

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user: domain.User, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """
    Generates an RFC-7519 compliant JSON Web Token signed with HMAC-SHA256.
    Includes a unique token identifier (jti) for persistent revocation tracking.
    """
    secret = get_secret_key()
    now = datetime.datetime.utcnow()
    expire = now + (expires_delta or datetime.timedelta(hours=JWT_EXPIRATION_HOURS))
    token_jti = uuid.uuid4().hex

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "jti": token_jti,
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
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and cryptographically verifies an HMAC-SHA256 signed JWT.
    Validates structure, algorithm header, HMAC signature, required claims, and expiration.
    Raises ValueError if invalid, expired, or tampered.
    """
    secret = get_secret_key()
    if not token or not isinstance(token, str):
        raise ValueError("Invalid JWT token: token must be a non-empty string.")

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token format: token must consist of 3 period-separated parts.")

    header_b64, payload_b64, signature_b64 = parts

    try:
        header_json = _base64url_decode(header_b64).decode("utf-8")
        header = json.loads(header_json)
    except Exception as e:
        raise ValueError(f"Malformed JWT header: {str(e)}")

    if not isinstance(header, dict) or header.get("alg") != JWT_ALGORITHM:
        raise ValueError(f"Unsupported JWT algorithm: expected {JWT_ALGORITHM}.")

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _base64url_decode(signature_b64)
    except Exception as e:
        raise ValueError(f"Malformed JWT signature encoding: {str(e)}")

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("JWT signature verification failed: token signature is invalid or tampered.")

    try:
        payload_json = _base64url_decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception as e:
        raise ValueError(f"Malformed JWT payload: {str(e)}")

    if not isinstance(payload, dict):
        raise ValueError("Invalid JWT payload structure.")

    for claim in ["sub", "jti", "iat", "exp"]:
        if claim not in payload:
            raise ValueError(f"JWT missing required claim: '{claim}'.")

    # Validate claim types and non-empty values
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise ValueError("JWT claim 'sub' must be a non-empty string.")

    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti.strip():
        raise ValueError("JWT claim 'jti' must be a non-empty string.")

    iat = payload.get("iat")
    if isinstance(iat, bool) or not isinstance(iat, (int, float)):
        raise ValueError("JWT claim 'iat' must be a numeric timestamp.")

    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        raise ValueError("JWT claim 'exp' must be a numeric timestamp.")

    now_ts = datetime.datetime.utcnow().timestamp()

    # Check for unreasonable future issuance (allow 60s clock skew)
    if iat > now_ts + 60:
        raise ValueError("JWT token issued in the future.")

    if exp <= iat:
        raise ValueError("JWT claim 'exp' must be greater than 'iat'.")

    if now_ts > exp:
        raise ValueError("JWT token has expired.")

    return payload


# =========================================================================
# TOKEN REVOCATION (DATABASE-BACKED LOGOUT INVALIDATION)
# =========================================================================

def revoke_token(db: Session, token: str, reason: str = "LOGOUT") -> domain.RevokedToken:
    """
    Decodes the token and persistently records its unique JTI in the revoked_tokens table.
    Raises ValueError on invalid token, or RuntimeError if database persistence fails.
    Never swallows exceptions.
    """
    payload = decode_access_token(token)
    token_jti = payload.get("jti")
    user_id = payload.get("sub")
    exp = payload.get("exp")
    exp_dt = datetime.datetime.fromtimestamp(exp) if exp else None

    if not token_jti or not isinstance(token_jti, str) or not token_jti.strip():
        raise ValueError("Cannot revoke token: missing or empty 'jti' claim.")

    try:
        existing = db.query(domain.RevokedToken).filter(domain.RevokedToken.jti == token_jti).first()
        if existing:
            return existing

        revoked = domain.RevokedToken(
            jti=token_jti,
            user_id=user_id,
            revoked_at=datetime.datetime.utcnow(),
            expires_at=exp_dt,
            reason=reason,
        )
        db.add(revoked)
        db.commit()
        db.refresh(revoked)
        return revoked
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to persist token revocation for user_id={user_id}: {type(e).__name__}")
        raise RuntimeError("Database error during token revocation.")


# =========================================================================
# FASTAPI AUTHENTICATION & AUTHORIZATION DEPENDENCIES
# =========================================================================

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> domain.User:
    """
    Enforces authentication on protected endpoints.
    Resolves active user from valid JWT Bearer token and checks database-backed revocation status.
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
    except RuntimeError as re:
        logger.error(f"Internal authentication configuration error: {type(re).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication service error.",
        )
    except Exception as exc:
        logger.error(f"Unexpected error during token validation: {type(exc).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token validation failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_jti = payload.get("jti")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

    # Check if token is revoked
    if token_jti:
        try:
            revoked = db.query(domain.RevokedToken).filter(domain.RevokedToken.jti == token_jti).first()
            if revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked. Please sign in again.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Database error querying revoked token: {type(e).__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication verification failed.",
            )

    try:
        user = db.query(domain.User).filter(domain.User.id == user_id).first()
    except Exception as e:
        logger.error(f"Database error querying user profile: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication verification failed.",
        )

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")
    return user


def require_role(allowed_roles: List[str]):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that authenticated user possesses one of the allowed roles.
    Always resolves the active role from the database user record.
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
