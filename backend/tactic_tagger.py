"""
SentiCall v3 — Shared Tactic Tagger & Multilingual Manipulation Detector
Synchronized with data/tactics.json for zero drift between Python and JavaScript engines.
Extracts multi-label manipulation tactics across English and Hinglish phrasings.
Handles negation and warning contexts ("never share your OTP", "we will not ask for your PIN").
"""

import os
import re
import json
from typing import List, Dict, Any, Tuple

TACTICS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "tactics.json"))

_TACTICS_CACHE = None

def get_tactics_data() -> Dict[str, Any]:
    global _TACTICS_CACHE
    if _TACTICS_CACHE is not None:
        return _TACTICS_CACHE
    if os.path.exists(TACTICS_PATH):
        try:
            with open(TACTICS_PATH, "r", encoding="utf-8") as f:
                _TACTICS_CACHE = json.load(f)
                return _TACTICS_CACHE
        except Exception as e:
            print(f"Error loading tactics.json: {e}")
    return {"tactics": [], "safety_rules": {"negation_patterns": []}}


def find_negation_spans(text: str, negation_patterns: List[str]) -> List[Tuple[int, int]]:
    """Find character ranges of negation/warning sentences to prevent false alerts."""
    spans = []
    t_lower = text.lower()
    for pat in negation_patterns:
        try:
            for m in re.finditer(pat, t_lower):
                spans.append((m.start(), m.end()))
        except Exception:
            continue
    return spans


def is_in_negation(start: int, end: int, neg_spans: List[Tuple[int, int]]) -> bool:
    """Check if a match overlap with a negation/warning statement."""
    for n_start, n_end in neg_spans:
        # Check if match is inside or substantially overlaps negation span
        if not (end <= n_start or start >= n_end):
            return True
    return False


def detect_all_tactics(text: str) -> Dict[str, Any]:
    """
    Run regex pattern matching across all tactics loaded from data/tactics.json.
    Excludes phrases inside legitimate negation warnings.
    Returns list of tactic hits, highlights, and critical safety indicator flag.
    """
    data = get_tactics_data()
    tactics = data.get("tactics", [])
    safety = data.get("safety_rules", {})
    negation_patterns = safety.get("negation_patterns", [])

    t_lower = text.lower()
    neg_spans = find_negation_spans(t_lower, negation_patterns)

    tactic_hits = []
    has_critical = False
    highlights = []

    for item in tactics:
        en_matches = list(re.finditer(item["regex"], t_lower)) if item.get("regex") else []
        hi_matches = list(re.finditer(item["hinglish_regex"], t_lower)) if item.get("hinglish_regex") else []
        all_m = en_matches + hi_matches

        # Filter out matches that appear in a negation context
        valid_matches = []
        for m in all_m:
            if not is_in_negation(m.start(), m.end(), neg_spans):
                valid_matches.append(m)

        if valid_matches:
            matched_phrases = list(set([m.group(0).strip() for m in valid_matches]))
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

            for m in valid_matches:
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
        if h["start"] > curr_pos:
            pre_text = text[curr_pos : h["start"]]
            html_parts.append(pre_text)

        hl_phrase = text[h["start"] : h["end"]]
        t_id = h["tactic_id"]
        sev = h["severity"]
        title = h["tactic_title"]

        pill_class = f"tactic-pill pill-{sev}"
        html_parts.append(f'<mark class="{pill_class}" data-tactic="{t_id}" title="{title}">{hl_phrase}</mark>')
        curr_pos = h["end"]

    if curr_pos < len(text):
        html_parts.append(text[curr_pos:])

    return "".join(html_parts)


def tag_manipulation_tactics(text: str) -> List[Dict[str, Any]]:
    """Helper returning list of tactic breakdown hits."""
    return detect_all_tactics(text).get("tactic_breakdown", [])

