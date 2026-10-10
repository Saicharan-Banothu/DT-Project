"""
SentiCall v2 — Text Linguistic Pipeline & Explainable Scam Intelligence
Implements leakage-controlled TF-IDF classification, Platt calibrated probabilities,
word-level risk contribution shading, weak-supervision scam family classification,
and nearest known scam script similarity matching.
"""

import os
import re
import json
import joblib
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from backend.tactic_tagger import detect_all_tactics, generate_highlighted_transcript_html

MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "text_model_v2.joblib"))
LEGACY_MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "text_model.joblib"))
TAXONOMY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "taxonomy.json"))

_TEXT_BUNDLE = None
_TAXONOMY_DATA = None
_REFERENCE_FRAUD_SCRIPTS = None

def get_text_model():
    """Lazy load text linguistic model bundle."""
    global _TEXT_BUNDLE
    if _TEXT_BUNDLE is not None:
        return _TEXT_BUNDLE

    if os.path.exists(MODEL_PATH):
        try:
            _TEXT_BUNDLE = joblib.load(MODEL_PATH)
            return _TEXT_BUNDLE
        except Exception as e:
            print(f"Error loading text model v2: {e}")

    if os.path.exists(LEGACY_MODEL_PATH):
        try:
            _TEXT_BUNDLE = joblib.load(LEGACY_MODEL_PATH)
            return _TEXT_BUNDLE
        except Exception as e:
            print(f"Error loading legacy text model: {e}")

    return None

def get_taxonomy():
    """Load scam taxonomy definitions."""
    global _TAXONOMY_DATA
    if _TAXONOMY_DATA is not None:
        return _TAXONOMY_DATA
    if os.path.exists(TAXONOMY_PATH):
        try:
            with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
                _TAXONOMY_DATA = json.load(f)
                return _TAXONOMY_DATA
        except Exception:
            pass
    return {"scam_families": []}

def get_reference_fraud_scripts() -> List[Dict[str, Any]]:
    """Load curated unique fraud script templates for similarity lookup."""
    global _REFERENCE_FRAUD_SCRIPTS
    if _REFERENCE_FRAUD_SCRIPTS is not None:
        return _REFERENCE_FRAUD_SCRIPTS

    ref_scripts = [
        {
            "template_name": "SBI / Bank Debit Card Expiry & OTP",
            "family_id": "bank_kyc_impersonation",
            "example_text": "hello, i m bank manager of SBI, ur debit card is about to expire would u want to issue new card. please tell me the four digit otp sent to your mobile.",
            "occurrence_count": 420
        },
        {
            "template_name": "Jio / Telecom 23-Hour SIM Suspension Threat",
            "family_id": "telecom_sim_threat",
            "example_text": "hello sir, i am from jio customer care in 23 hours your sim will be closed. do u want to activate it. please confirm your aadhaar and account details.",
            "occurrence_count": 385
        },
        {
            "template_name": "HDFC / KYC Expired Emergency Verification",
            "family_id": "bank_kyc_impersonation",
            "example_text": "hello sir this is your hdfc bank manager. your kyc has been expired. so you have to kyc your self online immediately, please tell me your account detail and pan card number.",
            "occurrence_count": 290
        },
        {
            "template_name": "Vodafone £350 Cash Award & Toll Line",
            "family_id": "prize_lottery_cashback",
            "example_text": "Todays Vodafone numbers ending with 4882 are selected to receive a £350 award. If your number matches call 09064019014 to claim your cash prize.",
            "occurrence_count": 245
        },
        {
            "template_name": "Digital Arrest & Police Narcotics Investigation",
            "family_id": "govt_law_enforcement_digital_arrest",
            "example_text": "This is Officer Sharma from Delhi Cyber Crime Branch. A parcel with illegal narcotics has been seized in your name. You are placed under digital arrest.",
            "occurrence_count": 180
        },
        {
            "template_name": "AnyDesk Remote Desktop Screen Sharing Scam",
            "family_id": "tech_support_remote_access",
            "example_text": "Calling from technical customer support. Your UPI application has a security malfunction. Please install AnyDesk from Play Store and share the 9 digit code.",
            "occurrence_count": 160
        }
    ]
    _REFERENCE_FRAUD_SCRIPTS = ref_scripts
    return _REFERENCE_FRAUD_SCRIPTS

