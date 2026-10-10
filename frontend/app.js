/**
 * SentiCall — The Third Voice Frontend Application
 * Designed with warmth, empathy, and crystal-clear non-technical UX.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const tabAudioBtn = document.getElementById('tabAudioBtn');
  const tabTextBtn = document.getElementById('tabTextBtn');
  const tabAudioContent = document.getElementById('tabAudioContent');
  const tabTextContent = document.getElementById('tabTextContent');

  const dropzone = document.getElementById('dropzone');
  const audioFileInput = document.getElementById('audioFileInput');
  const selectedFileBadge = document.getElementById('selectedFileBadge');
  const selectedFileName = document.getElementById('selectedFileName');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const audioPlayerWrapper = document.getElementById('audioPlayerWrapper');
  const audioPreviewPlayer = document.getElementById('audioPreviewPlayer');
  const analyzeAudioBtn = document.getElementById('analyzeAudioBtn');
  const browseSamplesBtn = document.getElementById('browseSamplesBtn');

  const transcriptTextInput = document.getElementById('transcriptTextInput');
  const charCount = document.getElementById('charCount');
  const clearTextBtn = document.getElementById('clearTextBtn');
  const analyzeTextBtn = document.getElementById('analyzeTextBtn');
  const quickSampleChips = document.querySelectorAll('.quick-sample-chip');

  const loadingSection = document.getElementById('loadingSection');
  const loadingTitle = document.getElementById('loadingTitle');
  const loadingSubtitle = document.getElementById('loadingSubtitle');
  const stepItems = [
    document.getElementById('step1'),
    document.getElementById('step2'),
    document.getElementById('step3'),
    document.getElementById('step4')
  ];

  const resultsSection = document.getElementById('resultsSection');
  const gaugeCircle = document.getElementById('gaugeCircle');
  const gaugeScore = document.getElementById('gaugeScore');
  const riskBadge = document.getElementById('riskBadge');
  const verdictHeading = document.getElementById('verdictHeading');
  const summarySentence = document.getElementById('summarySentence');
  const sourceTag = document.getElementById('sourceTag');
  const timestampTag = document.getElementById('timestampTag');

  const transcriptDisplayBox = document.getElementById('transcriptDisplayBox');
  const tacticsList = document.getElementById('tacticsList');
  const voiceChannelScore = document.getElementById('voiceChannelScore');
  const voiceSignalsList = document.getElementById('voiceSignalsList');
  const textChannelScore = document.getElementById('textChannelScore');
  const textSignalsList = document.getElementById('textSignalsList');

  const helplineTag = document.getElementById('helplineTag');
  const helplineHeading = document.getElementById('helplineHeading');
  const helplineTipsList = document.getElementById('helplineTipsList');
  const restartAnalysisBtn = document.getElementById('restartAnalysisBtn');

  const sampleCardsGrid = document.getElementById('sampleCardsGrid');
  const ethicsModal = document.getElementById('ethicsModal');
  const openEthicsModalBtn = document.getElementById('openEthicsModalBtn');
  const closeEthicsModalBtn = document.getElementById('closeEthicsModalBtn');

  let selectedAudioFile = null;
  let selectedSampleAudioFilename = null;

  // --------------------------------------------------------------------------
  // 1. Tab Switching
  // --------------------------------------------------------------------------
  tabAudioBtn.addEventListener('click', () => switchTab('audio'));
  tabTextBtn.addEventListener('click', () => switchTab('text'));

  function switchTab(tab) {
    if (tab === 'audio') {
      tabAudioBtn.classList.add('active');
      tabTextBtn.classList.remove('active');
      tabAudioContent.style.display = 'block';
      tabTextContent.style.display = 'none';
    } else {
      tabTextBtn.classList.add('active');
      tabAudioBtn.classList.remove('active');
      tabTextContent.style.display = 'block';
      tabAudioContent.style.display = 'none';
    }
  }

  // --------------------------------------------------------------------------
  // 2. Audio Drag & Drop and File Selection
  // --------------------------------------------------------------------------
  dropzone.addEventListener('click', () => audioFileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAudioFileSelected(e.dataTransfer.files[0]);
    }
  });

  audioFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleAudioFileSelected(e.target.files[0]);
    }
  });

  function handleAudioFileSelected(file) {
    selectedAudioFile = file;
    selectedSampleAudioFilename = null;
    selectedFileName.textContent = file.name;
    selectedFileBadge.style.display = 'inline-flex';
    analyzeAudioBtn.disabled = false;

    // Load into preview player
    const objectUrl = URL.createObjectURL(file);
    audioPreviewPlayer.src = objectUrl;
    audioPlayerWrapper.style.display = 'block';
  }

  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    clearAudioSelection();
  });

  function clearAudioSelection() {
    selectedAudioFile = null;
    selectedSampleAudioFilename = null;
    audioFileInput.value = '';
    selectedFileBadge.style.display = 'none';
    audioPlayerWrapper.style.display = 'none';
    audioPreviewPlayer.pause();
    audioPreviewPlayer.src = '';
    analyzeAudioBtn.disabled = true;
  }

  browseSamplesBtn.addEventListener('click', () => {
    const samplesSec = document.getElementById('samples-section');
    if (samplesSec) {
      samplesSec.scrollIntoView({ behavior: 'smooth' });
    }
  });

  // --------------------------------------------------------------------------
  // 3. Text Input & Quick Chips
  // --------------------------------------------------------------------------
  transcriptTextInput.addEventListener('input', () => {
    const text = transcriptTextInput.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    charCount.textContent = `${words} word${words === 1 ? '' : 's'}`;
  });

  clearTextBtn.addEventListener('click', () => {
    transcriptTextInput.value = '';
    charCount.textContent = '0 words';
  });

  quickSampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const sampleText = chip.getAttribute('data-sample-text');
      transcriptTextInput.value = sampleText;
      const words = sampleText.split(/\s+/).length;
      charCount.textContent = `${words} words`;
      // Smooth scroll to analyze text button
      analyzeTextBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  });

  // --------------------------------------------------------------------------
  // 4. Analysis Execution Handlers
  // --------------------------------------------------------------------------
  analyzeAudioBtn.addEventListener('click', async () => {
    if (!selectedAudioFile && !selectedSampleAudioFilename) return;

    showLoadingState('audio');

    const formData = new FormData();
    if (selectedAudioFile) {
      formData.append('audio_file', selectedAudioFile);
    } else if (selectedSampleAudioFilename) {
      formData.append('sample_filename', selectedSampleAudioFilename);
    }

    try {
      const response = await fetch('/api/analyze-audio', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Analysis request failed');
      }

      const data = await response.json();
      setTimeout(() => {
        hideLoadingState();
        renderResults(data);
      }, 1200); // Friendly pacing so steps are seen

    } catch (error) {
      hideLoadingState();
      alert('Could not analyze the audio call: ' + error.message);
    }
  });

  analyzeTextBtn.addEventListener('click', async () => {
    const text = transcriptTextInput.value.trim();
    if (!text) {
      alert('Please enter or paste a call transcript first.');
      return;
    }

    showLoadingState('text');

    try {
      const response = await fetch('/api/analyze-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Analysis request failed');
      }

      const data = await response.json();
      setTimeout(() => {
        hideLoadingState();
        renderResults(data);
      }, 1000);

    } catch (error) {
      hideLoadingState();
      alert('Could not analyze the transcript: ' + error.message);
    }
  });

  // --------------------------------------------------------------------------
  // 5. Friendly Step-by-Step Loading State Orchestration
  // --------------------------------------------------------------------------
  let stepTimer = null;

  function showLoadingState(mode) {
    document.getElementById('analyze-section').style.display = 'none';
    resultsSection.style.display = 'none';
    loadingSection.style.display = 'block';
    loadingSection.scrollIntoView({ behavior: 'smooth', block: 'center' });

    stepItems.forEach(item => {
      item.className = 'step-item';
    });

    if (mode === 'audio') {
      loadingTitle.textContent = "Listening to the call...";
      loadingSubtitle.textContent = "Our AI is listening to voice cadence and checking conversational manipulation patterns.";
      
      stepItems[0].classList.add('active');
      stepTimer = setTimeout(() => {
        stepItems[0].className = 'step-item completed';
        stepItems[1].className = 'step-item active';
        loadingTitle.textContent = "Transcribing spoken words...";
      }, 700);

      setTimeout(() => {
        stepItems[1].className = 'step-item completed';
        stepItems[2].className = 'step-item active';
        loadingTitle.textContent = "Checking for pressure tactics...";
      }, 1400);

      setTimeout(() => {
        stepItems[2].className = 'step-item completed';
        stepItems[3].className = 'step-item active';
        loadingTitle.textContent = "Preparing your safety verdict...";
      }, 2100);

    } else {
      loadingTitle.textContent = "Reading the transcript...";
      loadingSubtitle.textContent = "Analyzing vocabulary, urgency indicators, and deception patterns.";
      
      stepItems[0].style.display = 'none';
      stepItems[1].className = 'step-item active';
      stepItems[1].querySelector('.step-text').textContent = "Processing transcript phrasing";

      stepTimer = setTimeout(() => {
        stepItems[1].className = 'step-item completed';
        stepItems[2].className = 'step-item active';
        loadingTitle.textContent = "Checking for manipulation patterns...";
      }, 600);

      setTimeout(() => {
        stepItems[2].className = 'step-item completed';
        stepItems[3].className = 'step-item active';
        loadingTitle.textContent = "Generating plain-language explanation...";
      }, 1200);
    }
  }

  function hideLoadingState() {
    clearTimeout(stepTimer);
    loadingSection.style.display = 'none';
  }

  // --------------------------------------------------------------------------
  // 6. Result Screen Centerpiece Rendering
  // --------------------------------------------------------------------------
  function renderResults(data) {
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    const fusion = data.fusion;
    const score = fusion.overall_score; // 0 to 100
    const riskTier = fusion.risk_tier; // Low Risk, Moderate Risk, High Risk

    // 1. Animated Score Gauge
    animateGauge(score, fusion.risk_theme_color);
    gaugeScore.textContent = score;

    // 2. Risk Badge & Verdict Heading
    riskBadge.textContent = riskTier;
    riskBadge.className = `risk-badge ${fusion.risk_badge_class}`;
    verdictHeading.textContent = fusion.verdict_heading;
    summarySentence.textContent = fusion.summary_sentence;

    sourceTag.textContent = data.input_type === 'audio' 
      ? `Analyzed Audio: ${data.source_name || 'Call Recording'}`
      : 'Analyzed Text Transcript';
    timestampTag.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // 3. Highlighted Transcript View
    const textRes = data.text_result;
    if (textRes && textRes.highlighted_html) {
      transcriptDisplayBox.innerHTML = textRes.highlighted_html;
    } else if (data.transcript) {
      transcriptDisplayBox.textContent = data.transcript;
    } else {
      transcriptDisplayBox.innerHTML = '<em style="color: var(--text-subtle);">No conversational transcript was generated for this recording.</em>';
    }

    // 4. Manipulation Tactics Breakdown Cards
    renderTacticsList(textRes ? textRes.tactic_breakdown : []);

    // 5. Dual Channel Evidence
    const audioRes = data.audio_result;
    if (audioRes && audioRes.success) {
      voiceChannelScore.textContent = `Acoustic Risk: ${audioRes.audio_risk_score}%`;
      voiceSignalsList.innerHTML = audioRes.signals.map(s => `<li>${escapeHtml(s)}</li>`).join('');
    } else {
      voiceChannelScore.textContent = 'Acoustic Analysis: N/A';
      voiceSignalsList.innerHTML = `<li>Text transcript submitted (audio channel not applicable).</li>`;
    }

    if (textRes && textRes.success) {
      textChannelScore.textContent = `Language Risk: ${textRes.text_risk_score}%`;
      textSignalsList.innerHTML = textRes.linguistic_signals.map(s => `<li>${escapeHtml(s)}</li>`).join('');
    } else {
      textChannelScore.textContent = 'Language Risk: --';
      textSignalsList.innerHTML = `<li>Audio recording contained no clear verbal conversation.</li>`;
    }

    // 6. Helpline Guidance Card
    const nextSteps = fusion.next_steps;
    helplineTag.textContent = nextSteps.badge;
    helplineHeading.textContent = nextSteps.headline;
    helplineTipsList.innerHTML = nextSteps.tips.map(tip => `<li>${escapeHtml(tip)}</li>`).join('');
  }

  function animateGauge(score, color) {
    const radius = 50;
    const circumference = 2 * Math.PI * radius; // ~314.15
    const offset = circumference - (score / 100) * circumference;
    gaugeCircle.style.stroke = color;
    gaugeCircle.style.strokeDashoffset = offset;
  }

  function renderTacticsList(tactics) {
    if (!tactics || tactics.length === 0) {
      tacticsList.innerHTML = '<p class="text-muted" style="font-size: 0.9rem;">No tactic indicators detected.</p>';
      return;
    }

    tacticsList.innerHTML = tactics.map(t => {
      const isDetected = t.detected;
      const cardClass = isDetected ? 'tactic-card detected' : 'tactic-card';
      const statusTag = isDetected 
        ? '<span class="tactic-status-tag tag-detected">Detected</span>'
        : '<span class="tactic-status-tag tag-clear">Clear</span>';

      const meterFillClass = t.confidence >= 70 ? 'fill-high' : (t.confidence >= 40 ? 'fill-mod' : '');
      const matchedPills = (t.matched_phrases && t.matched_phrases.length > 0)
        ? `<div class="tactic-matched-pills">${t.matched_phrases.map(p => `<span class="matched-pill">"${escapeHtml(p)}"</span>`).join('')}</div>`
        : '';

      return `
        <div class="${cardClass}">
          <div class="tactic-top-row">
            <span class="tactic-name">${escapeHtml(t.title)}</span>
            ${statusTag}
          </div>
          <p class="tactic-desc">${escapeHtml(t.description)}</p>
          <div class="tactic-meter-bar">
            <div class="tactic-meter-fill ${meterFillClass}" style="width: ${t.confidence}%"></div>
          </div>
          ${matchedPills}
        </div>
      `;
    }).join('');
  }

  restartAnalysisBtn.addEventListener('click', () => {
    resultsSection.style.display = 'none';
    document.getElementById('analyze-section').style.display = 'block';
    document.getElementById('analyze-section').scrollIntoView({ behavior: 'smooth' });
  });

  // --------------------------------------------------------------------------
  // 7. Load Built-In Samples Library
  // --------------------------------------------------------------------------
  async function loadSamples() {
    try {
      const res = await fetch('/api/samples');
      if (!res.ok) return;
      const data = await res.json();

      let cardsHtml = '';

      // Audio Samples
      data.audio_samples.forEach(sample => {
        const badgeClass = sample.type === 'scam' ? 'sample-badge-scam' : 'sample-badge-normal';
        cardsHtml += `
          <div class="sample-item-card" data-sample-type="audio" data-filename="${escapeHtml(sample.filename)}">
            <div>
              <span class="sample-card-badge ${badgeClass}">${escapeHtml(sample.badge)}</span>
              <h4 class="sample-item-title">${escapeHtml(sample.title)}</h4>
              <p class="sample-item-desc">${escapeHtml(sample.description)}</p>
            </div>
            <div class="sample-action-row">
              <span class="sample-type-label">Audio Call</span>
              <span class="sample-test-btn">Test Sample &rarr;</span>
            </div>
          </div>
        `;
      });

      // Text Samples
      data.text_samples.forEach(sample => {
        const badgeClass = sample.type === 'scam' ? 'sample-badge-scam' : 'sample-badge-normal';
        cardsHtml += `
          <div class="sample-item-card" data-sample-type="text" data-text="${escapeHtml(sample.text)}">
            <div>
              <span class="sample-card-badge ${badgeClass}">${escapeHtml(sample.badge)}</span>
              <h4 class="sample-item-title">${escapeHtml(sample.title)}</h4>
              <p class="sample-item-desc">${escapeHtml(sample.description)}</p>
            </div>
            <div class="sample-action-row">
              <span class="sample-type-label">Transcript</span>
              <span class="sample-test-btn">Test Sample &rarr;</span>
            </div>
          </div>
        `;
      });

      sampleCardsGrid.innerHTML = cardsHtml;

      // Attach click listeners to sample cards
      document.querySelectorAll('.sample-item-card').forEach(card => {
        card.addEventListener('click', () => {
          const type = card.getAttribute('data-sample-type');
          if (type === 'audio') {
            const filename = card.getAttribute('data-filename');
            selectedSampleAudioFilename = filename;
            selectedAudioFile = null;
            selectedFileName.textContent = filename;
            selectedFileBadge.style.display = 'inline-flex';
            analyzeAudioBtn.disabled = false;

            // Load audio preview from endpoint
            audioPreviewPlayer.src = `/api/audio/${filename}`;
            audioPlayerWrapper.style.display = 'block';

            switchTab('audio');
            // Auto trigger analysis
            analyzeAudioBtn.click();

          } else {
            const sampleText = card.getAttribute('data-text');
            transcriptTextInput.value = sampleText;
            const words = sampleText.split(/\s+/).length;
            charCount.textContent = `${words} words`;

            switchTab('text');
            // Auto trigger text analysis
            analyzeTextBtn.click();
          }
        });
      });

    } catch (e) {
      console.log('Error loading sample calls:', e);
    }
  }

  loadSamples();

  // --------------------------------------------------------------------------
  // 8. Ethics & Real Metrics Modal
  // --------------------------------------------------------------------------
  openEthicsModalBtn.addEventListener('click', async () => {
    ethicsModal.style.display = 'flex';
    try {
      const res = await fetch('/api/metrics');
      if (res.ok) {
        const metrics = await res.json();
        if (metrics.text_pipeline) {
          document.getElementById('textCvAcc').textContent = (metrics.text_pipeline.accuracy * 100).toFixed(2) + '%';
          document.getElementById('textCvPrec').textContent = (metrics.text_pipeline.precision * 100).toFixed(2) + '%';
          document.getElementById('textCvRec').textContent = (metrics.text_pipeline.recall * 100).toFixed(2) + '%';
          document.getElementById('textCvF1').textContent = (metrics.text_pipeline.f1 * 100).toFixed(2) + '%';
          document.getElementById('textCvRoc').textContent = metrics.text_pipeline.roc_auc.toFixed(4);
        }
        if (metrics.audio_pipeline) {
          document.getElementById('audioCvAcc').textContent = (metrics.audio_pipeline.accuracy * 100).toFixed(2) + '%';
          document.getElementById('audioCvPrec').textContent = (metrics.audio_pipeline.precision * 100).toFixed(2) + '%';
          document.getElementById('audioCvRec').textContent = (metrics.audio_pipeline.recall * 100).toFixed(2) + '%';
          document.getElementById('audioCvF1').textContent = (metrics.audio_pipeline.f1 * 100).toFixed(2) + '%';
        }
      }
    } catch (e) {
      console.log('Metrics fetch notice:', e);
    }
  });

  closeEthicsModalBtn.addEventListener('click', () => {
    ethicsModal.style.display = 'none';
  });

  ethicsModal.addEventListener('click', (e) => {
    if (e.target === ethicsModal) {
      ethicsModal.style.display = 'none';
    }
  });

  function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;')
               .replace(/"/g, '&quot;')
               .replace(/'/g, '&#39;');
  }
});
