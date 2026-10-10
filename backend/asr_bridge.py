"""
SentiCall v2 — Offline Speech-to-Text Bridge (faster-whisper + language detection + translation)
Provides word-level timestamps, language detection (Hindi/Telugu/English), and offline caching.
"""

import os
import json
import hashlib
import tempfile
from typing import Dict, Any, List, Optional

_WHISPER_MODEL = None
_ENGINE_TYPE = None

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_FILE = os.path.join(BASE_DIR, "data", "transcripts", "transcripts_cache.json")

def get_file_sha256(filepath: str) -> str:
    """Compute sha256 hash of audio file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def load_cached_transcripts() -> Dict[str, Any]:
    """Load pre-computed transcripts from disk."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def get_whisper_engine():
    """Lazy load faster-whisper (or fallback to openai-whisper)."""
    global _WHISPER_MODEL, _ENGINE_TYPE
    if _WHISPER_MODEL is not None:
        return _ENGINE_TYPE, _WHISPER_MODEL

    try:
        from faster_whisper import WhisperModel
        print("Loading faster-whisper base model (offline quantized int8)...")
        _WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
        _ENGINE_TYPE = "faster_whisper"
        return _ENGINE_TYPE, _WHISPER_MODEL
    except Exception as e:
        print(f"faster-whisper load failed ({e}), falling back to openai-whisper...")
        try:
            import whisper
            _WHISPER_MODEL = whisper.load_model("base")
            _ENGINE_TYPE = "openai_whisper"
            return _ENGINE_TYPE, _WHISPER_MODEL
        except Exception as e2:
            print(f"Whisper fallback failed: {e2}")
            return "none", None

def transcribe_audio_file(audio_path: str, task: str = "transcribe") -> Dict[str, Any]:
    """
    Transcribe audio file on device with word-level timestamps and language detection.
    Returns:
    {
        "text": full_transcript_text,
        "language": "en" | "hi" | "te" | ...,
        "language_probability": 0.98,
        "is_translated": bool,
        "original_text": str (if translated),
        "segments": [{ "start": float, "end": float, "text": str, "words": [...] }],
        "method": "cached" | "faster-whisper" | "openai-whisper"
    }
    """
    fname = os.path.basename(audio_path)
    cache = load_cached_transcripts()

    # 1. Fast path: check transcript cache by filename
    if fname in cache:
        c_entry = cache[fname]
        return {
            "text": c_entry.get("text", ""),
            "language": c_entry.get("language", "en"),
            "language_probability": 0.99,
            "is_translated": False,
            "original_text": c_entry.get("text", ""),
            "segments": c_entry.get("segments", []),
            "method": "cached_dataset_transcript"
        }

    # 2. Offline Inference
    engine_type, model = get_whisper_engine()

    if engine_type == "faster_whisper" and model is not None:
        try:
            segments_gen, info = model.transcribe(audio_path, beam_size=2, word_timestamps=True, task=task)
            detected_lang = info.language
            lang_prob = round(info.language_probability, 2)

            segments = []
            full_text_list = []

            for s in segments_gen:
                words = []
                if s.words:
                    for w in s.words:
                        words.append({
                            "word": w.word.strip(),
                            "start": round(w.start, 2),
                            "end": round(w.end, 2),
                            "probability": round(w.probability, 2)
                        })
                segments.append({
                    "start": round(s.start, 2),
                    "end": round(s.end, 2),
                    "text": s.text.strip(),
                    "words": words
                })
                full_text_list.append(s.text.strip())

            full_text = " ".join(full_text_list)

            # If language is non-English, generate optional English translation
            translated_text = None
            if detected_lang in ["hi", "te", "ta", "mr", "bn", "gu", "kn"]:
                try:
                    trans_segs, _ = model.transcribe(audio_path, beam_size=2, task="translate")
                    translated_text = " ".join([ts.text.strip() for ts in trans_segs])
                except Exception:
                    pass

            return {
                "text": full_text if not translated_text else translated_text,
                "language": detected_lang,
                "language_probability": lang_prob,
                "is_translated": bool(translated_text is not None),
                "original_text": full_text,
                "segments": segments,
                "method": "faster-whisper"
            }
        except Exception as ex:
            print(f"faster-whisper transcription error: {ex}")

    elif engine_type == "openai_whisper" and model is not None:
        try:
            res = model.transcribe(audio_path, word_timestamps=True)
            detected_lang = res.get("language", "en")
            full_text = res.get("text", "").strip()
            segments = []
            for s in res.get("segments", []):
                words = []
                if "words" in s:
                    for w in s["words"]:
                        words.append({
                            "word": w.get("word", "").strip(),
                            "start": round(w.get("start", 0.0), 2),
                            "end": round(w.get("end", 0.0), 2),
                            "probability": round(w.get("probability", 0.9), 2)
                        })
                segments.append({
                    "start": round(s.get("start", 0.0), 2),
                    "end": round(s.get("end", 0.0), 2),
                    "text": s.get("text", "").strip(),
                    "words": words
                })
            return {
                "text": full_text,
                "language": detected_lang,
                "language_probability": 0.95,
                "is_translated": False,
                "original_text": full_text,
                "segments": segments,
                "method": "openai-whisper"
            }
        except Exception as ex2:
            print(f"openai-whisper transcription error: {ex2}")

    # Fallback if audio could not be transcribed
    return {
        "text": "",
        "language": "en",
        "language_probability": 0.0,
        "is_translated": False,
        "original_text": "",
        "segments": [],
        "method": "untranscribed_fallback"
    }