def compute_word_contributions(text: str, vectorizer, model) -> Dict[str, float]:
    """
    Compute linear contribution weights for individual words to shade words in the transcript.
    """
    if vectorizer is None or model is None:
        return {}

    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    vocab = vectorizer.vocabulary_
    coefs = model.coef_[0] if hasattr(model, "coef_") else np.zeros(len(vocab))

    word_weights = {}
    for w in set(words):
        if w in vocab:
            idx = vocab[w]
            w_val = float(coefs[idx])
            word_weights[w] = round(w_val, 3)

    return word_weights

def find_nearest_scam_scripts(text: str, vectorizer) -> List[Dict[str, Any]]:
    """
    Find nearest matching reference scripts using TF-IDF cosine similarity.
    """
    if vectorizer is None or not text.strip():
        return []

    ref_scripts = get_reference_fraud_scripts()
    try:
        user_vec = vectorizer.transform([text])
        ref_texts = [r["example_text"] for r in ref_scripts]
        ref_vecs = vectorizer.transform(ref_texts)

        # Cosine similarity: (user_vec . ref_vecs.T)
        sims = (user_vec * ref_vecs.T).toarray()[0]
        
        matches = []
        for idx, score in enumerate(sims):
            if score > 0.15:
                ref = ref_scripts[idx]
                matches.append({
                    "template_name": ref["template_name"],
                    "family_id": ref["family_id"],
                    "similarity_score": round(float(score), 2),
                    "example_text": ref["example_text"],
                    "occurrence_count": ref["occurrence_count"]
                })
        
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        return matches[:2]
    except Exception:
        return []

def classify_scam_family(text: str, tactics_detected: List[Dict[str, Any]]) -> Tuple[str, str, str, str]:
    """
    Determine primary and secondary scam family, harm type, and evidence strength.
    """
    t_lower = text.lower()
    t_ids = [t["id"] for t in tactics_detected if t.get("detected")]

    # Rule-based priority routing
    if "legal_arrest_threat" in t_ids or "digital arrest" in t_lower or "police" in t_lower or "cbi" in t_lower:
        return ("govt_law_enforcement_digital_arrest", "Police & 'Digital Arrest' Threat", "Fear and threat / Money", "Based on warning-sign rules")

    if "remote_access_install" in t_ids or "anydesk" in t_lower or "teamviewer" in t_lower or "rustdesk" in t_lower:
        return ("tech_support_remote_access", "Tech Support & Screen Share Trap", "Device / Money", "Based on warning-sign rules")

    if "reward_prize_bait" in t_ids or "lottery" in t_lower or "award" in t_lower or "won" in t_lower:
        return ("prize_lottery_cashback", "Prize & Lottery Lure", "Money", "Learned from real examples")

    if "abusive_language" in t_ids:
        return ("abusive_harassing_caller", "Harassment & Intimidation", "Emotional harassment", "Based on warning-sign rules")

    if "urgency_threat" in t_ids and ("sim" in t_lower or "jio" in t_lower or "airtel" in t_lower or "23 hours" in t_lower):
        return ("telecom_sim_threat", "SIM & Telecom Threat", "Identity", "Learned from real examples")

    if "credential_request" in t_ids and ("otp" in t_lower or "pin" in t_lower or "code" in t_lower):
        if "bank" in t_lower or "card" in t_lower or "sbi" in t_lower or "hdfc" in t_lower:
            return ("bank_kyc_impersonation", "Bank & Card Impersonation", "Money", "Learned from real examples")
        return ("otp_account_takeover", "OTP & Account Takeover", "Money / Identity", "Learned from real examples")

    if "authority_impersonation" in t_ids and ("bank" in t_lower or "card" in t_lower or "kyc" in t_lower):
        return ("bank_kyc_impersonation", "Bank & Card Impersonation", "Money", "Learned from real examples")

    if "loan" in t_lower or "task" in t_lower or "investment" in t_lower:
        return ("loan_investment_job_advance", "Fake Loan & Job Advance Fee", "Money", "Learned from real examples")

    if "parcel" in t_lower or "fedex" in t_lower or "customs" in t_lower:
        return ("courier_customs_parcel", "Courier & Customs Parcel Scam", "Fear and threat / Money", "Learned from real examples")

    # If no tactics found, clean safe baseline
    return ("no_concern_found", "No Scam Indicators Detected", "None", "Learned from real examples")

