from flask import Blueprint, request, url_for

from config import Config
from routes import error_response, success_response
from services.pdf_extractor import clean_text
from services.tts_engine import convert_text_to_mp3_sync, get_english_voices_sync, validate_voice

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
        result = convert_text_to_mp3_sync(text, voice, speed, Config.OUTPUT_FOLDER)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception:
        return error_response("Audio generation failed. Please try again.", 502)

    return success_response(
        {
            "filename": result["filename"],
            "download_url": url_for("download.download_file", filename=result["filename"]),
            "voice": result["voice"],
            "speed": result["speed"],
        }
    )
