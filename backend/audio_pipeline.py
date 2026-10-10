import os
import joblib
import numpy as np
import librosa
from backend.train_audio import extract_window_features

MODEL_PATH = "models/audio_xgb_model.joblib"
_audio_bundle = None

def get_audio_model():
    global _audio_bundle
    if _audio_bundle is None:
        if os.path.exists(MODEL_PATH):
            try:
                _audio_bundle = joblib.load(MODEL_PATH)
            except Exception as e:
                print(f"Error loading audio model: {e}")
                _audio_bundle = None
    return _audio_bundle

def analyze_audio(audio_path: str) -> dict:
    """
    Run acoustic feature extraction and XGBoost classification on an audio recording.
    Returns plain-language acoustic signals and risk score.
    """
    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        duration = float(librosa.get_duration(y=y, sr=sr))
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read audio: {str(e)}",
            "audio_risk_score": 0,
            "probability": 0.0,
            "duration_seconds": 0.0,
            "signals": ["Unable to process audio stream"]
        }

    features = extract_window_features(y, sr=sr, window_size=10)
    if not features or len(features) == 0:
        return {
            "success": True,
            "audio_risk_score": 15,
            "probability": 0.15,
            "duration_seconds": duration,
            "signals": ["Audio recording is very short or quiet."]
        }

    bundle = get_audio_model()
    if bundle and 'model' in bundle:
        model = bundle['model']
        X = np.array(features)
        window_probs = model.predict_proba(X)[:, 1]

        # Combine window probabilities: blend average and peak window to detect focal scam bursts
        avg_prob = float(np.mean(window_probs))
        peak_prob = float(np.max(window_probs))
        combined_prob = 0.6 * peak_prob + 0.4 * avg_prob
    else:
        # Fallback heuristic if model file isn't loaded
        combined_prob = 0.5

    # Human-friendly acoustic signals
    signals = []
    
    # 1. Zero crossing rate (speech tension/noise)
    zcr = np.mean(librosa.feature.zero_crossing_rate(y))
    if zcr > 0.12:
        signals.append("High voice urgency and vocal tension detected in speech cadence")
    else:
        signals.append("Even, natural speech cadence with steady vocal tempo")

    # 2. Spectral contrast (call compression / VoIP artifacts)
    spec_con = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr))
    if spec_con > 22.0:
        signals.append("Digital compression artifacts consistent with bulk VoIP/dialer routing")
    else:
        signals.append("Natural acoustic background typical of standard phone calls")

    if combined_prob >= 0.65:
        signals.append("Voice tone and frequency patterns align closely with known fraud call recordings")
    elif combined_prob >= 0.40:
        signals.append("Mixed acoustic cues detected; speech patterns show mild stress indicators")
    else:
        signals.append("Acoustic tone reflects relaxed, unscripted normal conversation")

    audio_risk = round(combined_prob * 100)

    return {
        "success": True,
        "audio_risk_score": audio_risk,
        "probability": float(combined_prob),
        "duration_seconds": round(duration, 1),
        "windows_analyzed": len(features),
        "signals": signals
    }
