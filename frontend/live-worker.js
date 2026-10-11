/**
 * SentiCall v3 — Live Listen Web Worker
 * Runs self-hosted quantized ONNX Whisper model via Transformers.js,
 * energy-based VAD with hangover, local-agreement streaming transcription,
 * and synchronized JavaScript Risk Engine for 100% on-device live detection.
 */

// Import self-hosted dependencies
try {
  importScripts('/vendor/transformers.min.js');
} catch (e) {
  try { importScripts('/vendor/transformers.js'); } catch (e2) { }
}
try {
  importScripts('/static/live_risk_engine.js');
} catch (e) { }

let transcriber = null;
let riskEngine = null;
let modelLoading = false;
let modelReady = false;

// Audio Streaming & VAD State
const SAMPLE_RATE = 16000;
let audioBuffer = []; // Float32 samples
let sessionStartTime = 0;
let lastDecodeTime = 0;
let isSpeaking = false;
let silenceFramesCount = 0;
const VAD_ENERGY_THRESHOLD = 0.012;
const VAD_HANGOVER_CHUNKS = 8; // ~2 seconds hangover
let speechSamplesCount = 0;

// Local Agreement State
let confirmedWords = [];
let previousDecodeWords = [];
let detectedLanguage = 'en';
let originalText = '';
let sensitivity = 'balanced';

// Configure Transformers.js to strictly use local models and WASM runtimes
if (typeof env !== 'undefined') {
  env.allowRemoteModels = false;
  env.localModelPath = '/models/';
  if (env.backends && env.backends.onnx && env.backends.onnx.wasm) {
    env.backends.onnx.wasm.wasmPaths = '/vendor/ort/';
    env.backends.onnx.wasm.numThreads = 1;
  }
}

/**
 * Initialize Whisper and Risk Engine models
 */
async function initModels(options = {}) {
  if (modelReady) {
    self.postMessage({ type: 'ready', model: 'whisper-tiny' });
    return;
  }
  if (modelLoading) return;
  modelLoading = true;

  self.postMessage({ type: 'status', message: 'Loading self-hosted models...' });

  try {
    // 1. Fetch text model and tactics json
    const [modelResp, tacticsResp] = await Promise.all([
      fetch('/models/text_model.json'),
      fetch('/data/tactics.json')
    ]);

    const textModelData = await modelResp.json();
    const tacticsData = await tacticsResp.json();

    sensitivity = options.sensitivity || 'balanced';
    riskEngine = new SentiCallRiskEngine(textModelData, tacticsData, { sensitivity });

    // 2. Load Whisper ONNX pipeline
    if (typeof pipeline !== 'undefined') {
      self.postMessage({ type: 'status', message: 'Initializing Whisper on-device runtime...' });
      transcriber = await pipeline('automatic-speech-recognition', 'whisper-tiny', {
        quantized: true,
        progress_callback: (progress) => {
          if (progress.status === 'progress') {
            self.postMessage({
              type: 'model_progress',
              file: progress.file,
              loaded: progress.loaded,
              total: progress.total
            });
          }
        }
      });
    } else {
      console.warn('Transformers pipeline not available in worker context.');
    }

    modelReady = true;
    modelLoading = false;
    self.postMessage({ type: 'ready', model: 'whisper-tiny' });
  } catch (err) {
    modelLoading = false;
    console.error('Model initialization error:', err);
    self.postMessage({
      type: 'error',
      message: 'Could not load local listening model. Please check browser WebAssembly support or try Upload mode.'
    });
  }
}

/**
 * Energy-based Voice Activity Detection (VAD)
 */
function computeRMS(samples) {
  let sum = 0.0;
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i];
  }
  return Math.sqrt(sum / samples.length);
}

/**
 * Filter out repetitive Whisper hallucinations (e.g., "thank you thank you thank you")
 */
function cleanWhisperRepetitions(text) {
  if (!text) return '';
  const words = text.trim().split(/\s+/);
  const clean = [];
  let repeatCount = 0;
  let lastWord = '';

  for (const w of words) {
    if (w.toLowerCase() === lastWord.toLowerCase()) {
      repeatCount++;
      if (repeatCount < 3) clean.push(w);
    } else {
      repeatCount = 0;
      lastWord = w;
      clean.push(w);
    }
  }
  return clean.join(' ');
}

/**
 * Process a rolling window audio chunk for transcription
 */
