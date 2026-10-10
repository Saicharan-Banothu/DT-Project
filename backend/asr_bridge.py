import os
import tempfile
import numpy as np
import librosa
import soundfile as sf
import speech_recognition as sr_module

_whisper_model = None

def get_whisper_model():
    """Lazy load Whisper model to keep startup fast and conserve memory."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            print("Loading local OpenAI Whisper model ('tiny')...")
            _whisper_model = whisper.load_model("tiny")
            print("Whisper model loaded successfully.")
        except Exception as e:
            print(f"Notice: Whisper load deferred or fallback used: {e}")
            _whisper_model = False
    return _whisper_model

def transcribe_audio_file(audio_path: str) -> dict:
    """
    Transcribe an audio file using local OpenAI Whisper with robust fallback.
    Returns: {
        'text': str,
        'duration_seconds': float,
        'method': str,
        'success': bool
    }
    """
    try:
        # Load and verify audio with librosa
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        duration = float(librosa.get_duration(y=y, sr=sr))
    except Exception as e:
        return {
            'text': "",
            'duration_seconds': 0.0,
            'method': 'error',
            'success': False,
            'error': str(e)
        }

    # 1. Try OpenAI Whisper (Local, offline)
    whisper_model = get_whisper_model()
    if whisper_model:
        try:
            # Whisper can transcribe float32 audio arrays or wav paths
            # Write to a clean temporary WAV file for Whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            sf.write(tmp_path, y, sr)

            result = whisper_model.transcribe(tmp_path, fp16=False)
            try:
                os.remove(tmp_path)
            except Exception:
                pass

            transcription = result.get("text", "").strip()
            if transcription:
                return {
                    'text': transcription,
                    'duration_seconds': duration,
                    'method': 'whisper-local',
                    'success': True
                }
        except Exception as we:
            print(f"Whisper inference notice: {we}, attempting speech recognition fallback...")

    # 2. Fallback: SpeechRecognition library
    try:
        r = sr_module.Recognizer()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, y, sr)

        with sr_module.AudioFile(tmp_path) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data)
            try:
                os.remove(tmp_path)
            except Exception:
                pass

            return {
                'text': text.strip(),
                'duration_seconds': duration,
                'method': 'speech-recognition-engine',
                'success': True
            }
    except Exception as se:
        # If offline without whisper, return clean indicator
        return {
            'text': "",
            'duration_seconds': duration,
            'method': 'acoustic-only',
            'success': False,
            'note': 'Speech could not be converted to text; acoustic analysis performed.'
        }

if __name__ == "__main__":
    import glob
    samples = glob.glob("Scam calls/*.mp3") + glob.glob("Normal calls/*.mp3")
    if samples:
        print("Testing transcription on:", samples[0])
        res = transcribe_audio_file(samples[0])
        print("Result:", res)
