# SentiCall v3 — "The Third Voice"
> **Personal, Secure Voice Safety Suite Against Phone Scams & Vishing**  
> *Live Listen, Google Sign-In, and a Privacy-First Security Layer*

---

## 🌟 Overview & Product Mission

**SentiCall v3 ("The Third Voice")** is an empathetic, privacy-first web application designed to protect everyday people from phone scams, voice phishing (vishing), and social engineering fraud. 

Calls are private. Every architectural choice in SentiCall favors user privacy over server convenience. SentiCall acts as a vigilant protector ("the third voice in the room"):
1. **Live Listen (On-Device)**: Listens to calls playing on speakerphone (via microphone) or directly from a browser tab (WhatsApp Web, Google Meet, Zoom), transcribes speech live using self-hosted quantized Whisper in a Web Worker, scores psychological manipulation tactics as they occur, warns the user visually and by voice, and displays an end-of-call summary with computed warning lead time.
2. **Google Sign-In & Personalization**: Minimal-scope OpenID Connect (`openid email profile`) authentication with PKCE, server-side session management (`__Host-session`), role-based access (Guest, Verified User, Admin), emergency bank advice, and WhatsApp family alerts.
3. **Privacy & Security Layer**: Truthful privacy badging by operating mode, zero call content stored on the server database, client-side encryption (WebCrypto AES-GCM + PBKDF2 600,000 rounds) for saved cases, and self-service account and data deletion.

---

## 🔒 Truthful Privacy Guarantees by Mode

Every privacy badge and notice in SentiCall dynamically reflects the verified data path:

- **Live Listen (Microphone or Browser Tab):**
  > *"Audio is processed on this device and is never uploaded."*
  Microphone and tab audio streams are processed completely inside the browser using WebAssembly and WebGPU runtimes via Transformers.js. No audio or transcript ever leaves your device in this mode.

- **Upload Analysis (Hosted Mode):**
  > *"Your file is processed in memory on our secure server and deleted immediately. We never store it, share it or use it for training."*
  Audio files are written to a temporary memory-backed directory with owner-only (0700) permissions, processed transiently, and deleted immediately in a `finally` block. A background sweeper purges any temp files older than 10 minutes.

---

## 🚀 Key Capabilities

### Part A — Live Listen [On-Device]
- **Dual Audio Sources**: Speakerphone calls via microphone (`getUserMedia`) with noisy-room filtering, or web calls via browser tabs (`getDisplayMedia` with automatic video track teardown).
- **Pre-Flight System Check**: Verifies audio permissions, live input VU meter reactivity, on-device Whisper model readiness, and device speed test (Real-Time Factor).
- **Streaming Speech-to-Text**: Energy-based Voice Activity Detection (VAD) with hangover, 30s rolling context window, hallucination suppression, and a local-agreement confirmation policy (unconfirmed words shown in gray).
- **Synchronized Risk Engine**: 9 signature manipulation tactics (authority impersonation, urgency, secrecy, credential extraction, remote access, prize lures, threats) evaluated in JavaScript with exact Scikit-Learn mathematical parity.
- **Graduated Alerts**:
  - *Calm*: Standard active monitoring.
  - *Heads-Up*: Amber slide-in banner warning against pressure or secrecy demands.
  - *Danger*: Full-width red takeover overlay with large **"Hang up call now"** headline action, audible WebAudio alarm tone, spoken synthesized voice warning, mobile vibration, and background tab notification.
- **End-of-Call Summary**: Automatically transitions to the Case Report view showing computed lead time (*"SentiCall warned you 18 seconds before the caller asked for your OTP"*), actionable steps, and emergency helplines.

### Part B — Google Sign-In & Authorization
- **OAuth 2.0 / OpenID Connect with PKCE**: Scopes restricted strictly to `openid email profile`. Access and ID tokens are verified and discarded immediately; tokens are never stored.
- **Secure Server Sessions**: Cryptographically hashed 256-bit tokens, stored in `__Host-session` cookies with `HttpOnly`, `Secure`, `SameSite=Lax`, 24h idle timeout, and 7-day absolute lifetime.
- **CSRF & Origin Enforcement**: State-changing requests enforce `X-CSRF-Token` headers and same-origin validation.
- **Three Access Levels**:
  - *Guest*: Landing page, sample calls, Scam Atlas, Practice Mode, Model Insights, Privacy Center.
  - *Signed-in User*: Own audio/text analysis, Live Listen, My Cases, PDF export, personalization settings.
  - *Admin*: Minimal `/admin/health` dashboard showing system counts only (users, active sessions, events, uptime). Zero access to call contents.
- **Inverted Data Ownership (Anti-IDOR)**: Users can only access their own jobs and reports.

### Part C — Privacy & Security Layer
- **Client-Side Encrypted Cases (IndexedDB)**: Saved personal cases are stored locally on the user's device and encrypted with WebCrypto AES-GCM (256-bit).
- **App Lock**: Optional passphrase deriving an AES-GCM key with PBKDF2 (600,000 rounds). Auto-locks after 5 idle minutes.
- **Privacy Center**: One-click data export (`/me/export`), local device wipe, security audit log, and permanent account deletion (`DELETE /me`).
- **Fail-Closed Architecture**: Missing secrets or dev bypass enabled in production causes the server to refuse startup immediately.
- **Upload Hardening**: Magic-byte signature verification, 25 MB size cap, 0700 temp directories, 10-minute temp sweeper, and argument-list FFmpeg.

---

## 📊 Transparent Machine Learning Evaluation & Live Benchmarks

