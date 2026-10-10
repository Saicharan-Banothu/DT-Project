import re
from typing import List, Dict, Any

# Plain-language tactic definitions designed for non-technical users
TACTIC_DEFINITIONS = {
    "authority_impersonation": {
        "id": "authority_impersonation",
        "title": "Pretending to Be an Authority",
        "badge": "Authority Claim",
        "icon": "shield-alert",
        "description": "Claims to represent a bank manager, telecom company, cyber cell, or government official to gain your trust and intimidate you.",
        "patterns": [
            r"\b(?:bank\s+manager|manager\s+of\s+\w+)\b",
            r"\b(?:customer\s+care(?:\s+center)?)\b",
            r"\b(?:jio|airtel|vodafone|bsnl|idea|mtnl)\s+customer\s+care\b",
            r"\b(?:sbi|hdfc|icici|axis\s+bank|pnb|kotak|canara\s+bank)\b",
            r"\b(?:police|customs\s+department|cyber\s+cell|rbi|income\s+tax|telecom\s+department|cbi|trai)\b",
            r"\b(?:official\s+verification|head\s+office|branch\s+manager)\b"
        ],
        "weight": 0.25
    },
    "urgency_threat": {
        "id": "urgency_threat",
        "title": "Creating False Urgency or Pressure",
        "badge": "Urgency / Threat",
        "icon": "alarm",
        "description": "Pressures you with immediate deadlines, threats of SIM deactivation, or legal penalties so you act without thinking.",
        "patterns": [
            r"\bin\s+\d+\s+(?:hours|minutes|hrs|mins)\b",
            r"\b(?:sim\s+will\s+be\s+(?:closed|deactivate[d]?|blocked|suspended))\b",
            r"\b(?:account\s+will\s+be\s+(?:blocked|frozen|suspended|closed|deactivate[d]?))\b",
            r"\b(?:immediate(?:ly)?|urgent(?:ly)?|last\s+warning|within\s+24\s+hours|today\s+only)\b",
            r"\b(?:legal\s+action|police\s+case|arrest\s+warrant|penalty|fine|action\s+will\s+be\s+taken)\b",
            r"\b(?:card\s+is\s+about\s+to\s+expire|expiring\s+today)\b"
        ],
        "weight": 0.25
    },
    "payment_credential_request": {
        "id": "payment_credential_request",
        "title": "Asking for Passwords, OTP, or Money",
        "badge": "Credential / Payment",
        "icon": "key",
        "description": "Asks for your secret one-time password (OTP), PIN, CVV, or asks you to make an upfront payment or download remote access software.",
        "patterns": [
            r"\b(?:(?:four|six|\d+)\s+digit\s+(?:otp|opt|code))\b",
            r"\b(?:tell\s+me\s+that\s+otp|share\s+(?:your\s+)?otp|send\s+otp|otp\s+sent|opt\s+will\s+have\s+send)\b",
            r"\b(?:cvv|card\s+number|pin\s+number|atm\s+pin|password|net\s+banking\s+password)\b",
            r"\b(?:send\s+money|transfer\s+fee|processing\s+fee|refundable\s+amount|registration\s+charge|pay\s+now)\b",
            r"\b(?:anydesk|teamviewer|quicksupport|rustdesk|download\s+this\s+app)\b"
        ],
        "weight": 0.30
    },
    "reward_lottery_bait": {
        "id": "reward_lottery_bait",
        "title": "Dangling Fake Prizes or Lotteries",
        "badge": "Prize / Lottery Bait",
        "icon": "gift",
        "description": "Promises cash prizes, lottery payouts, or expensive gift vouchers for contests you never entered.",
        "patterns": [
            r"\b(?:selected\s+to\s+receive|selected\s+for|lucky\s+winner|won\s+(?:cash|lottery|prize|award))\b",
            r"\b(?:receive\s+a\s+[£\$€₹]?\s*\d+\s*(?:award|prize|cash)?)\b",
            r"\b(?:won\s+[£\$€₹]?\s*\d+)\b",
            r"\b(?:claim\s+(?:your\s+)?(?:prize|award|lottery|reward|cash))\b",
            r"\b(?:congratulations\s+you\s+have\s+won|gift\s+voucher|bonus\s+points|free\s+iphone)\b"
        ],
        "weight": 0.20
    },
    "identity_document_request": {
        "id": "identity_document_request",
        "title": "Requesting Sensitive Identity Details",
        "badge": "Identity / KYC Request",
        "icon": "id-card",
        "description": "Requests sensitive personal credentials like Aadhaar, PAN, date of birth, or claims your KYC verification has expired.",
        "patterns": [
            r"\b(?:kyc\s+has\s+been\s+expired|kyc\s+is\s+expired|kyc\s+expire[d]?)\b",
            r"\b(?:kyc\s+your\s*self|kyc\s+online|update\s+(?:your\s+)?kyc|complete\s+kyc)\b",
            r"\b(?:account\s+detail[s]?|bank\s+account\s+number|account\s+information)\b",
            r"\b(?:aadhaar(?:\s+card|\s+number)?|aadhar(?:\s+card|\s+number)?|pan\s+card(?:\s+number)?)\b",
            r"\b(?:verify\s+your\s+identity|date\s+of\s+birth|mother(?:'s)?\s+maiden\s+name)\b"
        ],
        "weight": 0.20
    }
}

