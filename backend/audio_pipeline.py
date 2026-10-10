"""
SentiCall v2 — Acoustic Audio Pipeline & Telephony Feature Extraction
Implements telephony audio profile preprocessing (16kHz, 300-3400Hz, -20dBFS norm)
and XGBoost acoustic classification with interpretable voice fingerprint descriptors.
"""

import os
import joblib
import numpy as np
import scipy.signal
import librosa
from typing import Dict, Any, Tuple, Optional, List

MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "audio_xgb_model_v2.joblib"))
LEGACY_MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "audio_xgb_model.joblib"))

_AUDIO_BUNDLE = None

def get_audio_model():
    """Lazy load acoustic model bundle."""
    global _AUDIO_BUNDLE
    if _AUDIO_BUNDLE is not None:
        return _AUDIO_BUNDLE

    if os.path.exists(MODEL_PATH):
        try:
            _AUDIO_BUNDLE = joblib.load(MODEL_PATH)
            return _AUDIO_BUNDLE
        except Exception as e:
            print(f"Error loading v2 audio model: {e}")

    if os.path.exists(LEGACY_MODEL_PATH):
        try:
            _AUDIO_BUNDLE = joblib.load(LEGACY_MODEL_PATH)
            return _AUDIO_BUNDLE
        except Exception as e:
            print(f"Error loading legacy audio model: {e}")

    return None

