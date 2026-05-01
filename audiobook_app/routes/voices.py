from flask import Blueprint

from routes import error_response, success_response
from services.tts_engine import get_english_voices_sync

voices_bp = Blueprint("voices", __name__)


@voices_bp.get("/voices")
def get_voices():
    try:
        voices = get_english_voices_sync()
    except Exception:
        return error_response("Failed to load voices from edge-tts.", 502)

    grouped = {"Female": [], "Male": [], "Neutral": []}
    for voice in voices:
        gender = str(voice.get("gender") or "Neutral").capitalize()
        if gender not in grouped:
            gender = "Neutral"
        grouped[gender].append(voice)

    return success_response({"voices": grouped})
