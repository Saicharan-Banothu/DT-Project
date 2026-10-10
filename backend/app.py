import os
import glob
import tempfile
import shutil
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.asr_bridge import transcribe_audio_file
from backend.audio_pipeline import analyze_audio
from backend.text_pipeline import analyze_text
from backend.fusion_engine import FusionEngine
from backend.audio_pipeline import get_audio_model
from backend.text_pipeline import get_text_model

app = FastAPI(
    title="SentiCall API",
    description="The Third Voice: AI-Powered Voice Scam & Vishing Detection Backend",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fusion_engine = FusionEngine(audio_weight=0.35, text_weight=0.65)

# Pydantic schemas
class TextAnalysisRequest(BaseModel):
    text: str
    sample_id: Optional[str] = None

# Audio file directory map
NORMAL_AUDIO_DIR = os.path.abspath("Normal calls")
SCAM_AUDIO_DIR = os.path.abspath("Scam calls")

@app.get("/api/health")
def health_check():
    audio_bundle = get_audio_model()
    text_bundle = get_text_model()
    return {
        "status": "online",
        "audio_model_loaded": audio_bundle is not None,
        "text_model_loaded": text_bundle is not None
    }

@app.get("/api/metrics")
def get_metrics():
    """Return real cross-validated metrics for both pipelines."""
    audio_bundle = get_audio_model()
    text_bundle = get_text_model()

    return {
        "audio_pipeline": audio_bundle.get("cv_metrics", {}) if audio_bundle else None,
        "text_pipeline": text_bundle.get("cv_metrics", {}) if text_bundle else None
    }

@app.get("/api/samples")
def get_samples():
    """Return pre-configured audio and text sample calls for one-click testing."""
    # List actual audio files
    normal_audio_list = sorted([os.path.basename(f) for f in glob.glob(os.path.join(NORMAL_AUDIO_DIR, "*.*"))])
    scam_audio_list = sorted([os.path.basename(f) for f in glob.glob(os.path.join(SCAM_AUDIO_DIR, "*.*"))])

    audio_samples = [
        {
            "id": "audio_scam_1",
            "title": "SBI Debit Card Expiry Scam Call",
            "type": "scam",
            "badge": "Simulated Bank Scam",
            "filename": scam_audio_list[0] if scam_audio_list else "scam_1.mp3",
            "description": "Caller pretends to be an SBI bank manager claiming debit card is expiring and requests an OTP to renew."
        },
        {
            "id": "audio_scam_2",
            "title": "Telecom SIM Deactivation Alert",
            "type": "scam",
            "badge": "Simulated Telecom Scam",
            "filename": scam_audio_list[1] if len(scam_audio_list) > 1 else (scam_audio_list[0] if scam_audio_list else "scam_2.mp3"),
            "description": "Urgent automated call threatening mobile SIM suspension within 23 hours unless verified."
        },
        {
            "id": "audio_scam_3",
            "title": "Cash Prize & Lottery Award Lure",
            "type": "scam",
            "badge": "Simulated Prize Scam",
            "filename": scam_audio_list[2] if len(scam_audio_list) > 2 else (scam_audio_list[0] if scam_audio_list else "scam_3.mp3"),
            "description": "Caller claims your phone number won an exclusive cash award and asks for claim verification."
        },
        {
            "id": "audio_normal_1",
            "title": "Casual Weekend Family Catchup",
            "type": "normal",
            "badge": "Normal Conversation",
            "filename": normal_audio_list[0] if normal_audio_list else "normal_1.mp3",
            "description": "Everyday casual phone conversation between friends discussing travel and daily plans."
        },
        {
            "id": "audio_normal_2",
            "title": "Doctor Appointment Reminder",
            "type": "normal",
            "badge": "Normal Conversation",
            "filename": normal_audio_list[1] if len(normal_audio_list) > 1 else (normal_audio_list[0] if normal_audio_list else "normal_2.mp3"),
            "description": "Friendly check-in and schedule confirmation with natural everyday speech."
        }
    ]

    text_samples = [
        {
            "id": "text_scam_1",
            "title": "SBI Card Expiry & OTP Request",
            "type": "scam",
            "badge": "Bank Fraud Pattern",
            "text": "hello, i m bank manager of SBI, ur debit card is about to expire would u want to issue new card. please tell me the four digit otp sent to your mobile.",
            "description": "Classic authority claim combined with urgent OTP extraction."
        },
        {
            "id": "text_scam_2",
            "title": "Jio SIM 23-Hour Deactivation Threat",
            "type": "scam",
            "badge": "Telecom Pressure",
            "text": "hello sir, i am from jio customer care in 23 hours your sim will be closed. do u want to activate it. please confirm your aadhaar and account details.",
            "description": "Threatens service closure to force instant credential disclosure."
        },
        {
            "id": "text_scam_3",
            "title": "HDFC Bank Online KYC Emergency",
            "type": "scam",
            "badge": "KYC Identity Trap",
            "text": "hello sir this is your hdfc bank manager. your kyc has been expired. so you have to kyc your self online immediately, please tell me your account detail and pan card number.",
            "description": "Exploits KYC anxiety to extract full banking details."
        },
        {
            "id": "text_scam_4",
            "title": "Vodafone £350 Award Notification",
            "type": "scam",
            "badge": "Lottery Lure",
            "text": "Todays Vodafone numbers ending with 4882 are selected to receive a £350 award. If your number matches call 09064019014 to claim your cash prize.",
            "description": "Promises unsolicited prize money to lure victims into toll fraud."
        },
        {
            "id": "text_normal_1",
            "title": "Family Train Journey Update",
            "type": "normal",
            "badge": "Safe Everyday Message",
            "text": "Allo! We have braved the buses and taken on the trains and triumphed. I mean we are in b'ham. Have a jolly good rest of the week!",
            "description": "Normal, unscripted friendly text with zero pressure tactics."
        },
        {
            "id": "text_normal_2",
            "title": "Thanksgiving Restock Conversation",
            "type": "normal",
            "badge": "Safe Everyday Message",
            "text": "Well i am definitely in need to restock before thanksgiving, I'll let you know when I'm out. See you on Tuesday afternoon!",
            "description": "Everyday casual reminder and informal chat."
        }
    ]

    return {
        "audio_samples": audio_samples,
        "text_samples": text_samples
    }

@app.get("/api/audio/{filename}")
def stream_audio(filename: str):
    """Serve audio sample file from Normal or Scam calls folder."""
    # Check scam calls folder
    scam_path = os.path.join(SCAM_AUDIO_DIR, filename)
    if os.path.exists(scam_path):
        return FileResponse(scam_path, media_type="audio/mpeg")

    # Check normal calls folder
    normal_path = os.path.join(NORMAL_AUDIO_DIR, filename)
    if os.path.exists(normal_path):
        return FileResponse(normal_path, media_type="audio/mpeg")

    raise HTTPException(status_code=404, detail="Audio file not found")

@app.post("/api/analyze-audio")
async def analyze_audio_endpoint(
    audio_file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    sample_filename: Optional[str] = Form(None)
):
    """
    Multimodal analysis: Audio acoustic model + Local Whisper Speech-to-Text + Text linguistic model + Tactic tagging + Fusion.
    """
    temp_path = None
    target_audio_path = None

    try:
        if audio_file and audio_file.filename:
            # User uploaded a custom audio file
            suffix = os.path.splitext(audio_file.filename)[1] or ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                temp_path = tmp.name
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(audio_file.file, buffer)
            target_audio_path = temp_path
            input_source_name = audio_file.filename

        elif sample_filename:
            # User picked one of the built-in audio samples
            scam_candidate = os.path.join(SCAM_AUDIO_DIR, sample_filename)
            normal_candidate = os.path.join(NORMAL_AUDIO_DIR, sample_filename)

            if os.path.exists(scam_candidate):
                target_audio_path = scam_candidate
            elif os.path.exists(normal_candidate):
                target_audio_path = normal_candidate
            else:
                raise HTTPException(status_code=404, detail=f"Sample audio file '{sample_filename}' not found.")
            input_source_name = sample_filename
        else:
            raise HTTPException(status_code=400, detail="Please upload an audio file or select a sample call.")

        # Step 1: Acoustic Pipeline (XGBoost on audio features)
        audio_result = analyze_audio(target_audio_path)

        # Step 2: Speech-to-Text Bridge (Local Whisper ASR)
        asr_result = transcribe_audio_file(target_audio_path)
        transcript = asr_result.get("text", "")

        # Step 3: Text Pipeline (if transcript extracted)
        text_result = None
        if transcript:
            text_result = analyze_text(transcript)
        else:
            # If speech couldn't be transcribed (e.g. background noise/no speech detected),
            # provide clean neutral text result
            text_result = {
                "success": False,
                "text_risk_score": 0,
                "probability": 0.0,
                "tactics_detected": [],
                "tactic_breakdown": [],
                "highlights": [],
                "highlighted_html": "",
                "linguistic_signals": ["Audio recording contains no clear conversational speech."]
            }

        # Step 4: Fusion & Explanation Layer
        fusion_result = fusion_engine.fuse_and_evaluate(
            text_result=text_result,
            audio_result=audio_result,
            transcript_text=transcript
        )

        return {
            "input_type": "audio",
            "source_name": input_source_name,
            "transcript": transcript,
            "transcript_method": asr_result.get("method", "local"),
            "audio_result": audio_result,
            "text_result": text_result,
            "fusion": fusion_result
        }

    finally:
        # Cleanup temporary uploaded file if any
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@app.post("/api/analyze-text")
def analyze_text_endpoint(payload: TextAnalysisRequest):
    """
    Text-only analysis: TF-IDF + Classifier + Tactic tagging + Fusion.
    """
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    # Step 1: Text Linguistic Pipeline
    text_result = analyze_text(text)

    # Step 2: Fusion & Plain-Language Explanation
    fusion_result = fusion_engine.fuse_and_evaluate(
        text_result=text_result,
        audio_result=None,
        transcript_text=text
    )

    return {
        "input_type": "text",
        "transcript": text,
        "text_result": text_result,
        "audio_result": None,
        "fusion": fusion_result
    }

# Serve frontend static assets
frontend_dir = os.path.abspath("frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "SentiCall Backend is running. Frontend index.html not yet built."}