All numbers originate from verified evaluation reports ([`reports/metrics.json`](reports/metrics.json) and [`reports/live_metrics.json`](reports/live_metrics.json)):

| Pipeline / Channel | Metric | Measured Value | Sample Size ($n$) & 95% Wilson CI | Validation Method |
| :--- | :--- | :--- | :--- | :--- |
| **Text Linguistic Model** | **F1-Score** | **93.0%** | $n=120$, 95% CI [86.8%, 96.7%] | 5-Fold Leakage-Controlled `GroupKFold` |
| | **ROC-AUC** | **0.9902** | $n=120$, 95% CI [0.971, 0.999] | Platt-calibrated logistic regression |
| | **Python vs JS Parity** | **0.0000 max diff** | $n=200$ golden samples | Exact TF-IDF + Logistic Sigmoid parity (100% matched) |
| **Live Listen Engine** | **Hard Negative Specificity** | **86.7%** | $n=30$, 95% CI [70.3%, 94.7%] | Genuine bank warnings with contextual negation matching |
| | **Normal Everyday Calls** | **100.0% Specificity** | $n=10$, 95% CI [72.2%, 100.0%] | Zero false alarms on friendly conversational speech |
| | **Early Detection Buffer** | **26.6s Median Lead Time** | $n=8$ real scam calls | SentiCall alert fires 26.6s before secret credential ask |
| | **Median First Alert Time** | **16.9s from call start** | $n=8$ real scam calls | Authority + urgency prompt detection |
| | **Real-Time Factor (RTF)** | **0.055x** | Machine benchmark | 18x faster than real-time speech |
| | **Model Cold-Start Load** | **2567.1 ms** | Local benchmark | Quantized ONNX multilingual Whisper Tiny |
| **Audio Acoustic Model** | **Accuracy** | **89.9%** | $n=96$, 95% CI [82.3%, 94.4%] | Telephony-Normalized XGBoost (Upload mode only) |
| | **ROC-AUC** | **0.9670** | $n=96$, 95% CI [0.932, 0.988] | Windowed acoustic features (10s window) |

*Note: SentiCall does not claim 100% accuracy or zero risk. It provides an early-warning defense buffer to help users pause and verify.*

---

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python 3.12 / 3.13), SQLAlchemy 2.0 (SQLite for local dev, PostgreSQL for production), Authlib, Cryptography, ReportLab.
- **Frontend**: Vanilla ES6+ JavaScript, Web Audio API, Web Workers, Transformers.js (v2.17+ quantized ONNX), IndexedDB, WebCrypto API.
- **Styling**: Curated Vanilla CSS tokens (Bright/Light theme, WCAG AA contrast, responsive at 360px, 768px, and 1366px).
- **Deployment**: Docker container on Render (`render.yaml`), Uvicorn with `--proxy-headers`.

---

## 🚀 Local Development Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (for asset vendoring and tests)
- FFmpeg installed and available on PATH

### 2. Installation
```bash
# Clone repository
git clone https://github.com/Saicharan-Banothu/DT-Project.git
cd DT-Project

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies and vendor Transformers.js assets
npm install
node scripts/vendor_assets.js

# Download quantized Whisper ONNX models (one-time build step)
python scripts/download_whisper_models.py
```

### 3. Environment Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` for local development:
```ini
ENV=development
PUBLIC_BASE_URL=http://localhost:8000
DEV_LOGIN_BYPASS=true
DATABASE_URL=sqlite:///./data/senticall.db
SESSION_SECRET=local-development-secret-key-32-chars-min
```

### 4. Run Development Server
```bash
python run_server.py
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🧪 Testing & Verification

```bash
# 1. Run Python unit & integration tests
pytest tests/test_backend.py -v

# 2. Run Python vs. JavaScript 200-sample scoring parity test
node tests/test_parity_golden_200.js

# 3. Run security audit
bandit -r backend/ -ll
```

---

## 🌐 Production Deployment (Render)

SentiCall is configured for automated deployment on Render using Docker:
1. Review [`docs/SETUP_GOOGLE_AUTH.md`](docs/SETUP_GOOGLE_AUTH.md) for step-by-step instructions on creating Google Cloud OAuth credentials and setting up a free external PostgreSQL database (Neon / Supabase).
2. Connect your repository to Render using `render.yaml`.
3. Set the required production environment variables in the Render dashboard.

### Render Free Tier Cold Starts
On Render's free tier, the web service spins down after 15 minutes of inactivity. When waking up, the service may take 30–50 seconds to initialize. **For live demonstrations, send an HTTP GET request to `/healthz` 1–2 minutes beforehand to ensure an instant response.**

---

## 📚 Documentation Directory

- [`docs/PRIVACY.md`](docs/PRIVACY.md) — Truthful privacy guarantees, data inventory, and data sovereignty rights.
- [`docs/SECURITY.md`](docs/SECURITY.md) — Hardening guide, fail-closed architecture, CSP, and session management.
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — STRIDE threat modeling, abuse cases, and mitigations.
- [`docs/SETUP_GOOGLE_AUTH.md`](docs/SETUP_GOOGLE_AUTH.md) — Step-by-step Google OAuth and external PostgreSQL setup.
- [`docs/MANUAL_TEST.md`](docs/MANUAL_TEST.md) — Manual QA checklist for browser tab audio capture and hardware features.

---

## ⚖️ License & Ethical Use
SentiCall is developed for educational, defensive, and personal safety research. Always adhere to local consent rules when recording or listening to telephone calls.
