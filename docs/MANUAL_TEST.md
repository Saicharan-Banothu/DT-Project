# SentiCall v3 — Manual Verification Checklist

*Use this checklist for manual quality assurance of hardware-dependent features, browser tab audio capture, and Google OAuth flows.*

---

## 1. Browser Tab Audio Capture (WhatsApp Web, Google Meet, Zoom)

Because automated headless browsers cannot natively simulate user interaction with the OS-level screen/tab sharing picker dialog, verify tab capture using these steps:

### Test Procedure:
1. Open Chrome or Microsoft Edge (desktop).
2. Open SentiCall at `http://localhost:8000` (or `https://senticall-v2.onrender.com`).
3. Ensure you are signed in, then navigate to the **Live Listen** tab.
4. Under *Choose Audio Source*, select **Listen to a browser tab**.
5. In a second browser tab, open a YouTube video or a WhatsApp Web voice note (e.g. searching for a scam call recording or bank warning video).
6. In SentiCall, click **Start Live Protection**.
7. The browser's native sharing picker appears:
   - Select the **Chrome Tab** (or **Edge Tab**) where your audio is playing.
   - **Crucial Step:** Check the box labeled **"Share tab audio"** in the bottom left of the picker dialog.
   - Click **Share**.
8. Verify that SentiCall immediately suppresses the video feed and begins processing only the audio track.
9. Play the audio in the source tab.
10. **Expected Behavior:**
    - The VAD indicator turns to *"Speaking..."*.
    - Transcribed words appear in the *Live Transcript Stream* pane.
    - If the source is a scam sample (e.g., demanding OTP or money), the *Risk Gauge* rises, warning checklist lights turn red, and the *Danger Takeover Overlay* appears.
    - Click **Stop & Summarize**. Verify the End-of-Call Summary renders with the correct lead time buffer and action plan.
11. **Negative Test (Missing Tab Audio Checkbox):**
    - Click *Start Live Protection* again, choose a tab, but **uncheck** *"Share tab audio"*.
    - Click *Share*.
    - **Expected Behavior:** SentiCall detects the absence of an audio track and displays a friendly prompt explaining that *"Share tab audio"* must be ticked.

---

## 2. Speakerphone Microphone Verification

1. Place your smartphone on the table next to your laptop.
2. Navigate to **Live Listen** and select **Listen through my microphone**.
3. Verify the **Pre-Flight System Check**:
   - Audio Permission: Green check mark (✓).
   - Audio Input Detection: VU meter canvas reacts in real time to background room noise.
   - On-Device Whisper Model: Green check mark (✓).
   - Device Speed Test: Click *Test Speed*, verify Real-Time Factor (RTF) measurement appears with green check mark.
4. Click **Start Live Protection**.
5. Speak in English, Hindi, or Telugu: *"Hello, I am calling from State Bank of India, your card is blocked, please share your OTP immediately."*
6. **Expected Behavior:**
   - The *Live Transcript* renders the words in real-time with gray unconfirmed words turning black upon confirmation.
   - *Claims to be your bank* and *Creating pressure* light up red on the checklist.
   - Full-width *DANGER* takeover fires with an audible alarm tone, spoken speech warning, and large *Hang Up* action.
   - Click **Not a scam (Dismiss)**: The overlay closes and local correction is recorded without uploading.

---

## 3. Google Sign-In & Session Verification

1. Click **Sign In** in the top navigation bar.
2. Verify the Google branded button matches official specifications.
3. Click **Sign in with Google**:
   - Redirects to `accounts.google.com`.
   - Displays consent screen with application name `SentiCall` and minimal scopes (`openid`, `email`, `profile`).
4. Complete authentication.
5. Redirects to SentiCall with `auth=success`.
6. **Expected Behavior:**
   - Avatar and user's first name appear in navigation bar.
   - User dropdown menu displays email and role badge.
   - If first login, the 3-step *Informed Consent* onboarding modal appears.
7. Open DevTools > Application > Cookies:
   - Verify `__Host-session` (or `session_token`) has `HttpOnly: true`, `SameSite: Lax`, `Secure: true`.
8. Click **Sign Out**:
   - Cookie is cleared, user state reverts to Guest immediately.

---

## 4. Privacy Center & Data Sovereignty

1. Sign in and open **Privacy Center**.
2. **Export My Data:** Click *Export JSON Data*.
   - Verify downloaded JSON contains user profile, sessions, consent timestamp, and audit log.
   - Verify file contains **zero** call audio, transcripts, or call data.
3. **Wipe This Device:**
   - Click *Wipe Local Storage* and confirm.
   - Verify all IndexedDB cases, local settings, and view preferences are purged.
4. **Delete Account:**
   - Click *Delete My Account*.
   - Verify prompt requires typing `DELETE`.
   - Submit deletion. Verify user record and all server sessions are permanently purged from database.
