"""
SentiCall v2 — Tactic Tagger & Multilingual Manipulation Detector
Extracts multi-label manipulation tactics across English and Hinglish phrasings.
Provides exact character/word spans and severity classifications.
"""

import re
from typing import List, Dict, Any, Tuple

# Comprehensive tactic definitions matching the 5 Core + 4 Expanded Tactics
TACTIC_DEFINITIONS = [
    {
        "id": "authority_impersonation",
        "title": "Pretending to be an authority",
        "icon": "shield-alert",
        "severity": "high",
        "badge_class": "badge-authority",
        "description": "Claims to represent a bank manager, telecom company, police, customs, or court official.",
        "regex": (
            r'\b('
            r'bank\s+manager|sbi\s+bank|hdfc\s+bank|icici\s+bank|axis\s+bank|state\s+bank\s+of\s+india|'
            r'jio\s+customer\s+care|airtel\s+customer\s+care|vodafone\s+customer|vi\s+customer|telecom\s+official|'
            r'cyber\s+crime\s+branch|police\s+officer|cbi\s+officer|customs\s+officer|income\s+tax\s+department|'
            r'rbi\s+officer|supreme\s+court|high\s+court|mha\s+official|trai\s+official|customs\s+department|'
            r'sharma\s+speaking\s+from\s+sbi|calling\s+from\s+head\s+office|customer\s+care\s+executive|'
            r'branch\s+manager|nodal\s+officer|investigating\s+officer'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'mai\s+bank\s+se\s+bol\s+raha\s+hu|sbi\s+ka\s+manager\s+hu|jio\s+office\s+se\s+call\s+hai|'
            r'police\s+thana\s+se\s+bol\s+rahe\s+hai|cyber\s+branch\s+se\s+phone\s+hai'
            r')\b'
        )
    },
    {
        "id": "urgency_threat",
        "title": "Creating false urgency or pressure",
        "icon": "clock",
        "severity": "high",
        "badge_class": "badge-urgency",
        "description": "Forces quick compliance with strict time limits or threats of immediate service cutoff.",
        "regex": (
            r'\b('
            r'in\s+23\s+hours|in\s+2\s+hours|within\s+\d+\s+hours|immediately|right\s+now|urgent|urgently|'
            r'sim\s+will\s+be\s+closed|sim\s+will\s+be\s+blocked|account\s+will\s+be\s+blocked|'
            r'card\s+is\s+about\s+to\s+expire|last\s+chance|before\s+midnight|today\s+only|'
            r'final\s+notice|service\s+will\s+be\s+suspended|electricity\s+power\s+cut'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'turant\s+karna\s+hoga|aaj\s+hi\s+karna\s+padega|23\s+ghante\s+me\s+sim\s+band\s+hoga|'
            r'account\s+block\s+ho\s+jayega|line\s+kat\s+di\s+jayegi|aakhri\s+mauka'
            r')\b'
        )
    },
    {
        "id": "secrecy_isolation",
        "title": "Demanding secrecy and isolation",
        "icon": "lock",
        "severity": "critical",
        "badge_class": "badge-secrecy",
        "description": "Instructs the listener not to disconnect, not to speak to family, or to remain isolated on video.",
        "regex": (
            r'\b('
            r'don\'t\s+tell\s+anyone|do\s+not\s+tell\s+anyone|stay\s+on\s+the\s+line|do\s+not\s+hang\s+up|'
            r'don\'t\s+hang\s+up|stay\s+on\s+video|do\s+not\s+speak\s+to\s+family|keep\s+it\s+strictly\s+confidential|'
            r'close\s+the\s+door|go\s+to\s+a\s+quiet\s+room|do\s+not\s+share\s+with\s+anyone'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'kisi\s+ko\s+mat\s+batana|ghar\s+walo\s+se\s+baat\s+mat\s+karo|phone\s+mat\s+katna|'
            r'line\s+par\s+raho|kamra\s+band\s+karlo'
            r')\b'
        )
    },
    {
        "id": "credential_request",
        "title": "Asking for passwords, OTP, or money",
        "icon": "key",
        "severity": "critical",
        "badge_class": "badge-credential",
        "description": "Demands disclosure of one-time passwords, CVV, ATM PINs, or money transfers.",
        "regex": (
            r'\b('
            r'four\s+digit\s+otp|six\s+digit\s+otp|\botp\b|one\s+time\s+password|verification\s+code|'
            r'share\s+the\s+otp|tell\s+me\s+the\s+otp|read\s+out\s+the\s+code|tell\s+me\s+the\s+code|'
            r'cvv|atm\s+pin|upi\s+pin|net\s+banking\s+password|card\s+number|'
            r'transfer\s+money|send\s+amount|processing\s+fee|registration\s+charge|refundable\s+security\s+deposit'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'chaar\s+digit\s+ka\s+otp|otp\s+bataiye|otp\s+share\s+kare|pin\s+number\s+batao|'
            r'paise\s+transfer\s+karo|charge\s+dena\s+padega'
            r')\b'
        )
    },
    {
        "id": "identity_document_request",
        "title": "Requesting sensitive identity details",
        "icon": "id-card",
        "severity": "medium",
        "badge_class": "badge-identity",
        "description": "Demands Aadhaar numbers, PAN cards, dates of birth, or full bank account details.",
        "regex": (
            r'\b('
            r'aadhaar|pan\s+card|pan\s+number|account\s+details|account\s+number|'
            r'date\s+of\s+birth|passport\s+number|voter\s+id|kyc\s+documents|'
            r'kyc\s+details|verify\s+your\s+identity'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'aadhaar\s+number\s+batao|pan\s+card\s+bhejo|account\s+number\s+bataiye|'
            r'apna\s+kyc\s+detail\s+do'
            r')\b'
        )
    },
    {
        "id": "remote_access_install",
        "title": "Asking you to install an app or share your screen",
        "icon": "monitor-down",
        "severity": "critical",
        "badge_class": "badge-remote",
        "description": "Instructs the listener to download remote access software or APK files.",
        "regex": (
            r'\b('
            r'anydesk|teamviewer|rustdesk|quicksupport|screen\s+share|share\s+screen|'
            r'install\s+this\s+app|download\s+app|download\s+apk|open\s+play\s+store|'
            r'accept\s+remote\s+connection|give\s+permission|allow\s+access'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'anydesk\s+install\s+karo|screen\s+share\s+kijiye|ye\s+app\s+download\s+karo|'
            r'remote\s+access\s+accept\s+karo'
            r')\b'
        )
    },
    {
        "id": "reward_prize_bait",
        "title": "Dangling a fake prize, lottery or reward",
        "icon": "gift",
        "severity": "medium",
        "badge_class": "badge-reward",
        "description": "Promises unsolicited lottery jackpots, cash awards, or prizes to lure advance fee payments.",
        "regex": (
            r'\b('
            r'won|selected\s+to\s+receive|£350\s+award|\$350\s+award|cash\s+prize|'
            r'lucky\s+winner|won\s+a\s+car|lottery\s+winner|unclaimed\s+reward|'
            r'cashback\s+bonus|claim\s+your\s+prize'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'aapko\s+lottery\s+lagi\s+hai|inaam\s+jeeta\s+hai|lucky\s+draw\s+nikla\s+hai|'
            r'cash\s+prize\s+mila\s+hai'
            r')\b'
        )
    },
    {
        "id": "legal_arrest_threat",
        "title": "Threatening arrest or legal consequences",
        "icon": "alert-triangle",
        "severity": "critical",
        "badge_class": "badge-legal",
        "description": "Threatens digital arrest, court prosecution, CBI probe, or FIR registration.",
        "regex": (
            r'\b('
            r'digital\s+arrest|arrest\s+warrant|police\s+custody|fir\s+registered|'
            r'supreme\s+court\s+notice|court\s+order|criminal\s+case|narcotics\s+case|'
            r'customs\s+seizure|illegal\s+parcel|jail\s+term|imprisonment'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'digital\s+arrest\s+kiya\s+jata\s+hai|police\s+pakad\s+ke\s+le\s+jayegi|'
            r'fir\s+darj\s+ho\s+chuki\s+hai|jail\s+jana\s+padega'
            r')\b'
        )
    },
    {
        "id": "abusive_language",
        "title": "Abusive or harassing language",
        "icon": "message-square-off",
        "severity": "high",
        "badge_class": "badge-abusive",
        "description": "Uses vulgarity, verbal abuse, aggressive profanity, or harassment.",
        "regex": (
            r'\b('
            r'bastard|bitch|idiot|fool|shut\s+up|nonsense|harass|'
            r'verbal\s+abuse|threaten\s+you|kill\s+you|destroy\s+you'
            r')\b'
        ),
        "hinglish_regex": (
            r'\b('
            r'kutta|harami|badtameez|pagal|gali|marunga'
            r')\b'
        )
    }
]


