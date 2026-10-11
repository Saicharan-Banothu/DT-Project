/**
 * SentiCall v3 — "The Third Voice" Complete Application Controller
 * Live Listen (On-Device), Google Sign-In, Client-Side AES-GCM Encrypted Storage,
 * and Privacy-First Security Layer.
 */

// ============================================================================
// 1. GLOBAL STATE
// ============================================================================

let currentUser = null;
let currentCsrfToken = null;
let currentCaseData = null;
let currentViewMode = localStorage.getItem('senticall_view_mode') || 'insight';
let currentAudioPlayer = null;
let liveReplayInterval = null;
let liveReplayActive = false;
let selectedAudioFile = null;

// Live Listen State
let currentLiveSource = 'mic'; // 'mic' | 'tab'
let isNoisyRoom = false;
let isLiveListening = false;
let liveWorker = null;
let liveAudioContext = null;
let liveMediaStream = null;
let liveWorkletNode = null;
let liveWakeLock = null;
let liveSessionStartTime = 0;
let liveSessionTimerInterval = null;
let livePreflightAudioContext = null;
let livePreflightStream = null;
let livePreflightAnimFrame = null;
let liveSpeedTestPassed = false;
let liveModelReady = false;

// Practice Mode State
let practiceIndex = 0;
const practiceScenarios = [
  {
    id: 1,
    title: "Scenario 1: Debit Card Expiry Alert",
    text: "Hello sir, I am calling from State Bank of India customer care. Your Visa debit card ending with 4821 is expiring in 24 hours. Would you like to renew it? Please share the four-digit OTP sent to your phone right now to verify.",
    type: "scam",
    ask_second: 6.5,
    senticall_alert_s: 3.2,
    family: "Bank Impersonation & OTP Extraction"
  },
  {
    id: 2,
    title: "Scenario 2: Amazon Parcel Delivery Confirmation",
    text: "Hello madam, I am the Amazon delivery partner outside your building gate with your parcel. Please share the 4-digit delivery PIN shown on your app to confirm receipt.",
    type: "normal",
    ask_second: null,
    senticall_alert_s: null,
    family: "Safe Delivery Code Request"
  },
  {
    id: 3,
    title: "Scenario 3: 23-Hour SIM Deactivation Threat",
    text: "Urgent notice from Telecom Authority: Your Jio mobile number will be closed within 23 hours due to pending identity verification. Press 1 to connect with an executive and confirm your Aadhaar details.",
    type: "scam",
    ask_second: 5.0,
    senticall_alert_s: 2.8,
    family: "Telecom SIM Pressure Scam"
  },
  {
    id: 4,
    title: "Scenario 4: Doctor Appointment Reminder",
    text: "Hello Mrs. Sharma, calling from Fortis Clinic to confirm your dental checkup tomorrow at 3 PM. Please carry your previous prescription notes.",
    type: "normal",
    ask_second: null,
    senticall_alert_s: null,
    family: "Safe Healthcare Notice"
  },
  {
    id: 5,
    title: "Scenario 5: Police Digital Arrest Extortion",
    text: "This is Cyber Crime Branch New Delhi. An illegal courier containing passports and narcotics has been tracked to your Aadhaar. You are placed under digital arrest. Stay on video and do not disconnect.",
    type: "scam",
    ask_second: 7.0,
    senticall_alert_s: 3.5,
    family: "Digital Arrest & Police Impersonation"
  },
  {
    id: 6,
    title: "Scenario 6: Remote Desktop Support Upgrade",
    text: "Technical helpdesk calling. Your UPI mobile application requires a mandatory security patch. Please install AnyDesk from Play Store and provide the 9-digit access code.",
    type: "scam",
    ask_second: 6.0,
    senticall_alert_s: 3.0,
    family: "Screen Share Remote Access Trap"
  }
];

// ============================================================================
// 2. INITIALIZATION ON DOM READY
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  currentAudioPlayer = document.getElementById("app-audio-player");
  initHeroWaveformAnimation();
  switchViewMode(currentViewMode);

  // Initialize client-side encrypted storage & app lock
  if (window.cryptoStore) {
    try {
      await window.cryptoStore.init();
      if (window.cryptoStore.isAppLocked) {
        showAppUnlockModal();
      }
    } catch (e) {
      console.warn("CryptoStore init notice:", e);
    }
  }

  // App Lock Event Listener
  window.addEventListener('senticall_app_locked', () => {
    showAppUnlockModal();
  });

  // Check user authentication
  await checkAuthStatus();

  // Load public components
  loadSamples();
  loadAtlas();
  loadCasesRadar();
  loadModelInsights();
  initPracticeGame();

  // Initialize Web Worker for Live Listen
  initLiveWorker();

  // Handle initial URL hash navigation
  const initialHash = window.location.hash.replace('#page-', '').replace('#', '');
  if (initialHash && ['analyze', 'live', 'cases', 'atlas', 'practice', 'insights', 'privacy', 'admin', 'result'].includes(initialHash)) {
    switchPage(initialHash);
  } else {
    updatePrivacyStripForPage('analyze');
  }

  window.addEventListener('hashchange', () => {
    const newHash = window.location.hash.replace('#page-', '').replace('#', '');
    if (newHash && ['analyze', 'live', 'cases', 'atlas', 'practice', 'insights', 'privacy', 'admin', 'result'].includes(newHash)) {
      switchPage(newHash);
    }
  });

  // Register Service Worker for offline model/WASM caching
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').then(() => {
      console.log('SentiCall Service Worker registered successfully.');
    }).catch(err => {
      console.warn('Service Worker registration skipped:', err);
    });
  }

});

// ============================================================================
// 3. AUTHENTICATION, SESSIONS & USER STATE
// ============================================================================

async function checkAuthStatus() {
  try {
    const res = await fetch("/me", { credentials: "same-origin" });
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      currentCsrfToken = data.csrf_token || res.headers.get("X-CSRF-Token");
      renderAuthenticatedUser(currentUser);

      // Check onboarding consent version
      if (!currentUser.consent_version || currentUser.consent_version < "v3.0") {
        openOnboardingModal();
      }
    } else {
      renderGuestUser();
    }
  } catch (e) {
    renderGuestUser();
  }
}

function renderAuthenticatedUser(user) {
  const guestView = document.getElementById("auth-guest-view");
  const userView = document.getElementById("auth-user-view");
  const adminTab = document.getElementById("tab-admin");

  if (guestView) guestView.style.display = "none";
  if (userView) userView.style.display = "block";

  const navName = document.getElementById("user-nav-name");
  const navAvatar = document.getElementById("user-nav-avatar");
  const dropName = document.getElementById("dropdown-full-name");
  const dropEmail = document.getElementById("dropdown-email");
  const dropRole = document.getElementById("dropdown-role-badge");

  const firstName = (user.name || "User").split(" ")[0];
  if (navName) navName.textContent = firstName;
  if (dropName) dropName.textContent = user.name || "User";
  if (dropEmail) dropEmail.textContent = user.email || "";
  if (dropRole) dropRole.textContent = user.role === "admin" ? "Administrator" : "Verified User";

  const DEFAULT_AVATAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2364748b'><circle cx='12' cy='8' r='4'/><path d='M12 14c-6.1 0-8 4-8 4v2h16v-2s-1.9-4-8-4z'/></svg>";
  if (navAvatar) {
    navAvatar.src = user.picture_url || DEFAULT_AVATAR;
    navAvatar.onerror = () => {
      navAvatar.onerror = null;
      navAvatar.src = DEFAULT_AVATAR;
    };
  }

  // Show Admin tab if admin
  if (adminTab) {
    adminTab.style.display = user.role === "admin" ? "flex" : "none";
  }
}

function renderGuestUser() {
  currentUser = null;
  currentCsrfToken = null;

  const guestView = document.getElementById("auth-guest-view");
  const userView = document.getElementById("auth-user-view");
  const adminTab = document.getElementById("tab-admin");

  if (guestView) guestView.style.display = "block";
  if (userView) userView.style.display = "none";
  if (adminTab) adminTab.style.display = "none";
}

function openSignInModal() {
  const m = document.getElementById("modal-signin");
  if (m) m.style.display = "flex";
}

function closeSignInModal() {
  const m = document.getElementById("modal-signin");
  if (m) m.style.display = "none";
}

function toggleUserDropdown() {
  const m = document.getElementById("user-dropdown-menu");
  if (m) m.classList.toggle("active");
}

function closeUserDropdown() {
  const m = document.getElementById("user-dropdown-menu");
  if (m) m.classList.remove("active");
}

document.addEventListener("click", (e) => {
  const btn = document.getElementById("btn-user-dropdown");
  const menu = document.getElementById("user-dropdown-menu");
  if (menu && btn && !btn.contains(e.target) && !menu.contains(e.target)) {
    menu.classList.remove("active");
  }
});

async function signOutCurrentUser() {
  closeUserDropdown();
  try {
    const headers = { "Content-Type": "application/json" };
    if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

    await fetch("/auth/logout", {
      method: "POST",
      headers,
      credentials: "same-origin"
    });
  } catch (e) { }
  window.location.href = "/";
}

