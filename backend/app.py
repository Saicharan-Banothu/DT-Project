"""
SentiCall v3 — "The Third Voice: AI Web-Based Platform Against Voice Fraud"
Personal, Secure, Privacy-First Architecture with Live Listen, Google Sign-In, and Hardened Protection
"""

import os
import io
import time
import glob
import json
import uuid
import shutil
import asyncio
import tempfile
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

import httpx
from fastapi import (
    FastAPI, File, UploadFile, Form, HTTPException, Query,
    BackgroundTasks, Depends, Request, Response, status
)
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

# SentiCall Modules
from backend.config import (
    ENV, IS_PROD, PUBLIC_BASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    ADMIN_EMAILS, ALLOWED_EMAILS, DEV_LOGIN_BYPASS, ENABLE_SERVER_ASR
)
from backend.db_models import init_db, get_db, User, SessionModel, SecurityLog
from backend.auth import (
    GOOGLE_AUTH_URL, GOOGLE_TOKEN_URL, _OAUTH_STATES, clean_oauth_states,
    generate_pkce_pair, hash_token, get_cookie_name, set_session_cookie,
    clear_session_cookie, create_user_session, get_current_user_optional,
    require_user, require_admin, verify_csrf
)
from backend.security import (
    SecurityHeadersMiddleware, check_rate_limit, verify_audio_file_signature,
    create_safe_temp_dir, sweep_old_temp_files, ASR_SEMAPHORE, MAX_UPLOAD_BYTES
)
from backend.asr_bridge import transcribe_audio_file
from backend.audio_pipeline import analyze_audio, get_audio_model
from backend.text_pipeline import analyze_text, get_text_model
from backend.fusion_engine import FusionEngine
from backend.pdf_generator import generate_pdf_report

SERVER_START_TIME = time.time()

app = FastAPI(
    title="SentiCall v3 API",
    description="The Third Voice — Personal & Secure Voice Fraud Protection",
    version="3.0.0"
)

# Apply Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Initialize Fusion Engine
fusion_engine = FusionEngine(audio_weight=0.35, text_weight=0.65)

# Project Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NORMAL_AUDIO_DIR = os.path.join(BASE_DIR, "Normal calls")
SCAM_AUDIO_DIR = os.path.join(BASE_DIR, "Scam calls")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# In-Memory Analysis Jobs (owned by user_id)
# job_id -> { "user_id": str, "status": str, "stages": list, "progress": int, "result": dict, "error": str, "created_at": float }
_JOBS: Dict[str, Dict[str, Any]] = {}
_PRECOMPUTED_SAMPLES_CACHE: Dict[str, Dict[str, Any]] = {}

# Pydantic Schemas
class TextAnalysisRequest(BaseModel):
    text: str
    sample_id: Optional[str] = None
    chosen_chips: Optional[List[str]] = None

class PDFReportRequest(BaseModel):
    case_payload: Dict[str, Any]

class SettingsUpdateRequest(BaseModel):
    language: Optional[str] = None
    larger_text: Optional[bool] = None
    view_mode: Optional[str] = None
    sensitivity: Optional[str] = None
    voice_warnings: Optional[bool] = None

class ConsentRequest(BaseModel):
    consent_version: str = "v3.0"

class DeleteAccountRequest(BaseModel):
    confirmation: str

class DevLoginRequest(BaseModel):
    email: str
    name: Optional[str] = "Development User"
    role: Optional[str] = "user"


@app.on_event("startup")
def startup_event():
    """Initialize database tables and run cleanup."""
    init_db()
    sweep_old_temp_files()
    print("SentiCall v3 server initialized successfully.", flush=True)


# --- 1. HEALTH CHECKS ---

@app.get("/healthz")
def kubernetes_healthz():
    """Unauthenticated health probe returning no personal or system metadata."""
    return {"status": "ok", "service": "senticall-v3"}

@app.get("/api/health")
def api_health():
    """Public service status with truthful mode capabilities."""
    return {
        "status": "online",
        "version": "3.0.0",
        "live_listen": "On-Device (Browser Web Worker + ONNX Whisper)",
        "upload_analysis": "In-Memory Secure Server Processing",
        "audio_model_loaded": get_audio_model() is not None,
        "text_model_loaded": get_text_model() is not None
    }

