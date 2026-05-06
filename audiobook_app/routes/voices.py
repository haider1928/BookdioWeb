import asyncio
import edge_tts
from flask import Blueprint, Response, request
from routes import success_response, error_response
from config import Config

voices_bp = Blueprint("voices", __name__)

_voices_cache = None


@voices_bp.route("/voices", methods=["GET"])
def get_voices():
    global _voices_cache
    
    try:
        # Try to get from cache first
        if _voices_cache is not None:
            locale = request.args.get("locale", "en")
            return _format_voices(_voices_cache, locale)
        
        # Fetch from EdgeTTS API
        voices = asyncio.run(edge_tts.list_voices())
        
        # Cache the result
        _voices_cache = voices
        
        locale = request.args.get("locale", "en")
        return _format_voices(voices, locale)
        
    except Exception as e:
        # Fallback to hardcoded voices from config
        print(f"Warning: EdgeTTS API failed, using fallback: {e}")
        locale = request.args.get("locale", "en")
        return _format_fallback_voices(locale)


def _format_voices(voices, locale):
    if locale == "ur":
        target_voices = [v for v in voices if v["Locale"].startswith("ur-")]
    else:
        target_voices = [v for v in voices if v["Locale"].startswith("en-")]
    
    grouped = {"Female": [], "Male": [], "Neutral": []}
    
    for voice in target_voices:
        gender = voice.get("Gender", "Neutral")
        grouped[gender].append({
            "ShortName": voice["ShortName"],
            "FriendlyName": voice["FriendlyName"],
            "Locale": voice["Locale"]
        })
    
    return success_response({"voices": grouped})


def _format_fallback_voices(locale):
    """Fallback hardcoded voices when API fails"""
    fallback_en = [
        {"ShortName": "en-US-JennyNeural", "FriendlyName": "Jenny (US)", "Gender": "Female", "Locale": "en-US"},
        {"ShortName": "en-US-GuyNeural", "FriendlyName": "Guy (US)", "Gender": "Male", "Locale": "en-US"},
        {"ShortName": "en-GB-SoniaNeural", "FriendlyName": "Sonia (UK)", "Gender": "Female", "Locale": "en-GB"},
    ]
    fallback_ur = [
        {"ShortName": "ur-PK-AsadNeural", "FriendlyName": "Asad (Pakistan)", "Gender": "Male", "Locale": "ur-PK"},
        {"ShortName": "ur-PK-UzmaNeural", "FriendlyName": "Uzma (Pakistan)", "Gender": "Female", "Locale": "ur-PK"},
    ]
    
    voices = fallback_ur if locale == "ur" else fallback_en
    
    grouped = {"Female": [], "Male": [], "Neutral": []}
    for voice in voices:
        gender = voice.get("Gender", "Neutral")
        grouped[gender].append({
            "ShortName": voice["ShortName"],
            "FriendlyName": voice["FriendlyName"],
            "Locale": voice["Locale"]
        })
    
    return success_response({"voices": grouped})


async def _synthesize_preview(voice: str, speed: str, text: str) -> bytes:
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=speed,
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
