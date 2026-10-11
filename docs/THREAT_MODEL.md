# SentiCall v3 — Comprehensive Threat Model

*Framework: STRIDE & Defense-in-Depth*  
*Last Reviewed: October 2026*

---

## 1. Assets to Protect

1. **User Voice Audio & Call Contents:** Extremely sensitive personal audio that may contain financial details, personal names, account numbers, or intimate family discussions.
2. **Conversation Transcripts:** Text representation of private speech.
3. **User Identity & Account Credentials:** Google OAuth identity, email, session tokens.
4. **Local Case Archives:** User's history of detected fraud attempts, timestamps, and notes.
5. **System Availability & Model Integrity:** Server compute resources, preventing denial-of-service or model poisoning.

---

## 2. Threat Actors & Capabilities

| Threat Actor | Capabilities | Motivation |
|---|---|---|
| **Eavesdropper / Network Attacker** | Can inspect, intercept, or modify unencrypted network traffic (e.g. on public Wi-Fi). | Steal session tokens or eavesdrop on call transcripts. |
| **Malicious Web Application (Cross-Site)** | Runs malicious JavaScript on third-party origins visited by the victim. | Execute CSRF attacks, read sensitive case reports, access microphone stream. |
| **Malicious Call Participant (Scammer)** | Speaks coercive scam scripts to manipulate victim and extract OTPs/PINs. | Financial fraud, intimidation, credential extortion. |
| **Physical Shoulder Surfer / Device Thief** | Observes user's screen in public places or gains temporary physical access to an unlocked laptop/phone. | Read private transcripts or inspect past fraud reports. |
| **Rogue / Compromised Cloud Infrastructure** | Has access to server disk snapshots or database backups on cloud provider. | Harvest user records or exfiltrate databases. |

---

## 3. Abuse Cases & Detailed Mitigations

### 3.1 Abuse Case: Stolen Session Cookie via XSS or Packet Sniffing
- **Threat:** Attacker obtains session cookie and impersonates the victim.
- **Mitigation:**
  - `__Host-session` cookie configured with `HttpOnly`, `Secure`, `SameSite=Lax`, and `Path=/`.
  - Stored in database as SHA-256 hash. Even if database is leaked, raw session token cannot be recovered.
  - Idle timeout after 24 hours; absolute expiry after 7 days.
  - User can immediately click "Sign out of all devices" to revoke all sessions.

### 3.2 Abuse Case: Cross-Site Request Forgery (CSRF)
- **Threat:** Malicious website submits state-changing requests (e.g. account deletion, profile modification) on behalf of logged-in user.
- **Mitigation:**
  - Random `csrf_token` tied to each session.
  - Backend enforces `X-CSRF-Token` header check on all `POST`, `PUT`, `PATCH`, `DELETE` requests.
  - Origin header validation rejecting cross-origin requests.

### 3.3 Abuse Case: Cross-Site WebSocket or Worker Eavesdropping
- **Threat:** Malicious tab attempts to connect to local Web Worker or stream audio.
- **Mitigation:**
  - Web Workers operate within a dedicated execution context scoped strictly to the same origin.
  - Strict Content-Security-Policy: `connect-src 'self'`, `worker-src 'self' blob:`, `frame-ancestors 'none'`.

### 3.4 Abuse Case: Malicious Audio File Upload (Polyglot / Zip Bomb / Buffer Overflow)
- **Threat:** Attacker uploads crafted media file containing shell exploits, decompression bombs, or script polyglots.
- **Mitigation:**
  - Magic byte verification checking audio file signature, rejecting executables and archives.
  - File size strictly capped at 25 MB before reading into disk.
  - Argument-list FFmpeg invocation (`shell=False`) with strict timeouts.
  - Processed in temporary directory with owner-only (`0700`) permissions, destroyed in `finally` block.
  - ASR concurrency semaphore cap (`asyncio.Semaphore(2)`) preventing memory exhaustion DoS.

### 3.5 Abuse Case: Insecure Direct Object Reference (IDOR)
- **Threat:** User A guesses Job ID of User B to access their transcription or analysis.
- **Mitigation:**
  - All job streams (`/api/jobs/{id}/stream`) verify `job["user_id"] == user.id`. Cross-user access returns HTTP 403 Forbidden.
  - Call records and transcripts are never stored in the server database; each case is held exclusively in the user's browser IndexedDB.

### 3.6 Abuse Case: Shoulder Surfing in Public Places
- **Threat:** Onlooker reads live transcript on the user's laptop screen while user is on a speakerphone call.
- **Mitigation:**
  - Live Listen includes a one-tap **"Hide transcript in public"** toggle that blurs all transcribed words until explicitly tapped or hovered.

### 3.7 Abuse Case: Lost or Stolen Unlocked Device
- **Threat:** Thief opens the laptop browser and inspects historical fraud cases in IndexedDB.
- **Mitigation:**
  - Optional **App Lock** encrypts all client-side cases using WebCrypto AES-GCM (256-bit) with PBKDF2 (600,000 rounds).
  - Idle timer automatically locks the vault after 5 minutes of inactivity.
  - One-tap "Wipe This Device" purges all encrypted cases from IndexedDB.

### 3.8 Abuse Case: Server Database Compromise
- **Threat:** Database snapshot on Render / Neon is stolen by an attacker.
- **Mitigation:**
  - Database contains zero call audio, zero transcripts, zero contacts, and zero emergency bank details.
  - Contains only Google `sub`, email, hashed session tokens, and content-free security logs.
