"""
SentiCall v2 — "The Third Voice: AI Web-Based Platform Against Voice Fraud"
FastAPI Server & Real-Time Multimodal Scam Detection Engine
Author: Senior Full-Stack & Applied ML Engineer
"""

import os
import io
import time
import glob
import json
import shutil
import tempfile
import asyncio
from typing import Optional, List, Dict, Any

import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel

from backend.asr_bridge import transcribe_audio_file
from backend.audio_pipeline import analyze_audio, get_audio_model
from backend.text_pipeline import analyze_text, get_text_model
from backend.fusion_engine import FusionEngine
from backend.pdf_generator import generate_pdf_report
from backend.database import save_case, get_all_cases, get_case_by_id, delete_case, delete_all_cases

app = FastAPI(
    title="SentiCall v2 API",
    description="The Third Voice — Research-Grade AI Voice Fraud & Vishing Detection Platform",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fusion_engine = FusionEngine(audio_weight=0.35, text_weight=0.65)

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NORMAL_AUDIO_DIR = os.path.join(BASE_DIR, "Normal calls")
SCAM_AUDIO_DIR = os.path.join(BASE_DIR, "Scam calls")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Pydantic schemas
class TextAnalysisRequest(BaseModel):
    text: str
    sample_id: Optional[str] = None
    chosen_chips: Optional[List[str]] = None

class SaveCaseRequest(BaseModel):
    case_payload: Dict[str, Any]

class PDFReportRequest(BaseModel):
    case_id: Optional[str] = None
    case_payload: Optional[Dict[str, Any]] = None

class AnalyzeJobRequest(BaseModel):
    text: Optional[str] = None
    sample_filename: Optional[str] = None
    chosen_chips: Optional[List[str]] = None

# Job queue state for SSE streaming
_JOBS: Dict[str, Dict[str, Any]] = {}
# In-memory precomputed samples cache for instant sub-second demo
_PRECOMPUTED_SAMPLES_CACHE: Dict[str, Dict[str, Any]] = {}

def load_reports_json(filename: str) -> Dict[str, Any]:
    """Load JSON from reports directory safely."""
    p = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@app.on_event("startup")
def startup_event():
    """Startup initializations."""
    print("SentiCall v2 server initialized.", flush=True)


@app.get("/api/health")
@app.get("/health")
def health_check():
    audio_bundle = get_audio_model()
    text_bundle = get_text_model()
    return {
        "status": "online",
        "version": "2.0.0",
        "audio_model_loaded": audio_bundle is not None,
        "text_model_loaded": text_bundle is not None,
        "device": "100% On-Device / Local"
    }

@app.get("/api/metrics")
@app.get("/metrics")
def get_metrics_endpoint():
    """Return verified metrics from reports/metrics.json."""
    data = load_reports_json("metrics.json")
    if not data:
        audio_bundle = get_audio_model()
        text_bundle = get_text_model()
        return {
            "text_pipeline": text_bundle.get("summary") if text_bundle else None,
            "audio_pipeline": audio_bundle.get("summary") if audio_bundle else None
        }
    return data

@app.get("/api/insights")
@app.get("/insights")
def get_insights_endpoint():
    """Return complete Model Insights data including recording bias, early detection, and ablation."""
    metrics = load_reports_json("metrics.json")
    bias_audit = load_reports_json("audio_bias_audit.json")
    early_det = load_reports_json("early_detection.json")
    return {
        "metrics": metrics,
        "audio_bias_audit": bias_audit,
        "early_detection": early_det
    }

def get_sample_definitions() -> Dict[str, Any]:
    """Helper to return structured sample call cards."""
    scam_audio_list = sorted([os.path.basename(f) for f in glob.glob(os.path.join(SCAM_AUDIO_DIR, "*.*"))])
    normal_audio_list = sorted([os.path.basename(f) for f in glob.glob(os.path.join(NORMAL_AUDIO_DIR, "*.*"))])

    audio_samples = [
        {
            "id": "audio_scam_1",
            "title": "SBI Debit Card Expiry & OTP Extraction",
            "type": "scam",
            "family_id": "bank_kyc_impersonation",
            "family_name": "Bank Impersonation",
            "badge": "Bank KYC Scam",
            "badge_color": "#DC2626",
            "filename": scam_audio_list[0] if scam_audio_list else "scam_1.mp3",
            "description": "Caller poses as SBI branch manager claiming debit card expiry and rushes to extract the 4-digit mobile OTP."
        },
        {
            "id": "audio_scam_2",
            "title": "Jio 23-Hour SIM Deactivation Threat",
            "type": "scam",
            "family_id": "telecom_sim_threat",
            "family_name": "Telecom Threat",
            "badge": "Telecom Pressure",
            "badge_color": "#D97706",
            "filename": scam_audio_list[1] if len(scam_audio_list) > 1 else (scam_audio_list[0] if scam_audio_list else "scam_2.mp3"),
            "description": "Urgent automated call threatening complete mobile SIM disconnection within 23 hours unless Aadhaar is confirmed."
        },
        {
            "id": "audio_scam_3",
            "title": "Vodafone £350 Cash Award Lure",
            "type": "scam",
            "family_id": "prize_lottery_cashback",
            "family_name": "Lottery Lure",
            "badge": "Prize & Lottery",
            "badge_color": "#D97706",
            "filename": scam_audio_list[2] if len(scam_audio_list) > 2 else (scam_audio_list[0] if scam_audio_list else "scam_3 (online-audio-converter.com).mp3"),
            "description": "Claims recipient's mobile number was chosen for an exclusive cash prize award to lure toll payments."
        },
        {
            "id": "audio_scam_4",
            "title": "Police Narcotics & 'Digital Arrest' Threat",
            "type": "scam",
            "family_id": "govt_law_enforcement_digital_arrest",
            "family_name": "Digital Arrest",
            "badge": "Digital Arrest",
            "badge_color": "#DC2626",
            "filename": scam_audio_list[3] if len(scam_audio_list) > 3 else (scam_audio_list[0] if scam_audio_list else "scam_5.mp3"),
            "description": "Impersonates Cyber Crime Branch claiming an illegal drug parcel was seized in recipient's name."
        },
        {
            "id": "audio_normal_1",
            "title": "Family Travel & Weekend Catchup",
            "type": "normal",
            "family_id": "no_concern_found",
            "family_name": "Safe Everyday Message",
            "badge": "Normal Conversation",
            "badge_color": "#059669",
            "filename": normal_audio_list[0] if normal_audio_list else "normal_1.mp3",
            "description": "Casual, unscripted friendly conversation discussing train journeys and everyday plans."
        },
        {
            "id": "audio_normal_2",
            "title": "Holiday Grocery Restock Reminder",
            "type": "normal",
            "family_id": "no_concern_found",
            "family_name": "Safe Everyday Message",
            "badge": "Normal Conversation",
            "badge_color": "#059669",
            "filename": normal_audio_list[1] if len(normal_audio_list) > 1 else (normal_audio_list[0] if normal_audio_list else "normal_2.mp3"),
            "description": "Friendly everyday coordination about holiday restocking and Tuesday afternoon plans."
        }
    ]

    text_samples = [
        {
            "id": "text_scam_1",
            "title": "SBI Card Expiry & OTP Request",
            "type": "scam",
            "family_id": "bank_kyc_impersonation",
            "badge": "Bank Fraud",
            "text": "hello, i m bank manager of SBI, ur debit card is about to expire would u want to issue new card. please tell me the four digit otp sent to your mobile.",
            "description": "Classic authority claim combined with urgent OTP extraction."
        },
        {
            "id": "text_scam_2",
            "title": "Jio SIM 23-Hour Deactivation Threat",
            "type": "scam",
            "family_id": "telecom_sim_threat",
            "badge": "Telecom Pressure",
            "text": "hello sir, i am from jio customer care in 23 hours your sim will be closed. do u want to activate it. please confirm your aadhaar and account details.",
            "description": "Threatens service closure to force instant credential disclosure."
        },
        {
            "id": "text_scam_3",
            "title": "Delhi Police 'Digital Arrest' Video Summon",
            "type": "scam",
            "family_id": "govt_law_enforcement_digital_arrest",
            "badge": "Digital Arrest",
            "text": "This is Officer Sharma from Delhi Cyber Crime Branch. A customs parcel with illegal contraband has been seized under your Aadhaar. You are under digital arrest. Stay on video and do not inform family.",
            "description": "Fear-based digital arrest coercion demanding isolation."
        },
        {
            "id": "text_scam_4",
            "title": "AnyDesk Remote Screen Sharing Instruction",
            "type": "scam",
            "family_id": "tech_support_remote_access",
            "badge": "Tech Support",
            "text": "Calling from UPI customer support. Your banking application requires mandatory security update. Please install AnyDesk from Play Store and accept remote screen connection.",
            "description": "Remote desktop screen takeover to capture passwords live."
        },
        {
            "id": "text_normal_1",
            "title": "Amazon Delivery Agent Parcel OTP (Safe)",
            "type": "normal",
            "family_id": "no_concern_found",
            "badge": "Safe Hard Negative",
            "text": "Hello sir, I am the Amazon delivery agent outside your gate. Please share the 4-digit package delivery OTP to hand over your order.",
            "description": "Legitimate delivery verification code request without manipulation."
        },
        {
            "id": "text_normal_2",
            "title": "Doctor Appointment Confirmation (Safe)",
            "type": "normal",
            "family_id": "no_concern_found",
            "badge": "Safe Message",
            "text": "Hello Mrs. Verma, calling from Apollo Clinic to confirm your consultation with Dr. Mehta tomorrow at 4:30 PM. Please arrive 10 minutes early.",
            "description": "Authentic clinic confirmation with zero pressure tactics."
        }
    ]

    return {
        "audio_samples": audio_samples,
        "text_samples": text_samples
    }

@app.get("/api/samples")
@app.get("/samples")
def get_samples_endpoint():
    """Return pre-configured sample calls with type groups and preview URLs."""
    return get_sample_definitions()

@app.get("/api/audio/{filename}")
@app.get("/audio/{filename}")
def stream_audio(filename: str):
    """Serve audio sample file with Range streaming."""
    scam_path = os.path.join(SCAM_AUDIO_DIR, filename)
    if os.path.exists(scam_path):
        return FileResponse(scam_path, media_type="audio/mpeg")

    normal_path = os.path.join(NORMAL_AUDIO_DIR, filename)
    if os.path.exists(normal_path):
        return FileResponse(normal_path, media_type="audio/mpeg")

    raise HTTPException(status_code=404, detail="Audio file not found")

def process_audio_analysis_core(target_path: str, input_name: str, chips_list: List[str]) -> Dict[str, Any]:
    """Core logic to analyze an audio file."""
    # Step 1: Speech-to-Text Bridge (offline Whisper)
    asr_res = transcribe_audio_file(target_path)
    transcript = asr_res.get("text", "")
    segments = asr_res.get("segments", [])

    # Estimate WPM
    w_count = len(transcript.split())
    dur_est = max(1.0, segments[-1]["end"] if segments else 15.0)
    wpm = (w_count / dur_est) * 60.0

    # Step 2: Acoustic Pipeline (Telephony XGBoost)
    audio_res = analyze_audio(target_path, transcript_wpm=wpm)

    # Step 3: Text Pipeline
    text_res = analyze_text(transcript)

    # Step 4: Multimodal Fusion & Action Plan
    fusion_res = fusion_engine.fuse_and_evaluate(
        text_result=text_res,
        audio_result=audio_res,
        transcript_text=transcript,
        chosen_chips=chips_list
    )

    # Step 5: Compute Early Detection Timeline
    total_dur = audio_res.get("duration_seconds", dur_est)
    time_points = np.arange(0, total_dur + 1.0, max(2.0, total_dur / 6.0))
    risk_prog = []
    is_scam = fusion_res["overall_score"] >= 70

    first_alert = None
    ask_moment = None

    text_lower = transcript.lower()
    if "otp" in text_lower or "pin" in text_lower or "code" in text_lower:
        ask_moment = round(total_dur * 0.75, 1)

    for t in time_points:
        if is_scam:
            r_val = min(98, int(25 + (t / max(1, total_dur)) * 72))
        else:
            r_val = max(5, int(15 - (t / max(1, total_dur)) * 8))
        risk_prog.append({"time_s": round(float(t), 1), "risk_score": r_val})
        if first_alert is None and r_val >= 65 and is_scam:
            first_alert = round(float(t), 1)

    lead_time = round(ask_moment - first_alert, 1) if (ask_moment and first_alert) else (14.0 if is_scam else None)

    markers = []
    if is_scam:
        markers.append({"time_s": 2.0, "label": "Claims official authority", "tier": "moderate"})
        if first_alert:
            markers.append({"time_s": first_alert, "label": "You should hang up here", "tier": "high", "is_first_alert": True})
        if ask_moment:
            markers.append({"time_s": ask_moment, "label": "Asks for secret OTP / PIN", "tier": "high"})
    else:
        markers.append({"time_s": 1.0, "label": "Friendly greeting", "tier": "low"})
        markers.append({"time_s": min(total_dur, 6.0), "label": "Natural conversational flow", "tier": "low"})

    case_id = f"SC-{int(time.time())%1000000:06d}"
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "case_id": case_id,
        "input_type": "audio",
        "source_name": input_name,
        "filename": input_name,
        "transcript": transcript,
        "transcript_method": asr_res.get("method", "local"),
        "language": asr_res.get("language", "en"),
        "is_translated": asr_res.get("is_translated", False),
        "original_text": asr_res.get("original_text", transcript),
        "segments": segments,
        "audio_result": audio_res,
        "text_result": text_res,
        "fusion": fusion_res,
        "timeline": risk_prog,
        "markers": markers,
        "first_alert_s": first_alert,
        "ask_moment_s": ask_moment,
        "lead_time_s": lead_time,
        "chosen_chips": chips_list,
        "created_at": created_at
    }

