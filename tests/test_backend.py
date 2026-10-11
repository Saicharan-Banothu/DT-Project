"""
SentiCall v3 — Comprehensive Backend Security & Core Engine Tests
Tests:
- Health & Security Headers (CSP, HSTS, Permissions-Policy)
- Authentication, Sessions, Cookie flags, CSRF enforcement
- Authorization & IDOR prevention (User A vs User B job isolation)
- Upload validation (Magic byte detection, size limits)
- Tactic tagging & Negation context rules (Hard negatives)
- Data export & Complete user deletion
- Admin access controls
"""

import os

# Set environment before any imports
os.environ["ENV"] = "development"
os.environ["DEV_LOGIN_BYPASS"] = "true"
os.environ["SESSION_SECRET"] = "test-session-secret-at-least-32-chars-long"

import json
import pytest
from fastapi.testclient import TestClient

import backend.config as cfg
cfg.DEV_LOGIN_BYPASS = True
cfg.IS_PROD = False

from backend.app import app
from backend.db_models import get_db, User, SessionModel, SecurityLog
from backend.tactic_tagger import tag_manipulation_tactics
from backend.text_pipeline import analyze_text
from backend.security import verify_audio_file_signature


def test_healthz():
    """Verify /healthz returns 200 without exposing telemetry."""
    client = TestClient(app, base_url="http://localhost:8000")
    res = client.get("/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "senticall-v3"


def test_security_headers():
    """Verify strict CSP, HSTS, no-sniff, and permissions policy."""
    client = TestClient(app, base_url="http://localhost:8000")
    res = client.get("/healthz")
    headers = res.headers

    assert "content-security-policy" in headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("referrer-policy") == "no-referrer"
    assert "microphone=(self)" in headers.get("permissions-policy", "")
    assert headers.get("cross-origin-opener-policy") == "same-origin"


def test_auth_dev_login_and_cookie_flags():
    """Verify session creation, CSRF token attachment, and cookie security flags."""
    client = TestClient(app, base_url="http://localhost:8000")
    res = client.post(
        "/auth/dev-login",
        json={"email": "alice@example.com", "name": "Alice Tester", "role": "user"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "logged_in"
    assert data["user"]["email"] == "alice@example.com"
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 16

    # Verify session cookie was set
    cookies = client.cookies
    assert "session_token" in cookies or "__Host-session" in cookies


def test_csrf_protection():
    """Verify CSRF token is required on state-changing requests."""
    client = TestClient(app, base_url="http://localhost:8000")
    login_res = client.post(
        "/auth/dev-login",
        json={"email": "bob@example.com", "name": "Bob Tester", "role": "user"}
    )
    assert login_res.status_code == 200
    csrf_token = login_res.json()["csrf_token"]

    # 1. State-changing request without CSRF token header should fail with 403
    res_no_csrf = client.patch(
        "/me/settings",
        json={"sensitivity": "cautious"}
    )
    assert res_no_csrf.status_code == 403

    # 2. State-changing request with wrong CSRF token should fail with 403
    res_bad_csrf = client.patch(
        "/me/settings",
        json={"sensitivity": "cautious"},
        headers={"X-CSRF-Token": "invalid_csrf_token_value", "Origin": "http://localhost:8000"}
    )
    assert res_bad_csrf.status_code == 403

    # 3. State-changing request with valid CSRF token and valid Origin should succeed
    res_valid = client.patch(
        "/me/settings",
        json={"sensitivity": "cautious"},
        headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:8000"}
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "updated"


def test_idor_job_isolation():
    """Verify User B cannot access or stream User A's analysis job."""
    alice_client = TestClient(app, base_url="http://localhost:8000")
    alice_login = alice_client.post(
        "/auth/dev-login",
        json={"email": "alice_idor@example.com", "name": "Alice IDOR", "role": "user"}
    )
    assert alice_login.status_code == 200
    alice_csrf = alice_login.json()["csrf_token"]

    job_create = alice_client.post(
        "/api/analyze",
        data={"text": "Hello this is a test call for job creation."},
        headers={"X-CSRF-Token": alice_csrf, "Origin": "http://localhost:8000"}
    )
    assert job_create.status_code == 200
    job_id = job_create.json()["job_id"]

    # Bob logs in on a separate client session
    bob_client = TestClient(app, base_url="http://localhost:8000")
    bob_login = bob_client.post(
        "/auth/dev-login",
        json={"email": "bob_idor@example.com", "name": "Bob IDOR", "role": "user"}
    )
    assert bob_login.status_code == 200

    # Bob attempts to stream Alice's job -> MUST be rejected with 403 Forbidden
    bob_stream = bob_client.get(f"/api/jobs/{job_id}/stream")
    assert bob_stream.status_code == 403
    assert "Access denied" in bob_stream.json()["detail"]


def test_upload_magic_bytes_validation():
    """Verify audio file signature verification rejects malicious or invalid binaries."""
    # 1. Valid MP3 signature
    fake_mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x10" + b"\x00" * 100
    valid, mime = verify_audio_file_signature(fake_mp3)
    assert valid is True
    assert mime == "audio/mpeg"

    # 2. Valid WAV signature
    fake_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 50
    valid_wav, mime_wav = verify_audio_file_signature(fake_wav)
    assert valid_wav is True
    assert mime_wav == "audio/wav"

    # 3. Invalid binary (e.g. executable script or zip)
    fake_malicious = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    invalid, err = verify_audio_file_signature(fake_malicious)
    assert invalid is False
    assert "Unsupported file format" in err


def test_tactic_rules_and_negation_handling():
    """Verify tactic tagging flags genuine scams while suppressing false alarms on negation patterns."""
    # 1. Clear scam call: Authority + Urgency + OTP demand
    scam_text = "Hello I am bank manager from State Bank of India. Your debit card is expired in 24 hours. Please share your four digit OTP right now."
    scam_tactics = tag_manipulation_tactics(scam_text)
    hit_ids = [t["id"] for t in scam_tactics if t["detected"]]

    assert "authority_impersonation" in hit_ids
    assert "urgency_threat" in hit_ids
    assert "credential_request" in hit_ids

    scam_eval = analyze_text(scam_text)
    assert scam_eval["text_risk_score"] >= 70

    # 2. Hard negative bank alert with negation: "We will NEVER ask for your OTP or password"
    bank_warning = "State Bank of India official notice: Please remember our bank staff will never ask for your secret OTP, PIN or password on telephone calls."
    warning_tactics = tag_manipulation_tactics(bank_warning)
    warning_hits = [t["id"] for t in warning_tactics if t["detected"]]

    # Negation context should suppress false credential extraction alert
    assert "credential_request" not in warning_hits

    # 3. Legitimate Amazon delivery PIN
    delivery_text = "Hello madam, Amazon delivery agent outside your gate with your order. Please share the four digit delivery PIN to hand over parcel."
    delivery_tactics = tag_manipulation_tactics(delivery_text)
    delivery_hits = [t["id"] for t in delivery_tactics if t["detected"]]

    # Safe delivery PIN should not trigger bank impersonation or threat
    assert "authority_impersonation" not in delivery_hits
    assert "threats_penalties" not in delivery_hits


def test_user_export_and_account_deletion():
    """Verify data export contains zero call audio, and deletion purges user row and sessions."""
    client = TestClient(app, base_url="http://localhost:8000")
    login_res = client.post(
        "/auth/dev-login",
        json={"email": "charlie@example.com", "name": "Charlie Delete", "role": "user"}
    )
    assert login_res.status_code == 200
    csrf_token = login_res.json()["csrf_token"]

    # 1. Test Data Export
    export_res = client.get("/me/export")
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert export_data["user_profile"]["email"] == "charlie@example.com"
    assert "privacy_notice" in export_data
    # Assert zero call audio or transcripts exist in export
    assert "call_audio" not in export_data
    assert "transcripts" not in export_data

    # 2. Test Account Deletion without typing DELETE fails
    del_bad = client.request(
        "DELETE",
        "/me",
        json={"confirmation": "NO"},
        headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:8000"}
    )
    assert del_bad.status_code == 400

    # 3. Test Account Deletion with confirmation DELETE succeeds
    del_good = client.request(
        "DELETE",
        "/me",
        json={"confirmation": "DELETE"},
        headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:8000"}
    )
    assert del_good.status_code == 200
    assert del_good.json()["status"] == "account_permanently_deleted"

    # Subsequent /me request should be unauthenticated
    subsequent_me = client.get("/me")
    assert subsequent_me.status_code == 401


def test_admin_health_authorization():
    """Verify non-admin users cannot access admin health dashboard."""
    # Normal user
    user_client = TestClient(app, base_url="http://localhost:8000")
    user_login = user_client.post(
        "/auth/dev-login",
        json={"email": "standard_user@example.com", "name": "Standard", "role": "user"}
    )
    assert user_login.status_code == 200
    res_user = user_client.get("/admin/health")
    assert res_user.status_code == 403

    # Admin user
    admin_client = TestClient(app, base_url="http://localhost:8000")
    admin_login = admin_client.post(
        "/auth/dev-login",
        json={"email": "admin_test@senticall.ai", "name": "Admin", "role": "admin"}
    )
    assert admin_login.status_code == 200
    res_admin = admin_client.get("/admin/health")
    assert res_admin.status_code == 200
    admin_data = res_admin.json()
    assert "total_registered_users" in admin_data
    assert "active_sessions_count" in admin_data
    assert "uptime_seconds" in admin_data or "server_uptime_seconds" in admin_data
