import asyncio
import edge_tts
from flask import Blueprint
from routes import success_response, error_response

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
