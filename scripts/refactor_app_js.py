import re

with open("frontend/app.js", "r", encoding="utf-8") as f:
    js = f.read()

# 1. Update loadSamples dynamic HTML
js = js.replace(
    '''<div class="sample-card" onclick="runSampleCall('${s.filename}', '${s.title}')">''',
    '''<div class="sample-card" data-action="runSampleCall" data-filename="${s.filename}" data-title="${s.title}">'''
)
js = js.replace(
    '''<div class="sample-actions" onclick="event.stopPropagation();">''',
    '''<div class="sample-actions">'''
)
js = js.replace(
    '''<button class="btn-preview-play" onclick="playAudioPreview('/api/audio/${s.filename}')">''',
    '''<button class="btn-preview-play" data-action="playAudioPreview" data-url="/api/audio/${s.filename}">'''
)
js = js.replace(
    '''<button class="btn-run-sample" onclick="runSampleCall('${s.filename}', '${s.title}')">''',
    '''<button class="btn-run-sample" data-action="runSampleCall" data-filename="${s.filename}" data-title="${s.title}">'''
)

# 2. Update timeline markers dynamic HTML
js = js.replace(
    '''<div class="timeline-marker-chip ${isFirstAlert ? 'marker-first-alert' : ''}" onclick="jumpAudioToSecond(${m.time_s})">''',
    '''<div class="timeline-marker-chip ${isFirstAlert ? 'marker-first-alert' : ''}" data-action="jumpAudioToSecond" data-second="${m.time_s}">'''
)

# 3. Update cases radar dynamic HTML
js = js.replace(
    '''<button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" onclick="viewSavedCase('${c.id}')">View</button>''',
    '''<button class="btn-secondary" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" data-action="viewSavedCase" data-id="${c.id}">View</button>'''
)
js = js.replace(
    '''<button class="btn-secondary text-danger" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" onclick="deleteSavedCase('${c.id}')">Delete</button>''',
    '''<button class="btn-secondary text-danger" style="min-height:28px; padding:2px 8px; font-size:0.75rem;" data-action="deleteSavedCase" data-id="${c.id}">Delete</button>'''
)

# 4. Update practice scenarios dynamic HTML
js = js.replace(
    '''onclick="practiceIndex=0; renderPracticeScenario(0);"''',
    '''data-action="practiceRestart"'''
)
js = js.replace(
    '''onclick="handlePracticeHangup(${idx})"''',
    '''data-action="practiceHangup" data-idx="${idx}"'''
)
js = js.replace(
    '''onclick="handlePracticeSafe(${idx})"''',
    '''data-action="practiceSafe" data-idx="${idx}"'''
)
js = js.replace(
    '''onclick="practiceIndex++; renderPracticeScenario(practiceIndex);"''',
    '''data-action="practiceNext"'''
)

# 5. Add Service Worker registration inside DOMContentLoaded
sw_code = """
  // Register Service Worker for offline model/WASM caching
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').then(() => {
      console.log('SentiCall Service Worker registered successfully.');
    }).catch(err => {
      console.warn('Service Worker registration skipped:', err);
    });
  }
"""
js = js.replace(
    "  // Update dynamic privacy statement for default page\n  updatePrivacyStripForPage('analyze');",
    "  // Update dynamic privacy statement for default page\n  updatePrivacyStripForPage('analyze');\n" + sw_code
)

# 6. Append the centralized event delegator
delegator_code = """

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
  }
});
"""

js += delegator_code

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(js)

print("Updated frontend/app.js with delegator and CSP-compliant templates.")
