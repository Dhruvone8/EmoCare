"""Supabase and guest authentication with owner-level authorization helpers."""
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWKClientError

logger = logging.getLogger("emocare.auth")

GUEST_ISSUER = "emocare"
GUEST_AUDIENCE = "emocare-guest"
SUPABASE_AUDIENCE = "authenticated"
GUEST_TOKEN_TTL = timedelta(days=30)

_bearer = HTTPBearer(auto_error=False)
_jwks_client: Optional[jwt.PyJWKClient] = None
_jwks_client_url: Optional[str] = None


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: Optional[str] = None
    is_guest: bool = False


def _auth_error(detail: str = "Invalid or expired authentication token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _supabase_issuer() -> Optional[str]:
    base_url = (
        os.getenv("SUPABASE_URL", "").strip()
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    ).rstrip("/")
    return f"{base_url}/auth/v1" if base_url else None


def _supabase_jwks_url() -> Optional[str]:
    explicit_url = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if explicit_url:
        return explicit_url
    issuer = _supabase_issuer()
    return f"{issuer}/.well-known/jwks.json" if issuer else None


def _get_jwks_client(url: str) -> jwt.PyJWKClient:
    global _jwks_client, _jwks_client_url
    if _jwks_client is None or _jwks_client_url != url:
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True, timeout=5)
        _jwks_client_url = url
    return _jwks_client


def _decode_guest_token(token: str) -> dict:
    secret = os.getenv("GUEST_SESSION_SECRET", "").strip()
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Guest authentication is not configured",
        )
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=GUEST_AUDIENCE,
        issuer=GUEST_ISSUER,
        leeway=30,
        options={"require": ["sub", "exp", "iat"]},
    )


def _decode_supabase_token(token: str) -> dict:
    issuer = _supabase_issuer()
    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured",
        )

    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()

    if algorithm == "HS256" and secret:
        key = secret
    elif algorithm in {"RS256", "ES256"}:
        jwks_url = _supabase_jwks_url()
        if not jwks_url:
            raise _auth_error()
        key = _get_jwks_client(jwks_url).get_signing_key_from_jwt(token).key
    else:
        raise _auth_error()

    return jwt.decode(
        token,
        key,
        algorithms=[algorithm],
        audience=SUPABASE_AUDIENCE,
        issuer=issuer,
        leeway=30,
        options={"require": ["sub", "exp", "iat"]},
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_error("Authentication required")

    token = credentials.credentials.strip()
    if not token:
        raise _auth_error("Authentication required")

    try:
        unverified_claims = jwt.decode(
            token,
            options={"verify_signature": False},
        )
        if (
            unverified_claims.get("iss") == GUEST_ISSUER
            and unverified_claims.get("aud") == GUEST_AUDIENCE
        ):
            claims = _decode_guest_token(token)
            is_guest = True
            if claims.get("token_type") != "guest":
                raise _auth_error()
        else:
            claims = _decode_supabase_token(token)
            is_guest = False
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise _auth_error() from None
    except (jwt.InvalidTokenError, PyJWKClientError, ValueError, TypeError):
        raise _auth_error() from None

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise _auth_error()
    user_id = user_id.strip()
    if is_guest and not user_id.startswith("guest_"):
        raise _auth_error()

    return AuthenticatedUser(
        id=user_id,
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
        is_guest=is_guest,
    )


def create_guest_token() -> dict:
    secret = os.getenv("GUEST_SESSION_SECRET", "").strip()
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Guest authentication is not configured",
        )

    now = datetime.now(timezone.utc)
    expires_at = now + GUEST_TOKEN_TTL
    user_id = f"guest_{uuid.uuid4().hex}"
    token = jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": expires_at,
            "iss": GUEST_ISSUER,
            "aud": GUEST_AUDIENCE,
            "token_type": "guest",
        },
        secret,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "expires_at": int(expires_at.timestamp()),
    }


def require_user_ownership(user_id: str, current_user: AuthenticatedUser) -> str:
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this user's data",
        )
    return current_user.id


def require_session_ownership(session_id: int, current_user: AuthenticatedUser) -> dict:
    from .db import get_therapy_session

    session = get_therapy_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapy session not found",
        )
    if session.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this therapy session",
        )
    return session