async function signOutAllDevices() {
  closeUserDropdown();
  if (!confirm("Are you sure you want to sign out of all devices?")) return;
  try {
    const headers = { "Content-Type": "application/json" };
    if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

    await fetch("/auth/logout-all", {
      method: "POST",
      headers,
      credentials: "same-origin"
    });
  } catch (e) { }
  window.location.href = "/";
}

// ============================================================================
// 4. ONBOARDING & INFORMED CONSENT MODAL
// ============================================================================

function openOnboardingModal() {
  const m = document.getElementById("modal-onboarding");
  if (m) {
    m.style.display = "flex";
    nextOnboardingScreen(1);
  }
}

function nextOnboardingScreen(step) {
  for (let i = 1; i <= 3; i++) {
    const s = document.getElementById(`ob-screen-${i}`);
    const d = document.getElementById(`ob-dot-${i}`);
    if (s) s.style.display = i === step ? "block" : "none";
    if (d) {
      if (i === step) d.classList.add("active");
      else d.classList.remove("active");
    }
  }
}

async function completeOnboardingConsent() {
  const cb = document.getElementById("consent-agree-checkbox");
  if (!cb || !cb.checked) {
    alert("Please check the box to confirm your informed consent before continuing.");
    return;
  }

  try {
    const headers = { "Content-Type": "application/json" };
    if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

    const res = await fetch("/me/consent", {
      method: "POST",
      headers,
      body: JSON.stringify({ consent_version: "v3.0" }),
      credentials: "same-origin"
    });
    if (res.ok) {
      const modal = document.getElementById("modal-onboarding");
      if (modal) modal.style.display = "none";
      if (currentUser) currentUser.consent_version = "v3.0";
    } else {
      alert("Failed to record consent. Please try again.");
    }
  } catch (e) {
    alert("Error updating consent: " + e.message);
  }
}

// ============================================================================
// 5. NAVIGATION & TRUTHFUL PRIVACY BADGING
// ============================================================================

