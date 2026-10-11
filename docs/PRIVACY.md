# SentiCall v3 — Truthful Privacy Policy & Architecture

*Last Updated: October 2026*  
*Privacy Commitment: Calls are private. We favor user privacy over server convenience at every architectural layer.*

---

## 1. Our Privacy Promise in Plain Language

> "We don't sell your data. We don't listen to your calls on our servers. You can delete everything at any time."

SentiCall v3 is designed from the ground up to minimize data collection. We never train AI models on your private conversations, we never sell data to advertisers, and we never retain your audio recordings.

---

## 2. Truthful Data Path by Operating Mode

Every privacy badge displayed in the SentiCall interface dynamically reflects the exact data path of the active mode:

| Mode | Real Data Path | Truthful Privacy Statement |
|---|---|---|
| **Live Listen** (Microphone / Browser Tab) | **100% On-Device Browser Processing**<br>Audio captured via `AudioWorklet`, transcribed locally in a Web Worker using self-hosted quantized ONNX Whisper model, scored locally using our client-side JavaScript risk engine. | *"Audio is processed on this device and is never uploaded."* |
| **Upload Analysis** (Hosted Mode) | **Transient In-Memory Evaluation**<br>Audio file written to a temporary memory-backed directory with owner-only (0700) permissions, analyzed, and deleted immediately in a `finally` block. Background sweeper purges any orphaned temp file older than 10 minutes. Audio and transcripts never appear in logs or persistent database storage. | *"Your file is processed in memory on our secure server and deleted immediately. We never store it, share it or use it for training."* |

---

## 3. Data Inventory: What We Store vs. What We Never Store

### What We Store on the Server:
1. **Google Identity Profile:** Stable Google identifier (`sub`), verified email, display name, profile photo URL.
2. **Session Records:** Cryptographic hash of session token, last active timestamp, user-agent snippet, creation timestamp.
3. **Informed Consent Record:** Consent version (e.g. `v3.0`) and UTC timestamp.
4. **Non-Sensitive Preferences:** Language, larger text mode, sensitivity preset.
5. **Security Audit Log:** Content-free security events (e.g., `login`, `logout`, `consent_updated`, `settings_changed`) with timestamp and hashed IP.

### What We NEVER Store on the Server:
- ❌ Call audio recordings (.mp3, .wav)
- ❌ Live transcripts or spoken conversation text
- ❌ Microphone or browser audio streams
- ❌ Personal contacts or address book data
- ❌ Geolocation coordinates
- ❌ Advertising identifiers or browser fingerprinters
- ❌ Emergency contacts or banking provider names (stored solely on the user's local device, encrypted)

---

## 4. Client-Side Encryption & App Lock

To allow users to keep a history of suspicious calls without trusting our servers:
- **Local Storage via IndexedDB:** Saved case summaries, flagged phrases, and timelines are stored on your local device.
- **WebCrypto AES-GCM (256-bit):** All local case records are encrypted using browser WebCrypto APIs.
- **App Lock (PBKDF2 600,000 Iterations):** Users can set an optional passphrase. The encryption key is derived using PBKDF2 with 600,000 iterations and SHA-256.
- **Auto-Lock:** The app automatically locks after 5 idle minutes. If no passphrase is set, a non-extractable device key is used.
- **No Master Key:** We do not possess a recovery key. If a passphrase is forgotten, local data cannot be recovered.

---

## 5. User Rights & Data Sovereignty

SentiCall provides one-click self-service data management directly from the **Privacy Center**:
1. **Export My Data:** Download a machine-readable JSON file (`SentiCall_Account_Data_Export.json`) containing all server-held profile and security event records.
2. **Wipe This Device:** Instant client-side purge of all locally encrypted cases, cached models, and stored settings.
3. **Delete Account:** Permanent server-side deletion of user records, active sessions, consent timestamps, and logs. Requires typing `DELETE` to confirm.

---

## 6. Zero Third-Party Runtime Requests

To eliminate cross-site tracking and network leaks:
- All fonts are loaded from the user's native system font stack.
- Whisper ONNX models and Transformers.js runtimes are self-hosted from same-origin `/models/` and `/vendor/`.
- No analytics scripts (Google Analytics, Mixpanel, etc.).
- No external CDNs, advertising networks, or third-party error trackers.
- The only external domain ever contacted is `accounts.google.com` during the OAuth 2.0 authorization step.
