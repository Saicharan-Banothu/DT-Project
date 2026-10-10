"""
SentiCall v2 — Multimodal Fusion Engine & Empathetic Playbook Generator
Fuses calibrated text and acoustic predictions with deterministic safety rules,
generates plain-language verdicts, early detection lead-time summaries,
and custom tailored action plans for victim state chips.
"""

import os
import json
from typing import Dict, Any, Optional, List

TAXONOMY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "taxonomy.json"))
HELPLINES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "helplines.json"))

class FusionEngine:
    def __init__(self, audio_weight: float = 0.35, text_weight: float = 0.65):
        self.audio_weight = audio_weight
        self.text_weight = text_weight
        self._taxonomy = self._load_json(TAXONOMY_PATH)
        self._helplines = self._load_json(HELPLINES_PATH)

    def _load_json(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get_taxonomy_entry(self, family_id: str) -> Dict[str, Any]:
        """Fetch playbook configuration for a scam family."""
        families = self._taxonomy.get("scam_families", [])
        for f in families:
            if f.get("id") == family_id:
                return f
        # Return fallback family 0
        return next((f for f in families if f.get("id") == "no_concern_found"), {
            "id": "no_concern_found",
            "plain_name": "No Concern Found",
            "harm_type": "None",
            "do_now_steps": [{"title": "Keep general phone safety in mind", "detail": "Remember: Real banks never ask for OTPs."}],
            "never_do": ["Never share OTPs."],
            "per_chip_actions": {},
            "safe_replies": ["Thank you. Have a great day."],
            "helpline_ids": ["chakshu", "cybercrime_gov"],
            "evidence_strength": "Learned from real examples"
        })

    def fuse_and_evaluate(
        self,
        text_result: Optional[Dict[str, Any]] = None,
        audio_result: Optional[Dict[str, Any]] = None,
        transcript_text: str = "",
        chosen_chips: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Multimodal fusion with safety rule overrides and personalized action plan rendering.
        """
        has_audio = audio_result is not None and audio_result.get("success", False)
        has_text = text_result is not None and text_result.get("success", False)

        audio_prob = audio_result.get("probability", 0.0) if has_audio else 0.0
        text_prob = text_result.get("probability", 0.0) if has_text else 0.0

        safety_rule_triggered = None
        is_unsure = False

        if has_audio and has_text:
            # Weighted average
            fused_prob = (self.audio_weight * audio_prob) + (self.text_weight * text_prob)

            # Check if models sharply disagree and no strong text rule match
            if abs(audio_prob - text_prob) > 0.55 and not text_result.get("has_critical_indicators", False):
                is_unsure = True

        elif has_text:
            fused_prob = text_prob
        elif has_audio:
            fused_prob = audio_prob
        else:
            fused_prob = 0.0

        # --- SAFETY RULE OVERRIDES (Deterministic Protection Layer) ---
        # Rule: Authority claim + OTP / PIN / CVV / money / remote access request floors at High Risk
        # (because no real bank or government agency asks for credentials/remote access over a phone call).
        if text_result:
            tactic_ids = [t["id"] for t in text_result.get("tactic_breakdown", []) if t.get("detected")]
            
            if "authority_impersonation" in tactic_ids and ("credential_request" in tactic_ids or "remote_access_install" in tactic_ids or "money_transfer_demand" in tactic_ids):
                fused_prob = max(fused_prob, 0.94)
                safety_rule_triggered = "Authority Claim + Secret Code/Money Demand (Strict High Risk Floor)"
            elif "legal_arrest_threat" in tactic_ids:
                fused_prob = max(fused_prob, 0.92)
                safety_rule_triggered = "Digital Arrest / Extortion Threat (Strict High Risk Floor)"
            elif "remote_access_install" in tactic_ids and ("authority_impersonation" in tactic_ids or "urgency_threat" in tactic_ids):
                fused_prob = max(fused_prob, 0.90)
                safety_rule_triggered = "Urgent Remote Desktop Installation Request (Strict High Risk Floor)"

        fused_prob = min(1.0, max(0.0, fused_prob))
        overall_score = int(round(fused_prob * 100))

        # Determine Tier
        if is_unsure and 25 <= overall_score <= 75:
            risk_tier = "Unsure"
            risk_badge_class = "risk-unsure"
            risk_theme_color = "#6366F1"
            verdict_heading = "Inconclusive Call Signs — Caution Advised"
            confidence_words = "Be careful, we're unsure"
        elif overall_score >= 70:
            risk_tier = "High Risk"
            risk_badge_class = "risk-high"
            risk_theme_color = "#DC2626"
            verdict_heading = "High Likelihood of a Voice Scam (Vishing)"
            confidence_words = "We're very sure"
        elif overall_score >= 36:
            risk_tier = "Moderate Risk"
            risk_badge_class = "risk-moderate"
            risk_theme_color = "#D97706"
            verdict_heading = "Caution Advised — Suspicious Manipulation Signs"
            confidence_words = "We're fairly sure"
        else:
            risk_tier = "Low Risk"
            risk_badge_class = "risk-low"
            risk_theme_color = "#059669"
            verdict_heading = "Call Appears Safe and Normal"
            confidence_words = "Normal conversation signs"

        # Lookup Scam Family from Taxonomy
        primary_family_id = text_result.get("primary_family_id", "no_concern_found") if text_result else "no_concern_found"
        if overall_score < 36:
            primary_family_id = "no_concern_found"

        taxonomy_entry = self.get_taxonomy_entry(primary_family_id)

        # Generate Plain-Language Summary
        summary_sentence = self._generate_warm_summary(
            risk_tier=risk_tier,
            primary_family_name=taxonomy_entry.get("plain_name", ""),
            text_result=text_result,
            safety_rule=safety_rule_triggered,
            is_unsure=is_unsure
        )

        # Build Action Plan Tailored to Selected Chips
        action_plan = self._build_personalized_plan(taxonomy_entry, chosen_chips or [])

        # Fetch Relevant Helplines
        relevant_helplines = self._get_relevant_helplines(taxonomy_entry.get("helpline_ids", ["1930", "cybercrime_gov"]))

        return {
            "overall_score": overall_score,
            "risk_tier": risk_tier,
            "confidence_words": confidence_words,
            "risk_badge_class": risk_badge_class,
            "risk_theme_color": risk_theme_color,
            "verdict_heading": verdict_heading,
            "summary_sentence": summary_sentence,
            "primary_family_id": primary_family_id,
            "primary_family_name": taxonomy_entry.get("name", "General Voice Analysis"),
            "harm_type": taxonomy_entry.get("harm_type", "None"),
            "evidence_strength": taxonomy_entry.get("evidence_strength", "Learned from real examples"),
            "evidence_count": taxonomy_entry.get("evidence_count", 0),
            "safety_rule_triggered": safety_rule_triggered,
            "is_unsure": is_unsure,
            "action_plan": action_plan,
            "helplines": relevant_helplines,
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
        primary_family_name: str,
        text_result: Optional[Dict[str, Any]],
        safety_rule: Optional[str],
        is_unsure: bool
    ) -> str:
        """Create a clear, non-technical sentence explaining why the verdict was reached."""
        if is_unsure:
            return "We cannot reach a confident verdict on this call. Legitimate organizations never pressure you over the phone—when in doubt, hang up and call back on a trusted number."

        if risk_tier == "High Risk":
            if text_result:
                tactics = [t["title"].lower() for t in text_result.get("tactic_breakdown", []) if t.get("detected")]
                if "asking for passwords, otp, or money" in tactics and "pretending to be an authority" in tactics:
                    return "This call impersonates an official representative and asks for your secret OTP or passwords — a well-documented trap used to drain bank accounts."
                elif "creating false urgency or pressure" in tactics and "requesting sensitive identity details" in tactics:
                    return "This call creates artificial panic about your SIM card or account expiring to rush you into sharing sensitive personal identity details."
                elif "asking you to install an app or share your screen" in tactics:
                    return "This caller is attempting to trick you into installing remote desktop software to secretly take control of your phone and banking apps."
                elif "threatening arrest or legal consequences" in tactics:
                    return "This call uses fake police badges or digital arrest ultimatums to extort money. Real law enforcement officers never conduct trials or arrest people over phone calls."
                elif "dangling a fake prize, lottery or reward" in tactics:
                    return "This call claims you won an unsolicited prize or lottery payout — a classic lure designed to trick you into paying advance fees."
            return f"This call exhibits deceptive patterns consistent with {primary_family_name} scams."

        elif risk_tier == "Moderate Risk":
            return f"This call contains subtle pressure signals ({primary_family_name}); we strongly recommend verifying the caller's identity through official channels before taking action."

        else:
            return "This conversation flows naturally like an everyday phone call, with zero signs of impersonation, urgency traps, or credential requests."

    def _build_personalized_plan(self, taxonomy_entry: Dict[str, Any], chosen_chips: List[str]) -> Dict[str, Any]:
        """Construct 'Do This Now' steps, dynamic chip adaptations, and safe replies."""
        do_now_steps = taxonomy_entry.get("do_now_steps", [])
        never_do = taxonomy_entry.get("never_do", [])
        per_chip = taxonomy_entry.get("per_chip_actions", {})
        safe_replies = taxonomy_entry.get("safe_replies", [
            "I do not share sensitive information over the phone.",
            "I will verify this directly with the official customer support office."
        ])

        # Extra dynamic steps based on user state chips
        adapted_steps = []
        for chip in chosen_chips:
            if chip in per_chip:
                chip_name = chip.replace("_", " ").title()
                adapted_steps.append({
                    "trigger_chip": chip,
                    "chip_label": chip_name,
                    "action_text": per_chip[chip]
                })

        return {
            "headline": f"Immediate Action Plan: {taxonomy_entry.get('plain_name', 'General Safety')}",
            "do_now_steps": do_now_steps[:3],
            "never_do": never_do,
            "adapted_chip_steps": adapted_steps,
            "per_chip_actions": per_chip,
            "safe_replies": safe_replies,
            "how_it_works": taxonomy_entry.get("how_it_works", []),
            "golden_rule": "When in doubt, hang up and call back on a number you trust."
        }

    def _get_relevant_helplines(self, helpline_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch helpline details from data/helplines.json."""
        all_helplines = self._helplines.get("helplines", [])
        result = []
        for h in all_helplines:
            if h.get("id") in helpline_ids or h.get("is_primary"):
                result.append(h)
        return result