class TacticTagger:
    def __init__(self):
        # Precompile regular expressions
        self.compiled_rules = {}
        for tactic_id, info in TACTIC_DEFINITIONS.items():
            compiled = [re.compile(p, re.IGNORECASE) for p in info["patterns"]]
            self.compiled_rules[tactic_id] = compiled

    def tag_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Analyzes a transcript for manipulation tactics and extracts
        exact matched text snippets and character spans for highlight rendering.
        """
        if not transcript or not isinstance(transcript, str):
            return {
                "tactics_detected": [],
                "tactic_breakdown": [],
                "highlights": [],
                "manipulation_score": 0.0,
                "has_critical_indicators": False
            }

        text = transcript
        detected_tactics = []
        breakdown = []
        highlights = []
        total_weight_score = 0.0
        has_critical = False

        # Find matches for each tactic
        for tactic_id, info in TACTIC_DEFINITIONS.items():
            regexes = self.compiled_rules[tactic_id]
            matched_phrases = set()
            tactic_spans = []

            for rgx in regexes:
                for match in rgx.finditer(text):
                    phrase = match.group(0).strip()
                    matched_phrases.add(phrase)
                    tactic_spans.append({
                        "start": match.start(),
                        "end": match.end(),
                        "text": phrase,
                        "tactic_id": tactic_id,
                        "tactic_title": info["title"],
                        "badge": info["badge"]
                    })

            presence_score = 0.0
            if matched_phrases:
                # Score increases with multiple hits up to 1.0
                presence_score = min(1.0, 0.45 + 0.25 * len(matched_phrases))
                total_weight_score += info["weight"] * presence_score
                
                # Check critical risk indicators (OTP requests or KYC + urgency)
                if tactic_id in ["payment_credential_request", "identity_document_request"]:
                    has_critical = True

                detected_tactics.append(tactic_id)
                highlights.extend(tactic_spans)

            breakdown.append({
                "id": tactic_id,
                "title": info["title"],
                "badge": info["badge"],
                "description": info["description"],
                "detected": bool(matched_phrases),
                "confidence": round(presence_score * 100),
                "matched_phrases": list(matched_phrases),
                "match_count": len(matched_phrases)
            })

        # Sort and deduplicate highlights by start index
        # Avoid overlapping highlight tags
        sorted_highlights = sorted(highlights, key=lambda x: (x["start"], -(x["end"] - x["start"])))
        non_overlapping_highlights = []
        last_end = -1
        for h in sorted_highlights:
            if h["start"] >= last_end:
                non_overlapping_highlights.append(h)
                last_end = h["end"]

        # Build highlighted HTML transcript for safe rendering
        highlighted_html = self._generate_highlighted_html(text, non_overlapping_highlights)

        normalized_manipulation_score = min(1.0, total_weight_score)

        return {
            "tactics_detected": detected_tactics,
            "tactic_breakdown": breakdown,
            "highlights": non_overlapping_highlights,
            "highlighted_html": highlighted_html,
            "manipulation_score": normalized_manipulation_score,
            "has_critical_indicators": has_critical
        }

    def _generate_highlighted_html(self, original_text: str, highlights: List[Dict[str, Any]]) -> str:
        """Create clean HTML wrapping flagged phrases in gentle highlight spans."""
        if not highlights:
            return self._escape_html(original_text)

        html_pieces = []
        current_idx = 0

        for h in highlights:
            start, end = h["start"], h["end"]
            if start > current_idx:
                html_pieces.append(self._escape_html(original_text[current_idx:start]))

            flagged_text = self._escape_html(original_text[start:end])
            tactic_title = self._escape_html(h["tactic_title"])
            tactic_id = h["tactic_id"]
            
            span_tag = f'<mark class="flagged-phrase tactic-{tactic_id}" data-tactic="{tactic_id}" title="{tactic_title}: {flagged_text}">{flagged_text}</mark>'
            html_pieces.append(span_tag)
            current_idx = end

        if current_idx < len(original_text):
            html_pieces.append(self._escape_html(original_text[current_idx:]))

        return "".join(html_pieces)

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&#39;"))

if __name__ == "__main__":
    tagger = TacticTagger()
    sample = "hello, i m bank manager of SBI, ur debit card is about to expire. tell me four digit otp to activate in 23 hours."
    res = tagger.tag_transcript(sample)
    print("Detected Tactics:", res["tactics_detected"])
    print("Highlighted HTML:", res["highlighted_html"])