def apply_telephone_filter(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """Apply 300-3400 Hz Butterworth band-pass filter."""
    nyquist = 0.5 * sample_rate
    low = 300.0 / nyquist
    high = min(3400.0 / nyquist, 0.99)
    b, a = scipy.signal.butter(4, [low, high], btype='band')
    filtered = scipy.signal.filtfilt(b, a, audio_data)
    return filtered.astype(np.float32)

def normalize_loudness(audio_data: np.ndarray, target_rms: float = 0.05) -> np.ndarray:
    """Normalize loudness to standard ~ -20 dBFS."""
    rms = np.sqrt(np.mean(audio_data ** 2) + 1e-9)
    if rms > 0:
        audio_data = audio_data * (target_rms / rms)
    return np.clip(audio_data, -1.0, 1.0)

def preprocess_audio_telephone(file_path: str) -> Tuple[np.ndarray, int, float]:
    """
    Standard telephony pipeline: 16 kHz mono, silence trimmed, 300-3400 Hz bandpass, loudness normalized.
    """
    try:
        y, sr = librosa.load(file_path, sr=16000, mono=True)
        y_trimmed, _ = librosa.effects.trim(y, top_db=25)
        if len(y_trimmed) < 1600:
            y_trimmed = y
        y_filtered = apply_telephone_filter(y_trimmed, 16000)
        y_norm = normalize_loudness(y_filtered, target_rms=0.05)
        duration = len(y_norm) / 16000.0
        return y_norm, 16000, duration
    except Exception as e:
        print(f"Error preprocessing audio {file_path}: {e}")
        dummy = np.zeros(16000, dtype=np.float32)
        return dummy, 16000, 1.0

def extract_window_features(win: np.ndarray, sample_rate: int = 16000) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Extract 64-dim acoustic feature vector for a 10s audio window."""
    # 1. MFCC 13 + delta + delta2 (39)
    mfcc = librosa.feature.mfcc(y=win, sr=sample_rate, n_mfcc=13)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_delta = librosa.feature.delta(mfcc)
    mfcc_delta_mean = np.mean(mfcc_delta, axis=1)
    mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
    mfcc_delta2_mean = np.mean(mfcc_delta2, axis=1)

    # 2. Spectral Contrast (7 bands)
    try:
        spec_con = librosa.feature.spectral_contrast(y=win, sr=sample_rate, n_bands=6)
        spec_con_mean = np.mean(spec_con, axis=1)
    except Exception:
        spec_con_mean = np.zeros(7)

    # 3. Chroma STFT (12 bins)
    try:
        chroma = librosa.feature.chroma_stft(y=win, sr=sample_rate)
        chroma_mean = np.mean(chroma, axis=1)
    except Exception:
        chroma_mean = np.zeros(12)

    # 4. Zero Crossing Rate
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(win)))

    # 5. Interpretable metrics
    rms_val = float(np.sqrt(np.mean(win ** 2) + 1e-9))
    rms_var = float(np.std(librosa.feature.rms(y=win)[0]))
    spec_flat = float(np.mean(librosa.feature.spectral_flatness(y=win)))
    silence_ratio = float(np.mean(np.abs(win) < 0.01))

    # Fast pitch variation estimate
    try:
        pitches, magnitudes = librosa.core.piptrack(y=win, sr=sample_rate, hop_length=1024)
        pitch_vals = pitches[magnitudes > np.median(magnitudes)]
        pitch_std = float(np.std(pitch_vals)) if len(pitch_vals) > 0 else 0.0
    except Exception:
        pitch_std = 0.0

    feat_vec = np.hstack([
        mfcc_mean, mfcc_delta_mean, mfcc_delta2_mean,
        spec_con_mean,
        chroma_mean,
        [zcr, rms_val, rms_var, spec_flat, silence_ratio, pitch_std]
    ])

    descriptors = {
        "rms_energy": round(rms_val, 4),
        "loudness_variation": round(rms_var, 4),
        "pitch_variation": round(pitch_std, 2),
        "silence_ratio": round(silence_ratio, 2),
        "background_noise_level": round(spec_flat, 4)
    }

    return feat_vec.astype(np.float32), descriptors

def analyze_audio(file_path: str, transcript_wpm: float = 140.0) -> Dict[str, Any]:
    """
    Execute full acoustic pipeline: telephony normalization, windowed extraction, XGBoost inference,
    and generate human-readable voice fingerprint cards.
    """
    bundle = get_audio_model()
    if bundle is None:
        return {
            "success": False,
            "error": "Acoustic XGBoost model not available.",
            "probability": 0.0,
            "risk_score": 0
        }

    model = bundle.get("model") if isinstance(bundle, dict) else bundle

    # 1. Telephony Profile Preprocessing
    y_tel, sr, total_dur = preprocess_audio_telephone(file_path)

    # 2. Windowed feature extraction (10s window, 5s hop)
    win_len = int(10.0 * sr)
    hop_len = int(5.0 * sr)

    if len(y_tel) < win_len:
        padded = np.pad(y_tel, (0, win_len - len(y_tel)), mode='constant')
        windows = [padded]
        time_offsets = [0.0]
    else:
        windows = []
        time_offsets = []
        for start in range(0, len(y_tel) - win_len + 1, hop_len):
            windows.append(y_tel[start : start + win_len])
            time_offsets.append(start / float(sr))

    window_feats = []
    window_descriptors = []
    for w in windows:
        f_vec, desc = extract_window_features(w, sr)
        window_feats.append(f_vec)
        window_descriptors.append(desc)

    X_mat = np.array(window_feats)

    # 3. XGBoost Inference
    probs = model.predict_proba(X_mat)[:, 1] if hasattr(model, "predict_proba") else [0.5]
    mean_prob = float(np.mean(probs))
    max_prob = float(np.max(probs))

    # Weight max window risk to catch short high-pressure bursts
    final_prob = min(1.0, max(0.0, (0.6 * mean_prob) + (0.4 * max_prob)))
    risk_score = int(round(final_prob * 100))

    # 4. Generate Interpretable Voice Fingerprint Cards
    avg_pitch_var = float(np.mean([d["pitch_variation"] for d in window_descriptors])) if window_descriptors else 0.0
    avg_loud_var = float(np.mean([d["loudness_variation"] for d in window_descriptors])) if window_descriptors else 0.0
    avg_noise = float(np.mean([d["background_noise_level"] for d in window_descriptors])) if window_descriptors else 0.0
    avg_silence = float(np.mean([d["silence_ratio"] for d in window_descriptors])) if window_descriptors else 0.0

    # Speaking Rhythm assessment
    if transcript_wpm > 170:
        pace_label = "Fast, high-pressure pace"
        pace_score = 82
        pace_desc = f"Speaking rapidly (~{int(transcript_wpm)} words/min), a known technique to rush listeners into making hasty decisions."
    elif transcript_wpm < 110:
        pace_label = "Slow, deliberate pace"
        pace_score = 35
        pace_desc = f"Measured, relaxed conversational pace (~{int(transcript_wpm)} words/min)."
    else:
        pace_label = "Scripted, steady conversational pace"
        pace_score = 65 if final_prob > 0.6 else 40
        pace_desc = f"Consistent rhythmic delivery (~{int(transcript_wpm)} words/min) consistent with standard telephonic scripts."

    # Vocal Tension assessment
    if avg_pitch_var > 60 or avg_loud_var > 0.04:
        pressure_label = "Elevated vocal urgency"
        pressure_score = 78
        pressure_desc = "Noticeable pitch elevation and emphatic syllable stress designed to convey authority or crisis."
    else:
        pressure_label = "Calm, natural inflection"
        pressure_score = 30
        pressure_desc = "Even vocal tone without artificial emotional pressure spikes."

    # Background Line Quality assessment
    if avg_noise > 0.02:
        bg_label = "Call-centre / ambient noise"
        bg_score = 70
        bg_desc = "Acoustic background texture consistent with multi-agent call center environments."
    else:
        bg_label = "Quiet / clear telephone line"
        bg_score = 25
        bg_desc = "Clean audio channel with minimal ambient interference."

    voice_fingerprint = [
        {
            "id": "speaking_rhythm",
            "title": "Speaking Rhythm & Pace",
            "label": pace_label,
            "meter_score": pace_score,
            "description": pace_desc
        },
        {
            "id": "voice_pressure",
            "title": "Vocal Pressure & Urgency",
            "label": pressure_label,
            "meter_score": pressure_score,
            "description": pressure_desc
        },
        {
            "id": "background_quality",
            "title": "Background & Line Environment",
            "label": bg_label,
            "meter_score": bg_score,
            "description": bg_desc
        }
    ]

    return {
        "success": True,
        "probability": round(final_prob, 4),
        "risk_score": risk_score,
        "duration_seconds": round(total_dur, 2),
        "total_windows": len(windows),
        "window_probabilities": [round(float(p), 4) for p in probs],
        "voice_fingerprint": voice_fingerprint,
        "acoustic_summary": f"Analyzed {len(windows)} temporal audio windows across telephony profile (16 kHz, 300–3400 Hz)."
    }
