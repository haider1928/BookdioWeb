from flask import Blueprint, request
from routes import success_response, error_response
from services.job_manager import create_job
from config import Config

convert_bp = Blueprint("convert", __name__)


@convert_bp.route("/convert", methods=["POST"])
def convert():
    data = request.json
    if not data:
        return error_response("No data provided")
        
    text_chunks = data.get("text_chunks")
    voice = data.get("voice")
    speed = data.get("speed", "+0%")
    target_language = data.get("target_language", "en")
    
    if not text_chunks:
        return error_response("text_chunks is required")
    if not voice:
        return error_response("voice is required")
    
    if target_language == "ur":
        voice = Config.URDU_VOICES[0]
        
    try:
        job_info = create_job(text_chunks, voice, speed, target_language=target_language)
        return success_response(job_info)
    except Exception as e:
        return error_response(str(e))