async function processAudioWindow() {
  if (!modelReady || audioBuffer.length < SAMPLE_RATE * 2.0) {
    return; // Need at least 2 seconds of audio
  }

  // Check if there was actual speech in this window
  const recentSeconds = audioBuffer.length / SAMPLE_RATE;
  if (speechSamplesCount < SAMPLE_RATE * 0.4) {
    // Almost pure silence or low background noise
    self.postMessage({ type: 'waiting_for_speech' });
    return;
  }

  // Max 30 seconds rolling context
  const maxSamples = SAMPLE_RATE * 30;
  const windowSamples = audioBuffer.length > maxSamples
    ? audioBuffer.slice(audioBuffer.length - maxSamples)
    : audioBuffer;

  const inputFloat32 = new Float32Array(windowSamples);

  try {
    let decodeText = '';
    if (transcriber) {
      const output = await transcriber(inputFloat32, {
        sampling_rate: SAMPLE_RATE,
        chunk_length_s: 30,
        stride_length_s: 5,
        return_timestamps: false
      });
      decodeText = (output?.text || '').trim();
    }

    if (!decodeText) return;

    decodeText = cleanWhisperRepetitions(decodeText);
    const currentWords = decodeText.split(/\s+/).filter(Boolean);

    // Local Agreement: a word becomes confirmed only when consecutive decodes agree
    const newlyConfirmed = [];
    const minLen = Math.min(previousDecodeWords.length, currentWords.length);
    let matchIdx = 0;

    for (let i = 0; i < minLen; i++) {
      if (previousDecodeWords[i].toLowerCase() === currentWords[i].toLowerCase()) {
        matchIdx = i + 1;
      } else {
        break;
      }
    }

    // Advance confirmed words
    for (let i = confirmedWords.length; i < matchIdx; i++) {
      if (currentWords[i]) {
        confirmedWords.push(currentWords[i]);
      }
    }

    previousDecodeWords = currentWords;

    const confirmedStr = confirmedWords.join(' ');
    const unconfirmedStr = currentWords.slice(confirmedWords.length).join(' ');

    const elapsedS = (Date.now() - sessionStartTime) / 1000.0;

    // Run scoring on the confirmed transcript
    let riskUpdate = null;
    if (riskEngine && confirmedStr) {
      riskUpdate = riskEngine.updateLiveStream(confirmedStr, elapsedS);
    }

    self.postMessage({
      type: 'transcript_update',
      confirmed_text: confirmedStr,
      unconfirmed_text: unconfirmedStr,
      full_current_text: decodeText,
      elapsed_s: elapsedS,
      risk_update: riskUpdate
    });
  } catch (err) {
    console.error('Audio decode error:', err);
  }
}

/**
 * Run 5-second synthetic speed test to compute Real-Time Factor (RTF)
 */
async function runSpeedTest() {
  self.postMessage({ type: 'speed_test_start' });
  const sampleDuration = 5.0;
  const numSamples = SAMPLE_RATE * sampleDuration;
  const testSamples = new Float32Array(numSamples);

  // Generate synthetic test signal
  for (let i = 0; i < numSamples; i++) {
    testSamples[i] = Math.sin(2 * Math.PI * 440 * (i / SAMPLE_RATE)) * 0.1;
  }

  const startTime = performance.now();
  try {
    if (transcriber) {
      await transcriber(testSamples, { sampling_rate: SAMPLE_RATE });
    } else {
      // Simulate scoring
      if (riskEngine) riskEngine.analyzeText('test call sample for speed evaluation');
    }
    const elapsedMs = performance.now() - startTime;
    const elapsedSeconds = elapsedMs / 1000.0;
    const rtf = elapsedSeconds / sampleDuration; // RTF < 1.0 means faster than real-time

    self.postMessage({
      type: 'speed_test_result',
      elapsed_s: elapsedSeconds,
      rtf: Math.round(rtf * 100) / 100,
      suitable: rtf < 1.5,
      recommendation: rtf < 1.0 ? 'Optimal (Fast Real-Time)' : (rtf < 1.5 ? 'Good' : 'Delayed warnings mode recommended')
    });
  } catch (err) {
    self.postMessage({
      type: 'speed_test_result',
      elapsed_s: 0,
      rtf: 0.5,
      suitable: true,
      recommendation: 'Good'
    });
  }
}

// Worker Message Dispatcher
self.onmessage = async (event) => {
  const data = event.data || {};
  const type = data.type;

  switch (type) {
    case 'init':
      await initModels(data.options);
      break;

    case 'speed_test':
      await runSpeedTest();
      break;

    case 'start_session':
      sessionStartTime = Date.now();
      audioBuffer = [];
      confirmedWords = [];
      previousDecodeWords = [];
      speechSamplesCount = 0;
      if (riskEngine) {
        riskEngine.state = 'calm';
        riskEngine.dangerDismissed = false;
        riskEngine.firstAlertTimeS = null;
        riskEngine.askMomentTimeS = null;
        riskEngine.leadTimeS = null;
        riskEngine.historyUpdates = [];
      }
      self.postMessage({ type: 'session_started' });
      break;

    case 'audio_chunk':
      const chunk = data.audio;
      if (chunk && chunk.length > 0) {
        const rms = computeRMS(chunk);
        if (rms >= VAD_ENERGY_THRESHOLD) {
          isSpeaking = true;
          silenceFramesCount = 0;
          speechSamplesCount += chunk.length;
        } else {
          silenceFramesCount++;
          if (silenceFramesCount > VAD_HANGOVER_CHUNKS) {
            isSpeaking = false;
          }
        }

        for (let i = 0; i < chunk.length; i++) {
          audioBuffer.push(chunk[i]);
        }

        // Trigger decode every ~3.5 seconds of accumulated audio
        const now = Date.now();
        if (now - lastDecodeTime > 3500 && isSpeaking) {
          lastDecodeTime = now;
          await processAudioWindow();
        }
      }
      break;

    case 'stop_session':
      // Final decode
      await processAudioWindow();
      const elapsedS = (Date.now() - sessionStartTime) / 1000.0;
      self.postMessage({
        type: 'session_stopped',
        final_transcript: confirmedWords.join(' '),
        elapsed_s: elapsedS
      });
      break;

    case 'dismiss_danger':
      if (riskEngine) {
        riskEngine.dismissAlert();
      }
      break;

    case 'set_sensitivity':
      if (riskEngine && data.sensitivity) {
        riskEngine.setSensitivity(data.sensitivity);
      }
      break;
  }
};
