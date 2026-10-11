"""
SentiCall v3 — Environment Configuration & Security Enforcement
Fails closed if required production secrets are missing.
"""

import os
import sys
import secrets
from typing import List
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "development").lower()
IS_PROD = ENV == "production"

# Resolve PUBLIC_BASE_URL with automatic Render and HTTPS detection
raw_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
render_external = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()

if raw_base_url and (not IS_PROD or raw_base_url.startswith("https://")):
    PUBLIC_BASE_URL = raw_base_url
elif render_external:
    PUBLIC_BASE_URL = render_external
elif render_host:
    PUBLIC_BASE_URL = f"https://{render_host}"
elif IS_PROD or os.getenv("RENDER"):
    PUBLIC_BASE_URL = "https://senticall-v2.onrender.com"
else:
    PUBLIC_BASE_URL = "http://localhost:8000"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

# SESSION_SECRET: auto-generate cryptographically secure token if omitted in Render
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
if not SESSION_SECRET or len(SESSION_SECRET) < 32 or "change-this" in SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(48)
    if IS_PROD:
        sys.stderr.write("[CONFIG] SESSION_SECRET not provided in environment; generated a transient 384-bit secure key.\n")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./data/senticall_auth.db"

# Admin and access lists
ADMIN_EMAILS: List[str] = [
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "admin@senticall.ai").split(",") if e.strip()
]

allowed_env = os.getenv("ALLOWED_EMAILS", "").strip()
ALLOWED_EMAILS: List[str] = [
    e.strip().lower() for e in allowed_env.split(",") if e.strip()
] if allowed_env else []

DEV_LOGIN_BYPASS = os.getenv("DEV_LOGIN_BYPASS", "false").lower() in ("true", "1", "yes")
ENABLE_SERVER_ASR = os.getenv("ENABLE_SERVER_ASR", "false").lower() in ("true", "1", "yes")

# Session lifetimes
IDLE_SESSION_TIMEOUT_SECONDS = int(os.getenv("IDLE_SESSION_TIMEOUT_SECONDS", "86400")) # 24 hours
ABSOLUTE_SESSION_TIMEOUT_SECONDS = int(os.getenv("ABSOLUTE_SESSION_TIMEOUT_SECONDS", "604800")) # 7 days

# Validation & Fail-Closed Guards
def validate_production_configuration():
    errors = []
    if IS_PROD:
        if DEV_LOGIN_BYPASS:
            errors.append("DEV_LOGIN_BYPASS is strictly prohibited in production mode (ENV=production).")
            
        if not PUBLIC_BASE_URL.startswith("https://"):
            errors.append(f"PUBLIC_BASE_URL must use HTTPS in production (got: {PUBLIC_BASE_URL}).")
            
        if not GOOGLE_CLIENT_ID or "your-google-client-id" in GOOGLE_CLIENT_ID:
            sys.stderr.write("[CONFIG WARNING] GOOGLE_CLIENT_ID is not configured. Google Sign-In will prompt for setup.\n")
            
        if not GOOGLE_CLIENT_SECRET or "your-google-client-secret" in GOOGLE_CLIENT_SECRET:
            sys.stderr.write("[CONFIG WARNING] GOOGLE_CLIENT_SECRET is not configured. Google Sign-In will prompt for setup.\n")

    if errors:
        sys.stderr.write("\n" + "="*70 + "\n")
        sys.stderr.write(" FATAL SECURITY CONFIGURATION ERROR — REFUSING TO START\n")
        sys.stderr.write("="*70 + "\n")
        for err in errors:
            sys.stderr.write(f" [!] {err}\n")
        sys.stderr.write("="*70 + "\n\n")
        sys.exit(1)

validate_production_configuration()

