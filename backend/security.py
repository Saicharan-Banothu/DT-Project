"""
SentiCall v3 — Privacy & Security Layer
Implements strict security headers, upload hardening (magic bytes, size limits, safe temp dirs),
rate limiting, ASR concurrency capping, and privacy-preserving structured logging.
"""

import os
import time
import glob
import asyncio
import tempfile
from typing import Dict, Tuple, Optional
from collections import defaultdict

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import IS_PROD, PUBLIC_BASE_URL

# Audio Magic Byte Signatures
AUDIO_SIGNATURES = [
    (b"ID3", "audio/mpeg"),          # MP3 with ID3 header
    (b"\xff\xfb", "audio/mpeg"),      # MP3 frame sync
    (b"\xff\xf3", "audio/mpeg"),      # MP3 frame sync
    (b"\xff\xf2", "audio/mpeg"),      # MP3 frame sync
    (b"RIFF", "audio/wav"),           # WAV / RIFF container
    (b"OggS", "audio/ogg"),           # Ogg container
    (b"fLaC", "audio/flac"),          # FLAC
    (b"\x00\x00\x00", "audio/mp4"),   # MP4 / M4A / AAC container
]

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

# Concurrency Semaphore for CPU/GPU heavy ASR jobs
ASR_SEMAPHORE = asyncio.Semaphore(2)

# Rate Limiter State: IP/Key -> list of timestamps
_RATE_LIMIT_STORE: Dict[str, list] = defaultdict(list)

def check_rate_limit(key: str, max_requests: int, window_seconds: int = 60) -> bool:
    """Sliding-window rate limiter."""
    now = time.time()
    timestamps = _RATE_LIMIT_STORE[key]
    # Prune old timestamps
    _RATE_LIMIT_STORE[key] = [t for t in timestamps if now - t < window_seconds]
    if len(_RATE_LIMIT_STORE[key]) >= max_requests:
        return False
    _RATE_LIMIT_STORE[key].append(now)
    return True

def verify_audio_file_signature(file_bytes: bytes) -> Tuple[bool, str]:
    """Verify that file starts with valid audio magic bytes, not just file extension."""
    if len(file_bytes) < 4:
        return False, "File too small"
    header = file_bytes[:16]
    for sig, mime in AUDIO_SIGNATURES:
        if header.startswith(sig):
            return True, mime
        # Handle WAV RIFF header where format is at offset 8
        if sig == b"RIFF" and header[:4] == b"RIFF" and b"WAVE" in header[:12]:
            return True, "audio/wav"
    return False, "Unsupported file format. Please upload a standard MP3, WAV, OGG, or M4A file."

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies strict CSP, HSTS, X-Content-Type-Options, Referrer-Policy,
    Permissions-Policy, COOP, and Cache-Control headers.
    """
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 1. Content Security Policy
        # Self-hosted models, fonts, scripts. accounts.google.com permitted for Google Sign-In redirect.
        # lh3.googleusercontent.com permitted for Google avatar thumbnails.
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'wasm-unsafe-eval'; "
            "worker-src 'self' blob:; "
            "connect-src 'self'; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "frame-ancestors 'none'; "
            "form-action 'self' https://accounts.google.com; "
            "base-uri 'self';"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        # 2. Hardening Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=(), payment=(), usb=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # 3. HSTS in production or HTTPS
        if request.url.scheme == "https" or IS_PROD or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # 4. Cache-Control: no-store on authenticated endpoints and API calls
        if request.url.path.startswith("/api/") or request.url.path.startswith("/me") or request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


def create_safe_temp_dir() -> str:
    """Create a private temporary directory with owner-only (0700) permissions."""
    tmp_dir = tempfile.mkdtemp(prefix="senticall_job_")
    try:
        os.chmod(tmp_dir, 0o700)
    except Exception:
        pass
    return tmp_dir

def sweep_old_temp_files():
    """Remove any temporary files older than 10 minutes."""
    try:
        pattern = os.path.join(tempfile.gettempdir(), "senticall_job_*")
        now = time.time()
        for p in glob.glob(pattern):
            try:
                if os.path.isdir(p) and (now - os.path.getmtime(p) > 600):
                    import shutil
                    shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass
    except Exception:
        pass