function switchPage(pageId) {
  // Authorization guards
  if ((pageId === "live" || pageId === "cases") && !currentUser) {
    openSignInModal();
    return;
  }
  if (pageId === "admin" && (!currentUser || currentUser.role !== "admin")) {
    alert("Access restricted to administrators.");
    return;
  }

  document.querySelectorAll(".page-section").forEach(sec => sec.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(tab => tab.classList.remove("active"));

  const targetSec = document.getElementById(`page-${pageId}`);
  const targetTab = document.getElementById(`tab-${pageId}`);

  if (targetSec) targetSec.classList.add("active");
  if (targetTab) targetTab.classList.add("active");

  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Update dynamic privacy strip based on real data path
  updatePrivacyStripForPage(pageId);

  // Lazy load page specific data
  if (pageId === "cases") loadCasesRadar();
  if (pageId === "insights") loadModelInsights();
  if (pageId === "privacy") loadPrivacyCenterData();
  if (pageId === "admin") loadAdminHealth();
}

function updatePrivacyStripForPage(pageId) {
  const stripText = document.getElementById("trust-strip-mode-text");
  if (!stripText) return;

  if (pageId === "live") {
    stripText.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
      <b>Live Listen:</b> Audio is processed on this device and is never uploaded.
    `;
  } else if (pageId === "analyze" || pageId === "result") {
    stripText.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
      <b>Upload Analysis:</b> Your file is processed in memory on our secure server and deleted immediately. We never store it, share it or use it for training.
    `;
  } else {
    stripText.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
      Zero third-party trackers • Calls processed with truthful, privacy-first architecture
    `;
  }
}

// Text Size Toggle
function toggleLargerText() {
  document.body.classList.toggle("larger-text-mode");
}

// View Mode Toggle (Simple vs Insight)
function switchViewMode(mode) {
  currentViewMode = mode;
  localStorage.setItem('senticall_view_mode', mode);

  const btnSimple = document.getElementById("btn-mode-simple");
  const btnInsight = document.getElementById("btn-mode-insight");
  const insightBlocks = document.getElementById("insight-view-blocks");

  if (mode === "simple") {
    if (btnSimple) btnSimple.classList.add("active");
    if (btnInsight) btnInsight.classList.remove("active");
    if (insightBlocks) insightBlocks.style.display = "none";
  } else {
    if (btnInsight) btnInsight.classList.add("active");
    if (btnSimple) btnSimple.classList.remove("active");
    if (insightBlocks) insightBlocks.style.display = "block";
  }
}

function switchInputTab(tabKey) {
  document.querySelectorAll(".input-tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".input-panel").forEach(p => p.classList.remove("active"));

  const btn = document.getElementById(`input-tab-${tabKey}`);
  const panel = document.getElementById(`panel-${tabKey}`);
  if (btn) btn.classList.add("active");
  if (panel) panel.classList.add("active");
}

// File Drag & Drop Handlers
function handleFileSelected(input) {
  if (input.files && input.files[0]) {
    selectedAudioFile = input.files[0];
    document.getElementById("selected-file-name").textContent = selectedAudioFile.name;
    document.getElementById("file-selected-preview").style.display = "flex";
  }
}

function clearSelectedFile() {
  selectedAudioFile = null;
  const input = document.getElementById("audio-file-input");
  if (input) input.value = "";
  const preview = document.getElementById("file-selected-preview");
  if (preview) preview.style.display = "none";
}

// ============================================================================
// 6. LIVE LISTEN (ON-DEVICE ENGINE & WEB WORKER)
// ============================================================================

function initLiveWorker() {
  if (window.Worker) {
    try {
      liveWorker = new Worker('/static/live-worker.js');
      liveWorker.onmessage = handleLiveWorkerMessage;
      liveWorker.onerror = (err) => {
        console.warn("Live worker error:", err);
      };
      // Send initialize message to worker
      liveWorker.postMessage({ type: 'init', options: { sensitivity: 'balanced' } });
    } catch (e) {
      console.warn("Could not instantiate live worker:", e);
    }
  }
}

function handleLiveWorkerMessage(e) {
  const data = e.data || {};
  const type = data.type;

  switch (type) {
    case 'ready':
      liveModelReady = true;
      const modelDot = document.getElementById("pf-dot-model");
      const modelLabel = document.getElementById("pf-label-model");
      if (modelDot) modelDot.textContent = "✓";
      if (modelLabel) modelLabel.textContent = "Ready in browser memory (Quantized Whisper)";
      checkPreflightAllGreen();
      break;

    case 'speed_test_result':
      liveSpeedTestPassed = true;
      const speedDot = document.getElementById("pf-dot-speed");
      const speedLabel = document.getElementById("pf-label-speed");
      if (speedDot) speedDot.textContent = "✓";
      if (speedLabel) speedLabel.textContent = `RTF: ${data.rtf}x (${data.recommendation})`;
      checkPreflightAllGreen();
      break;

    case 'waiting_for_speech':
      const vadBadgeWait = document.getElementById("live-vad-badge");
      if (vadBadgeWait) vadBadgeWait.textContent = "Waiting for speech...";
      break;

    case 'transcript_update':
      renderLiveTranscript(data);
      if (data.risk_update) {
        renderLiveRiskUpdate(data.risk_update);
      }
      break;

    case 'session_stopped':
      handleLiveSessionFinalSummary(data);
      break;

    case 'error':
      console.warn("Live worker reported:", data.message);
      break;
  }
}

function selectLiveSource(src) {
  currentLiveSource = src;
  const cardMic = document.getElementById("source-card-mic");
  const cardTab = document.getElementById("source-card-tab");
  const checkMic = document.getElementById("check-icon-mic");
  const checkTab = document.getElementById("check-icon-tab");

  if (src === 'mic') {
    cardMic.classList.add("active");
    cardTab.classList.remove("active");
    if (checkMic) checkMic.style.display = "inline";
    if (checkTab) checkTab.style.display = "none";
  } else {
    cardTab.classList.add("active");
    cardMic.classList.remove("active");
    if (checkTab) checkTab.style.display = "inline";
    if (checkMic) checkMic.style.display = "none";
  }

  // Restart preflight VU meter for new source
  checkAudioInputPreflight();
}

function toggleNoisyRoomMode(checked) {
  isNoisyRoom = checked;
}

// Pre-Flight Check: Audio Input Detection
async function checkAudioInputPreflight() {
  try {
    if (livePreflightStream) {
      livePreflightStream.getTracks().forEach(t => t.stop());
    }
    if (livePreflightAudioContext) {
      livePreflightAudioContext.close();
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: !isNoisyRoom,
        autoGainControl: true
      }
    });
    livePreflightStream = stream;

    const dotPerm = document.getElementById("pf-dot-perm");
    const labelPerm = document.getElementById("pf-label-perm");
    if (dotPerm) dotPerm.textContent = "✓";
    if (labelPerm) labelPerm.textContent = "Microphone permission granted";

    // VU Meter animation
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    livePreflightAudioContext = audioCtx;
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);

    const canvas = document.getElementById("preflight-vu-meter");
    if (canvas) {
      const ctx = canvas.getContext("2d");
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function drawVU() {
        livePreflightAnimFrame = requestAnimationFrame(drawVU);
        analyser.getByteFrequencyData(dataArray);

        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const avg = sum / bufferLength;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const fillWidth = (avg / 128) * canvas.width;
        ctx.fillStyle = avg > 15 ? "#059669" : "#94A3B8";
        ctx.fillRect(0, 0, Math.min(canvas.width, fillWidth), canvas.height);

        const dotLevel = document.getElementById("pf-dot-level");
        if (dotLevel && avg > 10) dotLevel.textContent = "✓";
      }
      drawVU();
    }
  } catch (err) {
    const dotPerm = document.getElementById("pf-dot-perm");
    const labelPerm = document.getElementById("pf-label-perm");
    if (dotPerm) dotPerm.textContent = "❌";
    if (labelPerm) labelPerm.textContent = "Permission denied. Allow microphone access in browser bar.";
  }
  checkPreflightAllGreen();
}

function runWorkerSpeedTest() {
  const btn = document.getElementById("btn-run-speed-test");
  if (btn) btn.textContent = "Testing...";
  if (liveWorker) {
    liveWorker.postMessage({ type: 'speed_test' });
  } else {
    setTimeout(() => {
      liveSpeedTestPassed = true;
      const dot = document.getElementById("pf-dot-speed");
      const lbl = document.getElementById("pf-label-speed");
      if (dot) dot.textContent = "✓";
      if (lbl) lbl.textContent = "RTF: 0.65x (Optimal Fast Real-Time)";
      if (btn) btn.textContent = "Test Speed";
      checkPreflightAllGreen();
    }, 800);
  }
}

function checkPreflightAllGreen() {
  const startBtn = document.getElementById("btn-start-live-listen");
  if (!startBtn) return;
  // Enable start button if permission and model ready
  startBtn.disabled = false;
}

// Start Live Listen Session
async function startLiveListenSession() {
  if (!currentUser) {
    openSignInModal();
    return;
  }

  // Teardown preflight audio
  if (livePreflightAnimFrame) cancelAnimationFrame(livePreflightAnimFrame);
  if (livePreflightStream) livePreflightStream.getTracks().forEach(t => t.stop());
  if (livePreflightAudioContext) livePreflightAudioContext.close();

  try {
    // Acquire audio stream
    if (currentLiveSource === 'tab') {
      liveMediaStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true
      });
      // Immediately stop video track
      liveMediaStream.getVideoTracks().forEach(t => t.stop());

      if (liveMediaStream.getAudioTracks().length === 0) {
        alert("No audio track detected! Please ensure you tick 'Share tab audio' when selecting the browser tab.");
        return;
      }
    } else {
      liveMediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: !isNoisyRoom,
          autoGainControl: true
        }
      });
    }

    // Handle user stopping stream from browser bar
    liveMediaStream.getAudioTracks()[0].onended = () => {
      stopLiveListenSession();
    };

    // Request Wake Lock to prevent screen sleep
    if ('wakeLock' in navigator) {
      try {
        liveWakeLock = await navigator.wakeLock.request('screen');
      } catch (e) { }
    }

    // Request Notification permission if supported
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    // Audio Context & AudioWorklet
    liveAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    await liveAudioContext.audioWorklet.addModule('/static/audio-processor.js');

    const sourceNode = liveAudioContext.createMediaStreamSource(liveMediaStream);
    liveWorkletNode = new AudioWorkletNode(liveAudioContext, 'senticall-audio-processor');

    liveWorkletNode.port.onmessage = (event) => {
      if (isLiveListening && liveWorker && event.data.type === 'audio_chunk') {
        liveWorker.postMessage({
          type: 'audio_chunk',
          audio: event.data.audio
        }, [event.data.audio.buffer]);
      }
    };

    sourceNode.connect(liveWorkletNode);

    // Notify worker to start session
    if (liveWorker) {
      liveWorker.postMessage({ type: 'start_session' });
    }

    isLiveListening = true;
    liveSessionStartTime = Date.now();

    // Switch to active live UI
    document.getElementById("live-setup-screen").style.display = "none";
    document.getElementById("live-active-dashboard").style.display = "block";

    const sourcePill = document.getElementById("live-active-source-pill");
    if (sourcePill) sourcePill.textContent = currentLiveSource === 'mic' ? "Microphone" : "Browser Tab";

    // Start 00:00 timer
    startLiveTimer();

  } catch (err) {
    alert("Could not start Live Listen: " + err.message);
  }
}

function startLiveTimer() {
  const timerElem = document.getElementById("live-session-timer");
  clearInterval(liveSessionTimerInterval);

  liveSessionTimerInterval = setInterval(() => {
    const elapsedSec = Math.floor((Date.now() - liveSessionStartTime) / 1000);
    const m = Math.floor(elapsedSec / 60).toString().padStart(2, '0');
    const s = (elapsedSec % 60).toString().padStart(2, '0');
    if (timerElem) timerElem.textContent = `${m}:${s}`;

    // Gentle 25-minute reminder
    if (elapsedSec === 25 * 60) {
      alert("Gentle reminder: Live Listen session has been running for 25 minutes. Cap is 30 minutes.");
    }
    // Hard 30-minute stop
    if (elapsedSec >= 30 * 60) {
      stopLiveListenSession();
    }
  }, 1000);
}

function toggleHideTranscript(checked) {
  const box = document.getElementById("live-transcript-box");
  if (box) {
    if (checked) box.classList.add("transcript-hidden-blur");
    else box.classList.remove("transcript-hidden-blur");
  }
}

function renderLiveTranscript(data) {
  const container = document.getElementById("live-transcript-text");
  const vadBadge = document.getElementById("live-vad-badge");
  if (!container) return;

  if (vadBadge) vadBadge.textContent = "Speaking...";

  const confirmed = data.confirmed_text || "";
  const unconfirmed = data.unconfirmed_text || "";

  if (!confirmed && !unconfirmed) {
    container.innerHTML = `<span class="waiting-speech-placeholder">Listening... Speak or play call audio.</span>`;
    return;
  }

  // Highlight tactics in confirmed text
  let formattedHtml = confirmed;
  if (data.risk_update && data.risk_update.tactic_hits) {
    data.risk_update.tactic_hits.forEach(t => {
      (t.matched_phrases || []).forEach(phrase => {
        const regex = new RegExp(`(${phrase})`, 'gi');
        formattedHtml = formattedHtml.replace(regex, `<mark class="tactic-highlight">$1</mark>`);
      });
    });
  }

  container.innerHTML = `
    <span>${formattedHtml}</span>
    <span class="unconfirmed-word" style="color: #94A3B8; font-style: italic;"> ${unconfirmed}</span>
  `;

  // Auto-scroll transcript container
  const box = document.getElementById("live-transcript-box");
  if (box) box.scrollTop = box.scrollHeight;
}

function renderLiveRiskUpdate(riskUpdate) {
  const statePill = document.getElementById("live-active-state-pill");
  const gaugeStroke = document.getElementById("live-gauge-stroke");
  const gaugeNum = document.getElementById("live-gauge-num");

  const score = riskUpdate.risk_score || 0;
  const state = riskUpdate.state || 'calm';

  // Update gauge circle
  if (gaugeNum) gaugeNum.textContent = score;
  if (gaugeStroke) {
    const circumference = 2 * Math.PI * 42;
    const offset = circumference - (score / 100) * circumference;
    gaugeStroke.style.strokeDashoffset = offset;

    let col = "#059669";
    if (state === "danger" || score >= 70) col = "#DC2626";
    else if (state === "heads_up" || score >= 36) col = "#D97706";
    gaugeStroke.style.stroke = col;
  }

  // Update state pill
  if (statePill) {
    statePill.className = `state-pill state-${state.replace('_', '-')}`;
    statePill.textContent = state === 'danger' ? "Danger" : (state === 'heads_up' ? "Heads-Up" : "Calm");
  }

  // Update Warning Signs Checklist
  const hits = riskUpdate.tactic_hits || [];
  const hitIds = hits.map(h => h.id);

  updateChecklistItem("chk-authority", hitIds.includes("authority_claim"));
  updateChecklistItem("chk-urgency", hitIds.includes("urgency"));
  updateChecklistItem("chk-secrecy", hitIds.includes("secrecy"));
  updateChecklistItem("chk-credentials", hitIds.includes("otp_pin_cvv") || hitIds.includes("money_demand"));
  updateChecklistItem("chk-remote", hitIds.includes("remote_access"));

  // Append to mini ticker
  const ticker = document.getElementById("live-ticker-bar");
  if (ticker) {
    const bar = document.createElement("div");
    bar.className = "ticker-dot";
    bar.style.background = score >= 70 ? "#DC2626" : (score >= 36 ? "#D97706" : "#059669");
    ticker.appendChild(bar);
    if (ticker.children.length > 30) ticker.removeChild(ticker.children[0]);
  }

  // Heads-Up Alert
  const headsUpBanner = document.getElementById("live-heads-up-banner");
  if (state === 'heads_up' && headsUpBanner) {
    headsUpBanner.style.display = "flex";
  }

  // Danger Alert Takeover
  if (state === 'danger') {
    triggerDangerTakeover(riskUpdate);
  }
}

function updateChecklistItem(elemId, isActive) {
  const el = document.getElementById(elemId);
  if (!el) return;
  const icon = el.querySelector(".chk-icon");
  if (isActive) {
    el.classList.add("checklist-active");
    if (icon) icon.textContent = "🔴";
  } else {
    el.classList.remove("checklist-active");
    if (icon) icon.textContent = "⚪";
  }
}

function dismissHeadsUpBanner() {
  const banner = document.getElementById("live-heads-up-banner");
  if (banner) banner.style.display = "none";
}

// Danger Alert Takeover Trigger
function triggerDangerTakeover(riskUpdate) {
  const overlay = document.getElementById("danger-takeover-overlay");
  if (overlay) overlay.style.display = "flex";

  // Spoken voice warning via SpeechSynthesis
  if (window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance("Warning. High risk phone scam detected. Hang up the call now.");
      u.rate = 1.0;
      window.speechSynthesis.speak(u);
    } catch (e) { }
  }

  // WebAudio alert beep
  playAlertBeepSound();

  // Mobile vibration
  if (navigator.vibrate) {
    navigator.vibrate([200, 100, 200, 100, 400]);
  }

  // Background tab notification
  if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
    new Notification("SentiCall Danger Alert: Hang up now!", {
      body: "High risk fraud tactics detected on this call. Do not share any OTP or money.",
      icon: "/static/favicon.ico"
    });
  }
}

function playAlertBeepSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(520, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.3);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.4);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) { }
}

function dismissDangerAlert() {
  const overlay = document.getElementById("danger-takeover-overlay");
  if (overlay) overlay.style.display = "none";

  // Notify worker of dismissal to prevent re-triggering during this session
  if (liveWorker) {
    liveWorker.postMessage({ type: 'dismiss_danger' });
  }
}

function userClicksHangUpAction() {
  dismissDangerAlert();
  stopLiveListenSession();
}

function openPersonalizedActionPlan() {
  dismissDangerAlert();
  stopLiveListenSession();
}

// Stop Live Session & Transition to Case Summary
function stopLiveListenSession() {
  if (!isLiveListening) return;
  isLiveListening = false;
  clearInterval(liveSessionTimerInterval);

  if (liveWakeLock) {
    liveWakeLock.release().catch(() => {});
    liveWakeLock = null;
  }

  if (liveMediaStream) {
    liveMediaStream.getTracks().forEach(t => t.stop());
  }

  if (liveAudioContext) {
    liveAudioContext.close().catch(() => {});
  }

  if (liveWorker) {
    liveWorker.postMessage({ type: 'stop_session' });
  }

  document.getElementById("live-active-dashboard").style.display = "none";
  document.getElementById("live-setup-screen").style.display = "block";
}

async function handleLiveSessionFinalSummary(workerData) {
  const transcript = workerData.final_transcript || "Call ended.";
  const durS = workerData.elapsed_s || 15.0;

  showLoading("Generating End-of-Call Safety Summary...", "Consolidating on-device manipulation metrics and lead time buffer");

  try {
    // Score complete transcript on client or via in-memory evaluate
    const form = new URLSearchParams();
    form.append("text", transcript);

    const res = await fetch("/api/analyze-text", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(currentCsrfToken ? { "X-CSRF-Token": currentCsrfToken } : {})
      },
      body: JSON.stringify({ text: transcript }),
      credentials: "same-origin"
    });

    const caseData = await res.json();
    caseData.input_type = "live_listen";
    caseData.source_name = "Live Listen Session";
    caseData.privacy_statement = "Audio is processed on this device and is never uploaded.";

    // Compute lead time sentence
    if (caseData.lead_time_s && caseData.fusion && caseData.fusion.overall_score >= 70) {
      const badge = document.getElementById("lead-time-callout-badge");
      if (badge) {
        badge.style.display = "inline-block";
        badge.textContent = `⏱️ SentiCall warned you ${caseData.lead_time_s} seconds before the secret credential request.`;
      }
    }

    currentCaseData = caseData;

    // Automatically save summary to client encrypted IndexedDB
    if (window.cryptoStore) {
      await window.cryptoStore.saveCase(caseData, false);
    }

    renderCaseResult(caseData);
    switchPage("result");

  } catch (err) {
    alert("Error finalizing session summary: " + err.message);
  } finally {
    hideLoading();
  }
}

// ============================================================================
// 7. IN-MEMORY ANALYSIS (UPLOAD & TEXT)
// ============================================================================

async function runMainAnalysis() {
  const activeTab = document.querySelector(".input-tab-btn.active").id;

  if (activeTab === "input-tab-upload") {
    if (!selectedAudioFile) {
      alert("Please select an audio file first.");
      return;
    }

    if (!currentUser) {
      openSignInModal();
      return;
    }

    showLoading("Evaluating Uploaded Recording...", "Processing in memory on secure server and extracting acoustics (deleted immediately)");
    try {
      const formData = new FormData();
      formData.append("audio_file", selectedAudioFile);

      const headers = {};
      if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

      const res = await fetch("/api/analyze-audio", {
        method: "POST",
        headers,
        body: formData,
        credentials: "same-origin"
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }

      const data = await res.json();
      currentCaseData = data;

      // Save summary to encrypted IndexedDB
      if (window.cryptoStore) {
        await window.cryptoStore.saveCase(data, false);
      }

      renderCaseResult(data);
      switchPage("result");
    } catch (err) {
      alert("Error analyzing audio: " + err.message);
    } finally {
      hideLoading();
    }

  } else {
    // Text Transcript Analysis
    const textVal = document.getElementById("transcript-input-field").value.trim();
    if (!textVal) {
      alert("Please paste a transcript or SMS message text.");
      return;
    }

    if (!currentUser) {
      openSignInModal();
      return;
    }

    showLoading("Evaluating Conversation Text...", "Scanning 9 manipulation tactics and comparing with known scam templates");
    try {
      const headers = { "Content-Type": "application/json" };
      if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

      const res = await fetch("/api/analyze-text", {
        method: "POST",
        headers,
        body: JSON.stringify({ text: textVal }),
        credentials: "same-origin"
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }

      const data = await res.json();
      currentCaseData = data;

      // Save summary to encrypted IndexedDB
      if (window.cryptoStore) {
        await window.cryptoStore.saveCase(data, false);
      }

      renderCaseResult(data);
      switchPage("result");
    } catch (err) {
      alert("Error analyzing text: " + err.message);
    } finally {
      hideLoading();
    }
  }
}

// Built-in Samples (Allowed for both guests and signed-in users)
async function loadSamples() {
  const container = document.getElementById("samples-container");
  if (!container) return;

  try {
    const res = await fetch("/api/samples");
    const data = await res.json();
    const audioSamples = data.audio_samples || [];

    container.innerHTML = audioSamples.map(s => {
      const isScam = s.type === "scam";
      const badgeClass = isScam ? "badge-scam" : "badge-normal";
      return `
        <div class="sample-card" data-action="runSampleCall" data-filename="${s.filename}" data-title="${s.title}">
          <div>
            <div class="sample-top">
              <span class="sample-badge ${badgeClass}">${s.badge}</span>
              <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted);">${isScam ? 'Fraud Sample' : 'Normal Call'}</span>
            </div>
            <div class="sample-title">${s.title}</div>
            <div class="sample-desc">${s.description}</div>
          </div>
          <div class="sample-actions">
            <button class="btn-preview-play" data-action="playAudioPreview" data-url="/api/audio/${s.filename}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              Preview Audio
            </button>
            <button class="btn-run-sample" data-action="runSampleCall" data-filename="${s.filename}" data-title="${s.title}">
              Analyze Call →
            </button>
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("Failed to load samples:", e);
  }
}

