import os
import joblib
import numpy as np
from backend.train_text import clean_text
from backend.tactic_tagger import TacticTagger

MODEL_PATH = "models/text_model.joblib"
_text_bundle = None
_tagger = None

def get_tagger():
    global _tagger
    if _tagger is None:
        _tagger = TacticTagger()
    return _tagger

def get_text_model():
    global _text_bundle
    if _text_bundle is None:
        if os.path.exists(MODEL_PATH):
            try:
                _text_bundle = joblib.load(MODEL_PATH)
            except Exception as e:
                print(f"Error loading text model: {e}")
                _text_bundle = None
    return _text_bundle

def analyze_text(transcript: str) -> dict:
    """
    Run linguistic classification and manipulation tactic tagging on transcript text.
    Returns plain language breakdown, highlighted transcript, and risk score.
    """
    if not transcript or not transcript.strip():
        return {
            "success": False,
            "error": "Transcript is empty",
            "text_risk_score": 0,
            "probability": 0.0,
            "tactics_detected": [],
            "tactic_breakdown": [],
            "highlights": [],
            "highlighted_html": "",
            "linguistic_signals": ["No text provided for analysis"]
        }

    cleaned = clean_text(transcript)
    tagger = get_tagger()
    tactic_results = tagger.tag_transcript(transcript)

    bundle = get_text_model()
    if bundle and 'model' in bundle and 'vectorizer' in bundle:
        vectorizer = bundle['vectorizer']
        model = bundle['model']

        vec = vectorizer.transform([cleaned])
        ml_prob = float(model.predict_proba(vec)[0, 1])
    else:
        ml_prob = 0.5

    # Combine ML probability with rule-based tactic presence
    manip_score = tactic_results["manipulation_score"]
    
    # If explicit critical tactics (e.g. OTP, SIM deactivation threats, bank manager claim) are detected,
    # ensure probability reflects this strong evidence.
    if tactic_results["has_critical_indicators"]:
        combined_prob = max(ml_prob, 0.55 + 0.45 * manip_score)
    else:
        combined_prob = 0.65 * ml_prob + 0.35 * manip_score

    text_risk = round(min(1.0, max(0.0, combined_prob)) * 100)

    # Human-readable linguistic signals
    signals = []
    if tactic_results["tactics_detected"]:
        tactic_names = [t["title"] for t in tactic_results["tactic_breakdown"] if t["detected"]]
        signals.append(f"Detected conversational manipulation patterns: {', '.join(tactic_names)}.")
    else:
        signals.append("No overt manipulation or coercive phrasing patterns detected in message vocabulary.")

    if combined_prob >= 0.70:
        signals.append("Message syntax strongly mirrors confirmed banking, KYC, or telecom fraud scripts.")
    elif combined_prob >= 0.35:
        signals.append("Message contains ambiguous language requiring careful verification.")
    else:
        signals.append("Language is conversational and matches typical benign communications.")

    return {
        "success": True,
        "text_risk_score": text_risk,
        "probability": float(combined_prob),
        "cleaned_text": cleaned,
        "tactics_detected": tactic_results["tactics_detected"],
        "tactic_breakdown": tactic_results["tactic_breakdown"],
        "highlights": tactic_results["highlights"],
        "highlighted_html": tactic_results["highlighted_html"],
        "has_critical_indicators": tactic_results["has_critical_indicators"],
        "linguistic_signals": signals
    }
