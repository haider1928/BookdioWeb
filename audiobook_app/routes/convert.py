from flask import Blueprint, request, url_for

from routes import error_response, success_response
from services.pdf_extractor import clean_text
from services.job_manager import create_job
from services.tts_engine import get_english_voices_sync, validate_voice

convert_bp = Blueprint("convert", __name__)


@convert_bp.post("/convert")
def convert_text():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("Request body must be valid JSON.", 400)

    text = clean_text(str(data.get("text", "")))
    voice = str(data.get("voice", "")).strip()
    speed = data.get("speed", "+0%")

    if not text:
        return error_response("Text content is required.", 400)
    if not voice:
        return error_response("Voice selection is required.", 400)

    try:
        voices = get_english_voices_sync()
    except Exception:
        return error_response("Failed to load voices from edge-tts.", 502)

    if not validate_voice(voice, voices):
        return error_response("Invalid voice selection.", 400)

    try:
        job = create_job(text, voice, speed)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception:
        return error_response("Unable to start conversion job.", 500)

    return success_response(
        {
            "job_id": job["job_id"],
            "status": job["status"],
            "chunks_done": job["chunks_done"],
            "chunks_total": job["chunks_total"],
            "preview_ready": job["preview_ready"],
            "status_url": url_for("status.get_status", job_id=job["job_id"]),
            "preview_url": url_for("preview.preview_audio", job_id=job["job_id"]),
            "download_url": url_for("download.download_file", job_id=job["job_id"]),
            "voice": job["voice"],
            "speed": job["speed"],
        },
        202,
    )