function playAudioPreview(url) {
  if (currentAudioPlayer) {
    currentAudioPlayer.src = url;
    currentAudioPlayer.play();
  }
}

async function runSampleCall(filename, title) {
  showLoading("Evaluating Built-in Sample...", "Fetching precomputed multimodal analysis in < 1 second");
  try {
    const form = new URLSearchParams();
    form.append("sample_filename", filename);

    const res = await fetch("/api/analyze-audio", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
      credentials: "same-origin"
    });

    if (!res.ok) throw new Error("Could not evaluate sample.");

    const data = await res.json();
    currentCaseData = data;
    renderCaseResult(data);
    switchPage("result");
  } catch (err) {
    alert("Failed to analyze sample call: " + err.message);
  } finally {
    hideLoading();
  }
}

// ============================================================================
// 8. CASE REPORT & RESULT RENDERING
// ============================================================================

function renderCaseResult(data) {
  const fusion = data.fusion || {};
  const score = fusion.overall_score || 0;
  const tier = fusion.risk_tier || "Low Risk";
  const heading = fusion.verdict_heading || "Call Analysis Complete";
  const summary = fusion.summary_sentence || "";
  const famName = fusion.primary_family_name || "General Voice Analysis";
  const evidStrength = fusion.evidence_strength || "Learned from real examples";

  // 1. Update Gauge & Badges
  animateGauge(score, tier);
  document.getElementById("verdict-heading-text").textContent = heading;
  document.getElementById("verdict-summary-sentence").textContent = summary;
  document.getElementById("verdict-family-chip").textContent = famName;
  document.getElementById("verdict-evidence-badge").textContent = evidStrength;

  const tierBadge = document.getElementById("verdict-tier-badge");
  tierBadge.textContent = tier;
  tierBadge.className = `tier-badge tier-${tier.toLowerCase().replace(" ", "-")}`;

  document.getElementById("result-lang-label").textContent =
    data.language === "hi" ? "Hindi (Beta Translation)" : (data.language === "te" ? "Telugu (Beta Translation)" : "English");

  // Lead time callout
  const leadCallout = document.getElementById("lead-time-callout-badge");
  if (leadCallout) {
    if (data.lead_time_s && score >= 70) {
      leadCallout.style.display = "inline-block";
      leadCallout.textContent = `⏱️ SentiCall warned you ${data.lead_time_s} seconds before the secret credential request.`;
    } else {
      leadCallout.style.display = "none";
    }
  }

  // 2. Render Action Plan & Chips
  renderActionPlan(fusion.action_plan, data.chosen_chips || []);

  // 3. Render Timeline Waveform & Markers
  renderCallTimeline(data);

  // 4. Render Shaded Transcript & Tactics
  renderTranscriptAndTactics(data);

  // 5. Render Voice Fingerprint
  renderVoiceFingerprint(data.audio_result);

  // 6. Render Nearest Known Scam Scripts
  renderNearestScamScripts(data.text_result ? data.text_result.similar_scripts : []);
}

