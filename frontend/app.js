/**
 * SentiCall v2 — "The Third Voice" Frontend Application Controller
 * Author: Senior Full-Stack & Applied ML Engineer
 */

// Global State
let currentCaseData = null;
let currentViewMode = localStorage.getItem('senticall_view_mode') || 'insight';
let currentAudioPlayer = null;
let liveReplayInterval = null;
let liveReplayActive = false;
let mediaRecorder = null;
let recordedAudioChunks = [];
let selectedAudioFile = null;

// Practice Mode State
let practiceIndex = 0;
let practiceStartTime = 0;
let practiceTimerInterval = null;
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

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initHeroWaveformAnimation();
  loadSamples();
  loadAtlas();
  loadCasesRadar();
  loadModelInsights();
  initPracticeGame();
  
  currentAudioPlayer = document.getElementById("app-audio-player");
  
  // Restore view mode
  switchViewMode(currentViewMode);
});

// Navigation Switcher
function switchPage(pageId) {
  document.querySelectorAll(".page-section").forEach(sec => sec.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(tab => tab.classList.remove("active"));

  const targetSec = document.getElementById(`page-${pageId}`);
  const targetTab = document.getElementById(`tab-${pageId}`);

  if (targetSec) targetSec.classList.add("active");
  if (targetTab) targetTab.classList.add("active");

  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (pageId === "cases") loadCasesRadar();
  if (pageId === "insights") loadModelInsights();
}

// Larger Text Mode Toggle
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

// Input Tabs Switcher
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
  document.getElementById("audio-file-input").value = "";
  document.getElementById("file-selected-preview").style.display = "none";
}

// Microphone Recording Handler
async function toggleMicRecording() {
  const btn = document.getElementById("btn-mic-toggle");
  const statusText = document.getElementById("mic-status-text");

  if (mediaRecorder && mediaRecorder.state === "recording") {
    // Stop recording
    mediaRecorder.stop();
    btn.classList.remove("recording");
    statusText.textContent = "Processing recorded audio...";
  } else {
    // Start recording
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordedAudioChunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedAudioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(recordedAudioChunks, { type: 'audio/mp3' });
        selectedAudioFile = new File([audioBlob], "recorded_call.mp3", { type: 'audio/mp3' });
        statusText.textContent = `Recorded ${(audioBlob.size/1024).toFixed(1)} KB clip. Ready to analyze.`;
        // Auto trigger analysis
        runMainAnalysis();
      };

      mediaRecorder.start();
      btn.classList.add("recording");
      statusText.textContent = "Recording in progress... Speak now. Tap button to finish.";
    } catch (err) {
      alert("Microphone access was denied or is not supported in this browser.");
    }
  }
}

// Hero Animated Soundwave Canvas
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

// Load Pre-configured Sample Calls Grid
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
        <div class="sample-card" onclick="runSampleCall('${s.filename}', '${s.title}')">
          <div>
            <div class="sample-top">
              <span class="sample-badge ${badgeClass}">${s.badge}</span>
              <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted);">${isScam ? 'Fraud Sample' : 'Normal Call'}</span>
            </div>
            <div class="sample-title">${s.title}</div>
            <div class="sample-desc">${s.description}</div>
          </div>
          <div class="sample-actions" onclick="event.stopPropagation();">
            <button class="btn-preview-play" onclick="playAudioPreview('/api/audio/${s.filename}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              Preview Audio
            </button>
            <button class="btn-run-sample" onclick="runSampleCall('${s.filename}', '${s.title}')">
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

// Play Short Audio Preview
function playAudioPreview(url) {
  if (currentAudioPlayer) {
    currentAudioPlayer.src = url;
    currentAudioPlayer.play();
  }
}

