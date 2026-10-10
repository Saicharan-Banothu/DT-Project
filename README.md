# SentiCall — "The Third Voice"
> **An AI Web-Based Prototype Against Voice Fraud (Vishing)**
> *A Design Thinking Course Project*

---

## 🌟 Overview
**SentiCall** is an AI-powered voice fraud (vishing) detection prototype designed with a warm, comforting, non-technical interface. It analyzes phone calls—either from an uploaded audio recording (`.mp3`, `.wav`) or a pasted transcript—to assess if the caller is employing common manipulation and deception tactics (such as fake bank KYC renewal, 23-hour SIM deactivation ultimatums, OTP extraction, or lottery awards).

Instead of providing clinical, opaque technical jargon, SentiCall breaks down *why* a call was flagged into plain-language manipulation signals, provides an interactive highlighted transcript, and gives reassuring next steps including direct connection to the **National Cyber Crime Helpline (1930)**.

---

## 🚀 Key Features

1. **Dual-Channel Multimodal Pipeline**:
   - **Acoustic Channel**: Extracts 98-dimensional acoustic features (10-second windowed MFCC 13 + delta + delta-delta, spectral contrast, chroma STFT, zero-crossing rate) and predicts deception likelihood with a trained **XGBoost Classifier**.
   - **Linguistic Channel**: Classifies conversational scripts with a **TF-IDF + Logistic Regression Model** trained on ~5,927 verified Indian and international call samples.
   - **Speech-to-Text Bridge**: Local **OpenAI Whisper** transcribes audio on device offline.
2. **5 Core Manipulation Tactics Tagged**:
   - 🏛️ **Authority Impersonation**: Bank managers, Jio/Airtel/Vodafone telecom officials, police/customs/cyber cell.
   - ⏳ **Urgency & Threat Framing**: "In 23 hours", "SIM will be closed", "account blocked immediately".
   - 🔑 **Payment & Credential Requests**: OTP disclosure, ATM PIN, CVV, wire transfer fees.
   - 🎁 **Reward & Lottery Bait**: "Won £350 award", "lucky winner", unsolicited cash prize.
   - 🪪 **Identity Document Demands**: Expired KYC claims, Aadhaar, PAN card, account numbers.
3. **Warm & Bright Consumer UI/UX**:
   - Light, airy visual design with soft shadows and modern typography ([Outfit](https://fonts.google.com/specimen/Outfit) & [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans)).
   - Animated 0–100 circular risk gauge with Low / Moderate / High safety tiers.
   - Step-by-step reassuring loading state.
   - Interactive highlighted transcript with gentle pastel pills.
   - Built-in **"Try a Sample Call"** library for instant 1-click demonstrations.
   - Helpline card with direct guidance for National Cybercrime Helpline **1930** ([cybercrime.gov.in](https://cybercrime.gov.in)).

---

## 📊 Evaluation & Validation Metrics (Stratified 5-Fold Cross-Validation)

In accordance with ethical academic standards, metrics are verified using real Stratified 5-Fold Cross-Validation:

- **Text Linguistic Model (`fraud_call.txt` — 5,927 rows)**:
  - Accuracy: `98.40% (±0.29%)`
  - Precision (Fraud Class): `92.66% (±1.72%)`
  - Recall: `92.49% (±2.53%)`
  - F1-Score: `92.54% (±1.39%)`
  - ROC-AUC: `0.9910`
- **Audio Acoustic XGBoost Model (47 audio files + data augmentation)**:
  - Accuracy: `89.87% (±5.99%)`
  - Precision: `89.63% (±10.28%)`
  - Recall: `94.02% (±5.08%)`
  - F1-Score: `91.22% (±4.74%)`
  - ROC-AUC: `0.9670`

---

## 📂 Project Structure

```
.
├── backend/
│   ├── app.py                 # FastAPI application & API routing
│   ├── audio_pipeline.py      # Acoustic feature extraction & XGBoost inference
│   ├── text_pipeline.py       # TF-IDF classification & tactic tagging
│   ├── tactic_tagger.py       # Rule-based + ML tactic detection & highlights
│   ├── asr_bridge.py          # OpenAI Whisper speech-to-text bridge
│   ├── fusion_engine.py       # Multimodal scoring & warm summary generator
│   ├── train_audio.py         # 5-Fold CV training script for audio XGBoost
│   └── train_text.py          # 5-Fold CV training script for text TF-IDF
├── frontend/
│   ├── index.html             # Semantic HTML5 consumer interface
│   ├── style.css              # Bright, modern CSS design system
│   └── app.js                 # Frontend application controller
├── models/
│   ├── audio_xgb_model.joblib # Saved XGBoost acoustic model
│   └── text_model.joblib      # Saved TF-IDF + Logistic Regression model
├── Normal calls/              # Benign / normal audio recordings
├── Scam calls/                # Scam / vishing audio recordings
├── fraud_call.txt             # Text dataset (~5,927 rows)
├── run_server.py              # Server entry point
└── requirements.txt           # Python dependencies
```

---

## ⚙️ Installation & Running Locally

### Prerequisites
- Python 3.10+ (tested on Python 3.13)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. (Optional) Train Models
```bash
# Train linguistic text model
python backend/train_text.py

# Train acoustic audio model
python backend/train_audio.py
```

### 3. Launch SentiCall Web App
```bash
python run_server.py
```

Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.