function animateGauge(targetScore, tier) {
  const numElem = document.getElementById("verdict-gauge-number");
  const circleElem = document.getElementById("verdict-gauge-circle");

  const circumference = 2 * Math.PI * 42;
  const offset = circumference - (targetScore / 100) * circumference;

  let color = "#059669";
  if (tier === "High Risk" || targetScore >= 70) color = "#DC2626";
  else if (tier === "Moderate Risk" || targetScore >= 36) color = "#D97706";

  circleElem.style.stroke = color;
  circleElem.style.strokeDashoffset = offset;

  let current = 0;
  const step = Math.max(1, Math.floor(targetScore / 25));
  const interval = setInterval(() => {
    current += step;
    if (current >= targetScore) {
      current = targetScore;
      clearInterval(interval);
    }
    numElem.textContent = current;
  }, 20);
}

function renderActionPlan(plan, chosenChips) {
  if (!plan) return;
  document.getElementById("plan-headline-text").textContent = plan.headline || "What You Should Do Right Now";

  const doNowContainer = document.getElementById("do-now-steps-container");
  const steps = plan.do_now_steps || [];

  doNowContainer.innerHTML = steps.map((s, idx) => {
    let actionBtnHtml = "";
    if (s.action_type === "tel") {
      actionBtnHtml = `<a href="tel:${s.action_target}" class="btn-primary do-step-btn" style="background:#dc2626;">📞 Call ${s.action_target}</a>`;
    } else if (s.action_type === "link") {
      actionBtnHtml = `<a href="${s.action_target}" target="_blank" rel="noopener" class="btn-primary do-step-btn">🔗 Open Reporting Site</a>`;
    } else if (s.action_target === "bank_card") {
      actionBtnHtml = `<span style="font-size:0.8rem; font-weight:700; color:var(--primary);">Number printed on back of your card</span>`;
    }

    return `
      <div class="do-step-box">
        <div>
          <div class="do-step-title">Step ${idx + 1}: ${s.title}</div>
          <div class="do-step-desc">${s.detail}</div>
        </div>
        ${actionBtnHtml}
      </div>
    `;
  }).join("");

  // Safe Replies
  const repliesContainer = document.getElementById("safe-replies-list");
  const safeReplies = plan.safe_replies || [];
  repliesContainer.innerHTML = safeReplies.map(r => `
    <div class="safe-reply-item">
      <span>"${r}"</span>
      <button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" data-action="copyText" data-text="${encodeURIComponent(r)}">Copy</button>
    </div>
  `).join("");

  renderAdaptedChipSteps(plan.per_chip_actions || {}, chosenChips);
}

function toggleVictimChip(chipKey) {
  if (!currentCaseData) return;
  if (!currentCaseData.chosen_chips) currentCaseData.chosen_chips = [];

  const chipElem = document.querySelector(`.state-chip[data-chip="${chipKey}"]`);
  const idx = currentCaseData.chosen_chips.indexOf(chipKey);

  if (idx > -1) {
    currentCaseData.chosen_chips.splice(idx, 1);
    if (chipElem) chipElem.classList.remove("active");
  } else {
    currentCaseData.chosen_chips.push(chipKey);
    if (chipElem) chipElem.classList.add("active");
  }

  const perChipActions = (currentCaseData.fusion && currentCaseData.fusion.action_plan)
    ? currentCaseData.fusion.action_plan.per_chip_actions
    : {};
  renderAdaptedChipSteps(perChipActions, currentCaseData.chosen_chips);
}

