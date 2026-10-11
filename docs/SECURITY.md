# SentiCall v3 — Security Architecture & Hardening Guide

*Fail-Closed Architecture: If a required security setting or secret is missing in production, the server terminates startup immediately with an actionable error.*

---

## 1. Authentication & Session Management

### Google OpenID Connect / OAuth 2.0 with PKCE
- **Flow:** Authorization Code Flow with PKCE (`code_challenge` / `code_verifier` with `S256`), random state, and nonce.
- **Minimal Scopes:** `openid email profile`. Never requests offline access, Gmail, Contacts, or Drive.
- **Cryptographic Verification:** Every ID token is cryptographically validated using Google's public keys via `google.oauth2.id_token.verify_oauth2_token`.
- **Token Discard:** Access tokens and ID tokens are discarded immediately after extracting the user profile; they are never stored in the database.
- **User Identifier:** Users are identified by Google's permanent `sub` string, not mutable email addresses.

### Server-Side Sessions
- **Session Tokens:** 256-bit cryptographically secure random tokens generated via `secrets.token_urlsafe(32)`.
- **Hashed Storage:** Tokens are stored in the database as SHA-256 hashes (`hash_token(raw_token)`). A database leak does not expose valid session credentials.
- **Cookie Flags:** Stored in cookie `__Host-session` (or fallback `session_token` for plain HTTP localhost testing):
  - `HttpOnly`: Inaccessible to JavaScript (mitigates XSS token theft).
  - `Secure`: Transmitted only over HTTPS.
  - `SameSite=Lax`: Prevents cross-site request forgery via top-level navigations.
  - `Path=/`: Root path scope.
  - No `Domain` attribute: Restricts cookie strictly to the host.
- **Timeouts:**
  - Idle timeout: 24 hours of inactivity invalidates the session.
  - Absolute lifetime: 7 days maximum session lifetime regardless of activity.
- **Revocation:** Explicit single-session logout or "Sign out of all devices" instantly removes session rows from the database.

---

## 2. Cross-Site Request Forgery (CSRF) & Origin Defense

- **CSRF Token Header:** All state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) require an `X-CSRF-Token` header matching the active session's random CSRF token.
- **Origin & Host Verification:** The backend strictly checks `Origin` and `Host` headers on incoming requests against `PUBLIC_BASE_URL`. Cross-origin state modifications are rejected with HTTP 403.
- **Same-Origin Policy:** CORS middleware restricts requests strictly to the same origin (`PUBLIC_BASE_URL` or localhost in development).

---

## 3. Authorization & IDOR Prevention

- **Deny-by-Default:** Every route declares an explicit access level:
  - `Public`: Landing page, sample calls, Scam Atlas, Practice Mode, Model Insights, `/healthz`.
  - `require_user`: Own audio/text analysis, Live Listen, My Cases, user settings, PDF export, consent updates.
  - `require_admin`: Admin Health dashboard (`/admin/health`).
- **Inverted Data Ownership (Anti-IDOR):**
  - All background analysis jobs (`/api/jobs/{id}/stream`) strictly verify `job.user_id == user.id`. Users cannot inspect or cancel other users' jobs.
  - Call records and transcripts are not stored on the server database, fundamentally eliminating server-side call IDOR vulnerabilities.
- **Development Bypass Safety:**
  - `DEV_LOGIN_BYPASS` is permitted **only** when `ENV=development` AND the request origin is `localhost` / `127.0.0.1`.
  - In production (`ENV=production`), the application refuses to start if `DEV_LOGIN_BYPASS=true`.

---

## 4. Security Headers & Content Security Policy (CSP)

SentiCall enforces strict HTTP response headers via custom FastAPI middleware:

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; form-action 'self' https://accounts.google.com;
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Permissions-Policy: microphone=(self), camera=(), geolocation=(), payment=()
Cross-Origin-Opener-Policy: same-origin
Cache-Control: no-store, no-cache, must-revalidate (for authenticated responses)
```

- Zero third-party scripts, CDNs, or trackers.
- Microphone permission is explicitly restricted to `(self)`.

---

## 5. Audio Upload Hardening & Input Sanitization

1. **Magic Bytes Validation:** File type is validated by inspecting raw header bytes (e.g. `ID3`/`\xff\xfb` for MP3, `RIFF...WAVE` for WAV, `OggS` for OGG), not trusting client-provided file extensions.
2. **File Size Limit:** Maximum upload cap enforced at 25 MB (`MAX_UPLOAD_BYTES = 25 * 1024 * 1024`).
3. **Owner-Only Temp Directories:** Uploads are written to dedicated temp directories created with `0700` permissions (`os.mkdir(path, mode=0o700)`).
4. **Immediate Deletion:** Temp files are deleted in a `finally` block immediately after in-memory processing.
5. **Background Sweeper:** A periodic sweeper thread runs every 60 seconds and permanently unlinks any orphaned temp file older than 10 minutes.
6. **Command Hardening:** FFmpeg is invoked exclusively via argument lists (`subprocess.run(["ffmpeg", "-i", ...])`), never through a shell (`shell=False`), preventing command injection.
7. **Concurrency Cap:** In-memory transcription jobs are capped at 2 concurrent processes via an `asyncio.Semaphore(2)` to protect against resource exhaustion.

---

## 6. Rate Limiting & Quotas

- In-memory sliding-window rate limiter per client IP and per authenticated user:
  - Analysis jobs: 30 requests per minute.
  - Sign-in attempts: 10 requests per minute.
  - General API: 60 requests per minute.
- Rate limit violations return `HTTP 429 Too Many Requests`.

---

## 7. Container & Infrastructure Security

- Non-root user (`appuser`, UID 10001) in Dockerfile.
- Read-only container root with minimal dependencies based on `python:3.12-slim`.
- Health check configured at `/healthz` returning HTTP 200 without exposing sensitive telemetry.
- No hardcoded secrets. All sensitive keys are provided via environment variables.

---

## 8. Dependency Hygiene & Audit Findings

- **Python Dependencies (`bandit` & `pip-audit`):**
  - Bandit security scan across all backend code runs clean: `0 issues identified` across 4,094 lines of code.
  - Python dependencies are audited against PyPI and OSV databases; core dependencies (`fastapi`, `sqlalchemy`, `authlib`, `cryptography`, `httpx`, `reportlab`) use hardened, modern releases.
- **Node.js Dependencies (`npm audit`):**
  - Transitive advisory findings on `sharp` and `protobufjs` exist inside `@xenova/transformers` development dependencies if installed via npm.
  - **Runtime Boundary:** Node.js is **never** executed in production on Render. The server is a Python container running FastAPI and Uvicorn. `@xenova/transformers` was utilized strictly at build time to copy the compiled client-side script (`transformers.min.js`) into `frontend/vendor/`.
  - In the browser, `transformers.min.js` runs within an isolated Web Worker with remote network requests disabled (`env.allowRemoteModels = false`) and strict CSP preventing exfiltration.