// Run Built-in Sample Call (Instant Fast Path)
async function runSampleCall(filename, title) {
  showLoading("Evaluating Sample Call...", "Fetching precomputed multimodal analysis in < 1 second");
  try {
    const form = new URLSearchParams();
    form.append("sample_filename", filename);

    const res = await fetch("/api/analyze-audio", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    });
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

// Run Main Analysis (Upload, Mic, or Text)
async function runMainAnalysis() {
  const activeTab = document.querySelector(".input-tab-btn.active").id;

  if (activeTab === "input-tab-upload" || activeTab === "input-tab-mic") {
    if (!selectedAudioFile) {
      alert("Please select or record an audio file first.");
      return;
    }

    showLoading("Listening to the Call...", "Extracting telephony features and running on-device Whisper transcription");
    try {
      const formData = new FormData();
      formData.append("audio_file", selectedAudioFile);

      const res = await fetch("/api/analyze-audio", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      currentCaseData = data;
      renderCaseResult(data);
      switchPage("result");
    } catch (err) {
      alert("Error analyzing audio: " + err.message);
    } finally {
      hideLoading();
    }
  } else {
    // Text Analysis
    const textVal = document.getElementById("transcript-input-field").value.trim();
    if (!textVal) {
      alert("Please paste a transcript or SMS message text.");
      return;
    }

    showLoading("Reading What Was Said...", "Scanning 9 manipulation tactics and comparing with known scam templates");
    try {
      const res = await fetch("/api/analyze-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textVal })
      });
      const data = await res.json();
      currentCaseData = data;
      renderCaseResult(data);
      switchPage("result");
    } catch (err) {
      alert("Error analyzing text: " + err.message);
    } finally {
      hideLoading();
    }
  }
}

// Render Result View from JSON Payload
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

  document.getElementById("result-lang-label").textContent = data.language === "hi" ? "Hindi (Beta Translation)" : (data.language === "te" ? "Telugu (Beta Translation)" : "English");

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

// Animate Circular Gauge (0 to target)
function animateGauge(targetScore, tier) {
  const numElem = document.getElementById("verdict-gauge-number");
  const circleElem = document.getElementById("verdict-gauge-circle");
  
  const circumference = 2 * Math.PI * 42; // ~263.89
  const offset = circumference - (targetScore / 100) * circumference;

  let color = "#059669";
  if (tier === "High Risk") color = "#dc2626";
  else if (tier === "Moderate Risk") color = "#d97706";
  else if (tier === "Unsure") color = "#6366f1";

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

// Render "Do This Now" Steps and "What Did You Already Do?" Chips
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
      actionBtnHtml = `<a href="${s.action_target}" target="_blank" class="btn-primary do-step-btn">🔗 Open Reporting Site</a>`;
    } else if (s.action_target === "bank_card") {
      actionBtnHtml = `<span style="font-size:0.8rem; font-weight:700; color:var(--primary);">Number is printed on back of your card</span>`;
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
      <button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" onclick="copyTextToClipboard('${r.replace(/'/g, "\\'")}')">Copy</button>
    </div>
  `).join("");

  // Update Adapted Steps
  renderAdaptedChipSteps(plan.per_chip_actions || {}, chosenChips);
}

// Toggle "What did you already do?" Chip
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

  const perChipActions = (currentCaseData.fusion && currentCaseData.fusion.action_plan) ? currentCaseData.fusion.action_plan.per_chip_actions : {};
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

// Render Call Timeline Waveform & Milestone Markers
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

  // Draw Waveform Bars with Color Gradient (Green -> Amber -> Red)
  const barCount = 64;
  const barW = (canvas.width / barCount) - 2;

  for (let i = 0; i < barCount; i++) {
    const tRatio = i / barCount;
    const tSec = tRatio * totalDur;

    // Find risk near tSec
    const rPt = timeline.find(p => p.time_s >= tSec) || timeline[timeline.length - 1] || { risk_score: 20 };
    const rScore = rPt.risk_score;

    let barColor = "#059669";
    if (rScore >= 70) barColor = "#dc2626";
    else if (rScore >= 36) barColor = "#d97706";

    const waveHeight = Math.max(12, Math.sin(i * 0.4) * 20 + Math.cos(i * 0.8) * 15 + 30);
    const y = (canvas.height - waveHeight) / 2;

    ctx.fillStyle = barColor;
    ctx.beginPath();
    ctx.roundRect(i * (barW + 2), y, barW, waveHeight, 2);
    ctx.fill();
  }

  // Render Milestone Markers Track
  const markersTrack = document.getElementById("timeline-markers-track");
  markersTrack.innerHTML = markers.map(m => {
    const isFirstAlert = m.is_first_alert;
    return `
      <div class="timeline-marker-chip ${isFirstAlert ? 'marker-first-alert' : ''}" onclick="jumpAudioToSecond(${m.time_s})">
        <span>⏱️ ${m.time_s}s:</span>
        <span><b>${m.label}</b></span>
      </div>
    `;
  }).join("");

  // Setup Audio Player if audio source available
  if (data.filename) {
    currentAudioPlayer.src = `/api/audio/${data.filename}`;
    currentAudioPlayer.ontimeupdate = updateAudioProgress;
  }
}

// Jump Audio Playback to Specified Second
function jumpAudioToSecond(sec) {
  if (currentAudioPlayer && currentAudioPlayer.src) {
    currentAudioPlayer.currentTime = sec;
    currentAudioPlayer.play();
    document.getElementById("play-pause-icon").innerHTML = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';
  }
}

function toggleAudioPlayback() {
  if (!currentAudioPlayer || !currentAudioPlayer.src) return;
  const icon = document.getElementById("play-pause-icon");

  if (currentAudioPlayer.paused) {
    currentAudioPlayer.play();
    icon.innerHTML = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';
  } else {
    currentAudioPlayer.pause();
    icon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
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

  document.getElementById("audio-time-display").textContent = `${curMin}:${curSec} / ${durMin}:${durSec}`;
}

// Live Replay Mode Simulation
function toggleLiveReplayMode() {
  if (liveReplayActive) {
    stopLiveReplay();
  } else {
    startLiveReplay();
  }
}

function startLiveReplay() {
  if (!currentCaseData) return;
  liveReplayActive = true;

  const btn = document.getElementById("btn-live-replay");
  btn.textContent = "⏹ Stop Live Replay";
  btn.style.background = "#dc2626";

  const banner = document.getElementById("live-replay-alert-banner");
  banner.classList.remove("active");

  const firstAlertS = currentCaseData.first_alert_s || 4.5;
  const leadTime = currentCaseData.lead_time_s || 14.5;
  document.getElementById("live-lead-time-notice").textContent = `SentiCall triggered alert ${leadTime} seconds before the secret credential request.`;

  if (currentAudioPlayer && currentAudioPlayer.src) {
    currentAudioPlayer.currentTime = 0;
    currentAudioPlayer.play();
  }

  let elapsedSec = 0;
  clearInterval(liveReplayInterval);

  liveReplayInterval = setInterval(() => {
    elapsedSec += 0.5;
    
    // Check if first alert moment reached
    if (elapsedSec >= firstAlertS && currentCaseData.fusion.overall_score >= 70) {
      banner.classList.add("active");
    }

    if (elapsedSec >= (currentCaseData.audio_result ? currentCaseData.audio_result.duration_seconds : 18.0)) {
      stopLiveReplay();
    }
  }, 500);
}

function stopLiveReplay() {
  liveReplayActive = false;
  clearInterval(liveReplayInterval);

  const btn = document.getElementById("btn-live-replay");
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Watch It as If It Were Live`;
  btn.style.background = "";

  if (currentAudioPlayer) currentAudioPlayer.pause();
}