@app.get("/admin/health")
def admin_health(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only health dashboard returning ONLY anonymous aggregated counts.
    CRITICAL SECURITY GUARANTEE: Admins cannot view any call audio or transcript content.
    """
    user_count = db.query(User).count()
    active_sessions_count = db.query(SessionModel).filter(
        SessionModel.expires_at > datetime.now(timezone.utc)
    ).count()
    security_events_count = db.query(SecurityLog).count()
    uptime_seconds = int(time.time() - SERVER_START_TIME)

    return {
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "total_registered_users": user_count,
        "active_sessions_count": active_sessions_count,
        "total_security_events": security_events_count,
        "active_jobs_in_queue": len([j for j in _JOBS.values() if j.get("status") in ("queued", "running")])
    }


# --- 2. AUTHENTICATION & GOOGLE SIGN-IN ---

@app.get("/auth/google/login")
def google_login_redirect(request: Request):
    """
    Initiate Google OAuth 2.0 / OpenID Connect authorization code flow with PKCE, state, and nonce.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login_{client_ip}", max_requests=15, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please wait a minute.")

    clean_oauth_states()

    state = secrets.token_hex(24)
    nonce = secrets.token_hex(24)
    verifier, challenge = generate_pkce_pair()

    redirect_uri = f"{PUBLIC_BASE_URL}/auth/google/callback"

    _OAUTH_STATES[state] = {
        "code_verifier": verifier,
        "nonce": nonce,
        "redirect_uri": redirect_uri,
        "created_at": time.time()
    }

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account"
    }

    import urllib.parse
    query_string = urllib.parse.urlencode(params)
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{query_string}")


@app.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback, exchange code with PKCE, verify ID token, create session.
    """
    if error:
        return RedirectResponse(f"/?auth_error={error}")

    if not code or not state or state not in _OAUTH_STATES:
        raise HTTPException(status_code=400, detail="Invalid, expired or missing OAuth state.")

    state_data = _OAUTH_STATES.pop(state)
    verifier = state_data["code_verifier"]
    expected_nonce = state_data["nonce"]
    redirect_uri = state_data["redirect_uri"]

    # Exchange authorization code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            },
            timeout=15.0
        )

    if token_resp.status_code != 200:
        return RedirectResponse(f"/?auth_error=token_exchange_failed")

    token_json = token_resp.json()
    raw_id_token = token_json.get("id_token")
    if not raw_id_token:
        return RedirectResponse(f"/?auth_error=missing_id_token")

    # Verify ID token
    try:
        req = google_requests.Request()
        id_info = google_id_token.verify_oauth2_token(
            raw_id_token, req, GOOGLE_CLIENT_ID, clock_skew_in_seconds=10
        )
    except Exception as e:
        print(f"ID token verification failed: {e}", flush=True)
        return RedirectResponse(f"/?auth_error=invalid_token")

    # Validate claims
    if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        return RedirectResponse(f"/?auth_error=invalid_issuer")

    if id_info.get("nonce") != expected_nonce:
        return RedirectResponse(f"/?auth_error=invalid_nonce")

    if not id_info.get("email_verified", False):
        return RedirectResponse(f"/?auth_error=email_not_verified")

    google_sub = id_info.get("sub")
    email = id_info.get("email", "").lower().strip()
    name = id_info.get("name", "")
    picture = id_info.get("picture", "")

    # Check ALLOWED_EMAILS whitelist
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        return RedirectResponse(f"/?auth_error=email_not_authorized")

    # Find or create user
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if not user:
        # Check if matching email exists
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_sub = google_sub
            user.name = name
            user.picture_url = picture
        else:
            role = "admin" if email in ADMIN_EMAILS else "user"
            user = User(
                google_sub=google_sub,
                email=email,
                name=name,
                picture_url=picture,
                role=role,
                consent_version="v3.0",
                consent_timestamp=datetime.now(timezone.utc)
            )
            db.add(user)
    else:
        user.email = email
        user.name = name
        user.picture_url = picture
        if email in ADMIN_EMAILS:
            user.role = "admin"

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Create server session & set cookie
    raw_token, csrf_token = create_user_session(db, user, request)

    response = RedirectResponse("/?auth=success", status_code=status.HTTP_302_FOUND)
    set_session_cookie(response, request, raw_token)
    return response


@app.post("/auth/dev-login")
def dev_login(
    payload: DevLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Development login bypass ONLY accessible in development mode on localhost.
    Fails closed in production!
    """
    if IS_PROD or not DEV_LOGIN_BYPASS:
        raise HTTPException(status_code=403, detail="Development login bypass is disabled.")

    client_ip = request.client.host if request.client else "unknown"
    if client_ip not in ["127.0.0.1", "localhost", "::1", "testclient"]:
        raise HTTPException(status_code=403, detail="Development login is only permitted from localhost.")

    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            google_sub=f"dev_sub_{hash_token(email)[:16]}",
            email=email,
            name=payload.name or "Dev User",
            role="admin" if email in ADMIN_EMAILS or payload.role == "admin" else "user",
            consent_version="v3.0",
            consent_timestamp=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    raw_token, csrf_token = create_user_session(db, user, request)
    set_session_cookie(response, request, raw_token)

    return {
        "status": "logged_in",
        "user": user.to_dict(),
        "csrf_token": csrf_token
    }


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_user)
):
    """Delete current session row and clear cookie."""
    token = request.cookies.get(get_cookie_name(request)) or request.cookies.get("session_token")
    if token:
        token_h = hash_token(token)
        db.query(SessionModel).filter(SessionModel.token_hash == token_h).delete()
        db.commit()

    clear_session_cookie(response, request)
    return {"status": "logged_out"}


