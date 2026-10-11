"""
SentiCall v3 — Google Sign-In & Authentication Layer
OpenID Connect / OAuth 2.0 PKCE, audited tokens, server-side session management,
CSRF protection, role-based access control, and IDOR prevention.
"""

import os
import time
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any

import httpx
from fastapi import Request, Response, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from backend.config import (
    ENV, IS_PROD, PUBLIC_BASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    ADMIN_EMAILS, ALLOWED_EMAILS, DEV_LOGIN_BYPASS,
    IDLE_SESSION_TIMEOUT_SECONDS, ABSOLUTE_SESSION_TIMEOUT_SECONDS
)
from backend.db_models import get_db, User, SessionModel, SecurityLog

# Google OpenID Endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# In-memory transient store for OAuth PKCE state (state -> {code_verifier, nonce, redirect_uri, created_at})
_OAUTH_STATES: Dict[str, Dict[str, Any]] = {}

def clean_oauth_states():
    """Remove OAuth states older than 10 minutes."""
    now = time.time()
    expired = [k for k, v in _OAUTH_STATES.items() if now - v["created_at"] > 600]
    for k in expired:
        _OAUTH_STATES.pop(k, None)

def generate_pkce_pair() -> Tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return verifier, challenge

def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a session token or IP address."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def get_cookie_name(request: Request) -> str:
    """Use __Host-session in HTTPS, fallback to session_token for plain HTTP in dev."""
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        return "__Host-session"
    return "session_token"

def set_session_cookie(response: Response, request: Request, session_token: str, max_age: int = ABSOLUTE_SESSION_TIMEOUT_SECONDS):
    """Set secure HttpOnly cookie for session token."""
    cookie_name = get_cookie_name(request)
    is_secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https" or IS_PROD
    
    response.set_cookie(
        key=cookie_name,
        value=session_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
        max_age=max_age
    )
    # Also set fallback cookie if in dev mode
    if not is_secure and cookie_name != "session_token":
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
            max_age=max_age
        )

def clear_session_cookie(response: Response, request: Request):
    """Clear session cookie across possible names."""
    for c_name in ["__Host-session", "session_token"]:
        response.delete_cookie(key=c_name, path="/")

def create_user_session(db: Session, user: User, request: Request) -> Tuple[str, str]:
    """
    Create a server-side session with random 256-bit token.
    Store only its SHA-256 hash in DB.
    Returns: (raw_session_token, raw_csrf_token)
    """
    raw_token = secrets.token_hex(32)
    token_h = hash_token(raw_token)
    csrf_token = secrets.token_hex(32)

    client_ip = request.client.host if request.client else "unknown"
    ip_h = hash_token(client_ip)
    ua = request.headers.get("user-agent", "")[:250]

    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ABSOLUTE_SESSION_TIMEOUT_SECONDS)

    sess = SessionModel(
        token_hash=token_h,
        user_id=user.id,
        created_at=now,
        last_active_at=now,
        expires_at=expires,
        ip_hash=ip_h,
        user_agent=ua,
        csrf_token=csrf_token
    )
    db.add(sess)

    # Log security event
    sec_event = SecurityLog(
        user_id=user.id,
        event_type="login",
        ip_hash=ip_h,
        details_json=f'{{"ua": "{ua[:60]}"}}',
        created_at=now
    )
    db.add(sec_event)
    db.commit()

    return raw_token, csrf_token

def get_session_token_from_request(request: Request) -> Optional[str]:
    """Extract session token from __Host-session or session_token cookie or Bearer header."""
    cookie_name = get_cookie_name(request)
    token = request.cookies.get(cookie_name)
    if not token and cookie_name != "session_token":
        token = request.cookies.get("session_token")
    if not token:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    return token

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Return User if valid session exists, otherwise None (for public endpoints)."""
    token = get_session_token_from_request(request)
    if not token:
        # Check dev login bypass
        if DEV_LOGIN_BYPASS and not IS_PROD:
            dev_user_header = request.headers.get("x-dev-user-email")
            if dev_user_header:
                dev_user = db.query(User).filter(User.email == dev_user_header.lower()).first()
                if not dev_user:
                    dev_user = User(
                        google_sub=f"dev_sub_{hash_token(dev_user_header)[:16]}",
                        email=dev_user_header.lower(),
                        name="Development User",
                        role="admin" if dev_user_header.lower() in ADMIN_EMAILS else "user",
                        consent_version="v3.0",
                        consent_timestamp=datetime.now(timezone.utc)
                    )
                    db.add(dev_user)
                    db.commit()
                    db.refresh(dev_user)
                return dev_user
        return None

    token_h = hash_token(token)
    sess = db.query(SessionModel).filter(SessionModel.token_hash == token_h).first()
    if not sess:
        return None

    now = datetime.now(timezone.utc)
    sess_expires = sess.expires_at.replace(tzinfo=timezone.utc) if sess.expires_at.tzinfo is None else sess.expires_at
    sess_last_active = sess.last_active_at.replace(tzinfo=timezone.utc) if sess.last_active_at.tzinfo is None else sess.last_active_at

    # Check absolute lifetime
    if now > sess_expires:
        db.delete(sess)
        db.commit()
        return None

    # Check idle timeout (24h)
    if (now - sess_last_active).total_seconds() > IDLE_SESSION_TIMEOUT_SECONDS:
        db.delete(sess)
        db.commit()
        return None

    # Update last_active_at
    sess.last_active_at = now
    db.commit()

    user = db.query(User).filter(User.id == sess.user_id).first()
    if not user or user.is_suspended:
        return None

    # Attach csrf token to request state
    request.state.csrf_token = sess.csrf_token
    request.state.session_id = sess.id
    return user

def require_user(request: Request, user: Optional[User] = Depends(get_current_user_optional)) -> User:
    """Enforce authentication. Deny by default."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with Google."
        )
    return user

def require_admin(request: Request, user: User = Depends(require_user)) -> User:
    """Enforce admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required."
        )
    return user

def verify_csrf(request: Request, user: User = Depends(require_user)):
    """
    Verify CSRF on state-changing requests (POST, PUT, PATCH, DELETE).
    Checks X-CSRF-Token header and Origin header.
    """
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        csrf_header = request.headers.get("x-csrf-token")
        expected_csrf = getattr(request.state, "csrf_token", None)
        
        # Origin check
        origin = request.headers.get("origin")
        if origin:
            expected_origin = PUBLIC_BASE_URL
            host_header = request.headers.get("host")
            # Allowed origins: PUBLIC_BASE_URL or same host
            valid_origins = [expected_origin, f"http://{host_header}", f"https://{host_header}"]
            if origin not in valid_origins and not any(origin.startswith(v) for v in valid_origins):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-origin request rejected.")

        if expected_csrf and csrf_header != expected_csrf:
            # Allow dev bypass in local test if explicitly set
            if not (DEV_LOGIN_BYPASS and not IS_PROD and csrf_header == "dev-test-csrf"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing CSRF token.")
    return True