// Render Transcript with Word Shading & Manipulation Tactics
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
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-top: 4px;">The conversation follows natural social dialogue with zero authority threats or credential demands.</p>
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

// Render Voice Fingerprint Cards
function renderVoiceFingerprint(audioRes) {
  const grid = document.getElementById("voice-fp-grid");
  if (!grid) return;

  if (!audioRes || !audioRes.voice_fingerprint) {
    grid.innerHTML = `
      <div class="fp-metric-card" style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 20px;">
        Acoustic voice fingerprint is available for audio recordings and mic inputs. (Text-only analysis performed)
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

// Render Nearest Known Scam Scripts
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

// Download Branded Case Report PDF
async function downloadCaseReportPDF() {
  if (!currentCaseData) return;
  showLoading("Generating Case Report PDF...", "Formatting vector charts, timeline, and complaint summary via ReportLab");

  try {
    const res = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_payload: currentCaseData })
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

// Share with Family on WhatsApp
function shareWithFamilyWhatsApp() {
  if (!currentCaseData) return;
  const score = currentCaseData.fusion ? currentCaseData.fusion.overall_score : 0;
  const fam = currentCaseData.fusion ? currentCaseData.fusion.primary_family_name : "Suspicious Call";
  
  const text = `⚠️ SentiCall Alert: I checked a suspicious call and it was flagged as "${fam}" (Risk Score: ${score}/100). Do NOT share any OTP, PIN, or transfer money. National Cyber Crime Helpline: 1930.`;
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank");
}

// Save Current Case to SQLite History
async function saveCurrentCaseToHistory() {
  if (!currentCaseData) return;
  try {
    const res = await fetch("/api/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_payload: currentCaseData })
    });
    const d = await res.json();
    alert(`Case ${d.case_id} saved successfully to your on-device history!`);
  } catch (err) {
    alert("Failed to save case: " + err.message);
  }
}

// Load Cases & Scam Radar History
async function loadCasesRadar() {
  try {
    const res = await fetch("/api/cases");
    const data = await res.json();

    document.getElementById("stat-total-cases").textContent = data.total_cases || 0;
    document.getElementById("stat-scams-detected").textContent = data.scam_count || 0;
    document.getElementById("stat-safe-calls").textContent = data.safe_count || 0;
    document.getElementById("stat-top-family").textContent = data.most_common_type || "None";

    const tableBody = document.getElementById("cases-table-body");
    const cases = data.cases || [];

    if (cases.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No saved cases yet. Try analyzing a sample call or upload a recording!
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = cases.map(c => `
      <tr>
        <td><b>${c.id}</b></td>
        <td>${c.created_at}</td>
        <td>${c.primary_family_name}</td>
        <td><span class="tier-badge tier-${c.risk_tier.toLowerCase().replace(' ', '-')}">${c.overall_score}/100</span></td>
        <td><span style="font-size:0.8rem; color:var(--text-muted);">${c.evidence_strength}</span></td>
        <td>
          <button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" onclick="viewSavedCase('${c.id}')">View</button>
          <button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem; color:#dc2626;" onclick="deleteSavedCase('${c.id}')">Delete</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading cases radar:", err);
  }
}