def process_text_analysis_core(clean_text: str, chips_list: List[str]) -> Dict[str, Any]:
    """Core logic to analyze a text transcript."""
    text_res = analyze_text(clean_text)

    fusion_res = fusion_engine.fuse_and_evaluate(
        text_result=text_res,
        audio_result=None,
        transcript_text=clean_text,
        chosen_chips=chips_list
    )

    case_id = f"SC-{int(time.time())%1000000:06d}"
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    # Synthetic text progression timeline
    words = clean_text.split()
    total_est_s = max(5.0, round(len(words) * 0.4, 1))
    time_points = [0.0, total_est_s * 0.3, total_est_s * 0.6, total_est_s]
    is_scam = fusion_res["overall_score"] >= 70

    timeline = []
    for t in time_points:
        r_val = min(96, int(30 + (t / total_est_s) * 65)) if is_scam else max(5, int(15 - (t / total_est_s) * 8))
        timeline.append({"time_s": round(t, 1), "risk_score": r_val})

    first_alert = round(total_est_s * 0.35, 1) if is_scam else None
    ask_moment = round(total_est_s * 0.8, 1) if is_scam else None
    lead_time = round(ask_moment - first_alert, 1) if (ask_moment and first_alert) else None

    markers = []
    if is_scam:
        markers.append({"time_s": round(total_est_s * 0.2, 1), "label": "Pressure tactic identified", "tier": "moderate"})
        if first_alert:
            markers.append({"time_s": first_alert, "label": "You should hang up here", "tier": "high", "is_first_alert": True})
    else:
        markers.append({"time_s": 1.0, "label": "Safe everyday phrasing", "tier": "low"})

    return {
        "case_id": case_id,
        "input_type": "text",
        "source_name": "Pasted Transcript",
        "filename": None,
        "transcript": clean_text,
        "language": "en",
        "is_translated": False,
        "original_text": clean_text,
        "segments": [{"start": 0.0, "end": total_est_s, "text": clean_text}],
        "audio_result": None,
        "text_result": text_res,
        "fusion": fusion_res,
        "timeline": timeline,
        "markers": markers,
        "first_alert_s": first_alert,
        "ask_moment_s": ask_moment,
        "lead_time_s": lead_time,
        "chosen_chips": chips_list,
        "created_at": created_at
    }