def detect_all_tactics(text: str) -> Dict[str, Any]:
    """
    Run regex pattern matching across all 9 tactics (English + Hinglish).
    Returns list of tactic hits, highlights, and critical safety indicator flag.
    """
    t_lower = text.lower()
    tactic_hits = []
    has_critical = False
    highlights = []

    for item in TACTIC_DEFINITIONS:
        en_matches = list(re.finditer(item["regex"], t_lower))
        hi_matches = list(re.finditer(item["hinglish_regex"], t_lower))
        all_m = en_matches + hi_matches

        if all_m:
            matched_phrases = list(set([m.group(0).strip() for m in all_m]))
            tactic_hits.append({
                "id": item["id"],
                "title": item["title"],
                "description": item["description"],
                "severity": item["severity"],
                "icon": item["icon"],
                "badge_class": item["badge_class"],
                "matched_phrases": matched_phrases[:4],
                "detected": True
            })

            if item["severity"] == "critical":
                has_critical = True

            for m in all_m:
                highlights.append({
                    "start": m.start(),
                    "end": m.end(),
                    "phrase": text[m.start():m.end()],
                    "tactic_id": item["id"],
                    "tactic_title": item["title"],
                    "severity": item["severity"]
                })

    # Sort highlights by character position
    highlights.sort(key=lambda x: x["start"])

    # Remove overlapping highlights
    clean_highlights = []
    last_end = -1
    for h in highlights:
        if h["start"] >= last_end:
            clean_highlights.append(h)
            last_end = h["end"]

    return {
        "tactic_breakdown": tactic_hits,
        "total_tactics_found": len(tactic_hits),
        "has_critical_indicators": has_critical,
        "highlights": clean_highlights
    }