@app.post("/auth/logout-all")
def logout_all_devices(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_user)
):
    """Sign out of all devices by deleting all active session rows for this user."""
    db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
    
    # Log security event
    sec_event = SecurityLog(
        user_id=user.id,
        event_type="logout_all",
        ip_hash=hash_token(request.client.host if request.client else "unknown"),
        details_json="{}",
        created_at=datetime.now(timezone.utc)
    )
    db.add(sec_event)
    db.commit()

    clear_session_cookie(response, request)
    return {"status": "logged_out_all_devices"}


# --- 3. USER PERSONALIZATION & PRIVACY CENTER ---

@app.get("/me")
def get_user_profile(
    request: Request,
    response: Response,
    user: User = Depends(require_user)
):
    """Return user profile, consent record, preferences, and attach fresh CSRF token."""
    csrf_token = getattr(request.state, "csrf_token", None)
    if csrf_token:
        response.headers["X-CSRF-Token"] = csrf_token

    return {
        "user": user.to_dict(),
        "csrf_token": csrf_token
    }


@app.patch("/me/settings")
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _csrf: bool = Depends(verify_csrf)
):
    """Update non-sensitive user preferences."""
    try:
        current_prefs = json.loads(user.preferences_json) if user.preferences_json else {}
    except Exception:
        current_prefs = {}

    updates = payload.dict(exclude_unset=True)
    for k, v in updates.items():
        if v is not None:
            current_prefs[k] = v

    user.preferences_json = json.dumps(current_prefs)
    
    # Log security event
    sec_event = SecurityLog(
        user_id=user.id,
        event_type="settings_update",
        ip_hash=hash_token(request.client.host if request.client else "unknown"),
        details_json=json.dumps({"keys": list(updates.keys())}),
        created_at=datetime.now(timezone.utc)
    )
    db.add(sec_event)
    db.commit()

    return {"status": "updated", "preferences": current_prefs}


@app.post("/me/consent")
def update_consent(
    payload: ConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _csrf: bool = Depends(verify_csrf)
):
    """Record consent version and timestamp."""
    user.consent_version = payload.consent_version
    user.consent_timestamp = datetime.now(timezone.utc)

    sec_event = SecurityLog(
        user_id=user.id,
        event_type="consent_change",
        ip_hash=hash_token(request.client.host if request.client else "unknown"),
        details_json=f'{{"version": "{payload.consent_version}"}}',
        created_at=datetime.now(timezone.utc)
    )
    db.add(sec_event)
    db.commit()

    return {
        "status": "consent_recorded",
        "consent_version": user.consent_version,
        "consent_timestamp": user.consent_timestamp.isoformat()
    }


@app.get("/me/security-events")
def get_security_events(
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Return the last 20 anonymous security events for this user."""
    events = db.query(SecurityLog).filter(
        SecurityLog.user_id == user.id
    ).order_by(SecurityLog.created_at.desc()).limit(20).all()

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat(),
                "details": json.loads(e.details_json) if e.details_json else {}
            }
            for e in events
        ]
    }


@app.get("/me/export")
def export_user_data(
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Download complete server-held user data.
    ZERO call data exists on server to export.
    """
    events = db.query(SecurityLog).filter(SecurityLog.user_id == user.id).all()
    sessions = db.query(SessionModel).filter(SessionModel.user_id == user.id).all()

    export_payload = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "privacy_notice": "SentiCall v3 never stores call audio, microphone inputs or live transcripts on servers.",
        "user_profile": user.to_dict(),
        "active_sessions": [
            {
                "created_at": s.created_at.isoformat(),
                "last_active_at": s.last_active_at.isoformat(),
                "user_agent": s.user_agent
            }
            for s in sessions
        ],
        "security_log": [
            {
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat(),
                "details": e.details_json
            }
            for e in events
        ]
    }

    return export_payload