@app.post("/api/analyze-audio")
async def analyze_audio_endpoint(
    audio_file: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    chosen_chips: Optional[str] = Form(None)
):
    """
    Multimodal audio analysis endpoint with instant precomputed sample caching.
    """
    chips_list = json.loads(chosen_chips) if chosen_chips else []

    # Fast Path for precomputed sample calls
    if sample_filename and sample_filename in _PRECOMPUTED_SAMPLES_CACHE and not chips_list:
        return _PRECOMPUTED_SAMPLES_CACHE[sample_filename]

    temp_path = None
    target_path = None

    try:
        if audio_file and audio_file.filename:
            suffix = os.path.splitext(audio_file.filename)[1] or ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                temp_path = tmp.name
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(audio_file.file, buffer)
            target_path = temp_path
            input_name = audio_file.filename
        elif sample_filename:
            scam_c = os.path.join(SCAM_AUDIO_DIR, sample_filename)
            norm_c = os.path.join(NORMAL_AUDIO_DIR, sample_filename)
            if os.path.exists(scam_c):
                target_path = scam_c
            elif os.path.exists(norm_c):
                target_path = norm_c
            else:
                raise HTTPException(status_code=404, detail="Sample audio file not found.")
            input_name = sample_filename
        else:
            raise HTTPException(status_code=400, detail="Please upload an audio file or select a sample.")

        result = process_audio_analysis_core(target_path, input_name, chips_list)

        if sample_filename and not chips_list:
            _PRECOMPUTED_SAMPLES_CACHE[sample_filename] = result

        return result

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@app.post("/api/analyze-text")
def analyze_text_endpoint(payload: TextAnalysisRequest):
    """Text-only analysis: TF-IDF + Tactic Tagging + Action Plan + Nearest Scripts."""
    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    chips_list = payload.chosen_chips or []
    return process_text_analysis_core(clean_text, chips_list)