def generate_highlighted_transcript_html(text: str, highlights: List[Dict[str, Any]], word_weights: Dict[str, float] = None) -> str:
    """
    Build HTML with soft pastel colored pills for detected tactics and gentle word shading.
    """
    if not text:
        return ""

    if not highlights:
        # Render clean paragraphs with subtle word shading
        words = text.split()
        shaded_words = []
        for w in words:
            clean_w = re.sub(r'[^\w]', '', w.lower())
            w_weight = word_weights.get(clean_w, 0.0) if word_weights else 0.0
            if w_weight > 0.8:
                alpha = min(0.35, max(0.08, w_weight * 0.12))
                shaded_words.append(f'<span class="word-shade-risk" style="background-color: rgba(220, 38, 38, {alpha:.2f})">{w}</span>')
            else:
                shaded_words.append(w)
        return " ".join(shaded_words)

    html_parts = []
    curr_pos = 0

    for h in highlights:
        # Preceding normal text
        if h["start"] > curr_pos:
            pre_text = text[curr_pos : h["start"]]
            html_parts.append(pre_text)

        # Highlighted span
        hl_phrase = text[h["start"] : h["end"]]
        t_id = h["tactic_id"]
        sev = h["severity"]
        title = h["tactic_title"]

        pill_class = f"tactic-pill pill-{sev}"
        html_parts.append(f'<mark class="{pill_class}" data-tactic="{t_id}" title="{title}">{hl_phrase}</mark>')
        curr_pos = h["end"]

    # Trailing text
    if curr_pos < len(text):
        html_parts.append(text[curr_pos:])

    return "".join(html_parts)