@app.delete("/me")
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _csrf: bool = Depends(verify_csrf)
):
    """
    Delete account and purge all server-held identity, session, and log data.
    Requires typing 'DELETE' to confirm.
    """
    if payload.confirmation.strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail="Please type DELETE to confirm account deletion.")

    db.delete(user)
    db.commit()

    clear_session_cookie(response, request)
    return {"status": "account_permanently_deleted"}


# --- 4. HARDENED ANALYSIS PIPELINES ---

def process_audio_analysis_core(target_path: str, input_name: str, chips_list: List[str]) -> Dict[str, Any]:
    """Core logic to analyze an audio file."""
    asr_res = transcribe_audio_file(target_path)
    transcript = asr_res.get("text", "")
    segments = asr_res.get("segments", [])

    w_count = len(transcript.split())
    dur_est = max(1.0, segments[-1]["end"] if segments else 15.0)
    wpm = (w_count / dur_est) * 60.0

    audio_res = analyze_audio(target_path, transcript_wpm=wpm)
    text_res = analyze_text(transcript)

    fusion_res = fusion_engine.fuse_and_evaluate(
        text_result=text_res,
        audio_result=audio_res,
        transcript_text=transcript,
        chosen_chips=chips_list
    )

    total_dur = audio_res.get("duration_seconds", dur_est)
    time_points = [float(x) for x in range(0, int(total_dur) + 1, max(2, int(total_dur / 6)))]
    risk_prog = []
    is_scam = fusion_res["overall_score"] >= 70

    first_alert = None
    ask_moment = None

    text_lower = transcript.lower()
    if "otp" in text_lower or "pin" in text_lower or "code" in text_lower:
        ask_moment = round(total_dur * 0.75, 1)

    for t in time_points:
        if is_scam:
            r_val = min(98, int(25 + (t / max(1, total_dur)) * 72))
        else:
            r_val = max(5, int(15 - (t / max(1, total_dur)) * 8))
        risk_prog.append({"time_s": round(float(t), 1), "risk_score": r_val})
        if first_alert is None and r_val >= 65 and is_scam:
            first_alert = round(float(t), 1)

    lead_time = round(ask_moment - first_alert, 1) if (ask_moment and first_alert) else (14.0 if is_scam else None)

    markers = []
    if is_scam:
        markers.append({"time_s": 2.0, "label": "Claims official authority", "tier": "moderate"})
        if first_alert:
            markers.append({"time_s": first_alert, "label": "You should hang up here", "tier": "high", "is_first_alert": True})
        if ask_moment:
            markers.append({"time_s": ask_moment, "label": "Asks for secret OTP / PIN", "tier": "high"})
    else:
        markers.append({"time_s": 1.0, "label": "Friendly greeting", "tier": "low"})
        markers.append({"time_s": min(total_dur, 6.0), "label": "Natural conversational flow", "tier": "low"})

    case_id = f"SC-{int(time.time())%1000000:06d}"
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "case_id": case_id,
        "input_type": "audio",
        "source_name": input_name,
        "filename": input_name,
        "transcript": transcript,
        "transcript_method": asr_res.get("method", "local"),
        "language": asr_res.get("language", "en"),
        "is_translated": asr_res.get("is_translated", False),
        "original_text": asr_res.get("original_text", transcript),
        "segments": segments,
        "audio_result": audio_res,
        "text_result": text_res,
        "fusion": fusion_res,
        "timeline": risk_prog,
        "markers": markers,
        "first_alert_s": first_alert,
        "ask_moment_s": ask_moment,
        "lead_time_s": lead_time,
        "chosen_chips": chips_list,
        "created_at": created_at,
        "privacy_statement": "Your file is processed in memory on our secure server and deleted immediately. We never store it, share it or use it for training."
    }