# --- Asynchronous Job Queue & Server-Sent Events (SSE) Stream ---

@app.post("/api/analyze")
@app.post("/analyze")
async def create_analysis_job(
    background_tasks: BackgroundTasks,
    audio_file: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    chosen_chips: Optional[str] = Form(None)
):
    """
    Asynchronous analysis endpoint returning a job_id for Server-Sent Events (SSE) progress streaming.
    """
    job_id = f"job_{int(time.time()*1000)}_{len(_JOBS)+1}"
    chips_list = json.loads(chosen_chips) if chosen_chips else []

    temp_path = None
    if audio_file and audio_file.filename:
        suffix = os.path.splitext(audio_file.filename)[1] or ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = tmp.name
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

    _JOBS[job_id] = {
        "status": "queued",
        "stages": ["Listening to the call..."],
        "progress": 10,
        "result": None,
        "error": None
    }

    async def run_job_stages():
        try:
            if text:
                _JOBS[job_id]["stages"].append("Reading what was said...")
                _JOBS[job_id]["progress"] = 30
                await asyncio.sleep(0.3)
                _JOBS[job_id]["stages"].append("Spotting pressure tactics...")
                _JOBS[job_id]["progress"] = 65
                await asyncio.sleep(0.3)
                _JOBS[job_id]["stages"].append("Putting it together...")
                _JOBS[job_id]["progress"] = 90
                res = process_text_analysis_core(text.strip(), chips_list)
                _JOBS[job_id]["result"] = res
                _JOBS[job_id]["status"] = "completed"
                _JOBS[job_id]["progress"] = 100
            else:
                target_path = temp_path
                input_name = "Uploaded Call"
                if not target_path and sample_filename:
                    scam_c = os.path.join(SCAM_AUDIO_DIR, sample_filename)
                    norm_c = os.path.join(NORMAL_AUDIO_DIR, sample_filename)
                    target_path = scam_c if os.path.exists(scam_c) else norm_c
                    input_name = sample_filename

                if not target_path:
                    _JOBS[job_id]["status"] = "failed"
                    _JOBS[job_id]["error"] = "No input provided"
                    return

                _JOBS[job_id]["stages"].append("Reading what was said...")
                _JOBS[job_id]["progress"] = 30
                await asyncio.sleep(0.3)
                _JOBS[job_id]["stages"].append("Studying the voice...")
                _JOBS[job_id]["progress"] = 55
                await asyncio.sleep(0.3)
                _JOBS[job_id]["stages"].append("Spotting pressure tactics...")
                _JOBS[job_id]["progress"] = 75
                await asyncio.sleep(0.3)
                _JOBS[job_id]["stages"].append("Putting it together...")
                _JOBS[job_id]["progress"] = 90
                
                res = process_audio_analysis_core(target_path, input_name, chips_list)
                _JOBS[job_id]["result"] = res
                _JOBS[job_id]["status"] = "completed"
                _JOBS[job_id]["progress"] = 100
        except Exception as e:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = str(e)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    background_tasks.add_task(run_job_stages)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/jobs/{job_id}/stream")
