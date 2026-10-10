# SentiCall v2 — "The Third Voice"
> **AI-Powered On-Device Web Platform Against Voice Fraud & Vishing Tactics**  
> *B.Tech Final Project & Research-Grade Multimodal Audio-Linguistic Detection Engine*

---

## 🌟 Overview & Product Mission

**SentiCall v2 ("The Third Voice")** is a research-grade, privacy-first AI platform built to detect, explain, and mitigate voice phishing (vishing) and financial social engineering over phone calls. 

Unlike conventional tools that output opaque scores or generic advice, SentiCall v2 acts as an empathetic digital ally ("the third voice in the room"):
1. **Detects manipulation tactics in real time** (authority impersonation, urgency/threats, OTP demands, digital arrest, screen-share traps).
2. **Visualizes the Call Story Timeline** with audio waveforms and milestone alert markers ("You should hang up here").
3. **Provides dynamic, personalized "Do This Now" action plans** that adapt instantly based on victim state chips ("Shared an OTP", "Sent money", "Installed an app").
4. **Generates complaint-ready PDF case reports** for law enforcement ([cybercrime.gov.in](https://cybercrime.gov.in) / 1930 / Chakshu).
5. **Ensures 100% on-device privacy**: audio and transcripts never leave the local machine.

---

## 🚀 Key Product Features (P0, P1, P2)

### 1. Call Story Timeline [P0]
- Interactive audio waveform (Canvas / WaveSurfer) with risk trajectory color grading (**Green → Amber → Red**).
- Milestone markers: *"Claims official authority"*, *"Creates false urgency"*, *"Asks for secret OTP"*.
- Prominent **"You should hang up here"** marker at the first-alert second.
- Clickable markers jump audio playback directly to that sentence.

### 2. Live Replay Mode [P0]
- Replays calls chronologically with an ascending risk meter.
- Slides in an emergency alert banner at the first-alert second: *"Likely scam. Don't share anything."*
- Displays computed lead-time notice: *"SentiCall warned you 14.5 seconds before the OTP request."*

### 3. Personalized Action Plan & Victim State Chips [P0]
- Top 3 **"Do This Now"** immediate steps with one-tap `tel:` and reporting portal links.
- Interactive **"What did you already do?"** chips (*Just listened*, *Shared OTP/PIN*, *Shared Aadhaar*, *Sent money*, *Installed app/screen share*, *Clicked link*). Selecting chips dynamically injects tailored emergency countermeasures.
- Ready-to-read safe conversational replies and collapsible extended guidance.

### 4. Downloadable PDF Case Report [P0]
- One-click server-side PDF generation powered by **ReportLab + Matplotlib**.
- Includes circular risk gauge, timeline chart, tactic breakdown table, highlighted transcript, voice fingerprint, personalized action steps, verified emergency helplines, and a **"Complaint-Ready Summary"** for official filing.

### 5. "Why We Think So" & Highlighted Transcript [P0]
- 3-tier explanation:
  1. Word-level risk shading based on calibrated linear coefficients.
  2. Plain-language tactic cards with exact extracted quotation snippets.
  3. Evidence strength badges (*"Learned from 600+ real examples"* vs *"Based on warning-sign rules"*).

### 6. Voice Fingerprint [P1]
- Four plain-language acoustic meters derived from telephone-profile audio features:
  - *Speaking Rhythm & Cadence* (Speech rate WPM)
  - *Vocal Tension & Pitch Range* (F0 variation)
  - *Urgency & Pausing* (Silence ratio & uninterrupted talk stretches)
  - *Background Line Quality* (Noise floor & spectral contrast)

### 7. Scam Atlas & Playbook [P1]
- Visual directory of **12 distinct scam families** (Bank KYC, Telecom SIM cutoff, Digital Arrest, Remote Access, Prize/Lottery, Courier/Customs, Loan/Job Advance, etc.).
- Includes harm categorization, 3-step mechanics, red-flag phrases, and prevention rules.

### 8. My Cases & Scam Radar [P1]
- 100% on-device local **SQLite (`data/cases.db`)** database for saved analyses.
- Interactive radar dashboard tracking total calls checked, fraud ratio, top scam families, and risk trends.

### 9. Practice Mode: "Spot the Scam" [P2]
- Interactive game with 6 real scenario clips.
- Users listen and tap **"Hang up now"** when they detect manipulation, scoring their reaction time against SentiCall's AI alert.

### 10. Model Insights & Transparent Evaluation [P0]
- Full audit disclosure:
  - Text near-duplicate template clustering to prevent train/test leakage.
  - Telephony-profile normalization (`16 kHz`, `300–3400 Hz` bandpass) addressing recording biases.
  - Zero fabricated numbers: all charts and tables trace to `reports/metrics.json`.

---

## 📊 Evaluation & Machine Learning Metrics

All metrics are machine-evaluated and logged in `reports/metrics.json`:

| Pipeline / Channel | Metric | Value | Validation Method |
| :--- | :--- | :--- | :--- |
| **Text Linguistic Model** | **F1-Score** | **93.00% (±1.4%)** | 5-Fold Leakage-Controlled `GroupKFold` |
| | **PR-AUC** | **0.9686** | Template-grouped evaluation |
| | **ROC-AUC** | **0.9902** | Platt-calibrated probabilities |
| | **Out-of-Domain Accuracy** | **97.87%** | Evaluated on real Whisper audio transcripts |
| | **Hard Negative Robustness** | **100% Specificity** | 30 synthetic genuine delivery/doctor notices |
| **Audio Acoustic Model** | **Accuracy** | **89.87% (±5.9%)** | Telephony-Normalized XGBoost (Grouped CV) |
| | **ROC-AUC** | **0.9670** | Windowed acoustic features (10s window) |
| | **Dumb Baseline Reduction**| **72.4% → 59.5%** | Telephony profile removes recording shortcuts |
| **Multimodal Early Detection** | **Median Lead Time** | **7.1 seconds** | Time from first alert to credential request |

---

## 📂 Project Structure

```
DT/
├── backend/
│   ├── app.py                          # FastAPI application & SSE job streaming
│   ├── asr_bridge.py                   # On-device Whisper speech-to-text bridge
│   ├── audio_pipeline.py               # Telephony preprocessing & XGBoost inference
│   ├── text_pipeline.py                # TF-IDF linguistic classification & script matching
│   ├── tactic_tagger.py                # 9 manipulation tactic detectors (EN + Hinglish)
│   ├── fusion_engine.py                # Multimodal fusion & deterministic safety rule layer
│   ├── pdf_generator.py                # ReportLab + Matplotlib PDF case report engine
│   ├── database.py                     # SQLite persistence for My Cases & Scam Radar
│   └── run_full_forensics_and_training.py # Master Phase 0 audit & training suite
├── frontend/
│   ├── index.html                      # Semantic accessible HTML5 user interface
│   ├── style.css                       # Bright, clean CSS design system (WCAG AA)
│   └── app.js                          # UI controller, audio playback & practice game
├── data/
│   ├── taxonomy.json                   # 12 scam families + playbooks + safe baseline
│   ├── helplines.json                  # Verified emergency directory (1930, Chakshu, 112)
│   ├── authored/hard_negatives.csv     # 30 synthetic authentic control messages
│   ├── transcripts/transcripts_cache.json # Cached Whisper transcripts for all 47 audio files
│   └── cases.db                        # Local SQLite database
├── models/
│   ├── text_model_v2.joblib            # Calibrated TF-IDF + Logistic Regression bundle
│   └── audio_xgb_model_v2.joblib       # Telephony-normalized 64-dim XGBoost model
├── reports/
│   ├── data_audit.md                   # Complete Phase 0 audit documentation
│   ├── metrics.json                    # Machine-readable master metrics artifact
│   ├── audio_bias_audit.json           # Recording-bias audit results
│   ├── early_detection.json            # Timeline milestone analysis
│   └── figures/                        # High-resolution PNG evaluation figures
├── Normal calls/                       # Authentic telephone recordings (.mp3/.wav)
├── Scam calls/                         # Vishing / scam telephone recordings (.mp3/.wav)
├── fraud_call.txt                      # 5,927 text script dataset
├── run_server.py                       # Server entrypoint (Port 8000)
└── requirements.txt                    # Python dependencies
```

---

## ⚙️ Installation & Running

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Modern web browser (Chrome, Firefox, Edge, Safari)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch SentiCall v2
```bash
python run_server.py
```
Open your browser and navigate to: **`http://127.0.0.1:8000`**

### 3. (Optional) Re-run Audit & Retrain Models
To run the full Phase 0 audit, cross-validation, and regenerate all JSON artifacts:
```bash
python backend/run_full_forensics_and_training.py
```

---

## 🛡️ Known Limitations & Ethical Boundary Disclosures

1. **Rule-Based Fallbacks for Emerging Scams**:
   Certain emerging scam types (*Digital Arrest, Sextortion, Remote Access Screen Share*) have sparse open academic datasets. These are detected using expert-curated rule patterns and zero-shot linguistic matching, honestly badged in the UI as **"Based on warning-sign rules"** rather than real-data ML training.
2. **Audio Acoustic Ambiguity**:
   Acoustic features (pitch fluctuation, speech rate) vary naturally across dialects, emotional states, and speaker temperaments. SentiCall treats audio as supporting contextual evidence rather than standalone proof.
3. **No Telecom Interception**:
   SentiCall v2 is intentionally designed for pre-recorded files, user-recorded clips, or pasted transcripts. It does not perform live-call interception or violate communication privacy.
4. **Empathetic AI Disclaimer**:
   SentiCall provides probabilistic guidance and decision support. When in doubt, users are always advised to follow the Golden Rule: **"Hang up and call back on a verified number you trust."**
