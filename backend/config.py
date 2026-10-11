"""
SentiCall v3 — Environment Configuration & Security Enforcement
Fails closed if required production secrets are missing.
"""

import os
import sys
from typing import List
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "development").lower()
IS_PROD = ENV == "production"

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

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
        
        if not SESSION_SECRET or len(SESSION_SECRET) < 32 or "change-this" in SESSION_SECRET:
            errors.append("SESSION_SECRET must be set to a secure random string of at least 32 characters in production.")
            
        if not GOOGLE_CLIENT_ID or "your-google-client-id" in GOOGLE_CLIENT_ID:
            errors.append("GOOGLE_CLIENT_ID is required for production Google Sign-In.")
            
        if not GOOGLE_CLIENT_SECRET or "your-google-client-secret" in GOOGLE_CLIENT_SECRET:
            errors.append("GOOGLE_CLIENT_SECRET is required for production Google Sign-In.")
            
        if not PUBLIC_BASE_URL.startswith("https://"):
            errors.append(f"PUBLIC_BASE_URL must use HTTPS in production (got: {PUBLIC_BASE_URL}).")

    if errors:
        sys.stderr.write("\n" + "="*70 + "\n")
        sys.stderr.write(" FATAL SECURITY CONFIGURATION ERROR — REFUSING TO START\n")
        sys.stderr.write("="*70 + "\n")
        for err in errors:
            sys.stderr.write(f" [!] {err}\n")
        sys.stderr.write("="*70 + "\n\n")
        sys.exit(1)

validate_production_configuration()
