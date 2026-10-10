from typing import Dict, Any, Optional

class FusionEngine:
    def __init__(self, audio_weight: float = 0.35, text_weight: float = 0.65):
        self.audio_weight = audio_weight
        self.text_weight = text_weight

    def fuse_and_evaluate(
        self,
        text_result: Optional[Dict[str, Any]] = None,
        audio_result: Optional[Dict[str, Any]] = None,
        transcript_text: str = ""
    ) -> Dict[str, Any]:
        """
        Multimodal fusion of text and audio streams with warm, human explanation generation.
        """
        has_audio = audio_result is not None and audio_result.get("success", False)
        has_text = text_result is not None and text_result.get("success", False)

        if has_audio and has_text:
            audio_prob = audio_result.get("probability", 0.0)
            text_prob = text_result.get("probability", 0.0)

            # Weight combination
            final_prob = (self.audio_weight * audio_prob) + (self.text_weight * text_prob)

            # If strong textual manipulation indicators exist, ensure final risk is not suppressed
            if text_result.get("has_critical_indicators", False):
                final_prob = max(final_prob, text_prob)

        elif has_text:
            final_prob = text_result.get("probability", 0.0)
        elif has_audio:
            final_prob = audio_result.get("probability", 0.0)
        else:
            final_prob = 0.0

        final_prob = min(1.0, max(0.0, final_prob))
        overall_score = round(final_prob * 100)

        # Determine Tier
        if overall_score >= 70:
            risk_tier = "High Risk"
            risk_badge_class = "risk-high"
            risk_theme_color = "#DC2626"
            verdict_heading = "High Likelihood of a Voice Scam (Vishing)"
        elif overall_score >= 36:
            risk_tier = "Moderate Risk"
            risk_badge_class = "risk-moderate"
            risk_theme_color = "#D97706"
            verdict_heading = "Caution Advised – Suspicious Elements Detected"
        else:
            risk_tier = "Low Risk"
            risk_badge_class = "risk-low"
            risk_theme_color = "#059669"
            verdict_heading = "Call Appears Safe and Normal"

        # Generate warm, plain-language summary sentence
        summary_sentence = self._generate_warm_summary(
            risk_tier=risk_tier,
            text_result=text_result,
            has_audio=has_audio
        )

        # Generate helpful next steps
        next_steps = self._generate_next_steps(risk_tier=risk_tier, text_result=text_result)

        return {
            "overall_score": overall_score,
            "risk_tier": risk_tier,
            "risk_badge_class": risk_badge_class,
            "risk_theme_color": risk_theme_color,
            "verdict_heading": verdict_heading,
            "summary_sentence": summary_sentence,
            "next_steps": next_steps,
            "has_audio": has_audio,
            "has_text": has_text,
            "weights": {
                "audio_weight": self.audio_weight if has_audio else 0.0,
                "text_weight": self.text_weight if has_audio else 1.0
            }
        }

    def _generate_warm_summary(
        self,
        risk_tier: str,
        text_result: Optional[Dict[str, Any]],
        has_audio: bool
    ) -> str:
        """Create a human, empathetic single sentence explaining why the verdict was reached."""
        detected_tactics = []
        if text_result and text_result.get("tactic_breakdown"):
            for t in text_result["tactic_breakdown"]:
                if t.get("detected"):
                    detected_tactics.append(t["title"].lower())

        if risk_tier == "High Risk":
            if "asking for passwords, otp, or money" in detected_tactics and "pretending to be an authority" in detected_tactics:
                return "This call appears to impersonate an official representative and asks for your secret OTP or passwords — a well-known tactic used to compromise bank accounts."
            elif "creating false urgency or pressure" in detected_tactics and "requesting sensitive identity details" in detected_tactics:
                return "This call creates artificial urgency about your service or KYC expiring to rush you into sharing sensitive personal identity details."
            elif "asking for passwords, otp, or money" in detected_tactics:
                return "This call asks you to disclose confidential security codes or transfer money, which legitimate organizations never request over the phone."
            elif "dangling fake prizes or lotteries" in detected_tactics:
                return "This call claims you won an unsolicited prize or lottery payout — a classic lure designed to trick you into paying advance fees."
            elif detected_tactics:
                tactics_str = " and ".join(detected_tactics[:2])
                return f"This call exhibits deceptive patterns including {tactics_str}, which are frequently observed in fraudulent phone scams."
            else:
                return "This call exhibits high-pressure conversational phrasing and vocal tension consistent with documented scam calls."

        elif risk_tier == "Moderate Risk":
            if detected_tactics:
                tactics_str = " and ".join(detected_tactics[:2])
                return f"This call contains ambiguous pressure signals such as {tactics_str}; we suggest verifying the caller's identity independently before taking any action."
            else:
                return "While no blatant fraud was identified, the call includes unusual phrasing or vocal tension that warrants careful attention."

        else: # Low Risk
            return "This conversation flows naturally like an everyday phone call, with no signs of impersonation, urgency traps, or credential requests."

    def _generate_next_steps(self, risk_tier: str, text_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate supportive, reassuring guidance."""
        if risk_tier == "High Risk":
            return {
                "headline": "Recommended Immediate Actions",
                "badge": "Action Advised",
                "show_helpline": True,
                "helpline_number": "1930",
                "helpline_name": "National Cyber Crime Helpline (India)",
                "helpline_url": "https://cybercrime.gov.in",
                "tips": [
                    "Do NOT share any OTP, PIN, CVV, or passwords under any circumstances.",
                    "Hang up immediately — legitimate bank and telecom officials will never threaten you with instant disconnection or arrest.",
                    "If you are concerned about your bank account or SIM card, call the official number printed on the back of your card or visit an official branch."
                ]
            }
        elif risk_tier == "Moderate Risk":
            return {
                "headline": "Helpful Precautions",
                "badge": "Stay Cautious",
                "show_helpline": True,
                "helpline_number": "1930",
                "helpline_name": "National Cyber Crime Helpline",
                "helpline_url": "https://cybercrime.gov.in",
                "tips": [
                    "Ask for the caller's official employee ID and branch location, then disconnect and verify independently.",
                    "Never click on links or download remote access apps (like AnyDesk or TeamViewer) sent during a call.",
                    "If in doubt, contact the official organization through their verified website or app."
                ]
            }
        else:
            return {
                "headline": "Safety Reassurance",
                "badge": "All Clear",
                "show_helpline": False,
                "tips": [
                    "This call matches ordinary, everyday conversation.",
                    "As a general safety habit, always keep your passwords and banking OTPs private."
                ]
            }

if __name__ == "__main__":
    fusion = FusionEngine()
    dummy_text = {
        "success": True,
        "probability": 0.92,
        "has_critical_indicators": True,
        "tactic_breakdown": [
            {"title": "Pretending to Be an Authority", "detected": True},
            {"title": "Asking for Passwords, OTP, or Money", "detected": True}
        ]
    }
    res = fusion.fuse_and_evaluate(text_result=dummy_text)
    print("Fusion Result:", res)
