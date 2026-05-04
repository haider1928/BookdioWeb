import asyncio
import edge_tts
from flask import Blueprint, Response, request
from routes import success_response, error_response
from config import Config

voices_bp = Blueprint("voices", __name__)


@voices_bp.route("/voices", methods=["GET"])
def get_voices():
    try:
        # Wrap async call with asyncio.run
        voices = asyncio.run(edge_tts.list_voices())
        
        # Group by gender and filter for English
        english_voices = [v for v in voices if "en-" in v["Locale"]]
        
        grouped = {
            "Female": [],
            "Male": [],
            "Neutral": []
        }
        
        for voice in english_voices:
            gender = voice.get("Gender", "Neutral")
            grouped[gender].append({
                "ShortName": voice["ShortName"],
                "FriendlyName": voice["FriendlyName"],
                "Locale": voice["Locale"]
            })
            
        return success_response({"voices": grouped})
    except Exception as e:
        return error_response(str(e))


async def _synthesize_preview(voice: str, speed: str, text: str) -> bytes:
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=speed,
        boundary="SentenceBoundary",
    )
    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])
    return bytes(audio_buffer)


@voices_bp.route("/voices/preview", methods=["POST"])
def preview_voice():
    data = request.get_json(silent=True) or {}
    voice = str(data.get("voice", "")).strip()
    speed = str(data.get("speed", "+0%")).strip() or "+0%"
    text = str(data.get("text", Config.VOICE_PREVIEW_TEXT)).strip() or Config.VOICE_PREVIEW_TEXT
    text = text[:Config.VOICE_PREVIEW_MAX_TEXT_CHARS]

    if not voice:
        return error_response("voice is required")

    try:
        audio_bytes = asyncio.run(_synthesize_preview(voice, speed, text))
        if not audio_bytes:
            return error_response("Failed to generate preview audio", 500)

        response = Response(audio_bytes, mimetype="audio/mpeg")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Voice-Preview"] = voice
        return response
    except Exception as exc:
        return error_response(str(exc), 500)