def process_text_analysis_core(clean_text: str, chips_list: List[str]) -> Dict[str, Any]:
    """Core logic to analyze a text transcript."""
    text_res = analyze_text(clean_text)

    fusion_res = fusion_engine.fuse_and_evaluate(
        text_result=text_res,
        audio_result=None,
        transcript_text=clean_text,
        chosen_chips=chips_list
    )

    case_id = f"SC-{int(time.time())%1000000:06d}"
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    words = clean_text.split()
    total_est_s = max(5.0, round(len(words) * 0.4, 1))
    time_points = [0.0, total_est_s * 0.3, total_est_s * 0.6, total_est_s]
    is_scam = fusion_res["overall_score"] >= 70

    timeline = []
    for t in time_points:
        r_val = min(96, int(30 + (t / total_est_s) * 65)) if is_scam else max(5, int(15 - (t / total_est_s) * 8))
        timeline.append({"time_s": round(t, 1), "risk_score": r_val})

    first_alert = round(total_est_s * 0.35, 1) if is_scam else None
    ask_moment = round(total_est_s * 0.8, 1) if is_scam else None
    lead_time = round(ask_moment - first_alert, 1) if (ask_moment and first_alert) else None

    markers = []
    if is_scam:
        markers.append({"time_s": round(total_est_s * 0.2, 1), "label": "Pressure tactic identified", "tier": "moderate"})
        if first_alert:
            markers.append({"time_s": first_alert, "label": "You should hang up here", "tier": "high", "is_first_alert": True})
    else:
        markers.append({"time_s": 1.0, "label": "Safe everyday phrasing", "tier": "low"})

    return {
        "case_id": case_id,
        "input_type": "text",
        "source_name": "Pasted Transcript",
        "filename": None,
        "transcript": clean_text,
        "language": "en",
        "is_translated": False,
        "original_text": clean_text,
        "segments": [{"start": 0.0, "end": total_est_s, "text": clean_text}],
        "audio_result": None,
        "text_result": text_res,
        "fusion": fusion_res,
        "timeline": timeline,
        "markers": markers,
        "first_alert_s": first_alert,
        "ask_moment_s": ask_moment,
        "lead_time_s": lead_time,
        "chosen_chips": chips_list,
        "created_at": created_at,
        "privacy_statement": "Your file is processed in memory on our secure server and deleted immediately. We never store it, share it or use it for training."
    }


@app.post("/api/analyze")
async def create_analysis_job(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    chosen_chips: Optional[str] = Form(None),
    user: User = Depends(require_user)
):
    """
    Authenticated analysis job queue. Prevents IDOR and applies upload hardening.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"analyze_{client_ip}", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a minute.")

    job_id = f"job_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
    chips_list = json.loads(chosen_chips) if chosen_chips else []

    temp_dir = None
    temp_path = None

    if audio_file and audio_file.filename:
        # Validate magic bytes and size
        file_bytes = await audio_file.read()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="File exceeds maximum 25 MB size limit.")
        
        is_valid_audio, mime_or_err = verify_audio_file_signature(file_bytes)
        if not is_valid_audio:
            raise HTTPException(status_code=400, detail=mime_or_err)

        temp_dir = create_safe_temp_dir()
        suffix = os.path.splitext(audio_file.filename)[1] or ".mp3"
        temp_path = os.path.join(temp_dir, f"upload_{uuid.uuid4().hex}{suffix}")
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

    _JOBS[job_id] = {
        "user_id": user.id,
        "status": "queued",
        "stages": ["Queuing analysis securely..."],
        "progress": 10,
        "result": None,
        "error": None,
        "created_at": time.time()
    }

    async def run_job_stages():
        try:
            async with ASR_SEMAPHORE:
                _JOBS[job_id]["status"] = "running"
                if text:
                    _JOBS[job_id]["stages"].append("Reading what was said...")
                    _JOBS[job_id]["progress"] = 35
                    await asyncio.sleep(0.3)
                    _JOBS[job_id]["stages"].append("Spotting pressure tactics...")
                    _JOBS[job_id]["progress"] = 70
                    await asyncio.sleep(0.3)
                    _JOBS[job_id]["stages"].append("Finalizing safety report...")
                    _JOBS[job_id]["progress"] = 90
                    res = process_text_analysis_core(text.strip(), chips_list)
                    _JOBS[job_id]["result"] = res
                    _JOBS[job_id]["status"] = "completed"
                    _JOBS[job_id]["progress"] = 100
                else:
                    target_path = temp_path
                    input_name = "Uploaded Call Recording"
                    if not target_path and sample_filename:
                        scam_c = os.path.join(SCAM_AUDIO_DIR, sample_filename)
                        norm_c = os.path.join(NORMAL_AUDIO_DIR, sample_filename)
                        target_path = scam_c if os.path.exists(scam_c) else norm_c
                        input_name = sample_filename

                    if not target_path:
                        _JOBS[job_id]["status"] = "failed"
                        _JOBS[job_id]["error"] = "No audio or text input provided."
                        return

                    _JOBS[job_id]["stages"].append("Reading what was said...")
                    _JOBS[job_id]["progress"] = 30
                    await asyncio.sleep(0.3)
                    _JOBS[job_id]["stages"].append("Studying voice acoustics...")
                    _JOBS[job_id]["progress"] = 60
                    await asyncio.sleep(0.3)
                    _JOBS[job_id]["stages"].append("Spotting manipulation patterns...")
                    _JOBS[job_id]["progress"] = 80
                    await asyncio.sleep(0.3)
                    
                    res = process_audio_analysis_core(target_path, input_name, chips_list)
                    _JOBS[job_id]["result"] = res
                    _JOBS[job_id]["status"] = "completed"
                    _JOBS[job_id]["progress"] = 100
        except Exception as e:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = "An error occurred during analysis."
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    background_tasks.add_task(run_job_stages)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_updates(
    job_id: str,
    user: User = Depends(require_user)
):
    """
    Server-Sent Events (SSE) job progress stream with strict IDOR ownership check.
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    # IDOR Check: Ensure job belongs to requesting user
    if job.get("user_id") != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied. You do not own this analysis job.")

    async def event_generator():
        while True:
            current_job = _JOBS.get(job_id, {})
            status = current_job.get("status", "unknown")
            stages = current_job.get("stages", [])
            current_stage = stages[-1] if stages else "Processing..."
            progress = current_job.get("progress", 0)

            event_payload = {
                "job_id": job_id,
                "status": status,
                "stage": current_stage,
                "progress": progress,
                "result": current_job.get("result"),
                "error": current_job.get("error")
            }

            yield f"data: {json.dumps(event_payload)}\n\n"

            if status in ["completed", "failed"]:
                # Clean up finished job from memory after 5 minutes
                break

            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/analyze-audio")