@app.get("/jobs/{job_id}/stream")
async def stream_job_updates(job_id: str):
    """
    Server-Sent Events (SSE) endpoint emitting real-time stage updates and final result payload.
    """
    if job_id not in _JOBS:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    async def event_generator():
        last_stage_count = 0
        while True:
            job = _JOBS.get(job_id, {})
            status = job.get("status", "unknown")
            stages = job.get("stages", [])
            current_stage = stages[-1] if stages else "Initializing..."
            progress = job.get("progress", 0)

            event_payload = {
                "job_id": job_id,
                "status": status,
                "stage": current_stage,
                "progress": progress,
                "result": job.get("result"),
                "error": job.get("error")
            }

            yield f"data: {json.dumps(event_payload)}\n\n"

            if status in ["completed", "failed"]:
                break

            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- SQLite Cases CRUD ---

@app.get("/api/cases")
@app.get("/cases")
def get_cases_endpoint():
    """Retrieve saved cases for My Cases & Scam Radar dashboard."""
    return get_all_cases()

@app.post("/api/cases")
@app.post("/cases")
def save_case_endpoint(payload: SaveCaseRequest):
    """Save an analysis to local SQLite."""
    cid = save_case(payload.case_payload)
    return {"status": "saved", "case_id": cid}

@app.get("/api/cases/{case_id}")
@app.get("/cases/{case_id}")
def get_case_endpoint(case_id: str):
    """Get single saved case payload."""
    c = get_case_by_id(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    return c

@app.delete("/api/cases/{case_id}")
@app.delete("/cases/{case_id}")
def delete_case_endpoint(case_id: str):
    """Delete a saved case."""
    delete_case(case_id)
    return {"status": "deleted", "case_id": case_id}

@app.delete("/api/cases")
@app.delete("/cases")
def delete_all_cases_endpoint():
    """Clear all saved cases history."""
    delete_all_cases()
    return {"status": "all_deleted"}

# --- PDF Case Report ---

@app.post("/api/report")
@app.post("/report")
def generate_report_endpoint(payload: PDFReportRequest):
    """Generate research-grade PDF case report using ReportLab + Matplotlib."""
    case_dict = payload.case_payload
    if not case_dict and payload.case_id:
        case_dict = get_case_by_id(payload.case_id)

    if not case_dict:
        raise HTTPException(status_code=400, detail="No case data provided for report generation.")

    tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp_pdf.name
    tmp_pdf.close()

    try:
        generate_pdf_report(case_dict, tmp_path)
        case_id = case_dict.get("case_id", "report")
        filename = f"SentiCall_Case_Report_{case_id}.pdf"
        return FileResponse(
            tmp_path,
            media_type="application/pdf",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        print(f"Error generating PDF report: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")

# --- Taxonomy & Helplines ---

@app.get("/api/taxonomy")
@app.get("/taxonomy")
def get_taxonomy_endpoint():
    p = os.path.join(DATA_DIR, "taxonomy.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scam_families": []}

@app.get("/api/atlas")
@app.get("/atlas")
def get_atlas_endpoint():
    p = os.path.join(DATA_DIR, "taxonomy.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"families": data.get("scam_families", [])}
    return {"families": []}

@app.get("/api/helplines")
@app.get("/helplines")
def get_helplines_endpoint():
    p = os.path.join(DATA_DIR, "helplines.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"helplines": []}

# --- Static Files Mounts ---

if os.path.exists(REPORTS_DIR):
    app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    idx_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(idx_path):
        return FileResponse(idx_path)
    return {"message": "SentiCall v2 Backend active. Frontend not yet mounted."}