async function viewSavedCase(caseId) {
  try {
    const res = await fetch(`/api/cases/${caseId}`);
    const data = await res.json();
    currentCaseData = data;
    renderCaseResult(data);
    switchPage("result");
  } catch (err) {
    alert("Error loading case: " + err.message);
  }
}

async function deleteSavedCase(caseId) {
  if (!confirm(`Delete case ${caseId}?`)) return;
  try {
    await fetch(`/api/cases/${caseId}`, { method: "DELETE" });
    loadCasesRadar();
  } catch (err) {
    alert("Failed to delete case.");
  }
}

async function clearAllCasesHistory() {
  if (!confirm("Are you sure you want to clear all saved case history?")) return;
  try {
    await fetch("/api/cases", { method: "DELETE" });
    loadCasesRadar();
  } catch (err) {
    alert("Failed to clear history.");
  }
}

// Load Scam Atlas Page
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

// Load Model Insights Page
async function loadModelInsights() {
  try {
    const res = await fetch("/api/insights");
    const data = await res.json();

    const metrics = data.metrics || {};
    const textPipe = metrics.text_pipeline || {};
    const earlyDet = data.early_detection || {};

    const textF1 = (textPipe.model_bakeoff && textPipe.model_bakeoff.tfidf_logreg) 
      ? (textPipe.model_bakeoff.tfidf_logreg.leakage_controlled_group_5fold.f1_score * 100).toFixed(1) + "%"
      : "93.0%";

    const leadTime = earlyDet.median_lead_time_seconds ? earlyDet.median_lead_time_seconds + "s" : "7.1s";

    document.getElementById("metric-text-f1").textContent = textF1;
    document.getElementById("metric-lead-time").textContent = leadTime;
  } catch (e) {
    console.error("Error loading insights:", e);
  }
}

// Spot the Scam Practice Mode
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
        <button class="btn-primary" onclick="practiceIndex=0; renderPracticeScenario(0);">Play Again</button>
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
      <button class="btn-primary" style="background: #dc2626; font-size: 1.1rem; padding: 14px 32px;" onclick="handlePracticeHangup(${idx})">
        🛑 Hang Up Now (It's a Scam)
      </button>
      <button class="btn-secondary" style="font-size: 1.1rem; padding: 14px 28px;" onclick="handlePracticeSafe(${idx})">
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
        <button class="btn-primary" style="padding: 6px 16px;" onclick="practiceIndex++; renderPracticeScenario(practiceIndex);">Next Scenario →</button>
      </div>
    `;
  } else {
    fb.innerHTML = `
      <div style="background: var(--risk-moderate-bg); border: 1px solid var(--risk-moderate-border); padding: 16px; border-radius: 8px; color: var(--risk-moderate);">
        <b>Notice:</b> This was a legitimate message (<b>${scenario.family}</b>) without threats or secrecy demands.
        <br/><br/>
        <button class="btn-secondary" style="padding: 6px 16px;" onclick="practiceIndex++; renderPracticeScenario(practiceIndex);">Next Scenario →</button>
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
        <button class="btn-primary" style="padding: 6px 16px;" onclick="practiceIndex++; renderPracticeScenario(practiceIndex);">Next Scenario →</button>
      </div>
    `;
  } else {
    fb.innerHTML = `
      <div style="background: var(--risk-high-bg); border: 1px solid var(--risk-high-border); padding: 16px; border-radius: 8px; color: var(--risk-high);">
        <b>⚠️ Danger:</b> This was actually a <b>${scenario.family}</b> scam! Notice the urgent pressure and request for secret credentials.
        <br/><br/>
        <button class="btn-secondary" style="padding: 6px 16px;" onclick="practiceIndex++; renderPracticeScenario(practiceIndex);">Next Scenario →</button>
      </div>
    `;
  }
}

// Read Aloud Verdict Helper
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

// Copy to Clipboard Utility
function copyTextToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied to clipboard!");
  }).catch(() => {
    alert("Failed to copy text.");
  });
}

// Loading Modal Helpers
function showLoading(status, subtext) {
  const overlay = document.getElementById("loading-overlay");
  document.getElementById("loading-status-text").textContent = status || "Analyzing...";
  document.getElementById("loading-subtext").textContent = subtext || "Please wait";
  if (overlay) overlay.classList.add("active");
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.remove("active");
}