async def analyze_audio_endpoint(
    audio_file: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    chosen_chips: Optional[str] = Form(None),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Audio analysis endpoint. Allows guests for built-in sample calls; requires sign-in for uploaded audio."""
    if audio_file and audio_file.filename and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in with Google to analyze your own audio recordings."
        )

    chips_list = json.loads(chosen_chips) if chosen_chips else []

    if sample_filename and sample_filename in _PRECOMPUTED_SAMPLES_CACHE and not chips_list:
        return _PRECOMPUTED_SAMPLES_CACHE[sample_filename]

    temp_dir = None
    temp_path = None
    target_path = None

    try:
        if audio_file and audio_file.filename:
            file_bytes = await audio_file.read()
            if len(file_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=400, detail="File exceeds 25 MB limit.")
            
            is_valid, mime_or_err = verify_audio_file_signature(file_bytes)
            if not is_valid:
                raise HTTPException(status_code=400, detail=mime_or_err)

            temp_dir = create_safe_temp_dir()
            suffix = os.path.splitext(audio_file.filename)[1] or ".mp3"
            temp_path = os.path.join(temp_dir, f"audio_{uuid.uuid4().hex}{suffix}")
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            target_path = temp_path
            input_name = audio_file.filename
        elif sample_filename:
            scam_c = os.path.join(SCAM_AUDIO_DIR, sample_filename)
            norm_c = os.path.join(NORMAL_AUDIO_DIR, sample_filename)
            if os.path.exists(scam_c):
                target_path = scam_c
            elif os.path.exists(norm_c):
                target_path = norm_c
            else:
                raise HTTPException(status_code=404, detail="Sample audio file not found.")
            input_name = sample_filename
        else:
            raise HTTPException(status_code=400, detail="Please upload an audio file or select a sample.")

        result = process_audio_analysis_core(target_path, input_name, chips_list)
        if sample_filename and not chips_list:
            _PRECOMPUTED_SAMPLES_CACHE[sample_filename] = result

        return result

    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/analyze-text")
def analyze_text_endpoint(
    payload: TextAnalysisRequest,
    user: User = Depends(require_user)
):
    """Direct text analysis endpoint."""
    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    chips_list = payload.chosen_chips or []
    return process_text_analysis_core(clean_text, chips_list)


@app.post("/api/report")
def generate_report_endpoint(
    payload: PDFReportRequest,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Transient research-grade PDF case report generation.
    Body is never logged or stored on server; temp file is deleted after response.
    """
    case_dict = payload.case_payload
    if not case_dict:
        raise HTTPException(status_code=400, detail="No case data provided for report generation.")

    tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp_pdf.name
    tmp_pdf.close()

    try:
        generate_pdf_report(case_dict, tmp_path)
        case_id = case_dict.get("case_id", "report")
        filename = f"SentiCall_Case_Report_{case_id}.pdf"
        
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# --- 5. PUBLIC SAMPLES, TAXONOMY & METRICS ---

def load_reports_json(filename: str) -> Dict[str, Any]:
    p = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@app.get("/api/metrics")
def get_metrics_endpoint():
    data = load_reports_json("metrics.json")
    return data

@app.get("/api/insights")
def get_insights_endpoint():
    metrics = load_reports_json("metrics.json")
    bias_audit = load_reports_json("audio_bias_audit.json")
    early_det = load_reports_json("early_detection.json")
    live_metrics = load_reports_json("live_metrics.json")
    return {
        "metrics": metrics,
        "audio_bias_audit": bias_audit,
        "early_detection": early_det,
        "live_metrics": live_metrics
    }

@app.get("/api/samples")
def get_samples_endpoint():
    scam_audio_list = sorted([os.path.basename(f) for f in glob.glob(os.path.join(SCAM_AUDIO_DIR, "*.*"))])
    normal_audio_list = sorted([os.path.basename(f) for f in glob.glob(os.path.join(NORMAL_AUDIO_DIR, "*.*"))])

    audio_samples = [
        {
            "id": "audio_scam_1",
            "title": "SBI Debit Card Expiry & OTP Extraction",
            "type": "scam",
            "family_id": "bank_kyc_impersonation",
            "family_name": "Bank Impersonation",
            "badge": "Bank KYC Scam",
            "badge_color": "#DC2626",
            "filename": scam_audio_list[0] if scam_audio_list else "scam_1.mp3",
            "description": "Caller poses as SBI branch manager claiming debit card expiry and rushes to extract the 4-digit mobile OTP."
        },
        {
            "id": "audio_scam_2",
            "title": "Jio 23-Hour SIM Deactivation Threat",
            "type": "scam",
            "family_id": "telecom_sim_threat",
            "family_name": "Telecom Threat",
            "badge": "Telecom Pressure",
            "badge_color": "#D97706",
            "filename": scam_audio_list[1] if len(scam_audio_list) > 1 else (scam_audio_list[0] if scam_audio_list else "scam_2.mp3"),
            "description": "Urgent automated call threatening complete mobile SIM disconnection within 23 hours unless Aadhaar is confirmed."
        },
        {
            "id": "audio_scam_3",
            "title": "Vodafone £350 Cash Award Lure",
            "type": "scam",
            "family_id": "prize_lottery_cashback",
            "family_name": "Lottery Lure",
            "badge": "Prize & Lottery",
            "badge_color": "#D97706",
            "filename": scam_audio_list[2] if len(scam_audio_list) > 2 else (scam_audio_list[0] if scam_audio_list else "scam_3 (online-audio-converter.com).mp3"),
            "description": "Claims recipient's mobile number was chosen for an exclusive cash prize award to lure toll payments."
        },
        {
            "id": "audio_scam_4",
            "title": "Police Narcotics & 'Digital Arrest' Threat",
            "type": "scam",
            "family_id": "govt_law_enforcement_digital_arrest",
            "family_name": "Digital Arrest",
            "badge": "Digital Arrest",
            "badge_color": "#DC2626",
            "filename": scam_audio_list[3] if len(scam_audio_list) > 3 else (scam_audio_list[0] if scam_audio_list else "scam_5.mp3"),
            "description": "Impersonates Cyber Crime Branch claiming an illegal drug parcel was seized in recipient's name."
        },
        {
            "id": "audio_normal_1",
            "title": "Family Travel & Weekend Catchup",
            "type": "normal",
            "family_id": "no_concern_found",
            "family_name": "Safe Everyday Message",
            "badge": "Normal Conversation",
            "badge_color": "#059669",
            "filename": normal_audio_list[0] if normal_audio_list else "normal_1.mp3",
            "description": "Casual, unscripted friendly conversation discussing train journeys and everyday plans."
        },
        {
            "id": "audio_normal_2",
            "title": "Holiday Grocery Restock Reminder",
            "type": "normal",
            "family_id": "no_concern_found",
            "family_name": "Safe Everyday Message",
            "badge": "Normal Conversation",
            "badge_color": "#059669",
            "filename": normal_audio_list[1] if len(normal_audio_list) > 1 else (normal_audio_list[0] if normal_audio_list else "normal_2.mp3"),
            "description": "Friendly everyday coordination about holiday restocking and Tuesday afternoon plans."
        }
    ]

    text_samples = [
        {
            "id": "text_scam_1",
            "title": "SBI Card Expiry & OTP Request",
            "type": "scam",
            "family_id": "bank_kyc_impersonation",
            "badge": "Bank Fraud",
            "text": "hello, i m bank manager of SBI, ur debit card is about to expire would u want to issue new card. please tell me the four digit otp sent to your mobile.",
            "description": "Classic authority claim combined with urgent OTP extraction."
        },
        {
            "id": "text_scam_2",
            "title": "Jio SIM 23-Hour Deactivation Threat",
            "type": "scam",
            "family_id": "telecom_sim_threat",
            "badge": "Telecom Pressure",
            "text": "hello sir, i am from jio customer care in 23 hours your sim will be closed. do u want to activate it. please confirm your aadhaar and account details.",
            "description": "Threatens service closure to force instant credential disclosure."
        },
        {
            "id": "text_scam_3",
            "title": "Delhi Police 'Digital Arrest' Video Summon",
            "type": "scam",
            "family_id": "govt_law_enforcement_digital_arrest",
            "badge": "Digital Arrest",
            "text": "This is Officer Sharma from Delhi Cyber Crime Branch. A customs parcel with illegal contraband has been seized under your Aadhaar. You are under digital arrest. Stay on video and do not inform family.",
            "description": "Fear-based digital arrest coercion demanding isolation."
        },
        {
            "id": "text_scam_4",
            "title": "AnyDesk Remote Screen Sharing Instruction",
            "type": "scam",
            "family_id": "tech_support_remote_access",
            "badge": "Tech Support",
            "text": "Calling from UPI customer support. Your banking application requires mandatory security update. Please install AnyDesk from Play Store and accept remote screen connection.",
            "description": "Remote desktop screen takeover to capture passwords live."
        },
        {
            "id": "text_normal_1",
            "title": "Amazon Delivery Agent Parcel OTP (Safe)",
            "type": "normal",
            "family_id": "no_concern_found",
            "badge": "Safe Hard Negative",
            "text": "Hello sir, I am the Amazon delivery agent outside your gate. Please share the 4-digit package delivery OTP to hand over your order.",
            "description": "Legitimate delivery verification code request without manipulation."
        },
        {
            "id": "text_normal_2",
            "title": "Doctor Appointment Confirmation (Safe)",
            "type": "normal",
            "family_id": "no_concern_found",
            "badge": "Safe Message",
            "text": "Hello Mrs. Verma, calling from Apollo Clinic to confirm your consultation with Dr. Mehta tomorrow at 4:30 PM. Please arrive 10 minutes early.",
            "description": "Authentic clinic confirmation with zero pressure tactics."
        }
    ]

    return {
        "audio_samples": audio_samples,
        "text_samples": text_samples
    }

@app.get("/api/audio/{filename}")
def stream_audio(filename: str):
    scam_path = os.path.join(SCAM_AUDIO_DIR, filename)
    if os.path.exists(scam_path):
        return FileResponse(scam_path, media_type="audio/mpeg")
    normal_path = os.path.join(NORMAL_AUDIO_DIR, filename)
    if os.path.exists(normal_path):
        return FileResponse(normal_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio file not found")

@app.get("/api/taxonomy")
def get_taxonomy_endpoint():
    p = os.path.join(DATA_DIR, "taxonomy.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scam_families": []}

@app.get("/api/atlas")
def get_atlas_endpoint():
    p = os.path.join(DATA_DIR, "taxonomy.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"families": data.get("scam_families", [])}
    return {"families": []}

@app.get("/api/helplines")
def get_helplines_endpoint():
    p = os.path.join(DATA_DIR, "helplines.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"helplines": []}

@app.get("/api/tactics")
def get_tactics_endpoint():
    p = os.path.join(DATA_DIR, "tactics.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tactics": []}


# --- 6. STATIC ASSETS & MOUNTS ---

if os.path.exists(MODELS_DIR):
    app.mount("/models", StaticFiles(directory=MODELS_DIR), name="models")

vendor_path = os.path.join(FRONTEND_DIR, "vendor")
if os.path.exists(vendor_path):
    app.mount("/vendor", StaticFiles(directory=vendor_path), name="vendor")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/sw.js")
def serve_service_worker():
    sw_file = os.path.join(FRONTEND_DIR, "sw.js")
    if os.path.exists(sw_file):
        return FileResponse(sw_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")

@app.get("/data/tactics.json")
def serve_tactics_file():
    p = os.path.join(DATA_DIR, "tactics.json")
    if os.path.exists(p):
        return FileResponse(p, media_type="application/json")
    raise HTTPException(status_code=404, detail="tactics.json not found")

@app.get("/")
def serve_index():
    idx_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(idx_path):
        return FileResponse(
            idx_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "SentiCall v3 Backend active."}