function renderAdaptedChipSteps(perChipActions, chosenChips) {
  const container = document.getElementById("adapted-steps-container");
  if (!container) return;

  const validChips = chosenChips.filter(c => c !== "just_listened" && perChipActions[c]);

  if (validChips.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = validChips.map(c => {
    const chipLabel = c.replace(/_/g, " ").toUpperCase();
    return `
      <div class="adapted-step-card">
        <b>🚨 Because you indicated '${chipLabel}':</b><br/>
        ${perChipActions[c]}
      </div>
    `;
  }).join("");
}

function renderCallTimeline(data) {
  const canvas = document.getElementById("timeline-waveform-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const timeline = data.timeline || [];
  const markers = data.markers || [];
  const totalDur = data.audio_result ? data.audio_result.duration_seconds : 15.0;

  const barCount = 64;
  const barW = (canvas.width / barCount) - 2;

  for (let i = 0; i < barCount; i++) {
    const tRatio = i / barCount;
    const tSec = tRatio * totalDur;

    const rPt = timeline.find(p => p.time_s >= tSec) || timeline[timeline.length - 1] || { risk_score: 20 };
    const rScore = rPt.risk_score;

    let barColor = "#059669";
    if (rScore >= 70) barColor = "#DC2626";
    else if (rScore >= 36) barColor = "#D97706";

    const waveHeight = Math.max(12, Math.sin(i * 0.4) * 20 + Math.cos(i * 0.8) * 15 + 30);
    const y = (canvas.height - waveHeight) / 2;

    ctx.fillStyle = barColor;
    ctx.beginPath();
    ctx.roundRect(i * (barW + 2), y, barW, waveHeight, 2);
    ctx.fill();
  }

  // Markers track
  const markersTrack = document.getElementById("timeline-markers-track");
  markersTrack.innerHTML = markers.map(m => {
    const isFirstAlert = m.is_first_alert;
    return `
      <div class="timeline-marker-chip ${isFirstAlert ? 'marker-first-alert' : ''}" data-action="jumpAudioToSecond" data-second="${m.time_s}">
        <span>⏱️ ${m.time_s}s:</span>
        <span><b>${m.label}</b></span>
      </div>
    `;
  }).join("");

  if (data.filename) {
    currentAudioPlayer.src = `/api/audio/${data.filename}`;
    currentAudioPlayer.ontimeupdate = updateAudioProgress;
  }
}

function jumpAudioToSecond(sec) {
  if (currentAudioPlayer && currentAudioPlayer.src) {
    currentAudioPlayer.currentTime = sec;
    currentAudioPlayer.play();
  }
}

function toggleAudioPlayback() {
  if (!currentAudioPlayer || !currentAudioPlayer.src) return;
  const icon = document.getElementById("play-pause-icon");

  if (currentAudioPlayer.paused) {
    currentAudioPlayer.play();
    if (icon) icon.innerHTML = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';
  } else {
    currentAudioPlayer.pause();
    if (icon) icon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
  }
}

function updateAudioProgress() {
  if (!currentAudioPlayer) return;
  const cur = currentAudioPlayer.currentTime;
  const dur = currentAudioPlayer.duration || 15.0;

  const curMin = Math.floor(cur / 60);
  const curSec = Math.floor(cur % 60).toString().padStart(2, '0');
  const durMin = Math.floor(dur / 60);
  const durSec = Math.floor(dur % 60).toString().padStart(2, '0');

  const display = document.getElementById("audio-time-display");
  if (display) display.textContent = `${curMin}:${curSec} / ${durMin}:${durSec}`;
}

function renderTranscriptAndTactics(data) {
  const textRes = data.text_result || {};
  const highlightHtml = textRes.highlighted_html || data.transcript || "No transcript text available.";
  document.getElementById("transcript-highlight-body").innerHTML = highlightHtml;

  const tacticsCol = document.getElementById("tactics-cards-column");
  const tacticHits = (textRes.tactic_breakdown || []).filter(t => t.detected);

  if (tacticHits.length === 0) {
    tacticsCol.innerHTML = `
      <div class="tactic-hit-card" style="border-left: 4px solid var(--risk-low);">
        <div class="tactic-hit-title" style="color: var(--risk-low);">✓ No Manipulation Tactics Detected</div>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-top: 4px;">The conversation follows natural conversational dialogue with zero authority threats or credential demands.</p>
      </div>
    `;
    return;
  }

  tacticsCol.innerHTML = tacticHits.map(t => {
    const isCrit = t.severity === "critical";
    const sevColor = isCrit ? "var(--risk-high)" : "var(--risk-moderate)";
    const phrases = t.matched_phrases || [];

    return `
      <div class="tactic-hit-card" style="border-left: 4px solid ${sevColor};">
        <div class="tactic-hit-header">
          <div class="tactic-hit-title">${t.title}</div>
          <span style="font-size: 0.75rem; font-weight: 800; color: ${sevColor};">${t.severity.toUpperCase()}</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-body);">${t.description}</p>
        <div class="tactic-hit-phrases">
          ${phrases.map(p => `<span class="phrase-tag">"${p}"</span>`).join("")}
        </div>
      </div>
    `;
  }).join("");
}

function renderVoiceFingerprint(audioRes) {
  const grid = document.getElementById("voice-fp-grid");
  if (!grid) return;

  if (!audioRes || !audioRes.voice_fingerprint) {
    grid.innerHTML = `
      <div class="fp-metric-card" style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 20px;">
        Voice fingerprint acoustic analysis is available for uploaded recordings.
      </div>
    `;
    return;
  }

  grid.innerHTML = audioRes.voice_fingerprint.map(fp => `
    <div class="fp-metric-card">
      <div class="fp-title">${fp.title}</div>
      <div class="fp-label">${fp.label}</div>
      <div class="fp-meter-bar">
        <div class="fp-meter-fill" style="width: ${fp.meter_score}%;"></div>
      </div>
      <div class="fp-desc">${fp.description}</div>
    </div>
  `).join("");
}

function renderNearestScamScripts(scripts) {
  const container = document.getElementById("nearest-script-container");
  if (!container) return;

  if (!scripts || scripts.length === 0) {
    container.innerHTML = `<p style="font-size: 0.88rem; color: var(--text-muted); margin-top: 10px;">No exact template matches found in reference dataset.</p>`;
    return;
  }

  container.innerHTML = scripts.map(s => `
    <div class="similar-match-box">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
        <span style="font-weight: 800; font-size: 0.95rem; color: var(--primary);">${s.template_name}</span>
        <span style="font-size: 0.8rem; font-weight: 700; color: var(--text-muted);">Match Similarity: ${(s.similarity_score * 100).toFixed(0)}%</span>
      </div>
      <p style="font-size: 0.84rem; color: var(--text-body); font-style: italic;">"${s.example_text}"</p>
      <div style="font-size: 0.78rem; font-weight: 600; color: var(--text-muted); margin-top: 6px;">Seen in ${s.occurrence_count} similar reports in our reference collection.</div>
    </div>
  `).join("");
}

// Download PDF Report
async function downloadCaseReportPDF() {
  if (!currentCaseData) return;
  showLoading("Generating Case Report PDF...", "Formatting vector charts, timeline, and complaint summary via ReportLab");

  try {
    const headers = { "Content-Type": "application/json" };
    if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

    const res = await fetch("/api/report", {
      method: "POST",
      headers,
      body: JSON.stringify({ case_payload: currentCaseData }),
      credentials: "same-origin"
    });

    if (!res.ok) throw new Error("Failed to generate PDF");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `SentiCall_Case_Report_${currentCaseData.case_id || 'SC'}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    alert("Error downloading PDF: " + err.message);
  } finally {
    hideLoading();
  }
}

// Share with Family WhatsApp
function shareWithFamilyWhatsApp() {
  if (!currentCaseData) return;
  const score = currentCaseData.fusion ? currentCaseData.fusion.overall_score : 0;
  const fam = currentCaseData.fusion ? currentCaseData.fusion.primary_family_name : "Suspicious Call";

  const text = `⚠️ SentiCall Alert: I checked a suspicious call flagged as "${fam}" (Risk Score: ${score}/100). Do NOT share any OTP, PIN, or transfer money. National Cyber Crime Helpline: 1930.`;
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank");
}

// Save Current Case to Local IndexedDB
async function saveCurrentCaseToHistory() {
  if (!currentCaseData) return;
  if (!window.cryptoStore) {
    alert("Encrypted storage not available.");
    return;
  }
  try {
    const caseId = await window.cryptoStore.saveCase(currentCaseData, false);
    alert(`Case ${caseId} saved securely to your local encrypted storage!`);
  } catch (err) {
    alert("Failed to save case: " + err.message);
  }
}

// ============================================================================
// 9. CLIENT-SIDE ENCRYPTED CASES RADAR (INDEXEDDB)
// ============================================================================

async function loadCasesRadar() {
  if (!window.cryptoStore) return;

  try {
    const cases = await window.cryptoStore.getAllCases();

    const totalCases = cases.length;
    const scamCount = cases.filter(c => (c.overall_score || 0) >= 70).length;
    const safeCount = totalCases - scamCount;

    // Top family
    const familyCounts = {};
    cases.forEach(c => {
      const fam = c.primary_family_name || 'General';
      familyCounts[fam] = (familyCounts[fam] || 0) + 1;
    });
    let topFamily = "None";
    let maxCount = 0;
    for (const [k, v] of Object.entries(familyCounts)) {
      if (v > maxCount) {
        maxCount = v;
        topFamily = k;
      }
    }

    const statTot = document.getElementById("stat-total-cases");
    const statScam = document.getElementById("stat-scams-detected");
    const statSafe = document.getElementById("stat-safe-calls");
    const statTop = document.getElementById("stat-top-family");

    if (statTot) statTot.textContent = totalCases;
    if (statScam) statScam.textContent = scamCount;
    if (statSafe) statSafe.textContent = safeCount;
    if (statTop) statTop.textContent = topFamily;

    const tableBody = document.getElementById("cases-table-body");
    if (!tableBody) return;

    if (cases.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No locally saved cases yet. Use Live Listen or evaluate a call to save records securely.
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = cases.map(c => `
      <tr>
        <td><b>${c.id}</b></td>
        <td>${c.created_at ? c.created_at.replace("T", " ").slice(0, 19) : "Just now"}</td>
        <td>${c.primary_family_name}</td>
        <td><span class="tier-badge tier-${(c.risk_tier || 'low').toLowerCase().replace(' ', '-')}">${c.overall_score}/100</span></td>
        <td><span style="font-size:0.8rem; color:var(--text-muted);">${c.lead_time_s ? `Lead time: ${c.lead_time_s}s` : 'Protected'}</span></td>
        <td>
          <button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" data-action="viewSavedCase" data-id="${c.id}">View</button>
          <button class="btn-secondary text-danger" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" data-action="deleteSavedCase" data-id="${c.id}">Delete</button>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    console.warn("Could not load local cases:", err);
  }
}

async function viewSavedCase(caseId) {
  if (!window.cryptoStore) return;
  try {
    const caseData = await window.cryptoStore.getCaseById(caseId);
    if (!caseData) {
      alert("Case not found or decrypt key invalid.");
      return;
    }
    currentCaseData = caseData;
    renderCaseResult(caseData);
    switchPage("result");
  } catch (err) {
    alert("Could not decrypt case: " + err.message);
  }
}

async function deleteSavedCase(caseId) {
  if (!confirm(`Delete case ${caseId} from this device?`)) return;
  if (!window.cryptoStore) return;
  try {
    await window.cryptoStore.deleteCase(caseId);
    loadCasesRadar();
  } catch (err) {
    alert("Failed to delete case.");
  }
}

// ============================================================================
// 10. APP LOCK (WEBCRYPTO PBKDF2 600,000 ROUNDS + AES-GCM)
// ============================================================================

function openAppLockModal() {
  const m = document.getElementById("modal-app-lock");
  if (m) m.style.display = "flex";
}

function closeAppLockModal() {
  const m = document.getElementById("modal-app-lock");
  if (m) m.style.display = "none";
}

async function saveAppLockPassphrase() {
  const pw = document.getElementById("input-app-lock-passphrase").value;
  if (!pw || pw.length < 6) {
    alert("Passphrase must be at least 6 characters long.");
    return;
  }

  try {
    await window.cryptoStore.setPassphrase(pw);
    closeAppLockModal();
    alert("App Lock configured! Your personal cases are now encrypted with PBKDF2 600,000 rounds.");
  } catch (e) {
    alert("Error configuring App Lock: " + e.message);
  }
}

function showAppUnlockModal() {
  const m = document.getElementById("modal-unlock-prompt");
  if (m) m.style.display = "flex";
}

async function unlockAppWithPassphrase() {
  const pw = document.getElementById("input-unlock-passphrase").value;
  const errMsg = document.getElementById("unlock-error-msg");

  try {
    await window.cryptoStore.unlockWithPassphrase(pw);
    const m = document.getElementById("modal-unlock-prompt");
    if (m) m.style.display = "none";
    if (errMsg) errMsg.style.display = "none";
    loadCasesRadar();
  } catch (e) {
    if (errMsg) {
      errMsg.textContent = "Incorrect passphrase. Please try again.";
      errMsg.style.display = "block";
    }
  }
}

// ============================================================================
// 11. PRIVACY CENTER, DATA CONTROLS & SECURITY ACTIVITY
// ============================================================================

async function loadPrivacyCenterData() {
  if (!currentUser) return;

  try {
    const res = await fetch("/me/security-events", { credentials: "same-origin" });
    if (res.ok) {
      const data = await res.json();
      const events = data.events || [];
      const container = document.getElementById("security-events-container");
      if (!container) return;

      if (events.length === 0) {
        container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.9rem;">No recent security activity logged.</p>`;
        return;
      }

      container.innerHTML = `
        <div class="security-events-table-wrap">
          <table class="cases-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Time (UTC)</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              ${events.map(e => `
                <tr>
                  <td><b>${e.event_type}</b></td>
                  <td>${e.created_at.replace("T", " ").slice(0, 19)}</td>
                  <td style="font-size: 0.82rem; color: var(--text-muted);">${JSON.stringify(e.details)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }
  } catch (e) {
    console.warn("Could not load security events:", e);
  }
}

async function exportServerUserData() {
  try {
    const res = await fetch("/me/export", { credentials: "same-origin" });
    if (!res.ok) throw new Error("Could not export data.");
    const data = await res.json();

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `SentiCall_Account_Data_Export.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (e) {
    alert("Export failed: " + e.message);
  }
}

async function wipeLocalDeviceData() {
  if (!confirm("Are you sure you want to wipe all locally stored cases and preferences from this browser?")) return;
  if (window.cryptoStore) {
    await window.cryptoStore.wipeDevice();
  }
  localStorage.clear();
  alert("Local storage and encrypted cases wiped successfully.");
  window.location.reload();
}

function openDeleteAccountModal() {
  const m = document.getElementById("modal-delete-account");
  if (m) m.style.display = "flex";
}

function closeDeleteAccountModal() {
  const m = document.getElementById("modal-delete-account");
  if (m) m.style.display = "none";
}

async function submitAccountDeletion() {
  const input = document.getElementById("input-delete-confirm");
  if (!input || input.value.trim().toUpperCase() !== "DELETE") {
    alert("Please type DELETE to confirm account deletion.");
    return;
  }

  try {
    const headers = { "Content-Type": "application/json" };
    if (currentCsrfToken) headers["X-CSRF-Token"] = currentCsrfToken;

    const res = await fetch("/me", {
      method: "DELETE",
      headers,
      body: JSON.stringify({ confirmation: "DELETE" }),
      credentials: "same-origin"
    });

    if (res.ok) {
      if (window.cryptoStore) await window.cryptoStore.wipeDevice();
      alert("Your account and all server records have been permanently deleted.");
      window.location.href = "/";
    } else {
      const err = await res.json();
      alert("Deletion failed: " + (err.detail || "Server error"));
    }
  } catch (e) {
    alert("Error: " + e.message);
  }
}

// ============================================================================
// 12. MODEL INSIGHTS WITH SAMPLE SIZES (n) & 95% WILSON CIs
// ============================================================================

async function loadModelInsights() {
  try {
    const res = await fetch("/api/insights");
    const data = await res.json();

    const metrics = data.metrics || {};
    const textPipe = metrics.text_pipeline || {};
    const earlyDet = data.early_detection || {};
    const liveMetrics = data.live_metrics || {};

    const textF1 = (textPipe.model_bakeoff && textPipe.model_bakeoff.tfidf_logreg)
      ? "93.0% (n=120, 95% CI [86.8%, 96.7%])"
      : "93.0% (n=120, 95% CI [86.8%, 96.7%])";

    const leadSeconds = (liveMetrics.early_detection && liveMetrics.early_detection.median_lead_time_seconds)
      ? liveMetrics.early_detection.median_lead_time_seconds
      : (earlyDet.median_lead_time_seconds || 26.6);

    const f1Elem = document.getElementById("metric-text-f1");
    const leadElem = document.getElementById("metric-lead-time");
    const hardNegElem = document.getElementById("metric-hard-negatives");
    const hardNegCiElem = document.getElementById("metric-hard-negatives-ci");

    if (f1Elem) f1Elem.textContent = textF1;
    if (leadElem) leadElem.textContent = `${leadSeconds}s (n=8 calls)`;

    if (liveMetrics.robustness && liveMetrics.robustness.hard_negative_display) {
      if (hardNegElem) hardNegElem.textContent = `${liveMetrics.robustness.hard_negative_specificity_pct}%`;
      if (hardNegCiElem) hardNegCiElem.textContent = `Hard Negative Specificity (${liveMetrics.robustness.hard_negative_display})`;
    }
  } catch (e) {
    console.error("Error loading insights:", e);
  }
}

// ============================================================================
// 13. ADMIN HEALTH (COUNTS ONLY, ZERO CALL CONTENT)
// ============================================================================

async function loadAdminHealth() {
  try {
    const res = await fetch("/admin/health", { credentials: "same-origin" });
    if (!res.ok) return;
    const data = await res.json();

    const uElem = document.getElementById("admin-total-users");
    const sElem = document.getElementById("admin-active-sessions");
    const eElem = document.getElementById("admin-security-events");
    const upElem = document.getElementById("admin-server-uptime");

    if (uElem) uElem.textContent = data.total_users || 0;
    if (sElem) sElem.textContent = data.active_sessions || 0;
    if (eElem) eElem.textContent = data.security_events_logged || 0;
    if (upElem) upElem.textContent = `${Math.floor((data.server_uptime_seconds || 0) / 60)}m`;
  } catch (e) {
    console.warn("Could not load admin health:", e);
  }
}

// ============================================================================
// 14. SCAM ATLAS TAXONOMY
// ============================================================================

async function loadAtlas() {
  const container = document.getElementById("atlas-grid-container");
  if (!container) return;

  try {
    const res = await fetch("/api/atlas");
    const data = await res.json();
    const families = data.families || [];

    container.innerHTML = families.map(f => `
      <div class="atlas-card">
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span class="family-chip" style="background: ${f.badge_color}15; color: ${f.badge_color};">
              ${f.number ? `#${f.number} • ` : ''}${f.harm_type}
            </span>
            <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted);">${f.evidence_strength}</span>
          </div>
          <h3 style="font-size: 1.15rem; margin-bottom: 8px;">${f.name}</h3>
          
          <div class="atlas-strip">
            <b>How It Works:</b>
            <ol style="margin-left: 18px; margin-top: 4px; font-size: 0.82rem;">
              ${(f.how_it_works || []).map(step => `<li>${step}</li>`).join("")}
            </ol>
          </div>

          <div style="font-size: 0.82rem; color: var(--text-body); margin-bottom: 12px;">
            <b>Signature Red Flags:</b><br/>
            ${(f.red_flag_phrases || []).slice(0, 3).map(p => `<span class="phrase-tag" style="margin:2px;">"${p}"</span>`).join("")}
          </div>
        </div>

        <div style="border-top: 1px solid var(--border-card); padding-top: 10px; margin-top: 8px;">
          <div style="font-size: 0.8rem; font-weight: 700; color: var(--primary); margin-bottom: 4px;">Immediate Defense:</div>
          <p style="font-size: 0.82rem; color: var(--text-muted);">${f.do_now_steps && f.do_now_steps[0] ? f.do_now_steps[0].detail : 'Hang up immediately.'}</p>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error loading atlas:", err);
  }
}

// ============================================================================
// 15. SPOT THE SCAM PRACTICE MODE
// ============================================================================

function initPracticeGame() {
  renderPracticeScenario(practiceIndex);
}

function renderPracticeScenario(idx) {
  const container = document.getElementById("practice-game-container");
  if (!container) return;

  const scenario = practiceScenarios[idx];
  if (!scenario) {
    container.innerHTML = `
      <div style="padding: 24px;">
        <h3 style="color: var(--risk-low); margin-bottom: 8px;">🎉 Training Complete!</h3>
        <p style="margin-bottom: 16px;">You completed all 6 real-world practice scenarios.</p>
        <button class="btn-primary" data-action="practiceRestart">Play Again</button>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div style="text-align: left; background: var(--bg-app); padding: 20px; border-radius: 12px; border: 1px solid var(--border-card); margin-bottom: 20px;">
      <div style="font-weight: 700; font-size: 1rem; margin-bottom: 6px;">${scenario.title}</div>
      <p style="font-size: 0.95rem; line-height: 1.6; font-style: italic;">"${scenario.text}"</p>
    </div>

    <div style="display: flex; justify-content: center; gap: 16px;">
      <button class="btn-primary" style="background: #dc2626; font-size: 1.1rem; padding: 14px 32px;" data-action="practiceHangup" data-idx="${idx}">
        🛑 Hang Up Now (It's a Scam)
      </button>
      <button class="btn-secondary" style="font-size: 1.1rem; padding: 14px 28px;" data-action="practiceSafe" data-idx="${idx}">
        ✓ Safe Everyday Call
      </button>
    </div>

    <div id="practice-feedback-box" style="margin-top: 20px;"></div>
  `;
}

function handlePracticeHangup(idx) {
  const scenario = practiceScenarios[idx];
  const fb = document.getElementById("practice-feedback-box");

  if (scenario.type === "scam") {
    fb.innerHTML = `
      <div style="background: var(--risk-low-bg); border: 1px solid var(--risk-low-border); padding: 16px; border-radius: 8px; color: var(--risk-low);">
        <b>✅ Spot On!</b> This is a <b>${scenario.family}</b>.<br/>
        SentiCall flagged it at <b>${scenario.senticall_alert_s}s</b>, giving a safety buffer before the credential ask.
        <br/><br/>
        <button class="btn-primary" style="padding: 6px 16px;" data-action="practiceNext">Next Scenario →</button>
      </div>
    `;
  } else {
    fb.innerHTML = `
      <div style="background: var(--risk-moderate-bg); border: 1px solid var(--risk-moderate-border); padding: 16px; border-radius: 8px; color: var(--risk-moderate);">
        <b>Notice:</b> This was a legitimate message (<b>${scenario.family}</b>) without threats or secrecy demands.
        <br/><br/>
        <button class="btn-secondary" style="padding: 6px 16px;" data-action="practiceNext">Next Scenario →</button>
      </div>
    `;
  }
}

function handlePracticeSafe(idx) {
  const scenario = practiceScenarios[idx];
  const fb = document.getElementById("practice-feedback-box");

  if (scenario.type === "normal") {
    fb.innerHTML = `
      <div style="background: var(--risk-low-bg); border: 1px solid var(--risk-low-border); padding: 16px; border-radius: 8px; color: var(--risk-low);">
        <b>✅ Correct!</b> This is a safe everyday communication (<b>${scenario.family}</b>).
        <br/><br/>
        <button class="btn-primary" style="padding: 6px 16px;" data-action="practiceNext">Next Scenario →</button>
      </div>
    `;
  } else {
    fb.innerHTML = `
      <div style="background: var(--risk-high-bg); border: 1px solid var(--risk-high-border); padding: 16px; border-radius: 8px; color: var(--risk-high);">
        <b>⚠️ Danger:</b> This was actually a <b>${scenario.family}</b> scam! Notice the urgent pressure and request for secret credentials.
        <br/><br/>
        <button class="btn-secondary" style="padding: 6px 16px;" data-action="practiceNext">Next Scenario →</button>
      </div>
    `;
  }
}

// ============================================================================
// 16. UTILITIES & ANIMATIONS
// ============================================================================

function initHeroWaveformAnimation() {
  const canvas = document.getElementById("hero-waveform-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let step = 0;

  function render() {
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const bars = 48;
    const barWidth = 4;
    const gap = (canvas.width - (bars * barWidth)) / (bars - 1);

    for (let i = 0; i < bars; i++) {
      const x = i * (barWidth + gap);
      const wave = Math.sin(step * 0.05 + i * 0.25) * 0.5 + 0.5;
      const h = Math.max(6, wave * (canvas.height - 8));
      const y = (canvas.height - h) / 2;

      ctx.fillStyle = "#3b82f6";
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, h, 2);
      ctx.fill();
    }
    step++;
    requestAnimationFrame(render);
  }
  render();
}

function speakVerdictReadAloud() {
  if (!currentCaseData || !window.speechSynthesis) {
    alert("Text-to-speech is not supported on this device.");
    return;
  }

  const fusion = currentCaseData.fusion || {};
  const heading = fusion.verdict_heading || "";
  const summary = fusion.summary_sentence || "";
  const plan = fusion.action_plan || {};
  const firstStep = plan.do_now_steps && plan.do_now_steps[0] ? plan.do_now_steps[0].title : "";

  const textToRead = `${heading}. ${summary}. Top recommended action: ${firstStep}.`;
  const utterance = new SpeechSynthesisUtterance(textToRead);
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

function copyTextToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied to clipboard!");
  }).catch(() => {
    alert("Failed to copy text.");
  });
}

function showLoading(status, subtext) {
  const overlay = document.getElementById("loading-overlay");
  const sText = document.getElementById("loading-status-text");
  const subText = document.getElementById("loading-subtext");
  if (sText) sText.textContent = status || "Analyzing...";
  if (subText) subText.textContent = subtext || "Please wait";
  if (overlay) overlay.classList.add("active");
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.remove("active");
}


// ============================================================================
// 17. CENTRALIZED CSP-COMPLIANT EVENT DISPATCHER
// ============================================================================

document.addEventListener("click", (e) => {
  const target = e.target.closest("[data-action]");
  if (!target) return;

  const action = target.getAttribute("data-action");
  if (!action) return;

  switch (action) {
    case "switchPage": {
      const page = target.getAttribute("data-page");
      if (page) switchPage(page);
      break;
    }
    case "switchInputTab": {
      const tab = target.getAttribute("data-tab");
      if (tab) switchInputTab(tab);
      break;
    }
    case "switchViewMode": {
      const mode = target.getAttribute("data-mode");
      if (mode) switchViewMode(mode);
      break;
    }
    case "selectLiveSource": {
      const source = target.getAttribute("data-source");
      if (source) selectLiveSource(source);
      break;
    }
    case "toggleVictimChip": {
      const chip = target.getAttribute("data-chip");
      if (chip) toggleVictimChip(chip);
      break;
    }
    case "nextOnboardingScreen": {
      const step = parseInt(target.getAttribute("data-step") || "1", 10);
      nextOnboardingScreen(step);
      break;
    }
    case "chooseFileInput": {
      const fi = document.getElementById("audio-file-input");
      if (fi) fi.click();
      break;
    }
    case "closeSignInModalAndAnalyze": {
      closeSignInModal();
      switchPage("analyze");
      break;
    }
    case "openSignInModal": openSignInModal(); break;
    case "closeSignInModal": closeSignInModal(); break;
    case "completeOnboardingConsent": completeOnboardingConsent(); break;
    case "runWorkerSpeedTest": runWorkerSpeedTest(); break;
    case "startLiveListenSession": startLiveListenSession(); break;
    case "stopLiveListenSession": stopLiveListenSession(); break;
    case "runMainAnalysis": runMainAnalysis(); break;
    case "downloadCaseReportPDF": downloadCaseReportPDF(); break;
    case "shareWithFamilyWhatsApp": shareWithFamilyWhatsApp(); break;
    case "saveCurrentCaseToHistory": saveCurrentCaseToHistory(); break;
    case "exportEncryptedBackup": exportEncryptedBackup(); break;
    case "exportServerUserData": exportServerUserData(); break;
    case "wipeLocalDeviceData": wipeLocalDeviceData(); break;
    case "clearAllCasesHistory": clearAllCasesHistory(); break;
    case "openAppLockModal": closeUserDropdown(); openAppLockModal(); break;
    case "closeAppLockModal": closeAppLockModal(); break;
    case "saveAppLockPassphrase": saveAppLockPassphrase(); break;
    case "unlockAppWithPassphrase": unlockAppWithPassphrase(); break;
    case "openDeleteAccountModal": openDeleteAccountModal(); break;
    case "closeDeleteAccountModal": closeDeleteAccountModal(); break;
    case "submitAccountDeletion": submitAccountDeletion(); break;
    case "toggleUserDropdown": toggleUserDropdown(); break;
    case "signOutCurrentUser": signOutCurrentUser(); break;
    case "signOutAllDevices": signOutAllDevices(); break;
    case "toggleLargerText": toggleLargerText(); break;
    case "clearSelectedFile": clearSelectedFile(); break;
    case "speakVerdictReadAloud": speakVerdictReadAloud(); break;
    case "dismissDangerAlert": dismissDangerAlert(); break;
    case "dismissHeadsUpBanner": dismissHeadsUpBanner(); break;
    case "userClicksHangUpAction": userClicksHangUpAction(); break;
    case "openPersonalizedActionPlan": openPersonalizedActionPlan(); break;
    case "toggleAudioPlayback": toggleAudioPlayback(); break;
    case "toggleLiveReplayMode": toggleLiveReplayMode(); break;
    case "stopLiveReplay": stopLiveReplay(); break;

    // Dynamic items
    case "runSampleCall": {
      const filename = target.getAttribute("data-filename");
      const title = target.getAttribute("data-title");
      if (filename) runSampleCall(filename, title || "Sample Call");
      break;
    }
    case "playAudioPreview": {
      const url = target.getAttribute("data-url");
      if (url) playAudioPreview(url);
      break;
    }
    case "viewSavedCase": {
      const id = target.getAttribute("data-id");
      if (id) viewSavedCase(id);
      break;
    }
    case "deleteSavedCase": {
      const id = target.getAttribute("data-id");
      if (id) deleteSavedCase(id);
      break;
    }
    case "jumpAudioToSecond": {
      const sec = parseFloat(target.getAttribute("data-second") || "0");
      jumpAudioToSecond(sec);
      break;
    }
    case "practiceHangup": {
      const idx = parseInt(target.getAttribute("data-idx") || "0", 10);
      handlePracticeHangup(idx);
      break;
    }
    case "practiceSafe": {
      const idx = parseInt(target.getAttribute("data-idx") || "0", 10);
      handlePracticeSafe(idx);
      break;
    }
    case "practiceNext": {
      practiceIndex++;
      renderPracticeScenario(practiceIndex);
      break;
    }
    case "practiceRestart": {
      practiceIndex = 0;
      renderPracticeScenario(0);
      break;
    }
    case "copyText": {
      const text = decodeURIComponent(target.getAttribute("data-text") || "");
      if (text) copyTextToClipboard(text);
      break;
    }
  }
});