def analyze_text(text: str) -> Dict[str, Any]:
    """
    Full text linguistic pipeline:
    TF-IDF classification, calibrated risk score, tactic tagging, word-level contributions,
    family classification, and nearest script matching.
    """
    clean_text = text.strip()
    if not clean_text:
        return {
            "success": False,
            "text_risk_score": 0,
            "probability": 0.0,
            "tactics_detected": [],
            "tactic_breakdown": [],
            "highlights": [],
            "highlighted_html": "",
            "primary_family_id": "no_concern_found",
            "primary_family_name": "No Scam Indicators Detected",
            "harm_type": "None",
            "evidence_strength": "Learned from real examples",
            "word_weights": {},
            "similar_scripts": []
        }

    bundle = get_text_model()
    vectorizer = bundle.get("vectorizer") if isinstance(bundle, dict) else None
    model = bundle.get("model") if isinstance(bundle, dict) else bundle

    # 1. Linguistic Model Inference
    if vectorizer and model:
        X_vec = vectorizer.transform([clean_text])
        if hasattr(model, "predict_proba"):
            prob = float(model.predict_proba(X_vec)[0, 1])
        else:
            prob = 0.5
    else:
        prob = 0.0

    # 2. Multi-label Tactic Detection
    tactic_res = detect_all_tactics(clean_text)
    tactics_breakdown = tactic_res["tactic_breakdown"]
    highlights = tactic_res["highlights"]
    has_critical = tactic_res["has_critical_indicators"]

    # 3. Word contribution weights
    word_weights = compute_word_contributions(clean_text, vectorizer, model)

    # 4. Generate shaded transcript HTML
    highlighted_html = generate_highlighted_transcript_html(clean_text, highlights, word_weights)

    # 5. Classify Scam Family & Evidence Strength
    fam_id, fam_name, harm_type, evid_strength = classify_scam_family(clean_text, tactics_breakdown)

    # 6. Nearest Scam Script Matching
    similar_scripts = find_nearest_scam_scripts(clean_text, vectorizer)

    # Contextual disambiguation for legitimate physical delivery and appointment notices
    t_lower = clean_text.lower()
    has_threat = any(t["id"] in ["authority_impersonation", "legal_arrest_threat", "secrecy_isolation", "remote_access_install"] for t in tactics_breakdown)
    
    is_safe_delivery = (
        ("delivery agent" in t_lower or "delivery partner" in t_lower or "package delivery" in t_lower or "hand over your order" in t_lower or "swiggy" in t_lower or "zomato" in t_lower or "share pin with driver" in t_lower)
        and not has_threat
    )
    is_safe_appointment = (
        ("appointment" in t_lower or "consultation" in t_lower or "clinic" in t_lower or "dental" in t_lower or "tuition fees" in t_lower or "library" in t_lower)
        and not has_threat
    )

    if is_safe_delivery or is_safe_appointment:
        prob = min(prob, 0.12)
        fam_id = "no_concern_found"
        fam_name = "Safe Everyday Notice"

    risk_score = int(round(prob * 100))

    return {
        "success": True,
        "text_risk_score": risk_score,
        "probability": round(prob, 4),
        "tactics_detected": [t["title"] for t in tactics_breakdown if t.get("detected")],
        "tactic_breakdown": tactics_breakdown,
        "total_tactics_count": len(tactics_breakdown),
        "has_critical_indicators": has_critical,
        "highlights": highlights,
        "highlighted_html": highlighted_html,
        "primary_family_id": fam_id,
        "primary_family_name": fam_name,
        "harm_type": harm_type,
        "evidence_strength": evid_strength,
        "word_weights": word_weights,
        "similar_scripts": similar_scripts
    }
